# Bộ dữ liệu đánh giá dự thảo

Thư mục này là sản phẩm trung gian cho bộ 200 câu hỏi đánh giá RAG đa phương thức.

- resource_inventory.json: danh mục 48 học liệu gốc, số trang/slide/đoạn timestamp và ID quản lý.
- evaluation_matrix.json: ma trận phân bổ 8 nhóm, trạng thái dữ liệu và các khoảng trống cần kiểm tra.
- batch_01.jsonl: 20 record đầu tiên, ID Q001–Q020.
- assets_inventory.json, chroma_inventory.json: báo cáo máy sinh tự động về file và snapshot Chroma tại thời điểm tạo batch 01.

Các record trong batch_01.jsonl là bản nháp. review_status luôn là pending_human_review; chưa được xem là ground truth. Khi chạy hệ thống, chỉ đưa question và query_context vào hệ thống, giữ draft_answer và evidence_groups riêng để chấm.

Phạm vi hiện tại chỉ gồm hai môn trong assets/: Cấu trúc rời rạc và Nhập môn Lập trình. Các resource ID được tạo cho việc quản lý bộ đánh giá, không phải ID đã có sẵn trong Chroma. Quyền sử dụng học liệu vẫn cần người sở hữu xác nhận.
