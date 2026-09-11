from __future__ import annotations

import gc
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from app.config.settings import resolve_device
from app.generation.context import relative_path_for_hit
from app.models.retrieval import RetrievalResult

_VISUAL_CONTENT_TYPES = {"image", "page"}
_VISUAL_FILE_TYPES = {"pdf", "ppt", "pptx", "docx"}


class LocalQwenVLAnswerer:
    """Answer document questions by reading retrieved local page images."""

    def __init__(
        self,
        model_name: str,
        device: str,
        max_new_tokens: int = 768,
    ) -> None:
        try:
            import torch
            from transformers import AutoModelForMultimodalLM, AutoProcessor
        except ImportError as exc:
            raise RuntimeError(
                'Visual generation requires extra "generation". '
                'Install with: pip install -e ".[generation]" or pip install -e ".[all]"'
            ) from exc

        self.model_name = model_name
        self.device = resolve_device(device)
        self.max_new_tokens = max_new_tokens
        dtype = torch.float16 if self.device == "mps" else torch.float32

        import logging

        logging.getLogger(__name__).info(
            "Loading visual generation model %s on %s", model_name, self.device
        )
        self.processor = AutoProcessor.from_pretrained(model_name)
        model_kwargs: dict[str, Any] = {
            "trust_remote_code": True,
            "low_cpu_mem_usage": True,
        }
        try:
            self.model = AutoModelForMultimodalLM.from_pretrained(
                model_name, dtype=dtype, **model_kwargs
            )
        except TypeError:
            # Older Transformers releases use torch_dtype instead of dtype.
            self.model = AutoModelForMultimodalLM.from_pretrained(
                model_name, torch_dtype=dtype, **model_kwargs
            )
        if self.device in {"mps", "cuda"}:
            self.model.to(self.device)
        self.model.eval()

    @classmethod
    def valid_visual_results(
        cls,
        results: Sequence[RetrievalResult],
        max_images: int,
    ) -> list[RetrievalResult]:
        valid: list[RetrievalResult] = []
        for result in results:
            if result.content_type not in _VISUAL_CONTENT_TYPES:
                continue
            metadata = result.metadata or {}
            file_type = str(metadata.get("file_type") or "").lower().lstrip(".")
            if not file_type:
                file_type = Path(relative_path_for_hit(result)).suffix.lower().lstrip(".")
            if file_type not in _VISUAL_FILE_TYPES:
                continue
            image_path = Path(str(metadata.get("image_path") or ""))
            if image_path.is_file():
                valid.append(result)
            if len(valid) >= max_images:
                break
        return valid

    @staticmethod
    def _visual_description(index: int, result: RetrievalResult) -> str:
        metadata = result.metadata or {}
        source = relative_path_for_hit(result)
        page = metadata.get("page_number")
        location = f"trang/slide {page}" if page not in (None, "") else "hình ảnh"
        extracted = " ".join((result.content or "").split())
        suffix = f" Nội dung trích xuất kèm theo: {extracted}" if extracted else ""
        return f"[V{index}] {source}, {location}.{suffix}"

    @staticmethod
    def _text_context(results: Sequence[RetrievalResult]) -> str:
        parts: list[str] = []
        index = 0
        for result in results:
            if result.content_type in _VISUAL_CONTENT_TYPES:
                continue
            text = " ".join((result.content or "").split())
            if not text:
                continue
            index += 1
            metadata = result.metadata or {}
            source = relative_path_for_hit(result)
            page = metadata.get("page_number")
            location = f" p.{page}" if page not in (None, "") else ""
            parts.append(f"[T{index}] {source}{location}\n{text}")
        return "\n\n".join(parts) or "(không có text context)"

    def answer(
        self,
        question: str,
        results: Sequence[RetrievalResult],
        *,
        max_images: int = 3,
    ) -> str:
        visual_results = self.valid_visual_results(results, max_images)
        if not visual_results:
            return "Mình không tìm thấy ảnh trang/slide phù hợp trong tài liệu."

        content: list[dict[str, Any]] = []
        visual_notes: list[str] = []
        for index, result in enumerate(visual_results, start=1):
            image_path = str(Path(str(result.metadata["image_path"])).resolve())
            content.append({"type": "image", "image": image_path})
            visual_notes.append(self._visual_description(index, result))

        prompt = (
            "Bạn là trợ lý học tập môn Cấu trúc rời rạc. Hãy trả lời bằng tiếng Việt. "
            "Đọc trực tiếp các ảnh trang/slide được cung cấp, đồng thời dùng TEXT CONTEXT "
            "nếu có. Chỉ kết luận điều nhìn thấy hoặc có trong context; nếu ảnh mờ hoặc "
            "thiếu dữ liệu, hãy nói rõ. Trích dẫn ảnh bằng [V1], [V2] và văn bản bằng "
            "[T1], [T2]. Không bịa nội dung hay nguồn.\n\n"
            "CÁC ẢNH ĐƯỢC TRUY XUẤT:\n"
            + "\n".join(visual_notes)
            + "\n\nTEXT CONTEXT:\n"
            + self._text_context(results)
            + f"\n\nCÂU HỎI: {question}"
        )
        content.append({"type": "text", "text": prompt})
        messages = [{"role": "user", "content": content}]

        try:
            from qwen_vl_utils import process_vision_info
        except ImportError as exc:
            raise RuntimeError(
                "Thiếu qwen-vl-utils. Hãy chạy: pip install -e \".[generation]\""
            ) from exc

        text = self.processor.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
        )
        image_inputs, video_inputs = process_vision_info(messages)
        inputs = self.processor(
            text=[text],
            images=image_inputs,
            videos=video_inputs,
            padding=True,
            return_tensors="pt",
        )
        inputs = inputs.to(self.device)
        import torch

        with torch.inference_mode():
            output_ids = self.model.generate(
                **inputs,
                max_new_tokens=self.max_new_tokens,
                do_sample=False,
            )
        input_length = inputs["input_ids"].shape[-1]
        generated_ids = output_ids[:, input_length:]
        return self.processor.batch_decode(
            generated_ids,
            skip_special_tokens=True,
            clean_up_tokenization_spaces=False,
        )[0].strip()

    def close(self) -> None:
        model = getattr(self, "model", None)
        self.model = None
        self.processor = None
        if model is not None:
            del model
        gc.collect()
        try:
            import torch

            if torch.backends.mps.is_available():
                torch.mps.empty_cache()
        except (ImportError, AttributeError):
            pass
