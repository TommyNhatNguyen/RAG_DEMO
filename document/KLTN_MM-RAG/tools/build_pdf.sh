#!/usr/bin/env bash
# Dựng PDF khóa luận: ./tools/build_pdf.sh   (chạy được từ bất kỳ thư mục nào)
#
# - Dùng pdflatex + biber (theo thesis.cls), xuất trung gian vào build/, chép PDF ra KLTN_MM-RAG_ban_thao.pdf.
# - Cần các gói LaTeX và biber; nếu thiếu, xem NOTES.md mục 3 (đã cài vào ~/Library/texlive/2026 và ~/Library/texmf).
# - Thêm -g nếu latexmk từ chối chạy lại sau một lần lỗi:  ./tools/build_pdf.sh -g
set -euo pipefail
cd "$(dirname "$0")/.."

export PATH="$HOME/Library/texlive/2026/bin/universal-darwin:/Library/TeX/texbin:$PATH"
# thesis.cls và references.bib nằm trong src/, còn main.tex gọi \input{src/...} theo đường dẫn từ thư mục này
export TEXINPUTS=".:./src//:" BIBINPUTS=".:./src:"

mkdir -p build/src/chapters build/src/covers
latexmk -pdf -interaction=nonstopmode -file-line-error -outdir=build "$@" src/main.tex
cp build/main.pdf KLTN_MM-RAG_ban_thao.pdf
echo "Đã dựng: $(pwd)/KLTN_MM-RAG_ban_thao.pdf"
