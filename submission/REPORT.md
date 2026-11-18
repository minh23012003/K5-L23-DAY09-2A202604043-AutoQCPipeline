# Báo cáo Day 09 — Nguyễn Viết Minh, 2A202604043

## 1. Kết luận trước
Pipeline kết luận **HOLD** (mã thoát 10). Vào **224** ảnh; cửa vào loại 22 ảnh (hỏng, quá nhỏ, trùng, rò rỉ test); **202/224** ảnh còn lại được xuất thành `export/clean_v1` dưới dạng **bản NHÁP** (manifest ghi decision=Hold, chưa phát hành).
Lý do: sau người duyệt không còn lỗi bắt buộc nào (0), nhưng **38/202 ảnh (18.8%)** còn cảnh báo chưa được người xem, vượt ngưỡng `warn_ratio_hold` 10% — hàng đợi 125 ảnh lớn hơn ngân sách duyệt 80 ảnh.

## 2. Lỗi và phân việc
Số liệu từ `02_error_list_v1.csv` (211 issue trên 224 ảnh vào; các mã ảnh lấy từ `01_intake.csv`), cách sửa từ `03_fixes.csv` (35 thay đổi: 20 `drop_line`, 8 `clip_box`, 6 `needs_label`, 1 `rename_classes`).

| Mã lỗi | Số ảnh/dòng | Ai sửa (máy/người) | Vì sao |
|---|---:|---|---|
| CORRUPT_IMAGE | 2 ảnh / 224 | máy (loại ở cửa vào) | ảnh không giải mã được thì không dùng được |
| BAD_SIZE | 3 ảnh / 224 | máy (loại) | cạnh ngắn < `min_side_px` |
| DUP_IMAGE_EXACT | 8 ảnh / 224 | máy (loại) | trùng md5: chắc chắn |
| DUP_IMAGE_NEAR | 4 ảnh / 224 | máy (loại) | phash ≤ 12, đã mở xem cặp d=6 và d=10 là trùng thật |
| LEAK_TEST | 5 ảnh / 224 | máy (loại) | ảnh trùng tập test/val làm điểm test bị thổi phồng |
| BAD_CLASS_NAME | 1 file (2 issue) | máy (`rename_classes`) | tên lớp trong `data.yaml` sai hoa/thường, có danh sách đúng trong cfg |
| BAD_CLASS_ID | 6 dòng / 6 ảnh | máy (`drop_line`) | ID ngoài 0..3 không đoán được lớp đúng |
| BAD_FORMAT | 3 dòng / 3 ảnh | máy (`drop_line`) | thiếu cột / `nan` |
| BOX_ZERO | 4 dòng / 4 ảnh | máy (`drop_line`) | box rộng/cao 0 |
| DUP_BOX | 7 dòng / 7 ảnh | máy (`drop_line`) | cùng lớp, IoU > 0.9 với dòng trước |
| BOX_OUT_OF_IMAGE | 8 dòng / 8 ảnh | máy (`clip_box`) | cắt về [0,1], giữ nguyên lớp |
| MISSING_LABEL_FILE | 6 ảnh / 202 | **người** (`needs_label`) | máy không được bịa nhãn; ưu tiên cao nhất trong hàng đợi |
| POSSIBLE_MISSING | 53 issue / 52 ảnh | người | model thấy vật mà nhãn không có box: cần mắt người |
| POSSIBLE_LOOSE_BOX | 28 issue / 24 ảnh | người | box lệch/lỏng: sửa toạ độ là quyết định ngữ nghĩa |
| POSSIBLE_FALSE_POS | 29 issue / 27 ảnh | người | box không khớp vật nào model thấy; model cũng có thể sai |
| POSSIBLE_WRONG_CLASS | 18 issue / 18 ảnh | người | đổi lớp hợp lệ (car↔truck↔bus) là nhãn ngữ nghĩa |
| EMPTY_LABEL | 12 ảnh / 202 | người | ảnh nền hay thiếu nhãn: chỉ người phân biệt được |
| BOX_TINY / BOX_HUGE | 6 dòng / 4 ảnh; 3 dòng / 3 ảnh | người | chỉ là cảnh báo theo quy tắc dự án |
| CLASS_RARE | 4 issue (cấp dataset) | ghi nhận | token lớp hiếm (ID lạ) — hết sau khi máy xoá dòng ID sai |

