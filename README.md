# Multimodal RAG — trợ lý ảo e-learning

Nghiên cứu và phát triển trợ lý ảo thông minh tích hợp RAG đa phương thức cho hệ thống e-learning với học liệu dị chất (văn bản, hình ảnh, bảng, công thức, audio, video). Trợ lý course-aware, evidence-grounded: giải thích, tổng hợp, hướng dẫn ôn tập và hỗ trợ bài tập kèm nguồn (trang, slide, mốc thời gian) — không chỉ trả lời “nội dung nằm ở đâu trong video”.

Package: `multimodal-rag` **0.1.0**. CLI: `python -m app.main ingest|search|ask|stats|eval|rebuild-bm25` (also `multimodal-rag` after install).

## Architecture

```text
PDF/DOCX/PPTX ── Docling ── text chunks ── Qwen3-Embedding ── text_embeddings
                 └── images/pages ────── Qwen3-VL-Embedding ── visual_embeddings
TXT/MD ──────── chunking ────────────── Qwen3-Embedding ────── text_embeddings
Image ───────── Pillow + OCR ────────── text + VL embeddings
Video ───────── FFmpeg audio + Whisper transcript
            └── coarse frames (1 / 10s) → pHash / optional OCR / optional scenes
            └── representative frames only ── Qwen3-VL-Embedding ── visual_embeddings
            └── transcript windows ────────── Qwen3-Embedding ── text_embeddings
                                                      │
                                                 Retrieval
                                                      │
                                                  Reranker
                                                      │
                              Qwen3-1.7B / Qwen3-VL-2B-Instruct
```

Ingestion, retrieval, and generation are separate packages. `build_services()` always constructs a `GenerationService`, but the 1.7B chat weights load only on the first `ask` call (query rewrite, then generate). `ingest` / `search` / `stats` never load the LLM. Chroma uses two collections because Qwen3-Embedding and Qwen3-VL-Embedding are different vector spaces.

Qwen3-1.7B handles text-only answers and query planning. When retrieval returns a
PDF/PPTX/DOCX page or picture with a local image path, `ask` passes the top images
directly to Qwen3-VL-2B-Instruct together with the retrieved text context. Video
remains on the existing transcript/OCR path and is not sent to the VL answerer.

## Requirements

- Python 3.11 or 3.12 (not 3.14)
- Optional system packages:
  - Tesseract OCR
  - FFmpeg **and** ffprobe (video; missing either raises a clear `RuntimeError`)
  - LibreOffice (better DOCX VML/EMF images; text ingest works without it)

macOS (Homebrew):

```bash
brew install tesseract ffmpeg
```

Debian/Ubuntu:

```bash
sudo apt-get install tesseract-ocr ffmpeg
```

## Installation

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[all]"
cp .env.example .env
```

Install extras by need: `document`, `vision`, `video`, `generation`, `retrieval`, `eval`, `api`, `dev`. `pip install -e ".[generation]"` is enough for `ask` if embeddings and Chroma are already set up. Hybrid search needs `pip install -e ".[retrieval]"` (`rank-bm25`). Golden-set RAGAs scoring needs `pip install -e ".[eval]"`. `ingest` still needs `document` / `vision` / `video` as appropriate. The `video` extra includes `scenedetect` even though scene detection is off by default. HTTP API: `pip install -e ".[api]"` then `python -m app.api`. Next.js UI: see [docs/frontend-api.md](docs/frontend-api.md).

`.env` may include `HF_TOKEN` if you need Hub auth. If a token is set, **every** CLI command calls Hub `login` (`whoami-v2`). Do not hardcode tokens in source.

Run the CLI from the repo root. `project_root` is `Path.cwd()`.

## Command cheat sheet

Activate the venv, then run from the repo root. `ingest` / `search` / `stats` do not load the 1.7B LLM. `ask` does. The index only contains files you have ingested — it does **not** auto-load `./assets`. Check `python -m app.main stats` (and `data/index_manifest.json`) to see what is actually indexed.

```bash
# --- setup ---
source .venv/bin/activate
python -m app.main -h
python -m app.main ingest -h
python -m app.main search -h
python -m app.main ask -h
python -m app.main eval -h
python -m app.main stats

