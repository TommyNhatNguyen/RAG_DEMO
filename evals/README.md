# Golden eval set

`golden.jsonl` is the Phase 2 test set for `python -m app.main eval`.

## Schema

One JSON object per line (`#` and blank lines skipped):

- `id` — stable id
- `question` — student question (Vietnamese)
- `ground_truth` — extractive reference (RAGAs `reference`); never a HyDE-invented answer
- `kind` — `catalog` | `theory` | `exercise` | `slide` | `table` | `video`
- `course`, `source`, `content_type` — optional retrieve filters (must match indexed paths)
- `expected_paths` — repo-relative files that should appear in hits (path recall/precision)

## Composition

Seed set covers the indexed corpus in `data/index_manifest.json`: quy trình PDF chap01–08, bảo mật PDF/PPTX, `bai_tap_chuong_3.docx`, `Chuong_3_quan_he.pptx`, `buoi_3.mp4`. Grow toward 50–80 without changing field names.

## How to run

```bash
# 16GB smoke (no 1.7B):
python -m app.main eval evals/golden.jsonl --text-only --retrieve-only --out evals/reports/baseline.json

# Full judge (loads Qwen3-1.7B once). Optional: pip install -e ".[eval]" for RAGAs.
python -m app.main eval evals/golden.jsonl --text-only --out evals/reports/baseline.json
```

## Metric mapping (handoff)

- context / path **precision** down → chunking (`CHUNK_SIZE_*`) or `--course` / `--source` filters; then `ingest --rechunk`
- **faithfulness** down → prompt / `CONTEXT_COMPRESS`
- context / path **recall** down → hybrid / `RETRIEVER_FETCH_K`; **only then** `QUERY_HYDE=true` or `MAX_RETRIEVE_LOOPS=1`
- faithfulness &lt; 0.85 is a **warning**, not a CI fail

After a chunk-size change (or `ingest --rechunk`), rebuild BM25 and compare against the baseline:

```bash
python -m app.main rebuild-bm25
python -m app.main eval evals/golden.jsonl --text-only --retrieve-only --out evals/reports/post-chunk.json
```

Recorded retrieve-only baseline (`evals/reports/baseline.json`, n=35, old 500-char chunks): `path_recall=0.975`, `path_precision=0.392`, `weakest_metric=path_precision`.

Post-chunk (`evals/reports/post-chunk.json`, per-type `CHUNK_SIZE_*`, text-only reingest, no VL/video): `path_recall=0.889`, `path_precision=0.363`, `weakest_metric=path_precision`. Precision did not improve; recall drop is mostly missing `buoi_3.mp4` after a Chroma HNSW crash recovery (`data/chroma.corrupt-20260908`).

Phase 3 skip: [evals/reports/phase3-skip.json](reports/phase3-skip.json). `QUERY_HYDE` and `MAX_RETRIEVE_LOOPS` stay off. Do not enable them unless `weakest_metric` is `context_recall` or `path_recall`.
