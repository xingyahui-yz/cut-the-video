"""Source-backed KPL player lookup; Python standard library only."""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import date
import json
from pathlib import Path
import re
import sys
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent
ELIGIBLE_TYPES = {"appearance", "debut"}
FACT_TYPES = ELIGIBLE_TYPES | {"identity", "award", "team_history", "career_event", "roster_listing"}
KPL_MAIN_COMPETITION_TYPES = {"KPL_league", "KPL_annual_finals"}
COMPETITION_TYPES = KPL_MAIN_COMPETITION_TYPES | {"KPL_cup", "other_official_competition"}
ROSTER_KINDS = {"season_roster", "annual_finals_roster", "matchday_roster", "starting_lineup"}


def read_data(root: Path = ROOT) -> tuple[dict, dict, dict]:
    return tuple(json.loads((root / "data" / name).read_text(encoding="utf-8-sig"))
                 for name in ("players.json", "sources.json", "coverage.json"))


def read_chronicle_import(root: Path = ROOT) -> dict | None:
    path = root / "data" / "chronicle_import.json"
    return json.loads(path.read_text(encoding="utf-8-sig")) if path.exists() else None


def iso_date(value: str) -> date:
    return date.fromisoformat(value)


def event_upper_bound(fact: dict) -> date | None:
    if fact.get("event_date"):
        return iso_date(fact["event_date"])
    if fact.get("event_year"):
        return date(fact["event_year"], 12, 31)
    return None


def validate(players: dict, sources: dict, coverage: dict) -> list[str]:
    errors = []
    source_map = {}
    cutoff = iso_date(coverage["as_of"])
    for source in sources["sources"]:
        sid = source["id"]
        if sid in source_map:
            errors.append(f"duplicate source: {sid}")
        source_map[sid] = source
        if urlparse(source["url"]).scheme != "https":
            errors.append(f"non-HTTPS source: {sid}")
        if not source.get("publisher") or not source.get("title"):
            errors.append(f"source lacks publisher/title: {sid}")
        for field in ("published_on", "accessed_on"):
            if source.get(field):
                try:
                    if iso_date(source[field]) > cutoff:
                        errors.append(f"source {field} after cutoff: {sid}")
                except ValueError:
                    errors.append(f"invalid source {field}: {sid}")

    seen_players, seen_facts = set(), set()
    for player in players["players"]:
        pid = player["id"]
        if pid in seen_players:
            errors.append(f"duplicate player: {pid}")
        seen_players.add(pid)
        if not player.get("display_name"):
            errors.append(f"missing display name: {pid}")
        fact_map = {}
        for fact in player["facts"]:
            fid = fact["id"]
            if fid in seen_facts:
                errors.append(f"duplicate fact: {fid}")
            seen_facts.add(fid)
            fact_map[fid] = fact
            if fact["type"] not in FACT_TYPES:
                errors.append(f"unknown fact type: {fid}")
            if fact.get("competition_type") not in (None, *COMPETITION_TYPES):
                errors.append(f"unknown competition type: {fid}")
            if fact["type"] == "roster_listing" and fact.get("roster_kind") not in ROSTER_KINDS:
                errors.append(f"roster listing requires a valid roster_kind: {fid}")
            if not fact.get("summary") or not fact.get("source_ids"):
                errors.append(f"fact lacks summary/evidence: {fid}")
            first_party_evidence = False
            for sid in fact.get("source_ids", []):
                source = source_map.get(sid)
                if not source:
                    errors.append(f"unknown source {sid}: {fid}")
                elif source.get("first_party") is True and source.get("retrieval_status") == "opened":
                    first_party_evidence = True
            if fact.get("verified") and not first_party_evidence:
                errors.append(f"verified fact requires at least one opened first-party source: {fid}")
            if fact.get("event_date"):
                try:
                    if iso_date(fact["event_date"]) > cutoff:
                        errors.append(f"fact after cutoff: {fid}")
                except ValueError:
                    errors.append(f"invalid event date: {fid}")
            elif fact.get("event_year") is not None:
                year = fact["event_year"]
                if not isinstance(year, int) or not 2016 <= year <= cutoff.year:
                    errors.append(f"invalid event year: {fid}")
            elif fact["type"] in ELIGIBLE_TYPES:
                errors.append(f"appearance/debut lacks event date/year: {fid}")
        for alias in player.get("aliases", []):
            if not alias.get("text") or not alias.get("source_ids"):
                errors.append(f"alias lacks text/evidence: {pid}")
            for sid in alias.get("source_ids", []):
                source = source_map.get(sid)
                if not source or not source.get("first_party") or source.get("retrieval_status") != "opened":
                    errors.append(f"alias requires opened first-party evidence: {pid}")
        membership = player["kpl_appearance"]
        if membership["status"] not in {"verified", "pending"}:
            errors.append(f"invalid appearance status: {pid}")
        if membership["status"] == "verified":
            evidence = membership.get("evidence_fact_ids", [])
            if not evidence:
                errors.append(f"verified membership lacks appearance evidence: {pid}")
            for fid in evidence:
                fact = fact_map.get(fid)
                if not fact or not (fact.get("verified") and fact["type"] in ELIGIBLE_TYPES
                                    and fact.get("competition_type") in KPL_MAIN_COMPETITION_TYPES):
                    errors.append(f"non-KPL-main-event/non-appearance membership evidence: {pid}/{fid}")
    if coverage.get("full_roster_verified"):
        expected = coverage.get("expected_player_count")
        verified = sum(p["kpl_appearance"]["status"] == "verified" for p in players["players"])
        if expected is None or expected != verified or coverage.get("unresolved_gaps"):
            errors.append("full coverage requires known total, matching verified count and no gaps")
    return errors


