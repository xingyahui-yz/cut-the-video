"""Idempotent primary-source batch import for the KPL player knowledge base."""
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


def add_source(source):
    sources.setdefault(source["id"], source)


def add_player(player_id, display_name, unknowns=()):
    if player_id not in players:
        players[player_id] = {
            "id": player_id,
            "display_name": display_name,
            "aliases": [],
            "facts": [],
            "kpl_appearance": {"status": "pending", "evidence_fact_ids": []},
            "unknowns": list(unknowns),
        }
    return players[player_id]


def add_alias(player, text, source_id):
    if not any(a["text"] == text for a in player.get("aliases", [])):
        player.setdefault("aliases", []).append({"text": text, "source_ids": [source_id]})


def add_fact(player, fact):
    facts = player.setdefault("facts", [])
    if not any(old["id"] == fact["id"] for old in facts):
        facts.append(fact)
    if (fact.get("verified") and fact.get("type") in {"appearance", "debut"}
            and fact.get("competition_type") == "KPL_league"):
        membership = player["kpl_appearance"]
        membership["status"] = "verified"
        evidence = membership.setdefault("evidence_fact_ids", [])
        if fact["id"] not in evidence:
            evidence.append(fact["id"])


def make_fact(fact_id, fact_type, summary, source_ids, verified=True, **fields):
    return {"id": fact_id, "type": fact_type, "summary": summary, "verified": verified,
            "source_ids": source_ids, **fields}


