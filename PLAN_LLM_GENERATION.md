# Plan: RAG LLM Generation (Qwen3-1.7B)

Status: **ready to implement** (this file is the spec). Do not start coding until the phases below are followed in order.

Source of truth for generation behavior: RAG-Text notebook §2.1.3 (`/Users/tommynguyen/Desktop/Đại học UIT/deantotnghiep/RAG-Text/main.ipynb`, cells `gen-load-llm` + `gen-rag` + `gen-demo`).

This project already has ingest + retrieve. This plan adds **answer generation** on top of `MultimodalRetriever.search()`, without rewriting loaders, Chroma, or embeddings.

---

## 1. Goal

Generate a full Vietnamese tutoring answer with **`Qwen/Qwen3-1.7B`**:

| Setting | Value | Why |
| --- | --- | --- |
| Model | `Qwen/Qwen3-1.7B` | Notebook §2.1.3 |
| Thinking | **OFF** (`enable_thinking=False`) | Direct ChatGPT-like answers; avoid `<think>` token waste |
| `max_new_tokens` | **4096** | Long theory + exercise answers are not cut off |
| Sampling | `do_sample=False` | Deterministic, matches notebook |
| Stream API | `generate_answer_stream` | Print tokens as they arrive |
| Blocking API | `generate_answer` | Wait until complete |

CLI example after this work:

```bash
python -m app.main ask "link bài tập lý thuyết quan hệ"
python -m app.main ask "Quan hệ phản xạ trên tập {1,2,3,4}" --text-only
python -m app.main ask "…" --no-stream -k 8
```

---

## 2. Compatibility rules (do not violate)

The current codebase is modular: ingest ≠ retrieve, Pydantic domain models, factory DI, lazy model load, mocked unit tests. Generation must follow the same rules.

1. **Do not change ingest.** Loaders, indexing, IDs, manifest, Chroma writes stay as they are.
2. **Do not change `RetrievalResult`.** Generation consumes `list[RetrievalResult]` from `retriever.search()`. Do not require LangChain `Document` inside retrieval.
3. **Do not load the LLM on `ingest` / `search` / `stats`.** Lazy-load weights on first `ask` / `generate_*` call, same pattern as `TextEmbeddingService._ensure_loaded()`.
4. **Do not put ChatHuggingFace inside `MultimodalRetriever`.** Retriever stays retrieval-only. New package: `app/generation/`.
5. **Do not scatter transformers calls.** One service class owns tokenizer patch, pipeline, chat model.
6. **Keep thinking OFF at the tokenizer**, not only in the prompt. Notebook found that `ChatHuggingFace` reloads a fresh tokenizer unless we pass the patched one.
7. **Reuse existing query cleanup.** Call `process_user_query` (already in `app/retrieval/retriever.py`). Do not duplicate it.
8. **Reuse existing device helper.** Call `resolve_device(settings.device)` (already in `app/config/settings.py`).
9. **Citation paths** come from metadata already written at index time: `relative_path`, then `filename`, never invent `http://` URLs, never print absolute local paths to the user.
10. **Visual hits are text context for this LLM.** Qwen3-1.7B is **not** a VL generator. Pass OCR/caption/`content` plus citation (`image_path`, page, timestamps). Do not feed images into the 1.7B chat model.
11. **Unit tests must not download 1.7B.** Fake/mock the chat model. Real-model check stays manual / `@pytest.mark.integration`.
12. **Optional extra.** Generation deps go in `pyproject.toml` extra `generation`, and are included in `all`. Core ingest still installs without forcing a second copy of transformers if vision is already present.

---

## 3. What to port from the notebook (and what not to)

### 3.1 Port as-is (behavior)

From cell `gen-load-llm`:

- `LLM_MODEL = "Qwen/Qwen3-1.7B"`
- `MAX_NEW_TOKENS = 4096`
- `ENABLE_THINKING = False`
- `AutoTokenizer` + wrap `apply_chat_template` so every call sets `enable_thinking=ENABLE_THINKING`
- `AutoModelForCausalLM.from_pretrained(..., torch_dtype, trust_remote_code=True, low_cpu_mem_usage=True)`
- Move to `mps` / `cuda`; CPU uses `float32` + `device=-1`
- Clear `generation_config.max_length = None` and set `max_new_tokens=4096` (avoids the `max_length=20` warning seen in the notebook)
- `transformers.pipeline` task `text-generation`, `return_full_text=False`, `do_sample=False`
- `HuggingFacePipeline` + **`ChatHuggingFace(llm=llm, tokenizer=gen_tokenizer)`** using the **patched** tokenizer
- `strip_think()` for leftover `<think>…</think>`

