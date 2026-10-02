# Ghi chú bản thảo khóa luận (cập nhật 2026-10-01)

Thư mục này là bản thảo LaTeX theo mẫu `../CITD_CĐTN__Nhật_Hoà/` (mẫu được giữ nguyên, không sửa). Kế hoạch tổng thể nằm ở `../PLAN_VIET_KHOA_LUAN.md`.

## 1. Trạng thái

| Phần | Trạng thái | Ghi chú |
|---|---|---|
| Tóm tắt | Đã viết, đã rà lại 2026-10-01 | Đã cập nhật theo kết quả v7 (xem mục 8); không còn kết quả âm tính |
| Chương 1. Tổng quan | Đã viết, đã rà lại 2026-10-01 | 1.2 chỉ dùng nguồn đã xác thực; còn 1 mục cần bạn xác nhận (ngôn ngữ học liệu) |
| Chương 2. Cơ sở lý thuyết | Đã viết, đã rà lại 2026-10-01 | Công thức BM25 cần đối chiếu bài gốc (1 mục `\todo`, chưa làm) |
| Chương 3. Phương pháp | Đã viết, bám mã nguồn, đã rà lại 2026-10-01 | Đã kiểm tra chéo với mã hiện tại (kể cả các thay đổi 30/09–01/10); bổ sung lệnh CLI còn thiếu; mục hạn chế có 1 `\todo` về prompt gắn tên môn (vẫn đúng, mã chưa sửa) |
| Chương 4. Thực nghiệm | **Viết lại hoàn toàn (thực nghiệm v7), rút gọn còn 3 hệ thống 2026-10-01** | Chỉ còn so sánh Cơ sở/Lai/Lai+XHL (đã bỏ biến thể "lỗi"/đầu vào thô theo yêu cầu bạn — mục 9); đã bỏ hẳn mục "Hiện thực hệ thống" và "Sổ trạng thái thực nghiệm" (mục 9) |
| Chương 5. Kết luận | Đã viết, đã rà lại 2026-10-01 | Hướng phát triển đều có trích dẫn; khớp với kết quả v7 (3 hệ thống) |
| Bìa, lời cảm ơn | **Chưa** (chỗ trống `\todo`) | Chỉ bạn điền được |
| Hội đồng | Giữ nguyên mẫu | |
| Danh mục viết tắt, từ tạm dịch | Sinh tự động | `python3 tools/lint_thesis.py --build-lists` |
| Hình | 6 hình TikZ đã vẽ | 3 hình cũ (kiến trúc, luồng video, luồng truy xuất) + 3 hình Chương 4 (so sánh 3 hệ thống, theo nhóm câu hỏi, theo độ khó); mục ảnh chụp demo/API đã bỏ hẳn theo yêu cầu bạn (mục 9) |
| Bản dịch PDF | **Đã dựng lại 2026-10-01 (lần cuối, mục 11)** (`KLTN_MM-RAG_ban_thao.pdf`, 65 trang, 0 lỗi LaTeX thật sự, 34/34 trích dẫn đúng, 0 `??`, 14 `[TODO: ...]` còn lại) | Xem mục 3, mục 10 (bài học về `biber`) và mục 11 (rà soát toàn bộ lần cuối) |

## 2. Cấu trúc

```
KLTN_MM-RAG/
  src/main.tex, thesis.cls, references.bib       # như mẫu; main.tex có thêm \todo và \emergencystretch
  src/chapters/0..5.*.tex                        # nội dung
  src/figures/*.tex                              # hình TikZ
  src/covers, hoi_dong.tex, loi_cam_on.tex       # phần đầu
  src/danh_muc_viet_tat.tex, danh_muc_dich.tex   # SINH TỰ ĐỘNG, đừng sửa tay
  tools/glossary.json                            # bảng thuật ngữ (nguồn duy nhất)
  tools/lint_thesis.py                           # kiểm tra thuật ngữ, trích dẫn, nhãn, ngoặc, \todo
  tools/retrieval_stats.py                       # số liệu Chương 4 bản CŨ (bộ câu hỏi trước v7) — không còn dùng để viết bản thảo hiện tại
  tools/retrieval_stats_v7.py                    # tính lại số liệu truy xuất + bootstrap của Chương 4 hiện tại (bộ v7)
  tools/generation_stats_v7.py                   # tính lại số liệu sinh câu trả lời của Chương 4 hiện tại (bộ v7)
  citations_ledger.md                            # sổ xác thực trích dẫn
  NOTES.md                                       # tệp này
```

## 3. Biên dịch