for source in [
    {
        "id": "s-kpl-historical-finals-2017-2018",
        "url": "https://www.weibo.com/u/6074356560?tabtype=newVideo",
        "title": "KPL官方‘那年今日日历’：2017与2018春季赛冠军回顾",
        "publisher": "KPL王者荣耀职业联赛官方微博",
        "published_on": "2026-07-08", "accessed_on": "2026-10-04",
        "first_party": True, "retrieval_status": "opened",
        "access_mode": "official_account_timeline",
        "note": "读取官方账号时间线中的两段冠军回顾；未取得单条微博短链，名单正文在最初姓名后截断。只录入实际读到的人名和冠军首发信息，不推补截断名单或具体比赛日。",
    },
    {
        "id": "s-kpl-2024-spring-candidate-stats",
        "url": "https://weibo.com/6074356560/5028896414109899",
        "title": "2024 KPL春季赛常规赛最佳选手与新锐候选数据",
        "publisher": "KPL王者荣耀职业联赛官方微博",
        "published_on": "2024-04-30", "accessed_on": "2026-10-04",
        "first_party": True, "retrieval_status": "opened",
        "note": "统计范围为2024 KPL春季赛常规赛（含卡位赛）；正文给大帅、无幻的实际赛季MVP与个人数据，并排除登场率低于40%的选手。",
    },
    {
        "id": "s-kpl-20240510-spring-playoff-d9-g4",
        "url": "https://weibo.com/6074356560/5032602597592414",
        "title": "2024 KPL春季赛季后赛D9成都AG对重庆狼队第四局赛后战报",
        "publisher": "KPL王者荣耀职业联赛官方微博",
        "published_on": "2024-05-10", "accessed_on": "2026-10-04",
        "first_party": True, "retrieval_status": "opened",
    },
    {
        "id": "s-kpl-20241006-annual-finals-w1d5-g3",
        "url": "https://www.weibo.com/6074356560/OAl8CiIte",
        "title": "2024 KPL年度总决赛擂台赛W1D5重庆狼队对杭州LGD.NBW第三局战报",
        "publisher": "KPL王者荣耀职业联赛官方微博",
        "published_on": "2024-10-06", "accessed_on": "2026-10-04",
        "first_party": True, "retrieval_status": "opened",
        "note": "明确标记为年度总决赛擂台赛，赛事分类仍属KPL联赛体系，不与挑战者杯等杯赛荣誉混记。",
    },
    {
        "id": "s-kpl-menglan-20200919-debut-anniversary",
        "url": "https://www.sina.cn/news/detail/5344649699929115.html",
        "title": "佛山DRG官方回顾梦岚登场KPL六周年",
        "publisher": "佛山DRG电子竞技俱乐部官方微博（新浪原帖镜像）",
        "published_on": "2026-09-19", "accessed_on": "2026-10-04",
        "first_party": True, "retrieval_status": "opened",
        "access_mode": "publisher_post_on_platform_mirror", "mirror_platform": "新浪",
        "note": "俱乐部正文明确称梦岚于2020年初登KPL赛场；只记登场年份，不据六周年宣传推算比赛日。",
    },
    {
        "id": "s-kpl-qingyu-20230615-debut-anniversary",
        "url": "https://www.sina.cn/news/detail/5310011254508903.html",
        "title": "北京JDG官方祝轻语KPL登场三周年",
        "publisher": "北京JDG王者荣耀分部官方微博（新浪原帖镜像）",
        "published_on": "2026-06-15", "accessed_on": "2026-10-04",
        "first_party": True, "retrieval_status": "opened",
        "access_mode": "publisher_post_on_platform_mirror", "mirror_platform": "新浪",
        "note": "俱乐部正文确认其KPL登场三周年；只记2023年，未将周年帖日期直接当成具体比赛日期。",
    },
    {
        "id": "s-kpl-wanmo-20240614-debut-anniversary",
        "url": "https://www.sina.cn/news/detail/5309648892330670.html",
        "title": "RW侠官方回顾挽墨登场KPL二周年",
        "publisher": "RW侠王者荣耀分部官方微博（新浪原帖镜像）",
        "published_on": "2026-06-14", "accessed_on": "2026-10-04",
        "first_party": True, "retrieval_status": "opened",
        "access_mode": "publisher_post_on_platform_mirror", "mirror_platform": "新浪",
        "note": "俱乐部正文给出2024-06-14至2026-06-14的登场KPL二周年区间；按年记首登，不将周年日期视为某场比赛日。",
    },
    {
        "id": "s-kpl-jinyu-20201111-debut-anniversary",
        "url": "https://www.sina.cn/news/detail/4834543275611998.html",
        "title": "狼队官方祝今屿KPL登场两周年",
        "publisher": "狼队王者荣耀分部官方微博（新浪原帖镜像）",
        "published_on": "2022-11-11", "accessed_on": "2026-10-04",
        "first_party": True, "retrieval_status": "opened",
        "access_mode": "publisher_post_on_platform_mirror", "mirror_platform": "新浪",
        "note": "俱乐部正文明确列出2020-11-11至2022-11-11的KPL登场两周年区间；按年份记录，不独立推定赛事场次。",
    },
    {
        "id": "s-kpl-2025-spring-candidate-stats",
        "url": "https://weibo.com/6074356560/Ps4koqwBd",
        "title": "2025 KPL春季赛最佳阵容候选人与数据门槛",
        "publisher": "KPL王者荣耀职业联赛官方微博",
        "published_on": "2025-05-16", "accessed_on": "2026-10-04",
        "first_party": True, "retrieval_status": "opened",
        "note": "小A列入2025春季赛最佳游走候选；官方说明参与评选选手赛季及位置出场率均须不低于40%，可作实际参赛证据。",
    },
    {
        "id": "s-kpl-2019-spring-champions-20260615",
        "url": "https://www.sina.cn/news/detail/5310026350069275.html",
        "title": "eStarPro七年前夺冠：2019 KPL春季赛冠军首发回顾",
        "publisher": "KPL王者荣耀职业联赛官方微博（新浪原帖镜像）",
        "published_on": "2026-06-15", "accessed_on": "2026-10-04",
        "first_party": True, "retrieval_status": "opened",
        "access_mode": "publisher_post_on_platform_mirror", "mirror_platform": "新浪",
        "note": "正文列2019春季赛冠军首发及实名、Cat获决赛MVP；不把‘七年前的今天’换算成事件日期。",
    },
    {
        "id": "s-kpl-2025-summer-milestone-timeline",
        "url": "https://www.weibo.com/u/6074356560?tabtype=newVideo",
        "title": "KPL官方时间线：归期2025夏季赛200胜局里程碑",
        "publisher": "KPL王者荣耀职业联赛官方微博",
        "published_on": "2025-06-21", "accessed_on": "2026-10-04",
        "first_party": True, "retrieval_status": "opened",
        "access_mode": "official_account_timeline",
        "note": "官方时间线正文明确具体赛季、重庆狼队对北京JDG第三局和夏洛特；未取得目标帖单独短链，正文发布时刻可见。",
    },
    {
        "id": "s-xiaoyi-20201125",
        "url": "https://www.sina.cn/news/detail/4575195652168285.html",
        "title": "2020 KPL秋季赛常规赛最佳选手公告",
        "publisher": "KPL王者荣耀职业联赛官方微博（新浪原帖镜像）",
        "published_on": "2020-11-25", "accessed_on": "2026-10-04",
        "first_party": True, "retrieval_status": "opened",
        "access_mode": "publisher_post_on_platform_mirror", "mirror_platform": "新浪",
    },
    {
        "id": "s-ts-20200613-anniversary",
        "url": "https://www.sina.cn/news/detail/5309301574076321.html",
        "title": "TS夺得2020 KPL春季赛冠军六周年回顾",
        "publisher": "KPL王者荣耀职业联赛官方微博（新浪原帖镜像）",
        "published_on": "2026-06-13", "accessed_on": "2026-10-04",
        "first_party": True, "retrieval_status": "opened",
        "access_mode": "publisher_post_on_platform_mirror", "mirror_platform": "新浪",
        "note": "正文称TS夺冠，并列出当届冠军首发及姓名；与赛前首发公告区分。",
    },
    {
        "id": "s-kpl-20210703-spring-final",
        "url": "https://www.sina.cn/news/detail/4654867315951244.html",
        "title": "2021 KPL春季赛总决赛精彩操作回顾",
        "publisher": "KPL王者荣耀职业联赛官方微博（新浪原帖镜像）",
        "published_on": "2021-07-03", "accessed_on": "2026-10-04",
        "first_party": True, "retrieval_status": "opened",
        "access_mode": "publisher_post_on_platform_mirror", "mirror_platform": "新浪",
    },
    {
        "id": "s-kpl-cup-history-20250108",
        "url": "https://www.weibo.com/6074356560/P8Dcfg4WC",
        "title": "冬季冠军杯与挑战者杯历届冠军和FMVP回顾",
        "publisher": "KPL王者荣耀职业联赛官方微博",
        "published_on": "2025-01-08", "accessed_on": "2026-10-04",
        "first_party": True, "retrieval_status": "opened",
    },
    {
        "id": "s-kpl-qingrong-20211105",
        "url": "https://www.sina.cn/news/detail/4700124049836024.html",
        "title": "清融首发与生涯荣誉公告",
        "publisher": "KPL王者荣耀职业联赛官方微博（新浪原帖镜像）",
        "published_on": "2021-11-05", "accessed_on": "2026-10-04",
        "first_party": True, "retrieval_status": "opened",
        "access_mode": "publisher_post_on_platform_mirror", "mirror_platform": "新浪",
        "note": "赛前公告记载其加入武汉eStarPro及既往荣誉；不用于证明所公告比赛的实际出场。",
    },
    {
        "id": "s-kpl-20220903-final-g1",
        "url": "https://weibo.com/6074356560/4809686279000739",
        "title": "2022 KPL夏季赛总决赛第一局赛后战报",
        "publisher": "KPL王者荣耀职业联赛官方微博",
        "published_on": "2022-09-03", "accessed_on": "2026-10-04",
        "first_party": True, "retrieval_status": "opened",
    },
    {
        "id": "s-kpl-20230402-r2w4d5-g2",
        "url": "https://weibo.com/6074356560/MA88MgGHL",
        "title": "2023 KPL春季赛常规赛第二轮W4D5第二局赛后战报",
        "publisher": "KPL王者荣耀职业联赛官方微博",
        "published_on": "2023-04-02", "accessed_on": "2026-10-04",
        "first_party": True, "retrieval_status": "opened",
    },
    {
        "id": "s-wolves-fengxiao-20250529",
        "url": "https://www.weibo.com/6180100850/5171647163924896",
        "title": "重庆狼队风箫人员变动公告及KPL生涯回顾",
        "publisher": "重庆狼队王者荣耀分部官方微博",
        "published_on": "2025-05-29", "accessed_on": "2026-10-04",
        "first_party": True, "retrieval_status": "opened",
    },
    {
        "id": "s-ttg-fanfan-20250529",
        "url": "https://www.weibo.com/6383293935/5171649613922687",
        "title": "广州TTG帆帆人员变动公告",
        "publisher": "广州TTG王者荣耀分部官方微博",
        "published_on": "2025-05-29", "accessed_on": "2026-10-04",
        "first_party": True, "retrieval_status": "opened",
        "note": "确认帆帆姓名为杨帆及其在广州TTG的人员关系；开团与指挥评价作为俱乐部评价背景。",
    },
    {
        "id": "s-kpl-zhongyi-20250111-challenger-fmvp",
        "url": "https://weibo.com/6074356560/5121741756314089",
        "title": "钟意获得2024年王者荣耀挑战者杯决赛FMVP",
        "publisher": "KPL王者荣耀职业联赛官方微博",
        "published_on": "2025-01-11", "accessed_on": "2026-10-04",
        "first_party": True, "retrieval_status": "opened",
    },
    {
        "id": "s-chaofan-kpl-week-20211109",
        "url": "https://www.chaofan.com/news/lymsrcosp2x9t6l.html",
        "title": "常规赛第二轮第四周王者时刻（转载KPL官方内容）",
        "publisher": "超凡电竞网（页面注明转载自KPL官方微博）",
        "published_on": "2021-11-09", "accessed_on": "2026-10-04",
        "first_party": False, "retrieval_status": "opened",
        "note": "媒体转载，只作诺言、Alan赛场经历的待核线索，不作确认依据。",
    },
    {
        "id": "s-kpl-rookie-board-2023-index",
        "url": "https://weibo.com/6074356560/4937507982019787",
        "title": "2023 KPL常规赛新锐榜候选帖（搜索索引文本）",
        "publisher": "KPL王者荣耀职业联赛官方微博",
        "published_on": "2023-09-02", "accessed_on": "2026-10-04",
        "first_party": True, "retrieval_status": "search_excerpt",
        "note": "原帖正文未能打开，仅搜索索引含规则及候选内容，保留为待核线索。",
    },
]:
    add_source(source)

