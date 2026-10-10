import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET


REPO_ROOT = Path(__file__).resolve().parents[1]
EXPORTER = REPO_ROOT / "tools" / "kpl_timeline.py"


class TimelineExportCliTests(unittest.TestCase):
    def test_export_keeps_reviewable_clips_in_order_with_original_audio(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            media_paths = {
                "P1": root / "game-1.mp4",
                "P2": root / "game-2.mp4",
            }
            media_bytes = {
                "P1": b"synthetic media one",
                "P2": b"synthetic media two",
            }
            for asset_id, path in media_paths.items():
                path.write_bytes(media_bytes[asset_id])

            def source_asset(asset_id):
                return {
                    "asset_id": asset_id,
                    "sha256": hashlib.sha256(media_bytes[asset_id]).hexdigest(),
                    "duration_sec": 600.0,
                    "game_number": int(asset_id[-1]),
                    "team_names": ["北京JDG", "上海EDG.M"],
                }

            candidates = {
                "schema_version": 1,
                "content_type": "single_match_recap",
                "source_assets": [source_asset("P1"), source_asset("P2")],
                "analysis_notes": [],
                "candidates": [
                    {
                        "candidate_id": "C01",
                        "asset_id": "P1",
                        "source_start_sec": 60,
                        "source_end_sec": 150,
                        "timeline_order": 1,
                        "review_status": "selected",
                        "event_summary": "开局团战后的反打",
                        "visual_evidence": [{"start_sec": 65, "end_sec": 75, "summary": "合成画面证据"}],
                        "commentary_evidence": [],
                        "operation_quality_note": "技能衔接清晰",
                        "match_significance_note": "反打改变了资源争夺局势",
                        "participants": [{
                            "display_name": "选手甲", "team_name": "北京JDG",
                            "identity_status": "confirmed", "kb_player_id": None,
                            "verified_story_facts": [],
                        }],
                        "uncertainties": [],
                        "review_reason": None,
                        "exclusion_reason": None,
                        "editor_note": None,
                    },
                    {
                        "candidate_id": "C02",
                        "asset_id": "P2",
                        "source_start_sec": 120,
                        "source_end_sec": 210,
                        "timeline_order": 2,
                        "review_status": "needs_review",
                        "event_summary": "终局前的高地推进",
                        "visual_evidence": [],
                        "commentary_evidence": [{"start_sec": 121, "end_sec": 130, "summary": "合成解说证据"}],
                        "operation_quality_note": "需要复核细节",
                        "match_significance_note": "可能影响最终胜负",
                        "participants": [],
                        "uncertainties": ["选手身份待核"],
                        "review_reason": "身份与事件结果需要人工确认",
                        "exclusion_reason": None,
                        "editor_note": None,
                    },
                    {
                        "candidate_id": "C03",
                        "asset_id": "P1",
                        "source_start_sec": 300,
                        "source_end_sec": 330,
                        "timeline_order": 3,
                        "review_status": "not_selected",
                        "event_summary": "不进入时间线的候选",
                        "visual_evidence": [{"start_sec": 301, "end_sec": 305, "summary": "合成画面证据"}],
                        "commentary_evidence": [],
                        "operation_quality_note": "无特别操作",
                        "match_significance_note": "对比赛结果影响有限",
                        "participants": [],
                        "uncertainties": [],
                        "review_reason": None,
                        "exclusion_reason": "与已选内容相比信息重复",
                        "editor_note": None,
                    },
                ],
            }
            asset_map = {
                "assets": {
                    asset_id: {
                        "path": str(path),
                        "sha256": hashlib.sha256(media_bytes[asset_id]).hexdigest(),
                        "duration_sec": 600.0,
                        "width": 1920,
                        "height": 1080,
                        "frame_rate_num": 30,
                        "frame_rate_den": 1,
                        "audio_channels": 2,
                        "audio_sample_rate": 48000,
                    }
                    for asset_id, path in media_paths.items()
                }
            }
            candidates_path = root / "candidates.json"
            asset_map_path = root / "asset-map.json"
            output_path = root / "review-timeline.fcpxml"
            candidates_path.write_text(json.dumps(candidates, ensure_ascii=False), encoding="utf-8")
            asset_map_path.write_text(json.dumps(asset_map, ensure_ascii=False), encoding="utf-8")

            result = subprocess.run(
                [
                    sys.executable,
                    str(EXPORTER),
                    "--candidates", str(candidates_path),
                    "--asset-map", str(asset_map_path),
                    "--output", str(output_path),
                    "--project-name", "KPL 首轮合成验收",
                ],
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            root_xml = ET.parse(output_path).getroot()
            sequence = root_xml.find(".//sequence")
            self.assertEqual(root_xml.get("version"), "1.10")
            self.assertEqual(sequence.get("duration"), "180s")
            self.assertEqual(root_xml.find(".//resources/format").get("name"), "FFVideoFormat1080p30")
            self.assertEqual(sequence.get("audioRate"), "48k")
            clips = sequence.findall("./spine/asset-clip")
            self.assertEqual([clip.get("name") for clip in clips], ["C01｜开局团战后的反打", "C02｜终局前的高地推进"])
            self.assertEqual([clip.get("offset") for clip in clips], ["0s", "90s"])
            self.assertTrue(all(clip.get("srcEnable") == "all" for clip in clips))
            self.assertIn("needs_review", clips[1].findtext("note", ""))
            self.assertIn("选手甲", clips[0].findtext("note", ""))
            self.assertNotIn("C03", ET.tostring(root_xml, encoding="unicode"))

    def test_export_rejects_clip_past_source_duration(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            media_path = root / "game.mp4"
            media_bytes = b"synthetic media"
            media_path.write_bytes(media_bytes)
            digest = hashlib.sha256(media_bytes).hexdigest()

            def candidate(candidate_id, start, end, order):
                return {
                    "candidate_id": candidate_id,
                    "asset_id": "P1",
                    "source_start_sec": start,
                    "source_end_sec": end,
                    "timeline_order": order,
                    "review_status": "selected",
                    "event_summary": "合成比赛片段",
                    "visual_evidence": [{"start_sec": start, "end_sec": start + 1, "summary": "合成证据"}],
                    "commentary_evidence": [],
                    "operation_quality_note": "合成描述",
                    "match_significance_note": "合成描述",
                    "participants": [],
                    "uncertainties": [],
                    "review_reason": None,
                    "exclusion_reason": None,
                    "editor_note": None,
                }

            candidates = {
                "schema_version": 1,
                "content_type": "single_match_recap",
                "source_assets": [{
                    "asset_id": "P1", "sha256": digest, "duration_sec": 600,
                    "game_number": 1, "team_names": ["北京JDG", "上海EDG.M"],
                }],
                "analysis_notes": [],
                "candidates": [candidate("C01", 590, 670, 1), candidate("C02", 0, 100, 2)],
            }
            asset_map = {
                "assets": {
                    "P1": {
                        "path": str(media_path), "sha256": digest, "duration_sec": 600,
                        "width": 1920, "height": 1080, "frame_rate_num": 30,
                        "frame_rate_den": 1, "audio_channels": 2, "audio_sample_rate": 48000,
                    }
                }
            }
            candidates_path = root / "candidates.json"
            asset_map_path = root / "asset-map.json"
            output_path = root / "review-timeline.fcpxml"
            candidates_path.write_text(json.dumps(candidates, ensure_ascii=False), encoding="utf-8")
            asset_map_path.write_text(json.dumps(asset_map, ensure_ascii=False), encoding="utf-8")

            result = subprocess.run(
                [sys.executable, str(EXPORTER), "--candidates", str(candidates_path),
                 "--asset-map", str(asset_map_path), "--output", str(output_path)],
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("source duration", result.stderr)
            self.assertFalse(output_path.exists())

    def test_export_rejects_timeline_outside_user_length_target(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            media_path = root / "game.mp4"
            media_bytes = b"synthetic media"
            media_path.write_bytes(media_bytes)
            digest = hashlib.sha256(media_bytes).hexdigest()
            candidate = {
                "candidate_id": "C01", "asset_id": "P1", "source_start_sec": 10,
                "source_end_sec": 110, "timeline_order": 1, "review_status": "selected",
                "event_summary": "合成比赛片段",
                "visual_evidence": [{"start_sec": 20, "end_sec": 25, "summary": "合成证据"}],
                "commentary_evidence": [], "operation_quality_note": "合成描述",
                "match_significance_note": "合成描述", "participants": [], "uncertainties": [],
                "review_reason": None, "exclusion_reason": None, "editor_note": None,
            }
            candidates = {
                "schema_version": 1, "content_type": "single_match_recap",
                "source_assets": [{"asset_id": "P1", "sha256": digest, "duration_sec": 600,
                                   "game_number": 1, "team_names": ["北京JDG", "上海EDG.M"]}],
                "candidates": [candidate], "analysis_notes": [],
            }
            asset_map = {"assets": {"P1": {
                "path": str(media_path), "sha256": digest, "duration_sec": 600,
                "width": 1920, "height": 1080, "frame_rate_num": 30,
                "frame_rate_den": 1, "audio_channels": 2, "audio_sample_rate": 48000,
            }}}
            candidates_path = root / "candidates.json"
            asset_map_path = root / "asset-map.json"
            output_path = root / "review-timeline.fcpxml"
            candidates_path.write_text(json.dumps(candidates, ensure_ascii=False), encoding="utf-8")
            asset_map_path.write_text(json.dumps(asset_map, ensure_ascii=False), encoding="utf-8")

            result = subprocess.run(
                [sys.executable, str(EXPORTER), "--candidates", str(candidates_path),
                 "--asset-map", str(asset_map_path), "--output", str(output_path)],
                capture_output=True, text=True, check=False,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("120", result.stderr)
            self.assertFalse(output_path.exists())

    def test_export_rejects_review_candidate_without_review_reason(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            media_path = root / "game.mp4"
            media_bytes = b"synthetic media"
            media_path.write_bytes(media_bytes)
            digest = hashlib.sha256(media_bytes).hexdigest()
            candidate = {
                "candidate_id": "C01", "asset_id": "P1", "source_start_sec": 0,
                "source_end_sec": 120, "timeline_order": 1, "review_status": "needs_review",
                "event_summary": "合成待审片段",
                "visual_evidence": [{"start_sec": 1, "end_sec": 2, "summary": "合成证据"}],
                "commentary_evidence": [], "operation_quality_note": "合成描述",
                "match_significance_note": "合成描述", "participants": [], "uncertainties": [],
                "review_reason": None, "exclusion_reason": None, "editor_note": None,
            }
            candidates = {
                "schema_version": 1, "content_type": "single_match_recap",
                "source_assets": [{"asset_id": "P1", "sha256": digest, "duration_sec": 600,
                                   "game_number": 1, "team_names": ["北京JDG", "上海EDG.M"]}],
                "candidates": [candidate], "analysis_notes": [],
            }
            asset_map = {"assets": {"P1": {
                "path": str(media_path), "sha256": digest, "duration_sec": 600,
                "width": 1920, "height": 1080, "frame_rate_num": 30,
                "frame_rate_den": 1, "audio_channels": 2, "audio_sample_rate": 48000,
            }}}
            candidates_path = root / "candidates.json"
            asset_map_path = root / "asset-map.json"
            output_path = root / "review-timeline.fcpxml"
            candidates_path.write_text(json.dumps(candidates, ensure_ascii=False), encoding="utf-8")
            asset_map_path.write_text(json.dumps(asset_map, ensure_ascii=False), encoding="utf-8")

            result = subprocess.run(
                [sys.executable, str(EXPORTER), "--candidates", str(candidates_path),
                 "--asset-map", str(asset_map_path), "--output", str(output_path)],
                capture_output=True, text=True, check=False,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("review reason", result.stderr)
            self.assertFalse(output_path.exists())

    def test_export_rejects_candidate_without_visual_or_commentary_evidence(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            media_path = root / "game.mp4"
            media_bytes = b"synthetic media"
            media_path.write_bytes(media_bytes)
            digest = hashlib.sha256(media_bytes).hexdigest()
            candidate = {
                "candidate_id": "C01", "asset_id": "P1", "source_start_sec": 0,
                "source_end_sec": 120, "timeline_order": 1, "review_status": "selected",
                "event_summary": "无依据候选",
                "visual_evidence": [], "commentary_evidence": [],
                "operation_quality_note": "合成描述", "match_significance_note": "合成描述",
                "participants": [], "uncertainties": [], "review_reason": None,
                "exclusion_reason": None, "editor_note": None,
            }
            candidates = {
                "schema_version": 1, "content_type": "single_match_recap",
                "source_assets": [{"asset_id": "P1", "sha256": digest, "duration_sec": 600,
                                   "game_number": 1, "team_names": ["北京JDG", "上海EDG.M"]}],
                "candidates": [candidate], "analysis_notes": [],
            }
            asset_map = {"assets": {"P1": {
                "path": str(media_path), "sha256": digest, "duration_sec": 600,
                "width": 1920, "height": 1080, "frame_rate_num": 30,
                "frame_rate_den": 1, "audio_channels": 2, "audio_sample_rate": 48000,
            }}}
            candidates_path = root / "candidates.json"
            asset_map_path = root / "asset-map.json"
            output_path = root / "review-timeline.fcpxml"
            candidates_path.write_text(json.dumps(candidates, ensure_ascii=False), encoding="utf-8")
            asset_map_path.write_text(json.dumps(asset_map, ensure_ascii=False), encoding="utf-8")

            result = subprocess.run(
                [sys.executable, str(EXPORTER), "--candidates", str(candidates_path),
                 "--asset-map", str(asset_map_path), "--output", str(output_path)],
                capture_output=True, text=True, check=False,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("evidence", result.stderr.lower())
            self.assertFalse(output_path.exists())

    def test_export_rounds_source_trims_outward_to_video_frames(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            media_path = root / "game.mp4"
            media_bytes = b"synthetic media"
            media_path.write_bytes(media_bytes)
            digest = hashlib.sha256(media_bytes).hexdigest()
            candidate = {
                "candidate_id": "C01", "asset_id": "P1", "source_start_sec": 0.001,
                "source_end_sec": 120.001, "timeline_order": 1, "review_status": "selected",
                "event_summary": "合成比赛片段",
                "visual_evidence": [{"start_sec": 1, "end_sec": 2, "summary": "合成证据"}],
                "commentary_evidence": [], "operation_quality_note": "合成描述",
                "match_significance_note": "合成描述", "participants": [], "uncertainties": [],
                "review_reason": None, "exclusion_reason": None, "editor_note": None,
            }
            candidates = {
                "schema_version": 1, "content_type": "single_match_recap",
                "source_assets": [{"asset_id": "P1", "sha256": digest, "duration_sec": 600,
                                   "game_number": 1, "team_names": ["北京JDG", "上海EDG.M"]}],
                "candidates": [candidate], "analysis_notes": [],
            }
            asset_map = {"assets": {"P1": {
                "path": str(media_path), "sha256": digest, "duration_sec": 600,
                "width": 1920, "height": 1080, "frame_rate_num": 30,
                "frame_rate_den": 1, "audio_channels": 2, "audio_sample_rate": 48000,
            }}}
            candidates_path = root / "candidates.json"
            asset_map_path = root / "asset-map.json"
            output_path = root / "review-timeline.fcpxml"
            candidates_path.write_text(json.dumps(candidates, ensure_ascii=False), encoding="utf-8")
            asset_map_path.write_text(json.dumps(asset_map, ensure_ascii=False), encoding="utf-8")

            result = subprocess.run(
                [sys.executable, str(EXPORTER), "--candidates", str(candidates_path),
                 "--asset-map", str(asset_map_path), "--output", str(output_path)],
                capture_output=True, text=True, check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            root_xml = ET.parse(output_path).getroot()
            clip = root_xml.find(".//asset-clip")
            self.assertEqual(clip.get("start"), "0s")
            self.assertEqual(clip.get("duration"), "3601/30s")
            self.assertEqual(root_xml.find(".//sequence").get("duration"), "3601/30s")

    def test_export_does_not_overwrite_an_existing_timeline(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            media_path = root / "game.mp4"
            media_bytes = b"synthetic media"
            media_path.write_bytes(media_bytes)
            digest = hashlib.sha256(media_bytes).hexdigest()
            candidate = {
                "candidate_id": "C01", "asset_id": "P1", "source_start_sec": 0,
                "source_end_sec": 120, "timeline_order": 1, "review_status": "selected",
                "event_summary": "合成比赛片段",
                "visual_evidence": [{"start_sec": 1, "end_sec": 2, "summary": "合成证据"}],
                "commentary_evidence": [], "operation_quality_note": "合成描述",
                "match_significance_note": "合成描述", "participants": [], "uncertainties": [],
                "review_reason": None, "exclusion_reason": None, "editor_note": None,
            }
            candidates = {
                "schema_version": 1, "content_type": "single_match_recap",
                "source_assets": [{"asset_id": "P1", "sha256": digest, "duration_sec": 600,
                                   "game_number": 1, "team_names": ["北京JDG", "上海EDG.M"]}],
                "candidates": [candidate], "analysis_notes": [],
            }
            asset_map = {"assets": {"P1": {
                "path": str(media_path), "sha256": digest, "duration_sec": 600,
                "width": 1920, "height": 1080, "frame_rate_num": 30,
                "frame_rate_den": 1, "audio_channels": 2, "audio_sample_rate": 48000,
            }}}
            candidates_path = root / "candidates.json"
            asset_map_path = root / "asset-map.json"
            output_path = root / "review-timeline.fcpxml"
            original_output = b"preserve the earlier timeline"
            output_path.write_bytes(original_output)
            candidates_path.write_text(json.dumps(candidates, ensure_ascii=False), encoding="utf-8")
            asset_map_path.write_text(json.dumps(asset_map, ensure_ascii=False), encoding="utf-8")

            result = subprocess.run(
                [sys.executable, str(EXPORTER), "--candidates", str(candidates_path),
                 "--asset-map", str(asset_map_path), "--output", str(output_path)],
                capture_output=True, text=True, check=False,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("already exists", result.stderr.lower())
            self.assertEqual(output_path.read_bytes(), original_output)

    def test_export_rejects_source_hash_mismatch(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            media_path = root / "game.mp4"
            media_bytes = b"synthetic media"
            media_path.write_bytes(media_bytes)
            digest = hashlib.sha256(media_bytes).hexdigest()
            candidate = {
                "candidate_id": "C01", "asset_id": "P1", "source_start_sec": 0,
                "source_end_sec": 120, "timeline_order": 1, "review_status": "selected",
                "event_summary": "合成比赛片段",
                "visual_evidence": [{"start_sec": 1, "end_sec": 2, "summary": "合成证据"}],
                "commentary_evidence": [], "operation_quality_note": "合成描述",
                "match_significance_note": "合成描述", "participants": [], "uncertainties": [],
                "review_reason": None, "exclusion_reason": None, "editor_note": None,
            }
            candidates = {
                "schema_version": 1, "content_type": "single_match_recap",
                "source_assets": [{"asset_id": "P1", "sha256": digest, "duration_sec": 600,
                                   "game_number": 1, "team_names": ["北京JDG", "上海EDG.M"]}],
                "candidates": [candidate], "analysis_notes": [],
            }
            asset_map = {"assets": {"P1": {
                "path": str(media_path), "sha256": "0" * 64, "duration_sec": 600,
                "width": 1920, "height": 1080, "frame_rate_num": 30,
                "frame_rate_den": 1, "audio_channels": 2, "audio_sample_rate": 48000,
            }}}
            candidates_path = root / "candidates.json"
            asset_map_path = root / "asset-map.json"
            output_path = root / "review-timeline.fcpxml"
            candidates_path.write_text(json.dumps(candidates, ensure_ascii=False), encoding="utf-8")
            asset_map_path.write_text(json.dumps(asset_map, ensure_ascii=False), encoding="utf-8")

            result = subprocess.run(
                [sys.executable, str(EXPORTER), "--candidates", str(candidates_path),
                 "--asset-map", str(asset_map_path), "--output", str(output_path)],
                capture_output=True, text=True, check=False,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("SHA-256 mismatch", result.stderr)
            self.assertFalse(output_path.exists())

    def test_export_rejects_overlapping_selected_ranges_from_same_source(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            media_path = root / "game.mp4"
            media_bytes = b"synthetic media"
            media_path.write_bytes(media_bytes)
            digest = hashlib.sha256(media_bytes).hexdigest()

            def candidate(candidate_id, start, end, order):
                return {
                    "candidate_id": candidate_id, "asset_id": "P1",
                    "source_start_sec": start, "source_end_sec": end, "timeline_order": order,
                    "review_status": "selected", "event_summary": "合成片段",
                    "visual_evidence": [{"start_sec": start + 1, "end_sec": start + 2, "summary": "合成证据"}],
                    "commentary_evidence": [], "operation_quality_note": "合成描述",
                    "match_significance_note": "合成描述", "participants": [], "uncertainties": [],
                    "review_reason": None, "exclusion_reason": None, "editor_note": None,
                }

            candidates = {
                "schema_version": 1, "content_type": "single_match_recap",
                "source_assets": [{"asset_id": "P1", "sha256": digest, "duration_sec": 600,
                                   "game_number": 1, "team_names": ["北京JDG", "上海EDG.M"]}],
                "candidates": [candidate("C01", 60, 150, 1), candidate("C02", 140, 230, 2)],
                "analysis_notes": [],
            }
            asset_map = {"assets": {"P1": {
                "path": str(media_path), "sha256": digest, "duration_sec": 600,
                "width": 1920, "height": 1080, "frame_rate_num": 30,
                "frame_rate_den": 1, "audio_channels": 2, "audio_sample_rate": 48000,
            }}}
            candidates_path = root / "candidates.json"
            asset_map_path = root / "asset-map.json"
            output_path = root / "review-timeline.fcpxml"
            candidates_path.write_text(json.dumps(candidates, ensure_ascii=False), encoding="utf-8")
            asset_map_path.write_text(json.dumps(asset_map, ensure_ascii=False), encoding="utf-8")

            result = subprocess.run(
                [sys.executable, str(EXPORTER), "--candidates", str(candidates_path),
                 "--asset-map", str(asset_map_path), "--output", str(output_path)],
                capture_output=True, text=True, check=False,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("overlap", result.stderr.lower())
            self.assertFalse(output_path.exists())

    def test_export_rejects_candidate_duration_that_disagrees_with_media_manifest(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            media_path = root / "game.mp4"
            media_bytes = b"synthetic media"
            media_path.write_bytes(media_bytes)
            digest = hashlib.sha256(media_bytes).hexdigest()
            candidate = {
                "candidate_id": "C01", "asset_id": "P1", "source_start_sec": 0,
                "source_end_sec": 120, "timeline_order": 1, "review_status": "selected",
                "event_summary": "合成比赛片段",
                "visual_evidence": [{"start_sec": 1, "end_sec": 2, "summary": "合成证据"}],
                "commentary_evidence": [], "operation_quality_note": "合成描述",
                "match_significance_note": "合成描述", "participants": [], "uncertainties": [],
                "review_reason": None, "exclusion_reason": None, "editor_note": None,
            }
            candidates = {
                "schema_version": 1, "content_type": "single_match_recap",
                "source_assets": [{"asset_id": "P1", "sha256": digest, "duration_sec": 600,
                                   "game_number": 1, "team_names": ["北京JDG", "上海EDG.M"]}],
                "candidates": [candidate], "analysis_notes": [],
            }
            asset_map = {"assets": {"P1": {
                "path": str(media_path), "sha256": digest, "duration_sec": 599,
                "width": 1920, "height": 1080, "frame_rate_num": 30,
                "frame_rate_den": 1, "audio_channels": 2, "audio_sample_rate": 48000,
            }}}
            candidates_path = root / "candidates.json"
            asset_map_path = root / "asset-map.json"
            output_path = root / "review-timeline.fcpxml"
            candidates_path.write_text(json.dumps(candidates, ensure_ascii=False), encoding="utf-8")
            asset_map_path.write_text(json.dumps(asset_map, ensure_ascii=False), encoding="utf-8")

            result = subprocess.run(
                [sys.executable, str(EXPORTER), "--candidates", str(candidates_path),
                 "--asset-map", str(asset_map_path), "--output", str(output_path)],
                capture_output=True, text=True, check=False,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("duration", result.stderr.lower())
            self.assertFalse(output_path.exists())

    def test_export_rejects_duplicate_timeline_order(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            media_path = root / "game.mp4"
            media_bytes = b"synthetic media"
            media_path.write_bytes(media_bytes)
            digest = hashlib.sha256(media_bytes).hexdigest()

            def candidate(candidate_id, start, order):
                return {
                    "candidate_id": candidate_id, "asset_id": "P1",
                    "source_start_sec": start, "source_end_sec": start + 90,
                    "timeline_order": order, "review_status": "selected",
                    "event_summary": "合成片段",
                    "visual_evidence": [{"start_sec": start + 1, "end_sec": start + 2, "summary": "合成证据"}],
                    "commentary_evidence": [], "operation_quality_note": "合成描述",
                    "match_significance_note": "合成描述", "participants": [], "uncertainties": [],
                    "review_reason": None, "exclusion_reason": None, "editor_note": None,
                }

            candidates = {
                "schema_version": 1, "content_type": "single_match_recap",
                "source_assets": [{"asset_id": "P1", "sha256": digest, "duration_sec": 600,
                                   "game_number": 1, "team_names": ["北京JDG", "上海EDG.M"]}],
                "candidates": [candidate("C01", 0, 1), candidate("C02", 120, 1)],
                "analysis_notes": [],
            }
            asset_map = {"assets": {"P1": {
                "path": str(media_path), "sha256": digest, "duration_sec": 600,
                "width": 1920, "height": 1080, "frame_rate_num": 30,
                "frame_rate_den": 1, "audio_channels": 2, "audio_sample_rate": 48000,
            }}}
            candidates_path = root / "candidates.json"
            asset_map_path = root / "asset-map.json"
            output_path = root / "review-timeline.fcpxml"
            candidates_path.write_text(json.dumps(candidates, ensure_ascii=False), encoding="utf-8")
            asset_map_path.write_text(json.dumps(asset_map, ensure_ascii=False), encoding="utf-8")

            result = subprocess.run(
                [sys.executable, str(EXPORTER), "--candidates", str(candidates_path),
                 "--asset-map", str(asset_map_path), "--output", str(output_path)],
                capture_output=True, text=True, check=False,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("timeline order", result.stderr.lower())
            self.assertFalse(output_path.exists())

    def test_export_reports_when_no_candidates_are_reviewable(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            media_path = root / "game.mp4"
            media_bytes = b"synthetic media"
            media_path.write_bytes(media_bytes)
            digest = hashlib.sha256(media_bytes).hexdigest()
            candidates = {
                "schema_version": 1, "content_type": "single_match_recap",
                "source_assets": [{"asset_id": "P1", "sha256": digest, "duration_sec": 600,
                                   "game_number": 1, "team_names": ["北京JDG", "上海EDG.M"]}],
                "candidates": [], "analysis_notes": ["没有找到可审阅候选"],
            }
            asset_map = {"assets": {"P1": {
                "path": str(media_path), "sha256": digest, "duration_sec": 600,
                "width": 1920, "height": 1080, "frame_rate_num": 30,
                "frame_rate_den": 1, "audio_channels": 2, "audio_sample_rate": 48000,
            }}}
            candidates_path = root / "candidates.json"
            asset_map_path = root / "asset-map.json"
            output_path = root / "review-timeline.fcpxml"
            candidates_path.write_text(json.dumps(candidates, ensure_ascii=False), encoding="utf-8")
            asset_map_path.write_text(json.dumps(asset_map, ensure_ascii=False), encoding="utf-8")

            result = subprocess.run(
                [sys.executable, str(EXPORTER), "--candidates", str(candidates_path),
                 "--asset-map", str(asset_map_path), "--output", str(output_path)],
                capture_output=True, text=True, check=False,
            )

            self.assertEqual(result.returncode, 2)
            self.assertIn("no reviewable candidates", result.stderr.lower())
            self.assertFalse(output_path.exists())

    def test_export_rejects_mixed_sequence_video_formats(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            media = {"P1": b"synthetic media one", "P2": b"synthetic media two"}
            media_paths = {asset_id: root / f"{asset_id}.mp4" for asset_id in media}
            for asset_id, path in media_paths.items():
                path.write_bytes(media[asset_id])
            assets = [{
                "asset_id": asset_id,
                "sha256": hashlib.sha256(media[asset_id]).hexdigest(),
                "duration_sec": 600,
                "game_number": int(asset_id[-1]),
                "team_names": ["北京JDG", "上海EDG.M"],
            } for asset_id in media]
            candidates = {
                "schema_version": 1, "content_type": "single_match_recap",
                "source_assets": assets, "analysis_notes": [],
                "candidates": [
                    {
                        "candidate_id": "C01", "asset_id": "P1", "source_start_sec": 0,
                        "source_end_sec": 90, "timeline_order": 1, "review_status": "selected",
                        "event_summary": "合成片段一",
                        "visual_evidence": [{"start_sec": 1, "end_sec": 2, "summary": "合成证据"}],
                        "commentary_evidence": [], "operation_quality_note": "合成描述",
                        "match_significance_note": "合成描述", "participants": [], "uncertainties": [],
                        "review_reason": None, "exclusion_reason": None, "editor_note": None,
                    },
                    {
                        "candidate_id": "C02", "asset_id": "P2", "source_start_sec": 120,
                        "source_end_sec": 210, "timeline_order": 2, "review_status": "selected",
                        "event_summary": "合成片段二",
                        "visual_evidence": [{"start_sec": 121, "end_sec": 122, "summary": "合成证据"}],
                        "commentary_evidence": [], "operation_quality_note": "合成描述",
                        "match_significance_note": "合成描述", "participants": [], "uncertainties": [],
                        "review_reason": None, "exclusion_reason": None, "editor_note": None,
                    },
                ],
            }
            asset_map = {"assets": {
                "P1": {
                    "path": str(media_paths["P1"]), "sha256": assets[0]["sha256"],
                    "duration_sec": 600, "width": 1920, "height": 1080,
                    "frame_rate_num": 30, "frame_rate_den": 1,
                    "audio_channels": 2, "audio_sample_rate": 48000,
                },
                "P2": {
                    "path": str(media_paths["P2"]), "sha256": assets[1]["sha256"],
                    "duration_sec": 600, "width": 1280, "height": 720,
                    "frame_rate_num": 60, "frame_rate_den": 1,
                    "audio_channels": 2, "audio_sample_rate": 48000,
                },
            }}
            candidates_path = root / "candidates.json"
            asset_map_path = root / "asset-map.json"
            output_path = root / "review-timeline.fcpxml"
            candidates_path.write_text(json.dumps(candidates, ensure_ascii=False), encoding="utf-8")
            asset_map_path.write_text(json.dumps(asset_map, ensure_ascii=False), encoding="utf-8")

            result = subprocess.run(
                [sys.executable, str(EXPORTER), "--candidates", str(candidates_path),
                 "--asset-map", str(asset_map_path), "--output", str(output_path)],
                capture_output=True, text=True, check=False,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("video format", result.stderr.lower())
            self.assertFalse(output_path.exists())

    def test_export_rejects_story_fact_not_confirmed_in_player_knowledge_base(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            media_path = root / "game.mp4"
            media_bytes = b"synthetic media"
            media_path.write_bytes(media_bytes)
            digest = hashlib.sha256(media_bytes).hexdigest()
            knowledge_dir = root / "knowledge"
            knowledge_dir.mkdir()
            (knowledge_dir / "players.json").write_text(json.dumps({"players": [{
                "id": "fixture-player", "facts": [{
                    "id": "confirmed-fact", "summary": "知识库确认的标准事实",
                    "verified": True, "source_ids": ["official-source"],
                }],
            }]}), encoding="utf-8")
            (knowledge_dir / "sources.json").write_text(json.dumps({"sources": [{
                "id": "official-source", "url": "https://example.test/official",
                "first_party": True, "retrieval_status": "opened",
            }]}), encoding="utf-8")
            candidate = {
                "candidate_id": "C01", "asset_id": "P1", "source_start_sec": 0,
                "source_end_sec": 120, "timeline_order": 1, "review_status": "selected",
                "event_summary": "合成比赛片段",
                "visual_evidence": [{"start_sec": 1, "end_sec": 2, "summary": "合成证据"}],
                "commentary_evidence": [], "operation_quality_note": "合成描述",
                "match_significance_note": "合成描述", "participants": [{
                    "display_name": "测试选手", "team_name": "测试战队",
                    "identity_status": "confirmed", "kb_player_id": "fixture-player",
                    "verified_story_facts": [{
                        "fact_id": "unknown-fact", "claim": "未证实的故事主张",
                        "sources": ["https://example.test/official"],
                    }],
                }],
                "uncertainties": [], "review_reason": None, "exclusion_reason": None,
                "editor_note": None,
            }
            candidates = {
                "schema_version": 1, "content_type": "single_match_recap",
                "source_assets": [{"asset_id": "P1", "sha256": digest, "duration_sec": 600,
                                   "game_number": 1, "team_names": ["测试战队", "另一战队"]}],
                "candidates": [candidate], "analysis_notes": [],
            }
            asset_map = {"assets": {"P1": {
                "path": str(media_path), "sha256": digest, "duration_sec": 600,
                "width": 1920, "height": 1080, "frame_rate_num": 30,
                "frame_rate_den": 1, "audio_channels": 2, "audio_sample_rate": 48000,
            }}}
            candidates_path = root / "candidates.json"
            asset_map_path = root / "asset-map.json"
            output_path = root / "review-timeline.fcpxml"
            candidates_path.write_text(json.dumps(candidates, ensure_ascii=False), encoding="utf-8")
            asset_map_path.write_text(json.dumps(asset_map, ensure_ascii=False), encoding="utf-8")

            result = subprocess.run(
                [sys.executable, str(EXPORTER), "--candidates", str(candidates_path),
                 "--asset-map", str(asset_map_path), "--knowledge-base", str(knowledge_dir),
                 "--output", str(output_path)],
                capture_output=True, text=True, check=False,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("not a verified knowledge-base fact", result.stderr.lower())
            self.assertFalse(output_path.exists())

            candidate["participants"][0]["identity_status"] = "uncertain"
            candidate["participants"][0]["verified_story_facts"] = []
            candidates_path.write_text(json.dumps(candidates, ensure_ascii=False), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(EXPORTER), "--candidates", str(candidates_path),
                 "--asset-map", str(asset_map_path), "--knowledge-base", str(knowledge_dir),
                 "--output", str(output_path)],
                capture_output=True, text=True, check=False,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("uncertain player identity", result.stderr.lower())
            self.assertFalse(output_path.exists())

            candidate["participants"][0]["identity_status"] = "confirmed"
            candidate["participants"][0]["verified_story_facts"] = [{
                "fact_id": "confirmed-fact", "claim": "Codex 生成的改写",
                "sources": ["https://example.test/official"],
            }]
            candidates_path.write_text(json.dumps(candidates, ensure_ascii=False), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(EXPORTER), "--candidates", str(candidates_path),
                 "--asset-map", str(asset_map_path), "--knowledge-base", str(knowledge_dir),
                 "--output", str(output_path)],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            note = ET.parse(output_path).findtext(".//asset-clip/note", "")
            self.assertIn("https://example.test/official", note)
            self.assertIn("知识库确认的标准事实", note)
            self.assertNotIn("Codex 生成的改写", note)


if __name__ == "__main__":
    unittest.main()
