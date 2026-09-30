# Ghi chú bản thảo khóa luận (cập nhật 2026-09-28)

Thư mục này là bản thảo LaTeX theo mẫu `../CITD_CĐTN__Nhật_Hoà/` (mẫu được giữ nguyên, không sửa). Kế hoạch tổng thể nằm ở `../PLAN_VIET_KHOA_LUAN.md`.

## 1. Trạng thái

| Phần | Trạng thái | Ghi chú |
|---|---|---|
| Tóm tắt | Đã viết | Có nêu kết quả âm tính; cập nhật khi có kết quả mới |
| Chương 1. Tổng quan | Đã viết | 1.2 chỉ dùng nguồn đã xác thực; còn 1 mục cần bạn xác nhận (ngôn ngữ học liệu) |
| Chương 2. Cơ sở lý thuyết | Đã viết | Công thức BM25 cần đối chiếu bài gốc (1 mục `\todo`) |
| Chương 3. Phương pháp | Đã viết, bám mã nguồn | Đã kiểm tra chéo với mã; mục hạn chế có 1 `\todo` về prompt gắn tên môn |
| Chương 4. Thực nghiệm | Đã viết với số liệu đã có | Nhiều `\todo` về dữ liệu/phần cứng/ảnh chụp; sổ trạng thái đang/đã/sẽ; đã sửa theo kiểm tra chéo (xem mục 7) |
| Chương 5. Kết luận | Đã viết | Hướng phát triển đều có trích dẫn |
| Bìa, lời cảm ơn | **Chưa** (chỗ trống `\todo`) | Chỉ bạn điền được |
| Hội đồng | Giữ nguyên mẫu | |
| Danh mục viết tắt, từ tạm dịch | Sinh tự động | `python3 tools/lint_thesis.py --build-lists` |
| Hình | 3 hình TikZ đã vẽ | Kiến trúc, luồng video, luồng truy xuất; ảnh chụp demo là việc của bạn |
| Bản dịch PDF | **Đã dựng** (`KLTN_MM-RAG_ban_thao.pdf`, 64 trang, 0 lỗi, 0 tham chiếu/trích dẫn hụt) | Xem mục 3 |

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
  tools/retrieval_stats.py                       # tính lại mọi số liệu thống kê của Chương 4
  citations_ledger.md                            # sổ xác thực trích dẫn
  NOTES.md                                       # tệp này
