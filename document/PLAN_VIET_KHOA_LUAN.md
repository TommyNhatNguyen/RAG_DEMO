# Kế hoạch viết khóa luận (bản chốt 2026-09-28)

> **Cập nhật cuối ngày 2026-09-28:** đã bắt đầu viết, xem `KLTN_MM-RAG/NOTES.md` để biết trạng thái mới nhất. Riêng phần kiểm định thống kê ở §1b và §4 dưới đây (khoảng tin cậy theo bản ghi, K=5 thấp hơn có ý nghĩa) **đã bị thay thế**: bộ câu hỏi có nhiều bản ghi trùng nội dung nên phân tích chính là bootstrap theo truy vấn, trong đó mọi khoảng tin cậy đều chứa 0.

Đề tài: *Nghiên cứu và phát triển trợ lý ảo thông minh tích hợp RAG đa phương thức cho hệ thống e-learning với các nguồn học liệu đa định dạng*.
Mẫu: `document/CITD_CĐTN__Nhật_Hoà/` (LaTeX, `thesis.cls`, biber numeric, 5 chương, danh mục viết tắt + danh mục từ tạm dịch, văn phong "chúng tôi").

## 0. Quyết định đã chốt

| Vấn đề | Quyết định |
|---|---|
| Phạm vi | **Viết đúng phần đã làm.** Task-/reliability-aware fusion (C3), exercise index + phân quyền, đồ thị tri thức, evidence verification đầy đủ được trình bày là hướng phát triển, không phải đóng góp. |
| Thực nghiệm | **Ghi hết những gì đang / đã / sẽ có** (sổ trạng thái ở §4). Chỉ mục "đã có" mới được trình bày kèm số liệu; mục "đang" và "sẽ" ghi rõ là chưa có kết quả. |
| Thuật ngữ | Theo 3 mặc định: (1) tên riêng công cụ/mô hình (Qwen3, ChromaDB, Docling, FFmpeg, Whisper, BM25) giữ nguyên, không áp dụng quy tắc; (2) thuật ngữ không có viết tắt (vd. embedding): lần đầu "Tiếng Việt (English)", từ lần 2 dùng lại tiếng Việt; (3) Tóm tắt tính là lần xuất hiện đầu tiên; chú thích hình/bảng dùng tiếng Việt đầy đủ như tiêu đề. |

Quy tắc gốc của bạn: (1) lần đầu "Tiếng Việt đầy đủ (English full - VIẾT TẮT)", từ lần 2 chỉ viết tắt, riêng tiêu đề chương/mục/tiểu mục chỉ dùng tiếng Việt đầy đủ; (2) mọi nhận định về bài toán/định hướng phải có trích dẫn; (3) thông tin bịa = 0 điểm.

## 1. Quy trình chống bịa

### 1.1 Sổ khẳng định
Mỗi câu trong bản thảo mang một nhãn nguồn (viết dưới dạng chú thích LaTeX `% [..]`, xóa khi in). Câu không có nhãn thì không đưa vào.

- `[CODE file:hàm]` — sự kiện về hệ thống, đọc trực tiếp từ mã.
- `[LOG mục]` — số liệu/sự kiện từ `EXPERIMENT_LOG.md`, đã đối chiếu file gốc.
- `[CITE key]` — nhận định có trích dẫn đã xác thực.
- `[TODO-bạn]` — thiếu dữ kiện, chờ bạn bổ sung.

### 1.2 Sổ trích dẫn
Chỉ thêm vào `references.bib` sau khi làm đủ 4 bước:
1. Mở nguồn gốc (arXiv, ACL Anthology, DOI, IEEE Xplore, trang chính thức).
2. Đối chiếu tác giả, năm, nơi công bố với nguồn gốc (không sao chép từ trí nhớ hay từ file khác).
3. Tìm đúng đoạn nguồn hỗ trợ ý được trích; ghi lại vào sổ.
4. Ghi `ngày xác thực` và URL vào `citations_ledger.md`.