# --- ingest documents / slides (do this if stats only shows buoi_3.mp4) ---
python -m app.main ingest "./assets/test/bai_tap_chuong_3.docx"
python -m app.main ingest "./assets/test/Chuong_3_quan_he.pptx"
python -m app.main ingest "./assets/hethongquytrinhnghiepvu/chap01.pdf"
python -m app.main ingest "./assets/hethongquytrinhnghiepvu"
python -m app.main ingest "./assets/nhapmonbaomatvaanninhmang"
python -m app.main ingest "./assets/hethongquytrinhnghiepvu" --rechunk   # text/image only after CHUNK_SIZE_* change; skip video

# --- ingest video ---
python -m app.main ingest "./assets/test/buoi_3.mp4"
VIDEO_MAX_DURATION=60 python -m app.main ingest "./assets/test/buoi_3.mp4"   # smoke: first minute only
# faster remaining lectures (fewer VL frames, skip OCR):
#   VIDEO_MAX_REPRESENTATIVE_FRAMES=1 VIDEO_OCR_ENABLED=false python -m app.main ingest "./assets/test/buoi_3.mp4"

# --- ingest everything under assets (every video in the tree; can take days) ---
python -m app.main ingest ./assets

# --- search (no LLM) ---
python -m app.main search "Quan hệ phản xạ, đối xứng, bắc cầu trên tập {1,2,3,4}"
python -m app.main search "quan hệ" --text-only
python -m app.main search "Giảng viên nói gì ở đầu buổi học?" --text-only --source buoi_3.mp4
python -m app.main search "Giảng viên nói gì ở đầu buổi học?" --text-only --source assets/test/buoi_3.mp4 -k 8

# --- ask: documents / exercises (16GB: --text-only) ---
python -m app.main ask "link bài tập lý thuyết quan hệ" --text-only --show-hits
python -m app.main ask "Quan hệ phản xạ, đối xứng, bắc cầu trên tập {1,2,3,4}" --text-only --show-hits
python -m app.main ask "Giải thích quan hệ phản xạ và chỉ đường dẫn tài liệu, trang hoặc slide." --text-only --show-hits

# --- ask: lecture video (only works for content already ingested) ---
python -m app.main ask "Giảng viên giải thích quan hệ phản xạ, đối xứng, tương đương ở đoạn nào? Nêu mốc thời gian." --text-only --source buoi_3.mp4 --show-hits
python -m app.main ask "Giảng viên nói gì ở đầu buổi học? Ghi mốc thời gian và nguồn học liệu." --text-only --source buoi_3.mp4 --show-hits

# --- ask flags ---
python -m app.main ask "…" --text-only --no-enhance --show-hits   # raw query, no JSON planner
python -m app.main ask "…" --text-only --no-stream -k 8
python -m app.main ask "…" --show-hits                           # also searches visual_embeddings (loads 2B VL)

# --- after models are cached: skip Hub HEAD/404 noise ---
HF_HUB_OFFLINE=1 python -m app.main ask "Quan hệ phản xạ trên tập {1,2,3,4}" --text-only --show-hits

# --- eval (path recall/precision; optional RAGAs / 1.7B judge) ---
python -m app.main eval evals/golden.jsonl --text-only --retrieve-only --out evals/reports/baseline.json
python -m app.main eval evals/golden.jsonl --text-only --out evals/reports/baseline.json

# --- tests ---
pytest
SKIP_VIDEO=1 ./scripts/test_llm_by_type.sh
ONLY=docx,pdf ./scripts/test_llm_by_type.sh
SKIP_INGEST=1 ./scripts/test_llm_by_type.sh

# --- HTTP API (models stay in RAM; one worker) ---
python -m app.api
# or: uvicorn app.api.app:app --host 127.0.0.1 --port 8000 --workers 1
curl -s http://127.0.0.1:8000/health
curl -s http://127.0.0.1:8000/v1/stats
curl -s http://127.0.0.1:8000/v1/search -H 'Content-Type: application/json' \
  -d '{"query":"quan hệ phản xạ","text_only":true}'
curl -N http://127.0.0.1:8000/v1/ask -H 'Content-Type: application/json' \
  -d '{"query":"Giảng viên nói gì ở đầu buổi học?","text_only":true,"source":"buoi_3.mp4"}'
