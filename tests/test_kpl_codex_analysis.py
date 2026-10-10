import sys
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from kpl_codex_analysis import (
    _run_codex,
    _validate_packet_candidate_ranges,
    apply_selection_decisions,
    merge_packet_results,
    run_analysis,
)


def asset_map():
    return {
        "asset_set": "synthetic-series",
        "team_names": ["北京JDG", "上海EDG.M"],
        "assets": {
            "P1": {"sha256": "a" * 64, "duration_sec": 600, "game_number": 1,
                   "frame_rate_num": 30, "frame_rate_den": 1},
            "P2": {"sha256": "b" * 64, "duration_sec": 600, "game_number": 2,
                   "frame_rate_num": 30, "frame_rate_den": 1},
        },
    }


def candidate(candidate_id, asset_id, start, end, *, identity_status=None):
    participants = []
    if identity_status:
        participants.append({
            "display_name": "测试选手", "team_name": "北京JDG",
            "identity_status": identity_status, "kb_player_id": None,
            "verified_story_facts": [],
        })
    return {
        "candidate_id": candidate_id,
        "asset_id": asset_id,
        "source_start_sec": start,
        "source_end_sec": end,
        "timeline_order": 1,
        "review_status": "needs_review",
        "event_summary": "合成比赛事件",
        "visual_evidence": [{"start_sec": start, "end_sec": min(start + 1, end), "summary": "合成画面"}],
        "commentary_evidence": [],
        "operation_quality_note": "操作衔接清楚",
        "match_significance_note": "改变资源争夺节奏",
        "participants": participants,
        "uncertainties": [],
        "review_reason": "整组选片待复核",
        "exclusion_reason": None,
        "editor_note": None,
    }


