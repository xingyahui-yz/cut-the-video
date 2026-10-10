import copy
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import kb


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.sources = {"sources": [{"id": "s", "url": "https://example.org/match",
            "publisher": "fixture organizer", "title": "fixture result", "first_party": True,
            "retrieval_status": "opened", "published_on": "2025-01-01", "accessed_on": "2026-10-03"}]}
        self.player = {"id": "fixture-a", "display_name": "FixtureA",
            "aliases": [{"text": "共同别名", "source_ids": ["s"]}],
            "facts": [{"id": "a-match", "type": "appearance", "competition_type": "KPL_league",
                "event_date": "2025-01-01", "team_at_event": "旧队伍", "summary": "fixture",
                "verified": True, "source_ids": ["s"]},
                {"id": "a-transfer", "type": "team_history", "event_date": "2026-01-01",
                 "summary": "future fixture transfer", "verified": True, "source_ids": ["s"]}],
            "kpl_appearance": {"status": "verified", "evidence_fact_ids": ["a-match"]}}
        self.players = {"players": [self.player]}
        self.coverage = {"as_of": "2026-10-03", "scope": "fixture", "full_roster_verified": False,
                         "expected_player_count": None, "unresolved_gaps": ["fixture incomplete"]}

    def test_historical_context_omits_future_transfer(self):
        context = kb.make_context(self.player, self.sources, "2025-12-31")
        self.assertEqual([f["id"] for f in context["verified_facts"]], ["a-match"])
        self.assertEqual(context["verified_facts"][0]["team_at_event"], "旧队伍")

    def test_pre_appearance_context_does_not_claim_appearance(self):
        context = kb.make_context(self.player, self.sources, "2024-12-31")
        self.assertFalse(context["appearance_evidence_available_by_context_date"])
        self.assertEqual(context["verified_facts"], [])

    def test_non_league_game_cannot_prove_kpl_membership(self):
        self.player["facts"][0]["competition_type"] = "KPL_cup"
        self.assertTrue(any("non-KPL-main-event" in e for e in kb.validate(self.players, self.sources, self.coverage)))

    def test_annual_finals_match_can_prove_kpl_membership(self):
        self.player["facts"][0]["competition_type"] = "KPL_annual_finals"
        self.assertEqual(kb.validate(self.players, self.sources, self.coverage), [])
        context = kb.make_context(self.player, self.sources, "2025-12-31")
        self.assertTrue(context["appearance_evidence_available_by_context_date"])

    def test_search_excerpt_is_not_verified_evidence(self):
        self.sources["sources"][0]["retrieval_status"] = "search_excerpt"
        self.assertTrue(any("opened first-party" in e for e in kb.validate(self.players, self.sources, self.coverage)))

    def test_alias_collision_returns_both_players(self):
        second = copy.deepcopy(self.player)
        second["id"] = "fixture-b"
        second["display_name"] = "FixtureB"
        self.players["players"].append(second)
        self.assertEqual(len(kb.find_players(self.players, "共同别名")), 2)

    def test_missing_source_is_rejected(self):
        self.player["facts"][0]["source_ids"] = ["missing"]
        self.assertTrue(any("unknown source" in e for e in kb.validate(self.players, self.sources, self.coverage)))

    def test_incomplete_registry_cannot_claim_full_coverage(self):
        self.coverage["full_roster_verified"] = True
        self.assertTrue(any("full coverage" in e for e in kb.validate(self.players, self.sources, self.coverage)))

    def test_current_lookup_still_returns_source_dates(self):
        context = kb.make_context(self.player, self.sources, "2026-10-03")
        self.assertEqual(len(context["verified_facts"]), 2)
        self.assertEqual(context["verified_facts"][0]["citations"][0]["url"], "https://example.org/match")

    def test_year_only_evidence_does_not_invent_month_or_day(self):
        fact = self.player["facts"][0]
        fact.pop("event_date")
        fact["event_year"] = 2025
        self.assertEqual(kb.make_context(self.player, self.sources, "2025-06-01")["verified_facts"], [])
        context = kb.make_context(self.player, self.sources, "2025-12-31")
        self.assertEqual(context["verified_facts"][0]["event_year"], 2025)
        self.assertNotIn("event_date", context["verified_facts"][0])

    def test_export_preserves_human_authored_profile(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "profiles").mkdir()
            manual = root / "profiles" / "fixture-a.md"
            manual.write_text("human note", encoding="utf-8")
            with self.assertRaises(ValueError):
                kb.export_profiles(self.players, self.sources, self.coverage, root)
            self.assertEqual(manual.read_text(encoding="utf-8"), "human note")

    def test_unverified_fact_is_excluded_from_reading_view(self):
        self.player["facts"][1]["verified"] = False
        profile = kb.render_profile(self.player, self.sources)
        self.assertIn("待核线索（不得作为已确认事实）", profile)
        self.assertIn("future fixture transfer", profile)

    def test_team_index_uses_event_team_and_does_not_claim_current_team(self):
        additional = copy.deepcopy(self.player["facts"][0])
        additional["id"] = "a-second-match"
        additional["event_date"] = "2025-01-02"
        self.player["facts"].append(additional)
        rendered = kb.render_team_index(self.players, self.sources, self.coverage)
        self.assertIn("## 旧队伍", rendered)
        self.assertIn("旧队伍", rendered)
        self.assertIn("不代表完整转会史或当前所属", rendered)
        self.assertIn("暂无已核队伍记录", rendered)
        self.assertIn("fixture-a", rendered)
        self.assertEqual(rendered.count("[**FixtureA**]"), 1)
        self.assertIn("a-second-match", rendered)

    def test_secondary_source_stays_a_separate_pending_lead(self):
        secondary = {"id": "media", "url": "https://example.org/report", "publisher": "media",
                     "title": "reported cup result", "first_party": False,
                     "retrieval_status": "opened", "published_on": "2025-01-01", "accessed_on": "2026-10-03"}
        self.sources["sources"].append(secondary)
        lead = {"id": "a-cup-lead", "type": "award", "competition_type": "KPL_cup",
                "competition_name": "fixture cup", "event_year": 2025, "summary": "reported cup award",
                "verified": False, "source_ids": ["media"]}
        self.player["facts"].append(lead)
        self.assertEqual(kb.validate(self.players, self.sources, self.coverage), [])
        context = kb.make_context(self.player, self.sources, "2026-10-03")
        self.assertNotIn(lead["id"], [f["id"] for f in context["verified_facts"]])
        self.assertEqual(context["unverified_source_leads"][0]["verification_status"], "待核线索（不能作为已确认事实）")

    def test_secondary_source_cannot_confirm_a_fact(self):
        self.sources["sources"][0]["first_party"] = False
        self.assertTrue(any("first-party source" in e for e in kb.validate(self.players, self.sources, self.coverage)))

    def test_roster_listing_is_counted_separately_from_actual_appearance(self):
        candidate = {"id": "roster-only", "display_name": "RosterOnly", "aliases": [],
            "facts": [{"id": "roster-only-2025", "type": "roster_listing",
                "roster_kind": "annual_finals_roster", "competition_type": "KPL_annual_finals",
                "event_year": 2025, "season": "2025KPL年度总决赛", "team_at_event": "新队",
                "summary": "列入官方赛季大名单；未由此确认实际登场。",
                "verified": True, "source_ids": ["s"]}],
            "kpl_appearance": {"status": "pending", "evidence_fact_ids": []}}
        self.players["players"].append(candidate)

        cup_only = {"id": "cup-only", "display_name": "CupOnly", "aliases": [],
            "facts": [{"id": "cup-roster-only", "type": "roster_listing",
                "roster_kind": "season_roster", "competition_type": "KPL_cup",
                "event_year": 2025, "season": "2025挑战者杯", "team_at_event": "杯赛队伍",
                "summary": "列入挑战者杯名单。", "verified": True, "source_ids": ["s"]}],
            "kpl_appearance": {"status": "pending", "evidence_fact_ids": []}}
        self.players["players"].append(cup_only)

        self.assertEqual(kb.validate(self.players, self.sources, self.coverage), [])
        context = kb.make_context(candidate, self.sources, "2026-10-03")
        self.assertFalse(context["appearance_evidence_available_by_context_date"])
        counts = kb.stats(self.players, self.sources, self.coverage)
        self.assertEqual(counts["verified_actual_appearance_players"], 1)
        self.assertEqual(counts["known_distinct_kpl_roster_listed_players"], 1)
        self.assertEqual(counts["known_roster_listed_without_verified_appearance"], 1)

    def test_roster_listing_requires_a_source_kind(self):
        fact = {"id": "roster-only", "type": "roster_listing", "event_year": 2025,
                "summary": "listed", "verified": False, "source_ids": ["s"]}
        self.player["facts"].append(fact)
        self.assertTrue(any("valid roster_kind" in e for e in kb.validate(self.players, self.sources, self.coverage)))

    def test_chronicle_candidate_is_returned_only_as_an_unverified_source_lead(self):
        imported = {"source": {"title": "user chronicle", "local_path": "sources/chronicle.md"},
            "player_name_candidates": [{"display_name_as_written": "未建档选手",
                "candidate_status": "new_player_candidate", "mentions": [{
                    "year": 2025, "event_date_as_written": "2025.06.01 / 2025.12.01",
                    "name_variants_as_written": ["文档所写本名"],
                    "claim_lead_unverified": "待核故事线索"}]}]}
        leads = kb.find_chronicle_source_leads("未建档选手", imported, "2026-10-03")
        self.assertEqual(len(leads), 1)
        self.assertEqual(leads[0]["identity_status"], "文本称呼匹配；未核实为同一选手身份")
        self.assertEqual(leads[0]["mentions"][0]["claim_lead_unverified"], "待核故事线索")
        self.assertEqual(kb.find_chronicle_source_leads("未建档选手", imported, "2025-05-01"), [])
        self.assertEqual(kb.find_chronicle_source_leads("未建档选手", imported, "2025-07-01"), [])
        self.assertEqual(len(kb.find_chronicle_source_leads("文档所写本名", imported)), 1)


if __name__ == "__main__":
    unittest.main()
