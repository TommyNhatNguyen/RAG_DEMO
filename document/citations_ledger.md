# Sổ trích dẫn (xác thực ngày 2026-09-28)

Phương pháp xác thực: mở trang gốc (arXiv, ACL Anthology, PMLR, ICLR, IEEE SA, Google Research) hoặc siêu dữ liệu Crossref; đối chiếu tiêu đề, tác giả, năm, nơi công bố. Công cụ trích xuất trang web có thể sai sót, vì vậy **bạn nên mở nhanh từng liên kết để kiểm tra lại** trước khi nộp (cột "Cách xác thực" cho biết nên mở đâu).

Quy ước cột "Mức": **A** = đã đối chiếu trang gốc của nhà xuất bản/hội nghị hoặc arXiv; **B** = chỉ xác thực qua kết quả tìm kiếm/Crossref, cần bạn mở lại; **C** = chỉ dùng ở mức tiêu đề, chưa đọc được tóm tắt.

| Khóa | Tài liệu | Mức | Cách xác thực | Dùng để hỗ trợ (Chương) | Lưu ý |
|---|---|---|---|---|---|
| `lewis2020rag` | Lewis et al., RAG, NeurIPS 2020 | A | arxiv.org/abs/2005.11401 (ghi "Accepted at NeurIPS 2020") | 1, 2 | Chỉ nêu ý trong hai câu đầu tóm tắt và tiêu đề |
| `chen2022murag` | Chen et al., MuRAG, EMNLP 2022 | A | arxiv.org/abs/2210.02928 | 1, 2 | |
| `abootorabi2025ask` | Abootorabi et al., khảo sát Multimodal RAG, Findings of ACL 2025 | B | arXiv ok; nơi công bố và số trang lấy từ kết quả tìm kiếm ACL Anthology (2025.findings-acl.861) | 1, 2, 5 | Mở aclanthology.org/2025.findings-acl.861 để kiểm tra trang 16776–16809 |
| `faysse2025colpali` | Faysse et al., ColPali, ICLR 2025 | A | arxiv.org/abs/2407.01449 ("Published as a conference paper at ICLR 2025") | 1, 2, 5 | |
| `yu2025visrag` | Yu et al., VisRAG, ICLR 2025 | A | iclr.cc/virtual/2025/poster/27679, openreview.net/forum?id=zG459X3Xge | 1, 2 | |
| `huang2022layoutlmv3` | Huang et al., LayoutLMv3, ACM MM 2022 | A | arxiv.org/abs/2204.08387 (ghi "ACM Multimedia 2022") | 1 | Chỉ dùng ở mức mục tiêu tiền huấn luyện Document AI |
| `tanaka2025vdocrag` | Tanaka et al., VDocRAG, CVPR 2025 | A | arxiv.org/abs/2504.09795 ("Accepted by CVPR 2025") | 1, 2, 5 | |
| `gao2026scaling` | Gao et al., khảo sát Multimodal RAG cho hiểu tài liệu | A | aclanthology.org/2026.acl-long.204 (ACL 2026, tr. 4458–4489) | 1, 2 | **Đề cương ghi năm 2025 (bản arXiv 10/2025); bản chính thức là ACL 2026** |
| `gao2023ragsurvey` | Gao et al., khảo sát RAG cho LLM | A | arxiv.org/abs/2312.10997 | 1, 2 | |
| `jeong2025videorag` | Jeong et al., VideoRAG, Findings of ACL 2025 | A | aclanthology.org/2025.findings-acl.1096 | 1, 5 | |
| `tanner2025lecture` | Tanner, Marfurt et al., hỏi đáp video bài giảng bằng RAG đa phương thức | C | Crossref DOI 10.1007/978-3-031-81542-3_15; **tác giả thứ ba bị mâu thuẫn** (Crossref "Oçul", Semantic Scholar "Oğul") nên ghi "và cộng sự" | 1 | Chưa đọc được tóm tắt: chỉ dùng theo tiêu đề. Nên mở trang Springer để bổ sung |
| `li2025ragedu` | Li et al., khảo sát RAG cho ứng dụng giáo dục, Computers and Education: AI 8 (2025) 100417 | B | Crossref DOI 10.1016/j.caeai.2025.100417 | 1 | Chưa đọc được tóm tắt: chỉ dùng theo tiêu đề |
| `gokhman2025vlrag` | Gokhman et al., nền tảng dạy học VL-RAG | A | arxiv.org/abs/2503.05464 | 1 | |
| `kazemitabaar2024codeaid` | Kazemitabaar et al., CodeAid, CHI 2024 | A | arxiv.org/abs/2401.11314 | 5 | DOI lấy từ URL ACM trong kết quả tìm kiếm |
| `edge2024graphrag` | Edge et al., GraphRAG | A | arxiv.org/abs/2404.16130 | 5 | |
| `es2024ragas` | Es et al., RAGAs, EACL 2024 (demo) | A | aclanthology.org/2024.eacl-demo.16 | 1, 2, 5 | RAGAs là khung đánh giá không cần nhãn chuẩn; các số đo tham chiếu trong mã của dự án là bổ sung |
| `karpukhin2020dpr` | Karpukhin et al., DPR, EMNLP 2020 | A | arxiv.org/abs/2004.04906 | 1, 2 | |
| `cormack2009rrf` | Cormack et al., RRF, SIGIR 2009 | B | Crossref DOI 10.1145/1571941.1572114, dblp | 2 | Không nêu giá trị k của bài gốc; k = 60 là tham số của mã |
| `robertson2009bm25` | Robertson & Zaragoza, BM25 | B | DOI 10.1561/1500000019 | 2 | **Số tập/số trang mâu thuẫn giữa nguồn nên bỏ khỏi .bib**; cần tra lại và kiểm tra công thức trong bài |
| `malkov2020hnsw` | Malkov & Yashunin, HNSW, TPAMI 2020 | B | Crossref DOI 10.1109/TPAMI.2018.2889473 | 2 | |
| `nogueira2019passage` | Nogueira & Cho, Passage Re-ranking with BERT | A | arxiv.org/abs/1901.04085 | 2, 5 | |
| `gao2023hyde` | Gao et al., HyDE, ACL 2023 | A | aclanthology.org/2023.acl-long.99; arxiv.org/abs/2212.10496 | 2 | |
| `auer2024docling` | Auer et al., Docling Technical Report | A | arxiv.org/abs/2408.09869 | 2, 3 | Báo cáo mô tả chuyển đổi PDF; việc dùng cho DOCX/PPTX là từ mã |
| `smith2007tesseract` | Smith, Tesseract, ICDAR 2007 | A | research.google/pubs/an-overview-of-the-tesseract-ocr-engine | 2 | |
| `radford2023whisper` | Radford et al., Whisper, ICML 2023 | A | proceedings.mlr.press/v202/radford23a.html; arxiv.org/abs/2212.04356 | 2 | |
| `yang2025qwen3` | Qwen3 Technical Report | A | arxiv.org/abs/2505.09388 | 2 | Danh sách tác giả rút gọn ("và cộng sự") |
| `zhang2025qwen3embedding` | Qwen3 Embedding | A | arxiv.org/abs/2506.05176 | 2, 3 | |
| `bai2025qwen3vl` | Qwen3-VL Technical Report | A | arxiv.org/abs/2511.21631 | 2, 3 | Danh sách tác giả rút gọn |
| `li2026qwen3vlembedding` | Qwen3-VL-Embedding và Qwen3-VL-Reranker | A | arxiv.org/abs/2601.04720 | 2, 3 | |
| `ieee2020lom` | IEEE Std 1484.12.1-2020, LOM | C | standards.ieee.org/ieee/1484.12.1/7699/ (chỉ tiêu đề, năm, trạng thái) | 2, 5 | Chưa đọc được nội dung tiêu chuẩn; không nêu chi tiết các nhóm siêu dữ liệu |
| `furnas1987vocabulary` | Furnas et al., vấn đề từ vựng, CACM 1987 | B | kết quả tìm kiếm + URL ACM DL (DOI 10.1145/32206.32212) | 1 | Ý dùng: xác suất hai người chọn cùng một thuật ngữ < 0,20 trong các miền khảo sát |
| `manning2008ir` | Manning et al., Introduction to Information Retrieval | A | nlp.stanford.edu/IR-book (cosine ở mục "Dot products"; Precision/Recall/F ở mục "Evaluation of unranked retrieval sets") | 2 | |
| `efron1993bootstrap` | Efron & Tibshirani, bootstrap | B | kết quả tìm kiếm (Chapman & Hall, 1993) | 2, 4 | Số trang bị mâu thuẫn nên bỏ |
| `smucker2007comparison` | Smucker et al., CIKM 2007 | B | Crossref DOI 10.1145/1321440.1321528 | 2, 4 | Bài so sánh các kiểm định gồm bootstrap |

