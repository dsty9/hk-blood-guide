"""每日任务：取关键词 → claude -p 写文章 → 生成配图 → 构建校验 → git push 源码 + scripts/deploy.sh 发布 dist。

用法：
  uv run --with pillow --with pyyaml scripts/daily.py            # 按 site.config.json 的 dailyCount
  uv run --with pillow --with pyyaml scripts/daily.py --count 3  # 指定篇数
  加 --no-push 只生成不发布
"""
import argparse
import datetime as dt
import json
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent))
import images  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
POSTS = ROOT / "src" / "content" / "posts"
IMG = ROOT / "public" / "images"
QUEUE = ROOT / "data" / "keywords.txt"
DONE = ROOT / "data" / "keywords_done.txt"
LOGS = ROOT / "logs"
CFG = json.loads((ROOT / "site.config.json").read_text())
LOCAL = ROOT / "config.local.json"  # 不进 git，本机覆盖配置
if LOCAL.exists():
    CFG.update(json.loads(LOCAL.read_text()))
CATEGORIES = ["验血项目", "价格费用", "机构选择", "孕期检查", "体检套餐", "流程攻略", "报告解读"]
TODAY = dt.date.today()
LOGS.mkdir(exist_ok=True)
LOG = LOGS / f"{TODAY}.log"


def log(msg):
    line = f"[{dt.datetime.now():%H:%M:%S}] {msg}"
    print(line, flush=True)
    with LOG.open("a") as f:
        f.write(line + "\n")


def claude(prompt, tools="WebSearch WebFetch", timeout=900):
    cmd = ["claude", "-p", "--output-format", "text", "--model", CFG.get("model", "sonnet")]
    if tools:
        cmd += ["--allowedTools", tools]
    r = subprocess.run(cmd, input=prompt, capture_output=True, text=True, timeout=timeout, cwd="/tmp")
    if r.returncode != 0:
        raise RuntimeError(r.stderr.strip()[:300] or r.stdout.strip()[:300])
    return r.stdout


def read_queue():
    lines = [l.strip() for l in QUEUE.read_text().splitlines()]
    return [l for l in lines if l and not l.startswith("#") and "|" in l]


def write_queue(items):
    header = "# 格式：分类|关键词    （daily.py 从上往下取，写完移到 keywords_done.txt）\n"
    QUEUE.write_text(header + "".join(i + "\n" for i in items))


def all_known_keywords():
    done = [l.strip() for l in DONE.read_text().splitlines() if l.strip()] if DONE.exists() else []
    return [i.split("|", 1)[1] for i in read_queue() + done]


def expand_keywords(n):
    known = all_known_keywords()
    tpl = (ROOT / "scripts" / "prompt_keywords.md").read_text()
    out = claude(tpl.format(n=n, existing="\n".join(known[-1500:])), tools="", timeout=600)
    seen = set(known)
    new = []
    for line in out.splitlines():
        line = line.strip().lstrip("-• ").strip()
        if "|" not in line:
            continue
        cat, kw = [s.strip() for s in line.split("|", 1)]
        if cat in CATEGORIES and kw and kw not in seen:
            seen.add(kw)
            new.append(f"{cat}|{kw}")
    write_queue(read_queue() + new)
    log(f"关键词扩充 +{len(new)}")


def existing_posts():
    rows = []
    for p in sorted(POSTS.glob("*.md")):
        m = re.search(r'^title:\s*"?(.+?)"?\s*$', p.read_text(), re.M)
        rows.append((p.stem, m.group(1) if m else p.stem))
    return rows


def parse(md):
    md = md.strip()
    md = re.sub(r"^```(?:markdown|md)?\s*\n", "", md)
    md = re.sub(r"\n```\s*$", "", md)
    start = md.find("---")
    if start < 0:
        raise ValueError("缺少 frontmatter")
    md = md[start:]
    _, fm, body = md.split("---", 2)
    meta = yaml.safe_load(fm)
    for k in ("slug", "title", "description"):
        if not meta.get(k):
            raise ValueError(f"frontmatter 缺 {k}")
    body = body.strip()
    if len(body) < 1200:
        raise ValueError(f"正文太短（{len(body)} 字）")
    body = re.sub(r"^#\s+.+\n+", "", body)  # 去掉重复 H1
    return meta, body


def unique_slug(slug):
    slug = re.sub(r"[^a-z0-9-]+", "-", slug.lower()).strip("-")[:70] or f"post-{TODAY:%Y%m%d}"
    base, i = slug, 2
    while (POSTS / f"{slug}.md").exists():
        slug, i = f"{base}-{i}", i + 1
    return slug