# Verified 2020 KPL Spring champions and identities, from the post-event official recap.
ts_source = "s-ts-20200613-anniversary"
for pid, display, real_name in [
    ("shenren", "神人", "马腾飞"),
    ("qianshi", "千世", "周宽"),
    ("shijiu", "诗酒", "陈润之"),
    ("adou", "阿豆", "蒋涛"),
]:
    player = add_player(pid, display, ["其他生涯经历待补一手来源。"])
    add_alias(player, real_name, ts_source)
    add_fact(player, make_fact(f"{pid}-identity", "identity", f"{display}对应姓名{real_name}。", [ts_source], real_name=real_name))
    add_fact(player, make_fact(
        f"{pid}-20200613-final", "appearance",
        f"KPL官方六周年回顾将{display}列为TS的2020 KPL春季赛冠军首发。",
        [ts_source], event_date="2020-06-13", season="2020 KPL春季赛",
        competition_type="KPL_league", competition_name="2020 KPL春季赛总决赛",
        match="TS vs 成都AG超玩会", team_at_event="TS",
        evidence_kind="post_event_champion_starting_lineup",
        date_meaning="官方六周年回顾所指比赛日",
    ))
    add_fact(player, make_fact(
        f"{pid}-2020-kpl-title", "award", f"随TS获得2020 KPL春季赛冠军。", [ts_source],
        event_date="2020-06-13", season="2020 KPL春季赛",
        competition_type="KPL_league", competition_name="2020 KPL春季赛",
        team_at_event="TS",
    ))

warm = players["nuanyang"]
add_fact(warm, make_fact(
    "nuanyang-20200613-final-mvp", "award",
    "获得2020 KPL春季赛总决赛MVP；TS击败成都AG超玩会夺冠。", [ts_source],
    event_date="2020-06-13", season="2020 KPL春季赛",
    competition_type="KPL_league", competition_name="2020 KPL春季赛总决赛",
    team_at_event="TS",
))

