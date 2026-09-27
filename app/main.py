from __future__ import annotations

import argparse
import logging
import sys
from app.config.settings import Settings
from app.factory import build_services
from app.log_setup import setup_logging
from app.models.retrieval import RetrievalResult
from app.pipeline.ingestion import IngestReport

logger = logging.getLogger(__name__)


def _print_report(report: IngestReport) -> None:
    counts = report.counts()
    print(
        f"indexed={counts['indexed']} "
        f"skipped_unchanged={counts['skipped_unchanged']} "
        f"reindexed_changed={counts['reindexed_changed']} "
        f"skipped_video={counts['skipped_video']} "
        f"failed={counts['failed']}"
    )
    for item in report.failed:
        print(f"  FAIL {item.path}: {item.error}", file=sys.stderr)


def _print_hits(hits: list[RetrievalResult]) -> None:
    if not hits:
        print("No results.")
        return
    for index, hit in enumerate(hits, 1):
        meta = hit.metadata
        src = meta.get("relative_path") or meta.get("filename") or "?"
        extra = ""
        if meta.get("start_time") is not None:
            extra = f" @{meta.get('start_time'):.1f}-{meta.get('end_time'):.1f}s"
        page = meta.get("page_number")
        page_s = f" p.{page}" if page is not None else ""
        cosine = meta.get("cosine")
        cos_s = f" cosine={float(cosine):.4f}" if cosine is not None else ""
        preview = (hit.content or "").replace("\n", " ")[:240]
        print(f"[{index}] score={hit.score:.4f}{cos_s} {hit.content_type} {src}{page_s}{extra}")
        if preview:
            print(f"    {preview}")


def cmd_ingest(args: argparse.Namespace, settings: Settings) -> int:
    services = build_services(settings)
    report = services.pipeline.ingest(
        args.path,
        rechunk=getattr(args, "rechunk", False),
        no_video=getattr(args, "no_video", False),
    )
    _print_report(report)
    return 1 if report.failed else 0


def cmd_search(args: argparse.Namespace, settings: Settings) -> int:
    services = build_services(settings)
    hits = services.retriever.search(
        args.query,
        k=args.k,
        include_visual=not args.text_only,
        source=args.source,
        course=args.course,
        content_type=args.content_type,
    )
    if not hits:
        print("No results.")
        return 0
    _print_hits(hits)
    return 0


def cmd_ask(args: argparse.Namespace, settings: Settings) -> int:
    try:
        services = build_services(settings)
        print("=== Câu hỏi ===")
        print(args.query)
        print()
        print("=== Trả lời ===")
        include_visual = not args.text_only
        enhance = False if args.no_enhance else None
        if args.no_stream:
            answer = services.generator.generate_answer(
                args.query,
                k=args.k,
                include_visual=include_visual,
                enhance=enhance,
                source=args.source,
                course=args.course,
                content_type=args.content_type,
            )
            print(answer)
        else:
            answer = services.generator.generate_answer_stream(
                args.query,
                k=args.k,
                include_visual=include_visual,
                enhance=enhance,
                source=args.source,
                course=args.course,
                content_type=args.content_type,
            )
            print()
        print(f"(done — length: {len(answer)} chars)")
        if args.show_hits:
            print()
            enhanced = services.generator.last_enhanced
            if enhanced:
                print("=== Câu truy vấn ===")
                print(f"rewritten: {enhanced.rewritten}")
                if enhanced.subqueries:
                    print("subqueries: " + " | ".join(enhanced.subqueries))
                if enhanced.step_back:
                    print(f"step_back: {enhanced.step_back}")
                if enhanced.hyde:
                    print(f"hyde: {enhanced.hyde[:200]}")
                print()
            print("=== Ngữ cảnh retrieve ===")
            _print_hits(services.generator.last_hits)
        return 0
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        logger.exception("ask failed")
        return 1
    except Exception:
        logger.exception("ask failed")
        return 1