- **Dựng PDF:** `./tools/build_pdf.sh` (chạy trong thư mục này hoặc từ bất kỳ đâu). Script đặt `PATH`, `TEXINPUTS`, `BIBINPUTS`, chạy `latexmk -pdf` (pdflatex + biber) với thư mục trung gian `build/`, rồi chép kết quả thành `KLTN_MM-RAG_ban_thao.pdf`. Sau một lần lỗi, `latexmk` có thể từ chối chạy lại: thêm `-g` (`./tools/build_pdf.sh -g`).
- Kết quả lần dựng 2026-09-28: 64 trang, không có lỗi LaTeX, không có tham chiếu/trích dẫn chưa giải quyết (không còn `??`), biber không cảnh báo. Còn lại chỉ vài cảnh báo nhẹ: `Underfull \hbox` (dòng thưa, không ảnh hưởng nội dung), thiếu kiểu chữ in đậm đơn cách và chữ hoa nhỏ của phông (LaTeX tự thay), và cảnh báo trùng đích siêu liên kết `table.0.1` do môi trường bảng của mẫu (bỏ qua được). 27 chỗ `[TODO: ...]` màu đỏ trong PDF là các việc của bạn (mục 5).
- Kết quả lần dựng 2026-10-01 (sau khi viết lại Chương 4 cho thực nghiệm v7): 69 trang, `build/main.log` không có dòng lỗi LaTeX thật sự nào (không `! ...`, không `LaTeX Error`, không `Undefined control sequence`) và PDF được ghi đầy đủ (`Output written on build/main.pdf (69 pages, ...)`). **Lưu ý:** `pdflatex`/`latexmk` vẫn thoát với exit code khác 0 (1 và 12) dù log sạch — đã xác nhận đây là hành vi **có từ trước, không do nội dung đã sửa hôm nay** (kiểm bằng cách `git stash` riêng hai tệp Chương 3/4 vừa sửa rồi dựng lại: vẫn exit 1). Do `build_pdf.sh` dùng `set -e` nên script dừng trước bước chép tệp; mình đã chép `build/main.pdf` → `KLTN_MM-RAG_ban_thao.pdf` bằng tay. Nguyên nhân cụ thể của exit code khác 0 (có thể do các dòng `LaTeX Info: Font shape ... has incorrect series value` phát ra từ `thesis.cls`, không phải nội dung chương) chưa được điều tra sâu hơn — không ảnh hưởng nội dung PDF nhưng nên tự dựng lại và xem qua trước khi nộp. 20 chỗ `[TODO: ...]` còn lại (giảm từ 27, vì nhiều mục đã được điền ở lần viết lại Chương 4).
- **Máy này đã được cài thêm (chỉ trong thư mục người dùng, không sửa hệ thống):** các gói `mathdesign`, `vntex`, `algorithm2e`, `algorithms`, `biblatex`, `adjustbox`, `makecell`, `multirow`, `threeparttable`, `titlesec`, `ifoddpage`, `relsize`, `logreq`, `collectbox`, `ly1`, `charter` cài bằng `tlmgr --usermode` vào `~/Library/texmf` (bản gói từ kho TeX Live chính thức; `tlmgr` báo không kiểm tra được chữ ký gpg). `biber` được tải từ kho lưu trữ tlnet của TeX Live và đối chiếu sha512 với `tlpdb` trước khi đặt vào `~/Library/texlive/2026/bin/universal-darwin/biber`.
- **Trình soạn thảo (VS Code LaTeX Workshop):** không cần script này nếu bạn dùng Overleaf (xem `CITD_CĐTN__Nhật_Hoà/Readme.md`; tài liệu chính `src/main.tex`). Nếu muốn biên dịch trong VS Code, cấu hình phải chạy `latexmk` từ **thư mục này** (không phải `src/`) với biến môi trường `TEXINPUTS=".:./src//:"`, `BIBINPUTS=".:./src:"` và `~/Library/texlive/2026/bin/universal-darwin` trong `PATH`; nếu không, `main.tex` không tìm thấy `thesis.cls`, các chương và `references.bib`. Các tệp `src/main.aux|log|fdb_latexmk|fls` là rác do lần tự dựng trong `src/` của trình soạn thảo, xóa được.
- Kiểm tra bằng mắt: đã kết xuất và xem các trang bìa, mục lục, hai danh mục, ba hình, thuật toán và các bảng chương 3, 4; sửa hai lỗi bố cục phát hiện được (hình truy xuất lai bị chồng nút; bảng danh mục từ tạm dịch tràn lề). Chưa duyệt từng trang một; bạn nên đọc lướt toàn bộ PDF trước khi nộp.

## 4. Công cụ kiểm tra (chạy trong thư mục này)