**Danh sách khởi đầu (từ đề cương §23) — CHƯA xác thực:**
Lewis et al. (RAG, NeurIPS 2020); Chen et al. (MuRAG, EMNLP 2022); Abootorabi et al. (Ask in Any Modality, Findings of ACL 2025); Faysse et al. (ColPali, 2024); Yu et al. (VisRAG, ICLR 2025); Huang et al. (LayoutLMv3, ACM MM 2022); Es et al. (RAGAs, EACL 2024); IEEE 1484.12.1 (LOM); Tanaka et al. (VDocRAG, 2025); Gao et al. (Scaling Beyond Context, 2025).

**Cần tìm và xác thực thêm (ứng viên theo những gì mã dùng; chỉ dùng tên để tìm, không sao chép thông tin thư mục từ đây):**
Whisper; Qwen3 / Qwen3 Embedding / Qwen3-VL; BM25 (Robertson & Zaragoza); Reciprocal Rank Fusion (Cormack et al.); HNSW (Malkov & Yashunin); Docling; HyDE (Gao et al.); cross-encoder reranking; Tesseract.
**Chưa có nguồn nào** cho: RAG/trợ lý ảo trong giáo dục, hỏi đáp/truy xuất trên video bài giảng, và mọi nhận định "khoảng trống nghiên cứu". Nếu không tìm được nguồn, câu đó viết thành phạm vi của đề tài chứ không viết thành khẳng định.

### 1.3 Số liệu
Chỉ lấy từ file kết quả gốc và tính lại bằng script; script được lưu vào repo. Không sao chép số từ bản tóm tắt.

### 1.4 Kiểm tra thuật ngữ tự động
`glossary.yaml` (tiếng Việt | English đầy đủ | viết tắt | vị trí dùng đầu tiên) + `lint_glossary.py` bắt 5 lỗi:
1. lần đầu không đúng dạng "Tiếng Việt (English - VIẾT TẮT)";
2. lặp lại dạng đầy đủ ở các lần sau;
3. dùng viết tắt/English trước khi được định nghĩa;
4. tiêu đề chương/mục/tiểu mục hoặc chú thích hình/bảng chứa viết tắt/English;
5. thuật ngữ trong glossary nhưng chưa từng được dùng (dọn danh mục viết tắt).

Ví dụ thuật ngữ khởi đầu (**bản dịch tiếng Việt chỉ là đề xuất, cần bạn chốt**):

| Tiếng Việt (đề xuất) | English | Viết tắt |
|---|---|---|
| Sinh tăng cường truy xuất | Retrieval-augmented generation | RAG |
| Mô hình ngôn ngữ lớn | Large language model | LLM |
| Mô hình ngôn ngữ thị giác | Vision-language model | VLM |
| Nhận dạng giọng nói tự động | Automatic speech recognition | ASR |
| Nhận dạng ký tự quang học | Optical character recognition | OCR |
| Hợp nhất thứ hạng nghịch đảo | Reciprocal rank fusion | RRF |
| Hệ thống quản lý học tập | Learning management system | LMS |
| Siêu dữ liệu đối tượng học tập | Learning object metadata | LOM |
| Giao diện lập trình ứng dụng | Application programming interface | API |
| RAG đa phương thức | Multimodal RAG | *(chưa có viết tắt chuẩn — cần bạn chốt)* |
| Biểu diễn vector | Embedding | — |
| Phân đoạn văn bản | Chunking | — |

## 2. Bảng truy vết: đề cương ↔ hiện thực ↔ cách viết