def cmd_rebuild_bm25(args: argparse.Namespace, settings: Settings) -> int:
    from app.retrieval.sparse import persist_bm25
    from app.vectorstore.chroma import ChromaVectorStore

    store = ChromaVectorStore(
        persist_path=settings.resolve_path(settings.chroma_path),
        text_collection=settings.text_collection,
        visual_collection=settings.visual_collection,
    )
    path = settings.resolve_path(settings.bm25_path)
    index = persist_bm25(store, settings.text_collection, path)
    print(f"bm25 docs={index.size} path={path}")
    return 0


def cmd_eval(args: argparse.Namespace, settings: Settings) -> int:
    import json
    from pathlib import Path

    from app.eval.golden import load_golden
    from app.eval.report import format_report
    from app.eval.runner import run_eval

    settings.rerank_enabled = False
    services = build_services(settings)
    items = load_golden(args.golden)
    if args.limit is not None:
        items = items[: max(0, args.limit)]
    report = run_eval(
        services,
        items,
        text_only=args.text_only,
        retrieve_only=args.retrieve_only,
        enhance=args.enhance,
        k=args.k,
    )
    print(format_report(report))
    if args.out:
        out = Path(args.out)
        if not out.is_absolute():
            out = settings.resolve_path(out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"wrote {out}")
    return 0


def cmd_stats(args: argparse.Namespace, settings: Settings) -> int:
    import json
    from pathlib import Path

    from app.eval.inventory import (
        build_inventory,
        count_storage_images,
        count_vector_breakdown,
        format_inventory_vi,
        inventory_assets,
    )

    services = build_services(settings)
    text_n = services.vector_store.count(settings.text_collection)
    vis_n = services.vector_store.count(settings.visual_collection)
    storage = settings.resolve_path(settings.storage_root)
    chroma = settings.resolve_path(settings.chroma_path)
    print(f"text_collection={settings.text_collection} count={text_n}")
    print(f"visual_collection={settings.visual_collection} count={vis_n}")
    print(f"chroma_path={chroma}")
    print(f"storage_root={storage}")
    print(f"manifest={settings.resolve_path(settings.manifest_path)}")
    print(f"device={settings.device} embedding={settings.embedding_model}")
    print(f"llm_model={settings.llm_model}")
    if not getattr(args, "detailed", False):
        return 0

    assets_root = settings.project_root / "assets"
    assets = inventory_assets(assets_root, settings.project_root)
    images = count_storage_images(storage)
    vectors = count_vector_breakdown(
        services.vector_store, settings.text_collection, settings.visual_collection
    )
    data = build_inventory(
        assets=assets,
        storage_images=images,
        vectors=vectors,
        chroma_path=str(chroma),
        storage_root=str(storage),
        manifest=str(settings.resolve_path(settings.manifest_path)),
        query_hyde=settings.query_hyde,
        max_retrieve_loops=settings.max_retrieve_loops,
        no_video=True,
    )
    print()
    print(format_inventory_vi(data))
    out = getattr(args, "out", None) or "evals/reports/inventory.json"
    dest = Path(out)
    if not dest.is_absolute():
        dest = settings.resolve_path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {dest}")
    return 0


def cmd_inventory(args: argparse.Namespace, settings: Settings) -> int:
    import json
    from pathlib import Path

    from app.eval.inventory import inventory_assets

    target = Path(args.path)
    if not target.is_absolute():
        target = settings.resolve_path(target)
    data = inventory_assets(target, settings.project_root)
    out = Path(args.out)
    if not out.is_absolute():
        out = settings.resolve_path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        f"n_files={data['n_files']} bytes={data['bytes']} "
        f"video={data.get('by_kind', {}).get('video', 0)} wrote {out}"
    )
    return 0