curl -s http://127.0.0.1:8000/v1/ask -H 'Content-Type: application/json' \
  -d '{"query":"quan hệ phản xạ","text_only":true,"stream":false}'
# play / download a cited file (Range-enabled):
curl -I http://127.0.0.1:8000/v1/files/assets/test/buoi_3.mp4
```

`--source` is a filename (`buoi_3.mp4`), a repo-relative file path, or a course folder (`assets/hethongquytrinhnghiepvu`). `--course` is the folder slug under `assets/`. `--show-hits` prints rewritten queries, RRF `score`, and dense `cosine`. `--text-only` skips visual retrieval and is recommended on M1 16GB for text-only questions. For PDF/PPTX visual questions, the service releases the text model before loading Qwen3-VL-2B-Instruct and sends up to three retrieved pages/images.

The HTTP API (`python -m app.api`) keeps embedding and LLM weights in one process. `POST /v1/ask` streams SSE events (`status`, `query`, `sources`, `delta`, `done`). Concatenate every `delta.text` for the answer; render Download/Watch from `sources.assets` (`download_url`, `watch_url`). Browsers must use `fetch` + `ReadableStream`, not `EventSource`. Video `watch_url` uses `#t=START,END`; PDFs use `#page=N`. Files are served from `GET /v1/files/{path}` under `assets/` or `storage/` only.

Full Next.js (App Router) handoff: [docs/frontend-api.md](docs/frontend-api.md).

## Environment variables

See `.env.example`. Defaults from `app/config/settings.py`:

| Variable | Default |
| --- | --- |
| `EMBEDDING_MODEL` | `Qwen/Qwen3-Embedding-0.6B` |
| `VL_EMBEDDING_MODEL` | `Qwen/Qwen3-VL-Embedding-2B` |
| `DEVICE` | `mps` (falls back to CPU if MPS/CUDA unavailable) |
| `CHUNK_SIZE` / `CHUNK_OVERLAP` | `500` / `50` (fallback when file type is unknown) |
| `CHUNK_SIZE_PDF` / `CHUNK_OVERLAP_PDF` | `350` / `60` |
| `CHUNK_SIZE_DOCX` / `CHUNK_OVERLAP_DOCX` | `350` / `60` |
| `CHUNK_SIZE_PPTX` / `CHUNK_OVERLAP_PPTX` | `280` / `40` |
| `CHUNK_SIZE_TXT` / `CHUNK_OVERLAP_TXT` | `500` / `50` (txt/md) |
| `TEXT_BATCH_SIZE` | `8` |
| `VL_BATCH_SIZE` | `1` |
| `WHISPER_MODEL` | `base` |
| `WHISPER_COMPUTE_TYPE` | `int8` (CPU; CTranslate2 has no MPS) |
| `VIDEO_SEGMENT_DURATION` | `30` |
| `VIDEO_COARSE_SAMPLE_INTERVAL` | `10` |
| `VIDEO_MAX_REPRESENTATIVE_FRAMES` | `3` |
| `VIDEO_FRAMES_PER_SEGMENT` | `3` (fallback stride if pHash selection returns nothing) |
| `VIDEO_FRAME_SIMILARITY_THRESHOLD` | `0.90` (pHash near-duplicate skip) |
| `VIDEO_MAX_DURATION` | empty (process the full video). `60` is smoke-test only |
| `TEXT_COLLECTION` | `text_embeddings` |
| `VISUAL_COLLECTION` | `visual_embeddings` |
| `VIDEO_OCR_ENABLED` | `true` (Tesseract on coarse frames at `VIDEO_OCR_INTERVAL`) |
| `VIDEO_OCR_INTERVAL` | `30` |
| `VIDEO_SCENE_ENABLED` | `false` (optional PySceneDetect) |
| `VIDEO_SCENE_THRESHOLD` | `27.0` |
| `OCR_REQUIRED` | `false` (OCR failure does not abort video ingest) |
| `RETRIEVER_K` | `5` |
| `GENERATION_K` | `8` (`ask` uses `max(RETRIEVER_K, GENERATION_K)` unless `-k` is set) |
| `RETRIEVER_FETCH_K` | `20` (dense/BM25 over-fetch before diversity) |
| `RETRIEVE_MAX_PER_FILE` | `2` |
| `HYBRID_SEARCH` | `true` (BM25 + dense fused with existing RRF) |
| `BM25_PATH` | `./data/bm25.pkl` (missing file → dense-only + warning) |
| `CONTEXT_EXPAND` | `true` (query-time parent/neighbor join, no extra embeddings) |
| `CONTEXT_COMPRESS` | `true` (extractive sentence overlap; no LLM compressor) |
| `RERANK_ENABLED` | `false` (`Qwen/Qwen3-Reranker-0.6B` stays off on 16GB) |
| `RERANK_MODEL` | `Qwen/Qwen3-Reranker-0.6B` |
| `COSINE_FALLBACK_THRESHOLD` | `0.15` (skip 1.7B and list known files if max cosine is lower) |
| `QUERY_HYDE` | `false` (HyDE paragraph RRF’d with original queries; never HyDE-only) |
| `MAX_RETRIEVE_LOOPS` | `0` (set `1` only if eval `weakest_metric` is context/path recall) |
| `LLM_MODEL` | `Qwen/Qwen3-1.7B` |
| `LLM_MAX_NEW_TOKENS` | `4096` |
| `LLM_ENABLE_THINKING` | `false` (keep off for ChatGPT-like answers) |
| `LLM_MAX_CONTEXT_CHARS` | `10000` |
| `LLM_DO_SAMPLE` | `false` |
| `VL_LLM_MODEL` | `Qwen/Qwen3-VL-2B-Instruct` |
| `VL_LLM_MAX_NEW_TOKENS` | `768` |
| `VL_MAX_IMAGES` | `3` |
| `QUERY_ENHANCE` | `true` (`ask` rewrites the question with 1.7B before retrieve; `search` does not) |
| `QUERY_ENHANCE_MAX_SUBQUERIES` | `3` |
| `QUERY_ENHANCE_MAX_NEW_TOKENS` | `256` |
| `QUERY_TASK` | Instruct prefix for **query** embeddings only (not stored chunks). Default: learner questions over e-learning course materials with evidence |
| `API_HOST` / `API_PORT` | `127.0.0.1` / `8000` (`python -m app.api`) |
| `API_CORS_ORIGINS` | `*` (comma-separated origins) |
| `API_KEY` | empty (open local PoC). If set, send `X-API-Key` on `/v1/ask`, `/v1/search`, `/v1/stats`. File URLs stay unauthenticated so `<video>` can play |