From cell `gen-rag`:

- Vietnamese UIT tutor system prompt (full-answer, structured, no inner monologue)
- Human template with `{context}`, `{source_paths}`, `{question}`
- `MAX_CONTEXT_CHARS = 10000`
- `GENERATION_K = max(retriever_k, 8)`
- `format_docs` / `collect_source_paths`
- `generate_answer` = retrieve → chain.invoke → strip_think
- `generate_answer_stream` = retrieve → `chain.stream` → filter think tags while printing → return visible text

### 3.2 Do **not** port as notebook globals

| Notebook | This repo |
| --- | --- |
| Global `chat_model`, `pipe`, `text_store` | `GenerationService` + `AppServices` |
| `retrieve()` returning `(Document, score)` | `MultimodalRetriever.search()` → `RetrievalResult` |
| `hits = retrieve(...)` then `doc.page_content` | `hit.content` + `hit.metadata` |
| `_to_relative_path` on absolute `source` | Prefer `metadata["relative_path"]` already stored by `base_metadata()` |
| `_free_llm()` notebook RAM hack | Optional `close()` later; not required for v1 |
| `DEBUG_RETRIEVAL` prints | Existing logging in retriever |

### 3.3 Multimodal adaptation (required for compatibility)

Notebook retrieval was **text collection only**. This repo searches **text + visual** and merges.

Generation context formatter must include:

- `content_type` (`text` / `table` / `image` / `page` / `video_segment`)
- `page_number` when present
- `start_time` / `end_time` for video
- `relative_path` / `filename`
- body: `hit.content` (chunk text, table markdown, OCR, transcript, caption)

If a visual hit has empty `content`, still emit a stub line so the model can cite the file:

```text
[Đoạn 3 | image | assets/slides/foo.pptx p.2]
(Không có OCR/caption; đây là ảnh/slide được retrieve theo ngữ nghĩa thị giác.)
```

Default `ask` should still use visual retrieval (`include_visual=True`) so slide/image hits can appear as citations. Provide `--text-only` to skip VL embed + visual search (saves RAM on M1 16GB).

---

## 4. Target architecture

```text
CLI ask / Python API
        │
        ▼
 GenerationService.generate_answer[_stream]
        │
        ├─ process_user_query          (existing)
        ├─ retriever.search(...)       (existing, dual collections)
        ├─ format_hits + source_paths  (new, RetrievalResult → prompt strings)
        └─ ChatHuggingFace.stream/invoke
              Qwen/Qwen3-1.7B, thinking OFF, max_new_tokens=4096
```

Ingestion and search commands never construct the HF causal LM. `build_services()` may **construct** a `GenerationService` wrapper (cheap); `_ensure_loaded()` runs only on generate.

```text
AppServices
  pipeline          ingest only
  retriever         search + ask
  generator         ask only (lazy LLM)
```

---

## 5. Files to add / change

### 5.1 New files

| Path | Responsibility |
| --- | --- |
| `app/generation/__init__.py` | Export `GenerationService`, `strip_think` |
| `app/generation/base.py` | Protocol: `generate(query, *, k, include_visual) -> str` and `stream(...)` iterator |
| `app/generation/prompts.py` | System + human prompt strings (notebook text, plus multimodal citation hints) |
| `app/generation/context.py` | `format_hits`, `collect_source_paths`, `relative_path_for_hit`, `generation_k` |
| `app/generation/think.py` | `strip_think`, `ThinkStreamFilter` (token-safe hide of `<think>` blocks) |
| `app/generation/service.py` | Lazy Qwen3 load, ChatHuggingFace, `generate_answer`, `generate_answer_stream` |
| `tests/test_generation_context.py` | Formatter + citations, no model |
| `tests/test_generation_think.py` | strip + stream filter |
| `tests/test_generation_service.py` | Fake chat model; `generate_answer` / stream wiring |

Keep generation **out of** `app/retrieval/` so retrieval tests stay unchanged.

### 5.2 Existing files to touch (minimal)

| Path | Change |
| --- | --- |
| `app/config/settings.py` | Add LLM fields (section 6) |
| `.env.example` | Document those vars |
| `app/factory.py` | Construct `GenerationService`; add `generator` on `AppServices` |
| `app/main.py` | Subcommand `ask` |
| `pyproject.toml` | Extra `generation`; add to `all` |
| `README.md` | Ask command, RAM notes, thinking OFF |
| `tests/conftest.py` | Optional `FakeChatModel` / settings LLM fields |
| `TECHNICAL_DOCUMENTATION.html` | After implementation, add generation section (not in this coding slice unless asked) |