def identifiers(player: dict) -> set[str]:
    return {player["id"].casefold(), player["display_name"].casefold(),
            *(a["text"].casefold() for a in player.get("aliases", []))}


def find_players(players: dict, query: str) -> list[dict]:
    key = query.strip().casefold()
    exact = [p for p in players["players"] if key in identifiers(p)]
    if exact:
        return exact
    if not key:
        return []
    return [p for p in players["players"] if any(key in name for name in identifiers(p))]


def find_chronicle_source_leads(query: str, import_data: dict | None,
                               cutoff: str | None = None) -> list[dict]:
    """Return exact-name leads from the user compilation without asserting identity."""
    if not import_data or not query.strip():
        return []
    key = query.strip().casefold()
    when = iso_date(cutoff) if cutoff else None
    source = import_data.get("source", {})
    results = []
    for entry in import_data.get("player_name_candidates", []):
        names = {entry.get("display_name_as_written", "").casefold()}
        names.update(
            variant.casefold()
            for mention in entry.get("mentions", [])
            for variant in mention.get("name_variants_as_written", [])
        )
        if key not in names:
            continue
        mentions = []
        for mention in entry.get("mentions", []):
            if when:
                raw_date = mention.get("event_date_as_written", "")
                exact_dates = [date(int(y), int(m), int(d)) for y, m, d in
                               re.findall(r"(20\d{2})[./-](\d{1,2})[./-](\d{1,2})", raw_date)]
                if exact_dates:
                    bound = max(exact_dates)
                elif mention.get("year"):
                    bound = date(int(mention["year"]), 12, 31)
                else:
                    bound = None
                if bound and bound > when:
                    continue
            mentions.append(mention)
        if mentions:
            results.append({
                "candidate_name_as_written": entry["display_name_as_written"],
                "identity_status": "文本称呼匹配；未核实为同一选手身份",
                "candidate_status": entry.get("candidate_status"),
                "evidence_status": "用户提供的混合来源编年史；待一手来源核实",
                "source_title": source.get("title"),
                "source_path": source.get("local_path"),
                "mentions": mentions,
            })
    return results


