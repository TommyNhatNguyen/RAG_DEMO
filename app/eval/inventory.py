from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from app.ids import relative_posix
from app.loaders.base import IMAGE_EXTS, detect_kind, iter_input_files
from app.pipeline.indexing import course_from_relative_path

CONTENT_TYPES = (
    "text",
    "table",
    "page",
    "image",
    "video_segment",
    "video_frame",
)


def inventory_assets(assets_root: Path, project_root: Path) -> dict[str, Any]:
    files = iter_input_files(assets_root)
    by_kind: Counter[str] = Counter()
    by_suffix: Counter[str] = Counter()
    by_course: dict[str, dict[str, Any]] = {}
    bytes_by_kind: Counter[str] = Counter()
    videos: list[dict[str, Any]] = []
    total_bytes = 0
    rows: list[dict[str, Any]] = []
    for path in files:
        kind = detect_kind(path) or "unknown"
        suffix = path.suffix.lower().lstrip(".") or "none"
        size = path.stat().st_size if path.exists() else 0
        rel = relative_posix(path, project_root)
        course = course_from_relative_path(rel) or "(root)"
        by_kind[kind] += 1
        by_suffix[suffix] += 1
        bytes_by_kind[kind] += size
        total_bytes += size
        bucket = by_course.setdefault(
            course, {"files": 0, "bytes": 0, "by_kind": Counter(), "by_suffix": Counter()}
        )
        bucket["files"] += 1
        bucket["bytes"] += size
        bucket["by_kind"][kind] += 1
        bucket["by_suffix"][suffix] += 1
        row = {
            "relative_path": rel,
            "kind": kind,
            "suffix": suffix,
            "bytes": size,
            "course": course,
            "ingest": "skip" if kind == "video" else "yes",
        }
        rows.append(row)
        if kind == "video":
            videos.append(row)
    courses = {
        name: {
            "files": data["files"],
            "bytes": data["bytes"],
            "by_kind": dict(data["by_kind"]),
            "by_suffix": dict(data["by_suffix"]),
        }
        for name, data in sorted(by_course.items())
    }
    return {
        "root": str(assets_root),
        "n_files": len(files),
        "bytes": total_bytes,
        "by_kind": dict(by_kind),
        "by_suffix": dict(by_suffix),
        "bytes_by_kind": dict(bytes_by_kind),
        "by_course": courses,
        "videos": videos,
        "files": rows,
    }


def count_storage_images(storage_root: Path) -> dict[str, Any]:
    images_dir = storage_root / "images"
    page = 0
    picture = 0
    other = 0
    bytes_total = 0
    if images_dir.exists():
        for path in images_dir.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in IMAGE_EXTS:
                continue
            size = path.stat().st_size
            bytes_total += size
            name = path.name.lower()
            if name.startswith("page_"):
                page += 1
            elif name.startswith("picture_") or name == "original.png":
                picture += 1
            else:
                other += 1
    frames_dir = storage_root / "frames"
    frames = 0
    frame_bytes = 0
    if frames_dir.exists():
        for path in frames_dir.rglob("*"):
            if path.is_file() and path.suffix.lower() in IMAGE_EXTS:
                frames += 1
                frame_bytes += path.stat().st_size
    return {
        "page": page,
        "picture": picture,
        "other": other,
        "bytes": bytes_total,
        "video_frames_on_disk": frames,
        "video_frame_bytes": frame_bytes,
    }


def count_vector_breakdown(vector_store: Any, text_collection: str, visual_collection: str) -> dict[str, Any]:
    by_content: Counter[str] = Counter()
    by_file_type: Counter[str] = Counter()
    by_course: Counter[str] = Counter()
    by_collection_content: dict[str, Counter[str]] = {
        "text": Counter(),
        "visual": Counter(),
    }
    text_n = 0
    visual_n = 0
    for name, collection, bucket in (
        ("text", text_collection, "text"),
        ("visual", visual_collection, "visual"),
    ):
        try:
            got = vector_store.get(collection)
        except Exception:
            continue
        ids = got.get("ids") or []
        metas = got.get("metadatas") or []
        n = len(ids)
        if name == "text":
            text_n = n
        else:
            visual_n = n
        for meta in metas:
            meta = meta or {}
            ctype = str(meta.get("content_type") or "unknown")
            ftype = str(meta.get("file_type") or "unknown")
            course = str(meta.get("course") or "(none)")
            by_content[ctype] += 1
            by_file_type[ftype] += 1
            by_course[course] += 1
            by_collection_content[bucket][ctype] += 1
    for key in CONTENT_TYPES:
        by_content.setdefault(key, 0)
        by_collection_content["text"].setdefault(key, 0)
        by_collection_content["visual"].setdefault(key, 0)
    return {
        "text_count": text_n,
        "visual_count": visual_n,
        "by_content_type": dict(by_content),
        "by_file_type": dict(by_file_type),
        "by_course": dict(by_course),
        "text_by_content_type": dict(by_collection_content["text"]),
        "visual_by_content_type": dict(by_collection_content["visual"]),
    }


def build_inventory(
    *,
    assets: dict[str, Any],
    storage_images: dict[str, Any],
    vectors: dict[str, Any],
    chroma_path: str,
    storage_root: str,
    manifest: str,
    query_hyde: bool = False,
    max_retrieve_loops: int = 0,
    no_video: bool = True,
) -> dict[str, Any]:
    return {
        "assets": assets,
        "images": storage_images,
        "vectors": vectors,
        "chroma_path": chroma_path,
        "storage_root": storage_root,
        "manifest": manifest,
        "flags": {
            "query_hyde": query_hyde,
            "max_retrieve_loops": max_retrieve_loops,
            "no_video": no_video,
        },
    }


def format_inventory_vi(data: dict[str, Any]) -> str:
    assets = data.get("assets") or {}
    images = data.get("images") or {}
    vectors = data.get("vectors") or {}
    by_suffix = assets.get("by_suffix") or {}
    by_content = vectors.get("by_content_type") or {}
    lines = [
        f"FILES  pdf={by_suffix.get('pdf', 0)} pptx={by_suffix.get('pptx', 0)} "
        f"docx={by_suffix.get('docx', 0)} txt={by_suffix.get('txt', 0)} "
        f"image={assets.get('by_kind', {}).get('image', 0)} "
        f"video={assets.get('by_kind', {}).get('video', 0)} (skipped)  "
        f"n={assets.get('n_files', 0)} bytes={assets.get('bytes', 0)}",
        f"IMAGES extracted page={images.get('page', 0)} picture={images.get('picture', 0)} "
        f"other={images.get('other', 0)} bytes={images.get('bytes', 0)}",
        f"VECTORS text_collection={vectors.get('text_count', 0)} "
        f"visual_collection={vectors.get('visual_count', 0)}",
        "  content_type "
        + " ".join(f"{key}={by_content.get(key, 0)}" for key in CONTENT_TYPES),
    ]
    return "\n".join(lines)