| Đề cương | Trạng thái trong `app/` | Cách viết trong khóa luận |
|---|---|---|
| Kho tri thức đa nguồn (video, slide, PDF, ảnh, bảng) | **Có**: `loaders/docling_loader.py`, `image_loader.py`, `video_loader.py`, `pipeline/indexing.py` | Đóng góp chính (Chương 3) |
| Ghép ASR + OCR + khung hình | **Có**: Whisper hoặc sidecar `<video>_segments.json`, Tesseract, chọn khung hình (`processors/frame_selection.py`) | Chương 3 |
| Biểu diễn đối tượng tri thức thống nhất (C1) | **Một phần**: `base_metadata` có `document_id`, `relative_path`, `file_type`, `content_type`, `chunk_index`, `page_number`, `section`, `start_time`, `end_time`, `timestamp`, `course`. Thiếu module, learning outcome, khái niệm, độ khó, quyền truy cập, độ tin cậy | Mô tả lược đồ thực tế; nêu phần thiếu ở Chương 5 |
| Truy xuất phân cấp course-aware (C2) | **Một phần**: lọc `course`/`content_type` (Chroma `where` hoặc lọc sau), dense + BM25 + visual → RRF → type-prior → đa dạng theo file → mở rộng ngữ cảnh → nén trích xuất | Trình bày là "truy xuất lai đa phương thức có lọc course", không gọi là truy xuất phân cấp ba tầng |
| Task-aware routing + reliability-aware fusion (C3) | **Chưa có.** RRF không trọng số; chỉ có regex `is_lecture_query` (thưởng điểm nhỏ cho video) và `is_catalog_query` | Hướng phát triển (Chương 5) |
| Đồ thị tri thức nhẹ, liên kết video↔slide↔PDF | **Chưa có** | Hướng phát triển |
| Chỉ mục bài tập, kiểm soát lộ đáp án theo mức (RQ5) | **Chưa có** (bài tập DOCX chỉ là văn bản thường; đề cương ghi "nếu được sẽ làm cho ĐATN") | Hướng phát triển |
| Evidence verification | **Rất hạn chế**: ngưỡng cosine 0,15 để từ chối; vòng reflect tùy chọn (`max_retrieve_loops`, tối đa 1, mặc định 0) | Mô tả đúng là "cơ chế từ chối theo ngưỡng" |
| Sinh câu trả lời có căn cứ, có trích dẫn | **Có**: `generation/prompts.py`, `api/citations.py` (`Citation`, `Locator`, `#t=` cho video, `#page=` cho PDF), Qwen3-VL đọc ảnh trang | Đóng góp chính |
| Đánh giá truy xuất | **Có**: `eval/retrieval_benchmark.py` (P/R/F1@{1,5,10}, tách câu không trả lời được, truy vấn chỉ có 3 trường để tránh rò rỉ) | Chương 4 |
| Đánh giá câu trả lời/grounding | Mã có (`eval/ragas_backend.py`, `judge.py`), **chưa có kết quả** | Ghi ở sổ trạng thái |
| Baseline B0–B8 | Chỉ 2 hệ thống. Baseline đã có lọc course ⇒ gần nhất với B3; proposed ≈ B4/B5 *(suy luận của mình từ mã, cần bạn xác nhận)* | Nêu rõ tương ứng gần đúng |

## 3. Dàn ý chi tiết

Tiêu đề chỉ dùng tiếng Việt đầy đủ. Mỗi mục ghi nguồn sự thật; mọi nhận định về bài toán/định hướng đều cần `\cite`.

### Đầu sách
Bìa, trang phụ, hội đồng, lời cảm ơn: `[TODO-bạn]`. Tóm tắt: viết sau cùng. Danh mục viết tắt và danh mục từ tạm dịch: sinh từ `glossary.yaml`.

### Chương 1. Tổng quan đề tài
- 1.1 Lý do chọn đề tài — học liệu phân tán (video/slide/PDF), tìm từ khóa dễ thất bại khi diễn đạt khác; nguồn: đề cương §3 + trích dẫn.
- 1.2 Các nghiên cứu liên quan
  - 1.2.1 Sinh tăng cường truy xuất và mở rộng đa phương thức
  - 1.2.2 Truy xuất tài liệu giàu thị giác
  - 1.2.3 Hỏi đáp và truy xuất trên video bài giảng *(chưa có nguồn — cần tìm)*
  - 1.2.4 Trợ lý ảo và sinh tăng cường truy xuất trong giáo dục *(chưa có nguồn — cần tìm)*
  - 1.2.5 Đánh giá hệ thống sinh tăng cường truy xuất
