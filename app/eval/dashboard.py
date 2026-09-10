from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any

HYDE_SKIP_REASON = (
    "HyDE tắt vì weakest_metric là precision (không phải recall). "
    "HyDE thêm một danh sách RRF nên thường kéo thêm file — recall đã cao, precision đang yếu."
)


def _esc(value: Any) -> str:
    return html.escape(str(value), quote=True)


def _fmt_int(value: Any) -> str:
    try:
        return f"{int(value):,}".replace(",", ".")
    except (TypeError, ValueError):
        return "0"


def _fmt_bytes(value: Any) -> str:
    try:
        n = int(value)
    except (TypeError, ValueError):
        return "0 B"
    units = ["B", "KB", "MB", "GB", "TB"]
    size = float(n)
    for unit in units:
        if size < 1024 or unit == units[-1]:
            if unit == "B":
                return f"{int(size)} B"
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{n} B"


def _fmt_score(value: Any) -> str:
    if value is None:
        return "—"
    try:
        return f"{float(value):.3f}"
    except (TypeError, ValueError):
        return "—"


def _bar(value: Any, *, max_value: float = 1.0) -> str:
    try:
        ratio = max(0.0, min(1.0, float(value) / max_value if max_value else 0.0))
    except (TypeError, ValueError):
        ratio = 0.0
    pct = int(round(ratio * 100))
    return (
        f'<div class="bar"><span style="width:{pct}%"></span>'
        f'<em>{_fmt_score(value)}</em></div>'
    )


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def load_reports(reports_dir: Path) -> dict[str, Any]:
    reports_dir = Path(reports_dir)
    names = {
        "assets": "assets-inventory.json",
        "inventory": "inventory.json",
        "fresh": "fresh.json",
        "baseline": "baseline.json",
        "post_chunk": "post-chunk.json",
        "phase3_skip": "phase3-skip.json",
    }
    loaded = {key: _load_json(reports_dir / name) for key, name in names.items()}
    loaded["reports_dir"] = str(reports_dir)
    return loaded


def _kv_table(rows: list[tuple[str, str]]) -> str:
    body = "".join(
        f"<tr><th>{_esc(label)}</th><td>{value}</td></tr>" for label, value in rows
    )
    return f'<table class="kv">{body}</table>'


def _dict_table(data: dict[str, Any], *, key_label: str, value_label: str = "Số lượng") -> str:
    if not data:
        return "<p class='muted'>Không có dữ liệu.</p>"
    rows = "".join(
        f"<tr><td>{_esc(k)}</td><td class='num'>{_fmt_int(v)}</td></tr>"
        for k, v in data.items()
    )
    return (
        f"<table><thead><tr><th>{_esc(key_label)}</th><th>{_esc(value_label)}</th></tr></thead>"
        f"<tbody>{rows}</tbody></table>"
    )