def make_context(player: dict, sources: dict, cutoff: str) -> dict:
    when = iso_date(cutoff)
    source_map = {s["id"]: s for s in sources["sources"]}
    facts, undated = [], []
    for fact in player["facts"]:
        if not fact.get("verified"):
            continue
        upper = event_upper_bound(fact)
        if upper:
            if upper > when:
                continue
        elif fact["type"] != "identity":
            undated.append(fact["id"])
            continue
        facts.append({**fact, "citations": [{"id": sid, "title": source_map[sid]["title"],
                      "publisher": source_map[sid]["publisher"], "url": source_map[sid]["url"],
                      "first_party": source_map[sid].get("first_party") is True}
                     for sid in fact["source_ids"]]})
    facts.sort(key=lambda f: (event_upper_bound(f) or date.min, f["id"]))
    pending_leads = []
    for fact in player["facts"]:
        if fact.get("verified"):
            continue
        upper = event_upper_bound(fact)
        if upper and upper > when:
            continue
        citations = [{"id": sid, "title": source_map[sid]["title"],
                      "publisher": source_map[sid]["publisher"], "url": source_map[sid]["url"],
                      "first_party": source_map[sid].get("first_party") is True}
                     for sid in fact.get("source_ids", []) if sid in source_map]
        pending_leads.append({**fact, "verification_status": "待核线索（不能作为已确认事实）",
                              "citations": citations})
    pending_leads.sort(key=lambda f: (event_upper_bound(f) or date.min, f["id"]))
    source_ids = {sid for f in facts for sid in f["source_ids"]}
    aliases = [a["text"] for a in player.get("aliases", [])
               if any(sid in source_ids for sid in a["source_ids"])]
    eligibility = any(f["type"] in ELIGIBLE_TYPES
                      and f.get("competition_type") in KPL_MAIN_COMPETITION_TYPES
                      for f in facts)
    return {
        "player_id": player["id"], "display_name": player["display_name"],
        "registry_status": player["kpl_appearance"]["status"],
        "known_identifiers": aliases, "context_date": cutoff,
        "appearance_evidence_available_by_context_date": eligibility,
        "verified_facts": facts,
        "unverified_source_leads": pending_leads,
        "unknowns": player.get("unknowns", []),
        "omitted_undated_event_fact_ids": undated,
        "usage_limits": [
            "战队字段只描述对应事件日期；当前战队和录像当日阵容需另外核实。",
            "大名单或首发名单只证明被列入相应名单；除非另有已完成小局的直接证据，不代表实际登场。",
            "此记录中的一次登场或获奖不代表完整生涯统计。",
            "史料只能提供背景；素材中的身份、英雄和具体操作需由画面证据确认。",
            "叙事建议应与已验证事实分开，并引用相关事实ID。",
        ],
    }


def stats(players: dict, sources: dict, coverage: dict) -> dict:
    statuses = Counter(p["kpl_appearance"]["status"] for p in players["players"])
    fact_statuses = Counter("verified" if f.get("verified") else "pending"
                            for p in players["players"] for f in p["facts"])
    years = Counter(str(event_upper_bound(f).year) for p in players["players"] for f in p["facts"]
                    if f.get("verified") and f["type"] in ELIGIBLE_TYPES
                    and f.get("competition_type") in KPL_MAIN_COMPETITION_TYPES
                    and event_upper_bound(f))
    actual_players = {p["id"] for p in players["players"] if p["kpl_appearance"]["status"] == "verified"}
    roster_players_by_kind = {kind: set() for kind in ROSTER_KINDS}
    for player in players["players"]:
        for fact in player["facts"]:
            if (fact.get("verified") and fact["type"] == "roster_listing"
                    and fact.get("competition_type") in KPL_MAIN_COMPETITION_TYPES
                    and fact.get("roster_kind") in ROSTER_KINDS):
                roster_players_by_kind[fact["roster_kind"]].add(player["id"])
    roster_players = set().union(*roster_players_by_kind.values())
    roster_coverage = coverage.get("roster_listing_coverage", {})
    return {
        "scope": coverage["scope"], "as_of": coverage["as_of"],
        "players": len(players["players"]), "verified_players": statuses["verified"],
        "verified_actual_appearance_players": len(actual_players),
        "known_distinct_kpl_roster_listed_players": len(roster_players),
        "kpl_roster_listed_players_by_kind": {
            kind: len(ids) for kind, ids in sorted(roster_players_by_kind.items())
        },
        "known_roster_listed_without_verified_appearance": len(roster_players - actual_players),
        "roster_listing_coverage_complete": roster_coverage.get("complete", False),
        "roster_listing_identity_dedup_complete": roster_coverage.get("identity_dedup_complete", False),
        "roster_listing_coverage_gaps": roster_coverage.get("unresolved_gaps", []),
        "pending_players": statuses["pending"], "sources": len(sources["sources"]),
        "facts": sum(len(p["facts"]) for p in players["players"]),
        "verified_facts": fact_statuses["verified"], "pending_facts": fact_statuses["pending"],
        "appearance_evidence_counts_by_year": dict(sorted(years.items())),
        "expected_player_count": coverage.get("expected_player_count"),
        "full_roster_verified": coverage["full_roster_verified"],
        "unresolved_gaps": coverage["unresolved_gaps"],
    }


