# Handoff: RAG production checklist vs this codebase

**Audience:** another AI that will write an implementation plan (or implement).  
**Do not rewrite the stack.** Fit the 16 techniques into the existing package.  
**Source article:** https://www.sapotacorp.vn/blog/rag-production-checklist-16-techniques (SapotaCorp, 2026-08-25)

This file is self-contained. Read it, then inspect the cited files. The article’s own rule: **do not deploy all 16**. Instrument, measure, apply the technique that targets the weakest metric.

---

## 1. What this project is

Package `multimodal-rag` **0.1.0**. E-learning virtual assistant: course-aware, evidence-grounded RAG over heterogeneous materials (PDF, DOCX, PPTX, images, tables, formulas, audio/transcript, video). Answers must cite path / page / slide / timestamps. Vietnamese UI prompts.

- CLI: `python -m app.main ingest|search|ask|stats`
- HTTP: `python -m app.api` (FastAPI, SSE on `/v1/ask`)
- Hardware target: **Apple Silicon 16GB** (M1). Default `ask` is `--text-only` so Qwen3-VL-2B stays unloaded.
- Python 3.11 or 3.12. Extras: `document`, `vision`, `video`, `generation`, `api`, `dev`, `all`.

Existing architecture notes (do not contradict):

- [README.md](../README.md)
- [rag_multimodal_improvements.md](../rag_multimodal_improvements.md) (wishlist, partially already done: RRF, flattened Chroma metadata)
- [docs/frontend-api.md](frontend-api.md) (Next.js is **not** in-repo; API contract only)

---

## 2. Current architecture (as implemented)

```
PDF/DOCX/PPTX ── Docling ── text chunks ── Qwen3-Embedding-0.6B ── text_embeddings
                 └── page/picture images ── Qwen3-VL-Embedding-2B ── visual_embeddings
TXT/MD ──────── RecursiveCharacterTextSplitter ── text embedder
Image ───────── Pillow + OCR ── text + VL
Video ───────── FFmpeg + Whisper ── 30s transcript windows ── text embedder
            └── representative frames ── VL embedder
                                                      │
                                    MultimodalRetriever (dense only)
                                    RRF across multi-query + text/visual lists
                                    TypePriorReranker (tiny score bonus, NOT a cross-encoder)
                                                      │
                                    Qwen3-1.7B (thinking OFF)
                                    Visual hits → OCR/caption/transcript text only
                                    Images are NOT sent into the chat model
```

Wiring: `build_services()` in `app/factory.py`. GenerationService is always constructed; 1.7B loads on first `ask`. `ingest` / `search` / `stats` never load the LLM.

Two Chroma collections because text and VL are **different vector spaces**. Persistent path `./data/chroma`, `hnsw:space=cosine`. Score = `1.0 - cosine_distance`. Vector ids: `{sha256}:{kind}:{chunk_index}`.

### 2.1 Key modules

| Area | Path | Role |
|------|------|------|
| Settings | `app/config/settings.py` | Pydantic Settings + `.env` |
| Ingest | `app/pipeline/ingestion.py` | Walk files, hash skip, load → chunk → index |
| Index | `app/pipeline/indexing.py` | `base_metadata`, write Chroma |
| Chunk text | `app/chunking/text_chunker.py` | RecursiveCharacterTextSplitter 500/50 **chars** |
| Chunk video | `app/chunking/video_chunker.py` | Fixed 30s windows; Whisper pieces assigned by start time |
| Vector store | `app/vectorstore/chroma.py` | add/search/get/delete; `flatten_metadata` primitives only |
| Retrieve | `app/retrieval/retriever.py` | Dense search, multi-query, `source_where`, RRF, rerank |
| Fusion | `app/retrieval/merger.py` | `rrf_merge` (RRF_K=60) |
| Rerank | `app/retrieval/reranker.py` | `ScoreReranker`, `TypePriorReranker`; placeholder `Reranker` for Qwen later |
| Query plan | `app/generation/query_enhance.py` | JSON `{rewritten, subqueries, step_back}`; **forbids HyDE** |
| Generate | `app/generation/service.py` | enhance → retrieve → `format_hits` → stream answer |
| Context | `app/generation/context.py` | Cap `LLM_MAX_CONTEXT_CHARS=10000` |
| Prompt | `app/generation/prompts.py` | Vietnamese e-learning, no invented homework, relative paths only |
| API | `app/api/app.py`, `app/api/schemas.py` | `/v1/ask`, `/v1/search`, `/v1/stats`, `/v1/files/{path}` |
| Tests | `tests/` | Mock embeddings/LLM; do not download 1.7B |