# KPL's official anniversary timeline names players in the 2017 and 2018 spring champion
# starting lineups. The post is a first-party retrospective, but its individual permalink was
# not available and the 2017 list was truncated after YANG, so only explicitly visible names are used.
historic_source = "s-kpl-historical-finals-2017-2018"
for pid, display, real_name, aliases, year, team, opponent, season in [
    ("hurt", "Hurt", "夏圣钦", ["刺痛", "刺痛Hurt"], 2017, "QGhappy", "AG超玩会", "2017 KPL春季赛"),
    ("yang", "YANG", "万潇阳", ["老阳"], 2017, "QGhappy", "AG超玩会", "2017 KPL春季赛"),
    ("chenxia", "尘夏", "王庆", [], 2018, "Hero久竞", "EDG.M", "2018 KPL春季赛"),
    ("xixi", "兮兮", "张世豪", [], 2018, "Hero久竞", "EDG.M", "2018 KPL春季赛"),
    ("ningzhi", "柠栀", "袁俊", [], 2018, "Hero久竞", "EDG.M", "2018 KPL春季赛"),
    ("chuxin", "最初", None, ["最初ovo"], 2018, "Hero久竞", "EDG.M", "2018 KPL春季赛"),
]:
    player = add_player(pid, display, ["2026-07-08 KPL官方回顾的最初姓名字段被截断，完整实名待一手来源补证。"] if pid == "chuxin" else [])
    if real_name:
        add_alias(player, real_name, historic_source)
        add_fact(player, make_fact(
            f"{pid}-identity", "identity", f"{display}对应姓名{real_name}。",
            [historic_source], real_name=real_name))
    for alias in aliases:
        add_alias(player, alias, historic_source)
    add_fact(player, make_fact(
        f"{pid}-{year}-spring-final-lineup", "appearance",
        f"KPL官方回顾将{display}列入{team}夺得{season}冠军时的冠军首发信息；回顾没有提供具体比赛日。",
        [historic_source], event_year=year, season=f"{season}总决赛",
        competition_type="KPL_league", competition_name=f"{season}总决赛",
        match=f"{team} vs {opponent}", team_at_event=team,
        evidence_kind="post_event_champion_starting_lineup",
        date_meaning="官方回顾只支持赛季和总决赛年份，不填具体比赛日",
    ))
    add_fact(player, make_fact(
        f"{pid}-{year}-spring-title", "award",
        f"KPL官方回顾将{display}列入{team}的{season}冠军首发。",
        [historic_source], event_year=year, season=season,
        competition_type="KPL_league", competition_name=season,
        team_at_event=team,
    ))

for pid, display, year, team, opponent, season in [
    ("cat", "Cat", 2017, "QGhappy", "AG超玩会", "2017 KPL春季赛"),
    ("fly", "Fly", 2017, "QGhappy", "AG超玩会", "2017 KPL春季赛"),
    ("jiucheng", "久诚", 2018, "Hero久竞", "EDG.M", "2018 KPL春季赛"),
]:
    player = players[pid]
    add_fact(player, make_fact(
        f"{pid}-{year}-spring-final-lineup", "appearance",
        f"KPL官方回顾将{display}列入{team}夺得{season}冠军时的冠军首发信息；回顾没有提供具体比赛日。",
        [historic_source], event_year=year, season=f"{season}总决赛",
        competition_type="KPL_league", competition_name=f"{season}总决赛",
        match=f"{team} vs {opponent}", team_at_event=team,
        evidence_kind="post_event_champion_starting_lineup",
        date_meaning="官方回顾只支持赛季和总决赛年份，不填具体比赛日",
    ))

jiucheng = players["jiucheng"]
add_fact(jiucheng, make_fact(
    "jiucheng-2018-spring-final-mvp", "award",
    "KPL官方回顾确认久诚获得2018 KPL春季赛总决赛MVP；Hero久竞击败EDG.M夺冠。",
    [historic_source], event_year=2018, season="2018 KPL春季赛",
    competition_type="KPL_league", competition_name="2018 KPL春季赛总决赛",
    team_at_event="Hero久竞",
))

# The KPL's 2019 spring champion retrospective confirms the five named starters and finals MVP.
spring19_source = "s-kpl-2019-spring-champions-20260615"
for pid, display, real_name in [
    ("alan", "Alan", "王添龙"),
    ("nuoyan", "诺言", "郭桂鑫"),
    ("wuming", "无铭", "张聪"),
]:
    player = add_player(pid, display, ["其他生涯节点待补一手来源。"] if pid == "wuming" else [])
    add_alias(player, real_name, spring19_source)
    add_fact(player, make_fact(
        f"{pid}-2019-spring-identity", "identity", f"{display}对应姓名{real_name}。",
        [spring19_source], real_name=real_name))
    player["unknowns"] = [u for u in player.get("unknowns", []) if "确认实际登场" not in u]
    add_fact(player, make_fact(
        f"{pid}-2019-spring-final-lineup", "appearance",
        f"KPL官方回顾将{display}列入eStarPro夺得2019 KPL春季赛冠军时的冠军首发。",
        [spring19_source], event_year=2019, season="2019 KPL春季赛总决赛",
        competition_type="KPL_league", competition_name="2019 KPL春季赛总决赛",
        match="eStarPro vs RNG.M", team_at_event="eStarPro",
        evidence_kind="post_event_champion_starting_lineup",
        date_meaning="官方回顾只支持赛季和总决赛年份，不填具体比赛日",
    ))
    add_fact(player, make_fact(
        f"{pid}-2019-spring-title", "award",
        f"随eStarPro获得2019 KPL春季赛冠军。", [spring19_source],
        event_year=2019, season="2019 KPL春季赛",
        competition_type="KPL_league", competition_name="2019 KPL春季赛",
        team_at_event="eStarPro",
    ))

