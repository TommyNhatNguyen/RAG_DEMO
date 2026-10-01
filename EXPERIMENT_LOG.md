# EXPERIMENT LOG

> Trạng thái: nhật ký thực nghiệm dự thảo, dùng làm nguồn sự thật khi viết báo cáo.
>
> Ngày chạy retrieval benchmark: 2026-09-26.
>
> Quy ước: `[CHƯA XÁC NHẬN]` nghĩa là thông tin chưa có đủ bằng chứng trong mã, dữ liệu hoặc log đã kiểm tra. Các kết quả trong tài liệu này chưa phải kết luận nghiên cứu chính thức.

# 1. Research objective

## Mục tiêu thực nghiệm

Đánh giá khả năng truy xuất bằng chứng từ kho học liệu e-learning đa định dạng cho cùng một bộ 400 câu hỏi. Thực nghiệm hiện tại chỉ đánh giá **retrieval**, chưa đánh giá chất lượng câu trả lời end-to-end.

Các mục tiêu đã thực hiện:

- Chạy cùng một tập truy vấn qua hai cấu hình retrieval.
- Lưu tối đa Top-10 kết quả cho từng câu hỏi.
- Đối chiếu kết quả với evidence trong bộ câu hỏi sau khi retrieval hoàn tất.
- Tính Precision@K, Recall@K và F1@K tại K = 1, 5, 10.
- Tách câu hỏi unanswerable khỏi retrieval Precision/Recall/F1.
- Loại khỏi macro evaluation những câu answerable có ground-truth thuộc tài nguyên chưa được index.

## Baseline cần so sánh

`baseline_dense_text`: dense retrieval trên text collection bằng `Qwen/Qwen3-Embedding-0.6B`; không truy xuất visual collection, không BM25, không reranker.

## Proposed system cần đánh giá

`proposed_hybrid_multimodal`: kết hợp dense text retrieval, BM25 và visual retrieval bằng `Qwen/Qwen3-VL-Embedding-2B`; hợp nhất các danh sách bằng Reciprocal Rank Fusion (RRF); không bật reranker.

# 2. Dataset construction

## Bộ câu hỏi hiện được dùng

- File nguồn: `/Users/VoThiXuanHoa/Documents/RAG project/questions_draft.json`.
- Số record: **400**.
- File nguồn không lưu `question_id`; bước chuẩn bị benchmark gán ID liên tục theo vị trí mảng: `Q001`–`Q400`.
- Phân bố theo môn:
  - `cau_truc_roi_rac`: 134 câu.
  - `nhap_mon_lap_trinh`: 133 câu.
  - `cau_truc_du_lieu_va_giai_thuat`: 133 câu.
- SHA-256 của file nguồn tại thời điểm chạy: `346530eecd70b2b6f0bd15ce13d72b6989dac6d32a0b14522ef02851af463648`.

## Các loại câu hỏi

Thiết kế ban đầu quy định tám nhóm và chỉ tiêu sau:

| Nhóm thiết kế | Chỉ tiêu |
|---|---:|
| `video_grounded` | 60 |
| `slide_grounded` | 60 |
| `pdf_grounded` | 60 |
| `exercise_grounded` | 40 |
| `metadata_grounded` | 40 |
| `cross_source` | 80 |
| `visual` | 40 |
| `unanswerable` | 20 |
| **Tổng** | **400** |

Tuy nhiên, file `questions_draft.json` hiện tại **không có trường `category`**. Vì vậy, phân bố thực tế theo tám nhóm trên là `[CHƯA XÁC NHẬN]`; không được mặc định rằng chỉ tiêu thiết kế chính là phân bố thực tế.

## Cấu trúc mỗi question trong file hiện tại

Mỗi record hiện có đúng các trường:

- `question`
- `required_sources`
- `evidence`
- `course_id`
- `module_id`
- `learning_outcome`
- `answerable`
- `difficulty`

File hiện không có `answer`, `review_status`, `review_note` hoặc `question_id`.

## `required_sources`

Các tổ hợp thực tế trong 400 record:

| `required_sources` | Số câu |
|---|---:|
| `['slide']` | 103 |
| `['video', 'pdf']` | 77 |
| `['video']` | 61 |
| `['pdf']` | 56 |
| `['metadata']` | 41 |
| `['exercise']` | 41 |
| `['metadata', 'slide']` | 1 |
| `[]` | 20 |

Các tổ hợp này không thay thế cho trường `category` và không đủ để khôi phục chắc chắn tám nhóm thiết kế.

## `evidence`

- 380 câu có ít nhất một evidence.
- 20 câu có evidence rỗng.
- Các trường evidence xuất hiện trong file: `resource_id`, `page`, `slide`, `timestamp`.
- Evidence không có trường `excerpt` trong phiên bản file đã chạy.
- `resource_id` được dùng để ánh xạ về file học liệu thật.
- `page` và `slide` là vị trí bắt đầu từ 1 theo quy ước của bộ câu hỏi.
- `timestamp` có dạng khoảng thời gian, ví dụ `00:00:32–00:00:57`.

## `answerable` / `unanswerable`

Nhãn lưu trực tiếp trong file:

- `answerable=true`: 151 câu.
- `answerable=null`: 249 câu.
- `answerable=false`: 0 câu.

Khi chấm retrieval, đã dùng `null_policy=infer`:

- `answerable=null` và evidence không rỗng → suy ra answerable: 229 câu.
- `answerable=null` và evidence rỗng → suy ra unanswerable: 20 câu.

Do đó tập đánh giá được xem là 380 answerable và 20 unanswerable. Đây là **nhãn suy ra cho lần đánh giá**, không phải 20 nhãn `false` được lưu trực tiếp trong dataset.

## Cách xác định ground truth

- Ground truth retrieval là danh sách `evidence` của từng record trong `questions_draft.json`.
- Mỗi evidence xác định tài nguyên đúng và, khi có, vị trí đúng bằng trang, slide hoặc khoảng timestamp.
- Người dùng đã chấp nhận bộ 400 câu là hoàn thiện cho lần chạy hiện tại do giới hạn thời gian.
- Mức độ rà soát độc lập toàn bộ 400 câu bởi người đánh giá thứ hai: `[CHƯA XÁC NHẬN]`.
- Bộ câu hỏi này được giữ làm dữ liệu human/evaluation và không được ingest làm học liệu đầu vào của RAG.

# 3. Corpus preparation

## Học liệu local được kiểm kê

Tại thời điểm đánh giá, thư mục `assets/` có 65 file học liệu thuộc ba môn:

| Loại file | Số file local |
|---|---:|
| PDF | 20 |
| PPTX | 12 |
| DOCX | 4 |
| MP4 | 29 |
| **Tổng** | **65** |

## Trạng thái ChromaDB khi chạy benchmark