### 2.2 Defaults (`app/config/settings.py`)

- `CHUNK_SIZE=500`, `CHUNK_OVERLAP=50`
- `RETRIEVER_K=5`, `GENERATION_K=8` (`ask` uses `max` of both unless `-k`)
- `QUERY_ENHANCE=true`, max 3 subqueries, 256 new tokens
- `LLM_MODEL=Qwen/Qwen3-1.7B`, `LLM_ENABLE_THINKING=false`, `LLM_MAX_NEW_TOKENS=4096`
- `EMBEDDING_MODEL=Qwen/Qwen3-Embedding-0.6B`
- `VL_EMBEDDING_MODEL=Qwen/Qwen3-VL-Embedding-2B`
- `VIDEO_SEGMENT_DURATION=30`
- `WHISPER_COMPUTE_TYPE=int8`
- `API` ask schema defaults `text_only=true`

### 2.3 Retrieval flow today (`MultimodalRetriever.search`)

1. `process_user_query` (NFC, collapse whitespace).
2. If `EnhancedQuery` present: text queries = rewritten + subqueries + step_back; visual query = rewritten.
3. Dense search each text query on `text_embeddings` with optional `where`.
4. Dense VL search on `visual_embeddings` unless `--text-only`.
5. `rrf_merge` all groups.
6. `TypePriorReranker` (lecture cues boost `video_segment` / `video_frame` by 0.02/0.01).
7. Truncate to `k`.

`source_where(source)`: if path-like → `{relative_path: ...}` else `{filename: ...}`. **Only filter today.**

### 2.4 Metadata already on vectors (`base_metadata`)

`document_id`, `source`, `file_name`, `filename`, `relative_path`, `file_type`, `content_type`, `chunk_index`, plus extras: `page_number`, `section`, video `start_time`/`end_time`/`timestamp`.

Chroma metadata **must** be `str|int|float|bool` (`flatten_metadata`). No lists.

### 2.5 Query enhance (already agentic-lite)

Same 1.7B, short JSON planner. Answer still uses **original** student question. Prompt explicitly: do not invent exam questions, **do not write a fake answer (no HyDE)**.

```json
{"rewritten":"...","subqueries":[],"step_back":""}
```

### 2.6 What is NOT implemented

BM25 / sparse hybrid, parent-child index, sentence-window expand, cross-encoder, contextual compression (beyond char truncate), RAGAs, LLM-as-judge, golden set, iterative retrieve loop, ColBERT, ColPali, CLIP, embedding/LLM binary quantization, in-repo frontend.

---

## 3. The 16 techniques (from the article)

### Part 1 — retrieval

1. **Calibrate chunk size/overlap per document type.** Not a global 512. Dense regulatory: 256–384 tokens, 15–20% overlap. Narrative: 512–768, lower overlap.
2. **Parent-child chunking.** Index small children; pass parent text to the LLM.
3. **Hybrid search (dense + sparse).** BM25 + vectors, fuse with RRF. Especially important for exact terms, codes, Vietnamese domain vocabulary. Article claims +8–15 precision@5 vs dense-only.
4. **HyDE.** LLM writes a hypothetical document, embed that, search. Helps short/underspecified queries.
5. **Sentence-window retrieval.** Retrieve on sentence; expand ±2 sentences for generation.
6. **Metadata filter before vector search.** Product / department / date / language. Stops cross-document contamination. Multi-tenant security requirement.
7. **Cross-encoder rerank.** Retrieve 20–50, rerank to top 5. Article used `cross-encoder/ms-marco-MiniLM-L-6-v2`. Claims +10–20% answer quality.
8. **Contextual compression.** Drop irrelevant sentences in retrieved chunks before the LLM. Article used LangChain `LLMChainExtractor`.