cat = players["cat"]
add_fact(cat, make_fact(
    "cat-2019-spring-final-lineup", "appearance",
    "KPL官方回顾将Cat（陈正正）列入eStarPro夺得2019 KPL春季赛冠军时的冠军首发。",
    [spring19_source], event_year=2019, season="2019 KPL春季赛总决赛",
    competition_type="KPL_league", competition_name="2019 KPL春季赛总决赛",
    match="eStarPro vs RNG.M", team_at_event="eStarPro",
    evidence_kind="post_event_champion_starting_lineup",
    date_meaning="官方回顾只支持赛季和总决赛年份，不填具体比赛日",
))
add_fact(cat, make_fact(
    "cat-2019-spring-final-mvp", "award",
    "获得2019 KPL春季赛总决赛MVP；eStarPro击败RNG.M夺冠。", [spring19_source],
    event_year=2019, season="2019 KPL春季赛",
    competition_type="KPL_league", competition_name="2019 KPL春季赛总决赛",
    team_at_event="eStarPro",
))

# Official match reports document actual 2024 league-series actions beyond candidate statistics.
spring24_playoff = "s-kpl-20240510-spring-playoff-d9-g4"
for pid, display, real_name, summary, hero in [
    ("dashuai", "大帅", "孟家俊",
     "KPL官方战报记录大帅在第四局使用鲁班大师，4分钟以大招拉回狄仁杰并配合队友击杀。",
     "鲁班大师"),
    ("guiqi", "归期", "双小钧",
     "KPL官方战报记录归期在第四局使用狂铁，4分50秒闪现进场一换二并拿下双杀。",
     "狂铁"),
]:
    player = add_player(pid, display)
    add_alias(player, real_name, spring24_playoff)
    add_fact(player, make_fact(
        f"{pid}-20240510-spring-playoff-d9-g4", "appearance", summary,
        [spring24_playoff], event_date="2024-05-10",
        season="2024 KPL春季赛季后赛", competition_type="KPL_league",
        competition_name="2024 KPL春季赛季后赛",
        match="成都AG超玩会 3:1 重庆狼队（第四局）",
        team_at_event="成都AG超玩会" if pid == "dashuai" else "重庆狼队",
        hero_at_event=hero,
    ))

annual24 = "s-kpl-20241006-annual-finals-w1d5-g3"
for pid, display, real_name, summary, hero in [
    ("xiangyu", "向鱼", "蔡佑其",
     "KPL官方战报记录向鱼在第三局使用安琪拉，2分20秒蹲草支援并参与拿下一血。",
     "安琪拉"),
    ("daozai", "道崽", "杨凯博",
     "KPL官方战报记录道崽在第三局使用敖隐，5分钟趁上路拉扯先推下一塔，13分30秒强冲高地秒掉西施。",
     "敖隐"),
    ("guiqi", "归期", "双小钧",
     "KPL官方战报记录归期在第三局使用夏洛特，7分30秒突入后排击杀残血大司命。",
     "夏洛特"),
]:
    player = add_player(pid, display)
    add_alias(player, real_name, annual24)
    add_fact(player, make_fact(
        f"{pid}-20241006-annual-final-w1d5-g3", "appearance", summary,
        [annual24], event_date="2024-10-06",
        season="2024 KPL年度总决赛擂台赛", competition_type="KPL_league",
        competition_name="2024 KPL年度总决赛擂台赛",
        match="重庆狼队 2:1 杭州LGD.NBW（第三局）",
        team_at_event="重庆狼队", hero_at_event=hero,
    ))

# Official club anniversary retrospectives independently confirm KPL debut years.
for pid, source_id, summary, debut_year in [
    ("menglan", "s-kpl-menglan-20200919-debut-anniversary",
     "佛山DRG官方六周年回顾明确梦岚于2020年初登KPL赛场。", 2020),
    ("qingyu", "s-kpl-qingyu-20230615-debut-anniversary",
     "北京JDG官方三周年祝贺确认轻语已在2023年登场KPL。", 2023),
    ("wanmo", "s-kpl-wanmo-20240614-debut-anniversary",
     "RW侠官方二周年回顾给出挽墨2024至2026年的KPL登场周年区间，确认其2024年已登场。", 2024),
]:
    player = players[pid]
    add_fact(player, make_fact(
        f"{pid}-{debut_year}-kpl-debut-year", "debut", summary,
        [source_id], event_year=debut_year,
        season=f"{debut_year} KPL赛季", competition_type="KPL_league",
        competition_name="KPL联赛",
        date_meaning="俱乐部周年回顾支持登场年份；不推算具体比赛日期",
    ))

# KPL's official 2025 Spring statistical eligibility threshold confirms Xiaoa's league play.
xiaoa = players["xiaoa"]
add_fact(xiaoa, make_fact(
    "xiaoa-2025-spring-regular-appearance", "appearance",
    "KPL官方将小A（杨荣鑫）列入2025春季赛最佳游走候选，并说明候选人赛季及分路出场率均须达到40%，确认其实际参加该届联赛。",
    ["s-kpl-2025-spring-candidate-stats"], event_year=2025,
    season="2025 KPL春季赛", competition_type="KPL_league",
    competition_name="2025 KPL春季赛",
    stat_scope="KPL官方最佳候选公告；整体及分路登场率门槛均为40%",
))

# The Wolves' official anniversary post states Jinyu's KPL debut year.
jinyu = players["jinyu"]
add_fact(jinyu, make_fact(
    "jinyu-2020-kpl-debut-year", "debut",
    "狼队官方两周年回顾确认今屿在2020年登场KPL。",
    ["s-kpl-jinyu-20201111-debut-anniversary"], event_year=2020,
    season="2020 KPL赛季", competition_type="KPL_league",
    competition_name="KPL联赛",
    date_meaning="俱乐部周年回顾支持登场年份；不据此补具体比赛日期",
))