**Hàng đợi:** `05_review_queue.csv` xếp theo tổng trọng số `review.weights` của các mã trên ảnh. Đầu hàng là img_0020 (11.5: FIXED_DROP_LINE + POSSIBLE_MISSING + POSSIBLE_WRONG_CLASS), tiếp theo 6 ảnh `NEEDS_LABEL` (trọng số 10: chưa có nhãn thì không thể xuất), rồi các ảnh nhiều cảnh báo ngữ nghĩa (WRONG_CLASS 3, MISSING 2, FALSE_POS 2…); cuối hàng là cảnh báo nhẹ như BOX_TINY (0.3). Người duyệt đúng 80 ảnh đầu hàng (`06_review_log.csv`, 80/80 "thay bằng nhãn người").
Sau sửa tự động có **123 cảnh báo ngữ nghĩa trên 103 ảnh** (`04_error_list_v2`); với ngân sách 80 ảnh người xem được **94/123 cảnh báo (74/103 ảnh)**; 45 ảnh cuối hàng không ai xem, trong đó 38 ảnh còn cảnh báo → Hold.

## 3. Calibration (2 ngưỡng)
| Tham số | Khởi đầu | Đã chọn | Precision / Recall (trước → sau) | Lý do (đánh đổi) |
|---|---|---|---|---|
| `duplicates.phash_dist` | 2 | **12** | DUP_IMAGE_NEAR 1.00 / 0.50 → 1.00 / 0.67 (DUP_IMAGE_EXACT giữ 1.00 / 1.00) | Lỗi này **máy tự xoá ảnh**, FP = mất ảnh tốt, nên ưu tiên **precision**, rồi mới lấy recall. Trên calib mọi giá trị 4–14 cho cùng 1.00 / 0.67 (không có FP); 16 tăng recall lên 0.83 nhưng là ngưỡng mà trên raw bắt đầu gộp nhầm. Trên raw tôi mở xem: d=6 (img_0223~img_0077) và d=10 (img_0186~img_0061) là trùng thật, d=16 là khác cảnh → chọn 12, giữa vùng an toàn (bắt được d=10, cách 16 hai bậc). Kết quả: cửa vào loại 22/224 ảnh (ngưỡng 2: 19) |
| `second_opinion.conf` | 0.25 | **0.6** | WRONG_CLASS 0.56 / 0.83 → 0.62 / 0.83; MISSING 0.50 / 1.00 → 0.57 / 1.00; LOOSE_BOX 0.29 / 0.40 → 0.20 / 0.20; FALSE_POS 0.31 / 1.00 (không đổi: dùng `fp_conf` cố định) | Đây là **cảnh báo cho người** nên ưu tiên **recall** (FN = lỗi lọt vào dataset). Quy tắc chọn: **conf lớn nhất mà recall của MISSING và WRONG_CLASS chưa giảm** — từ 0.25 đến 0.6 hai recall này giữ 1.00 và 0.83, còn precision tăng (FP của MISSING 8 → 6, WRONG_CLASS 4 → 3); lên 0.7 MISSING recall tụt 0.88. Vì ngân sách duyệt chỉ 80 ảnh (hàng đợi 125 ảnh), bớt cờ giả nghĩa là 80 ảnh người xem chứa nhiều lỗi thật hơn. Không chọn 0.8 dù raw ra Release (16/202 = 7.9% ảnh còn cảnh báo): MISSING recall tụt 0.75 (sót 2/8), đó là Release giả. Cái giá chấp nhận: LOOSE_BOX recall 0.40 → 0.20 (chỉ 5 lỗi chèn, trọng số duyệt thấp 1.5) — ghi thành điểm mù ở mục 4 |

**Chỗ calibration đánh lừa:** trên calib `phash_dist = 16` là tốt nhất (DUP_IMAGE_NEAR 1.00 / 0.83). Nhưng trên raw, 16 loại 31/224 ảnh ở cửa vào, so với 22 ở ngưỡng 12: thêm 9 ảnh (3 DUP_IMAGE_NEAR đều đúng d=16 và 6 LEAK_TEST). Tôi mở xem img_0011~img_0008 và img_0013~test/test_087: cả hai cặp là **khác cảnh** — ngưỡng tối ưu cho calib (39 ảnh, không có ca LEAK_TEST) lại xoá nhầm ảnh tốt trên raw.