Selection score weights (code defaults; not all listed in `.env.example`): visual change `0.35`, OCR change `0.30`, scene boundary `0.20`, temporal coverage `0.15`.

Larger models are env-only upgrades, for example `Qwen/Qwen3-Embedding-4B` or `Qwen/Qwen3-VL-Embedding-8B`.

## Model setup

The first ingest/search downloads embedding models from Hugging Face into `~/.cache/huggingface/hub`. The first `ask` also downloads `Qwen/Qwen3-1.7B` there. Later commands **reuse those files**; they do not download the gigabytes again. Hub `404` lines (`sentence_bert_config.json`, `adapter_config.json`, …) are optional-file probes, not failed downloads. `Loading weights: N/N` is **disk → RAM/MPS** for that process.

Each `python -m app.main ask` is a new process, so weights still load from cache into memory (~5s for 1.7B on MPS). There is no persistent `chat` REPL. `python -m app.api` loads services once in the process lifespan; the first `/v1/ask` still loads 1.7B, then later requests reuse RAM. To skip Hub HEAD checks after the cache exists:

```bash
HF_HUB_OFFLINE=1 python -m app.main ask "Quan hệ phản xạ trên tập {1,2,3,4}" --text-only
```

Qwen embedding models are public. Text embeddings use `langchain_huggingface.HuggingFaceEmbeddings` with `trust_remote_code` and L2 normalize. Visual embeddings use Sentence Transformers (`Qwen/Qwen3-VL-Embedding-2B`). Text generation uses `ChatHuggingFace` with a patched tokenizer so `enable_thinking=False`; PDF/PPTX/DOCX visual answers use the Transformers multimodal interface for `Qwen/Qwen3-VL-2B-Instruct`.