### Part 2 — evaluation

9. **RAGAs:** faithfulness, answer relevancy, context precision, context recall. Golden set 50–100 queries. Faithfulness &lt; 0.85 = release block in their practice.
10. **LLM-as-judge** for completeness/tone; sample production queries.
11. **Iterative optimization loop.** Map metric → likely root cause → fix → re-eval. Context precision ↓ → chunking/filters. Faithfulness ↓ → prompt/compression.

### Part 3 — architecture

12. **Agentic query decomposition.** Split compound questions; retrieve per sub-question; synthesize.
13. **Iterative retrieval with self-reflection.** Loop until the model says it has enough, or max iterations.
14. **ColBERT late-interaction.** High-precision, higher latency/RAM. Article used RAGatouille / colbertv2.
15. **Multimodal retrieval.** ColPali (PDF as images) or CLIP shared space. This repo already uses Qwen3-VL on pages/frames — **do not replace**.
16. **Binary quantization.** 32× smaller index, first-pass filter + full-precision rerank. For large-scale latency, not this PoC corpus.

Article start set: hybrid, parent-child, reranking, RAGAs. Rest is a menu.

---

## 4. Gap map (decision table)

| # | Technique | Current | Decision for this repo |
|---|-----------|---------|-------------------------|
| 1 | Per-type chunk size | Global 500/50 chars | **Phase 2** after eval. Requires text reingest. |
| 2 | Parent-child | None | **Phase 1** query-time expand (no new embeddings). |
| 3 | Hybrid BM25+dense | Dense + multimodal RRF only | **Phase 1** BM25 sidecar on **text** collection. |
| 4 | HyDE | Explicitly forbidden in enhance prompt | **Default off.** Optional later; never invent homework. |
| 5 | Sentence-window | Video = 30s windows | **Phase 1** neighbor `chunk_index` ±1 for `video_segment`. |
| 6 | Metadata pre-filter | `--source` only | **Phase 1** add `course` + `content_type`. |
| 7 | Cross-encoder | Type-prior bonus only | **Phase 1** optional `Qwen/Qwen3-Reranker-0.6B` (same family, Vietnamese-friendly). Not MiniLM. |
| 8 | Compression | 10k char truncate | **Phase 1** extractive sentence keep. **No** second LLM pass (16GB). |
| 9 | RAGAs | None | **Phase 2** optional `eval` extra. |
| 10 | LLM-as-judge | None | **Phase 2** reuse 1.7B. |
| 11 | Metric loop | None | **Phase 2** `eval` CLI + documented mapping. |
| 12 | Query decomposition | Already in enhance | **Keep.** Raise fetch_k per subquery. No second synthesis LLM in Phase 1. |
| 13 | Iterative retrieval | One shot | **Phase 3**, max 1 extra loop, flag off. |
| 14 | ColBERT | None | **Skip.** New index, RAM, English-centric. |
| 15 | ColPali / CLIP | Qwen3-VL already | **Skip.** This is the multimodal analogue. |
| 16 | Binary quant | Whisper int8 only | **Skip** until corpus/latency requires it. |

---

## 5. Compatibility constraints (hard)

1. Keep **two** Chroma collections and Qwen3 text + VL embedders. Do not merge spaces. Do not swap CLIP/ColPali/ColBERT.
2. Keep `rrf_merge` in `app/retrieval/merger.py` as the fusion primitive. Hybrid BM25 is **another group** into the same RRF, not a parallel fusion library.
3. Plug into existing hooks:
   - `ScoreReranker.rerank(query, results, source=...)`
   - `source_where` → Chroma `where`
   - `EnhancedQuery.text_search_queries()`
   - `format_hits` / `generation_k`