**Do not edit** loaders, chunkers, vectorstore, indexing, or `retriever.search` signature.

---

## 6. Settings (env-configurable, no hardcoding)

Add to `Settings` with notebook defaults:

| Field | Env | Default |
| --- | --- | --- |
| `llm_model` | `LLM_MODEL` | `Qwen/Qwen3-1.7B` |
| `llm_max_new_tokens` | `LLM_MAX_NEW_TOKENS` | `4096` |
| `llm_enable_thinking` | `LLM_ENABLE_THINKING` | `false` |
| `llm_max_context_chars` | `LLM_MAX_CONTEXT_CHARS` | `10000` |
| `generation_k` | `GENERATION_K` | `8` |
| `llm_do_sample` | `LLM_DO_SAMPLE` | `false` |

Device: reuse `DEVICE` + `resolve_device()`. Do **not** add a second device flag in v1 unless MPS OOM forces `LLM_DEVICE` later.

Empty-string validator already treats `""` as `None` for some fields; booleans stay pydantic-settings native (`true`/`false`).

Effective k for generation:

```python
k = k if k is not None else max(settings.retriever_k, settings.generation_k)
```

Matches notebook `GENERATION_K = max(RETRIEVER_K, 8)`.

---

## 7. Service API (must match notebook names)

```python
class GenerationService:
    def __init__(self, settings: Settings, retriever: MultimodalRetriever) -> None: ...

    def generate_answer(
        self,
        raw_query: str,
        *,
        k: int | None = None,
        include_visual: bool = True,
    ) -> str:
        """Retrieve → full answer (blocking)."""

    def generate_answer_stream(
        self,
        raw_query: str,
        *,
        k: int | None = None,
        include_visual: bool = True,
        printer: Callable[[str], None] | None = None,
    ) -> str:
        """
        Retrieve → stream visible tokens (ChatGPT-like).
        Default printer writes to stdout with flush=True.
        Returns the full visible answer (think tags stripped).
        """

    def iter_answer_tokens(...) -> Iterator[str]:
        """Library-friendly: yield visible token chunks (no print). Used by tests and stream."""
```

`generate_answer_stream` is the operator-facing method (CLI). Internally it should use `iter_answer_tokens` so tests can assert chunks without capturing stdout.

Return type stays `str` like the notebook (not a Pydantic answer object in v1). Optional later: `GenerationResult(answer, hits, sources)`.

Empty retrieval: still call the LLM with `(Không có ngữ cảnh)` and source list `- (không có)`, same as notebook `format_docs`. Do not crash.

Empty query: `process_user_query` → `ValueError`, same as search.

---

## 8. Prompt (notebook + multimodal lines)

Keep the notebook system prompt. Add **one** short bullet so visual/video metadata is used:

- Khi ngữ cảnh có `page`, `slide`, hoặc mốc thời gian video: nêu rõ trong câu trả lời (ví dụ: trang 3, 00:15–00:30).
- Khi người dùng xin link/file: chỉ dùng đường dẫn tương đối trong mục "Tài liệu gốc".

Human template stays:

```text
Ngữ cảnh từ tài liệu:
{context}

Tài liệu gốc (đường dẫn tương đối trong project):
{source_paths}

Câu hỏi của sinh viên: {question}

Hãy trả lời đầy đủ.
```

Implement prompts as a function returning `ChatPromptTemplate` (LangChain is already in the stack via `langchain-huggingface`). This is generation-only; ingest remains non-LCEL.

### 8.1 `format_hits` header

Replace notebook `[Đoạn i | src#idx]` with something citation-complete:

```text
[Đoạn {i} | {content_type} | {relative_path} p.{page} @{start}-{end}s #{chunk_index}]
{content}
```

Omit empty optional fields. Cap total characters at `llm_max_context_chars` (stop adding hits when the next block would exceed).

### 8.2 `collect_source_paths`

Walk hits in rank order. Unique `relative_path` (NFC). If value looks absolute (`/` or `C:`), take `Path.name` only. Output markdown bullets. Fallback `- (không có)`.

---

## 9. Thinking OFF — implementation detail (critical)

Qwen3 chat templates emit a thinking channel unless `enable_thinking=False` is passed into `apply_chat_template`.