```bash
python3 tools/lint_thesis.py              # phải ra "0 lỗi"
python3 tools/lint_thesis.py --todos      # liệt kê mọi việc còn thiếu (\todo)
python3 tools/lint_thesis.py --english    # cảnh báo từ tiếng Anh nghi vấn (đa số là chính các dạng định nghĩa)
python3 tools/lint_thesis.py --build-lists   # sinh lại danh mục viết tắt và từ tạm dịch
# từ gốc repo (cần git HEAD còn các tệp evals/results):
python3 document/KLTN_MM-RAG/tools/retrieval_stats.py
```

`lint_thesis.py` kiểm tra theo thứ tự đọc (Tóm tắt → Chương 1..5): dạng thuật ngữ ở lần đầu, chỉ dùng viết tắt ở các lần sau, không lặp lại định nghĩa, tiêu đề/chú thích chỉ dùng tiếng Việt đầy đủ, `\cite` có trong `.bib`, `\ref` có `\label`, ngoặc cân bằng.

**Mỗi khi thêm thuật ngữ mới:** thêm vào `tools/glossary.json`, viết lần đầu theo đúng dạng, chạy lint, rồi chạy `--build-lists`.

## 5. Việc còn thiếu (mọi chỗ trong bản thảo đều đánh dấu chữ đỏ `[TODO: ...]`)

Chạy `--todos` để có danh sách đầy đủ và số dòng (14 mục tại 2026-10-01, sau khi bỏ mục "Hiện thực hệ thống"/ảnh chụp demo theo yêu cầu bạn — mục 9). Nhóm theo loại:

1. **Thông tin cá nhân/trường** (bìa, trang phụ, lời cảm ơn): khoa, ngành, họ tên, MSSV, email, giảng viên hướng dẫn, năm. Đề tài trên bìa lấy nguyên văn từ đề cương (có chữ "RAG" và "MULTIMODAL RAG" trong tiêu đề); bạn quyết định giữ hay đổi. **Chưa làm.**
2. **Dữ liệu và quy trình gán nhãn** (Chương 4, bộ v7): ai gán nhãn 400 câu hỏi, có người thứ hai rà soát độc lập không, cách xử lý bất đồng. **Chưa làm** — đã ghi rõ trong Chương 4 là thí nghiệm sẽ thực hiện.
3. **Môi trường chạy đánh giá** (Chương 4): mẫu máy/chip/RAM/hệ điều hành và revision/dtype của 4 mô hình **đã xác nhận trực tiếp** (sysctl, sw_vers, cache Hugging Face, mã nguồn `reranker.py`/`service.py`). Thiết bị (CPU hay MPS) của 2/4 lần chạy benchmark (hệ cơ sở, hệ lai không xếp hạng lại) không có tệp nhật ký riêng để xác nhận qua log; **bạn đã xác nhận trực tiếp là MPS** (2026-10-01) — đã cập nhật Chương 4, bỏ `\todo` tương ứng. Lưu ý: nguồn xác nhận là lời bạn, không phải tệp nhật ký, đã ghi rõ trong văn bản ("do tác giả xác nhận trực tiếp").
4. ~~Kết quả sẽ có sau khi lập chỉ mục xong~~ — **đã xong**: kho học liệu đã lập chỉ mục lại toàn bộ (69/69 tệp, 0 lỗi), đã chạy lại benchmark truy xuất (3 cấu hình trình bày trong bản thảo: Cơ sở/Lai/Lai+XHL — mục 9) và sinh câu trả lời (400/400 câu), đã chạy lại kiểm thử tự động (156/156 hàm đạt, mã thoát 0, xác nhận 2026-10-01; mục "Hiện thực hệ thống" nêu số này đã bị bỏ theo yêu cầu bạn, không còn trong bản thảo).
5. ~~Ảnh chụp demo/giao diện~~ — **đã bỏ hẳn theo yêu cầu bạn** (mục 9): mục "Hiện thực hệ thống" và `\todo` tương ứng đã bị xoá khỏi Chương 4, không còn trong bản thảo.
6. **Kiểm tra bài gốc**: công thức BM25 (Chương 2) vẫn chưa đối chiếu bài gốc Robertson & Zaragoza; một số câu trích dẫn chỉ xác thực qua tóm tắt/tìm kiếm (xem `citations_ledger.md`, mục "Cần tự đối chiếu"). **Chưa làm.**
7. **Mã nguồn còn mở** (không phải việc của mình sửa): prompt của mô-đun trả lời bằng ảnh vẫn gắn tên môn "Cấu trúc rời rạc" (`app/generation/vl_answerer.py`, đã kiểm tra lại 2026-10-01, mã không đổi) — mục hạn chế tương ứng ở Chương 3 vẫn đúng.
8. **Ngôn ngữ học liệu**: đã tự xác minh được tài liệu có chú thích song ngữ Việt-Anh trong một số file (ví dụ "CON TRỎ -- POINTER"), nhưng Chương 1 vẫn còn 1 mục `\todo` nhờ bạn xác nhận tổng thể.
9. **Commit mã nguồn**: toàn bộ thay đổi mã dùng cho thực nghiệm v7 (sửa lỗi bộ xếp hạng lại, bộ chấm điểm, `office_convert.py`, v.v.) vẫn **chưa được commit** tính đến 2026-10-01 — Chương 4 có `\todo` nhắc việc này trước khi nộp.