- 1.3 Mục tiêu, đối tượng và phạm vi nghiên cứu — phạm vi lấy theo hiện thực: 3 môn, 65 tệp học liệu tại thời điểm benchmark `[LOG §3]`.
- 1.4 Phương pháp nghiên cứu.
- 1.5 Những điểm mới của đề tài — chỉ những gì có bằng chứng trong mã/log.
- 1.6 Cấu trúc khóa luận.

### Chương 2. Cơ sở lý thuyết
- 2.1 Hệ thống e-learning và học liệu dị chất (LOM).
- 2.2 Mô hình ngôn ngữ lớn và mô hình biểu diễn.
- 2.3 Sinh tăng cường truy xuất và mở rộng đa phương thức.
- 2.4 Truy xuất thông tin: độ tương đồng cosine, HNSW, BM25, hợp nhất thứ hạng nghịch đảo, xếp hạng lại. Công thức lấy đúng như mã: điểm dense = 1 − khoảng cách cosine; RRF `Σ 1/(60+rank)`.
- 2.5 Xử lý học liệu đa định dạng: phân tích bố cục tài liệu, OCR, ASR, băm ảnh.
- 2.6 Viết lại truy vấn và sinh có căn cứ.
- 2.7 Chỉ số đánh giá: Precision/Recall/F1@K, trung bình macro, RAGAs.

### Chương 3. Phương pháp thực hiện
- 3.1 Kiến trúc tổng thể — `factory.py:build_services`; nạp dữ liệu, truy xuất, sinh câu trả lời là các gói tách rời; mô hình sinh chỉ nạp ở lần hỏi đầu.
- 3.2 Biểu diễn đối tượng tri thức và siêu dữ liệu — bảng trường thực tế (`pipeline/indexing.py:base_metadata`); mã vector `{sha256}:{kind}:{chunk_index}`; chuẩn hóa NFC; loại trùng bằng SHA-256.
- 3.3 Tiền xử lý tài liệu, bảng và ảnh — Docling với `do_ocr=False`, OCR dự phòng khi mọi trang < 40 ký tự gốc (`MIN_NATIVE_TEXT`), ảnh trang cho mọi trang PDF/PPTX, bảng dạng markdown; kích thước đoạn (ký tự): PDF/DOCX 350/60, PPTX 280/40, TXT 500/50.
- 3.4 Tiền xử lý video — 7 bước; cửa sổ 30 s (phiên âm gán theo thời điểm bắt đầu); khung thô 1 khung/10 s; băm trung bình 8×8 với ngưỡng 0,90; OCR mỗi 30 s; điểm chọn khung = 0,35·thay đổi thị giác + 0,30·thay đổi OCR + 0,20·biên cảnh + 0,15·phủ thời gian; tối đa 3 khung/cửa sổ; điểm kiểm tra tiếp tục (`video_pipeline_version=v2-long`).
- 3.5 Lập chỉ mục hai không gian vector — Qwen3-Embedding-0.6B (chuẩn hóa L2, tiền tố chỉ dẫn cho truy vấn); Qwen3-VL-Embedding-2B; Chroma cosine; BM25 sidecar `data/bm25.pkl`.
- 3.6 Truy xuất lai đa phương thức — thuật toán từng bước: xử lý truy vấn → (tuỳ chọn) viết lại + truy vấn con → dense × N + BM25 + visual → RRF (k=60) → thưởng theo loại (0,02/0,01/0,005) → đa dạng theo file (tối đa 2/tệp, xoay vòng) → mở rộng ngữ cảnh (cùng trang / ±1 đoạn) → nén trích xuất (đoạn ≥ 240 ký tự).
- 3.7 Sinh câu trả lời có căn cứ — prompt bắt buộc đường dẫn tương đối + trang/mốc thời gian; ngưỡng từ chối cosine 0,15; định tuyến sang Qwen3-VL-2B khi có ảnh trang/hình từ PDF/PPT/PPTX/DOCX; sự kiện SSE `status/query/sources/delta/done`.
- 3.8 Khung đánh giá không rò rỉ dữ liệu — tệp truy vấn chỉ có `question_id`, `question`, `course_id`; ground truth chỉ được đọc sau khi truy xuất xong; câu không trả lời được tính riêng.