# Official KPL regular-season performance statistics and a later match milestone independently
# prove appearances for players whose annual-award candidate cards alone were not used as lineup proof.
for pid, real_name, summary in [
    ("dashuai", "孟家俊",
     "KPL官方2024春季赛常规赛统计列其MVP次数11次，并给出S组游走位数据；统计范围含卡位赛，证明其实际参加该届联赛。"),
    ("wuhuan", "朱俊",
     "KPL官方2024春季赛常规赛统计列其S组对抗路个人数据；官方注明排名统计不计登场率低于40%的选手，支持其实际参加该届联赛。"),
]:
    player = players[pid]
    add_alias(player, real_name, "s-kpl-2024-spring-candidate-stats")
    add_fact(player, make_fact(
        f"{pid}-2024-spring-regular-stats", "appearance", summary,
        ["s-kpl-2024-spring-candidate-stats"],
        event_year=2024, season="2024 KPL春季赛常规赛（含卡位赛）",
        competition_type="KPL_league", competition_name="2024 KPL春季赛",
        stat_scope="KPL官方2024春季赛常规赛候选与数据公告",
    ))

guiqi = players["guiqi"]
add_fact(guiqi, make_fact(
    "guiqi-2025-summer-200-win-milestone", "appearance",
    "KPL官方记录归期（双小钧）在2025 KPL夏季赛常规赛第一轮重庆狼队对北京JDG第三局使用夏洛特，达成KPL赛场第200胜局里程碑。",
    ["s-kpl-2025-summer-milestone-timeline"], event_year=2025,
    season="2025 KPL夏季赛常规赛第一轮", competition_type="KPL_league",
    competition_name="2025 KPL夏季赛", match="重庆狼队 vs 北京JDG", game=3,
    team_at_event="重庆狼队", hero_at_event="夏洛特",
    milestone_at_event="KPL赛场第200胜局",
    date_meaning="官方时间线显示发布于6月21日；因单条回顾未独立打开，事件仅精确到赛季和轮次",
))

# Xiao Yi's first KPL season and season-scoped award/statistics.
xiaoyi = add_player("xiaoyi", "小义", ["本名、KPL首秀具体日期和后续转会时间待一手来源补证。"])
add_fact(xiaoyi, make_fact(
    "xiaoyi-2020-kpl-debut-season", "debut",
    "KPL官方称2020 KPL秋季赛是小义从KPLGT来到KPL赛区后的第一个赛季；具体首秀日未确认。",
    ["s-xiaoyi-20201125"], event_year=2020, season="2020 KPL秋季赛",
    competition_type="KPL_league", competition_name="2020 KPL秋季赛",
    date_meaning="赛季范围；不是具体首秀日期",
))
add_fact(xiaoyi, make_fact(
    "xiaoyi-2020-autumn-regular-award", "award",
    "获得2020 KPL秋季赛常规赛最佳选手；官方列其12次MVP、场均4.54次击杀，并记录其支援击杀率和场均10分钟对位经济差。",
    ["s-xiaoyi-20201125"], event_year=2020, season="2020 KPL秋季赛常规赛",
    competition_type="KPL_league", competition_name="2020 KPL秋季赛常规赛",
    team_at_event="DYG", stat_scope="官方公告所述2020 KPL秋季赛常规赛",
))

# 2021 spring final recap documents actual actions for Xinghen and Jiuku.
spring21 = "s-kpl-20210703-spring-final"
xinghen = add_player("xinghen", "星痕", ["真实姓名及更早首秀日期待一手来源补证。"])
add_fact(xinghen, make_fact(
    "xinghen-2021-spring-final", "appearance",
    "KPL官方总决赛回顾记录星痕使用廉颇开团并提供控制。",
    [spring21], event_year=2021, season="2021 KPL春季赛总决赛",
    competition_type="KPL_league", competition_name="2021 KPL春季赛总决赛",
    team_at_event="南京Hero久竞", hero_at_event="廉颇",
))
jiuku = players["jiuku"]
add_fact(jiuku, make_fact(
    "jiuku-2021-spring-final", "appearance",
    "KPL官方总决赛回顾记录久酷使用后羿、伽罗输出，并以黄忠拿到三杀。",
    [spring21], event_year=2021, season="2021 KPL春季赛总决赛",
    competition_type="KPL_league", competition_name="2021 KPL春季赛总决赛",
    team_at_event="南京Hero久竞", hero_at_event="后羿、伽罗、黄忠",
))

# Qingrong's league and cup honors are kept under their separate event classes.
qingrong = players["qingrong"]
add_fact(qingrong, make_fact(
    "qingrong-2020-winter-cup-fmvp", "award",
    "KPL官方回顾确认清融为2020王者荣耀冬季冠军杯FMVP。", ["s-kpl-qingrong-20211105"],
    event_year=2020, competition_type="KPL_cup", competition_name="2020王者荣耀冬季冠军杯",
))
add_fact(qingrong, make_fact(
    "qingrong-2021-spring-final-mvp", "award",
    "KPL官方回顾确认清融获得2021 KPL春季赛总决赛MVP。", ["s-kpl-qingrong-20211105"],
    event_year=2021, season="2021 KPL春季赛",
    competition_type="KPL_league", competition_name="2021 KPL春季赛总决赛",
))
add_fact(qingrong, make_fact(
    "qingrong-2021-joined-estar", "team_history",
    "KPL官方在2021 KPL秋季赛报道中称清融于本赛季加入武汉eStarPro。",
    ["s-kpl-qingrong-20211105"], event_year=2021, season="2021 KPL秋季赛",
    team_at_event="武汉eStarPro", competition_type="KPL_league",
    competition_name="2021 KPL秋季赛",
))

