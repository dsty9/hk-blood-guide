"""重新生成已有文章的封面/信息图；缺照片的补照片。用法：uv run --with pillow --with pyyaml scripts/regen_images.py [--photos 重新配所有照片]"""
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent))
import images  # noqa: E402
from daily import CFG, IMG, POSTS  # noqa: E402

for p in sorted(POSTS.glob("*.md")):
    _, fm, body = p.read_text().split("---", 2)
    meta, slug = yaml.safe_load(fm), p.stem
    d = IMG / slug
    images.make_cover(d / "cover.webp", meta["title"], meta["category"], CFG["siteName"], slug)
    if meta.get("keypoints"):
        images.make_infographic(d / "infographic.webp", meta["title"], meta["keypoints"], CFG["siteName"], slug)
    if "--photos" in sys.argv or not meta.get("photo"):
        for k in ("photoCredit", "photoCreditUrl"):
            meta.pop(k, None)
        if images.pick_photo(d / "photo.webp", meta["category"], slug):
            meta.update(photo=f"images/{slug}/photo.webp", photoAlt=meta["title"])
    p.write_text("---\n" + yaml.safe_dump(meta, allow_unicode=True, sort_keys=False, width=1000) + "---" + body)
    print("✓", slug)
