"""Import name and story leads from the user-provided KPL chronicle.

The chronicle is a mixed-source compilation, so this importer keeps its claims
in a separate, explicitly unverified registry. It never promotes them into the
first-party facts in data/players.json.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "sources" / "kpl-chronicle-2016-2026.md"
OUT_JSON = ROOT / "data" / "chronicle_import.json"
OUT_MD = ROOT / "chronicle-import.md"
SOURCE_PATH = "knowledge/kpl/sources/kpl-chronicle-2016-2026.md"
SOURCE_ID = "user-attachment-kpl-chronicle-2016-2026"
FORMAT_STANDARD_PATH = "knowledge/kpl/sources/kpl-chronicle-2016-2026-attachment-2026-10-06.md"
PLAYER_ROLES = (
    "对抗路", "边路", "上单", "发育路", "射手", "打野", "中路", "中单",
    "游走", "辅助", "坦克",
)


def clean_cell(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("**", "").replace("`", "").strip())


def split_names(value: str) -> list[tuple[str, list[str]]]:
    """Split grouped IDs while keeping a parenthetical ID variant attached."""
    names = []
    for part in re.split(r"\s*/\s*", clean_cell(value)):
        part = part.strip()
        if not part:
            continue
        match = re.fullmatch(r"(.+?)[（(]([^（）()]+)[）)]", part)
        if match:
            label = match.group(1).strip()
            variants = [x.strip() for x in re.split(r"[/、,，]", match.group(2)) if x.strip()]
        else:
            label, variants = part, []
        if label:
            names.append((label, variants))
    return names


def table_cells(line: str) -> list[str]:
    return [clean_cell(x) for x in line.strip().strip("|").split("|")]


def heading_year(line: str) -> int | None:
    match = re.match(r"##\s+(20\d{2})\b", line)
    return int(match.group(1)) if match else None


def make_mention(year: int | None, section: str, team: str, role: str, claim: str,
                 line_number: int, mention_type: str = "annual_table") -> dict:
    return {
        "year": year,
        "section": section,
        "team_as_written": team or None,
        "role_as_written": role or None,
        "claim_lead_unverified": claim or None,
        "source_line": line_number,
        "mention_type": mention_type,
        "source_id": SOURCE_ID,
    }


def is_coach(role: str, claim: str) -> bool:
    return "教练" in role or (not any(term in role for term in PLAYER_ROLES)
                              and ("主教练" in claim or "教练" in claim))


def parse_chronicle(path: Path = SOURCE) -> tuple[dict[str, list[dict]], dict[str, list[dict]]]:
    lines = path.read_text(encoding="utf-8-sig").splitlines()
    players: dict[str, list[dict]] = {}
    other_people: dict[str, list[dict]] = {}
    year: int | None = None
    section = ""
    mode: str | None = None
    in_highlights = False
    current_highlight_names: list[tuple[str, list[str]]] = []
    for index, line in enumerate(lines):
        if line.startswith("# 五、"):
            in_highlights = True
            mode = "personal_highlights"
            section = "个人高光时刻总表"
            headers = []
            current_highlight_names = []
        elif line.startswith("# 六、"):
            in_highlights = False
            mode = None
        found_year = heading_year(line)
        if found_year:
            year = found_year
            mode = None
        if line.startswith("# 三、"):
            year = None
            mode = None
            in_highlights = False
        if in_highlights and line.startswith("## "):
            section = f"个人高光时刻总表 · {clean_cell(line.lstrip('# '))}"
            mode = "personal_highlights"
            headers = []
            current_highlight_names = []
            continue
        if line.startswith("### "):
            section = clean_cell(line.lstrip("# "))
            if line.startswith("### 本年登场 / 崛起的代表选手") and year is not None:
                mode = "annual_table"
            elif year in {2024, 2025, 2026} and any(
                token in line for token in ("夺冠五人组", "（2025 赛季）", "（2026 春季赛", "（2026 夏季赛")
            ):
                mode = "roster_table"
            else:
                mode = None
        if not year:
            if not in_highlights:
                continue

        # The personal highlight table includes continued rows with a blank name cell.
        if in_highlights and line.startswith("|"):
            cells = table_cells(line)
            if not cells or set("".join(cells)) <= {"-", ":", " "}:
                continue
            lower = [c.casefold() for c in cells]
            if "选手" in lower:
                headers = lower
                continue
            if not headers or len(cells) < len(headers):
                continue
            cells += [""] * max(0, len(headers) - len(cells))
            row = dict(zip(headers, cells))
            raw_name = row.get("选手", "")
            if raw_name:
                current_highlight_names = split_names(raw_name)
            if not current_highlight_names:
                continue
            date_text = row.get("比赛时间", "")
            event_year_match = re.search(r"20\d{2}", date_text or row.get("赛事 / 对手", ""))
            event_year = int(event_year_match.group(0)) if event_year_match else None
            event = row.get("赛事 / 对手", "")
            highlight = row.get("高光表现", "")
            claim = "；".join(part for part in (date_text, event, highlight) if part)
            for label, variants in current_highlight_names:
                mention = make_mention(
                    event_year, section, "", section.rsplit("· ", 1)[-1], claim,
                    index + 1, "personal_highlight_table",
                )
                mention["event_date_as_written"] = date_text or None
                mention["raw_id_cell"] = raw_name or None
                mention["name_variants_as_written"] = variants
                mention["classification"] = "player_candidate"
                players.setdefault(label, []).append(mention)
            continue

        # Capture each structured yearly or championship-roster table.
        if mode and line.startswith("|"):
            cells = table_cells(line)
            if not cells or set("".join(cells)) <= {"-", ":", " "}:
                continue
            lower = [c.casefold() for c in cells]
            if any(c in {"id", "位置"} for c in lower) and ("id" in lower or "位置" in lower):
                headers = lower
                continue
            if "headers" not in locals() or not headers:
                continue
            if len(cells) < len(headers):
                cells += [""] * (len(headers) - len(cells))
            row = dict(zip(headers, cells))
            if "id" not in row:
                continue
            raw_id = row.get("id", "")
            if not raw_id:
                continue
            role = row.get("位置", "")
            team = row.get("战队", "")
            claim = next((row[k] for k in ("生涯历程", "履历", "备注", "2025 表现") if row.get(k)), "")
            # Keep the complete source row as an audit trail, including uncertain real names.
            row_excerpt = " | ".join(cells)
            target = other_people if is_coach(role, claim) else players
            classification = "coach_or_staff_mention" if target is other_people else (
                "player_candidate" if any(term in role for term in PLAYER_ROLES)
                or mode == "roster_table" else "unclassified_person"
            )
            for label, variants in split_names(raw_id):
                mention = make_mention(year, section, team, role, claim or row_excerpt,
                                       index + 1, mode)
                mention["raw_id_cell"] = raw_id
                mention["name_variants_as_written"] = variants
                mention["classification"] = classification
                target.setdefault(label, []).append(mention)
            continue

        # The 2017 paragraph names the two finalists' other players outside the table.
        if year == 2017 and line.startswith("**对手方**"):
            for team, group in re.findall(r"([^（）()；，:：]+)[（(]([^（）()]+)[）)]", line):
                for raw_name in re.split(r"[、,，;；]", group):
                    raw_name = clean_cell(raw_name)
                    if not raw_name or "教练" in raw_name:
                        continue
                    for label, variants in split_names(raw_name):
                        mention = make_mention(year, section, clean_cell(team), "未注明",
                                               clean_cell(line), index + 1, "finalist_group_note")
                        mention["raw_id_cell"] = raw_name
                        mention["name_variants_as_written"] = variants
                        mention["classification"] = "player_candidate"
                        players.setdefault(label, []).append(mention)

        # A heading begins a new section and therefore invalidates table headers.
        if line.startswith("## ") or line.startswith("### "):
            headers = []

    return players, other_people


def profile_matches(label: str, canonical_players: dict) -> list[str]:
    matches = []
    key = label.casefold()
    for player in canonical_players["players"]:
        names = {player["display_name"].casefold()}
        names.update(alias["text"].casefold() for alias in player.get("aliases", []))
        if key in names:
            matches.append(player["id"])
    return matches


def make_registry(mentions: dict[str, list[dict]], canonical_players: dict) -> list[dict]:
    entries = []
    for label, records in sorted(mentions.items(), key=lambda item: item[0].casefold()):
        matches = profile_matches(label, canonical_players)
        classifications = {r["classification"] for r in records}
        entries.append({
            "display_name_as_written": label,
            "name_key_is_identity_proof": False,
            "candidate_status": (
                "existing_profile_name_match" if len(matches) == 1 else
                "ambiguous_existing_profile_match" if len(matches) > 1 else
                "unclassified_person" if "unclassified_person" in classifications
                and "player_candidate" not in classifications else "new_player_candidate"
            ),
            "existing_profile_ids_by_exact_name_or_verified_alias": matches,
            "source_classifications": sorted(classifications),
            "mentions": sorted(records, key=lambda r: (r["year"] or 0, r["source_line"])),
        })
    return entries


def render_markdown(data: dict) -> str:
    entries = data["player_name_candidates"]
    counts = data["counts"]
    lines = [
        "<!-- Generated by import_chronicle.py; claims below are unverified leads. -->",
        "# KPL 十年编年史：选手称呼候选与事迹线索",
        "",
        f"来源快照：[{data['source']['title']}](sources/kpl-chronicle-2016-2026.md)。导入日期：{data['imported_on']}。",
        "",
        f"当前内容组织标准参考：[{data['format_standard_reference']['title']}](sources/{Path(data['format_standard_reference']['local_path']).name})。该附件只作为编年史结构参考，末尾在个人高光表中途截断，不用于替换完整旧版或删除候选线索。",
        "",
        "本页把用户提供的混合来源编年史转成姓名候选和事迹线索，方便先登记、再核证。文档自身列有多项争议和待核事项，因此本页**不是已确认事实**；不能用来确认选手身份、KPL 正赛登场、战队归属或荣誉，也不能直接用于旁白。只有联盟、俱乐部或选手本人一手来源核实后，才写入正式档案。",
        "",
        "来源覆盖限制：2016–2023 的章节使用‘代表选手’名单；2024–2026 主要是夺冠/决赛队伍阵容。它不是逐赛季官方大名单或逐场登场名册，未提到某人不代表此人未参赛，列出某人也不证明其参加过 KPL 正赛。相同称呼按文本合并仅用于检索，**不代表已判定为同一身份**。",
        "",
        f"导入统计：{counts['unique_name_labels']} 个不同人物称呼，其中 {counts['player_candidate_name_labels']} 个是选手候选；{counts['exact_existing_profile_matches']} 个与现有档案显示名或已核别名精确匹配，{counts['new_or_unmatched_player_candidate_labels']} 个尚无精确档案匹配，{counts['unclassified_person_name_labels']} 个身份类别待分；另有 {counts['coach_or_staff_name_labels']} 个教练/工作人员称呼单独保存，不计入选手候选。",
        "",
        "## 选手候选与原文线索",
        "",
    ]
    for entry in entries:
        label = entry["display_name_as_written"]
        status = entry["candidate_status"]
        if status == "existing_profile_name_match":
            profile = entry["existing_profile_ids_by_exact_name_or_verified_alias"][0]
            status_label = f"现有档案精确匹配：`{profile}`"
        elif status == "ambiguous_existing_profile_match":
            status_label = "现有档案匹配不唯一，待查"
        elif status == "unclassified_person":
            status_label = "身份类别待分；不计作选手"
        else:
            status_label = "新增候选；KPL 身份待一手来源核实"
        lines.extend([f"### {label}", "", f"登记状态：{status_label}。", ""])
        for record in entry["mentions"]:
            team = record.get("team_as_written") or "文档未注明"
            role = record.get("role_as_written") or "文档未注明"
            claim = (record.get("claim_lead_unverified") or "文档仅列出称呼，未附经历文字")
            claim = claim.replace("|", "／").replace("\n", " ")
            lines.append(
                f"- {record['year'] or '年份未解析'} · {record['section']} · 战队栏：{team} · 位置栏：{role} · "
                f"待核线索：{claim} · 原文第 {record['source_line']} 行。"
            )
        lines.append("")
    teams: dict[str, dict[str, set[int]]] = {}
    for entry in entries:
        for record in entry["mentions"]:
            team = record.get("team_as_written") or "文档未注明战队"
            years = teams.setdefault(team, {}).setdefault(entry["display_name_as_written"], set())
            if record.get("year"):
                years.add(record["year"])
    lines.extend(["## 按文档战队栏分类（线索，待核）", "",
                  "以下保留原文的战队写法，不合并历史队名，也不表示完整转会史或已确认效力。", ""])
    for team in sorted(teams, key=str.casefold):
        lines.extend([f"### {team}", ""])
        for name, years in sorted(teams[team].items(), key=lambda item: item[0].casefold()):
            year_text = "、".join(str(y) for y in sorted(years)) if years else "年份未解析"
            lines.append(f"- {name}（文档年份：{year_text}）")
        lines.append("")
    lines.extend(["## 教练与工作人员称呼（不进入选手候选）", "",
                  "文档在对应行明确标为教练/主教练的称呼保存在导入 JSON 的 `non_player_mentions`。这只是本次资料里的角色分类；若要收录其作为选手的历史经历，仍需另找一手参赛证据。", ""])
    return "\n".join(lines)


def main() -> int:
    if not SOURCE.exists():
        raise SystemExit(f"Source file missing: {SOURCE}")
    source_players, other_people = parse_chronicle()
    canonical_players = json.loads((ROOT / "data" / "players.json").read_text(encoding="utf-8-sig"))
    entries = make_registry(source_players, canonical_players)
    player_entries = [e for e in entries if "player_candidate" in e["source_classifications"]]
    exact_matches = sum(e["candidate_status"] == "existing_profile_name_match" for e in player_entries)
    unclassified_entries = [e for e in entries if e["candidate_status"] == "unclassified_person"]
    data = {
        "schema_version": 1,
        "imported_on": "2026-10-04",
        "source": {
            "id": SOURCE_ID,
            "title": "KPL 十年编年史（2016–2026）",
            "source_type": "user_provided_mixed_source_compilation",
            "evidence_status": "unverified_lead_only",
            "local_path": SOURCE_PATH,
            "document_as_of": "2026-10-04",
        },
        "format_standard_reference": {
            "title": "KPL 十年编年史（2026-10-06 附件）",
            "local_path": FORMAT_STANDARD_PATH,
            "document_as_of": "2026-10-04",
            "use": "content organization and story structure only; not factual evidence",
            "completeness": "partial; the attachment ends partway through the player highlights table",
        },
        "scope_note": "This compilation is representative and selective; it is not a complete league roster or match-appearance ledger.",
        "identity_deduplication": "Exact-name grouping only. It does not prove identity, aliases, or that mentions across seasons refer to the same person.",
        "counts": {
            "unique_name_labels": len(entries),
            "player_candidate_name_labels": len(player_entries),
            "exact_existing_profile_matches": exact_matches,
            "new_or_unmatched_player_candidate_labels": len(player_entries) - exact_matches,
            "unclassified_person_name_labels": len(unclassified_entries),
            "coach_or_staff_name_labels": len(other_people),
            "player_candidate_mentions": sum(len(e["mentions"]) for e in player_entries),
            "unclassified_person_mentions": sum(len(e["mentions"]) for e in unclassified_entries),
            "coach_or_staff_mentions": sum(len(v) for v in other_people.values()),
        },
        "player_name_candidates": entries,
        "non_player_mentions": [
            {"display_name_as_written": name, "mentions": sorted(records, key=lambda r: (r["year"] or 0, r["source_line"]))}
            for name, records in sorted(other_people.items(), key=lambda item: item[0].casefold())
        ],
    }
    OUT_JSON.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    OUT_MD.write_text(render_markdown(data), encoding="utf-8")
    print(json.dumps({"json": str(OUT_JSON), "markdown": str(OUT_MD), **data["counts"]}, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