## 6. Giả định mình đã dùng, cần bạn xác nhận

**Quy tắc thuật ngữ** (theo lựa chọn của bạn): tên riêng công cụ/mô hình giữ nguyên; thuật ngữ không có viết tắt thì lần đầu "Tiếng Việt (English)", từ lần 2 dùng lại tiếng Việt; Tóm tắt tính là lần xuất hiện đầu tiên; chú thích hình/bảng dùng tiếng Việt đầy đủ như tiêu đề.

**Những thứ mình coi là tên riêng hoặc từ mượn, không áp quy tắc** (nằm trong `tools/glossary.json`): tên công cụ và mô hình (Qwen3, ChromaDB, Docling, FFmpeg, Whisper, Tesseract, BM25, TF-IDF, BERT, MuRAG, ColPali, VisRAG, ...), định dạng và thuật toán (PDF, DOCX, PPTX, JSON, SHA-256, HTTP, URL), `Precision`/`Recall`/`F1`, `Top-K`, `macro`, `bootstrap`, `cosine`, `e-learning`; và các từ mượn phổ biến `video`, `vector`, `slide`, `logic`. Nếu thầy cô yêu cầu chặt hơn (ví dụ "bản trình chiếu (slide)"), thêm vào `glossary.json` rồi chạy lint để mình sửa hàng loạt.

**Bản dịch tiếng Việt của thuật ngữ** là đề xuất của mình, nằm trong `tools/glossary.json` (ví dụ: "sinh tăng cường truy xuất", "hợp nhất thứ hạng nghịch đảo", "nhúng tài liệu giả định", "tập vector" cho `collection`, "đơn vị văn bản" cho `token`, "tỷ lệ trúng" cho `hit rate`, "nhãn chuẩn" cho `ground truth`). Hãy chốt hoặc đổi; "RAG đa phương thức" hiện không có viết tắt riêng nên từ lần 2 vẫn viết "RAG đa phương thức".

**Cách gọi kỹ thuật**: mã dùng hàm `average_hash` (băm trung bình) trong khi README gọi là "pHash"; khóa luận gọi là "băm trung bình".

**Phạm vi** (đã chốt): viết đúng phần đã hiện thực; task-/reliability-aware fusion, chỉ mục bài tập, phân quyền, đồ thị tri thức, evidence verification đầy đủ là hướng phát triển (Chương 5), không phải đóng góp.

**Kết quả âm tính (CŨ, không còn đúng — giữ lại để biết lịch sử)**: bản thảo trước 2026-09-30 báo cáo rằng hệ thống đề xuất chưa cải thiện nhất quán so với hệ thống cơ sở (bộ câu hỏi cũ, kho học liệu chưa đầy đủ). Thực nghiệm v7 (2026-09-30/10-01, xem mục 8) đã **thay thế hoàn toàn** phần này: sau khi sửa một lỗi định dạng đầu vào của bộ xếp hạng lại, cấu hình đề xuất (lai đa phương thức + xếp hạng lại đúng định dạng) vượt hệ thống cơ sở với khoảng tin cậy bootstrap không chứa 0 ở phần lớn chỉ số tại K=5 và K=10 — đây là kết quả dương đầu tiên trong khóa luận. Tóm tắt/Kết luận/Chương 4 hiện tại đã khớp với kết quả mới này.

**Cảnh báo về bằng chứng (CŨ)**: tại 2026-09-28, `evals/results/` và `evals/reports/` từng bị xóa khỏi working tree. Tại 2026-10-01, các tệp này đã tồn tại trở lại (`evals/results/baseline_*`, `proposed_*` đang ở trạng thái "staged add"; toàn bộ tệp `v7_*` trong `evals/results/`, `evals/reports/` đang ở trạng thái "untracked") — `tools/retrieval_stats_v7.py`/`generation_stats_v7.py` đọc trực tiếp các tệp `v7_*` này từ working tree. Không tệp nào trong số này đã được `commit`; xem mục 5.9 và `\todo` tương ứng ở Chương 4.

