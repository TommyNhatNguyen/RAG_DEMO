#!/usr/bin/env bash
# Test Qwen3-1.7B RAG answers against each ingest modality.
#
# Usage (repo root, venv activated):
#   ./scripts/test_llm_by_type.sh
#   ONLY=docx,pdf ./scripts/test_llm_by_type.sh
#   SKIP_INGEST=1 ./scripts/test_llm_by_type.sh
#   SKIP_VIDEO=1 ./scripts/test_llm_by_type.sh
#   ONLY=image ./scripts/test_llm_by_type.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

PYTHON="${PYTHON:-python}"
LOG_DIR="${LOG_DIR:-$ROOT/tmp/llm_type_tests}"
mkdir -p "$LOG_DIR"

ensure_image_fixture() {
  local dest="$ROOT/scripts/fixtures/sample.png"
  [[ -f "$dest" ]] && return 0
  "$PYTHON" - <<'PY'
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

dest = Path("scripts/fixtures/sample.png")
dest.parent.mkdir(parents=True, exist_ok=True)
image = Image.new("RGB", (640, 240), (255, 255, 255))
draw = ImageDraw.Draw(image)
try:
    font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 28)
except OSError:
    font = ImageFont.load_default()
draw.text((24, 80), "QUAN HE PHAN XA  {1,2,3,4}", fill=(0, 0, 0), font=font)
draw.text((24, 140), "OCR fixture for multimodal RAG", fill=(40, 40, 40), font=font)
image.save(dest)
print(f"Wrote {dest}")
PY
}

ensure_image_fixture

# kind|path|query|text-only|ingest_env
CASES=(
  "docx|./assets/test/bai_tap_chuong_3.docx|Quan hệ phản xạ, đối xứng, bắc cầu trên tập {1,2,3,4}|1|"
  "pdf|./assets/hethongquytrinhnghiepvu/chap01.pdf|Tóm tắt nội dung chương 1 hệ thống quy trình nghiệp vụ|1|"
  "pptx|./assets/test/Chuong_3_quan_he.pptx|Giải thích các loại quan hệ trên slide chương 3|0|"
  "txt|./scripts/fixtures/sample.txt|Tóm tắt nội dung file sample.txt về quan hệ phản xạ|1|"
  "md|./scripts/fixtures/sample.md|Quan hệ phản xạ được định nghĩa thế nào trong file markdown?|1|"
  "image|./scripts/fixtures/sample.png|Hình này có chữ gì? Trích đúng nội dung OCR nếu có|0|"
  "video|./assets/test/buoi_3.mp4|Giảng viên nói gì ở đầu buổi học? Ghi mốc thời gian|0|VIDEO_MAX_DURATION=60"
)

want_kind() {
  local kind="$1"
  [[ -z "${ONLY:-}" ]] && return 0
  [[ ",${ONLY}," == *",${kind},"* ]]
}

run_ask() {
  local query="$1"
  local text_only="$2"
  local log="$3"
  local extra=()
  local rc=0
  [[ "$text_only" == "1" ]] && extra+=(--text-only)
  # --no-stream is easier to grep; still uses Qwen3-1.7B thinking OFF.
  set +e
  "$PYTHON" -m app.main ask "$query" --no-stream --show-hits -k 8 "${extra[@]}" | tee "$log"
  rc=${PIPESTATUS[0]}
  set -e
  return "$rc"
}

pass=0
fail=0
skip=0

for row in "${CASES[@]}"; do
  IFS='|' read -r kind path query text_only ingest_env <<<"$row"
  want_kind "$kind" || continue

  if [[ "$kind" == "video" && "${SKIP_VIDEO:-0}" == "1" ]]; then
    echo "SKIP $kind (SKIP_VIDEO=1)"
    skip=$((skip + 1))
    continue
  fi
  if [[ ! -f "$path" ]]; then
    echo "SKIP $kind — missing $path"
    skip=$((skip + 1))
    continue
  fi

  echo
  echo "========== $kind =========="
  echo "file : $path"
  echo "query: $query"
  echo "visual retrieval: $([[ "$text_only" == "1" ]] && echo no || echo yes)"

  if [[ "${SKIP_INGEST:-0}" != "1" ]]; then
    echo "-- ingest --"
    if [[ -n "${ingest_env:-}" ]]; then
      # shellcheck disable=SC2086
      env $ingest_env "$PYTHON" -m app.main ingest "$path"
    else
      "$PYTHON" -m app.main ingest "$path"
    fi
  fi

  log="$LOG_DIR/${kind}.txt"
  echo "-- ask --"
  set +e
  run_ask "$query" "$text_only" "$log"
  rc=$?
  set -e

  base="$(basename "$path")"
  if [[ $rc -ne 0 ]]; then
    echo "FAIL $kind (ask exit $rc)"
    fail=$((fail + 1))
    continue
  fi
  if ! grep -Fq "$base" "$log"; then
    echo "WARN $kind: filename $base not found in ask output (check hits / hallucination)"
  fi
  if grep -Eq 'length: 0 chars' "$log"; then
    echo "FAIL $kind: empty answer"
    fail=$((fail + 1))
    continue
  fi
  echo "PASS $kind  (log: $log)"
  pass=$((pass + 1))
done

echo
echo "done pass=$pass fail=$fail skip=$skip"
echo "logs in $LOG_DIR"
[[ "$fail" -eq 0 ]]