4. New behavior is **env-flagged** in `Settings`. Defaults must preserve today’s 16GB path: no extra 2B model, `RERANK_ENABLED=false`, API `text_only=true`.
5. HyDE off by default. Enhance prompt must keep “không bịa đề bài” / no fake answers.
6. Do not send images into Qwen3-1.7B.
7. Preserve vector id scheme `{sha256}:{kind}:{chunk_index}`.
8. Preserve CLI `ingest|search|ask|stats` and SSE events: `status` (`enhancing`|`retrieving`|`generating`), `query`, `sources`, `delta`, `done`. Adding fields is OK; renaming/removing is not.
9. Preserve query-enhance JSON keys: `rewritten`, `subqueries`, `step_back`.
10. Chroma metadata primitives only. Incremental ingest (SHA-256 skip) must keep working.
11. Unit tests mock models (`tests/conftest.py`). Do not download 1.7B in pytest. Add unit tests for new modules with fakes.
12. Optional deps: put BM25/rerank/eval in extras (`retrieval`, `eval`), not required base install.

### Target retrieval pipeline after Phase 1

```
query → QueryEnhance (existing 1.7B JSON)
     → dense text (Qwen) × N queries
     → BM25 text (if HYBRID_SEARCH)
     → dense VL (if not text_only)
     → rrf_merge (existing)
     → TypePriorReranker (existing)
     → optional Qwen3-Reranker-0.6B
     → parent / neighbor expand (query-time)
     → extractive compress
     → format_hits (10k cap)
     → Qwen3-1.7B answer on original question
```

Default order: **rerank on child text, then expand** so the CE scores the precise match. Then compress + char cap.

---

## 6. Phase 1 — implement (highest leverage)

### 6.1 Hybrid search (technique 3)

- New `app/retrieval/sparse.py`.
- Tokenize like `process_user_query` (NFC + whitespace). Do **not** add underthesea/pyvi unless eval proves it is needed.
- BM25 over **text collection documents only** (include `text`, `table`, `video_segment`, OCR sidecars). Not visual embeddings.
- Persist `data/bm25.pkl` (path via Settings). Rebuild on ingest after Chroma add (and on delete/reindex).
- Dependency: `rank-bm25` in extra `retrieval`.
- In `MultimodalRetriever.search`: if `HYBRID_SEARCH=true`, BM25 `top_k=retriever_fetch_k` per text query (or union of queries), then  
  `rrf_merge([*text_dense_groups, sparse_group, visual_group?])`.
- If BM25 file missing, log warning and dense-only (do not crash `search`).
- Tests: exact token match (`Bài 5`); RRF still dedupes by id.

Settings:

- `HYBRID_SEARCH` default `true` is acceptable if BM25 is CPU-only and tiny; otherwise default `true` after sidecar exists, `false` if file missing. Prefer **default true** once sidecar can be built from existing Chroma without re-embed (`rebuild from collection.get`). Provide `python -m app.main rebuild-bm25` or rebuild automatically on ingest.

### 6.2 Over-fetch + rerank (technique 7)

Today `k` is both fetch and return size (8 for ask). Change:

- `RETRIEVER_FETCH_K` default **20**. Dense/sparse/VL each fetch this many; after RRF+rerank return `k` (generation_k=8).
- Keep `TypePriorReranker` as pre-boost.
- New `QwenReranker(ScoreReranker)` using `Qwen/Qwen3-Reranker-0.6B` (not MiniLM). Lazy-load on first use, same pattern as GenerationService LLM.
- `RERANK_ENABLED` default **false** (16GB). `RERANK_MODEL` default `Qwen/Qwen3-Reranker-0.6B`.
- Factory: if enabled, inject Qwen reranker wrapping or chaining TypePrior. Suggested: TypePrior first, then CE on the fused list, then `[:k]`.
- If rerank model fails to load, fall back to TypePrior and log.

### 6.3 Parent expand + video window (techniques 2 and 5)

**No new embedding index.** After top-k children:

- Text/PDF/PPTX (`content_type` in `text`, `table`): `vector_store.get(where={document_id, page_number})` and join sibling chunk texts as parent `content` for generation. Retrieval key remains the child.
- If `page_number` is missing, expand same `section` or same `document_id` neighbors by `chunk_index` ±1 (cap size).
- Video `video_segment`: get same `document_id` with `chunk_index` in `{n-1, n, n+1}`.
- New `app/retrieval/expand.py`. Flag `CONTEXT_EXPAND` default **true** (no extra model).
- Deduplicate parents if several children share a page.
- Expanded text still goes through `format_hits` 10k cap.
- `ChromaVectorStore.get` already exists.

Do not store parent blobs in Chroma metadata (size). Optional later: `parent_id` field.

### 6.4 Metadata filters (technique 6)

Extend, do not replace `--source`.

- At ingest, set `course` from first path segment under `assets/` (e.g. `hethongquytrinhnghiepvu`, `nhapmonbaomatvaanninhmang`, `test`). Via `base_metadata` in `app/pipeline/indexing.py`.
- Old vectors without `course`: filter omitted if field absent (no crash). Document that full benefit needs reingest of text+video (VL reingest not required for course on text; but video/text share `base_metadata` so reingest those files).
- `source_where` becomes AND of:
  - existing filename / relative_path
  - optional `course`
  - optional `content_type`
- Chroma `where` with multiple keys: use `$and` list of eq dicts.
- API: optional `course`, `content_type` on `AskRequest` and `SearchRequest`.
- CLI: `--course`, `--content-type` on `search` and `ask`.
- Optional cheap: enhance JSON may add `course`/`content_type` **only if** they match known indexed values. Do not invent. Can be Phase 1.5 if it risks breaking the enhance parser — prefer API/CLI filters first.

### 6.5 Extractive compression (technique 8)

- New `app/retrieval/compress.py`.
- **Do not** use `LLMChainExtractor`.
- Keep sentences that overlap tokens from original + rewritten query, or that belong to the matched child span; drop the rest; then existing char cap.
- Flag `CONTEXT_COMPRESS` default **true** or **false** — prefer default **true** if expansion can blow context; if unsure, default true with a clear no-op when text is already short.
- Vietnamese: split on `।.!?` and newlines; keep order.

### 6.6 Query decomposition (technique 12)

Already implemented. Only ensure each subquery uses `retriever_fetch_k`. Do not add a second synthesis LLM call in Phase 1.

---

## 7. Phase 2 — eval then chunk calibration

### 7.1 RAGAs + judge (techniques 9–11)

- Extra `eval` (ragas if it can run with local HuggingFace; otherwise a thin local scorer around the same 1.7B).
- `evals/golden.jsonl`: 50–80 items from ingested `assets/`. Types: theory, exercise lookup, video timestamp, table, cross-slide. Fields: `question`, optional `source`, optional `ground_truth`, optional `course`.
- CLI: `python -m app.main eval evals/golden.jsonl --text-only` → report faithfulness, answer relevancy, context precision, context recall.
- Judge prompt: score 1–5 completeness + factuality given context; reuse ChatHuggingFace.
- Faithfulness &lt; 0.85 = warning in report, **not** CI hard-fail until the set is stable.
- Document mapping:
  - context precision ↓ → chunking / metadata filters
  - faithfulness ↓ → prompt / compression
  - context recall ↓ → hybrid / fetch_k / optional HyDE

### 7.2 Per-type chunk size (technique 1)

Only after baseline eval. Units are **characters** (current splitter), not tokens.

| `file_type` | size | overlap |
|-------------|------|---------|
| pdf, docx | 350 | 60 |
| pptx | 280 | 40 |
| txt, md | keep 500/50 or 450/50 |
| tables | do not split (already whole) |
| video transcript | keep 30s windows |

Requires **text reingest**. Global `CHUNK_SIZE` remains fallback. Settings like `CHUNK_SIZE_PDF`, `CHUNK_OVERLAP_PDF`, etc.

---

## 8. Phase 3 — optional / skip

