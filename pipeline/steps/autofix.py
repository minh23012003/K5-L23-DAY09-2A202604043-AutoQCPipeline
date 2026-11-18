"""BƯỚC 2/4 — Sửa tự động những lỗi bắt buộc mà máy sửa được AN TOÀN.   ★★

Test:  pytest tests/test_autofix.py -q

`fix(ds, issues, cfg) -> list[dict]`: duyệt `issues` (chỉ lỗi severity ERROR), sửa thẳng vào thư mục `ds`,
và trả về danh sách thay đổi; mỗi phần tử có khoá: image, line, action, before, after
(đây chính là file `03_fixes.csv` — bằng chứng pipeline đã làm gì, người có thể kiểm lại).

| code lỗi                                       | cách sửa                                    | action           |
|------------------------------------------------|---------------------------------------------|------------------|
| BAD_FORMAT, BAD_CLASS_ID, BOX_ZERO, DUP_BOX    | xoá dòng đó khỏi file nhãn                  | "drop_line"      |
| BOX_OUT_OF_IMAGE                               | cắt box về trong [0,1] (giữ nguyên lớp)     | "clip_box"       |
| MISSING_LABEL_FILE                             | KHÔNG sửa file (máy không thể bịa nhãn): ghi 1 dòng fix, before="(không có file)", after="chuyển người gán" | "needs_label" |
| BAD_CLASS_NAME                                 | ghi lại `names` trong data.yaml đúng `cfg["classes"]` | "rename_classes" |
| DUP_IMAGE_*, LEAK_TEST, CORRUPT_IMAGE, BAD_SIZE| xoá ảnh + nhãn khỏi `ds`                    | "remove_image"   |

Bẫy cần nghĩ tới (có test cho từng cái)
- Một file có NHIỀU dòng lỗi: số dòng trong `issues` là số dòng GỐC. Nếu xoá từng dòng một thì số dòng lệch.
  Gom theo file, rồi ghi lại MỘT lần.
- Sau khi cắt, box có thể không còn diện tích (nằm hẳn ngoài ảnh): lúc đó xoá dòng thay vì ghi box rỗng.
- Một dòng có 2 lỗi (vd. BOX_OUT_OF_IMAGE + DUP_BOX): xoá dòng thắng, chỉ ghi 1 fix `drop_line`, không ghi thêm `clip_box`. Dòng trống ở giữa file vẫn đếm vào số dòng gốc.
- Ảnh vừa bị xoá (DUP_IMAGE_*...) mà còn issue dòng của chính nó: bỏ qua êm, không được báo lỗi/chết.
- Không động tới lỗi WARN (cảnh báo là việc của người). Không sửa file ở `data/raw/` — chỉ sửa `ds`.
- Chạy lần 2 trên dữ liệu đã sửa phải không làm gì thêm (idempotent) — NGOẠI LỆ duy nhất: `needs_label` được ghi lại mỗi lần còn lỗi `MISSING_LABEL_FILE` (vì ảnh vẫn chưa có nhãn).

- `needs_label` KHÔNG tạo file nhãn rỗng (rỗng = "ảnh nền", khác với "chưa gán"). `review_queue` sẽ đẩy ảnh này lên đầu hàng đợi cho người.

Gợi ý: `yaml.safe_load / safe_dump`.
"""
from collections import defaultdict  # noqa: F401

import yaml  # noqa: F401

from ..common import ERROR, parse_yolo_line  # noqa: F401


DROP_CODES = {"BAD_FORMAT", "BAD_CLASS_ID", "BOX_ZERO", "DUP_BOX"}
CLIP_CODES = {"BOX_OUT_OF_IMAGE"}
REMOVE_CODES = {"DUP_IMAGE_EXACT", "DUP_IMAGE_NEAR", "LEAK_TEST", "CORRUPT_IMAGE", "BAD_SIZE"}


def _fx(image, line, action, before, after):
    return {"image": image, "line": line, "action": action, "before": before, "after": after}


