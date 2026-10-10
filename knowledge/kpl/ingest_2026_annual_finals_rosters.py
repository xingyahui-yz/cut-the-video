"""Idempotently import verified 2026 KPL annual-finals roster evidence."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
players_path = ROOT / "data" / "players.json"
sources_path = ROOT / "data" / "sources.json"
coverage_path = ROOT / "data" / "coverage.json"
players_data = json.loads(players_path.read_text(encoding="utf-8-sig"))
sources_data = json.loads(sources_path.read_text(encoding="utf-8-sig"))
coverage = json.loads(coverage_path.read_text(encoding="utf-8-sig"))
players = {p["id"]: p for p in players_data["players"]}
sources = {s["id"]: s for s in sources_data["sources"]}

source_records = [
    {
        "id": "s-kpl-2026-annual-finals-team-list",
        "url": "https://sina.cn/news/detail/5345555469042025.html",
        "title": "2026 KPL年度总决赛选手大名单公布：参赛队伍与分组",
        "publisher": "KPL王者荣耀职业联赛官方微博（新浪原帖镜像）",
        "published_on": "2026-09-21", "accessed_on": "2026-10-04",
        "first_party": True, "retrieval_status": "opened",
        "access_mode": "publisher_post_on_platform_mirror", "mirror_platform": "新浪",
        "note": "原帖认证账号正文确认大师组、精英组各6队；选手姓名见配图，本条只用于记录赛事范围。",
    },
    {
        "id": "s-wb-2026-annual-finals-roster",
        "url": "https://www.sina.cn/news/detail/5345600767793623.html",
        "title": "北京WB王者荣耀分部2026年KPL年度总决赛出征大名单",
        "publisher": "北京WB王者荣耀分部官方微博（新浪原帖镜像）",
        "published_on": "2026-09-21", "accessed_on": "2026-10-04",
        "first_party": True, "retrieval_status": "opened",
        "access_mode": "publisher_post_on_platform_mirror", "mirror_platform": "新浪",
        "note": "官方帖文正文逐名列出7名选手及实名；教练组另列，未计入选手。",
    },
    {
        "id": "s-wb-2026-annual-finals-tao-loan",
        "url": "https://sina.cn/news/detail/5344945242116615.html",
        "title": "北京WB公告：涛租借征战2026 KPL年度总决赛",
        "publisher": "北京WB王者荣耀分部官方微博（新浪原帖镜像）",
        "published_on": "2026-09-19", "accessed_on": "2026-10-04",
        "first_party": True, "retrieval_status": "opened",
        "access_mode": "publisher_post_on_platform_mirror", "mirror_platform": "新浪",
        "note": "官方正文确认RNGM游走选手应泽涛（ID：涛）租借至北京WB共同征战年总；完整名单公告也列出涛。",
    },
    {
        "id": "s-wolves-2026-annual-finals-fly-loan",
        "url": "https://sina.cn/news/detail/5345268652310672.html",
        "title": "重庆狼队公告：Fly租借征战2026 KPL年度总决赛",
        "publisher": "狼队王者荣耀分部官方微博（新浪原帖镜像）",
        "published_on": "2026-09-20", "accessed_on": "2026-10-04",
        "first_party": True, "retrieval_status": "opened",
        "access_mode": "publisher_post_on_platform_mirror", "mirror_platform": "新浪",
        "note": "公告明确原eStarPro选手Fly（彭云飞）租借至重庆狼队并随队征战年总。",
    },
    {
        "id": "s-hero-2026-annual-finals-jiguang-loan",
        "url": "https://sina.cn/news/detail/5344948218232888.html",
        "title": "南通Hero久竞公告：极光租借征战2026 KPL年度总决赛",
        "publisher": "南通Hero久竞王者荣耀分部官方微博（新浪原帖镜像）",
        "published_on": "2026-09-19", "accessed_on": "2026-10-04",
        "first_party": True, "retrieval_status": "opened",
        "access_mode": "publisher_post_on_platform_mirror", "mirror_platform": "新浪",
        "note": "公告明确原RNGM选手周文强（ID：极光）租借至南通Hero久竞征战年总。",
    },
    {
        "id": "s-jdg-2026-annual-finals-huayuan-loan",
        "url": "https://sina.cn/news/detail/5345163124671078.html",
        "title": "北京JDG公告：花缘租借征战2026 KPL年度总决赛",
        "publisher": "北京JDG王者荣耀分部官方微博（新浪原帖镜像）",
        "published_on": "2026-09-20", "accessed_on": "2026-10-04",
        "first_party": True, "retrieval_status": "opened",
        "access_mode": "publisher_post_on_platform_mirror", "mirror_platform": "新浪",
        "note": "官方正文确认佛山DRG选手谭锦威（ID：花缘）租借至北京JDG并随队征战年总。",
    },
    {
        "id": "s-ksg-2026-annual-finals-menglan-loan",
        "url": "https://sina.cn/news/detail/5345185949026562.html",
        "title": "KSG公告：梦岚租借征战2026 KPL年度总决赛",
        "publisher": "KSG王者荣耀分部官方微博（新浪原帖镜像）",
        "published_on": "2026-09-20", "accessed_on": "2026-10-04",
        "first_party": True, "retrieval_status": "opened",
        "access_mode": "publisher_post_on_platform_mirror", "mirror_platform": "新浪",
        "note": "官方正文及年总租借期标签确认佛山DRG选手彭俊岚（ID：梦岚）租借至KSG。",
    },
    {
        "id": "s-dyg-2026-annual-finals-xiaoa-loan",
        "url": "https://www.sina.cn/news/detail/5344219434845928.html",
        "title": "武汉eStarPro公告：小A租借至深圳DYG",
        "publisher": "武汉eStarPro王者荣耀分部官方微博（新浪原帖镜像）",
        "published_on": "2026-09-17", "accessed_on": "2026-10-04",
        "first_party": True, "retrieval_status": "opened",
        "access_mode": "publisher_post_on_platform_mirror", "mirror_platform": "新浪",
        "note": "官方正文及年总租借期标签确认游走选手杨荣鑫（ID：小A）租借至深圳DYG。",
    },
    {
        "id": "s-tes-2026-annual-finals-liangyu-loan",
        "url": "https://sina.cn/news/detail/5345200878129125.html",
        "title": "长沙TES.A公告：亮宇租借征战2026 KPL年度总决赛",
        "publisher": "滔搏电竞王者荣耀分部官方微博（新浪原帖镜像）",
        "published_on": "2026-09-20", "accessed_on": "2026-10-04",
        "first_party": True, "retrieval_status": "opened",
        "access_mode": "publisher_post_on_platform_mirror", "mirror_platform": "新浪",
        "note": "官方正文确认陈亮宇（ID：亮宇）租借至长沙TES.A并随队征战年总。",
    },
    {
        "id": "s-rw-2026-annual-finals-zaodian-loan",
        "url": "https://sina.cn/news/detail/5345525265859639.html",
        "title": "济南RW侠公告：早点租借征战2026 KPL年度总决赛",
        "publisher": "RW侠王者荣耀分部官方微博（新浪原帖镜像）",
        "published_on": "2026-09-21", "accessed_on": "2026-10-04",
        "first_party": True, "retrieval_status": "opened",
        "access_mode": "publisher_post_on_platform_mirror", "mirror_platform": "新浪",
        "note": "官方公告确认选手沈若飞（ID：早点）租借至济南RW侠，带有年总租借期标签。",
    },
]
for source in source_records:
    sources.setdefault(source["id"], source)

entries = [
    ("fly", "Fly", "重庆狼队", "s-wolves-2026-annual-finals-fly-loan", "彭云飞", "2026-09-20"),
    ("jiguang", "极光", "南通Hero久竞", "s-hero-2026-annual-finals-jiguang-loan", "周文强", "2026-09-19"),
    ("huayuan", "花缘", "北京JDG", "s-jdg-2026-annual-finals-huayuan-loan", "谭锦威", "2026-09-20"),
    ("menglan", "梦岚", "KSG", "s-ksg-2026-annual-finals-menglan-loan", "彭俊岚", "2026-09-20"),
    ("xiaoa", "小A", "深圳DYG", "s-dyg-2026-annual-finals-xiaoa-loan", "杨荣鑫", "2026-09-17"),
    ("liangyu", "亮宇", "长沙TES.A", "s-tes-2026-annual-finals-liangyu-loan", "陈亮宇", "2026-09-20"),
    ("zaodian", "早点", "济南RW侠", "s-rw-2026-annual-finals-zaodian-loan", "沈若飞", "2026-09-21"),
    ("zimo", "梓墨", "北京WB", "s-wb-2026-annual-finals-roster", "吴喆杰", "2026-09-21"),
    ("nuanyang", "暖阳", "北京WB", "s-wb-2026-annual-finals-roster", "林恒", "2026-09-21"),
    ("anliang", "安凉", "北京WB", "s-wb-2026-annual-finals-roster", "张雪龙", "2026-09-21"),
    ("tingyue", "听悦", "北京WB", "s-wb-2026-annual-finals-roster", "吴佐", "2026-09-21"),
    ("zhaojue", "昭珏", "北京WB", "s-wb-2026-annual-finals-roster", "屈万东", "2026-09-21"),
    ("yisheng", "一笙", "北京WB", "s-wb-2026-annual-finals-roster", "李自威", "2026-09-21"),
    ("tao", "涛", "北京WB", "s-wb-2026-annual-finals-roster", "应泽涛", "2026-09-21"),
]

for player_id, name, team, source_id, real_name, published_on in entries:
    player = players.get(player_id)
    if player is None:
        player = {
            "id": player_id, "display_name": name, "aliases": [], "facts": [],
            "kpl_appearance": {"status": "pending", "evidence_fact_ids": []},
            "unknowns": ["目前只有2026年度总决赛名单证据；KPL正赛实际登场仍需独立核实。"],
        }
        players[player_id] = player
    aliases = player.setdefault("aliases", [])
    alias = next((a for a in aliases if a["text"] == real_name), None)
    if alias is None:
        aliases.append({"text": real_name, "source_ids": [source_id]})
    elif source_id not in alias.setdefault("source_ids", []):
        alias["source_ids"].append(source_id)
    facts = player.setdefault("facts", [])
    if not any(f.get("type") == "identity" and f.get("real_name") == real_name for f in facts):
        identity_id = f"{player_id}-identity-2026-annual-finals-roster"
        if not any(f["id"] == identity_id for f in facts):
            facts.append({
                "id": identity_id, "type": "identity", "real_name": real_name,
                "summary": f"2026年总决赛官方名单将选手{name}对应姓名列为{real_name}。",
                "verified": True, "source_ids": [source_id],
            })
    roster_id = f"{player_id}-2026-annual-finals-roster"
    if not any(f["id"] == roster_id for f in facts):
        facts.append({
            "id": roster_id, "type": "roster_listing",
            "summary": f"官方资料确认{name}被列入{team}2026年KPL年度总决赛参赛名单。",
            "verified": True, "source_ids": [source_id], "event_date": published_on,
            "season": "2026 KPL年度总决赛", "competition_type": "KPL_league",
            "competition_name": "2026 KPL年度总决赛", "team_at_event": team,
            "roster_kind": "season_roster",
            "date_meaning": "官方名单或租借公告发布日期；列入名单不代表实际登场。",
        })
    if player_id == "tao":
        roster_fact = next(f for f in facts if f["id"] == roster_id)
        extra_source_id = "s-wb-2026-annual-finals-tao-loan"
        if extra_source_id not in roster_fact.setdefault("source_ids", []):
            roster_fact["source_ids"].append(extra_source_id)

players_data["players"] = sorted(players.values(), key=lambda p: p["id"])
sources_data["sources"] = sorted(sources.values(), key=lambda s: s["id"])
batch = {
    "competition_name": "2026 KPL年度总决赛", "as_of": "2026-10-04",
    "official_team_count": 12, "groups": {"大师组": 6, "精英组": 6},
    "official_team_announcement_sources_found": 9,
    "teams_with_full_named_roster_verified": 1,
    "verified_roster_listing_facts": len(entries),
    "known_distinct_players": len({entry[0] for entry in entries}),
    "teams_with_fully_unread_roster_images": [
        "重庆狼队（Fly仅由租借公告确认）", "成都AG超玩会", "北京JDG", "广州TTG",
        "KSG", "长沙TES.A", "上海EDG.M", "杭州LGD.NBW", "深圳DYG", "济南RW侠",
        "南通Hero久竞（极光仅由租借公告确认）",
    ],
    "unresolved_gaps": [
        "北京WB官方正文完整列出7名选手；其余队伍目前仅确认官方租借公告提及的选手，完整名单仍需读取官方海报或可读的逐人公告。",
        "官方名单只证明列名，不能替代KPL正赛实际登场证据。",
    ],
}
roster_coverage = coverage.setdefault("roster_listing_coverage", {})
batches = roster_coverage.setdefault("season_batches", [])
batches[:] = [b for b in batches if b.get("competition_name") != batch["competition_name"]]
batches.append(batch)
coverage["as_of"] = "2026-10-04"

players_path.write_text(json.dumps(players_data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
sources_path.write_text(json.dumps(sources_data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
coverage_path.write_text(json.dumps(coverage, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"players={len(players_data['players'])}; sources={len(sources_data['sources'])}; verified_2026_roster_entries={len(entries)}")
