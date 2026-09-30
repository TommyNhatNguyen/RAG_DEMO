from __future__ import annotations

import json
import logging
import shutil
import time
from pathlib import Path

from app.chunking.video_chunker import assign_pieces_to_windows, build_time_windows
from app.config.settings import Settings
from app.ids import nfc, relative_posix, vector_id
from app.loaders.base import LoadedVideo
from app.models.video import VideoAsset, VideoSegment
from app.processors.audio import extract_audio
from app.processors.frame_selection import (
    FrameCandidate,
    SemanticFrameSelectionStrategy,
    hash_file,
)
from app.processors.ocr import NullOCR, OCREngine
from app.processors.scene_detection import detect_scene_timestamps
from app.processors.video_checkpoint import VIDEO_PIPELINE_VERSION, VideoCheckpoint
from app.processors.video_frames import sample_coarse_frames
from app.processors.video_metadata import probe_video
from app.progress import log_progress
from app.storage.local import LocalFilesystemStore

logger = logging.getLogger(__name__)


class VideoLoader:
    def __init__(
        self,
        settings: Settings,
        object_store: LocalFilesystemStore,
        ocr: OCREngine | None = None,
    ) -> None:
        self.settings = settings
        self.object_store = object_store
        self.ocr = ocr or NullOCR()
        self._whisper = None
        self.last_stats: dict = {}

    def _whisper_model(self):
        if self._whisper is not None:
            return self._whisper
        from faster_whisper import WhisperModel

        compute_type = self.settings.whisper_compute_type
        logger.info(
            "Loading faster-whisper model %s on cpu compute_type=%s",
            self.settings.whisper_model,
            compute_type,
        )
        self._whisper = WhisperModel(
            self.settings.whisper_model,
            device="cpu",
            compute_type=compute_type,
        )
        return self._whisper

    def load(self, path: Path, document_id: str) -> LoadedVideo:
        started = time.perf_counter()
        storage = self.settings.resolve_path(self.settings.storage_root)
        relative = relative_posix(path, self.settings.project_root)
        meta = probe_video(path)
        probed = meta.duration_seconds
        max_dur = self.settings.video_max_duration
        processed = probed
        if max_dur is not None and probed > max_dur:
            logger.warning(
                "VIDEO_MAX_DURATION=%.1fs caps probed duration %.1fs for %s (smoke/test only)",
                max_dur,
                probed,
                path.name,
            )
            processed = max_dur

        logger.info(
            "[1/7] Video metadata id=%s duration=%.1fs processed=%.1fs %sx%s fps=%s audio=%s",
            document_id[:12],
            probed,
            processed,
            meta.width,
            meta.height,
            meta.fps,
            meta.has_audio,
        )

        work_dir = storage / "videos" / document_id
        work_dir.mkdir(parents=True, exist_ok=True)
        checkpoint = VideoCheckpoint(work_dir / "checkpoint.json")
        transcript_path = work_dir / "transcript.json"
        wav_path = storage / "audio" / f"{document_id}.wav"
        tmp_dir = storage / "tmp" / document_id / "candidates"
        frames_dir = storage / "frames" / document_id

        usable = checkpoint.matches(document_id, processed)
        if not usable:
            if wav_path.exists():
                wav_path.unlink()
            if transcript_path.exists():
                transcript_path.unlink()
            if tmp_dir.exists():
                shutil.rmtree(tmp_dir, ignore_errors=True)
            checkpoint.data = {}
            checkpoint.update(
                video_id=document_id,
                pipeline_version=VIDEO_PIPELINE_VERSION,
                stage="metadata",
                probed_duration=probed,
                processed_duration=processed,
            )

        checkpoint.update(
            video_id=document_id,
            pipeline_version=VIDEO_PIPELINE_VERSION,
            probed_duration=probed,
            processed_duration=processed,
        )

        timings: dict[str, float] = dict(checkpoint.data.get("timings") or {})

        t0 = time.perf_counter()
        logger.info("[2/7] Extracting audio")
        extract_audio(
            path,
            wav_path,
            max_duration=max_dur,
            reuse=usable and checkpoint.reached("audio"),
        )
        timings["audio"] = timings.get("audio") or (time.perf_counter() - t0)
        checkpoint.update(stage="audio", timings=timings)

        t0 = time.perf_counter()
        logger.info("[3/7] Transcribing audio")
        pieces = self._load_or_transcribe(
            path,
            transcript_path,
            wav_path,
            processed,
            usable and checkpoint.reached("transcript"),
        )
        timings["transcription"] = timings.get("transcription") or (time.perf_counter() - t0)
        checkpoint.update(stage="transcript", timings=timings)

        t0 = time.perf_counter()
        logger.info("[4/7] Sampling frames")
        coarse = self._load_or_sample_frames(
            path,
            tmp_dir,
            interval=self.settings.video_coarse_sample_interval,
            max_duration=max_dur,
            duration=processed,
            reuse=usable and checkpoint.reached("coarse_frames"),
        )
        timings["frame_sampling"] = timings.get("frame_sampling") or (time.perf_counter() - t0)
        checkpoint.update(stage="coarse_frames", candidate_count=len(coarse), timings=timings)

        windows = build_time_windows(processed, self.settings.video_segment_duration)
        transcripts = assign_pieces_to_windows(pieces, windows)
        segments = [
            VideoSegment(
                id=vector_id(document_id, "video_segment", index),
                video_id=document_id,
                start_time=start,
                end_time=end,
                transcript=transcripts[index] if index < len(transcripts) else "",
                metadata={"chunk_index": index},
            )
            for index, (start, end) in enumerate(windows)
        ]

        t0 = time.perf_counter()
        logger.info("[5/7] Selecting representative frames")
        candidates = self._build_candidates(coarse, path)
        selected_map = SemanticFrameSelectionStrategy().select(candidates, segments, self.settings)
        selected_count = self._persist_selected(segments, selected_map, frames_dir)
        timings["frame_filtering"] = timings.get("frame_filtering") or (time.perf_counter() - t0)
        checkpoint.update(stage="selected", selected_count=selected_count, timings=timings)

        reduction = 0.0
        if coarse:
            reduction = 100.0 * (1.0 - selected_count / max(len(coarse), 1))
        elapsed = time.perf_counter() - started
        logger.info(
            "[stats] duration=%.1fs candidates=%s selected=%s reduction=%.1f%% text_segments=%s elapsed=%.1fs",
            processed,
            len(coarse),
            selected_count,
            reduction,
            sum(1 for seg in segments if seg.transcript),
            elapsed,
        )
        self.last_stats = {
            "processed_duration": processed,
            "probed_duration": probed,
            "candidate_frames": len(coarse),
            "selected_frames": selected_count,
            "reduction_pct": reduction,
            "checkpoint_path": str(checkpoint.path),
            "video_pipeline_version": VIDEO_PIPELINE_VERSION,
        }
        full_transcript = " ".join(p["text"] for p in pieces).strip()
        asset = VideoAsset(
            id=document_id,
            source=str(path.resolve()),
            file_name=nfc(path.name),
            relative_path=relative,
            duration=processed,
            metadata=dict(self.last_stats),
        )
        return LoadedVideo(asset=asset, segments=segments, full_transcript=full_transcript)

    def _load_or_transcribe(
        self,
        video_path: Path,
        transcript_path: Path,
        wav_path: Path,
        duration: float,
        reuse: bool,
    ) -> list[dict]:
        if reuse and transcript_path.exists():
            logger.info("Reusing transcript checkpoint %s", transcript_path.name)
            return json.loads(transcript_path.read_text(encoding="utf-8"))
        sidecar = self._find_timestamp_sidecar(video_path)
        if sidecar is not None:
            pieces = self._read_timestamp_sidecar(sidecar, duration)
            transcript_path.write_text(json.dumps(pieces, ensure_ascii=False), encoding="utf-8")
            logger.info("Loaded timestamp transcript sidecar %s (%s segments)", sidecar.name, len(pieces))
            return pieces
        pieces = self._transcribe(wav_path, duration)
        transcript_path.write_text(json.dumps(pieces, ensure_ascii=False), encoding="utf-8")
        return pieces

    @staticmethod
    def _find_timestamp_sidecar(video_path: Path) -> Path | None:
        candidates = (
            video_path.with_name(f"{video_path.stem}_segments.json"),
            video_path.with_name(f"{video_path.stem}.segments.json"),
        )
        return next((candidate for candidate in candidates if candidate.is_file()), None)

    @staticmethod
    def _read_timestamp_sidecar(sidecar: Path, duration: float) -> list[dict]:
        payload = json.loads(sidecar.read_text(encoding="utf-8"))
        raw_segments = payload.get("segments", []) if isinstance(payload, dict) else payload
        if not isinstance(raw_segments, list):
            raise ValueError(f"Timestamp sidecar must contain a list in 'segments': {sidecar}")

        pieces: list[dict] = []
        for item in raw_segments:
            if not isinstance(item, dict):
                continue
            text = str(item.get("text", "")).strip()
            if not text:
                continue
            start = max(0.0, float(item.get("start", 0.0)))
            end = max(start, float(item.get("end", start)))
            if duration > 0:
                start = min(start, duration)
                end = min(end, duration)
            pieces.append({"start": start, "end": end, "text": text})
        return pieces

    def _transcribe(self, audio_path: Path, duration: float) -> list[dict]:
        try:
            model = self._whisper_model()
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "Video transcription requires faster-whisper, or a timestamp sidecar "
                "named '<video>_segments.json' beside the video."
            ) from exc
        language = self.settings.whisper_language or None
        segments, info = model.transcribe(str(audio_path), language=language)
        logger.info(
            "Whisper language=%s (forced=%s) probability=%.2f",
            info.language,
            language is not None,
            getattr(info, "language_probability", 0.0) or 0.0,
        )
        pieces: list[dict] = []
        last_pct = -10
        for seg in segments:
            text = (seg.text or "").strip()
            if not text:
                continue
            end = float(seg.end)
            pieces.append({"start": float(seg.start), "end": end, "text": text})
            if duration > 0:
                pct = 100.0 * min(end, duration) / duration
                if pct - last_pct >= 10:
                    logger.info("Transcribing audio: %.0f%%", pct)
                    last_pct = pct
        logger.info("Transcript segments: %s", len(pieces))
        return pieces

    def _load_or_sample_frames(
        self,
        video_path: Path,
        tmp_dir: Path,
        *,
        interval: float,
        max_duration: float | None,
        duration: float | None,
        reuse: bool,
    ) -> list[tuple[float, Path]]:
        existing = sorted(tmp_dir.glob("candidate_*.jpg")) if tmp_dir.exists() else []
        if reuse and existing:
            logger.info("Reusing %s coarse candidate frames", len(existing))
            return [(index * interval, path) for index, path in enumerate(existing)]
        return sample_coarse_frames(
            video_path,
            tmp_dir,
            interval=interval,
            max_duration=max_duration,
            duration=duration,
        )

    def _build_candidates(
        self,
        coarse: list[tuple[float, Path]],
        video_path: Path,
    ) -> list[FrameCandidate]:
        scene_times: list[float] = []
        if self.settings.video_scene_enabled:
            t0 = time.perf_counter()
            scene_times = detect_scene_timestamps(
                video_path,
                self.settings.video_scene_threshold,
                max_duration=self.settings.video_max_duration,
            )
            logger.info("Scene detection %.1fs", time.perf_counter() - t0)

        ocr_interval = self.settings.video_ocr_interval if self.settings.video_ocr_enabled else 0.0
        candidates: list[FrameCandidate] = []
        last_ocr_at = -1e9
        total = len(coarse)
        started = time.perf_counter()
        prev = 0
        if self.settings.video_ocr_enabled and total:
            log_progress(logger, "OCR frames", 0, total, started=started)
        for index, (timestamp, path) in enumerate(coarse, start=1):
            phash = hash_file(str(path))
            ocr_text = ""
            if ocr_interval > 0 and (timestamp - last_ocr_at) >= ocr_interval:
                try:
                    ocr_text = self.ocr.extract_text(path) or ""
                    last_ocr_at = timestamp
                except Exception:
                    logger.exception("OCR failed for frame t=%.1fs; continuing", timestamp)
                    if self.settings.ocr_required:
                        raise
            is_scene = any(abs(timestamp - stamp) <= self.settings.video_coarse_sample_interval / 2 for stamp in scene_times)
            candidates.append(
                FrameCandidate(
                    timestamp=timestamp,
                    path=str(path),
                    phash=phash,
                    ocr_text=ocr_text,
                    is_scene_boundary=is_scene,
                )
            )
            if self.settings.video_ocr_enabled and total:
                log_progress(logger, "OCR frames", index, total, started=started, prev=prev)
                prev = index
        return candidates

    def _persist_selected(
        self,
        segments: list[VideoSegment],
        selected_map: dict[str, list[FrameCandidate]],
        frames_dir: Path,
    ) -> int:
        if frames_dir.exists():
            shutil.rmtree(frames_dir, ignore_errors=True)
        frames_dir.mkdir(parents=True, exist_ok=True)
        count = 0
        for segment in segments:
            chosen = selected_map.get(segment.id) or []
            paths: list[str] = []
            stamps: list[float] = []
            ocrs: list[str] = []
            for candidate in chosen:
                dest = frames_dir / f"t{int(round(candidate.timestamp * 1000)):09d}.jpg"
                src = Path(candidate.path)
                if src.exists():
                    shutil.copy2(src, dest)
                    paths.append(str(dest))
                    stamps.append(candidate.timestamp)
                    ocrs.append(candidate.ocr_text)
                    count += 1
            segment.frame_paths = paths
            segment.frame_timestamps = stamps
            segment.ocr_texts = ocrs
        return count