On 16 GB Apple Silicon, keep the defaults. `ask --text-only` loads the 0.6B text embedder plus 1.7B text model. A visual PDF/PPTX question loads the 2B VL embedder for retrieval, releases the text model, and then loads Qwen3-VL-2B-Instruct for the answer. If MPS still runs out of memory: set `DEVICE=cpu`, `VL_BATCH_SIZE=1`, `VL_MAX_IMAGES=1`, or close other apps. Do not also switch to 4B/8B embeddings while generating.

## Running ingestion

PoC corpus is `./assets` (ingest in place). Start small:

```bash
python -m app.main ingest "./assets/test/bai_tap_chuong_3.docx"
python -m app.main ingest "./assets/hethongquytrinhnghiepvu/chap01.pdf"
python -m app.main ingest "./assets/hethongquytrinhnghiepvu"
python -m app.main ingest "./assets/test/Chuong_3_quan_he.pptx"
python -m app.main ingest "./assets/nhapmonbaomatvaanninhmang"
python -m app.main ingest "./assets/test/buoi_3.mp4"
```

`buoi_3.mp4` is ~716MB / ~3.4 hours. Ingest processes the **entire** lecture: Whisper on the full soundtrack, cheap coarse frames (default 1 every 10s via FFmpeg JPEG), then Qwen3-VL-Embedding only on a few representative frames per 30s window. Frame extraction is cheap; VL embedding is expensive.

A full Whisper pass on M1 16GB is still the long stage (CPU only). Default `WHISPER_COMPUTE_TYPE=int8` is much faster than float32. Checkpoints under `storage/videos/{sha256}/` reuse WAV + `transcript.json` if the job crashes (`video_pipeline_version=v2-long`). For a smoke test only:

```bash
VIDEO_MAX_DURATION=60 python -m app.main ingest "./assets/test/buoi_3.mp4"
```

If you already create timestamps with the MLX Whisper tool from the previous
project, save the result beside the video as `<video_stem>_segments.json`, for
example `buoi_1_segments.json`. RAG_DEMO detects this sidecar automatically,
normalizes its `start` / `end` / `text` records, and skips a second Whisper pass.
This is useful on Apple Silicon when `faster-whisper` is not installed in the
RAG_DEMO environment:

```bash
# Run once in the old project, using the MLX Whisper environment:
cd "/Users/VoThiXuanHoa/Downloads/UIT-Intelligent-virtual-assistant-integrating-multimodal-RAG-for-e-learning-systems"
source .venv/bin/activate
PYTHONPATH=src python -m edu_rag.cli transcribe \
  "/Users/VoThiXuanHoa/Documents/RAG project/RAG_DEMO/assets/cau_truc_roi_rac/buoi_1/buoi_1.mp4"

# Then ingest video + its timestamp sidecar in RAG_DEMO:
cd "/Users/VoThiXuanHoa/Documents/RAG project/RAG_DEMO"
source "/Users/VoThiXuanHoa/Downloads/rag_test/.venv311/bin/activate"
python -m app.main ingest "./assets/cau_truc_roi_rac/buoi_1"
```

That cap logs a **WARNING** and records `processed_duration=60`. Unset `VIDEO_MAX_DURATION` and ingest again to index the rest — the same file hash is **not** skipped while the cap is incomplete (`IndexManifest.is_video_complete`).

If you previously ingested with a 60s cap (or the old uniform-frame pipeline), run ingest again with the cap unset after pulling this code.

```bash
python -m app.main ingest "./assets/test/buoi_3.mp4"
python -m app.main stats
```

Re-running the same paths is safe. Unchanged files are skipped (`skipped_unchanged`) using SHA-256 of file bytes. Adding more files later:

```bash
python -m app.main ingest ./assets
python -m app.main rebuild-bm25
```

`rebuild-bm25` rebuilds the sparse sidecar from Chroma (no re-embed, no VL). Ingest also rebuilds it after new/changed files. If `data/bm25.pkl` is missing, search warns and stays dense-only.

## Running search

```bash
python -m app.main search "Quan hệ phản xạ, đối xứng, bắc cầu trên tập {1,2,3,4}"
python -m app.main search "quan hệ" --text-only
python -m app.main search "Giảng viên nói gì ở đầu buổi học?" --text-only --source buoi_3.mp4
python -m app.main search "lộ trình môn quy trình nghiệp vụ" --text-only --course hethongquytrinhnghiepvu
python -m app.main search "lộ trình" --text-only --source assets/hethongquytrinhnghiepvu
python -m app.main stats
```

