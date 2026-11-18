"""CHECK 2 — Dòng nhãn YOLO: sai định dạng, ID lớp lạ, box tràn ảnh, box rỗng, box lặp.   (Script 2 trong slide)   ★★

Test:  pytest tests/test_label_format.py -q

Mỗi dòng nhãn: `id cx cy w h` (5 số, toạ độ 0–1). Trả về list[Issue]; `Issue.line` = số dòng (đếm từ 1).

| code             | severity | khi nào                                                                  |
|------------------|----------|--------------------------------------------------------------------------|
| BAD_FORMAT       | ERROR    | không đúng 5 cột số (dùng `parse_yolo_line`, bắt `ValueError`)           |
| BAD_CLASS_ID     | ERROR    | id lớp ngoài 0..len(ds.classes)-1                                        |
| BOX_ZERO         | ERROR    | w <= 0 hoặc h <= 0                                                       |
| BOX_OUT_OF_IMAGE | ERROR    | mép box vượt [0,1] quá `cfg["label_format"]["overflow_tol"]`; extra={"overflow": mức tràn} |
| DUP_BOX          | ERROR    | cùng lớp với một dòng TRƯỚC ĐÓ và IoU > `dup_box_iou`; báo ở dòng SAU    |
| BOX_TINY         | WARN     | cạnh ngắn của box (px) < `min_box_px`  (cần `ds.image_size(stem)`)       |
| BOX_HUGE         | WARN     | w*h > `max_box_frac`                                                     |

Gợi ý
- Mép trái = x - w/2, mép phải = x + w/2 (xem câu hỏi "dòng YOLO nào lỗi?" trong slide).
- Một dòng hỏng (BAD_FORMAT, BAD_CLASS_ID, BOX_ZERO) thì `continue`, đừng kiểm tiếp hình học của dòng đó.
- Dòng thiếu cột làm script của slide dừng giữa chừng: đây là lý do phải `try/except`.
- `iou_xywh(a, b)` có sẵn trong common.py.
- Ngưỡng nằm trong `cfg["label_format"]` — đừng viết cứng số vào code.
"""
from ..common import ERROR, WARN, Issue, iou_xywh, parse_yolo_line  # noqa: F401


NAME = "label_format"


def run(ds, cfg):
    c = cfg["label_format"]
    n_cls = len(ds.classes)
    issues = []

    for lf in ds.label_files():                       # sorted -> kết quả ổn định
        stem = lf.stem
        size = ds.image_size(stem) if ds.image_path(stem) else None   # (W, H) px hoặc None
        kept = []                                     # [(số dòng, id, cx, cy, w, h)] các dòng hợp lệ trước đó, cho DUP_BOX

        for ln_no, text in ds.read_label_lines(stem) or []:   # đã bỏ dòng trống, giữ số dòng gốc
            # 1) Định dạng: thiếu/thừa cột, chữ, nan -> BAD_FORMAT, bỏ qua dòng
            try:
                cls, x, y, w, h = parse_yolo_line(text)
            except ValueError as e:
                issues.append(Issue(NAME, ERROR, "BAD_FORMAT", stem, f"dòng hỏng: {e}", line=ln_no))
                continue

            # 2) ID lớp ngoài 0..n_cls-1 -> BAD_CLASS_ID, bỏ qua dòng
            if not 0 <= cls < n_cls:
                issues.append(Issue(NAME, ERROR, "BAD_CLASS_ID", stem, f"id lớp {cls} ngoài 0..{n_cls - 1}", line=ln_no))
                continue

            # 3) BOX_ZERO: box rộng/cao <= 0 -> bỏ qua dòng
            if w <= 0 or h <= 0:
                issues.append(Issue(NAME, ERROR, "BOX_ZERO", stem, f"box rỗng: w={w} h={h}", line=ln_no))
                continue

            # 4) BOX_OUT_OF_IMAGE: mức tràn lớn nhất ở 4 mép (không continue)
            overflow = max(0.0, -(x - w / 2), (x + w / 2) - 1, -(y - h / 2), (y + h / 2) - 1)
            if overflow > c["overflow_tol"]:
                issues.append(Issue(NAME, ERROR, "BOX_OUT_OF_IMAGE", stem, f"box tràn ảnh {overflow:.4f}",
                                    line=ln_no, extra={"overflow": round(overflow, 4)}))

            # 5) DUP_BOX: cùng lớp + IoU cao với một dòng hợp lệ TRƯỚC đó -> báo ở dòng hiện tại
            for k_ln, k_cls, kx, ky, kw, kh in kept:
                if k_cls == cls and iou_xywh((x, y, w, h), (kx, ky, kw, kh)) > c["dup_box_iou"]:
                    issues.append(Issue(NAME, ERROR, "DUP_BOX", stem, f"box lặp với dòng {k_ln}",
                                        line=ln_no, extra={"dup_of": k_ln}))
                    break

            kept.append((ln_no, cls, x, y, w, h))

            # 6) BOX_TINY: cạnh ngắn theo pixel (cần kích thước ảnh)
            if size:
                short_px = min(w * size[0], h * size[1])
                if short_px < c["min_box_px"]:
                    issues.append(Issue(NAME, WARN, "BOX_TINY", stem, f"cạnh ngắn {short_px:.1f}px < {c['min_box_px']}px",
                                        line=ln_no, extra={"short_px": round(short_px, 1)}))

            # 7) BOX_HUGE: diện tích tỉ lệ
            if w * h > c["max_box_frac"]:
                issues.append(Issue(NAME, WARN, "BOX_HUGE", stem, f"box phủ {w * h:.0%} ảnh", line=ln_no))

    return issues