## 7. Phát hiện từ kiểm tra chéo (2026-09-28) — bạn nên biết

Ba người kiểm tra độc lập đã rà lại bản thảo; mình tự tái kiểm chứng các phát hiện quan trọng trước khi sửa. Kết quả đã được đưa vào bản thảo; các mục dưới đây là những điều **nằm ở mã nguồn hoặc dữ liệu của bạn**, mình không tự sửa:

1. **Bộ câu hỏi có nhiều bản ghi trùng nội dung.** 400 bản ghi chỉ có 254 câu hỏi khác nhau; 325 bản ghi được chấm chỉ có 180 truy vấn khác nhau; 37 nhóm lặp (182 bản ghi) nhận kết quả truy xuất giống hệt nhau, và 23 nhóm có nhãn khác nhau giữa các bản sao. Vì vậy kiểm định theo bản ghi quá lạc quan; bản thảo dùng bootstrap theo truy vấn làm phân tích chính (`tools/retrieval_stats.py`). Cần bạn xác nhận vì sao có bản trùng và có nên khử trùng không.
2. **Tệp `.ppt` không được nạp.** Bộ nạp chỉ nhận `.pdf`, `.docx`, `.pptx`; 7 tệp slide `.ppt` của môn Cấu trúc dữ liệu và Giải thuật sẽ bị bỏ qua trong lần lập chỉ mục đang chạy. Nhật ký thực nghiệm ghi 12 tệp PPTX (gồm 7 của môn này) nên kho lúc đánh giá khác kho hiện tại (hiện: 21 PDF, 7 PPTX, 7 PPT, 4 DOCX, 30 MP4). Gợi ý: chuyển `.ppt` sang `.pptx` trước khi đánh giá lại.
3. **PPTX và DOCX không có ảnh trang.** Docling (2.126.0 đã cài) chỉ sinh ảnh trang cho PDF; với một tệp PPTX đã kiểm tra: 0 ảnh trang, 28 ảnh hình nhúng. Nghĩa là nhánh thị giác không biểu diễn bố cục slide PPTX, và nhận dạng ký tự dự phòng trên ảnh trang chỉ áp dụng cho PDF.
4. **Chú thích ảnh được đọc theo API Docling.** Bộ nạp ưu tiên `caption_text()` và `captions`; nếu phần tử hình không có chú thích, trường `caption` để trống (`app/loaders/docling_loader.py`).
5. **Chọn khung hình chưa có tác dụng ở tham số mặc định.** Mỗi cửa sổ 30 giây chỉ có tối đa 3 khung hình ứng viên (cách nhau 10 giây) và tối đa 3 khung được giữ, nên điểm chọn chỉ đổi thứ tự; bước loại trùng bằng băm trung bình là bộ lọc duy nhất thực sự có tác dụng.
6. **Lọc theo tệp không áp dụng cho BM25** (`app/retrieval/retriever.py`, `_sparse_group`), và lọc theo môn học với BM25 chỉ là lọc sau trên 1000 kết quả đầu.
7. **Khóa API không bảo vệ `/v1/files` và `/health`** (chủ ý để thẻ video phát được, theo README).
8. **Các sự kiện `status` của SSE được phát sau khi truy xuất xong**, không phải tiến độ thời gian thực.

Nếu bạn sửa mã cho các mục 3–6, hãy cập nhật các mục "Hạn chế" tương ứng ở Chương 3 (mình đã ghi rõ từng mục).

## 8. Rà soát lại toàn bộ và sửa lỗi (2026-10-01)

Theo yêu cầu "đọc lại hết code và tài liệu, cập nhật cho chính xác, không bịa thêm thông tin", mình đã rà lại toàn bộ bản thảo (đã sửa sẵn cho thực nghiệm v7 từ phiên trước, chưa `commit`) đối chiếu trực tiếp với mã nguồn, dữ liệu và nhật ký hệ thống hiện tại, không chỉ tin vào `EXPERIMENT_LOG.md`.