`ChatHuggingFace` will load its **own** tokenizer if we omit `tokenizer=`. That copy is unpatched → model spends 4096 tokens inside `<think>` and the user sees nothing useful.

Required load sequence (from notebook):

```text
tokenizer = AutoTokenizer.from_pretrained(model, trust_remote_code=True)
tokenizer.apply_chat_template = wrapper that sets kwargs["enable_thinking"] = settings.llm_enable_thinking
model = AutoModelForCausalLM.from_pretrained(...)
pipe = pipeline(model=model, tokenizer=tokenizer, ...)
llm = HuggingFacePipeline(pipeline=pipe, pipeline_kwargs={max_new_tokens, do_sample})
chat_model = ChatHuggingFace(llm=llm, tokenizer=tokenizer)  # patched tokenizer
```

Defense in depth:

1. Tokenizer wrapper (primary)
2. Prompt says “Không viết phần suy nghĩ nội bộ”
3. `ThinkStreamFilter` + `strip_think` on output (hides leftover tags while streaming)

`strip_think` logic (notebook):

- If `</think>` present → take text after last close tag
- Else if `<think>` present with no close → return `""`
- Else strip whitespace

Build open/close tags at runtime (`"<" + "think" + ">"`) only if we want to avoid accidental highlighting; either form is fine in this repo.

Stream filter: same state machine as notebook `generate_answer_stream` (hold back incomplete tag prefixes so `"<thi"` is not printed). Do not print inside `in_think`.

---

## 10. Device, dtype, RAM (M1 16GB)

Notebook: MPS + `float16`; CUDA + `float16`; CPU + `float32` and warn.

This machine already may hold Qwen3-Embedding-0.6B and Qwen3-VL-Embedding-2B. Adding 1.7B on MPS can OOM.

v1 mitigations (document in README, no extra architecture):

- `ask --text-only` skips VL query embedding (VL weights stay unloaded if never used)
- Ingest/search do not load the LLM
- If OOM: `DEVICE=cpu` or close other apps; do not load VL until needed
- Do not also bump to 4B/8B embeddings while generating

Do **not** implement model offload/quantization in v1 unless load fails in manual test. If it fails, follow-up is `dtype=float16` already on MPS; next option is 8-bit/4-bit (out of this plan).

---

## 11. CLI

Add subparser `ask`:

| Arg | Meaning |
| --- | --- |
| `query` | Natural language question |
| `-k` | Override generation k |
| `--text-only` | `include_visual=False` |
| `--no-stream` | Call `generate_answer` instead of stream |
| `--show-hits` | After answer, print the same hit preview as `search` (optional, useful for debugging) |

Stdout:

```text
=== Câu hỏi ===
...

=== Trả lời ===
<streamed tokens>

(done — length: N chars)
```

Exit codes: `0` on success; `1` on empty query / missing extra / load error (log exception). Do not change ingest/search exit behavior.

`cmd_ask` uses `build_services` then `services.generator.generate_answer_stream(...)`.

`cmd_stats` may print `llm_model=` (settings only, do not load weights).

---

## 12. Dependencies

`pyproject.toml`:

```toml
generation = [
    "transformers>=4.51",
    "langchain-core>=0.3",
    "langchain-huggingface>=0.1",
]
```

Include `generation` packages in extra `all`.

`langchain-huggingface` is already a core dependency (text embeddings). `transformers` is likely pulled by `sentence-transformers` when vision extra is installed; still declare it on `generation` so `pip install -e ".[generation]"` is enough for ask without Docling.

Import LLM libraries **inside** `_ensure_loaded()`, not at module top, so unit tests that import `app.generation.context` do not need GPU stacks.

If `transformers` is missing, raise a clear `RuntimeError` telling the user to `pip install -e ".[generation]"` or `".[all]"`.

---

## 13. Tests (must pass without Hub)

### 13.1 `test_generation_context.py`

- `format_hits` includes `relative_path`, page, content_type
- Truncates at `max_chars`
- Empty hits → `(Không có ngữ cảnh)`
- `collect_source_paths` unique, strips absolute paths to basename
- Video timestamps appear in header

### 13.2 `test_generation_think.py`

- `strip_think` drops prefix before `</think>`
- Open tag without close → empty
- Stream filter: chunks like `"He", "llo <th", "ink>secret</th", "ink> world"` yield `"Hello  world"` (or equivalent visible text)

### 13.3 `test_generation_service.py`