# 2022 summer final game-one official report: direct league appearance evidence and highlight facts.
final22 = "s-kpl-20220903-final-g1"
game22 = [
    ("xiaopang", "小胖", "重庆狼队", "1分50秒以镜击杀狄仁杰拿一血，并参与后续控龙与终结。", "镜"),
    ("fanfan", "帆帆", "重庆狼队", "约6分半以张飞在中路控制三名对手，队友随后越塔发起团战。", "张飞"),
    ("ziyang", "子阳", "武汉eStarPro", "约8分50秒以东皇太一咬住吕布并完成互换。", "东皇太一"),
    ("huahai", "花海", "武汉eStarPro", "约11分半以澜突入后排击杀公孙离。", "澜"),
    ("tanran", "坦然", "武汉eStarPro", "以蒙恬承受团战伤害并参与守家，官方战报记录其在约16分钟团战后帮助队伍零换二。", "蒙恬"),
    ("yaodao", "妖刀", "重庆狼队", "终局以公孙离持续换伞输出，随队推进并赢下第一局。", "公孙离"),
    ("fly", "Fly", "重庆狼队", "使用吕布获得2022 KPL夏季赛总决赛第一局MVP。", "吕布"),
]
for pid, display, team, summary, hero in game22:
    player = add_player(pid, display, ["本名或其他生涯节点待一手来源补证。"] if pid in {"fanfan", "tanran"} else ())
    add_fact(player, make_fact(
        f"{pid}-20220903-final-g1", "appearance", summary, [final22],
        event_date="2022-09-03", season="2022 KPL夏季赛总决赛",
        competition_type="KPL_league", competition_name="2022 KPL夏季赛总决赛",
        match="武汉eStarPro vs 重庆狼队", game=1, team_at_event=team,
        hero_at_event=hero,
    ))

# 2023 spring game-two report establishes Tanran and Dongfang's league appearance.
game23 = "s-kpl-20230402-r2w4d5-g2"
tanran = players["tanran"]
add_fact(tanran, make_fact(
    "tanran-20230402-r2w4d5-g2", "appearance",
    "获得该局MVP；约15分钟以猪八戒抢下暗影暴君，帮助武汉eStarPro打出零换三并推进水晶。",
    [game23], event_date="2023-04-02", season="2023 KPL春季赛常规赛第二轮W4D5",
    competition_type="KPL_league", competition_name="2023 KPL春季赛",
    match="南京Hero久竞 vs 武汉eStarPro", game=2, team_at_event="武汉eStarPro",
    hero_at_event="猪八戒", award_at_event="单局MVP",
))
dongfang = add_player("dongfang", "东方", ["真实姓名和更早生涯节点待一手来源补证。"])
add_fact(dongfang, make_fact(
    "dongfang-20230402-r2w4d5-g2", "appearance",
    "以花木兰在暗影主宰团战中瞬秒孙尚香，随后追击完成三杀。",
    [game23], event_date="2023-04-02", season="2023 KPL春季赛常规赛第二轮W4D5",
    competition_type="KPL_league", competition_name="2023 KPL春季赛",
    match="南京Hero久竞 vs 武汉eStarPro", game=2, team_at_event="南京Hero久竞",
    hero_at_event="花木兰",
))

# Official club retrospective confirms Fengxiao's identity, debut year and league title.
fengxiao = add_player("fengxiao", "风箫", ["更早队伍和转会的完整时间线待补。"])
add_alias(fengxiao, "于翔任", "s-wolves-fengxiao-20250529")
add_fact(fengxiao, make_fact(
    "fengxiao-identity", "identity", "风箫对应姓名于翔任。", ["s-wolves-fengxiao-20250529"], real_name="于翔任"))
add_fact(fengxiao, make_fact(
    "fengxiao-2023-kpl-debut", "debut",
    "重庆狼队官方回顾确认风箫于2023年登上KPL舞台；具体首秀日期待补。",
    ["s-wolves-fengxiao-20250529"], event_year=2023, season="2023 KPL赛季",
    competition_type="KPL_league", competition_name="KPL联赛",
    date_meaning="官方确认的登场年份，不是具体日期",
))
add_fact(fengxiao, make_fact(
    "fengxiao-2023-summer-title", "award",
    "重庆狼队官方确认风箫于2023年登上KPL舞台，并在其效力广州TTG期间获得2023 KPL夏季赛冠军。",
    ["s-wolves-fengxiao-20250529"], event_year=2023, season="2023 KPL夏季赛",
    competition_type="KPL_league", competition_name="2023 KPL夏季赛",
    team_at_event="广州TTG",
))

# A club transfer announcement confirms Fanfan's real name; the KPL final report above independently
# confirms an actual 2022 league appearance and an edit-ready teamfight moment.
fanfan = players["fanfan"]
add_alias(fanfan, "杨帆", "s-ttg-fanfan-20250529")
add_fact(fanfan, make_fact(
    "fanfan-identity", "identity", "帆帆对应姓名杨帆。", ["s-ttg-fanfan-20250529"], real_name="杨帆"))

# 2024 league-day leaderboard confirms Xiaodu's identity and participation.
xiaodu = add_player("xiaodu", "小度", ["KPL首秀日期、赛季前后队伍变动待补。"])
add_alias(xiaodu, "古伟雄", "s-daily-20240331")
add_fact(xiaodu, make_fact("xiaodu-identity", "identity", "小度对应姓名古伟雄。", ["s-daily-20240331"], real_name="古伟雄"))
add_fact(xiaodu, make_fact(
    "xiaodu-20240331-mvp-leader", "appearance",
    "KPL官方赛果记录截至当日，小度以11次MVP与暖阳并列领跑2024春季赛MVP榜。",
    ["s-daily-20240331"], event_date="2024-03-31", season="2024 KPL春季赛",
    competition_type="KPL_league", competition_name="2024 KPL春季赛",
    team_at_event="佛山DRG", stat_scope="截至2024-03-31的赛季累计榜单",
))