```

## 3. Biên dịch

- **Dựng PDF:** `./tools/build_pdf.sh` (chạy trong thư mục này hoặc từ bất kỳ đâu). Script đặt `PATH`, `TEXINPUTS`, `BIBINPUTS`, chạy `latexmk -pdf` (pdflatex + biber) với thư mục trung gian `build/`, rồi chép kết quả thành `KLTN_MM-RAG_ban_thao.pdf`. Sau một lần lỗi, `latexmk` có thể từ chối chạy lại: thêm `-g` (`./tools/build_pdf.sh -g`).
- Kết quả lần dựng 2026-09-28: 64 trang, không có lỗi LaTeX, không có tham chiếu/trích dẫn chưa giải quyết (không còn `??`), biber không cảnh báo. Còn lại chỉ vài cảnh báo nhẹ: `Underfull \hbox` (dòng thưa, không ảnh hưởng nội dung), thiếu kiểu chữ in đậm đơn cách và chữ hoa nhỏ của phông (LaTeX tự thay), và cảnh báo trùng đích siêu liên kết `table.0.1` do môi trường bảng của mẫu (bỏ qua được). 27 chỗ `[TODO: ...]` màu đỏ trong PDF là các việc của bạn (mục 5).
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

Chạy `--todos` để có danh sách đầy đủ và số dòng. Nhóm theo loại:

1. **Thông tin cá nhân/trường** (bìa, trang phụ, lời cảm ơn): khoa, ngành, họ tên, MSSV, email, giảng viên hướng dẫn, năm. Đề tài trên bìa lấy nguyên văn từ đề cương (có chữ "RAG" và "MULTIMODAL RAG" trong tiêu đề); bạn quyết định giữ hay đổi.
2. **Dữ liệu và quy trình gán nhãn** (Chương 4): ai gán nhãn câu hỏi, có người thứ hai rà soát không, cách xử lý bất đồng; trường phân nhóm câu hỏi (nếu khôi phục được); tệp `questions_draft.json` (nằm ngoài repo).
3. **Môi trường chạy đánh giá** (Chương 4): mẫu máy, chip, RAM, hệ điều hành; revision và dtype của hai mô hình biểu diễn; xác nhận mã tại commit `7f1df63` là mã đã chạy đánh giá (lần chạy 26/09/2026, commit 27/09/2026).
4. **Kết quả sẽ có sau khi lập chỉ mục xong**: cập nhật số tệp/vector, chốt bản sao ChromaDB và BM25, chạy lại kiểm thử tự động; chạy lại benchmark nếu bạn chọn.
5. **Ảnh chụp demo/giao diện** (Chương 4).
6. **Kiểm tra bài gốc**: công thức BM25 (Chương 2); một số câu trích dẫn chỉ xác thực qua tóm tắt/tìm kiếm (xem `citations_ledger.md`, mục "Cần tự đối chiếu").
7. **Mã nguồn**: prompt của mô-đun trả lời bằng ảnh đang gắn tên môn "Cấu trúc rời rạc" (`app/generation/vl_answerer.py`). Mình không sửa mã của bạn; nếu bạn sửa hãy xóa mục hạn chế tương ứng ở Chương 3.
8. **Ngôn ngữ học liệu**: toàn tiếng Việt hay có tiếng Anh (Chương 1).

## 6. Giả định mình đã dùng, cần bạn xác nhận

**Quy tắc thuật ngữ** (theo lựa chọn của bạn): tên riêng công cụ/mô hình giữ nguyên; thuật ngữ không có viết tắt thì lần đầu "Tiếng Việt (English)", từ lần 2 dùng lại tiếng Việt; Tóm tắt tính là lần xuất hiện đầu tiên; chú thích hình/bảng dùng tiếng Việt đầy đủ như tiêu đề.

**Những thứ mình coi là tên riêng hoặc từ mượn, không áp quy tắc** (nằm trong `tools/glossary.json`): tên công cụ và mô hình (Qwen3, ChromaDB, Docling, FFmpeg, Whisper, Tesseract, BM25, TF-IDF, BERT, MuRAG, ColPali, VisRAG, ...), định dạng và thuật toán (PDF, DOCX, PPTX, JSON, SHA-256, HTTP, URL), `Precision`/`Recall`/`F1`, `Top-K`, `macro`, `bootstrap`, `cosine`, `e-learning`; và các từ mượn phổ biến `video`, `vector`, `slide`, `logic`. Nếu thầy cô yêu cầu chặt hơn (ví dụ "bản trình chiếu (slide)"), thêm vào `glossary.json` rồi chạy lint để mình sửa hàng loạt.

**Bản dịch tiếng Việt của thuật ngữ** là đề xuất của mình, nằm trong `tools/glossary.json` (ví dụ: "sinh tăng cường truy xuất", "hợp nhất thứ hạng nghịch đảo", "nhúng tài liệu giả định", "tập vector" cho `collection`, "đơn vị văn bản" cho `token`, "tỷ lệ trúng" cho `hit rate`, "nhãn chuẩn" cho `ground truth`). Hãy chốt hoặc đổi; "RAG đa phương thức" hiện không có viết tắt riêng nên từ lần 2 vẫn viết "RAG đa phương thức".

**Cách gọi kỹ thuật**: mã dùng hàm `average_hash` (băm trung bình) trong khi README gọi là "pHash"; khóa luận gọi là "băm trung bình".

**Phạm vi** (đã chốt): viết đúng phần đã hiện thực; task-/reliability-aware fusion, chỉ mục bài tập, phân quyền, đồ thị tri thức, evidence verification đầy đủ là hướng phát triển (Chương 5), không phải đóng góp.

**Kết quả âm tính**: bản thảo báo cáo trung thực rằng hệ thống đề xuất chưa cải thiện nhất quán so với hệ thống cơ sở. Phân tích chính (bootstrap theo truy vấn, vì bộ câu hỏi có nhiều bản ghi trùng nội dung) cho thấy mọi khoảng tin cậy đều chứa 0; ở K=5 chỉ có xu hướng thấp hơn. Nếu bạn có thêm kết quả (kho đầy đủ, thí nghiệm loại trừ), cập nhật Chương 4, Tóm tắt và Kết luận cho khớp.

**Cảnh báo về bằng chứng**: `evals/results/` và `evals/reports/` đang bị xóa trong working tree nhưng còn trong git `HEAD`, và `tools/retrieval_stats.py` đọc chúng từ đó. Đừng commit việc xóa; nếu muốn dọn hãy lưu bản sao ra ngoài trước.

## 7. Phát hiện từ kiểm tra chéo (2026-09-28) — bạn nên biết

Ba người kiểm tra độc lập đã rà lại bản thảo; mình tự tái kiểm chứng các phát hiện quan trọng trước khi sửa. Kết quả đã được đưa vào bản thảo; các mục dưới đây là những điều **nằm ở mã nguồn hoặc dữ liệu của bạn**, mình không tự sửa:

1. **Bộ câu hỏi có nhiều bản ghi trùng nội dung.** 400 bản ghi chỉ có 254 câu hỏi khác nhau; 325 bản ghi được chấm chỉ có 180 truy vấn khác nhau; 37 nhóm lặp (182 bản ghi) nhận kết quả truy xuất giống hệt nhau, và 23 nhóm có nhãn khác nhau giữa các bản sao. Vì vậy kiểm định theo bản ghi quá lạc quan; bản thảo dùng bootstrap theo truy vấn làm phân tích chính (`tools/retrieval_stats.py`). Cần bạn xác nhận vì sao có bản trùng và có nên khử trùng không.
2. **Tệp `.ppt` không được nạp.** Bộ nạp chỉ nhận `.pdf`, `.docx`, `.pptx`; 7 tệp slide `.ppt` của môn Cấu trúc dữ liệu và Giải thuật sẽ bị bỏ qua trong lần lập chỉ mục đang chạy. Nhật ký thực nghiệm ghi 12 tệp PPTX (gồm 7 của môn này) nên kho lúc đánh giá khác kho hiện tại (hiện: 21 PDF, 7 PPTX, 7 PPT, 4 DOCX, 30 MP4). Gợi ý: chuyển `.ppt` sang `.pptx` trước khi đánh giá lại.
3. **PPTX và DOCX không có ảnh trang.** Docling (2.126.0 đã cài) chỉ sinh ảnh trang cho PDF; với một tệp PPTX đã kiểm tra: 0 ảnh trang, 28 ảnh hình nhúng. Nghĩa là nhánh thị giác không biểu diễn bố cục slide PPTX, và nhận dạng ký tự dự phòng trên ảnh trang chỉ áp dụng cho PDF.
4. **Chú thích ảnh không được ghi.** Mã đọc `picture.caption` nhưng Docling cung cấp `captions`/`caption_text()`, nên trường `caption` luôn trống với ảnh của tài liệu (`app/loaders/docling_loader.py`).
5. **Chọn khung hình chưa có tác dụng ở tham số mặc định.** Mỗi cửa sổ 30 giây chỉ có tối đa 3 khung hình ứng viên (cách nhau 10 giây) và tối đa 3 khung được giữ, nên điểm chọn chỉ đổi thứ tự; bước loại trùng bằng băm trung bình là bộ lọc duy nhất thực sự có tác dụng.
6. **Lọc theo tệp không áp dụng cho BM25** (`app/retrieval/retriever.py`, `_sparse_group`), và lọc theo môn học với BM25 chỉ là lọc sau trên 1000 kết quả đầu.
7. **Khóa API không bảo vệ `/v1/files` và `/health`** (chủ ý để thẻ video phát được, theo README).
8. **Các sự kiện `status` của SSE được phát sau khi truy xuất xong**, không phải tiến độ thời gian thực.

Nếu bạn sửa mã cho các mục 3–6, hãy cập nhật các mục "Hạn chế" tương ứng ở Chương 3 (mình đã ghi rõ từng mục).