- Fake retriever returns two `RetrievalResult`s
- Fake chat model `.invoke` / `.stream` yield known strings (optionally with `<think>…</think>`)
- `generate_answer` returns stripped text
- `iter_answer_tokens` never yields think inner text
- **Does not** instantiate `AutoModelForCausalLM`

Do not mark these as `integration`. Keep `pytest` default suite green.

Manual (not automated in v1):

```bash
python -m app.main ask "Quan hệ phản xạ, đối xứng, bắc cầu trên tập {1,2,3,4}" --text-only
python -m app.main ask "link bài tập lý thuyết quan hệ"
```

Expect streamed Vietnamese answer citing `assets/test/bai_tap_chuong_3.docx` after that file is ingested.

---

## 14. Implementation phases

### Phase A — Context + prompt (no LLM)

1. Add settings fields + `.env.example`
2. Add `app/generation/context.py`, `prompts.py`, `think.py`
3. Unit tests for format / citations / think filter
4. `pytest` green

### Phase B — Service + factory (mocked)

1. `GenerationService` with lazy load behind `_ensure_loaded`
2. Constructor accepts optional `chat_model=` for tests
3. Wire `AppServices.generator` in factory
4. Service tests with fake chat + fake retriever
5. `pytest` green; ingest/search tests unchanged

### Phase C — CLI

1. `ask` subcommand, stream default, `--no-stream`, `--text-only`, `-k`
2. Help text matches README
3. Smoke: `python -m app.main ask --help`

### Phase D — Real model (manual)

1. Extra `generation` / `all`
2. Load 1.7B once; confirm log `thinking=False` and `MAX_NEW_TOKENS=4096`
3. Confirm no `max_length=20` warning (or it is harmless because `max_new_tokens` wins)
4. Stream looks like ChatGPT (token-by-token, no think dump)
5. If MPS OOM: document `--text-only` / `DEVICE=cpu`

### Phase E — Docs

1. README: architecture diagram includes LLM; ask examples; RAM; thinking OFF
2. Note that generation is now in-scope (today README says it is not)

Do not regenerate `CODEBASE_CONTEXT.html` unless asked.

---

## 15. Factory sketch (compatible)

```python
@dataclass
class AppServices:
    ...
    retriever: MultimodalRetriever
    generator: GenerationService  # new, last field with default only if needed

# after retriever = MultimodalRetriever(...)
generator = GenerationService(settings=settings, retriever=retriever)
```

`GenerationService.__init__` stores settings + retriever; sets `self._chat = None`.

Tests that build `IngestionPipeline(...)` directly **do not** need a generator.

If any test constructs `AppServices(...)` by keyword, add `generator=`. Grep before changing the dataclass.

---

## 16. Out of scope (do not sneak in)

- LLM answer API / FastAPI / UI
- Qwen3-VL as the generator (different model)
- Cross-encoder reranker (still `ScoreReranker`)
- Parent-child chunking / RRF (see `rag_multimodal_improvements.md`; not required for this slice)
- Changing embedding instruct format
- Unified Chroma collection
- Quantization, vLLM, Ollama
- Multi-turn chat history
- Forcing Docling OCR on

---

## 17. Done when

- [ ] `python -m app.main ask "…"` streams a full answer with thinking OFF
- [ ] `generate_answer` / `generate_answer_stream` exist on `GenerationService` with notebook semantics
- [ ] `max_new_tokens=4096`, `do_sample=False`, patched tokenizer passed into `ChatHuggingFace`
- [ ] `search` / `ingest` still work and do not load 1.7B
- [ ] Context + citations use `RetrievalResult` metadata (`relative_path`, page, timestamps)
- [ ] `pytest` passes without downloading the LLM
- [ ] README documents `ask`, extras, and M1 RAM
- [ ] Existing vector IDs / collections / loaders untouched

---

## 18. Notebook → code map

| Notebook | Package function |
| --- | --- |
| `strip_think` | `app.generation.think.strip_think` |
| stream while-loop | `ThinkStreamFilter.feed` + `generate_answer_stream` |
| `format_docs` | `format_hits(list[RetrievalResult])` |
| `collect_source_paths` | `collect_source_paths(list[RetrievalResult])` |
| `_prepare_rag` | `GenerationService._prepare(raw_query, k, include_visual)` |
| `answer_prompt` | `app.generation.prompts.build_answer_prompt()` |
| `chat_model` | lazy attr on `GenerationService` |
| `retrieve` | `self.retriever.search` |
| `process_user_query` | existing import |
| `USER_QUERY` demo | README + CLI examples |
)