### Chương 4. Thực nghiệm, đánh giá và thảo luận
- 4.1 Môi trường thực nghiệm — phải ghi rõ **môi trường nào cho mục nào**: benchmark chạy trên Python 3.11.15, torch 2.14.0, transformers 5.16.1, sentence-transformers 6.0.1, chromadb 1.5.9, rank-bm25 0.2.2 `[LOG §12]`; lần ingest hiện tại chạy Python 3.12.14 trên máy này. Phần cứng: `[TODO-bạn]`.
- 4.2 Dữ liệu thực nghiệm — 65 tệp (20 PDF, 12 PPTX, 4 DOCX, 29 MP4) thuộc 3 môn; 40/65 được index khi chạy; 400 câu → 380 có thể trả lời → 325 hợp lệ (coverage 85,53%) + 20 không trả lời được; chính sách nhãn `infer` `[LOG §2–3, §8]`.
- 4.3 Cấu hình hai hệ thống so sánh — bảng `[LOG §5]`.
- 4.4 Tiêu chí đánh giá — định nghĩa Precision/Recall/F1@K và điều kiện "kết quả liên quan" (trùng tài nguyên + trang/slide/giao khoảng timestamp) `[LOG §7]`.
- 4.5 Kết quả và nhận xét — bảng bên dưới + khoảng tin cậy bootstrap. **Không** viết "vượt trội".
- 4.6 Phân tích và thảo luận — hit@10 ≈ 0,40 ở cả hai hệ thống; P@10 bị chặn trên bởi thiết kế (tối đa 2 kết quả/tệp, K cố định, trung bình 1,345 evidence/câu); RQ nào đã/chưa trả lời được; mối đe dọa tính giá trị.
- 4.7 Hiện thực hệ thống — API `/v1/ask` (SSE), `/v1/search`, `/v1/stats`, `/v1/files`; khóa API tùy chọn; một tiến trình, một yêu cầu suy luận tại một thời điểm (`inference_lock`). Ảnh chụp demo: `[TODO-bạn]`.
- 4.8 Sổ trạng thái thực nghiệm (§4 dưới đây).
- 4.9 Ưu điểm và hạn chế `[LOG §13]`.

### Chương 5. Kết luận và hướng phát triển
- 5.1 Kết luận — chỉ những gì đạt được, bám số liệu.
- 5.2 Hướng phát triển — hợp nhất theo loại truy vấn và độ tin cậy nguồn; chỉ mục bài tập + phân quyền; đồ thị tri thức nhẹ; đánh giá đầu-cuối; mở rộng corpus. Mỗi hướng có `\cite`.

## 4. Sổ trạng thái thực nghiệm

### Đã có kết quả

| Nội dung | Bằng chứng | Ghi chú |
|---|---|---|
| Benchmark truy xuất 2 hệ thống, 400 câu, Top-10, P/R/F1@{1,5,10}, macro trên 325 câu | `EXPERIMENT_LOG.md` §10; đã đối chiếu `evals/results/*_metrics.json` trong git `HEAD` (khớp) | Xem bảng dưới |
| Kiểm định bootstrap ghép cặp (10.000 lần, seed 20260928) | Do mình tính ngày 2026-09-28 từ `per_question` của 2 file metrics | **Script chưa được lưu vào repo** — cần lưu và ghi vào chương 4 |
| Thử nghiệm sơ bộ golden set (n=35): baseline `path_recall=0,975`, `path_precision=0,392`; sau đổi kích thước đoạn `0,889`/`0,363` | `evals/README.md` | **Chưa đối chiếu với `evals/reports/baseline.json`/`post-chunk.json`**; corpus cũ; chỉ dùng như thử nghiệm sơ bộ |
| Kiểm thử tự động | 152 hàm `test_*` trong `tests/`; log ghi 16 test benchmark/eval chạy thành công | **Chưa chạy lại** (không chạy khi ingest đang chạy) |
| Dữ liệu thời gian ingest video | `logs/ingest_full_20260927_233033.log` (vd. `buoi_1.mp4`: 2521,81 s cho video 11383,9 s) | Không kiểm soát thiết bị/checkpoint nên chưa dùng làm số đo hiệu năng |