- **HyDE:** `QUERY_HYDE=false`. If recall is the weakest metric on slang queries, generate a **short topical paragraph** (not an exam answer / not a full solution) and RRF with rewritten query. Never HyDE-only. Keep enhance rule against inventing exercises.
- **Iterative retrieval:** `MAX_RETRIEVE_LOOPS=1`, default 0. If used, model emits structured `needs_more` + follow-up query. Repeat SSE `status: retrieving` is OK; do not break existing event names.
- **Skip:** ColBERT, ColPali, CLIP, binary quantization of embeddings.

---

## 9. Files to add/change

### Phase 1 (expected)

| File | Change |
|------|--------|
| `app/config/settings.py` | New flags (see below) |
| `.env.example` | Document flags |
| `pyproject.toml` | extras `retrieval` (`rank-bm25`), maybe `rerank` via existing `generation`/`vision` transformers |
| `app/retrieval/sparse.py` | **new** BM25 |
| `app/retrieval/expand.py` | **new** parent/neighbor |
| `app/retrieval/compress.py` | **new** extractive |
| `app/retrieval/retriever.py` | fetch_k, hybrid group, filters, expand/compress hooks |
| `app/retrieval/reranker.py` | `QwenReranker` |
| `app/factory.py` | wire reranker, sparse index |
| `app/pipeline/indexing.py` | `course` metadata; trigger BM25 rebuild |
| `app/pipeline/ingestion.py` | if needed, rebuild sparse after successful index |
| `app/vectorstore/chroma.py` | `$and` where helper if not inlined in retriever |
| `app/api/schemas.py` | `course`, `content_type` optional |
| `app/api/app.py` | pass new fields |
| `app/main.py` | CLI flags; optional `rebuild-bm25` |
| `tests/test_retrieval.py` | BM25, RRF, filters |
| `tests/test_expand.py` | **new** sibling/neighbor |
| `tests/test_compress.py` | **new** |
| `tests/test_api.py` | schema/filter passthrough |
| `README.md` | flags; Phase 1 does not require VL reingest |

### New Settings (Phase 1)

```
HYBRID_SEARCH=true
BM25_PATH=./data/bm25.pkl
RETRIEVER_FETCH_K=20
RERANK_ENABLED=false
RERANK_MODEL=Qwen/Qwen3-Reranker-0.6B
CONTEXT_EXPAND=true
CONTEXT_COMPRESS=true
QUERY_HYDE=false
```

### Phase 2 files

- `evals/golden.jsonl`
- `app/eval/` or `app/generation/judge.py`
- `eval` subcommand in `app/main.py`
- extra `eval` in `pyproject.toml`

---

## 10. What must stay unchanged

- Dual collections `text_embeddings` / `visual_embeddings`
- Qwen3-Embedding-0.6B + Qwen3-VL-Embedding-2B + Qwen3-1.7B
- Query-enhance JSON shape and “answer uses original question”
- SSE contract and citation / `relative_path` rules
- API default `text_only=true`
- Generation prompt: no invented homework, no `http://` URLs, no absolute local paths
- Incremental hash ingest / manifest
- Tests must remain mock-based by default

---

## 11. Suggested implementation order for the next AI

1. Settings + `$and` filters (`course` on new ingest, `content_type`, keep `--source`).
2. `RETRIEVER_FETCH_K` without changing returned `k`.
3. BM25 sidecar + RRF group + tests.
4. Query-time expand + tests.
5. Extractive compress + tests.
6. Optional Qwen reranker behind flag (lazy load).
7. README / `.env.example`.
8. Only then Phase 2 eval + golden set.
9. Only then per-type chunk sizes (reingest).
10. Do not implement skipped items unless eval demands them.

---

## 12. How to use this file

You are planning (or implementing) **compatible production-RAG upgrades** for `/Users/tommynguyen/Downloads/RAG Multimodal`.

1. Read this document.
2. Read the cited Python files; do not assume APIs beyond what is here.
3. Produce a concrete implementation plan **or** implement Phase 1 in small PRs matching the order in §11.
4. Prefer flags and fallbacks over breaking 16GB defaults.
5. If a technique conflicts with this file, **this file wins** over the Sapota article (e.g. no ColPali swap, no MiniLM, no HyDE default, no LLM compressor).