def cmd_report(args: argparse.Namespace, settings: Settings) -> int:
    from pathlib import Path

    from app.eval.dashboard import load_reports, write_dashboard

    reports_dir = Path(args.reports_dir)
    if not reports_dir.is_absolute():
        reports_dir = settings.resolve_path(reports_dir)
    out = Path(args.out)
    if not out.is_absolute():
        out = settings.resolve_path(out)
    bundle = load_reports(reports_dir)
    write_dashboard(out, bundle)
    print(f"wrote {out}")
    return 0


def cmd_prepare_retrieval_queries(args: argparse.Namespace, settings: Settings) -> int:
    from pathlib import Path

    from app.eval.retrieval_benchmark import prepare_query_file

    source = Path(args.questions)
    if not source.is_absolute():
        source = settings.resolve_path(source)
    target = Path(args.out)
    if not target.is_absolute():
        target = settings.resolve_path(target)
    count = prepare_query_file(source, target)
    print(f"prepared={count} wrote {target}")
    return 0


def cmd_benchmark_retrieve(args: argparse.Namespace, settings: Settings) -> int:
    from pathlib import Path

    from app.eval.retrieval_benchmark import (
        load_query_file,
        query_set_sha256,
        run_retrieval,
    )

    query_path = Path(args.queries)
    if not query_path.is_absolute():
        query_path = settings.resolve_path(query_path)
    output_path = Path(args.out)
    if not output_path.is_absolute():
        output_path = settings.resolve_path(output_path)

    settings.context_expand = False
    settings.context_compress = False
    settings.course_prefilter = not args.no_course_filter
    # Fetch a wider candidate pool so diversity-by-file can still return a
    # complete Top-10 instead of stopping at only a few source files.
    settings.retriever_fetch_k = max(settings.retriever_fetch_k, args.k * 10)
    if args.profile == "baseline":
        settings.hybrid_search = False
        settings.rerank_enabled = False
        include_visual = False
    else:
        settings.hybrid_search = True
        settings.rerank_enabled = bool(args.rerank)
        include_visual = True

    inputs = load_query_file(query_path)
    query_hash = query_set_sha256(inputs)
    start = max(1, int(args.start)) - 1
    selected = inputs[start:]
    if args.limit is not None:
        selected = selected[: max(0, args.limit)]
    services = build_services(settings)
    summary = run_retrieval(
        services.retriever,
        selected,
        output_path,
        system_id=args.system_id,
        top_k=args.k,
        include_visual=include_visual,
        use_course_filter=not args.no_course_filter,
        resume=args.resume,
        query_set_hash=query_hash,
    )
    print(
        f"system={summary['system_id']} requested={summary['requested']} "
        f"written={summary['written']} resumed={summary['resumed']} "
        f"failed={summary['failed']} wrote {summary['output']}"
    )
    return 1 if summary["failed"] else 0