- Text collection: `text_embeddings`, 13.869 vectors.
- Visual collection: `visual_embeddings`, 6.580 vectors.
- Tổng số vector: 20.449.
- Phân bố `content_type`:
  - `text`: 8.235.
  - `table`: 51.
  - `video_segment`: 5.583.
  - `page`: 227.
  - `image`: 640.
  - `video_frame`: 5.713.
- Số tài nguyên duy nhất thực sự xuất hiện trong metadata ChromaDB: **40/65**.

Phân bố 40 tài nguyên đã index:

| Môn | PDF | PPTX | DOCX | MP4 | Tổng |
|---|---:|---:|---:|---:|---:|
| Cấu trúc rời rạc | 4 | 5 | 3 | 5 | 17 |
| Nhập môn Lập trình | 5 | 0 | 0 | 1 | 6 |
| Cấu trúc Dữ liệu và Giải thuật | 0 | 7 | 0 | 10 | 17 |
| **Tổng** | **9** | **12** | **3** | **16** | **40** |

## Tài nguyên local chưa index

Có **25** file local chưa xuất hiện trong metadata của hai collection:

### Cấu trúc rời rạc — 5 file

- `RAG_DEMO/assets/cau_truc_roi_rac/buoi_5/buoi_5.mp4`
- `RAG_DEMO/assets/cau_truc_roi_rac/buoi_6/buoi_6.mp4`
- `RAG_DEMO/assets/cau_truc_roi_rac/buoi_7/buoi_7.mp4`
- `RAG_DEMO/assets/cau_truc_roi_rac/buoi_8/buoi_8.mp4`
- `RAG_DEMO/assets/cau_truc_roi_rac/buoi_9/buoi_9.mp4`

### Nhập môn Lập trình — 20 file

- `RAG_DEMO/assets/nhap_mon_lap_trinh/buoi_2/buoi_2_thuat_toan.mp4`
- `RAG_DEMO/assets/nhap_mon_lap_trinh/buoi_3/Cau_truc_lap.pdf`
- `RAG_DEMO/assets/nhap_mon_lap_trinh/buoi_3/buoi_3_cac_kieu_du_lieu_co_ban.mp4`
- `RAG_DEMO/assets/nhap_mon_lap_trinh/buoi_4/Ham.pdf`
- `RAG_DEMO/assets/nhap_mon_lap_trinh/buoi_4/buoi_4_cau_truc_dieu_khien.mp4`
- `RAG_DEMO/assets/nhap_mon_lap_trinh/buoi_5/De_quy.pdf`
- `RAG_DEMO/assets/nhap_mon_lap_trinh/buoi_5/buoi_5_function.mp4`
- `RAG_DEMO/assets/nhap_mon_lap_trinh/buoi_6/Mang1Chieu.pdf`
- `RAG_DEMO/assets/nhap_mon_lap_trinh/buoi_6/buoi_6_mang.mp4`
- `RAG_DEMO/assets/nhap_mon_lap_trinh/buoi_7/Mang2Chieu.pdf`
- `RAG_DEMO/assets/nhap_mon_lap_trinh/buoi_7/buoi_7_mang_hai_chieu_chuoi.mp4`
- `RAG_DEMO/assets/nhap_mon_lap_trinh/buoi_8/Chuoi_ky_tu.pdf`
- `RAG_DEMO/assets/nhap_mon_lap_trinh/buoi_8/buoi_8_con_tro.mp4`
- `RAG_DEMO/assets/nhap_mon_lap_trinh/buoi_9/Contro_P1.pdf`
- `RAG_DEMO/assets/nhap_mon_lap_trinh/buoi_9/Contro_P2.pdf`
- `RAG_DEMO/assets/nhap_mon_lap_trinh/buoi_9/buoi_9_struct.mp4`
- `RAG_DEMO/assets/nhap_mon_lap_trinh/de_cuong/IT001.M21.VB2_.pdf`
- `RAG_DEMO/assets/nhap_mon_lap_trinh/de_cuong/IT001.N11.CNVN.pdf`
- `RAG_DEMO/assets/nhap_mon_lap_trinh/de_cuong/IT001.N11.VB2_.pdf`
- `RAG_DEMO/assets/nhap_mon_lap_trinh/de_cuong/Noi_dung.docx`

Trong 25 file trên, có **18 resource_id** được evidence của bộ câu hỏi tham chiếu. Bảy file chưa index nhưng không nằm trong ground truth của 400 câu hiện tại là video Cấu trúc rời rạc Buổi 5–7 và bốn file đề cương Nhập môn Lập trình.

## Corpus coverage dùng khi chấm

- 380 câu answerable theo chính sách suy ra.
- 55/380 câu answerable có ít nhất một ground-truth resource chưa được index.
- 325/380 câu answerable có toàn bộ ground-truth resource trong ChromaDB.
- Corpus coverage cho answerable evaluation:

  `325 / 380 = 0,855263... = 85,53%`.

55 câu trên không được đưa vào macro retrieval evaluation vì hệ thống không thể trả về tài nguyên chưa tồn tại trong index. Việc tính chúng là retrieval miss sẽ làm giảm điểm do corpus chưa hoàn chỉnh, không phản ánh riêng chất lượng thuật toán retrieval.

# 4. Benchmark preparation

## Trình tự đã thực hiện

1. Đọc 400 record từ `../questions_draft.json`.
2. Gán `question_id` theo thứ tự mảng, từ `Q001` đến `Q400`.
3. Tạo file trung gian `evals/benchmark_queries.jsonl`.
4. Mỗi dòng file trung gian chỉ giữ:
   - `question_id`
   - `question`
   - `course_id`
5. Loader benchmark từ chối file query nếu xuất hiện bất kỳ trường ngoài ba trường trên.
6. Baseline và proposed chỉ đọc file query trung gian, không đọc file ground truth trong lúc retrieval.
7. Chỉ sau khi cả quá trình retrieval hoàn tất, scorer mới đọc lại `questions_draft.json` để đối chiếu evidence.

Lệnh đã dùng để tạo query file:

```bash
cd "/Users/VoThiXuanHoa/Documents/RAG project/RAG_DEMO"

"/Users/VoThiXuanHoa/Downloads/rag_test/.venv311/bin/python" \
  -m app.main prepare-retrieval-queries \
  ../questions_draft.json \
  --out evals/benchmark_queries.jsonl
```

## Query lấy từ đâu

`question` và `course_id` được lấy trực tiếp từ từng record trong `questions_draft.json`. Không đưa `required_sources`, `evidence`, `answerable`, `difficulty`, `module_id` hoặc `learning_outcome` vào query file.

## Ground truth được giữ ở đâu

Ground truth vẫn nằm trong `/Users/VoThiXuanHoa/Documents/RAG project/questions_draft.json`, tách khỏi `RAG_DEMO/evals/benchmark_queries.jsonl`. File ground truth chỉ được scorer dùng sau retrieval.

## Lý do tách ground truth khỏi query