class CodexAnalysisMergeTests(unittest.TestCase):
    def test_codex_runner_sends_prompt_on_stdin_and_collects_last_message(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_path = root / "response.json"
            log_prefix = root / "packet-001"
            observed = {}

            def fake_subprocess_run(command, **kwargs):
                observed["command"] = command
                observed["kwargs"] = kwargs
                last_message = Path(command[command.index("--output-last-message") + 1])
                last_message.write_text(json.dumps({"decisions": [], "analysis_notes": []}), encoding="utf-8")
                return SimpleNamespace(returncode=0, stdout="model stdout", stderr="model stderr")

            with patch("kpl_codex_analysis.subprocess.run", side_effect=fake_subprocess_run):
                response = _run_codex(
                    "codex", Path("selection-schema.json"), ["frame-a.jpg", "frame-b.jpg"],
                    "synthetic prompt", output_path, str(log_prefix), root / "codex-home",
                )

            self.assertEqual(response["decisions"], [])
            self.assertEqual(observed["kwargs"]["input"], "synthetic prompt")
            self.assertEqual(observed["kwargs"]["encoding"], "utf-8")
            command = observed["command"]
            self.assertEqual(command[-1], "-")
            self.assertEqual(command[command.index("--image") + 1:command.index("-")], [
                str(Path("frame-a.jpg").resolve()), str(Path("frame-b.jpg").resolve()),
            ])
            self.assertIn("--sandbox", command)
            self.assertEqual((root / "packet-001.stdout.txt").read_text(encoding="utf-8"), "model stdout")
            self.assertEqual((root / "packet-001.stderr.txt").read_text(encoding="utf-8"), "model stderr")

    def test_packet_ranges_require_candidate_and_evidence_timestamps_to_match_packet(self):
        packet = {"packet_id": "P1-002", "start_sec": 300, "end_sec": 600}
        valid_response = {"candidates": [candidate("local", "P1", 590, 620)]}
        _validate_packet_candidate_ranges(valid_response, packet)

        with self.assertRaisesRegex(ValueError, "outside analysis packet"):
            _validate_packet_candidate_ranges(
                {"candidates": [candidate("local", "P1", 290, 320)]}, packet,
            )

        wrong_evidence = candidate("local", "P1", 310, 350)
        wrong_evidence["visual_evidence"] = [{"start_sec": 610, "end_sec": 615, "summary": "越界"}]
        with self.assertRaisesRegex(ValueError, "timestamp 610"):
            _validate_packet_candidate_ranges({"candidates": [wrong_evidence]}, packet)

    def test_merge_uses_canonical_assets_and_chronological_ids(self):
        source_map = asset_map()
        merged = merge_packet_results([
            ("P2", {"candidates": [candidate("local-1", "wrong", 20, 80)], "analysis_notes": []}),
            ("P1", {"candidates": [candidate("local-1", "wrong", 100, 180)], "analysis_notes": []}),
        ], source_map)

        self.assertEqual([row["asset_id"] for row in merged["source_assets"]], ["P1", "P2"])
        self.assertEqual([row["candidate_id"] for row in merged["candidates"]], ["C001", "C002"])
        self.assertEqual([(row["asset_id"], row["timeline_order"]) for row in merged["candidates"]], [
            ("P1", 1), ("P2", 2),
        ])
        self.assertEqual(merged["candidates"][0]["asset_id"], "P1")
        self.assertEqual(merged["candidates"][0]["review_status"], "needs_review")
        self.assertEqual(merged["source_assets"][0]["team_names"], ["北京JDG", "上海EDG.M"])

    def test_apply_selection_sets_reasons_and_chronological_timeline_order(self):
        candidates = [
            candidate("C001", "P1", 100, 200),
            candidate("C002", "P1", 300, 400),
            candidate("C003", "P2", 10, 40),
        ]
        data = {"schema_version": 1, "content_type": "single_match_recap",
                "source_assets": [], "candidates": candidates, "analysis_notes": []}
        decisions = {"decisions": [
            {"candidate_id": "C001", "review_status": "selected", "selection_reason": "关键反打",
             "review_reason": None, "exclusion_reason": None},
            {"candidate_id": "C002", "review_status": "selected", "selection_reason": "决胜团战",
             "review_reason": None, "exclusion_reason": None},
            {"candidate_id": "C003", "review_status": "not_selected", "selection_reason": None,
             "review_reason": None, "exclusion_reason": "与主线关系较弱"},
        ], "analysis_notes": []}

        result = apply_selection_decisions(data, decisions, asset_map())

        self.assertEqual([row["timeline_order"] for row in result["candidates"]], [1, 2, 3])
        self.assertEqual(result["candidates"][0]["editor_note"], "关键反打")
        self.assertEqual(result["candidates"][2]["review_status"], "not_selected")
        self.assertEqual(result["candidates"][2]["exclusion_reason"], "与主线关系较弱")

    def test_apply_selection_requires_exactly_one_decision_per_candidate(self):
        data = {"schema_version": 1, "content_type": "single_match_recap",
                "source_assets": [], "candidates": [candidate("C001", "P1", 0, 120)],
                "analysis_notes": []}
        with self.assertRaisesRegex(ValueError, "exactly once"):
            apply_selection_decisions(data, {"decisions": [], "analysis_notes": []}, asset_map())

    def test_apply_selection_rejects_uncertain_selected_identity(self):
        data = {"schema_version": 1, "content_type": "single_match_recap",
                "source_assets": [], "candidates": [candidate("C001", "P1", 0, 120,
                                                                   identity_status="uncertain")],
                "analysis_notes": []}
        decisions = {"decisions": [{
            "candidate_id": "C001", "review_status": "selected", "selection_reason": "测试",
            "review_reason": None, "exclusion_reason": None,
        }], "analysis_notes": []}
        with self.assertRaisesRegex(ValueError, "uncertain player identity"):
            apply_selection_decisions(data, decisions, asset_map())

    def test_apply_selection_rejects_overlapping_or_out_of_target_timeline(self):
        source_map = asset_map()
        data = {"schema_version": 1, "content_type": "single_match_recap",
                "source_assets": [], "candidates": [
                    candidate("C001", "P1", 0, 150), candidate("C002", "P1", 140, 300),
                ], "analysis_notes": []}
        decisions = {"decisions": [{
            "candidate_id": item["candidate_id"], "review_status": "selected",
            "selection_reason": "主线事件", "review_reason": None, "exclusion_reason": None,
        } for item in data["candidates"]], "analysis_notes": []}
        with self.assertRaisesRegex(ValueError, "overlap"):
            apply_selection_decisions(data, decisions, source_map)

        data["candidates"] = [candidate("C001", "P1", 0, 90)]
        decisions["decisions"] = [{
            "candidate_id": "C001", "review_status": "selected",
            "selection_reason": "主线事件", "review_reason": None, "exclusion_reason": None,
        }]
        with self.assertRaisesRegex(ValueError, "120 and 300"):
            apply_selection_decisions(data, decisions, source_map)

    def test_two_stage_runner_writes_candidate_json_without_calling_codex(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            image_path = root / "frame.jpg"
            image_path.write_bytes(b"synthetic image fixture")
            packet_path = root / "packets.json"
            packet_path.write_text(json.dumps([{
                "packet_id": "P1-001", "asset_id": "P1", "start_sec": 0, "end_sec": 600,
                "frames": [{"timestamp_sec": 0, "path": str(image_path)}],
                "transcript": [],
            }]), encoding="utf-8")
            index_path = root / "index.json"
            index_path.write_text(json.dumps({
                "asset_set": "synthetic-series",
                "assets": [{"asset_id": "P1", "sha256": "a" * 64}],
                "packets": [{
                    "packet_id": "P1-001", "asset_id": "P1", "path": str(packet_path),
                }],
            }), encoding="utf-8")
            map_path = root / "asset-map.json"
            map_path.write_text(json.dumps({
                "asset_set": "synthetic-series", "team_names": ["北京JDG", "上海EDG.M"],
                "assets": {"P1": {
                    "sha256": "a" * 64, "duration_sec": 600, "game_number": 1,
                    "frame_rate_num": 30, "frame_rate_den": 1,
                }},
            }), encoding="utf-8")

            def fake_codex(_exe, schema, _images, _prompt, _output_path, _log_prefix, _home):
                if Path(schema).name == "candidate-schema.json":
                    return {"candidates": [candidate("local", "P1", 10, 130)], "analysis_notes": []}
                return {"decisions": [{
                    "candidate_id": "C001", "review_status": "selected",
                    "selection_reason": "具有前后因果的合成事件",
                    "review_reason": None, "exclusion_reason": None,
                }], "analysis_notes": []}

            args = SimpleNamespace(
                analysis_index=index_path, asset_map=map_path,
                output_dir=root / "codex-result", candidate_schema=Path("candidate-schema.json"),
                selection_schema=Path("selection-schema.json"), codex_exe="codex",
                codex_home=root / "codex-home",
            )
            summary = run_analysis(args, codex_runner=fake_codex)

            self.assertEqual(summary["candidate_count"], 1)
            self.assertEqual(summary["selected_count"], 1)
            timings = json.loads((args.output_dir / "codex-timings.json").read_text(encoding="utf-8"))
            self.assertEqual(len(timings), 2)
            self.assertIn("codex_wait_seconds", summary)
            final = json.loads((args.output_dir / "candidates.json").read_text(encoding="utf-8"))
            self.assertEqual(final["candidates"][0]["review_status"], "selected")
            self.assertEqual(final["candidates"][0]["asset_id"], "P1")


if __name__ == "__main__":
    unittest.main()