def write_article(cat, kw, existing):
    tpl = (ROOT / "scripts" / "prompt_article.md").read_text()
    ex = "\n".join(f"{s}｜{t}" for s, t in existing[-300:]) or "（暂无）"
    prompt = tpl.format(site_name=CFG["siteName"], keyword=kw, category=cat, today=TODAY, year=TODAY.year, existing=ex)
    last = None
    for _ in range(2):
        try:
            return parse(claude(prompt))
        except Exception as e:  # noqa: BLE001
            last = e
    raise last


def save(cat, kw, meta, body, valid_slugs, lock):
    with lock:
        slug = unique_slug(meta["slug"])
        (POSTS / f"{slug}.md").write_text("")  # 占位，防并发重名
    # 只保留指向已存在文章的站内链接
    def fix_link(m):
        s = m.group(2)
        return m.group(0) if s in valid_slugs else m.group(1)
    body = re.sub(r"\[([^\]]+)\]\(/posts/([a-z0-9-]+)/?\)", fix_link, body)
    body = re.sub(r"\[([^\]]+)\]\(https?://[^)]+\)", r"\1", body)  # 去站外链接
    keypoints = [str(k) for k in (meta.get("keypoints") or [])][:5]
    d = IMG / slug
    images.make_cover(d / "cover.webp", meta["title"], cat, CFG["siteName"], slug)
    fm = {
        "title": meta["title"], "description": meta["description"], "date": TODAY.isoformat(),
        "category": cat, "tags": meta.get("tags") or [], "keyword": kw,
        "cover": f"images/{slug}/cover.webp", "keypoints": keypoints,
        "faq": [{"q": str(f["q"]), "a": str(f["a"])} for f in (meta.get("faq") or []) if f.get("q") and f.get("a")],
    }
    if keypoints:
        images.make_infographic(d / "infographic.webp", meta["title"], keypoints, CFG["siteName"], slug)
        fm["infographic"] = f"images/{slug}/infographic.webp"
    with lock:  # used_photos 计数串行
        if images.pick_photo(d / "photo.webp", cat, slug):
            fm.update(photo=f"images/{slug}/photo.webp", photoAlt=meta["title"])
    text = "---\n" + yaml.safe_dump(fm, allow_unicode=True, sort_keys=False, width=1000) + "---\n\n" + body + "\n"
    (POSTS / f"{slug}.md").write_text(text)
    return slug


def git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--count", type=int, default=CFG.get("dailyCount", 10))
    ap.add_argument("--no-push", action="store_true")
    args = ap.parse_args()
    import threading
    lock = threading.Lock()

    if len(read_queue()) < args.count * 2:
        try:
            expand_keywords(max(200, args.count * 3))
        except Exception as e:  # noqa: BLE001
            log(f"关键词扩充失败：{e}")
    queue = read_queue()
    batch, rest = queue[: args.count], queue[args.count:]
    write_queue(rest)
    existing = existing_posts()
    valid = {s for s, _ in existing}
    log(f"开始：{len(batch)} 篇，并发 {CFG.get('parallel', 4)}")

    ok, failed = [], []
    with ThreadPoolExecutor(CFG.get("parallel", 4)) as ex:
        futs = {ex.submit(write_article, *b.split("|", 1), existing): b for b in batch}
        for f in as_completed(futs):
            item = futs[f]
            cat, kw = item.split("|", 1)
            try:
                meta, body = f.result()
                slug = save(cat, kw, meta, body, valid, lock)
                ok.append(slug)
                with DONE.open("a") as fh:
                    fh.write(item + "\n")
                log(f"✓ {kw} → {slug}")
            except Exception as e:  # noqa: BLE001
                failed.append(item)
                log(f"✗ {kw}：{e}")
    if failed:
        write_queue(read_queue() + failed)  # 失败的放回队尾

    if not ok:
        log("没有新文章，结束")
        return
    b = subprocess.run(["npm", "run", "build"], cwd=ROOT, capture_output=True, text=True)
    if b.returncode != 0:
        log("构建失败，不发布：\n" + b.stdout[-1500:] + b.stderr[-1500:])
        sys.exit(1)
    log(f"构建通过，新增 {len(ok)} 篇，失败 {len(failed)} 篇")
    if args.no_push:
        return
    git("add", "-A")
    git("commit", "-m", f"posts: {TODAY} +{len(ok)}")
    p = git("push")
    d = subprocess.run(["zsh", "scripts/deploy.sh"], cwd=ROOT, capture_output=True, text=True)
    log("已推送源码" if p.returncode == 0 else f"源码推送失败：{p.stderr[-500:]}")
    log("已发布到 GitHub Pages" if d.returncode == 0 else f"发布失败：{d.stderr[-500:]}")


if __name__ == "__main__":
    main()