def cmd_score_retrieval(args: argparse.Namespace, settings: Settings) -> int:
    import json
    from pathlib import Path

    from app.eval.retrieval_benchmark import (
        canonical_resource_id,
        score_retrieval_file,
    )

    questions = Path(args.questions)
    results = Path(args.results)
    output = Path(args.out)
    if not questions.is_absolute():
        questions = settings.resolve_path(questions)
    if not results.is_absolute():
        results = settings.resolve_path(results)
    if not output.is_absolute():
        output = settings.resolve_path(output)
    indexed_resources = None
    if not args.allow_unindexed_ground_truth:
        services = build_services(settings)
        indexed_resources = set()
        for collection in (settings.text_collection, settings.visual_collection):
            got = services.vector_store.get(collection)
            for metadata in got.get("metadatas") or []:
                relative_path = str((metadata or {}).get("relative_path") or "")
                if relative_path:
                    indexed_resources.add(canonical_resource_id(relative_path))
    report = score_retrieval_file(
        questions,
        results,
        null_policy=args.null_policy,
        indexed_resource_ids=indexed_resources,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"answerable_scored={report['counts']['answerable_scored']}")
    print(f"unanswerable_separate={report['counts']['unanswerable_separate']}")
    for key, value in report["macro_average_answerable"].items():
        if value is not None:
            print(f"{key}={float(value):.6f}")
    print(f"wrote {output}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m app.main",
        description="Trợ lý ảo e-learning: RAG đa phương thức trên học liệu dị chất",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    ingest = sub.add_parser("ingest", help="Ingest a file or directory")
    ingest.add_argument("path", help="File or directory (e.g. ./assets)")
    ingest.add_argument(
        "--rechunk",
        action="store_true",
        help="Force text/image reindex with current CHUNK_SIZE_* profile (skip video)",
    )
    ingest.add_argument(
        "--no-video",
        action="store_true",
        help="Skip video files (count them; do not transcribe or embed)",
    )
    ingest.set_defaults(func=cmd_ingest)

    search = sub.add_parser("search", help="Tìm kiếm học liệu đã index (văn bản và/hoặc thị giác)")
    search.add_argument("query", help="Natural language query")
    search.add_argument("-k", type=int, default=None, help="Top K results")
    search.add_argument("--text-only", action="store_true", help="Skip visual collection")
    search.add_argument("--source", default=None, help="Limit to filename or relative_path (e.g. buoi_3.mp4)")
    search.add_argument("--course", default=None, help="Limit to course folder slug (e.g. hethongquytrinhnghiepvu)")
    search.add_argument("--content-type", default=None, help="Limit to content_type (text, table, video_segment, ...)")
    search.set_defaults(func=cmd_search)

    ask = sub.add_parser(
        "ask",
        help="Truy xuất học liệu rồi trả lời như trợ lý ảo e-learning (có căn cứ)",
    )
    ask.add_argument("query", help="Natural language question")
    ask.add_argument("-k", type=int, default=None, help="Top K retrieved chunks for generation")
    ask.add_argument("--text-only", action="store_true", help="Skip visual collection (saves RAM)")
    ask.add_argument("--source", default=None, help="Limit to filename or relative_path (e.g. buoi_3.mp4)")
    ask.add_argument("--course", default=None, help="Limit to course folder slug (e.g. hethongquytrinhnghiepvu)")
    ask.add_argument("--content-type", default=None, help="Limit to content_type (text, table, video_segment, ...)")
    ask.add_argument("--no-stream", action="store_true", help="Wait for the full answer instead of streaming")
    ask.add_argument("--show-hits", action="store_true", help="Print retrieved hits after the answer")
    ask.add_argument(
        "--no-enhance",
        action="store_true",
        help="Skip LLM query rewrite; retrieve with the raw question",
    )
    ask.set_defaults(func=cmd_ask)

    stats = sub.add_parser("stats", help="Show collection and storage stats")
    stats.add_argument(
        "--detailed",
        action="store_true",
        help="Scan assets/, storage/images, and Chroma metadatas; write inventory JSON",
    )
    stats.add_argument(
        "--out",
        default="evals/reports/inventory.json",
        help="Write detailed inventory JSON (used with --detailed)",
    )
    stats.set_defaults(func=cmd_stats)

    inv = sub.add_parser("inventory", help="Walk assets/ on disk and write assets-inventory.json")
    inv.add_argument("path", nargs="?", default="./assets", help="Root to walk (default ./assets)")
    inv.add_argument(
        "--out",
        default="evals/reports/assets-inventory.json",
        help="Write assets inventory JSON",
    )
    inv.set_defaults(func=cmd_inventory)

    report = sub.add_parser(
        "report",
        help="Build self-contained HTML dashboard from evals/reports/*.json",
    )
    report.add_argument(
        "out",
        nargs="?",
        default="evals/reports/dashboard.html",
        help="HTML output path",
    )
    report.add_argument(
        "--reports-dir",
        default="evals/reports",
        help="Directory with assets-inventory.json, inventory.json, fresh.json, …",
    )
    report.set_defaults(func=cmd_report)

    rebuild = sub.add_parser(
        "rebuild-bm25",
        help="Rebuild BM25 sidecar from the text Chroma collection (no re-embed)",
        description="Rebuild BM25 sidecar from the text Chroma collection (no re-embed)",
    )
    rebuild.set_defaults(func=cmd_rebuild_bm25)

    ev = sub.add_parser(
        "eval",
        help="Run golden-set eval (path metrics; optional RAGAs / 1.7B judge)",
        description="Evaluate retrieve/generate against evals/golden.jsonl",
    )
    ev.add_argument("golden", help="Path to golden JSONL (e.g. evals/golden.jsonl)")
    ev.add_argument("-k", type=int, default=None, help="Top K retrieved chunks")
    ev.add_argument(
        "--text-only",
        action="store_true",
        default=True,
        help="Skip visual collection (default on)",
    )
    ev.add_argument(
        "--with-visual",
        dest="text_only",
        action="store_false",
        help="Include VL retrieval (not recommended on 16GB)",
    )
    ev.add_argument(
        "--retrieve-only",
        action="store_true",
        help="Skip generation and LLM metrics; path recall/precision only",
    )
    ev.add_argument(
        "--enhance",
        action="store_true",
        help="Run query enhance before retrieve (default off for stable eval)",
    )
    ev.add_argument("--limit", type=int, default=None, help="Evaluate only the first N items")
    ev.add_argument("--out", default=None, help="Write full JSON report (e.g. evals/reports/baseline.json)")
    ev.set_defaults(func=cmd_eval)

    prep = sub.add_parser(
        "prepare-retrieval-queries",
        help="Export question-only JSONL for leakage-free retrieval evaluation",
    )
    prep.add_argument("questions", help="questions_draft.json path")
    prep.add_argument(
        "--out",
        default="evals/benchmark_queries.jsonl",
        help="Sanitized JSONL containing only question_id, question, course_id",
    )
    prep.set_defaults(func=cmd_prepare_retrieval_queries)

    bench = sub.add_parser(
        "benchmark-retrieve",
        help="Run one retrieval system over a sanitized query JSONL and save Top-K",
    )
    bench.add_argument("queries", help="Sanitized query JSONL")
    bench.add_argument("--system-id", required=True, help="Stable system label")
    bench.add_argument(
        "--profile",
        choices=("baseline", "proposed"),
        required=True,
        help="baseline=text dense; proposed=hybrid multimodal",
    )
    bench.add_argument("-k", type=int, default=10, help="Top-K to save (minimum 10)")
    bench.add_argument("--out", required=True, help="retrieval_results.jsonl output")
    bench.add_argument("--rerank", action="store_true", help="Enable reranker for proposed")
    bench.add_argument("--no-course-filter", action="store_true", help="Do not pass course_id to retriever")
    bench.add_argument("--start", type=int, default=1, help="1-based first query to run")
    bench.add_argument("--limit", type=int, default=None, help="Run at most N queries")
    bench.add_argument("--resume", action="store_true", help="Append only missing question_ids")
    bench.set_defaults(func=cmd_benchmark_retrieve)

    score = sub.add_parser(
        "score-retrieval",
        help="Score a retrieval JSONL against evidence after retrieval has finished",
    )
    score.add_argument("questions", help="Ground-truth questions_draft.json")
    score.add_argument("results", help="Retrieval result JSONL")
    score.add_argument("--out", required=True, help="Evaluation report JSON")
    score.add_argument(
        "--null-policy",
        choices=("infer", "exclude", "error"),
        default="infer",
        help="infer: evidence=>answerable, empty evidence=>unanswerable",
    )
    score.add_argument(
        "--allow-unindexed-ground-truth",
        action="store_true",
        help="Include questions whose ground-truth resources are absent from ChromaDB",
    )
    score.set_defaults(func=cmd_score_retrieval)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    settings = Settings()
    setup_logging(settings.log_level)
    return int(args.func(args, settings))


if __name__ == "__main__":
    raise SystemExit(main())