**Kết quả benchmark (macro trên 325 câu; đã đối chiếu file gốc):**

| Hệ thống | P@1 | R@1 | F1@1 | P@5 | R@5 | F1@5 | P@10 | R@10 | F1@10 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Baseline dense text | 0,1877 | 0,1462 | 0,1589 | 0,0708 | 0,2841 | 0,1108 | 0,0486 | 0,3323 | 0,0828 |
| Proposed hybrid multimodal | 0,1908 | 0,1628 | 0,1715 | 0,0597 | 0,2462 | 0,0941 | 0,0458 | 0,3446 | 0,0793 |

**Chênh lệch proposed − baseline, khoảng tin cậy 95% (bootstrap ghép cặp):**
P@5 −0,0111 [−0,0191; −0,0037] · R@5 −0,0379 [−0,0687; −0,0087] · F1@5 −0,0167 [−0,0288; −0,0050] (khoảng **không** chứa 0).
Các chỉ số còn lại tại K=1 và K=10 có khoảng chứa 0 ⇒ chưa phân biệt được. Không thể kết luận proposed tốt hơn.

### Đang thực hiện

| Nội dung | Bằng chứng | Hệ quả |
|---|---|---|
| Ingest lại toàn bộ `./assets` trên máy này | Tiến trình `python -m app.main ingest ./assets` (PID 57084, khởi động 2026-09-27 23:30, chạy tuần tự, `HF_HUB_OFFLINE=1`); nhật ký `logs/ingest_full_20260927_233033.log`, cập nhật lần cuối 2026-09-28 19:49 | Index hiện tại là ảnh chụp giữa chừng (manifest có 14 đường dẫn lúc kiểm tra). Chỉ chạy lại benchmark **sau khi ingest xong** và đã chốt snapshot Chroma + BM25 |

### Sẽ thực hiện (đề xuất; hiện **chưa có kết quả** — không được viết số)

- Chạy lại baseline/proposed trên corpus đầy đủ sau khi ingest xong.
- Ablation: chỉ BM25; dense + BM25 không visual; text + visual không BM25; chỉ visual; không lọc course; bật reranker; mở rộng/nén ngữ cảnh; tham số RRF.
- Đánh giá đầu-cuối: đúng/sai của câu trả lời, faithfulness, độ chính xác/độ phủ trích dẫn, từ chối đúng câu ngoài phạm vi (cần định nghĩa trường `abstained`).
- Độ trễ công bằng (cùng thiết bị, khởi động nóng, lặp), bộ nhớ, chi phí; kết quả theo môn và theo loại câu hỏi (cần thêm trường `category`); phân tích lỗi định tính; người thứ hai rà soát ground truth.
- Hướng phát triển (chưa hiện thực): task-/reliability-aware fusion, chỉ mục bài tập + phân quyền, đồ thị tri thức, liên kết video↔slide.

## 5. Việc bạn cần cung cấp hoặc xác nhận

