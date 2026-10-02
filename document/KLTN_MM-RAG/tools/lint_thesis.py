#!/usr/bin/env python3
"""Kiểm tra bản thảo khóa luận theo các quy tắc của người dùng (chỉ dùng thư viện chuẩn).

Chạy từ thư mục KLTN_MM-RAG:
    python3 tools/lint_thesis.py              # kiểm tra tất cả
    python3 tools/lint_thesis.py --todos      # liệt kê mọi \\todo{...}
    python3 tools/lint_thesis.py --english    # cảnh báo từ tiếng Anh nghi vấn ngoài bảng thuật ngữ
    python3 tools/lint_thesis.py --build-lists  # sinh danh mục viết tắt và danh mục từ tạm dịch

Các kiểm tra:
  1. Thuật ngữ (tools/glossary.json), theo thứ tự đọc: Tóm tắt -> Chương 1..5
     - lần đầu phải đúng dạng "tiếng Việt (English - VIẾT TẮT)" hoặc "tiếng Việt (English)" nếu không có viết tắt;
     - các lần sau: thuật ngữ có viết tắt chỉ dùng VIẾT TẮT; thuật ngữ không có viết tắt dùng lại tiếng Việt;
     - tiêu đề chương/mục/tiểu mục và chú thích hình/bảng chỉ dùng tiếng Việt đầy đủ (không viết tắt, không tiếng Anh);
     - không dùng trước khi định nghĩa; không định nghĩa lặp lại.
  2. \\cite phải có trong references.bib; khóa trong .bib chưa được dùng sẽ được báo.
  3. \\ref phải có \\label; \\label trùng nhau; các tệp \\input tồn tại.
  4. Cặp \\begin/\\end và dấu ngoặc nhọn cân bằng.
Mã thoát 1 nếu có lỗi.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
CHAPTERS = [
    "0.tom_tat.tex",
    "1.tong_quan_de_tai.tex",
    "2.co_so_ly_thuyet.tex",
    "3.phuong_phap_thuc_hien.tex",
    "4.hien_thuc_danh_gia_thao_luan.tex",
    "5.ket_luan.tex",
]
CMD_MASK = ["texttt", "url", "cite", "ref", "eqref", "label", "nameref", "input", "include", "includegraphics", "todo", "tcp", "textcolor", "href"]
HEADING_CMDS = ["chapter", "section", "subsection", "subsubsection"]
ENV_MASK = ["equation", "equation*", "algorithm", "verbatim", "tikzpicture"]
WATCH = [
    "retrieval", "generation", "augmented", "query", "queries", "pipeline", "embedding", "embeddings", "benchmark",
    "baseline", "ground truth", "fallback", "prompt", "chunk", "chunking", "metadata", "timestamp", "transcript",
    "checkpoint", "sidecar", "reranker", "rerank", "ablation", "framework", "dataset", "token", "tokens", "score",
    "streaming", "end-to-end", "hit rate", "seed", "hybrid", "dense", "sparse", "recall", "precision", "fusion",
]
CHAPTER_LOCAL_TERMS = {
    "rag", "dense", "sparse", "hybrid", "prompt", "token", "embedding",
    "reranker", "llm", "vlm", "chunking", "rrf", "average_hash", "ablation",
    "sidecar", "checkpoint", "pipeline", "ground_truth", "benchmark",
    "bootstrap", "hit_rate", "faithfulness", "answer_relevancy",
}


def nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s)


def blank(text: str, start: int, end: int) -> str:
    """Thay đoạn [start,end) bằng khoảng trắng nhưng giữ nguyên xuống dòng để bảo toàn số dòng."""
    seg = "".join(c if c == "\n" else " " for c in text[start:end])
    return text[:start] + seg + text[end:]


def strip_comments(text: str) -> str:
    out = []
    for line in text.split("\n"):
        i = 0
        cut = None
        while i < len(line):
            if line[i] == "\\":
                i += 2
                continue
            if line[i] == "%":
                cut = i
                break
            i += 1
        out.append(line if cut is None else line[:cut] + " " * (len(line) - cut))
    return "\n".join(out)


def match_brace(text: str, open_idx: int) -> int:
    """open_idx trỏ tới '{'; trả về vị trí '}' tương ứng hoặc -1."""
    depth = 0
    i = open_idx
    while i < len(text):
        c = text[i]
        if c == "\\":
            i += 2
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return -1


def find_cmd_spans(text: str, cmd: str):
    """Trả về danh sách (start, arg_start, arg_end, end) của \\cmd[..]{...} (arg_end là vị trí '}')."""
    spans = []
    for m in re.finditer(r"\\" + re.escape(cmd) + r"(?![A-Za-z])", text):
        i = m.end()
        if i < len(text) and text[i] == "*":
            i += 1
        while i < len(text) and text[i] == " ":
            i += 1
        if i < len(text) and text[i] == "[":
            j = text.find("]", i)
            if j == -1:
                continue
            i = j + 1
        while i < len(text) and text[i] == " ":
            i += 1
        if i < len(text) and text[i] == "{":
            close = match_brace(text, i)
            if close != -1:
                spans.append((m.start(), i + 1, close, close + 1))
    return spans


def line_of(text: str, pos: int) -> int:
    return text.count("\n", 0, pos) + 1


class Report:
    def __init__(self):
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def err(self, fn: str, line: int, msg: str):
        self.errors.append(f"{fn}:{line}: {msg}")

    def warn(self, fn: str, line: int, msg: str):
        self.warnings.append(f"{fn}:{line}: {msg}")


def load_glossary():
    data = json.loads((ROOT / "tools" / "glossary.json").read_text(encoding="utf-8"))
    terms = []
    for t in data["terms"]:
        vi, en, abbr = nfc(t["vi"]), t["en"], t.get("abbr", "")
        vi_p = re.escape(vi).replace(r"\ ", r"\s+")
        en_p = re.escape(en).replace(r"\ ", r"\s+")
        en_p_formatted = r"(?:\\textit\{\s*" + en_p + r"\s*\}|" + en_p + r")"
        b_l, b_r = r"(?<![\w])", r"(?![\w])"
        if abbr:
            defre = re.compile(b_l + r"(?i:" + vi_p + r"\s*\(\s*" + en_p_formatted + r"\s*-\s*)(?-i:" + re.escape(abbr) + r")\s*\)")
            abbre = re.compile(b_l + re.escape(abbr) + b_r)
        else:
            defre = re.compile(b_l + r"(?i:" + vi_p + r"\s*\(\s*" + en_p_formatted + r"\s*\))")
            abbre = None
        terms.append({
            "id": t["id"], "vi": vi, "en": en, "abbr": abbr,
            "def": defre,
            "vire": re.compile(b_l + r"(?i:" + vi_p + r")" + b_r),
            "enre": re.compile(b_l + r"(?i:" + en_p + r")" + b_r),
            "abbre": abbre,
        })
    return terms, data.get("_ngoai_le_ten_rieng", [])


def prepare(fn: str, raw: str, exempt: list[str], rep: Report):
    """Trả về (body, headings) đã che các phần không cần kiểm tra thuật ngữ."""
    text = nfc(raw)
    if text != raw:
        rep.warn(fn, 1, "tệp không ở dạng Unicode NFC; đã chuẩn hóa khi kiểm tra")
    text = strip_comments(text)

    for env in ENV_MASK:
        for m in list(re.finditer(r"\\begin\{" + re.escape(env) + r"\}.*?\\end\{" + re.escape(env) + r"\}", text, flags=re.S)):
            text = blank(text, m.start(), m.end())
    for m in list(re.finditer(r"(?<!\\)\$.*?(?<!\\)\$", text, flags=re.S)):
        text = blank(text, m.start(), m.end())
    for cmd in CMD_MASK:
        for s, a0, a1, e in reversed(find_cmd_spans(text, cmd)):
            text = blank(text, s, e)

    headings = []
    body = text
    for cmd in HEADING_CMDS:
        for s, a0, a1, e in reversed(find_cmd_spans(body, cmd)):
            headings.append((line_of(body, s), body[a0:a1], f"\\{cmd}"))
            body = blank(body, s, e)
    for s, a0, a1, e in reversed(find_cmd_spans(body, "caption")):
        head = body[s:a0]
        opt = re.search(r"\[(.*)\]", head, flags=re.S)
        headings.append((line_of(body, s), body[a0:a1], "\\caption"))
        if opt:
            headings.append((line_of(body, s), opt.group(1), "\\caption[..]"))
        body = blank(body, s, e)

    for name in sorted(exempt, key=len, reverse=True):
        pat = name[3:] if name.startswith("re:") else re.escape(name)
        body = re.sub(r"(?<![\w])(?:" + pat + r")(?![\w])", lambda m: " " * len(m.group(0)), body)
    return body, headings


def check_glossary(rep: Report, terms, files: dict[str, tuple[str, list]]):
    first_seen: dict[str, str] = {}
    used: dict[str, bool] = {t["id"]: False for t in terms}
    for fn in CHAPTERS:
        if fn not in files:
            continue
        chapter_seen: dict[str, str] = {}
        body, headings = files[fn]
        events = []  # (pos, term, kind)
        masked = body
        for t in terms:
            for m in t["def"].finditer(body):
                events.append((m.start(), t, "def"))
        # che các đoạn định nghĩa để không đếm các thành phần bên trong như lần dùng riêng lẻ
        for pos, t, kind in events:
            m = t["def"].search(body, pos)
            if m and m.start() == pos:
                masked = blank(masked, m.start(), m.end())
        for t in terms:
            for m in t["vire"].finditer(masked):
                events.append((m.start(), t, "vi"))
            for m in t["enre"].finditer(masked):
                events.append((m.start(), t, "en"))
            if t["abbre"] is not None:
                for m in t["abbre"].finditer(masked):
                    events.append((m.start(), t, "abbr"))
        events.sort(key=lambda e: e[0])
        for pos, t, kind in events:
            line = line_of(body, pos)
            tid = t["id"]
            used[tid] = True
            label = f"{t['vi']} / {t['en']}" + (f" / {t['abbr']}" if t["abbr"] else "")
            seen = chapter_seen if tid in CHAPTER_LOCAL_TERMS else first_seen
            if kind == "def":
                if tid in seen:
                    rep.err(fn, line, f"định nghĩa lặp lại trong chương (đã định nghĩa ở {seen[tid]}): {label}")
                else:
                    seen[tid] = f"{fn}:{line}"
                    first_seen.setdefault(tid, seen[tid])
                continue
            if tid not in seen:
                form = f"{t['vi']} ({t['en']}" + (f" - {t['abbr']})" if t["abbr"] else ")")
                shown = {"vi": t["vi"], "en": t["en"], "abbr": t["abbr"]}[kind]
                rep.err(fn, line, f"'{shown}' xuất hiện lần đầu chưa đúng dạng; cần: {form}")
                seen[tid] = f"{fn}:{line}(sai dạng)"
                first_seen.setdefault(tid, seen[tid])
                continue
            if t["abbr"]:
                if kind == "vi":
                    rep.err(fn, line, f"đã có viết tắt, không lặp lại tiếng Việt đầy đủ: '{t['vi']}' -> {t['abbr']}")
                elif kind == "en":
                    rep.err(fn, line, f"đã có viết tắt, không lặp lại tiếng Anh đầy đủ: '{t['en']}' -> {t['abbr']}")
            else:
                if kind == "en":
                    rep.err(fn, line, f"không dùng lại tiếng Anh '{t['en']}' sau lần đầu; dùng '{t['vi']}'")
        # tiêu đề / chú thích
        for line, htxt, hkind in headings:
            for t in terms:
                if t["abbre"] is not None and t["abbre"].search(htxt):
                    rep.err(fn, line, f"{hkind}: tiêu đề/chú thích chứa viết tắt {t['abbr']}; dùng '{t['vi']}'")
                if t["enre"].search(htxt):
                    rep.err(fn, line, f"{hkind}: tiêu đề/chú thích chứa tiếng Anh '{t['en']}'; dùng '{t['vi']}'")
    return first_seen, used


def check_refs(rep: Report):
    bib = (SRC / "references.bib").read_text(encoding="utf-8")
    bib_keys = set(re.findall(r"@\w+\s*\{\s*([^,\s]+)\s*,", bib))
    labels: dict[str, str] = {}
    refs: list[tuple[str, int, str]] = []
    cites: list[tuple[str, int, str]] = []
    inputs: list[tuple[str, int, str]] = []
    for fn in CHAPTERS:
        path = SRC / "chapters" / fn
        if not path.exists():
            continue
        text = strip_comments(nfc(path.read_text(encoding="utf-8")))
        for m in re.finditer(r"\\label\{([^}]*)\}", text):
            key = m.group(1)
            if key in labels:
                rep.err(fn, line_of(text, m.start()), f"label trùng: {key} (đã có ở {labels[key]})")
            labels[key] = f"{fn}:{line_of(text, m.start())}"
        for m in re.finditer(r"\\(?:ref|eqref|nameref)\{([^}]*)\}", text):
            refs.append((fn, line_of(text, m.start()), m.group(1)))
        for m in re.finditer(r"\\cite\w*\{([^}]*)\}", text):
            for key in m.group(1).split(","):
                cites.append((fn, line_of(text, m.start()), key.strip()))
        for m in re.finditer(r"\\input\{([^}]*)\}", text):
            inputs.append((fn, line_of(text, m.start()), m.group(1)))
        for env in set(re.findall(r"\\begin\{([^}]*)\}", text)):
            b = len(re.findall(r"\\begin\{" + re.escape(env) + r"\}", text))
            e = len(re.findall(r"\\end\{" + re.escape(env) + r"\}", text))
            if b != e:
                rep.err(fn, 1, f"\\begin{{{env}}} ({b}) khác \\end{{{env}}} ({e})")
        depth = 0
        for i, c in enumerate(re.sub(r"\\[{}]", "  ", text)):
            depth += c == "{"
            depth -= c == "}"
            if depth < 0:
                rep.err(fn, 1, "dấu ngoặc nhọn đóng thừa")
                break
        if depth > 0:
            rep.err(fn, 1, f"thiếu {depth} dấu ngoặc nhọn đóng")
    # Các label ở tệp ngoài chapters (main.tex có thể tham chiếu) được bỏ qua vì không dùng.
    for fn, line, key in refs:
        if key not in labels:
            rep.err(fn, line, f"\\ref tới label không tồn tại: {key}")
    used_cites = set()
    for fn, line, key in cites:
        used_cites.add(key)
        if key not in bib_keys:
            rep.err(fn, line, f"\\cite tới khóa không có trong references.bib: {key}")
    for key in sorted(bib_keys - used_cites):
        rep.warn("references.bib", 1, f"khóa chưa được trích dẫn: {key} (nên xóa khỏi .bib theo hướng dẫn của mẫu)")
    for fn, line, target in inputs:
        cand = ROOT / (target if target.endswith(".tex") else target + ".tex")
        if not cand.exists():
            rep.err(fn, line, f"\\input tới tệp không tồn tại: {target}")


def list_todos():
    total = 0
    for fn in [f"chapters/{c}" for c in CHAPTERS] + ["covers/title_page.tex", "covers/second_title_page.tex", "loi_cam_on.tex", "hoi_dong.tex"]:
        path = SRC / fn
        if not path.exists():
            continue
        text = strip_comments(nfc(path.read_text(encoding="utf-8")))
        for s, a0, a1, e in find_cmd_spans(text, "todo"):
            total += 1
            msg = " ".join(text[a0:a1].split())
            print(f"[{total:02d}] {fn}:{line_of(text, s)}  {msg}")
    print(f"\nTổng cộng {total} mục \\todo.")


def check_english(rep: Report, terms, files):
    known = set()
    for t in terms:
        known.update(w.lower() for w in re.split(r"\W+", t["en"]) if w)
    for fn in CHAPTERS:
        if fn not in files:
            continue
        body, _ = files[fn]
        for w in WATCH:
            if w.lower() in known and len(w.split()) == 1:
                pass
            for m in re.finditer(r"(?<![\w-])" + re.escape(w) + r"(?![\w-])", body, flags=re.I):
                rep.warn(fn, line_of(body, m.start()), f"từ tiếng Anh nghi vấn '{m.group(0)}' nằm ngoài quy tắc thuật ngữ (kiểm tra thủ công)")


def build_lists(terms, first_seen):
    used = [t for t in terms if t["id"] in first_seen]
    abbr = sorted((t for t in used if t["abbr"]), key=lambda t: t["abbr"].lower())
    lines = ["\\chapter*{\\abbrevname}", "\\addcontentsline{toc}{section}{\\textbf{\\abbrevname}}", "\\begin{abbreviations}{ll}", ""]
    for t in abbr:
        lines += [f"\\textbf{{{t['abbr']}}} & {t['en']} \\\\", "\\addlinespace"]
    lines += ["", "\\end{abbreviations}", ""]
    (SRC / "danh_muc_viet_tat.tex").write_text("\n".join(lines), encoding="utf-8")

    def cap(s: str) -> str:
        return s[:1].upper() + s[1:]

    trans = sorted(used, key=lambda t: t["vi"].lower())
    lines = ["\\chapter*{\\transname}", "\\addcontentsline{toc}{section}{\\textbf{\\transname}}", "", "\\begin{translatetion}{p{0.44\\linewidth}p{0.44\\linewidth}}", ""]
    for t in trans:
        en = t["en"] if not t["abbr"] else t["en"]
        lines += [f"{cap(t['vi'])} & {en} \\\\", "\\addlinespace"]
    lines += ["", "\\end{translatetion}", ""]
    (SRC / "danh_muc_dich.tex").write_text("\n".join(lines), encoding="utf-8")
    print(f"Đã sinh danh_muc_viet_tat.tex ({len(abbr)} mục) và danh_muc_dich.tex ({len(trans)} mục).")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--todos", action="store_true")
    ap.add_argument("--english", action="store_true")
    ap.add_argument("--build-lists", action="store_true")
    ap.add_argument("--force", action="store_true", help="sinh danh mục kể cả khi còn lỗi")
    args = ap.parse_args()

    if args.todos:
        list_todos()
        return 0

    rep = Report()
    terms, exempt = load_glossary()
    files = {}
    for fn in CHAPTERS:
        path = SRC / "chapters" / fn
        if not path.exists():
            rep.err(fn, 1, "thiếu tệp chương")
            continue
        files[fn] = prepare(fn, path.read_text(encoding="utf-8"), exempt, rep)
    first_seen, used = check_glossary(rep, terms, files)
    check_refs(rep)
    if args.english:
        check_english(rep, terms, files)
    for tid, was_used in used.items():
        if not was_used:
            rep.warn("glossary.json", 1, f"thuật ngữ chưa được dùng: {tid}")

    for w in rep.warnings:
        print("WARN ", w)
    for e in rep.errors:
        print("ERROR", e)
    print(f"\n{len(rep.errors)} lỗi, {len(rep.warnings)} cảnh báo.")
    if args.build_lists:
        if rep.errors and not args.force:
            print("Còn lỗi; không sinh danh mục (dùng --force để bỏ qua).")
        else:
            build_lists(terms, first_seen)
    return 1 if rep.errors else 0


if __name__ == "__main__":
    sys.exit(main())