Nếu RAG nhận resource đúng, page/slide/timestamp đúng hoặc nhãn answerable trước khi tìm kiếm, hệ thống có thể dùng trực tiếp thông tin đáp án để định hướng retrieval. Điều này gây data leakage và làm metric không còn phản ánh truy vấn thật của sinh viên.

## Kiểm tra tách dữ liệu

- File query có đúng 400 dòng.
- Tập trường quan sát được chỉ là `question_id`, `question`, `course_id`.
- Không tìm thấy các trường `answer`, `answerable`, `evidence`, `required_sources`, `difficulty` trong query file.
- SHA-256 vật lý của `benchmark_queries.jsonl`: `4fea0bbf7733d27cd30321dc2267434750896802786b935ce0c28b516ddde92a`.
- Mã băm canonical query set được runner lưu trong cả hai result file: `9a41a256eea09093429cfdaf3655be58bd25a2335aca4b35793abbb0481d86ff`.

# 5. Systems being compared

## 5.1 Baseline dense text

Cấu hình thực sự đã chạy:

- System ID: `baseline_dense_text`.
- Text embedding: `Qwen/Qwen3-Embedding-0.6B`.
- Collection được tìm: `text_embeddings`.
- `include_visual=false`.
- `hybrid_search=false`, do đó không dùng BM25.
- `rerank_enabled=false`.
- `context_expand=false`.
- `context_compress=false`.
- Lọc `course_id` trực tiếp trong ChromaDB trước khi xếp hạng.
- `retriever_fetch_k=100` trong benchmark.
- Dense candidate request là 500 khi có course filter, sau đó mỗi query group được giới hạn còn 100 candidate trước hợp nhất.
- Final `k=10`.
- Diversity giới hạn tối đa 2 kết quả từ mỗi file (`retrieve_max_per_file=2`).
- Không chạy LLM answer generation.
- Query embedding thêm instruction hiện có trong source trước câu hỏi.
- Một số truy vấn dạng liệt kê được retriever hiện có tách thành nhiều `catalog_subqueries`; đây là rule-based behavior, không phải LLM query enhancement. Nếu có nhiều dense query groups, chúng được hợp nhất bằng RRF.

Thiết bị thực tế: tiến trình baseline chạy trong môi trường không truy cập được MPS; `resolve_device('mps')` fallback về CPU.

## 5.2 Proposed hybrid multimodal

Cấu hình thực sự đã chạy:

- System ID: `proposed_hybrid_multimodal`.
- Dense text embedding: `Qwen/Qwen3-Embedding-0.6B`.
- Lexical retrieval: BM25 từ sidecar `data/bm25.pkl`, dùng package `rank-bm25==0.2.2`.
- Visual query embedding: `Qwen/Qwen3-VL-Embedding-2B`.
- Collections được tìm: `text_embeddings` và `visual_embeddings`.
- `include_visual=true`.
- `hybrid_search=true`.
- Các ranked lists được hợp nhất bằng Reciprocal Rank Fusion, `RRF_K=60`, không có trọng số học được hoặc trọng số thủ công riêng cho từng modality.
- `rerank_enabled=false`; tùy chọn `--rerank` không được truyền khi chạy.
- `context_expand=false`.
- `context_compress=false`.
- Course pre-filter, candidate pool, final K và diversity giống baseline.
- Không chạy LLM answer generation.
- Visual query dùng prompt cố định trong source: `Retrieve relevant e-learning slides, diagrams, and lecture frames for the query.`

Quá trình proposed bị dừng an toàn sau Q011 vì phiên đầu fallback về CPU. Sau đó tiến trình được resume từ Q012 bằng MPS. Vì vậy file kết quả là một lần benchmark logic thống nhất nhưng thời gian của Q001–Q011 và Q012–Q400 được đo trên hai chế độ thiết bị khác nhau.

## Bảng so sánh cấu hình đã chạy

| Thành phần | Baseline | Proposed |
|---|---|---|
| System ID | `baseline_dense_text` | `proposed_hybrid_multimodal` |
| Query input | `question`, `course_id` | Giống baseline |
| Dense text model | `Qwen/Qwen3-Embedding-0.6B` | `Qwen/Qwen3-Embedding-0.6B` |
| Text collection | Có | Có |
| BM25 | Không | Có, `rank-bm25==0.2.2` |
| Visual model | Không dùng | `Qwen/Qwen3-VL-Embedding-2B` |
| Visual collection | Không | Có |
| Fusion | RRF khi có nhiều rule-based dense query groups | RRF cho các ranked lists, `RRF_K=60` |
| Learned/manual hybrid weights | Không | Không; dùng RRF không trọng số |
| Reranker | Tắt | Tắt |
| Context expansion | Tắt | Tắt |
| Context compression | Tắt | Tắt |
| Course pre-filter | Có | Có |
| `retriever_fetch_k` | 100 | 100 |
| Final Top-K | 10 | 10 |
| Max results/file | 2 | 2 |
| LLM generation | Không chạy | Không chạy |
| Model revision/commit | `[CHƯA XÁC NHẬN]` | `[CHƯA XÁC NHẬN]` |
| Inference dtype | `[CHƯA XÁC NHẬN]` | `[CHƯA XÁC NHẬN]` |
| Thiết bị của lần chạy | CPU | Q001–Q011 CPU; Q012–Q400 MPS |

# 6. Retrieval experiment procedure

Luồng thực nghiệm thực tế:

```text
questions_draft.json
        │
        ├─ lấy question + course_id, gán Q001–Q400
        ▼
benchmark_queries.jsonl
        │
        ├─ chạy baseline với Top-10
        ├─ chạy proposed với Top-10
        ▼
raw retrieval results JSONL
        │
        ├─ sau retrieval mới đọc evidence từ questions_draft.json
        ├─ đối chiếu resource + locator
        ▼
Precision@K / Recall@K / F1@K, K ∈ {1, 5, 10}
        │
        ▼
macro average trên 325 câu answerable hợp lệ
```

## Baseline command

```bash
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 DEVICE=mps \
caffeinate -is \
"/Users/VoThiXuanHoa/Downloads/rag_test/.venv311/bin/python" \
  -m app.main benchmark-retrieve \
  evals/benchmark_queries.jsonl \
  --system-id baseline_dense_text \
  --profile baseline \
  -k 10 \
  --out evals/results/baseline_retrieval_results.jsonl
```

Mặc dù command yêu cầu `DEVICE=mps`, môi trường chạy baseline báo MPS không available nên source tự fallback về CPU.

## Proposed commands

Lần đầu chạy proposed đã ghi Q001–Q011 rồi được dừng. Sau đó dùng cùng system ID và cùng output file với `--resume`:

```bash
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 DEVICE=mps \
VL_BATCH_SIZE=1 LOG_LEVEL=WARNING \
caffeinate -is \
"/Users/VoThiXuanHoa/Downloads/rag_test/.venv311/bin/python" \
  -m app.main benchmark-retrieve \
  evals/benchmark_queries.jsonl \
  --system-id proposed_hybrid_multimodal \
  --profile proposed \
  -k 10 \
  --out evals/results/proposed_retrieval_results.jsonl \
  --resume
```

