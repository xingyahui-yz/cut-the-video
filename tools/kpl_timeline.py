import argparse
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import sys
import xml.etree.ElementTree as ET


_AUDIO_RATE_NAMES = {
    32000: "32k",
    44100: "44.1k",
    48000: "48k",
    88200: "88.2k",
    96000: "96k",
    176400: "176.4k",
    192000: "192k",
}
_FRAME_RATE_NAMES = {
    Fraction(24000, 1001): "23976",
    Fraction(24, 1): "24",
    Fraction(25, 1): "25",
    Fraction(30000, 1001): "2997",
    Fraction(30, 1): "30",
    Fraction(50, 1): "50",
    Fraction(60000, 1001): "5994",
    Fraction(60, 1): "60",
}


def _digest(path):
    hasher = hashlib.sha256()
    with path.open("rb") as media_file:
        for chunk in iter(lambda: media_file.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _seconds(value):
    return Fraction(str(value))


def _time(value):
    value = Fraction(value)
    return f"{value.numerator}s" if value.denominator == 1 else f"{value.numerator}/{value.denominator}s"


def _format_name(height, frame_rate):
    rate_name = _FRAME_RATE_NAMES.get(frame_rate, f"{frame_rate.numerator}_{frame_rate.denominator}")
    return f"FFVideoFormat{height}p{rate_name}"


def _frame_count(seconds, frame_rate, *, round_up=False):
    frames = Fraction(seconds) * frame_rate
    quotient, remainder = divmod(frames.numerator, frames.denominator)
    return quotient + int(round_up and remainder != 0)


def _note(candidate, canonical_story_facts):
    participants = []
    for participant in candidate["participants"]:
        participant_note = dict(participant)
        participant_note["verified_story_facts"] = [
            canonical_story_facts[(candidate["candidate_id"], participant["kb_player_id"], story_fact["fact_id"])]
            for story_fact in participant["verified_story_facts"]
        ]
        participants.append(participant_note)
    note = {
        "candidate_id": candidate["candidate_id"],
        "review_status": candidate["review_status"],
        "event_summary": candidate["event_summary"],
        "operation_quality_note": candidate["operation_quality_note"],
        "match_significance_note": candidate["match_significance_note"],
        "review_reason": candidate["review_reason"],
        "exclusion_reason": candidate["exclusion_reason"],
        "editor_note": candidate["editor_note"],
        "participants": participants,
        "uncertainties": candidate["uncertainties"],
        "visual_evidence": candidate["visual_evidence"],
        "commentary_evidence": candidate["commentary_evidence"],
    }
    return json.dumps(note, ensure_ascii=False, separators=(",", ":"))


def _validate_story_facts(candidate_data, knowledge_base_path):
    for candidate in candidate_data["candidates"]:
        if (candidate["review_status"] == "selected"
                and any(participant["identity_status"] != "confirmed"
                        for participant in candidate["participants"])):
            raise ValueError(f"Candidate {candidate['candidate_id']} has an uncertain player identity and must be reviewed")
    fact_bearing_participants = [
        (candidate, participant, story_fact)
        for candidate in candidate_data["candidates"]
        for participant in candidate["participants"]
        for story_fact in participant["verified_story_facts"]
    ]
    if not fact_bearing_participants:
        return {}

    players_data = json.loads((knowledge_base_path / "players.json").read_text(encoding="utf-8"))
    sources_data = json.loads((knowledge_base_path / "sources.json").read_text(encoding="utf-8"))
    players = {player["id"]: player for player in players_data["players"]}
    sources = {source["id"]: source for source in sources_data["sources"]}
    canonical_facts = {}

    for candidate, participant, story_fact in fact_bearing_participants:
        player_id = participant["kb_player_id"]
        player = players.get(player_id)
        verified_fact = next((fact for fact in player["facts"]
                              if fact["id"] == story_fact["fact_id"] and fact["verified"]), None) if player else None
        if not verified_fact:
            raise ValueError(f"Story fact {story_fact['fact_id']} is not a verified knowledge-base fact")
        source_ids = verified_fact["source_ids"]
        if not source_ids or any(source_id not in sources for source_id in source_ids):
            raise ValueError(f"Story fact {story_fact['fact_id']} has unknown knowledge-base sources")
        official_sources = [sources[source_id] for source_id in source_ids]
        if any(not source["first_party"] or source["retrieval_status"] != "opened"
               for source in official_sources):
            raise ValueError(f"Story fact {story_fact['fact_id']} lacks verified first-party sources")
        expected_urls = {source["url"] for source in official_sources}
        provided_urls = set(story_fact["sources"])
        if not provided_urls or provided_urls != expected_urls:
            raise ValueError(f"Story fact {story_fact['fact_id']} source URLs do not match the knowledge base")
        if not verified_fact.get("summary"):
            raise ValueError(f"Story fact {story_fact['fact_id']} has no canonical knowledge-base summary")
        canonical_facts[(candidate["candidate_id"], player_id, story_fact["fact_id"])] = {
            "fact_id": story_fact["fact_id"],
            "claim": verified_fact["summary"],
            "sources": [source["url"] for source in official_sources],
        }
    return canonical_facts


def build_fcpxml(candidate_data, asset_map, project_name, knowledge_base_path=None):
    if knowledge_base_path is None:
        knowledge_base_path = Path(__file__).resolve().parents[1] / "knowledge" / "kpl" / "data"
    canonical_story_facts = _validate_story_facts(candidate_data, Path(knowledge_base_path))
    mapped_assets = asset_map["assets"]
    candidate_assets = {asset["asset_id"]: asset for asset in candidate_data["source_assets"]}
    for candidate in candidate_data["candidates"]:
        metadata = mapped_assets[candidate["asset_id"]]
        source_asset = candidate_assets[candidate["asset_id"]]
        frame_rate = Fraction(metadata["frame_rate_num"], metadata["frame_rate_den"])
        if abs(_seconds(source_asset["duration_sec"]) - _seconds(metadata["duration_sec"])) > 1 / frame_rate:
            raise ValueError(f"Candidate source duration does not match media manifest for {candidate['asset_id']}")
        source_start = _seconds(candidate["source_start_sec"])
        source_end = _seconds(candidate["source_end_sec"])
        if candidate["review_status"] == "needs_review" and not candidate["review_reason"]:
            raise ValueError(f"Candidate {candidate['candidate_id']} needs a review reason")
        if candidate["review_status"] == "not_selected" and not candidate["exclusion_reason"]:
            raise ValueError(f"Candidate {candidate['candidate_id']} needs an exclusion reason")
        if not candidate["visual_evidence"] and not candidate["commentary_evidence"]:
            raise ValueError(f"Candidate {candidate['candidate_id']} needs visual or commentary evidence")
        if source_start < 0 or source_end <= source_start:
            raise ValueError(f"Candidate {candidate['candidate_id']} has an invalid source range")
        if source_end > _seconds(metadata["duration_sec"]):
            raise ValueError(f"Candidate {candidate['candidate_id']} exceeds source duration for {candidate['asset_id']}")
    included = sorted(
        (candidate for candidate in candidate_data["candidates"]
         if candidate["review_status"] in ("selected", "needs_review")),
        key=lambda candidate: candidate["timeline_order"],
    )
    if not included:
        raise ValueError("No reviewable candidates are available for a timeline")
    orders = [candidate["timeline_order"] for candidate in included]
    if len(orders) != len(set(orders)):
        raise ValueError("Included candidates must have unique timeline order values")
    used_asset_ids = list(dict.fromkeys(candidate["asset_id"] for candidate in included))
    frame_rate = Fraction(
        mapped_assets[used_asset_ids[0]]["frame_rate_num"],
        mapped_assets[used_asset_ids[0]]["frame_rate_den"],
    )
    width = mapped_assets[used_asset_ids[0]]["width"]
    height = mapped_assets[used_asset_ids[0]]["height"]
    sample_rate = mapped_assets[used_asset_ids[0]]["audio_sample_rate"]
    audio_channels = mapped_assets[used_asset_ids[0]]["audio_channels"]
    if audio_channels not in (1, 2):
        raise ValueError("The source must have one or two audio channels to preserve original audio")
    if sample_rate not in _AUDIO_RATE_NAMES:
        raise ValueError(f"Unsupported source audio sample rate: {sample_rate}")
    video_spec = (width, height, frame_rate)
    audio_spec = (audio_channels, sample_rate)
    for asset_id in used_asset_ids[1:]:
        metadata = mapped_assets[asset_id]
        other_video_spec = (
            metadata["width"], metadata["height"],
            Fraction(metadata["frame_rate_num"], metadata["frame_rate_den"]),
        )
        if other_video_spec != video_spec:
            raise ValueError("Source assets have incompatible video formats for one timeline")
        if (metadata["audio_channels"], metadata["audio_sample_rate"]) != audio_spec:
            raise ValueError("Source assets have incompatible audio formats for one timeline")

    xml_root = ET.Element("fcpxml", {"version": "1.10"})
    resources = ET.SubElement(xml_root, "resources")
    format_id = "r1"
    ET.SubElement(resources, "format", {
        "id": format_id,
        "name": _format_name(height, frame_rate),
        "frameDuration": _time(1 / frame_rate),
        "width": str(width),
        "height": str(height),
        "colorSpace": "1-1-1 (Rec. 709)",
    })

    resource_ids = {}
    for index, asset_id in enumerate(used_asset_ids, start=2):
        metadata = mapped_assets[asset_id]
        path = Path(metadata["path"]).resolve()
        actual_digest = _digest(path)
        if actual_digest.lower() != metadata["sha256"].lower():
            raise ValueError(f"SHA-256 mismatch for source asset {asset_id}")
        if candidate_assets[asset_id]["sha256"].lower() != actual_digest.lower():
            raise ValueError(f"Candidate source hash does not match mapped media for {asset_id}")
        resource_id = f"r{index}"
        resource_ids[asset_id] = resource_id
        asset_attributes = {
            "id": resource_id,
            "name": path.name,
            "src": path.as_uri(),
            "start": "0s",
            "duration": _time(_seconds(metadata["duration_sec"])),
            "hasVideo": "1",
            "hasAudio": "1" if metadata["audio_channels"] else "0",
            "format": format_id,
            "videoSources": "1",
            "audioSources": "1" if metadata["audio_channels"] else "0",
        }
        if metadata["audio_channels"]:
            asset_attributes["audioChannels"] = str(metadata["audio_channels"])
            asset_attributes["audioRate"] = str(metadata["audio_sample_rate"])
        ET.SubElement(resources, "asset", asset_attributes)

    clip_frame_ranges = []
    for candidate in included:
        asset = mapped_assets[candidate["asset_id"]]
        source_rate = Fraction(asset["frame_rate_num"], asset["frame_rate_den"])
        start_frame = _frame_count(_seconds(candidate["source_start_sec"]), source_rate)
        end_frame = _frame_count(_seconds(candidate["source_end_sec"]), source_rate, round_up=True)
        clip_frame_ranges.append((candidate, start_frame, end_frame))

    source_ranges = {}
    for candidate, start_frame, end_frame in clip_frame_ranges:
        ranges = source_ranges.setdefault(candidate["asset_id"], [])
        if any(start_frame < existing_end and existing_start < end_frame
               for existing_start, existing_end in ranges):
            raise ValueError(f"Selected candidates overlap in source asset {candidate['asset_id']}")
        ranges.append((start_frame, end_frame))

    total_frames = sum(end - start for _, start, end in clip_frame_ranges)
    total_duration = Fraction(total_frames, 1) / frame_rate
    if not Fraction(120) <= total_duration <= Fraction(300):
        raise ValueError("Timeline duration must be between 120 and 300 seconds")
    sequence_duration = _time(total_duration)
    library = ET.SubElement(xml_root, "library")
    event = ET.SubElement(library, "event", {"name": "KPL 待审时间线"})
    project = ET.SubElement(event, "project", {"name": project_name})
    sequence = ET.SubElement(project, "sequence", {
        "format": format_id,
        "duration": sequence_duration,
        "tcStart": "0s",
        "tcFormat": "NDF",
        "audioLayout": "stereo" if audio_channels == 2 else "mono",
        "audioRate": _AUDIO_RATE_NAMES[sample_rate],
    })
    spine = ET.SubElement(sequence, "spine")
    offset_frames = 0
    for candidate, start_frame, end_frame in clip_frame_ranges:
        duration_frames = end_frame - start_frame
        clip = ET.SubElement(spine, "asset-clip", {
            "name": f"{candidate['candidate_id']}｜{candidate['event_summary']}",
            "ref": resource_ids[candidate["asset_id"]],
            "format": format_id,
            "offset": _time(Fraction(offset_frames, 1) / frame_rate),
            "start": _time(Fraction(start_frame, 1) / Fraction(
                mapped_assets[candidate["asset_id"]]["frame_rate_num"],
                mapped_assets[candidate["asset_id"]]["frame_rate_den"],
            )),
            "duration": _time(Fraction(duration_frames, 1) / Fraction(
                mapped_assets[candidate["asset_id"]]["frame_rate_num"],
                mapped_assets[candidate["asset_id"]]["frame_rate_den"],
            )),
            "srcEnable": "all",
            "audioRole": "dialogue",
        })
        ET.SubElement(clip, "note").text = _note(candidate, canonical_story_facts)
        offset_frames += duration_frames

    ET.indent(xml_root, space="  ")
    return ET.tostring(xml_root, encoding="utf-8", xml_declaration=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Export KPL clip candidates as a DaVinci-importable FCPXML timeline.")
    parser.add_argument("--candidates", required=True, type=Path)
    parser.add_argument("--asset-map", required=True, type=Path)
    parser.add_argument("--knowledge-base", type=Path,
                        default=Path(__file__).resolve().parents[1] / "knowledge" / "kpl" / "data")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--project-name", default="KPL 待审集锦")
    args = parser.parse_args(argv)

    try:
        if args.output.exists():
            raise ValueError(f"Output timeline already exists; choose a new path: {args.output}")
        candidate_data = json.loads(args.candidates.read_text(encoding="utf-8"))
        asset_map = json.loads(args.asset_map.read_text(encoding="utf-8"))
        xml_bytes = build_fcpxml(candidate_data, asset_map, args.project_name, args.knowledge_base)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("xb") as output_file:
            output_file.write(xml_bytes)
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError, ZeroDivisionError) as error:
        print(f"Timeline export failed: {error}", file=sys.stderr)
        return 2
    print(f"Wrote review timeline: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
