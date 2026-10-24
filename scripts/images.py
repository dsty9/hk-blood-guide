"""文章配图：本地生成封面 + 要点信息图；免费图库（Pexels 有 key 时优先，否则 Openverse）配实拍照片。"""
import hashlib
import io
import json
import random
import urllib.parse
import urllib.request
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
FONT = "/System/Library/Fonts/Hiragino Sans GB.ttc"
FONT_BOLD = "/System/Library/Fonts/STHeiti Medium.ttc"
CACHE = ROOT / "data" / "photo_cache"
USED = ROOT / "data" / "used_photos.txt"
UA = "hk-blood-guide/1.0 (static blog image fetcher)"

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


def _get_json(url, headers=None):
    req = urllib.request.Request(url, headers={"User-Agent": UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read())


def _search(query, pexels_key):
    """返回候选列表 [{id,url,credit,credit_url,alt}]，按查询词缓存。"""
    CACHE.mkdir(parents=True, exist_ok=True)
    src = "pexels" if pexels_key else "openverse"
    cf = CACHE / f"{src}-{hashlib.md5(query.encode()).hexdigest()}.json"
    if cf.exists():
        return json.loads(cf.read_text())
    q = urllib.parse.quote(query)
    items = []
    if pexels_key:
        data = _get_json(f"https://api.pexels.com/v1/search?query={q}&per_page=40&orientation=landscape",
                         {"Authorization": pexels_key})
        for p in data.get("photos", []):
            items.append({"id": f"pexels-{p['id']}", "url": p["src"]["large2x"], "alt": p.get("alt") or query,
                          "credit": f"{p['photographer']} / Pexels", "credit_url": p["url"]})
    else:
        data = _get_json(f"https://api.openverse.org/v1/images/?q={q}&license_type=commercial,modification"
                         f"&category=photograph&aspect_ratio=wide&size=large&page_size=20&mature=false")
        for p in data.get("results", []):
            lic = f"CC {p['license'].upper()}" if p["license"] not in ("cc0", "pdm") else p["license"].upper()
            items.append({"id": f"ov-{p['id']}", "url": p["url"], "alt": p.get("title") or query,
                          "credit": f"{p.get('creator') or 'Unknown'} / {lic}", "credit_url": p["foreign_landing_url"]})
    cf.write_text(json.dumps(items, ensure_ascii=False))
    return items


def fetch_photo(out: Path, query, pexels_key=""):
    """下载一张未用过的照片到 out（webp, 宽 1200）。成功返回 (alt, credit, credit_url)，失败返回 None。"""
    used = set(USED.read_text().split()) if USED.exists() else set()
    queries = [query, " ".join(query.split()[:2]), "blood test", "medical laboratory"]
    for q in dict.fromkeys(queries):
        try:
            items = _search(q, pexels_key)
        except Exception:
            continue
        for it in items:
            if it["id"] in used:
                continue
            try:
                req = urllib.request.Request(it["url"], headers={"User-Agent": UA})
                with urllib.request.urlopen(req, timeout=25) as r:
                    img = Image.open(io.BytesIO(r.read())).convert("RGB")
            except Exception:
                used.add(it["id"])
                continue
            if img.width < 800:
                used.add(it["id"])
                continue
            # 裁成 1200x630
            tw, th = 1200, 630
            scale = max(tw / img.width, th / img.height)
            img = img.resize((int(img.width * scale), int(img.height * scale)), Image.LANCZOS)
            left, top = (img.width - tw) // 2, (img.height - th) // 2
            img = img.crop((left, top, left + tw, top + th))
            out.parent.mkdir(parents=True, exist_ok=True)
            img.save(out, "WEBP", quality=80)
            with USED.open("a") as f:
                f.write(it["id"] + "\n")
            return it["alt"][:80], it["credit"][:80], it["credit_url"]
    return None