## Raw result schema

Mỗi dòng result JSONL chứa:

- `question_id`
- `system_id`
- `query_set_sha256`
- `question`
- `course_id`
- `top_k`
- `elapsed_ms`
- `results`

Mỗi phần tử trong `results` chứa:

- `question_id`
- `rank`
- `resource_id`
- `resource_type`
- `content_type`
- `chunk_id`
- `object_id`
- `page`
- `slide`
- `start_time`
- `end_time`
- `retrieval_score`
- `cosine_score`

Kết quả thực tế:

- Baseline: 400 dòng, 400 ID duy nhất, 0 lỗi. Có 349 câu trả đúng 10 result; các câu còn lại trả ít hơn do course filtering và giới hạn tối đa 2 result/file. Có 7 câu trả 0 result.
- Proposed: 400 dòng, 400 ID duy nhất, 0 lỗi. Có 399 câu trả 10 result và 1 câu trả 8 result.
- Precision luôn dùng mẫu số K cố định, kể cả khi hệ thống trả ít hơn K kết quả.

# 7. Metric definitions

Với câu hỏi `q`, tại cutoff `K`:

```text
Precision@K(q) = số retrieved results relevant trong Top-K / K
```

```text
Recall@K(q) = số ground-truth evidence riêng biệt được match trong Top-K
              / tổng số ground-truth evidence của q
```

```text
F1@K(q) = 2 × Precision@K(q) × Recall@K(q)
           / (Precision@K(q) + Recall@K(q))
```

Nếu Precision và Recall cùng bằng 0 thì F1 được đặt bằng 0.

Macro average của một metric tại K là trung bình cộng metric đó trên các câu answerable hợp lệ được chấm.

## Cách xác định retrieved result relevant

Một result relevant khi:

1. `resource_id` sau chuẩn hóa trùng với `resource_id` của evidence; và
2. Nếu evidence có `page`, page phải bằng chính xác; và
3. Nếu evidence có `slide`, slide phải bằng chính xác; và
4. Nếu evidence có `timestamp`, khoảng `[start_time, end_time]` của result phải giao với khoảng timestamp của evidence.

Nếu evidence không có page, slide hoặc timestamp thì resource match là đủ.

Chuẩn hóa resource ID đã thực hiện:

- Chuẩn hóa Unicode NFC.
- Đổi `\` thành `/`.
- Chuẩn hóa đường dẫn bắt đầu bằng `assets/` thành `RAG_DEMO/assets/`.

Một retrieved result match bất kỳ evidence nào được tính là relevant cho Precision. Nếu nhiều chunks cùng match một evidence thì từng result vẫn được tính trong tử số Precision; đối với Recall, evidence đó chỉ được tính một lần nhờ tập evidence index riêng biệt.

## Relevant ground truth

Ground-truth relevant set là toàn bộ các evidence entries của câu hỏi. Recall đo số evidence entries riêng biệt được retrieve, không chỉ số resource duy nhất.

## Population dùng cho macro average

Macro được tính trên **325 câu answerable** có evidence và có toàn bộ ground-truth resources xuất hiện trong ChromaDB.

Không tính vào macro:

- 20 câu suy ra unanswerable vì evidence rỗng.
- 55 câu answerable có ít nhất một ground-truth resource chưa index.

# 8. Evaluation population

Phép tính đã kiểm tra:

```text
400 total questions
  − 20 inferred unanswerable questions
= 380 answerable questions
  − 55 answerable questions with unindexed ground-truth resources