1. **Bìa và phần đầu:** tên tác giả, MSSV, email, giảng viên hướng dẫn, khoa/trường, năm, lời cảm ơn, hội đồng.
2. **Dữ liệu đánh giá:** `questions_draft.json` (nằm ngoài repo; log dùng đường dẫn của tài khoản máy khác); ai gán nhãn, quy trình rà soát chéo (đề cương yêu cầu tối thiểu 2 người); trạng thái `[CHƯA XÁC NHẬN]` của toàn bộ evidence.
3. **Tái lập:** benchmark chạy ngày 2026-09-26 trước khi mã được commit (`7f1df63`, 2026-09-27 18:32). Từ `7f1df63` đến `HEAD`, thư mục `retrieval/`, `eval/`, `generation/`, `pipeline/`, `embeddings/`, `vectorstore/` **không thay đổi** (đã kiểm tra bằng `git diff`); chỉ `app/storage/base.py` thêm 16 dòng. Vẫn còn thay đổi chưa commit ở 6 tệp (`.env.example`, `settings.py`, `factory.py`, `video_loader.py`, `main.py`, `video_checkpoint.py`); diff của `settings.py`/`factory.py`/`video_checkpoint.py` chủ yếu là định dạng, `whisper_language`, bỏ qua đăng nhập khi `HF_HUB_OFFLINE`, không lùi trạng thái checkpoint; **diff của `main.py` và `video_loader.py` mình chưa xem chi tiết**. Bạn cần xác nhận lúc chạy benchmark dùng đúng mã này.
4. **Phần cứng và mô hình:** chip/RAM/macOS đã chạy benchmark; revision + dtype của Qwen3-Embedding-0.6B và Qwen3-VL-Embedding-2B; mô hình và tham số Whisper (MLX) tạo các tệp sidecar timestamp.
5. **Lý do chọn công nghệ:** vì sao Qwen3/Chroma/Tesseract thay vì công cụ đề cương tham khảo (BGE-M3, PaddleOCR, FAISS/Qdrant). Cần có nguồn để trích dẫn, không phải suy đoán.
6. **Thuật ngữ:** chốt bản dịch tiếng Việt trong bảng §1.4, và tên gọi cho "RAG đa phương thức" (chưa có viết tắt chuẩn).
7. **Tên gọi kỹ thuật:** mã dùng `average_hash` (băm trung bình) nhưng README/`.env` gọi "pHash". Khóa luận sẽ gọi đúng là "băm trung bình" — cần bạn đồng ý.
8. **Lỗi trong mã (bạn tự quyết định sửa hay không):** prompt của `LocalQwenVLAnswerer` gắn cứng "môn Cấu trúc rời rạc" (`generation/vl_answerer.py`), mâu thuẫn với tuyên bố course-aware; nếu không sửa, phải ghi vào hạn chế.
9. **Bảo toàn bằng chứng:** `evals/results/` và `evals/reports/` đang bị xóa trong working tree (chưa commit) nhưng còn trong `HEAD`. Đừng commit việc xóa này; nếu muốn dọn, hãy lưu bản sao ra ngoài trước vì đó là bằng chứng cho Chương 4.
10. **Hình và demo:** ảnh chụp API/UI, deadline nộp.

Mâu thuẫn số liệu giữa các tài liệu cần thống nhất khi viết: `evals/draft/README.md` (200 câu, 48 học liệu, 2 môn) ≠ `EXPERIMENT_LOG.md` (400 câu, 65 tệp, 3 môn) ≠ đề cương (500–800 câu, 20–40 video). Khóa luận dùng số của log vì đó là lần chạy thực tế; các số còn lại chỉ nêu là kế hoạch hoặc phiên bản nháp.

## 6. Lộ trình

| Bước | Việc | Xong khi |
|---|---|---|
| 1 | Sao chép mẫu sang `document/KLTN_<tên>/` (giữ nguyên mẫu), biên dịch thử (`latexmk`, `biber`, gói `vietnam`) | PDF của mẫu biên dịch được trên máy này |
| 2 | Dựng `glossary.yaml`, `lint_glossary.py`, `citations_ledger.md`; lưu script bootstrap | Lint chạy được trên mẫu; sổ trích dẫn có 10 tài liệu khởi đầu ở trạng thái "chưa xác thực" |
| 3 | Xác thực trích dẫn (mở nguồn gốc, ghi sổ) | Mỗi mục trong `references.bib` có dòng xác thực |
| 4 | Viết theo thứ tự: Chương 3 → 4 → 2 → 1 → 5 → Tóm tắt → danh mục | Mỗi chương qua lint + đối chiếu sổ khẳng định |
| 5 | Vẽ hình: kiến trúc, pipeline video, luồng truy xuất | Bạn duyệt hình |
| 6 | Sau khi ingest xong: chốt snapshot, chạy lại benchmark (nếu chọn), cập nhật Chương 4 | Số liệu Chương 4 khớp file kết quả mới |
| 7 | Rà soát cuối: lint, sổ khẳng định, biên dịch, kiểm tra danh mục | Không còn `[TODO-bạn]` chưa xử lý |