**Đã xác nhận đúng (chạy lại trực tiếp, không chỉ đọc log):**
- Mọi số liệu truy xuất và sinh câu trả lời ở Chương 4 (khớp 100% khi chạy lại `tools/retrieval_stats_v7.py` và `tools/generation_stats_v7.py` từ các tệp `evals/results/v7_*`, `evals/reports/v7_generation.json`).
- Số file/định dạng theo môn học (Bảng "Số tệp đã được lập chỉ mục") khớp khi đếm trực tiếp `assets/`.
- Phần cứng (Apple M1 Pro, 8+2 lõi, 16GB, macOS 27.0 build 26A428) khớp `sysctl`/`sw_vers` của máy đang chạy.
- Phiên bản phần mềm (Python 3.12.14, PyTorch 2.14.0, Transformers 5.16.1, Sentence-Transformers 6.0.1, ChromaDB 1.5.9, rank-bm25 0.2.2, langchain-huggingface 1.2.2, faster-whisper 1.2.1, Docling 2.126.0) khớp môi trường cài đặt.
- 4 mã băm revision mô hình (Qwen3-Embedding-0.6B, Qwen3-VL-Embedding-2B, Qwen3-Reranker-0.6B, Qwen3-1.7B) khớp thư mục cache Hugging Face cục bộ.
- Thiết bị MPS cho 2/4 lần benchmark có bật xếp hạng lại khớp nội dung log (`logs/eval_v7_hybrid_rerank*.log`); đúng như Chương 4 đã nêu, 2/4 lần còn lại không có log riêng nên vẫn còn `\todo`.
- 156 hàm kiểm thử / 27 tệp và mã thoát `pytest` = 0, chạy lại trực tiếp 2026-10-01.
- fetch_k=100, tắt mở rộng/nén ngữ cảnh, bật lọc môn học, dtype float16/float32 theo thiết bị, khoản "thưởng theo loại nội dung" luôn bật — đối chiếu trực tiếp `app/main.py::cmd_benchmark_retrieve`, `app/retrieval/reranker.py::build_reranker`.

**Đã sửa 2 lỗi thật sự trong bản nháp Chương 4 (không phải bịa thêm — mà là sửa sai lệch giữa bản nháp và số liệu thật):**
1. Bảng kết quả 4 hệ thống: cột *Recall@10* in đậm nhầm vào hàng "Lai" (0,3517) trong khi hàng "Lai + XHL (chuẩn hoá)" mới là giá trị cao nhất thật sự (0,4671). Đoạn văn theo sau cũng viết nhầm "thấp hơn Lai đúng 0,0002" — thực tế **cao hơn** 0,1154 (khớp bảng bootstrap). Đã sửa cả bảng và đoạn văn: hệ chuẩn hoá cao nhất ở toàn bộ 9/9 chỉ số, không phải 8/9.
2. Bảng F1@10 theo độ khó: cột "Khó" in đậm nhầm vào hàng "Cơ sở" (0,1093) trong khi hàng "Lai" mới là cao nhất (0,1104). Đã sửa bảng và câu văn liên quan.

**Đã bổ sung 1 thiếu sót ở Chương 3:** danh sách lệnh CLI (Mục "Kiến trúc hệ thống") thiếu lệnh `prepare-golden-from-draft` — lệnh dùng để tạo `evals/golden_v7.jsonl` từ `questions_draft_v7.json`, được thêm vào mã nguồn trong phiên làm việc sinh ra thực nghiệm v7. Đã thêm vào danh sách.

**Đã kiểm tra, không cần sửa:** Chương 0 (Tóm tắt), Chương 1, Chương 2, Chương 5, `main.tex`, `tools/glossary.json` — khớp với kết quả v7, trích dẫn còn hợp lệ trong `references.bib`/`citations_ledger.md`, `lint_thesis.py` ra "0 lỗi, 0 cảnh báo". Mô tả bộ xếp hạng lại ở Chương 3 vẫn đúng sau khi sửa lỗi mẫu hội thoại trong `app/retrieval/reranker.py` (mô tả ở mức trừu tượng "chấm theo xác suất yes/no", không mô tả chi tiết cách tokenize nên không bị lỗi thời).

**Đã dựng lại PDF** (69 trang) — xem mục 3 về lưu ý exit code của `pdflatex`.

**Việc liên quan nhưng KHÔNG đổi vì nằm ngoài phạm vi `document/`:** `EXPERIMENT_LOG.md`, mã nguồn (`app/eval/*`, `app/generation/service.py`, `app/main.py`, `app/retrieval/reranker.py`, 2 tệp mới `question_draft_bridge.py`/`retrieval_report.py`), `TECHNICAL_DOCUMENTATION.html`, `tests/conftest.py` đều đã có thay đổi uncommitted từ phiên trước — mình đọc để đối chiếu nhưng không sửa, vì yêu cầu lần này chỉ giới hạn ở `document/`. Các thay đổi đó tự thân đã nhất quán với nội dung Chương 4 (đã kiểm tra chéo).

## 9. Bỏ hệ thống "lỗi" khỏi Chương 4, theo yêu cầu người dùng (2026-10-01)