The first query should retrieve Bài 5 from `bai_tap_chuong_3.docx` after that file is ingested.

`stats` prints collection counts, paths, `device`, embedding model name, and `llm_model` **without** loading LLM weights.

## Running ask (generation)

```bash
python -m app.main ask "link bài tập lý thuyết quan hệ" --text-only
python -m app.main ask "Quan hệ phản xạ, đối xứng, bắc cầu trên tập {1,2,3,4}" --text-only
python -m app.main ask "…" --no-stream -k 8
python -m app.main ask "…" --show-hits
python -m app.main ask "…" --text-only --no-enhance
python -m app.main ask "Giảng viên nói gì ở đầu buổi học?" --text-only --source buoi_3.mp4 --show-hits
python -m app.main ask "Tạo lộ trình môn quy trình nghiệp vụ, cho tôi tài liệu nếu có" --text-only --course hethongquytrinhnghiepvu --show-hits
```

Default `ask` streams tokens (thinking OFF, `max_new_tokens=4096`, `do_sample=False`). Before retrieval it runs **one short 1.7B JSON planner** (rewrite, optional sub-queries, optional step-back; planner uses 256 new tokens). The answer prompt still uses the original student question. `--no-enhance` searches the raw question. `--source` limits to a filename, file path, or **folder** (`assets/hethongquytrinhnghiepvu`). `--course` is the first folder under `assets/` (legacy vectors without a `course` field are prefix-matched). Multi-query dense + BM25 (and visual unless `--text-only`) are fused with RRF, then type prior, optional Qwen reranker (off by default), per-file diversity, parent expand, and extractive compress. `search` never loads the LLM. `QUERY_HYDE` and `MAX_RETRIEVE_LOOPS` stay off unless eval says context/path recall is the weakest metric. `--text-only` skips visual retrieval and is recommended on M1 16GB. `--no-stream` waits for the full answer. `--show-hits` prints rewritten queries, RRF `score`, and dense `cosine`.

Citations use project-relative paths already stored at index time (`relative_path`, then `filename`). The model is instructed not to invent `http://` URLs or print absolute local paths.

Smoke-test generation against each ingest kind (DOCX/PDF/PPTX from `assets/`, TXT/MD/PNG fixtures, optional video):

```bash
SKIP_VIDEO=1 ./scripts/test_llm_by_type.sh
ONLY=docx,pdf ./scripts/test_llm_by_type.sh
SKIP_INGEST=1 ./scripts/test_llm_by_type.sh
```

Logs: `tmp/llm_type_tests/`. Video case uses `VIDEO_MAX_DURATION=60`.

## ChromaDB layout

Persistent client at `./data/chroma` (`hnsw:space=cosine`, telemetry off):

```text
text_embeddings    PDF/DOCX/PPTX/TXT/MD/OCR/video transcript windows
visual_embeddings  images, page/slide renders, representative video frames
```

Binaries stay on disk under `storage/{documents,images,videos,frames,audio,tmp}`. Chroma stores embeddings, text, and path metadata only. Score is `1.0 - cosine_distance`.

Vector ids: `{sha256}:{kind}:{chunk_index}`.

| Kind in id | Metadata `content_type` | Notes |
| --- | --- | --- |
| `text` | `text` | RecursiveCharacterTextSplitter chunks |
| `text` | `video_segment` | Transcript windows; id still uses `text` |
| `text` | `text` | OCR sidecar strings at `chunk_index` 10000+ |
| `table` | `table` | Docling markdown tables |
| `image` | `image` | Pictures / standalone images |
| `page` | `page` | Slide/page renders |
| `video_frame` | `video_frame` | Selected frames; `chunk_index` is milliseconds (collision bump) |

Video `file_type` in Chroma metadata is still forced to `mp4` at index time.

## Supported file formats

- PDF, DOCX, PPTX via Docling (`do_ocr=False`; Tesseract only if no page has ≥40 native characters)
- TXT, Markdown (ATX headings become `section`)
- Images: png, jpg, jpeg, webp, gif, bmp, tiff / tif
- Video: mp4, mov, mkv, avi, webm, m4v