def _clip(text):
    """Cắt box về [0,1]. Trả về dòng mới, hoặc None nếu box không còn diện tích / không parse được."""
    try:
        cls, x, y, w, h = parse_yolo_line(text)
    except ValueError:
        return None
    x1, x2 = max(0.0, x - w / 2), min(1.0, x + w / 2)
    y1, y2 = max(0.0, y - h / 2), min(1.0, y + h / 2)
    if x2 <= x1 or y2 <= y1:
        return None
    return f"{cls} {(x1 + x2) / 2:.6f} {(y1 + y2) / 2:.6f} {x2 - x1:.6f} {y2 - y1:.6f}"


def fix(ds, issues, cfg):
    errs = [i for i in issues if i.severity == ERROR]          # WARN là việc của người
    fixes = []

    # 1) Xoá ảnh (trùng, rò rỉ test, hỏng, quá nhỏ) — làm trước để bỏ qua issue dòng của ảnh đã xoá
    removed = set()
    for stem in sorted({i.image for i in errs if i.code in REMOVE_CODES}):
        codes = ",".join(sorted({i.code for i in errs if i.image == stem and i.code in REMOVE_CODES}))
        img = ds.image_path(stem)
        lab = ds.label_path(stem)
        if img is None and not lab.exists():
            continue
        if img is not None:
            img.unlink()
        if lab.exists():
            lab.unlink()
        removed.add(stem)
        fixes.append(_fx(stem, None, "remove_image", f"{img.name if img else '(không có ảnh)'} ({codes})", "(đã xoá)"))

    # 2) Tên lớp trong data.yaml
    if any(i.code == "BAD_CLASS_NAME" for i in errs):
        d = yaml.safe_load(ds.yaml_path.read_text(encoding="utf-8")) if ds.yaml_path.exists() else None
        d = d if isinstance(d, dict) else {}
        old = d.get("names")
        if old != list(cfg["classes"]):
            d["names"] = list(cfg["classes"])
            if "nc" in d:
                d["nc"] = len(cfg["classes"])
            ds.yaml_path.write_text(yaml.safe_dump(d, allow_unicode=True, sort_keys=False), encoding="utf-8")
            fixes.append(_fx("data.yaml", None, "rename_classes", str(old), str(list(cfg["classes"]))))

    # 3) Ảnh thiếu file nhãn: KHÔNG bịa nhãn, chỉ ghi lại để chuyển người gán
    for stem in sorted({i.image for i in errs if i.code == "MISSING_LABEL_FILE"} - removed):
        fixes.append(_fx(stem, None, "needs_label", "(không có file)", "chuyển người gán"))

    # 4) Lỗi dòng: gom theo file, dùng số dòng GỐC, ghi lại file MỘT lần
    drop, clip = defaultdict(set), defaultdict(set)
    for i in errs:
        if i.line is None or i.image in removed:
            continue
        if i.code in DROP_CODES:
            drop[i.image].add(i.line)
        elif i.code in CLIP_CODES:
            clip[i.image].add(i.line)

    for stem in sorted(set(drop) | set(clip)):
        p = ds.label_path(stem)
        if not p.exists():
            continue
        raw = p.read_text(encoding="utf-8", errors="replace").splitlines()
        out, changed = [], False
        for ln_no, text in enumerate(raw, 1):             # đếm cả dòng trống như số dòng gốc
            if ln_no in drop[stem]:                        # xoá dòng thắng clip
                fixes.append(_fx(stem, ln_no, "drop_line", text, "(đã xoá)"))
                changed = True
                continue
            if ln_no in clip[stem]:
                new = _clip(text)
                if new is None:                            # box nằm hẳn ngoài ảnh -> xoá
                    fixes.append(_fx(stem, ln_no, "drop_line", text, "(đã xoá: box ngoài ảnh)"))
                    changed = True
                    continue
                if new != text:
                    fixes.append(_fx(stem, ln_no, "clip_box", text, new))
                    changed = True
                out.append(new)
                continue
            out.append(text)
        if changed:
            p.write_text("\n".join(out) + ("\n" if out else ""), encoding="utf-8")

    return fixes
