"""文章配图：本地生成封面 + 要点信息图；从本地精选 CC0 图库配实拍照片（不需要署名）。"""
import hashlib
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
FONT = "/System/Library/Fonts/Hiragino Sans GB.ttc"
FONT_BOLD = "/System/Library/Fonts/STHeiti Medium.ttc"
USED = ROOT / "data" / "used_photos.txt"

PALETTES = [
    ((192, 38, 45), (120, 16, 24)),
    ((22, 101, 148), (10, 52, 92)),
    ((16, 122, 104), (8, 70, 64)),
    ((122, 63, 160), (66, 30, 102)),
    ((200, 92, 30), (128, 44, 12)),
    ((40, 64, 110), (18, 28, 56)),
]


def font(size, bold=False):
    return ImageFont.truetype(FONT_BOLD if bold else FONT, size)


def wrap(draw, text, fnt, max_w):
    lines, cur = [], ""
    for ch in text:
        if draw.textlength(cur + ch, font=fnt) > max_w and cur:
            lines.append(cur)
            cur = ch
        else:
            cur += ch
    if cur:
        lines.append(cur)
    return lines


def gradient(w, h, c1, c2):
    img = Image.new("RGB", (w, h), c1)
    px = ImageDraw.Draw(img)
    for y in range(h):
        t = y / h
        px.line([(0, y), (w, y)], fill=tuple(int(c1[i] * (1 - t) + c2[i] * t) for i in range(3)))
    return img


def palette(slug):
    return PALETTES[int(hashlib.md5(slug.encode()).hexdigest(), 16) % len(PALETTES)]


def make_cover(out: Path, title, category, site_name, slug):
    w, h = 1200, 630
    c1, c2 = palette(slug)
    img = gradient(w, h, c1, c2)
    d = ImageDraw.Draw(img, "RGBA")
    # 装饰：大血滴 + 圆点
    d.ellipse((860, -120, 1320, 340), fill=(255, 255, 255, 22))
    d.ellipse((960, 380, 1180, 600), fill=(255, 255, 255, 16))
    rnd = random.Random(slug)
    for _ in range(18):
        x, y, r = rnd.randint(700, 1180), rnd.randint(40, 600), rnd.randint(3, 8)
        d.ellipse((x - r, y - r, x + r, y + r), fill=(255, 255, 255, 40))
    # 分类标签
    tag_f = font(28, True)
    tw = d.textlength(category, font=tag_f)
    d.rounded_rectangle((70, 70, 70 + tw + 40, 122), 26, fill=(255, 255, 255, 235))
    d.text((90, 78), category, font=tag_f, fill=c1)
    # 标题
    size = 68
    while size > 44:
        tf = font(size, True)
        lines = wrap(d, title, tf, w - 160)
        if len(lines) <= 3:
            break
        size -= 4
    y = 170
    for line in lines[:3]:
        d.text((70, y), line, font=tf, fill="white")
        y += int(size * 1.35)
    # 底部站名
    d.line((70, 530, 150, 530), fill=(255, 255, 255, 200), width=4)
    d.text((70, 548), f"{site_name}", font=font(30, True), fill=(255, 255, 255, 230))
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out, "WEBP", quality=82)


def make_infographic(out: Path, title, keypoints, site_name, slug):
    w = 1080
    c1, c2 = palette(slug)
    probe = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    kf, tf = font(36), font(48, True)
    title_lines = wrap(probe, title, tf, w - 140)
    blocks = [wrap(probe, k, kf, w - 260) for k in keypoints]
    h = 120 + len(title_lines) * 66 + 60 + sum(len(b) * 52 + 60 for b in blocks) + 110
    img = Image.new("RGB", (w, h), (252, 250, 248))
    d = ImageDraw.Draw(img)
    d.rectangle((0, 0, w, 16), fill=c1)
    y = 80
    for line in title_lines:
        d.text((70, y), line, font=tf, fill=(29, 35, 48))
        y += 66
    d.text((70, y + 6), "要点速览", font=font(30, True), fill=c1)
    y += 70
    for i, b in enumerate(blocks, 1):
        bh = len(b) * 52 + 36
        d.rounded_rectangle((70, y, w - 70, y + bh), 22, fill="white", outline=(232, 228, 224), width=2)
        d.ellipse((96, y + 22, 156, y + 82), fill=c1)
        num = str(i)
        nf = font(34, True)
        d.text((126, y + 52), num, font=nf, fill="white", anchor="mm")
        ty = y + 20
        for line in b:
            d.text((186, ty), line, font=kf, fill=(40, 46, 60))
            ty += 52
        y += bh + 24
    d.text((70, h - 70), f"{site_name} · 仅供科普参考，不构成医疗建议", font=font(26), fill=(130, 136, 150))
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out, "WEBP", quality=85)


# 分类 → 精选图库分组（data/photo_pool/<分组>/，均为 CC0 免署名图片，已人工挑选并裁成 1200x630）
POOL = ROOT / "data" / "photo_pool"
GROUPS = {
    "孕期检查": ["pregnancy", "blood"],
    "流程攻略": ["hongkong", "checkup"],
    "体检套餐": ["checkup", "blood"],
    "机构选择": ["checkup", "hongkong"],
}


def pick_photo(out: Path, category, slug):
    """从精选图库挑一张最少使用的照片复制到 out，返回 True/False。"""
    used = USED.read_text().split() if USED.exists() else []
    groups = GROUPS.get(category, ["blood", "checkup"])
    cands = [(i, f) for i, g in enumerate(groups) for f in sorted((POOL / g).glob("*.webp"))]
    if not cands:
        return False
    # 先选用得最少的，同等次数下优先主分组，再按 slug 打散
    key = lambda c: (used.count(f"{c[1].parent.name}/{c[1].name}"), c[0], hashlib.md5((slug + c[1].name).encode()).hexdigest())
    f = min(cands, key=key)[1]
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(f.read_bytes())
    with USED.open("a") as fh:
        fh.write(f"{f.parent.name}/{f.name}\n")
    return True
