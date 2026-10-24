"""一次性生成城市页、服务页正文（已存在的跳过）。
用法：uv run --with pillow --with pyyaml scripts/make_landing.py [--force]
"""
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent))
from daily import CFG, ROOT, claude, log  # noqa: E402

COMMON = """
要求：
- 简体中文，1200-1800 字，用 `##` 分 4-6 节，至少 1 个 Markdown 表格，不要写 H1，不要写 FAQ 节。
- 只写可靠的通用信息：费用、车程、班次等只给大致区间并注明「以官方/机构最新信息为准」；不编造机构名、地址、电话、统计数字。
- 不写如何跨境寄送或携带血液样本，不涉及胎儿性别鉴定渠道（内地法律禁止非医学需要的胎儿性别鉴定）。
- 结尾提醒检查结果需由医生解读。不要任何站外链接。

只输出 Markdown，以 YAML frontmatter 开头（字符串用双引号），不要代码块包裹：
---
title: "页面标题（含核心关键词，26 字内）"
description: "120 字内 meta 描述"
faq:
  - q: "问题"
    a: "回答（80 字内）"
  （共 3-4 个）
---
正文……
"""

CITY = """你在为网站「{site}」写落地页：「从{city}去香港验血/体检攻略」。
内容覆盖：从{city}到香港的主要交通方式（高铁到香港西九龙、航班、经深圳口岸过关等，按{city}实际情况挑合适的）、所需证件（港澳通行证+签注）、一天往返或两天行程建议（结合空腹抽血的时间安排）、预算构成、注意事项。
""" + COMMON

HK = """你在为网站「{site}」写落地页：「香港本地居民验血/体检指南」。
内容覆盖：公立与私营渠道的区别、是否需要医生转介、常见自费验血套餐类型、预约与取报告方式、医疗券/保险报销的一般说明、注意事项。
""" + COMMON

SERVICE = """你在为网站「{site}」写服务介绍落地页：「香港{name}」。
页面简介：{desc}
内容覆盖：这是什么检查/适合哪些人、常见项目构成（表格）、检查前准备、流程与报告时间、费用区间、如何选择机构、局限性与注意事项。
""" + COMMON


def parse(md):
    md = md.strip()
    md = md[md.find("---"):]
    _, fm, body = md.split("---", 2)
    meta = yaml.safe_load(fm)
    assert meta.get("title") and meta.get("description") and len(body.strip()) > 800, "内容不完整"
    return meta, body.strip()


def gen(out: Path, prompt):
    if out.exists() and "--force" not in sys.argv:
        return
    for _ in range(2):
        try:
            meta, body = parse(claude(prompt, tools="WebSearch"))
            fm = {"title": meta["title"], "description": meta["description"],
                  "faq": [{"q": str(f["q"]), "a": str(f["a"])} for f in meta.get("faq") or []]}
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text("---\n" + yaml.safe_dump(fm, allow_unicode=True, sort_keys=False, width=1000) + "---\n\n" + body + "\n")
            log(f"✓ {out.relative_to(ROOT)}")
            return
        except Exception as e:  # noqa: BLE001
            log(f"✗ {out.name}：{e}")


jobs = []
for slug, name in CFG["cities"]:
    tpl = HK if slug == "hongkong" else CITY
    jobs.append((ROOT / "src/content/cities" / f"{slug}.md", tpl.format(site=CFG["siteName"], city=name)))
for s in CFG["services"]:
    jobs.append((ROOT / "src/content/services" / f"{s['slug']}.md", SERVICE.format(site=CFG["siteName"], **s)))

GUIDES = {
    "labs": "香港医务化验所认证指南：HOKLAS 认可与医务化验师注册怎么查。内容覆盖：香港认可处（HKAS）与 HOKLAS 认可计划是什么、医学化验所认可（如 ISO 15189）的意义、怎么在官方名录里查一家化验所的认可范围、医务化验师管理委员会与执业注册怎么核实、私营化验所与诊所/医院的关系、选择化验所时要看的几点。必须用 WebSearch 核实机构名称和制度，不要编造网址；不点名推荐或评价任何具体私营机构。",
    "verify": "香港验血报告验真指南：怎么判断一份化验报告是否真实可靠。内容覆盖：一份正规报告应包含哪些要素（化验所名称、报告编号、采样/报告时间、检测方法、参考区间、签发人等）、如何直接联系化验所核实（用化验所官方公布的联系方式而非中介提供的）、常见风险信号（只给截图、无报告编号、价格异常、要求寄送血样等）、遇到问题去哪里投诉（如香港消费者委员会、卫生署）。必须用 WebSearch 核实，不要编造网址；不点名任何具体私营机构。",
}
for slug, desc in GUIDES.items():
    jobs.append((ROOT / "src/content/guides" / f"{slug}.md", f"你在为网站「{CFG['siteName']}」写科普落地页：{desc}\n" + COMMON))

with ThreadPoolExecutor(CFG.get("parallel", 4)) as ex:
    list(ex.map(lambda j: gen(*j), jobs))