## Đã loại

- **CourseTimeQA** (Kovalev & Kumar, arXiv 2512.00360): bài đã bị **rút lại** vì số liệu đo sai; không trích dẫn.

## Tài liệu trong đề cương nhưng chưa dùng

- IEEE 1484.12.1 chỉ dùng ở mức tên tiêu chuẩn. Các tài liệu còn lại của đề cương (§23) đều đã được xác thực và dùng.

## Phần mềm (chú thích chân trang, không đưa vào .bib)

Đã kiểm tra trang tồn tại và mô tả một dòng: `github.com/SYSTRAN/faster-whisper`, `github.com/chroma-core/chroma`, `github.com/tesseract-ocr/tesseract`, `github.com/docling-project/docling`, `ffmpeg.org`, `pypi.org/project/rank-bm25`. Thẻ mô hình Hugging Face của Qwen3-Embedding-0.6B, Qwen3-VL-Embedding-2B, Qwen3-1.7B, Qwen3-VL-2B-Instruct, Qwen3-Reranker-0.6B đã được đối chiếu với các thông số nêu trong Chương 3.

## Cập nhật sau kiểm tra độc lập (2026-09-28)

Ba người kiểm tra độc lập đã rà lại bản thảo (Chương 3 với mã nguồn, Chương 4 với số liệu gốc, các câu trích dẫn với nguồn). Kết luận về trích dẫn: không có khẳng định bịa hay gán sai nguồn; ba chỗ diễn đạt quá mức đã được sửa:

- **VL-RAG** (`gokhman2025vlrag`): tóm tắt gốc nói "database of tailored answers and images", không nói "được tuyển chọn"; bản thảo đã bỏ tính từ "tuyển chọn" và bỏ câu đối lập dựa vào nó.
- **LOM** (`ieee2020lom`): danh sách trường "chương, tuần, mục tiêu học tập, độ khó, phiên bản học liệu" là đề xuất của tác giả, không phải danh sách trong tiêu chuẩn (chỉ đọc được trang giới thiệu của tiêu chuẩn); Chương 5 đã nói rõ.
- **Docling** (`auer2024docling`): báo cáo kỹ thuật chỉ mô tả chuyển đổi PDF; việc dùng cho DOCX/PPTX là từ mã nguồn, đã tách rõ ở Chương 2 và 3.

**Các câu chỉ được xác thực qua tóm tắt hoặc kết quả tìm kiếm (không đọc toàn văn) — bạn nên tự mở đối chiếu:**

| Nguồn | Câu trong bản thảo | Nơi cần mở |
|---|---|---|
| `jeong2025videorag` | phần lớn RAG trước đây bỏ qua video; có cơ chế chọn khung hình; trích văn bản khi không có phụ đề (Chương 1) | aclanthology.org/2025.findings-acl.1096 |
| `gao2026scaling` | quy trình OCR mất chi tiết cấu trúc, mô hình đa phương thức gốc khó mô hình hóa ngữ cảnh (Chương 1); tiêu chí phân loại khảo sát (Chương 2) | aclanthology.org/2026.acl-long.204 |
| `abootorabi2025ask` | phạm vi khảo sát (Chương 1, 2, 5) | aclanthology.org/2025.findings-acl.861 |
| `furnas1987vocabulary` | xác suất < 0,20, năm miền ứng dụng (Chương 1) | dl.acm.org/doi/10.1145/32206.32212 |
| `bai2025qwen3vl` | ngữ cảnh xen kẽ văn bản, ảnh, video (Chương 2) | arxiv.org/abs/2511.21631 |
| `edge2024graphrag` | mô tả GraphRAG (Chương 5) | arxiv.org/abs/2404.16130 |
| `tanner2025lecture`, `li2025ragedu` | chỉ dùng ở mức tiêu đề (Chương 1) | trang Springer / ScienceDirect (chưa mở được) |
| `robertson2009bm25`, `efron1993bootstrap` | chỉ dùng tên khung/phương pháp; công thức BM25 cần đối chiếu (Chương 2) | bài gốc / sách |