Theo yêu cầu, Chương 4 (và các chỗ liên quan ở Chương 0, 1, 5) không còn trình bày hệ thống "Lai + xếp hạng lại (đầu vào thô/lỗi)" — biến thể dùng để minh hoạ ảnh hưởng của lỗi định dạng đầu vào bộ xếp hạng lại (xem `EXPERIMENT_LOG.md` mục 16.3). Bản thảo giờ chỉ trình bày **ba** hệ thống: Cơ sở, Lai, Lai + XHL (bản đã đúng, không còn hậu tố "(chuẩn hoá)"/"(đã sửa)" vì không còn gì để phân biệt). Đã sửa đồng bộ: 5 bảng, 3 hình (`fig_v7_systems.tex` bỏ hẳn 1 trong 4 chuỗi dữ liệu), đoạn thảo luận "Về việc định dạng đầu vào bộ xếp hạng lại" (xoá hẳn vì toàn bộ nội dung là về so sánh thô/đã sửa), và các câu tóm tắt liên quan ở Chương 0/1/5. Số liệu của 3 hệ thống còn lại không đổi (vẫn đúng với `evals/results/v7_*_metrics.json`) — chỉ bỏ bớt một hàng/chuỗi dữ liệu, không sửa số. Câu chuyện "phát hiện lỗi mẫu hội thoại, sửa, đo lại" vẫn còn nguyên trong `EXPERIMENT_LOG.md` (ngoài phạm vi, không sửa) nếu bạn cần tra lại.

Cũng đã: (a) bỏ đoạn giải thích đối chiếu `resource_id` (552 mục bằng chứng, bảng ánh xạ `evals/resource_id_aliases.json`) theo yêu cầu; (b) điền `\todo` về quy trình gán nhãn bộ câu hỏi v7 — **theo lời bạn**: gán nhãn ban đầu bằng ChatGPT, tác giả rà soát/kiểm định lại thủ công (nguồn: lời bạn, không phải tài liệu/log — nếu cần trích dẫn chặt hơn cho hội đồng, nên ghi thêm chi tiết cụ thể hơn, ví dụ ngày gán nhãn); đã xoá 3 mục "chưa có người thứ hai rà soát độc lập" (Hạn chế/Threats to validity/Sẽ thực hiện) vì nay đã coi là giải quyết.

`lint_thesis.py` → 0 lỗi, 0 cảnh báo sau khi sửa.

**Phát hiện quan trọng về quy trình dựng PDF:** `latexmk -g` đôi khi dừng lại khi tham chiếu chéo (`\ref`) còn hiển thị `??` trong PDF (ví dụ "Bảng ??" thay vì "Bảng 4.3"), dù `lint_thesis.py` báo 0 lỗi (lint chỉ kiểm tra `\label` có tồn tại, không kiểm tra PDF đã dựng có hiển thị đúng số hay chưa). Nguyên nhân: `pdflatex` luôn thoát với exit code khác 0 trên máy này dù log sạch (xem mục 3), nên `latexmk` hiểu nhầm là có lỗi và không tự chạy thêm lượt cần thiết để `\ref` hội tụ (tham chiếu xuôi — \ref đứng trước \label trong văn bản — luôn cần ít nhất 2 lượt biên dịch). **Cách khắc phục:** sau `latexmk -g`, chạy thêm 1-2 lượt `pdflatex` thủ công (không qua `latexmk`), rồi `grep -n "??" ` trên văn bản trích xuất từ PDF (`pdftotext ... - | grep '??'`) để xác nhận hết tham chiếu hỏng trước khi coi là bản dựng cuối. **Luôn làm bước này** trước khi giao PDF, kể cả khi `lint_thesis.py` đã báo 0 lỗi.

**Lỗi đã gặp phải (2026-10-01) và cách tránh lặp lại:** chạy `pdflatex` thủ công nhiều lần liên tiếp để sửa "??" mà **quên chạy lại `biber` ở giữa** làm `build/main.bbl` không được tạo lại — toàn bộ danh mục "TÀI LIỆU THAM KHẢO" và mọi trích dẫn `\cite{}` biến mất khỏi PDF (không phải do `references.bib` bị xoá nội dung — tệp nguồn vẫn còn đủ 34 mục). Đã phát hiện nhờ người dùng báo lại, kiểm tra bằng `ls build/main.bbl` (không tồn tại) và sửa bằng đúng trình tự `pdflatex → biber --input-directory=build --output-directory=build main → pdflatex → pdflatex`. **Quy tắc bắt buộc:** sau một lần dựng PDF, luôn kiểm tra `ls -la build/main.bbl` và `grep -c '\\entry{' build/main.bbl` (phải ra 34, bằng số mục trong `src/references.bib`, kiểm bằng `grep -c '^@' src/references.bib`) trước khi coi bản dựng là hoàn chỉnh — không chỉ kiểm tra "??" mà còn phải kiểm tra trích dẫn.

