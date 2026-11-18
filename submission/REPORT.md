# Báo cáo Day 09 — Nguyễn Viết Minh, 2A202604043

> Xoá mọi `TODO(học viên)` và dòng gợi ý. Mỗi ý trả lời bằng **số lấy từ `submission/reports/`**, kèm mẫu số. Cả báo cáo ~1–2 trang.

## 1. Kết luận trước
TODO(học viên): pipeline kết luận **Release / Hold / Rework**? Bao nhiêu ảnh vào, bao nhiêu ảnh ra dataset? Lý do chính (1–3 câu).

## 2. Lỗi và phân việc
Lấy từ `02_error_list_v1` (gom theo mã lỗi). Cột "ai sửa": **máy** (autofix) hay **người** (hàng đợi); chỉ ghi những mã có mặt trong lô của bạn.

| Mã lỗi | Số ảnh/dòng | Ai sửa (máy/người) | Vì sao |
|---|---:|---|---|
| TODO(học viên) | | | |

TODO(học viên): vì sao `05_review_queue.csv` xếp ảnh đầu hàng như vậy? Với ngân sách 80 ảnh, người xem được bao nhiêu lỗi ngữ nghĩa?

## 3. Calibration (2 ngưỡng)
| Tham số | Khởi đầu | Đã chọn | Precision / Recall (trước → sau) | Lý do (đánh đổi) |
|---|---|---|---|---|
| `duplicates.phash_dist` | 2 | **12** | DUP_IMAGE_NEAR 1.00 / 0.50 → 1.00 / 0.67 (DUP_IMAGE_EXACT giữ 1.00 / 1.00) | Lỗi này máy tự xoá ảnh nên ưu tiên precision. Trên calib 4–14 cho cùng kết quả; trên raw tôi mở xem: cặp d=6 (img_0223~img_0077) và d=10 (img_0186~img_0061) là trùng thật; cặp d=16 là khác cảnh. 12 bắt được cặp d=10 và còn cách 16 một khoảng an toàn |
| `second_opinion.conf` | 0.25 | **0.6** | WRONG_CLASS 0.56 / 0.83 → 0.62 / 0.83; MISSING 0.50 / 1.00 → 0.57 / 1.00; LOOSE_BOX 0.29 / 0.40 → 0.20 / 0.20 | Cảnh báo cho người nên giữ recall; 0.6 bớt báo động giả mà MISSING vẫn recall 1.00. 0.8 cho WRONG_CLASS precision 1.00 và raw ra Release (7.8% ảnh còn cảnh báo) nhưng MISSING recall tụt 0.75 (sót 2/8): Release giả. Đổi lại LOOSE_BOX recall giảm (0.40 → 0.20; chỉ 5 lỗi chèn nên nhảy bậc lớn) |

**Chỗ calibration đánh lừa:** trên calib `phash_dist = 16` là tốt nhất (DUP_IMAGE_NEAR 1.00 / 0.83). Nhưng trên raw, 16 loại 31/224 ảnh ở cửa vào, so với 22 ở ngưỡng 12: thêm 9 ảnh (3 DUP_IMAGE_NEAR đều đúng d=16 và 6 LEAK_TEST). Tôi mở xem img_0011~img_0008 và img_0013~test/test_087: cả hai cặp là **khác cảnh** — ngưỡng tối ưu cho calib (39 ảnh, không có ca LEAK_TEST) lại xoá nhầm ảnh tốt trên raw.

## 4. Cửa chặn và điều pipeline KHÔNG bắt được
TODO(học viên): (a) chứng minh gate chặn đúng: chạy `python -m pipeline.run --budget 0 --reports work/rep_nb --export-dir work/exp_nb` (không có người duyệt nên ảnh thiếu file nhãn còn nguyên), chỉ ra kết luận **Rework**, mã thoát 20 và việc **không xuất** dataset. (Đừng sửa tay `work/run/ds`: pipeline dựng lại thư mục này từ raw mỗi lần chạy.) (b) ≥ 2 điểm mù có bằng chứng (box lỏng nhẹ, nhầm lớp mà model lớn cũng nhầm, ảnh trùng biến đổi mạnh…).

## 5. Train: raw vs clean (tùy chọn, chấm riêng)
Chưa train: ghi "chưa chạy" và lý do, rồi bỏ qua phần còn lại của mục này. Nếu đã train: dán bảng từ `submission/results/comparison.md` (model, epoch, seed, số ảnh train mỗi biến thể).

TODO(học viên): chênh mAP50 (clean − raw) so với **độ lệch chuẩn giữa các seed**; kết luận **trung thực** (nằm trong nhiễu thì nói là chưa kết luận được); ≥ 2 giả thuyết giải thích (ảnh trùng/rò rỉ test trong `raw`, nhãn máy còn lại trong `clean`, test chỉ 100 ảnh…) và cách kiểm.

## 6. Quyết định và ghi chú AI
TODO(học viên): (a) quyết định cuối; nếu Hold/Rework cần làm gì để thành Release?

(b) Ghi chú AI (Claude Code viết 4 module):
- **Prompt chính:** "đọc docstring + test của từng module (label_format, gate, autofix, second_opinion), viết đúng đầu vào/đầu ra, ngưỡng lấy từ `cfg`, không sửa `tests/`, `data/` và file ĐÃ VIẾT SẴN".
- **Cách kiểm:** `pytest` 79/79 passed; tự thêm 3 ca ngoài test (một dòng dính 2 lỗi + dòng trống + `nan`; autofix chạy lần 2 không đổi gì; một ảnh nhiều dự đoán đủ 4 loại cảnh báo) đều xanh; chạy thử `python -m pipeline.run` ra `work/` trước khi calibrate; `calibrate` cho các lỗi cú pháp chèn sẵn precision/recall 1.00.
- **Một lần AI sai:** ca thử thêm cho `second_opinion` đặt box dự đoán quá nhỏ (IoU 0.25 < `iou_missing` 0.3) nhưng lại kỳ vọng POSSIBLE_LOOSE_BOX; test đỏ, kiểm lại phép tính IoU thì code đúng (ra POSSIBLE_MISSING + POSSIBLE_FALSE_POS), sửa lại ca thử.

*(Thưởng +2, tùy chọn)* CVAT: lọc `width < 20`, ảnh/số box khớp, đối chiếu `BOX_TINY` (xem docs/CVAT_FILTER.md), 1 câu về `can_review`.