def render_dashboard(bundle: dict[str, Any]) -> str:
    assets = bundle.get("assets") or {}
    inventory = bundle.get("inventory") or {}
    fresh = bundle.get("fresh") or {}
    baseline = bundle.get("baseline") or {}
    post_chunk = bundle.get("post_chunk") or {}
    phase3 = bundle.get("phase3_skip") or {}

    inv_assets = inventory.get("assets") or assets
    images = inventory.get("images") or {}
    vectors = inventory.get("vectors") or {}
    flags = inventory.get("flags") or {}
    by_suffix = inv_assets.get("by_suffix") or {}
    by_kind = inv_assets.get("by_kind") or {}
    by_course = inv_assets.get("by_course") or {}
    videos = inv_assets.get("videos") or []
    by_content = vectors.get("by_content_type") or {}
    scores = fresh.get("scores") or {}
    fresh_by_kind = fresh.get("by_kind") or {}

    hyde = flags.get("query_hyde", False)
    loops = flags.get("max_retrieve_loops", 0)
    no_video = flags.get("no_video", True)
    hyde_reason = phase3.get("reason") or HYDE_SKIP_REASON

    summary_rows = [
        ("Tổng file trên đĩa", f"{_fmt_int(inv_assets.get('n_files', 0))} ({_fmt_bytes(inv_assets.get('bytes', 0))})"),
        ("PDF", _fmt_int(by_suffix.get("pdf", 0))),
        ("PPTX", _fmt_int(by_suffix.get("pptx", 0))),
        ("DOCX", _fmt_int(by_suffix.get("docx", 0))),
        ("TXT", _fmt_int(by_suffix.get("txt", 0))),
        ("Ảnh nguồn", _fmt_int(by_kind.get("image", 0))),
        ("Video (đếm, không index)", _fmt_int(by_kind.get("video", 0))),
        ("Ảnh trích xuất (page)", _fmt_int(images.get("page", 0))),
        ("Ảnh trích xuất (picture)", _fmt_int(images.get("picture", 0))),
        ("Vector text_embeddings", _fmt_int(vectors.get("text_count", 0))),
        ("Vector visual_embeddings", _fmt_int(vectors.get("visual_count", 0))),
        ("content_type text", _fmt_int(by_content.get("text", 0))),
        ("content_type table", _fmt_int(by_content.get("table", 0))),
        ("content_type page", _fmt_int(by_content.get("page", 0))),
        ("content_type image", _fmt_int(by_content.get("image", 0))),
        ("content_type video_segment", _fmt_int(by_content.get("video_segment", 0))),
        ("content_type video_frame", _fmt_int(by_content.get("video_frame", 0))),
    ]

    course_rows = []
    for name, data in sorted(by_course.items()):
        kinds = data.get("by_kind") or {}
        course_rows.append(
            "<tr>"
            f"<td>{_esc(name)}</td>"
            f"<td class='num'>{_fmt_int(data.get('files', 0))}</td>"
            f"<td class='num'>{_fmt_bytes(data.get('bytes', 0))}</td>"
            f"<td>{_esc(', '.join(f'{k}={v}' for k, v in kinds.items()))}</td>"
            "</tr>"
        )
    course_table = (
        "<table><thead><tr><th>Môn / thư mục</th><th>File</th><th>Dung lượng</th><th>Loại</th></tr></thead>"
        f"<tbody>{''.join(course_rows) or '<tr><td colspan=4>Không có</td></tr>'}</tbody></table>"
    )

    video_rows = "".join(
        "<tr>"
        f"<td>{_esc(v.get('relative_path'))}</td>"
        f"<td>{_esc(v.get('course'))}</td>"
        f"<td class='num'>{_fmt_bytes(v.get('bytes', 0))}</td>"
        "<td>skip</td>"
        "</tr>"
        for v in videos
    )
    video_table = (
        "<table><thead><tr><th>File video</th><th>Môn</th><th>Dung lượng</th><th>Ingest</th></tr></thead>"
        f"<tbody>{video_rows or '<tr><td colspan=4>Không có file video</td></tr>'}</tbody></table>"
    )

    kind_rows = []
    for kind, data in sorted(fresh_by_kind.items()):
        kind_rows.append(
            "<tr>"
            f"<td>{_esc(kind)}</td>"
            f"<td class='num'>{_fmt_int(data.get('n', 0))}</td>"
            f"<td>{_bar(data.get('path_recall'))}</td>"
            f"<td>{_bar(data.get('path_precision'))}</td>"
            f"<td>{_fmt_score(data.get('path_recall_at_1'))}</td>"
            f"<td>{_fmt_score(data.get('path_recall_at_5'))}</td>"
            f"<td>{_fmt_score(data.get('path_recall_at_10'))}</td>"
            "</tr>"
        )
    kind_table = (
        "<table><thead><tr>"
        "<th>Kind</th><th>n</th><th>Path recall</th><th>Path precision</th>"
        "<th>R@1</th><th>R@5</th><th>R@10</th>"
        "</tr></thead>"
        f"<tbody>{''.join(kind_rows) or '<tr><td colspan=7>Chưa có eval</td></tr>'}</tbody></table>"
    )

    def _score_row(label: str, report: dict[str, Any]) -> str:
        s = report.get("scores") or report
        return (
            "<tr>"
            f"<td>{_esc(label)}</td>"
            f"<td class='num'>{_fmt_int(report.get('n', s.get('n', '—')))}</td>"
            f"<td>{_fmt_score(s.get('path_recall'))}</td>"
            f"<td>{_fmt_score(s.get('path_precision'))}</td>"
            f"<td>{_fmt_score(s.get('path_recall_at_1'))}</td>"
            f"<td>{_fmt_score(s.get('path_recall_at_5'))}</td>"
            f"<td>{_fmt_score(s.get('path_recall_at_10'))}</td>"
            f"<td>{_esc(report.get('weakest_metric') or s.get('weakest_metric') or '—')}</td>"
            "</tr>"
        )

    compare_body = ""
    if baseline:
        compare_body += _score_row("baseline", baseline)
    if post_chunk:
        compare_body += _score_row("post-chunk", post_chunk)
    if fresh:
        compare_body += _score_row("fresh (no video)", fresh)
    compare_table = (
        "<table><thead><tr>"
        "<th>Run</th><th>n</th><th>Path recall</th><th>Path precision</th>"
        "<th>R@1</th><th>R@5</th><th>R@10</th><th>Weakest</th>"
        "</tr></thead>"
        f"<tbody>{compare_body or '<tr><td colspan=8>Chưa có báo cáo so sánh</td></tr>'}</tbody></table>"
    )

    file_type_table = _dict_table(vectors.get("by_file_type") or {}, key_label="file_type")
    course_vec_table = _dict_table(vectors.get("by_course") or {}, key_label="course")

    indexed_paths = {
        str(row.get("relative_path"))
        for row in (inv_assets.get("files") or [])
        if row.get("ingest") != "skip"
    }
    expected: list[str] = []
    for item in fresh.get("items") or []:
        expected.extend(item.get("expected_paths") or [])
    missing_expected = sorted({p for p in expected if p and p not in indexed_paths})
    if missing_expected:
        coverage_note = (
            f'<p class="note">Golden expected_paths không có trong index hiện tại: '
            f"{_fmt_int(len(missing_expected))} path "
            f"(ví dụ {_esc(missing_expected[0])}). "
            "Corpus <code>assets/</code> đã đổi so với golden cũ; "
            "số path recall/precision lần này phản ánh lệch kho, không chỉ chất lượng retrieve. "
            "Video items = 0 vì --no-video.</p>"
        )
    else:
        coverage_note = (
            '<p class="muted">Mục video trong golden có path_recall = 0 vì ingest video bị hoãn.</p>'
        )

    return f"""<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>RAG Multimodal — thống kê kho học liệu</title>
<style>
:root {{
  --bg:#f4efe4; --ink:#1c1914; --muted:#5c564c; --card:#fffdf8;
  --line:#d9d0c0; --accent:#8b3a2a; --bar:#8b3a2a;
}}
* {{ box-sizing:border-box; }}
body {{
  margin:0; font:16px/1.5 "Iowan Old Style","Palatino Linotype",Palatino,serif;
  background:var(--bg); color:var(--ink);
}}
header {{
  padding:2.2rem 1.5rem 1.2rem; max-width:1100px; margin:0 auto;
}}
h1 {{ font-size:1.8rem; margin:0 0 .4rem; letter-spacing:-0.02em; }}
h2 {{ font-size:1.15rem; margin:0 0 .8rem; }}
.lede {{ color:var(--muted); max-width:46rem; }}
main {{ max-width:1100px; margin:0 auto 3rem; padding:0 1.5rem; display:grid; gap:1.2rem; }}
section {{
  background:var(--card); border:1px solid var(--line); border-radius:12px; padding:1.1rem 1.2rem;
}}
table {{ width:100%; border-collapse:collapse; font-size:.95rem; }}
th, td {{ text-align:left; padding:.4rem .45rem; border-bottom:1px solid var(--line); vertical-align:top; }}
th {{ font-weight:600; color:var(--muted); font-size:.82rem; text-transform:uppercase; letter-spacing:.04em; }}
.num {{ font-variant-numeric:tabular-nums; text-align:right; }}
table.kv th {{ width:42%; color:var(--ink); text-transform:none; font-size:.95rem; letter-spacing:0; }}
.muted {{ color:var(--muted); }}
.flags {{ display:flex; flex-wrap:wrap; gap:.4rem; }}
.flag {{
  border:1px solid var(--line); border-radius:999px; padding:.15rem .7rem; font-size:.85rem;
}}
.bar {{
  position:relative; height:1.15rem; background:#efe7d8; border-radius:4px; overflow:hidden;
}}
.bar span {{ display:block; height:100%; background:var(--bar); }}
.bar em {{
  position:absolute; inset:0; display:flex; align-items:center; justify-content:flex-end;
  padding-right:.4rem; font-style:normal; font-size:.78rem; font-variant-numeric:tabular-nums;
}}
.note {{
  background:#f8eee6; border-left:3px solid var(--accent); padding:.7rem .9rem; margin-top:.8rem;
}}
</style>
</head>
<body>
<header>
  <h1>Thống kê kho học liệu RAG đa phương thức</h1>
  <p class="lede">Snapshot sau reset: ingest toàn bộ <code>assets/</code> trừ video. HyDE tắt. Số liệu lấy từ JSON sibling, không đọc Chroma trực tiếp.</p>
</header>
<main>
<section>
  <h2>1. Tóm tắt thống kê</h2>
  {_kv_table(summary_rows)}
</section>
<section>
  <h2>2. Kho học liệu theo môn</h2>
  {course_table}
  <h2 style="margin-top:1.2rem">Video trên đĩa (không index)</h2>
  {video_table}
</section>
<section>
  <h2>3. Vector theo file_type / course</h2>
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:1rem">
    <div>{file_type_table}</div>
    <div>{course_vec_table}</div>
  </div>
</section>
<section>
  <h2>4. Eval golden (retrieve-only)</h2>
  {_kv_table([
      ("n", _fmt_int(fresh.get("n", 0))),
      ("path_recall", _fmt_score(scores.get("path_recall"))),
      ("path_precision", _fmt_score(scores.get("path_precision"))),
      ("Recall@1", _fmt_score(scores.get("path_recall_at_1"))),
      ("Recall@5", _fmt_score(scores.get("path_recall_at_5"))),
      ("Recall@10", _fmt_score(scores.get("path_recall_at_10"))),
      ("weakest_metric", _esc(fresh.get("weakest_metric") or "—")),
      ("next_step", _esc(fresh.get("next_step") or "—")),
  ])}
  {coverage_note}
  {kind_table}
</section>
<section>
  <h2>5. So sánh các lần đo</h2>
  {compare_table}
</section>
<section>
  <h2>6. Flags</h2>
  <div class="flags">
    <span class="flag">QUERY_HYDE={_esc(str(hyde).lower())}</span>
    <span class="flag">MAX_RETRIEVE_LOOPS={_esc(loops)}</span>
    <span class="flag">--no-video={_esc(str(no_video).lower())}</span>
  </div>
  <p class="note">{_esc(hyde_reason)}</p>
</section>
</main>
</body>
</html>
"""


def write_dashboard(path: Path, bundle: dict[str, Any]) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_dashboard(bundle), encoding="utf-8")
    return path