def render_profile(player: dict, sources: dict) -> str:
    source_map = {s["id"]: s for s in sources["sources"]}
    status = "已验证正赛登场" if player["kpl_appearance"]["status"] == "verified" else "登场证据待补"
    lines = ["<!-- Generated from data/players.json and data/sources.json -->", f"# {player['display_name']}",
             "", f"内部ID：`{player['id']}`。状态：{status}。", "",
             "姓名／别名（来源可查）：" + "、".join(a["text"] for a in player.get("aliases", [])), "",
             "## 已核实记录", ""]
    for fact in sorted((f for f in player["facts"] if f.get("verified")),
                       key=lambda f: (event_upper_bound(f) or date.min, f["id"])):
        label = fact.get("event_date") or (f"{fact['event_year']}年，具体日期未确定" if fact.get("event_year") else "身份信息")
        lines.extend([f"### {label}", "", fact["summary"], ""])
        details = [f"{title}：{fact[key]}" for key, title in (
            ("season", "赛事"), ("match", "对阵"), ("game", "小局"),
            ("team_at_event", "对应记录中的队伍"), ("hero_at_event", "该局使用英雄"),
            ("roster_kind", "名单类型"),
            ("game_clock_hint", "比赛内时间线索"), ("observed_on", "统计发布截止日期"),
            ("date_meaning", "日期含义")) if fact.get(key) is not None]
        if details:
            lines.extend(["；".join(details) + "。", ""])
        citations = "、".join(f"[{source_map[sid]['publisher']}：{source_map[sid]['title']}]({source_map[sid]['url']})"
                              for sid in fact["source_ids"])
        lines.extend([f"来源：{citations}。事实ID：`{fact['id']}`。", ""])
    pending = [f for f in player["facts"] if not f.get("verified")]
    if pending:
        lines.extend(["## 待核线索（不得作为已确认事实）", ""])
        for fact in sorted(pending, key=lambda f: (event_upper_bound(f) or date.min, f["id"])):
            label = fact.get("event_date") or (f"{fact['event_year']}年，具体日期未确定" if fact.get("event_year") else "日期待核")
            citations = "、".join(f"{source_map[sid]['publisher']}：{source_map[sid]['title']}" for sid in fact["source_ids"])
            lines.extend([f"### {label} · 待核", "", fact["summary"],
                          f"来源线索：{citations}。需补官方或俱乐部一手证据。", f"线索ID：`{fact['id']}`。", ""])
    lines.extend(["## 尚待补充", "", *("- " + x for x in player.get("unknowns", [])), "",
                  "单次英雄使用不等于招牌英雄。历史队伍信息需按比赛日期使用；比赛内时间需与本地录像时间对齐。", ""])
    return "\n".join(lines)