= 325 valid answerable questions
```

Do đó:

- Retrieval macro metrics được tính trên 325 câu.
- 20 câu unanswerable được báo riêng.
- 55 câu answerable không được coi là retrieval failure trong macro hiện tại.
- Corpus coverage: `325 / 380 = 85,53%`.

# 9. Experiment outputs

| File | Vai trò | Nội dung |
|---|---|---|
| `evals/benchmark_queries.jsonl` | Input của cả hai retrieval runs | 400 dòng chỉ gồm ID, question và course context; không có ground truth |
| `evals/results/baseline_retrieval_results.jsonl` | Raw baseline output | Top-10 hoặc tối đa 10 results cho từng câu |
| `evals/results/baseline_retrieval_metrics.json` | Baseline evaluation | Macro metrics, per-question metrics, corpus coverage và danh sách excluded |
| `evals/results/proposed_retrieval_results.jsonl` | Raw proposed output | Top-10 hoặc tối đa 10 results cho từng câu |
| `evals/results/proposed_retrieval_metrics.json` | Proposed evaluation | Macro metrics, per-question metrics, corpus coverage và danh sách excluded |

SHA-256 tại thời điểm ghi log:

| File | SHA-256 |
|---|---|
| `benchmark_queries.jsonl` | `4fea0bbf7733d27cd30321dc2267434750896802786b935ce0c28b516ddde92a` |
| `baseline_retrieval_results.jsonl` | `eb1b7e8e101d44ad072d608f9ad85102968e44df2ebc2dfd37010ccd03d9eedd` |
| `baseline_retrieval_metrics.json` | `f9815c57b66158ccd4c3847b752ff2701319118f10205cba83ff3ada84ba09eb` |
| `proposed_retrieval_results.jsonl` | `641497f345db273cf33bab487cb697c4936a30f18941c0bb18054b5abe10d798` |
| `proposed_retrieval_metrics.json` | `cc73efd5263592446d5c9cd1a74b3c30670aa809f9a0d9cf1138acea2771b478` |

# 10. Current retrieval results

Macro average trên 325 câu answerable hợp lệ:

| Hệ thống | P@1 | R@1 | F1@1 | P@5 | R@5 | F1@5 | P@10 | R@10 | F1@10 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Baseline dense text | 0,187692 | 0,146154 | 0,158872 | 0,070769 | 0,284103 | 0,110818 | 0,048615 | 0,332308 | 0,082816 |
| Proposed hybrid multimodal | 0,190769 | 0,162821 | 0,171487 | 0,059692 | 0,246154 | 0,094078 | 0,045846 | 0,344615 | 0,079336 |

Đây là kết quả dự thảo trên corpus coverage 85,53%, không phải kết luận cuối cùng.

# 11. Preliminary observations

Các quan sát trực tiếp từ bảng số liệu:

- Proposed cao hơn baseline tại Precision@1, Recall@1 và F1@1.
- Proposed cao hơn baseline tại Recall@10.
- Baseline cao hơn proposed tại Precision@5, Recall@5 và F1@5.
- Baseline cao hơn proposed tại Precision@10 và F1@10.
- Các metric chưa cho thấy proposed tốt hơn baseline một cách nhất quán trên mọi K.
- Chưa có kiểm định thống kê hoặc confidence interval, nên chưa thể kết luận chênh lệch có ý nghĩa thống kê.
- Không được dùng thời gian ghi trong hai result files để kết luận hệ thống nào nhanh hơn vì hai runs không dùng cùng điều kiện phần cứng.

# 12. Validation

Các kiểm tra đã thực hiện:

- Cả baseline và proposed dùng cùng file `benchmark_queries.jsonl` gồm 400 câu.
- Cả hai raw result files có cùng canonical query hash:
  `9a41a256eea09093429cfdaf3655be58bd25a2335aca4b35793abbb0481d86ff`.
- Mỗi result file có 400 dòng và 400 `question_id` duy nhất.
- Không có retrieval error trong 400 câu của mỗi hệ thống.
- Query loader chỉ chấp nhận ba trường và từ chối ground-truth fields.
- Ground truth chỉ được đọc trong scoring stage sau retrieval.
- Cả hai hệ thống dùng cùng:
  - course pre-filter;
  - K = 10 cho raw retrieval;
  - candidate fetch setting;
  - giới hạn 2 result/file;
  - tắt context expansion;
  - tắt context compression;
  - tắt reranker.
- Proposed ban đầu cảnh báo thiếu `rank-bm25`; package `rank-bm25==0.2.2` đã được cài và smoke test lại trước khi chạy full proposed benchmark. Smoke run thiếu BM25 không nằm trong result file cuối.
- 16 automated tests liên quan benchmark và evaluation đã chạy thành công.
- Model loading được chạy với `HF_HUB_OFFLINE=1` và `TRANSFORMERS_OFFLINE=1` để dùng model cache local, tránh thay đổi model do tải lại giữa hai runs.

Môi trường Python đã xác nhận:

| Thành phần | Phiên bản |
|---|---|
| Python | 3.11.15 |
| PyTorch | 2.14.0 |
| Transformers | 5.16.1 |
| Sentence Transformers | 6.0.1 |
| ChromaDB | 1.5.9 |
| rank-bm25 | 0.2.2 |
| pytest | 9.1.1 |
| langchain-huggingface | 1.2.2 |

# 13. Known limitations

- 18 ground-truth resources được tham chiếu trong evidence chưa được index.
- 55 answerable questions bị loại khỏi macro retrieval evaluation vì phụ thuộc các resource trên.
- Corpus coverage của answerable set hiện chỉ là 85,53%.
- Tổng cộng có 25/65 file local chưa xuất hiện trong ChromaDB, dù chỉ 18 file trong số đó ảnh hưởng trực tiếp đến ground truth hiện tại.
- 20 câu unanswerable không có nhãn `answerable=false` trực tiếp; chúng được suy ra từ `answerable=null` và evidence rỗng.
- Retrieval system luôn cố trả kết quả, chưa sinh quyết định `abstained`; vì vậy rejection/abstention accuracy chưa được tính.
- `retrieval_precision_recall_f1` của unanswerable được để `null`, tránh Recall chia cho 0 khi relevant set rỗng.
- Đây là retrieval evaluation, không phải end-to-end answer evaluation.
- Chưa đánh giá tính đúng của câu trả lời, faithfulness, chất lượng citation hoặc khả năng tổng hợp đa nguồn của LLM.
- Trường `category` không tồn tại trong dataset hiện tại; phân bố thực tế theo tám loại câu hỏi chưa được xác nhận.
- Trạng thái human review độc lập cho toàn bộ evidence: `[CHƯA XÁC NHẬN]`.
- Baseline chạy CPU; proposed chạy 11 câu đầu trên CPU và 389 câu còn lại trên MPS. Vì vậy latency giữa hai system không thể so sánh công bằng.
- Do giới hạn đa dạng tối đa 2 result/file, một số câu baseline trả ít hơn 10 kết quả. Precision vẫn chia cho K cố định.
- `retrieval_score` không nhất thiết cùng thang đo giữa mọi result: có thể là cosine-derived score hoặc RRF score tùy số ranked lists được hợp nhất. Không so sánh trực tiếp raw score giữa hai systems.
- Mã benchmark/evaluation đang là thay đổi chưa commit trên working tree tại thời điểm viết log. Git `HEAD` là `7797d67bf45e32ca370f9de09ea26ac17108a283`, nhưng commit này không chứa toàn bộ mã vừa dùng để chạy benchmark.

# 14. Experiments NOT YET DONE

Các thí nghiệm sau chưa được thực hiện:

- Ingest 25 tài nguyên còn thiếu và chạy lại cả baseline lẫn proposed trên corpus đầy đủ.
- End-to-end answer generation evaluation.
- Đánh giá answer correctness.
- Đánh giá faithfulness/groundedness.
- Đánh giá citation correctness và citation completeness.
- Rejection/abstention evaluation cho 20 câu unanswerable.
- BM25-only ablation.
- Dense-only versus dense+BM25 ablation dưới cùng proposed pipeline.
- Text+visual không BM25 ablation.
- Visual-only ablation.
- Reranker experiment; reranker đã tắt trong hai runs hiện tại.
- Context expansion/compression ablation.
- Course pre-filter ablation.
- RRF parameter/weight ablation.
- Per-course metric breakdown.
- Per-category metric breakdown; dataset hiện thiếu category label.
- Phân tích lỗi định tính theo extraction, retrieval, visual understanding và metadata.
- Latency benchmark công bằng trên cùng thiết bị, cùng warm-up và cùng số lần lặp.
- Memory, energy hoặc monetary cost comparison.
- Confidence interval, bootstrap hoặc significance test cho chênh lệch metric.
- Independent human adjudication cho toàn bộ ground truth.

# 15. Missing information required for final report

Checklist thông tin cần bổ sung hoặc xác nhận trước báo cáo cuối:

- [ ] Commit hoặc tag chứa đúng toàn bộ mã đã dùng cho benchmark.
- [ ] Snapshot/checksum của ChromaDB và BM25 sidecar dùng cho lần chạy.
- [ ] Ingest đầy đủ 25 file còn thiếu, hoặc chốt rõ phạm vi corpus chính thức.
- [ ] Xác nhận độc lập 18 missing ground-truth resources sau khi ingest.
- [ ] Model revision/commit hash chính xác của `Qwen/Qwen3-Embedding-0.6B`.
- [ ] Model revision/commit hash chính xác của `Qwen/Qwen3-VL-Embedding-2B`.
- [ ] Dtype thực tế của từng embedding model.
- [ ] Exact Mac model, chip, RAM và phiên bản macOS.
- [ ] Điều kiện thiết bị thống nhất cho benchmark latency.
- [ ] Full dependency lock hoặc `pip freeze` của môi trường chạy.
- [ ] Cấu hình HNSW/ANN chi tiết và random seed, nếu có.
- [ ] Xác nhận chunk size/overlap thực tế đã dùng cho từng resource đang nằm trong ChromaDB; source hiện có default nhưng index được tạo qua nhiều phiên.
- [ ] Model, version và tham số Whisper/MLX Whisper đã dùng để tạo từng timestamp sidecar.
- [ ] Quy tắc chọn video frames thực tế cho từng video đã index.
- [ ] Xác nhận tất cả page/slide/timestamp ground truth sau human review.
- [ ] Thêm hoặc phục hồi trường `category` nếu cần báo cáo kết quả theo tám nhóm câu hỏi.
- [ ] Xác nhận learning outcome và module mapping cho các record có giá trị null.
- [ ] Chốt protocol cho câu có nhiều evidence: yêu cầu retrieve tất cả hay ít nhất một evidence để coi câu trả lời đủ.
- [ ] Chốt protocol đánh giá unanswerable và định nghĩa trường `abstained`.
- [ ] Chốt metric cho answer correctness, faithfulness và citation.
- [ ] Chốt số lần chạy, warm-up và cách báo cáo latency variance.
- [ ] Thực hiện error analysis và ghi lại taxonomy lỗi.
- [ ] Thực hiện kiểm định thống kê trước khi viết kết luận so sánh hệ thống.

# 16. Bổ sung 2026-09-30: reset corpus, bộ câu hỏi v7, và bug reranker

> Trạng thái: nhật ký thực nghiệm dự thảo tiếp theo phần 1-15, cùng quy ước `[CHƯA XÁC NHẬN]`.

## 16.1 Reset toàn bộ index và ingest lại từ đầu

Theo yêu cầu người dùng, đã xoá sạch `data/chroma`, `data/index_manifest.json`, `data/bm25.pkl`, `storage/`, `evals/results/`, `evals/reports/*` và ingest lại toàn bộ `assets/` (15GB, 30 video, 3 môn: `cau_truc_du_lieu_va_giai_thuat`, `cau_truc_roi_rac`, `nhap_mon_lap_trinh`).

Trong lúc ingest phát hiện và sửa 3 lỗi trong code (không chỉ do môi trường):

1. **Whisper transcribe sai ngôn ngữ**: `faster-whisper` tự nhận diện ngôn ngữ trên video bài giảng tiếng Việt ra `en` với độ tin cậy 38%. Đã thêm `WHISPER_LANGUAGE=vi` (mặc định `vi`) vào `Settings` và ép cứng trong `VideoLoader._transcribe()`.
2. **Model ảnh (Qwen3-VL-Embedding) load lỗi giữa chừng do mạng chập chờn** ngay sau khi máy thức dậy từ sleep, làm mất toàn bộ `video_frame` của video đang xử lý (exception bị nuốt, chỉ còn `text`). Chuyển sang chạy `HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1` sau khi mọi model cần thiết đã cache sẵn.
3. **`HF_HUB_OFFLINE=1` xung đột với `HF_TOKEN`**: `app/factory.py::login_hub()` gọi `huggingface_hub.login()` (cần mạng để xác thực `whoami-v2`) bất kể chế độ offline, làm crash `build_services()`. Đã sửa: bỏ qua bước login khi `huggingface_hub.constants.HF_HUB_OFFLINE` bật.
4. **`VideoCheckpoint.update(stage=...)` ghi đè lùi stage**: mỗi lần resume, bước audio-extraction xong sẽ tự hạ `stage` về `"audio"` kể cả khi checkpoint đã ở `"indexed"`, khiến `checkpoint.reached("transcript")` luôn `False` và pipeline transcribe lại từ đầu dù transcript đã có sẵn. Đã sửa: `stage` chỉ được phép tiến, không được phép lùi (`app/processors/video_checkpoint.py`).

Cũng nâng `WHISPER_MODEL` từ `base` lên `small` (transcript rõ ràng hơn hẳn, tốc độ đo được không chậm hơn đáng kể trên máy này) và bật đồng thời `HYBRID_SEARCH`, `RERANK_ENABLED`, `CONTEXT_EXPAND`, `CONTEXT_COMPRESS`, `QUERY_HYDE`, `MAX_RETRIEVE_LOOPS=1`, `RETRIEVER_FETCH_K=40` trong `.env` để đo toàn bộ kỹ thuật retrieval sẵn có trong repo.

Kết quả ingest cuối cùng: 69 file trên đĩa (30 mp4, 21 pdf, 7 pptx, 7 ppt, 4 docx), 62 file được hỗ trợ lúc bắt đầu + 7 `.ppt` thêm sau (mục 16.2) = 69/69 **đã index, 0 lỗi**. 15.682 vector text (text=5.782, table=97, page=582, video_segment=9.803) + 12.793 vector ảnh (image=1.297, video_frame=10.914).

Trong lúc ingest, máy bị hệ điều hành đưa vào sleep nhiều lần (gập nắp, và có lúc chạy bằng pin khiến `caffeinate -s` — vốn chỉ hiệu lực khi cắm sạc AC — không ngăn được sleep). Nhờ fix #4 ở trên, quá trình resume sau mỗi lần sleep không mất tiến độ đã hoàn thành, chỉ kéo dài thêm đúng bằng thời gian máy ngủ.

## 16.2 Bộ câu hỏi `questions_draft_v7.json` (400 câu) và khoảng trống corpus

Người dùng cung cấp `questions_draft_v7.json` (gốc repo, chưa commit) — cùng dạng với `questions_draft.json` ở phần 1-15 nhưng có thêm trường `category` (4 nhóm cân bằng 100 câu: `video_grounded`, `slide_grounded`, `visual`, `cross_source`) và `difficulty` (`easy` 76, `medium` 296, `hard` 28). `answerable` luôn `true` (400/400) — bộ này **không có câu unanswerable**. Không có trường `answer`/`ground_truth`.

Kiểm tra 57 `resource_id` duy nhất trong `evidence` (552 evidence item) đối chiếu `assets/` trên đĩa:

- 34/57 khớp chính xác (toàn bộ 30 file video).
- 15/57 lệch chính tả (resource_id bị "slugify" bỏ dấu/khoảng trắng, ví dụ `Chuong_1_Co_so_logic_slides_bai_tap.pdf` so với file thật `Chuong 1. Cơ sở logic (slides + bài tập).pdf`) — file thật tồn tại, chỉ là tên gọi khác.
- 7/57 là 7 file `.ppt` (môn `cau_truc_du_lieu_va_giai_thuat`) — **chưa từng được ingest** vì Docling không đọc `.ppt`.
- 1/57 mơ hồ (`.../buoi_5/Chuong_5_Ly_thuyet_do_thi_phan_2.pptx` — tên trong JSON là diễn giải ngắn, không khớp trực tiếp file nào). Đã xác minh bằng cách đọc nội dung slide thật của cả 2 file "(phần 1)" và "(phần 2)": 17 câu hỏi liên quan đều hỏi về Euler/Hamilton/Dijkstra, khớp đúng nội dung "(phần 2)".

Tác động định lượng nếu không sửa: 138/400 câu (194/552 evidence) bị chấm sai thành "không tìm thấy" dù tài liệu đã index (do lệch chính tả); 96/400 câu (146/552 evidence) phụ thuộc hoàn toàn vào 7 file `.ppt` chưa index.

**Đã xử lý cả hai:**

- Cài LibreOffice (`brew install --cask libreoffice`), dùng `app/processors/office_convert.py` (đã viết sẵn trong phiên trước) chuyển `.ppt`→`.pptx` tạm thời chỉ để Docling parse; `relative_path`/`file_type` lưu trong Chroma vẫn là `.ppt` gốc (xác nhận bằng code: `DoclingLoader._load_parsed()` build `DocumentAsset` từ `path` gốc, không phải file đã convert). Ingest cả 7 file, 0 lỗi. 2/7 file có ảnh nhúng được trích ra được, 5/7 chỉ có text (bản thân slide gốc không có ảnh nhúng, không phải lỗi convert — đã xác minh Docling không tạo page-render cho PPTX dù `.ppt` hay `.pptx` gốc, ảnh chỉ đến từ *picture* nhúng).
- Tạo `evals/resource_id_aliases.json` (23 cặp `slug → tên thật`, tĩnh, đã review thủ công) và thêm `resolve_evidence_resource_id()` vào `app/eval/retrieval_benchmark.py`, áp dụng riêng cho phía evidence khi chấm điểm.

Sau khi áp dụng cả hai: chấm điểm 400 câu cho `corpus_coverage=1.0000` (400/400 đã index) — không còn câu nào bị loại vì thiếu nguồn.

## 16.3 Bug reranker: prompt sai định dạng khiến rerank làm giảm chất lượng

Benchmark đầu tiên với `RERANK_ENABLED=true` (đã bật sẵn trong `.env`) cho kết quả **tệ hơn rõ rệt** so với baseline dense-only, kể cả so với hybrid không rerank:

| Hệ thống | precision@1 | f1@1 | f1@5 | recall@10 | f1@10 |
|---|---:|---:|---:|---:|---:|
| baseline (dense-only) | 0,3075 | 0,2528 | 0,1341 | 0,3515 | 0,0916 |
| hybrid+visual, không rerank | 0,2425 | 0,1974 | 0,1304 | 0,3517 | 0,0854 |
| hybrid+visual+rerank (**bug**) | 0,1000 | 0,0783 | 0,0973 | 0,2690 | 0,0709 |

So sánh 2 dòng đầu cho thấy hybrid/visual một mình chỉ làm giảm nhẹ. Rerank mới là nguyên nhân chính, và đáng chú ý là **recall@10 cũng giảm** — bất thường vì rerank chỉ nên xếp lại thứ tự trong cùng tập candidate, không giảm recall trừ khi nó đẩy kết quả đúng ra khỏi top-10 trước bước `diversify_by_file`.

**Nguyên nhân xác nhận**: `Qwen/Qwen3-Reranker-0.6B` có `tokenizer.chat_template` bắt buộc — bọc câu hỏi/tài liệu trong system prompt cố định (`"Judge whether the Document meets the requirements..."`) và primer `<|im_start|>assistant\n<think>\n\n</think>\n\n` để bỏ qua chế độ suy nghĩ, buộc token tiếp theo là "yes"/"no". `app/retrieval/reranker.py::QwenReranker._scores()` trước đó tokenize một chuỗi thô `"<Instruct>: ...\n<Query>: ...\n<Document>: ..."` **không qua chat template** — model không ở đúng trạng thái đã huấn luyện để trả lời yes/no ngay, nên logit lấy ra ở vị trí token cuối gần như là nhiễu.

Xác minh bằng test thủ công (trước/sau fix, cùng 1 câu hỏi + 3 tài liệu, 1 đúng + 2 sai chủ đề): điểm relevant/irrelevant từ phân bố gần như ngẫu nhiên trở thành **0,9967 vs 0,0039 / 0,0003** sau khi áp dụng đúng chat template.

**Đã sửa**: `_scores()` giờ dùng `tokenizer.apply_chat_template()` với message `role="system"/"query"/"document"` đúng như template yêu cầu, thay vì tokenize chuỗi thô.

Chạy lại benchmark 400 câu với reranker đã sửa:

| Hệ thống | precision@1 | f1@1 | f1@5 | recall@10 | f1@10 |
|---|---:|---:|---:|---:|---:|
| baseline (dense-only) | 0,3075 | 0,2528 | 0,1341 | 0,3515 | 0,0916 |
| hybrid+visual+rerank (**đã sửa**) | 0,3200 | 0,2670 | 0,1887 | 0,4671 | 0,1121 |

Reranker đã sửa vượt baseline trên mọi chỉ số đo được — recall@10 tăng 32,9%, f1@10 tăng 22,4%, f1@5 tăng 40,7% (tương đối). Đây là bằng chứng thực nghiệm đầu tiên trong repo cho thấy rerank thực sự có ích, *với điều kiện* dùng đúng chat template của model.

Phân rã theo category (hybrid+rerank đã sửa, f1@10): `cross_source`=0,1839, `slide_grounded`=0,1388, `visual`=0,0797, `video_grounded`=0,0461 — `video_grounded` yếu nhất trong mọi cấu hình đã đo, kể cả sau khi sửa rerank, đáng để điều tra riêng (có thể do transcript window 30s quá thô, hoặc do câu hỏi video đòi hỏi mốc thời gian chính xác hơn path-level match cho phép).

## 16.4 Hạn chế / việc chưa làm ở phần này

- Chưa chạy biến thể `full-pipeline` (bật cả HyDE + iterative-loop qua `GenerationService.retrieve_for_eval()`, đã code ở `app/eval/retrieval_benchmark.py::run_retrieval(retrieve_fn=...)` và cờ `--use-generation-pipeline`) — người dùng chọn bỏ qua để tiết kiệm thời gian (~7-9h), ưu tiên hybrid+rerank + generation pass.
- Generation-level pass (faithfulness/answer_relevancy/citation-accuracy qua `evals/golden_v7.jsonl` và judge tham chiếu-tự-do) chưa chạy tại thời điểm ghi log này — xem file kết quả `evals/reports/v7_generation.json` nếu đã có.
- Chưa kiểm định thống kê cho chênh lệch baseline vs hybrid+rerank (đã sửa) — dù chênh lệch lớn và nhất quán trên mọi K, vẫn nên có bootstrap/CI trước khi viết kết luận chính thức.
- Bug reranker ở mục 16.3 có khả năng cũng ảnh hưởng đến bất kỳ lần chạy nào trước đây trong repo có bật `RERANK_ENABLED=true` — không có ghi nhận nào khác trong log trước đó cho thấy rerank từng được bật khi benchmark, nên nhiều khả năng đây là lần đầu bug này được kích hoạt và phát hiện.

## 16.5 Generation-level pass: bug judge + kết quả cuối

Chạy `python -m app.main eval evals/golden_v7.jsonl --text-only --rerank` (cấu hình tốt nhất đã xác nhận ở 16.3: hybrid+rerank đã sửa) trên toàn bộ 400 câu, dùng `GenerationService` thật (enhance + HyDE + retrieve + rerank + Qwen3-1.7B sinh câu trả lời), sau đó chấm bằng chính Qwen3-1.7B làm giám khảo tham chiếu-tự-do (không có `ground_truth`, xem mục Phase 4 trong plan).

**Bug thứ 3 phát hiện**: `app/eval/judge.py::score_with_judge()` và `score_reference_free()` gọi `chat.invoke({"question": payload, "judge": True})` — truyền **dict thô** cho `ChatHuggingFace.invoke()`, nhưng API LangChain chỉ nhận `str | PromptValue | list[BaseMessage]`. Toàn bộ 400/400 lệnh judge thất bại với `ValueError: Invalid input type <class 'dict'>` (bị try/except nuốt, chỉ log exception, nên cả lượt chạy 400 câu ~5,7 giờ vẫn "hoàn tất" nhưng `faithfulness`/`answer_relevancy` đều `None`). Đây là bug có từ trước, không phải do thay đổi hôm nay — dict-payload chỉ hoạt động với chat model giả lập trong test (`FakeChat.invoke()` bỏ qua nội dung tham số), chưa từng được xác minh với model thật trước phiên này.

**Đã sửa**: đổi thành `chat.invoke(payload)` (truyền thẳng chuỗi prompt đã format). Xác minh bằng test thủ công với model thật trước khi áp dụng lại (điểm ra `faithfulness=1.0, answer_relevancy=1.0` cho 1 câu trả lời rõ ràng đúng và bám ngữ cảnh).

Vì câu trả lời của LLM (400/400) đã sinh đúng ở lượt chạy đầu (không phụ thuộc đường code bị lỗi), không cần chạy lại toàn bộ — chỉ chấm lại judge trên `answer`/`contexts` đã lưu, mất **18,7 phút** thay vì ~5,7 giờ.

**Bug thứ 4 (nhỏ)**: `app/eval/runner.py::_run_one()` không copy `difficulty` từ `item.extra` vào `trace`, khiến `by_difficulty` trong báo cáo gộp hết vào nhãn `"unknown"`. Đã sửa `_run_one()` và vá lại báo cáo đã có bằng cách join `difficulty` từ `evals/golden_v7.jsonl` theo `id` (không cần chạy lại).

### Kết quả cuối — generation-level, 400/400 câu, cấu hình hybrid+rerank (đã sửa) + text-only

```
path_recall=0.946       path_precision=0.161
path_recall_at_1=0.523  path_recall_at_5=0.913  path_recall_at_10=0.946
faithfulness=0.504      answer_relevancy=0.501
citation_precision=0.085 (mean)   citation_recall=0.468 (mean)
weakest_metric=answer_relevancy   next_step=query enhance / generation prompt
```

`citation_precision`/`citation_recall` đo độ chính xác của **tập hit truy xuất được đưa vào ngữ cảnh cho LLM** (so với `evidence` thật, dùng lại đúng hàm `metrics_at_k`/alias đã sửa ở 16.3) — không phải phân tích chuỗi trích dẫn trong văn bản câu trả lời. Khớp hợp lý với `path_recall_at_10=0,946` (path-level, chỉ cần đúng file) và với recall@10 đo được ở benchmark retrieval thuần (0,467, đo ở page/slide/timestamp-level chính xác hơn) — `citation_recall=0,468` nằm giữa hai số này, đúng như kỳ vọng vì độ chặt matching khác nhau.

**Phân bố `faithfulness`/`answer_relevancy` gần như nhị phân**: 201/399 câu = 1,0, 198/399 câu = 0,0, gần như không có giá trị trung gian. Đây là dấu hiệu Qwen3-1.7B (1.7B tham số) làm giám khảo có xu hướng chấm cực đoan (toàn đúng/toàn sai) thay vì chấm theo thang liên tục 0-1 như prompt yêu cầu — hạn chế đã biết khi dùng model nhỏ tự chấm, cần đọc `faithfulness=0,504` là "một nửa số câu được chấm hoàn toàn đạt, nửa còn lại hoàn toàn không đạt", không phải "mỗi câu đạt một nửa".

Phân rã theo category (`path_recall@10` / ghi chú: category không có faithfulness/answer_relevancy riêng trong báo cáo hiện tại):

| category | n | path_recall@1 | path_recall@5 | path_recall@10 | path_precision |
|---|---:|---:|---:|---:|---:|
| video_grounded | 100 | 0,25 | 0,71 | 0,82 | 0,107 |
| slide_grounded | 100 | 0,79 | 0,99 | 1,00 | 0,135 |
| visual | 100 | 0,62 | 0,99 | 0,99 | 0,135 |
| cross_source | 100 | 0,43 | 0,96 | 0,975 | 0,267 |

`video_grounded` yếu nhất ở mọi K, nhất quán với kết quả retrieval-only ở 16.3 — đáng điều tra riêng (transcript window 30s có thể quá thô, hoặc câu hỏi video đòi hỏi mốc thời gian chính xác hơn path-level cho phép đo được ở đây).

Phân rã theo difficulty:

| difficulty | n | path_recall@1 | path_recall@5 | path_recall@10 | path_precision |
|---|---:|---:|---:|---:|---:|
| easy | 76 | 0,566 | 0,934 | 0,947 | 0,129 |
| medium | 296 | 0,484 | 0,899 | 0,941 | 0,172 |
| hard | 28 | 0,821 | 1,00 | 1,00 | 0,129 |

Đáng chú ý: nhóm `hard` (28 câu, n nhỏ) lại có path_recall cao nhất — có thể do cỡ mẫu nhỏ, hoặc do câu "khó" thường tham chiếu rõ ràng một nguồn cụ thể hơn là câu "dễ" mang tính khái quát — cần thêm dữ liệu trước khi kết luận.

### Việc chưa làm / hạn chế còn lại của phần 16

- `context_precision`/`context_recall` không đo được cho bộ v7 (không có `ground_truth` tham chiếu) — chỉ có ở `evals/golden.jsonl` cũ.
- Chưa chạy generation-level cho biến thể `full-pipeline` (HyDE+loop qua `retrieve_for_eval`) hay biến thể `--with-visual` (bị hệ thống dừng giữa chừng do thiếu RAM, xem log `logs/eval_v7_generation_20260930*.log` đầu tiên — không phải lỗi code).
- Chưa kiểm định thống kê cho mọi so sánh ở mục 16.
- File báo cáo đầy đủ: `evals/reports/v7_generation.json`; file gốc trước khi vá judge: `evals/reports/v7_generation.backup_prejudgefix.json` (giữ lại để đối chiếu, có thể xoá).
- Chưa đo K=20 cho retrieval (chỉ có @1/@5/@10) — dựa vào recall@5→recall@10 gần như bão hoà (+0,012 cho hybrid+rerank đã sửa), nhiều khả năng recall@20 không tăng nhiều, nhưng chưa có số đo thật.