## 4. Cửa chặn và điều pipeline KHÔNG bắt được
**(a) Gate chặn đúng.** `python -m pipeline.run --budget 0 --reports work/rep_nb --export-dir work/exp_nb` (không người duyệt): kết luận **REWORK — "còn 6 lỗi bắt buộc (MISSING_LABEL_FILE)"**, mã thoát **20**, log ghi "KHÔNG xuất: còn lỗi bắt buộc (Rework)" và thư mục `work/exp_nb` không được tạo. Ở lần chạy chính, 6 ảnh này nằm trong 80 ảnh đầu hàng nên được người gán nhãn → hết lỗi bắt buộc. Chạy `make run` hai lần cho các file báo cáo giống hệt (chỉ khác đường dẫn `exported` trong `08_summary.json`).

**(b) Điểm mù có bằng chứng:**
1. **Box lỏng nhẹ:** ở `conf = 0.6`, POSSIBLE_LOOSE_BOX trên calib chỉ bắt 1/5 lỗi chèn (recall 0.20); trên raw `07_error_list_v3` vẫn còn 20 cảnh báo LOOSE_BOX. Box phình nhẹ mà IoU với dự đoán vẫn ≥ 0.5 thì không bị cờ.
2. **Ảnh trùng biến đổi mạnh:** DUP_IMAGE_NEAR trên calib chỉ bắt 4/6 (recall 0.67) ở mọi ngưỡng 4–14; muốn bắt thêm phải lên 16 thì lại gộp nhầm ảnh khác cảnh (mục 3). Ảnh bị cắt/biến đổi mạnh lọt vào dataset.
3. **Chỗ guideline không quy định:** ở img_0100 có box người trong gương; quy tắc kiểm không biết ảnh phản chiếu có nên gán hay không, model chỉ cờ được nếu nó không thấy "người" ở đó.
4. **Gate tin người duyệt hoàn toàn:** cảnh báo của ảnh đã duyệt bị bỏ qua, nhưng img_0075 sau khi thay bằng nhãn người vẫn còn POSSIBLE_FALSE_POS ở dòng 6 (`07_error_list_v3`) — nếu người duyệt sai thì pipeline không phát hiện.

Đối chiếu với 3 lỗi tôi tự thấy khi xem `work/viz`: img_0075 (thừa box car ở vật bị mờ) được cờ POSSIBLE_WRONG_CLASS và đã duyệt; img_0150 (thừa 1 box person) được cờ POSSIBLE_FALSE_POS dòng 3 nhưng nằm ngoài 80 ảnh được duyệt, nên là một trong 38 ảnh gây Hold.

## 5. Train: raw vs clean (tùy chọn, chấm riêng)
**Chưa chạy.** Phần train là tùy chọn, cần GPU (Colab T4) và chưa thực hiện trong buổi này; vì vậy không có `submission/results/` và không đưa ra kết luận nào về việc clean tốt hơn raw.

## 6. Quyết định và ghi chú AI
(a) **Quyết định cuối: HOLD** — không phát hành `clean_v1`. Để thành Release: người cần duyệt thêm ảnh trong 45 ảnh cuối hàng cho tới khi số ảnh còn cảnh báo chưa duyệt < 10% của 202 (tức ≤ 20 ảnh, cần xử lý thêm ít nhất 18/38 ảnh), sau đó chạy lại pipeline; nếu lần chạy lại xuất hiện lỗi bắt buộc thì kết luận chuyển thành Rework. Không tăng `second_opinion.conf` chỉ để hàng đợi vừa ngân sách (ở 0.8 sẽ ra Release giả do MISSING recall tụt 0.75).

(b) Ghi chú AI (Claude Code viết 4 module):
- **Prompt chính:** "đọc docstring + test của từng module (label_format, gate, autofix, second_opinion), viết đúng đầu vào/đầu ra, ngưỡng lấy từ `cfg`, không sửa `tests/`, `data/` và file ĐÃ VIẾT SẴN".
- **Cách kiểm:** `pytest` 79/79 passed; tự thêm 3 ca ngoài test (một dòng dính 2 lỗi + dòng trống + `nan`; autofix chạy lần 2 không đổi gì; một ảnh nhiều dự đoán đủ 4 loại cảnh báo) đều xanh; chạy thử `python -m pipeline.run` ra `work/` trước khi calibrate; `calibrate` cho các lỗi cú pháp chèn sẵn precision/recall 1.00.
- **Một lần AI sai:** ca thử thêm cho `second_opinion` đặt box dự đoán quá nhỏ (IoU 0.25 < `iou_missing` 0.3) nhưng lại kỳ vọng POSSIBLE_LOOSE_BOX; test đỏ, kiểm lại phép tính IoU thì code đúng (ra POSSIBLE_MISSING + POSSIBLE_FALSE_POS), sửa lại ca thử.