def render_team_index(players: dict, sources: dict, coverage: dict) -> str:
    """Group source-backed event-team facts without implying current membership."""
    source_map = {s["id"]: s for s in sources["sources"]}
    teams: dict[str, list[tuple[dict, dict]]] = {}
    pending_teams: dict[str, list[tuple[dict, dict]]] = {}
    players_with_verified_team: set[str] = set()

    for player in players["players"]:
        for fact in player["facts"]:
            team = fact.get("team_at_event")
            if not team:
                continue
            bucket = teams if fact.get("verified") else pending_teams
            bucket.setdefault(team, []).append((player, fact))
            if fact.get("verified"):
                players_with_verified_team.add(player["id"])

    def order(item: tuple[dict, dict]) -> tuple:
        player, fact = item
        return (event_upper_bound(fact) or date.min, player["display_name"], fact["id"])

    type_labels = {
        "KPL_league": "KPL联赛",
        "KPL_annual_finals": "KPL年度总决赛",
        "KPL_cup": "KPL杯赛",
        "other_official_competition": "其他官方赛事",
    }
    lines = [
        "<!-- Generated from data/players.json and data/sources.json -->",
        "# KPL 选手战队分类（历史赛事记录）", "",
        f"快照日期：{coverage['as_of']}。", "",
        "本页按已核实事实中的“对应记录中的队伍”分类。每条只说明选手在该赛事或统计记录中对应的队伍；同一选手可出现在多个队伍下。队名按来源原样保留，不代表完整转会史或当前所属。未列入队伍表示本库还没有可确认的队伍事实，不表示选手没有战队。", "",
        "各队官方微博入口及名称沿革核验见[官方信息源目录](../../docs/kpl-team-official-weibo.md)；名单人数与实际登场人数的双口径见[核验记录](../../docs/kpl-roster-and-appearance-counting.md)。", "",
    ]

    for team in sorted(teams):
        records = teams[team]
        grouped: dict[str, tuple[dict, list[dict]]] = {}
        for player, fact in records:
            grouped.setdefault(player["id"], (player, []))[1].append(fact)
        def person_order(pair: tuple[dict, list[dict]]) -> tuple:
            player, facts = pair
            first_fact = min(facts, key=lambda f: order((player, f)))
            return order((player, first_fact))

        people = sorted(grouped.values(), key=person_order)
        lines.extend([f"## {team}", "", f"已核实赛事记录涉及 {len(people)} 位选手：", ""])
        for player, facts in people:
            profile_link = f"[**{player['display_name']}**](profiles/{player['id']}.md)"
            lines.append(f"- {profile_link}")
            for fact in sorted(facts, key=lambda f: order((player, f))):
                when = fact.get("event_date") or (f"{fact['event_year']}年" if fact.get("event_year") else "日期未注明")
                competition = type_labels.get(fact.get("competition_type"), "赛事类别未标注")
                event = fact.get("season") or fact.get("competition_name") or competition
                citation_links = "、".join(
                    f"[{source_map[sid]['publisher']}：{source_map[sid]['title']}]({source_map[sid]['url']})"
                    for sid in fact.get("source_ids", []) if sid in source_map
                )
                detail = f"{when} · {event}（{competition}）：{fact['summary']}"
                suffix = f"来源：{citation_links}。事实ID：`{fact['id']}`。" if citation_links else f"事实ID：`{fact['id']}`。"
                lines.append(f"  - {detail} {suffix}")
        lines.append("")

    unassigned = [p for p in players["players"] if p["id"] not in players_with_verified_team]
    lines.extend(["## 暂无已核队伍记录", "", "这些选手在当前库中还没有带队伍字段的已核实事实；这是资料缺口，不是无队伍结论。", ""])
    for player in sorted(unassigned, key=lambda p: p["display_name"]):
        pending = [(fact, fact.get("team_at_event")) for fact in player["facts"]
                   if not fact.get("verified") and fact.get("team_at_event")]
        line = f"- [**{player['display_name']}**](profiles/{player['id']}.md)"
        if pending:
            leads = "、".join(f"{team}（待核，`{fact['id']}`）" for fact, team in pending)
            line += f" — 有未确认队伍线索：{leads}。"
        lines.append(line)
    lines.append("")

    if pending_teams:
        lines.extend(["## 队伍线索（待核，不作为已确认分类）", ""])
        for team in sorted(pending_teams):
            lines.extend([f"### {team}", ""])
            for player, fact in sorted(pending_teams[team], key=order):
                when = fact.get("event_date") or (f"{fact['event_year']}年" if fact.get("event_year") else "日期未注明")
                links = "、".join(
                    f"[{source_map[sid]['publisher']}：{source_map[sid]['title']}]({source_map[sid]['url']})"
                    for sid in fact.get("source_ids", []) if sid in source_map
                )
                lines.append(f"- [{player['display_name']}](profiles/{player['id']}.md) — {when}：{fact['summary']} 来源线索：{links}。事实ID：`{fact['id']}`。")
            lines.append("")
    return "\n".join(lines)