# Official retrospective lists cup achievements; keep each trophy explicitly outside the league class.
cup_facts = [
    ("jiucheng", "jiucheng-20190113-winter-cup-fmvp", "久诚", "获得冬季冠军杯FMVP；南京Hero久竞于2019年1月13日捧起首座冰凤凰杯。", "2019-01-13", "王者荣耀冬季冠军杯"),
    ("fly", "fly-20200104-winter-cup-fmvp", "Fly", "随QGhappy获得冬季冠军杯冠军，并取得个人第二个FMVP皮肤。", "2020-01-04", "王者荣耀冬季冠军杯"),
    ("qingrong", "qingrong-20210123-winter-cup-fmvp", "清融", "南京Hero久竞获得冬季冠军杯冠军，清融获得该赛事FMVP。", "2021-01-23", "王者荣耀冬季冠军杯"),
    ("tanran", "tanran-20220115-challenger-cup-fmvp", "坦然", "武汉eStarPro获得挑战者杯冠军，坦然获得FMVP。", "2022-01-15", "王者荣耀挑战者杯"),
    ("ziyang", "ziyang-20221006-challenger-cup-fmvp", "子阳", "武汉eStarPro实现挑战者杯连冠，子阳获得游走位FMVP。", "2022-10-06", "王者荣耀挑战者杯"),
    ("xiaopang", "xiaopang-20231105-challenger-cup-fmvp", "小胖", "重庆狼队获得挑战者杯冠军，小胖获得个人首个FMVP。", "2023-11-05", "王者荣耀挑战者杯"),
]
for pid, fid, display, summary, day, cup_name in cup_facts:
    player = add_player(pid, display)
    add_fact(player, make_fact(
        fid, "award", summary, ["s-kpl-cup-history-20250108"], event_date=day,
        competition_type="KPL_cup", competition_name=cup_name,
    ))

# 2024 Challenger Cup FMVP is also stored as a cup honor, never as a league title.
add_fact(players["zhongyi"], make_fact(
    "zhongyi-20250111-challenger-cup-fmvp", "award",
    "获得2024年王者荣耀挑战者杯决赛FMVP；官方复盘提及其决赛使用镜、大司命、铠、夏侯惇和宫本武藏。",
    ["s-kpl-zhongyi-20250111-challenger-fmvp"], event_date="2025-01-11",
    competition_type="KPL_cup", competition_name="2024年王者荣耀挑战者杯",
    date_meaning="挑战者杯冠名年份为2024，决赛于2025-01-11完成",
))

# Qingrong's 2021 move and distinct earlier honors come from an official pre-match retrospective.
add_fact(players["qingrong"], make_fact(
    "qingrong-2021-joined-estar", "team_history",
    "KPL官方在2021 KPL秋季赛报道中称清融于本赛季加入武汉eStarPro。",
    ["s-kpl-qingrong-20211105"], event_year=2021, season="2021 KPL秋季赛",
    team_at_event="武汉eStarPro", competition_type="KPL_league",
    competition_name="2021 KPL秋季赛",
))

# Keep non-first-party reporting and unopened official snippets visible only as pending leads.
for pid, display in [("nuoyan", "诺言"), ("alan", "Alan")]:
    player = add_player(pid, display, ["需取得KPL或俱乐部一手赛后记录以确认实际登场。"])
    add_fact(player, make_fact(
        f"{pid}-20211109-weekly-highlight-lead", "appearance",
        f"媒体转载的KPL周精彩内容称{display}在该周重回赛场；原始官方战报尚未取得。",
        ["s-chaofan-kpl-week-20211109"], verified=False, event_year=2021,
        season="2021 KPL秋季赛常规赛第二轮第四周",
        competition_type="KPL_league", competition_name="2021 KPL秋季赛",
        date_meaning="转载发布日期，不等同于选手实际出场日期",
    ))

xiaole = add_player("xiaole", "小乐", ["姓名身份、实际登场对局及官方原帖正文待补。"])
add_fact(xiaole, make_fact(
    "xiaole-2023-rookie-board-lead", "debut",
    "KPL官方搜索索引将小乐列入2023年新锐榜，并说明新锐条件涉及当年首次登场；原帖正文未打开，暂不确认其正赛登场。",
    ["s-kpl-rookie-board-2023-index"], verified=False, event_year=2023,
    season="2023 KPL赛季", competition_type="KPL_league",
    competition_name="2023 KPL联赛", date_meaning="待核赛季线索",
))

players_data["players"] = sorted(players.values(), key=lambda p: p["id"])
sources_data["sources"] = sorted(sources.values(), key=lambda s: s["id"])
coverage["as_of"] = "2026-10-04"
coverage["scope"] = "2016年起至2026-10-04，所有历史上在KPL联赛正赛实际登场的选手；生涯事实另按主要官方职业赛事分类。"
coverage["full_roster_verified"] = False
coverage["expected_player_count"] = None
coverage["unresolved_gaps"] = [
    "尚未完成2016年至2026-10-04逐届KPL正赛的逐场实际登场名单枚举与身份去重。",
    "官方动态数据页的完整历史记录尚未取得；注册名单、候选名单和赛前首发不能替代逐局登场记录。",
    "当前补入多为可读取的一手赛果、荣誉或冠军回顾样本，不能据此推定各赛季参赛选手已完整。",
    "早期赛季的ID改名、同名和俱乐部变更仍需逐条核对；部分新记录的本名、首秀日和转会时间未确认。",
    "2025至2026-10-04的逐赛季逐场覆盖、退役状态及当前阵容尚未完成核验。",
]

players_path.write_text(json.dumps(players_data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
sources_path.write_text(json.dumps(sources_data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
coverage_path.write_text(json.dumps(coverage, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"players={len(players_data['players'])}; sources={len(sources_data['sources'])}; as_of={coverage['as_of']}")