Skipped names: `.DS_Store`, `Thumbs.db`, and any file whose name starts with `.`.

## Dedup

- Same bytes, same or new path → skip (no extra vectors)
- Same video bytes with a shorter `processed_duration` (e.g. `VIDEO_MAX_DURATION=60`) → reindex, do not skip
- Same path, new bytes → delete old vectors **and** object-store prefixes, index the new hash
- Incomplete or old `video_pipeline_version` → delete Chroma vectors only; WAV/transcript checkpoints reuse when duration still matches
- Changing `CHUNK_SIZE_*` stores a `chunk_profile` on new text/image records. A different profile (or `ingest --rechunk`) deletes **text+visual vectors** for that document and reindexes; video is never rechunked this way. Missing profile does not auto-rechunk (baseline corpus stays until `--rechunk`)
- `ingest` prints `indexed`, `skipped_unchanged`, `reindexed_changed`, `failed` (exit 1 if any failed)

## Evaluation

Golden set: [evals/golden.jsonl](evals/golden.jsonl). Schema and metric mapping: [evals/README.md](evals/README.md).

```bash
python -m app.main eval evals/golden.jsonl --text-only --retrieve-only --out evals/reports/baseline.json
python -m app.main eval evals/golden.jsonl --text-only --out evals/reports/post-chunk.json
```

Default `--text-only`; reranker is forced off. `--retrieve-only` skips 1.7B (path recall/precision only). Full judge uses RAGAs if extra `eval` is installed, else the same 1.7B as a JSON scorer. Faithfulness &lt; 0.85 is a **warning**, not a CI fail.

After a baseline JSON exists, compare `path_precision` / context precision. If precision is weak, change `CHUNK_SIZE_*` and `ingest --rechunk` (then `rebuild-bm25`). Enable `QUERY_HYDE=true` or `MAX_RETRIEVE_LOOPS=1` **only** when `weakest_metric` is `context_recall` or `path_recall`.

## Tests

```bash
pytest
```

Default tests mock embedding models (`tests/conftest.py`). They cover IDs, Unicode NFC, file detection, chunking, Chroma, metadata flatten, OCR protocol, text loader, retrieval merge / RRF, query enhance parse, incremental ingest, image RGB, video windows / ffmpeg missing, frame selection, video indexing, capped-video reingest, generation format/think/service, eval harness, CLI parser.

Do not download 1.7B in unit tests. Integration against `assets/` is manual via the CLI.

## Troubleshooting

- **Python 3.14**: recreate the venv with 3.11/3.12
- **MPS OOM**: `DEVICE=cpu`, smaller batch, `ask --text-only`, do not load VL until images/video are ingested
- **ask ImportError / missing extra**: `pip install -e ".[generation]"` or `".[all]"`
- **Empty or think-only answer**: `LLM_ENABLE_THINKING` must stay `false`; the patched tokenizer is required
- **FFmpeg not found**: video ingest fails with a clear install message; documents still work
- **Tesseract not found**: install tesseract, or set `VIDEO_OCR_ENABLED=false`; text-native PDFs still ingest
- **DOCX VML image warnings**: optional LibreOffice; text still indexes
- **Gated Hub models**: set `HF_TOKEN` in `.env`
- **Silence after VL load**: `Loaded 1 prompt` is normal; the next stage is embedding. Look for `Embedding frames i/N` (and `[6/7]` / `[7/7]` on video ingest)
- **Hub 404 spam on ask**: expected optional-config probes; set `HF_HUB_OFFLINE=1` after the first successful download
- **ask reloads 1.7B every command**: cache is reused; RAM is not. That is process lifetime, not a re-download

## Future architecture

Interfaces exist so these can be swapped later without rewriting the pipeline: S3/MinIO object store, Qdrant/Milvus/pgvector, Qwen rerankers, unified VL collection if benchmarking supports it. Text generation uses Qwen3-1.7B, while document visual generation uses Qwen3-VL-2B-Instruct. Quantization, vLLM/Ollama, and a persistent `chat` REPL remain out of scope for this slice.

`app/processors/video.py` still contains an unused OpenCV uniform sampler (`sample_frames`). The live video path is FFmpeg coarse JPEGs plus `SemanticFrameSelectionStrategy`.