def export_profiles(players: dict, sources: dict, coverage: dict, root: Path = ROOT) -> dict:
    marker = "<!-- Generated from data/players.json and data/sources.json -->"
    outdir = root / "profiles"
    files = {outdir / f"{p['id']}.md": render_profile(p, sources) for p in players["players"]}
    counts = stats(players, sources, coverage)
    lines = [marker, "# KPL 选手知识库", "", f"快照日期：{coverage['as_of']}。", "",
             f"收录 {counts['players']} 位，已验证正赛登场 {counts['verified_players']} 位，登场证据待补 {counts['pending_players']} 位。",
             f"已录入大名单证据的选手档案 {counts['known_distinct_kpl_roster_listed_players']} 位（含未登场者）；跨季身份去重完整：{'是' if counts['roster_listing_identity_dedup_complete'] else '否'}；名单覆盖完整：{'是' if counts['roster_listing_coverage_complete'] else '否'}。",
             f"生涯事实 {counts['facts']} 条：已核 {counts['verified_facts']} 条，待核线索 {counts['pending_facts']} 条。",
             "", "目标范围为全历史KPL联赛及年度总决赛正赛登场选手；当前尚未完成全量枚举，历史总人数未知。", "",
             "待补表示本库证据尚不完整，不表示该选手从未上场。", "",
             "按历史赛事对应队伍浏览：[战队分类索引](TEAMS.md)。", "",
             "各历史队名的官方微博入口：[官方信息源目录](../../docs/kpl-team-official-weibo.md)。大名单与实际登场双口径：[核验记录](../../docs/kpl-roster-and-appearance-counting.md)。[2026年度总决赛名单整理](../../docs/kpl-2026-annual-finals-rosters.md)。", "",
             "用户提供的编年史候选称呼和待核事迹：[导入索引](chronicle-import.md)；这些线索不计入已确认选手或事实。", "",
             "| 选手 | 正赛登场证据 | 已核事实 | 待核线索 |", "| --- | --- | ---: | ---: |"]
    for p in sorted(players["players"], key=lambda p: p["id"]):
        status = "已验证" if p["kpl_appearance"]["status"] == "verified" else "待补"
        verified_count = sum(bool(f.get("verified")) for f in p["facts"])
        pending_count = len(p["facts"]) - verified_count
        lines.append(f"| [{p['display_name']}](profiles/{p['id']}.md) | {status} | {verified_count} | {pending_count} |")
    lines.extend(["", "## 全量覆盖待办", "", *("- " + x for x in coverage["unresolved_gaps"]), ""])
    files[root / "INDEX.md"] = "\n".join(lines)
    files[root / "TEAMS.md"] = render_team_index(players, sources, coverage)
    for path in files:
        if path.exists() and not path.read_text(encoding="utf-8").startswith(marker):
            raise ValueError(f"保留人工文件，拒绝覆盖：{path}")
    outdir.mkdir(parents=True, exist_ok=True)
    for path, content in files.items():
        path.write_text(content, encoding="utf-8")
    return {"profiles_exported": len(players["players"]), "index": str(root / "INDEX.md"),
            "team_index": str(root / "TEAMS.md")}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("validate")
    commands.add_parser("stats")
    commands.add_parser("export")
    lookup = commands.add_parser("lookup")
    lookup.add_argument("name", help="选手ID、已验证别名或知识库内部ID")
    lookup.add_argument("--at", help="背景截止日期 YYYY-MM-DD，默认知识库快照日")
    args = parser.parse_args()
    try:
        players, sources, coverage = read_data()
        errors = validate(players, sources, coverage)
        if errors:
            print(json.dumps({"valid": False, "errors": errors}, ensure_ascii=False, indent=2))
            return 1
        if args.command == "validate":
            result = {"valid": True, **stats(players, sources, coverage)}
        elif args.command == "stats":
            result = stats(players, sources, coverage)
        elif args.command == "export":
            result = export_profiles(players, sources, coverage)
        else:
            matches = find_players(players, args.name)
            if len(matches) != 1:
                if not matches:
                    import_data = read_chronicle_import()
                    cutoff = args.at or coverage["as_of"]
                    if iso_date(cutoff) > iso_date(coverage["as_of"]):
                        raise ValueError("查询日期超过知识库快照日期")
                    leads = find_chronicle_source_leads(args.name, import_data, cutoff)
                    if leads:
                        result = {
                            "query": args.name,
                            "verified_profile_found": False,
                            "registry_status": "未列入已建档选手；编年史候选线索待核",
                            "warning": "下列内容仅供查找原始资料，不证明选手身份、KPL 正赛登场、队伍归属或文中事迹。",
                            "chronicle_source_leads": leads,
                        }
                        print(json.dumps(result, ensure_ascii=False, indent=2))
                        return 0
                print(json.dumps({"error": "not_found" if not matches else "ambiguous_identity",
                                  "candidates": [{"id": p["id"], "name": p["display_name"]}
                                                 for p in matches]}, ensure_ascii=False, indent=2))
                return 2
            cutoff = args.at or coverage["as_of"]
            if iso_date(cutoff) > iso_date(coverage["as_of"]):
                raise ValueError("查询日期超过知识库快照日期")
            result = make_context(matches[0], sources, cutoff)
            result["chronicle_source_leads"] = find_chronicle_source_leads(
                args.name, read_chronicle_import(), cutoff)
        if args.command == "stats":
            imported = read_chronicle_import()
            if imported:
                result["chronicle_import_candidates"] = imported["counts"]
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (ValueError, KeyError, TypeError, OSError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