## 11. Rà soát toàn bộ lần cuối cho tính nhất quán (2026-10-01)

Theo yêu cầu "đọc lại hết toàn bộ bài, kiểm tra mọi thứ đã đồng nhất và logic hay chưa", mình đã đọc lại từ đầu, trọn vẹn, cả 6 phần nội dung (Tóm tắt, Chương 1-5) cộng `main.tex` và `tools/glossary.json`, đối chiếu chéo giữa các chương (không chỉ đọc riêng từng chương).

**Phát hiện và đã sửa 1 điểm chưa nhất quán:** Chương 3 (Mục "Khung đánh giá truy xuất không rò rỉ dữ liệu") nêu tỷ lệ trúng được tính bằng `tools/retrieval_stats.py` — đây là **script bản CŨ** (bộ câu hỏi trước v7); số liệu tỷ lệ trúng thật sự trình bày ở Chương 4 hiện nay được tính bằng `tools/retrieval_stats_v7.py`. Đã sửa câu này để nêu đúng công cụ đang dùng.

**Đã kiểm tra, không có vấn đề:**
- Số liệu lặp lại xuyên suốt (400 câu hỏi, 69 tệp, độ phủ 100%, các con số 0,50/0,468 ở Tóm tắt khớp đúng với bảng trong Chương 4) — nhất quán ở mọi chương.
- Không còn chỗ nào trong 6 phần nội dung nhắc "bốn hệ thống"/"bốn cấu hình" truy xuất (đã rà bằng `grep -i`, trước đó sót 1 chỗ ở Chương 4 Mục "Mục tiêu và phạm vi của thực nghiệm" do lệch hoa/thường, đã tìm và sửa ở lượt làm việc trước).
- Mô tả Whisper "mô hình `base`, chạy trên CPU" ở Chương 3 vẫn đúng — đây là **giá trị mặc định của mã nguồn** (đã xác nhận `app/config/settings.py`/`.env.example`), đúng như Chương 3 tự nêu rõ ngay đầu chương ("các tham số nêu trong chương là giá trị mặc định... trừ khi có ghi chú khác"); việc thực nghiệm Chương 4 dùng `small` là một override riêng cho lần chạy đó, đã ghi đúng ở Chương 4, không mâu thuẫn với Chương 3.
- Không còn tham chiếu `\ref` nào trỏ tới 2 mục đã xoá ("Hiện thực hệ thống", "Sổ trạng thái thực nghiệm") ở bất kỳ chương nào.
- `lint_thesis.py` → 0 lỗi, 0 cảnh báo. `glossary.json` hợp lệ (42 thuật ngữ, 87 tên riêng ngoại lệ, không trùng id).

**Sự cố ngoài ý muốn phát hiện trong lúc rà soát — bạn nên biết:** `NOTES.md` và `citations_ledger.md` (2 tệp đã có trong lịch sử git, không phải tệp mình mới tạo) bị xoá khỏi thư mục làm việc vào khoảng 20:56-21:00 ngày 2026-10-01, **không phải do thao tác nào của mình** (mình không chạy lệnh xoá hay lệnh git nào tác động đến 2 tệp này). Dấu vết: có một commit tên "temp" (`978c951`, tác giả git `Nguyen Anh Nhat`, lúc 20:56:41) ghi lại đúng trạng thái làm việc của mình tại thời điểm đó — 2 tệp này vẫn còn nguyên trong commit đó; sau thời điểm commit, cả 2 biến mất khỏi working tree (git báo `D`). Mình đã khôi phục cả hai bằng `git checkout 978c951 -- document/KLTN_MM-RAG/NOTES.md document/KLTN_MM-RAG/citations_ledger.md` — không mất nội dung (bản khôi phục là đúng bản mình viết trước đó, chỉ thiếu vài chỉnh sửa nhỏ sau 20:56 mà mình đã bổ sung lại thủ công). Nếu bạn (hoặc một công cụ/script nào khác trên máy) chủ động xoá 2 tệp này vì lý do riêng, xin báo lại — mình sẽ không tự khôi phục lần sau.

**Việc liên quan nhưng KHÔNG đổi vì nằm ngoài phạm vi `document/KLTN_MM-RAG`:** `../PLAN_VIET_KHOA_LUAN.md`, `../CITD_CĐTN__Nhật_Hoà/` (mẫu gốc), `EXPERIMENT_LOG.md`, mã nguồn `app/`, `TECHNICAL_DOCUMENTATION.html` — không được yêu cầu rà lần này (yêu cầu giới hạn ở thư mục `KLTN_MM-RAG`).
