"""Build local, time-aligned evidence packets for later KPL review."""

import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time


_ASSET_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


def _positive_number(value, label):
    try:
        number = float(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{label} must be a positive number") from error
    if not math.isfinite(number) or number <= 0:
        raise ValueError(f"{label} must be a positive number")
    return number


def frame_timestamps(duration_sec, interval_sec):
    duration = _positive_number(duration_sec, "duration")
    interval = _positive_number(interval_sec, "frame interval")
    timestamps = []
    frame_index = 0
    while frame_index * interval < duration:
        timestamp = frame_index * interval
        timestamps.append(int(timestamp) if timestamp.is_integer() else timestamp)
        frame_index += 1
    return timestamps


def build_analysis_packets(
    *, asset_id, duration_sec, frame_interval_sec, packet_duration_sec, frames, transcript
):
    duration = _positive_number(duration_sec, "duration")
    frame_interval = _positive_number(frame_interval_sec, "frame interval")
    packet_duration = _positive_number(packet_duration_sec, "packet duration")
    if not isinstance(asset_id, str) or not _ASSET_ID_PATTERN.fullmatch(asset_id):
        raise ValueError("asset_id must contain only letters, digits, dots, underscores, or hyphens")

    packet_count = math.ceil(duration / packet_duration)
    packets = [{
        "packet_id": f"{asset_id}-{index + 1:03d}",
        "asset_id": asset_id,
        "start_sec": index * packet_duration,
        "end_sec": min((index + 1) * packet_duration, duration),
        "frames": [],
        "transcript": [],
    } for index in range(packet_count)]

    for frame in frames:
        try:
            timestamp = float(frame["timestamp_sec"])
            path = frame["path"]
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError("Each frame needs a numeric timestamp_sec and a path") from error
        if not math.isfinite(timestamp) or timestamp < 0 or timestamp >= duration:
            raise ValueError(f"Invalid frame timestamp for {asset_id}: {frame.get('timestamp_sec')}")
        if not isinstance(path, str) or not path:
            raise ValueError("Each frame path must be a non-empty string")
        packet_index = min(int(timestamp // packet_duration), packet_count - 1)
        packets[packet_index]["frames"].append({
            "timestamp_sec": int(timestamp) if timestamp.is_integer() else timestamp,
            "path": path,
        })

    for segment in transcript:
        try:
            start = float(segment["start_sec"])
            end = float(segment["end_sec"])
            text = segment["text"]
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError("Each transcript segment needs start_sec, end_sec, and text") from error
        if (not math.isfinite(start) or not math.isfinite(end)
                or start < 0 or end <= start or end > duration):
            raise ValueError(f"Invalid transcript timestamp for {asset_id}: {segment}")
        if not isinstance(text, str):
            raise ValueError("Transcript text must be a string")
        packet_index = min(int(start // packet_duration), packet_count - 1)
        packets[packet_index]["transcript"].append({
            "start_sec": int(start) if start.is_integer() else start,
            "end_sec": int(end) if end.is_integer() else end,
            "text": text,
        })

    for packet in packets:
        packet["frames"].sort(key=lambda row: row["timestamp_sec"])
        packet["transcript"].sort(key=lambda row: row["start_sec"])
    return packets


def _sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _resolve_ffmpeg(explicit_path):
    if explicit_path:
        executable = Path(explicit_path).expanduser()
        if executable.is_file():
            return str(executable.resolve())
        resolved = shutil.which(explicit_path)
        if resolved:
            return resolved
        raise ValueError(f"FFmpeg executable not found: {explicit_path}")

    try:
        import imageio_ffmpeg
        bundled = Path(imageio_ffmpeg.get_ffmpeg_exe())
        if bundled.is_file():
            return str(bundled)
    except (ImportError, RuntimeError):
        pass

    resolved = shutil.which("ffmpeg")
    if not resolved:
        raise ValueError("FFmpeg not found; pass --ffmpeg with its executable path")
    return resolved


def _extract_frames(ffmpeg, source_path, output_dir, interval_sec, width):
    output_dir.mkdir(parents=True, exist_ok=False)
    pattern = output_dir / "frame_%06d.jpg"
    command = [
        ffmpeg, "-nostdin", "-hide_banner", "-loglevel", "error",
        "-i", str(source_path),
        "-vf", f"fps=1/{interval_sec}:start_time=0:round=near,scale={width}:-2:flags=lanczos",
        "-q:v", "3", "-start_number", "0", "-fps_mode", "vfr",
        str(pattern),
    ]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg frame extraction failed for {source_path}: {result.stderr.strip()}")

    frames = []
    for path in sorted(output_dir.glob("frame_*.jpg")):
        try:
            frame_index = int(path.stem.rsplit("_", 1)[1])
        except ValueError as error:
            raise ValueError(f"Unexpected extracted frame name: {path.name}") from error
        frames.append({
            "timestamp_sec": frame_index * interval_sec,
            "path": str(path.resolve()),
        })
    return frames


def _transcribe(model, source_path, duration_sec, asset_id, progress):
    segments, info = model.transcribe(
        str(source_path), language="zh", beam_size=5, vad_filter=True,
    )
    transcript = []
    next_progress = 300
    for segment in segments:
        start = max(0.0, float(segment.start))
        end = min(float(duration_sec), float(segment.end))
        if end > start:
            transcript.append({
                "start_sec": round(start, 3),
                "end_sec": round(end, 3),
                "text": segment.text.strip(),
            })
        if progress and end >= next_progress:
            progress(f"{asset_id}: transcribed {int(end // 60)} minutes of source media")
            next_progress += 300
    audio_duration = getattr(info, "duration", None)
    if audio_duration is not None and abs(float(audio_duration) - duration_sec) > 1.0:
        raise ValueError(
            f"Audio duration for {asset_id} differs from asset map by more than one second"
        )
    return transcript, getattr(info, "language", None)


def _write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def prepare_analysis(args):
    run_started = time.monotonic()
    asset_map = json.loads(args.asset_map.read_text(encoding="utf-8"))
    assets = asset_map["assets"]
    selected_ids = args.asset_id or list(assets)
    missing_ids = [asset_id for asset_id in selected_ids if asset_id not in assets]
    if missing_ids:
        raise ValueError(f"Unknown asset IDs: {', '.join(missing_ids)}")
    for asset_id in selected_ids:
        if not _ASSET_ID_PATTERN.fullmatch(asset_id):
            raise ValueError(f"Unsafe asset ID: {asset_id}")

    ffmpeg = _resolve_ffmpeg(args.ffmpeg)
    source_paths = {}
    for asset_id in selected_ids:
        metadata = assets[asset_id]
        source_path = Path(metadata["path"])
        if not source_path.is_file():
            raise ValueError(f"Source asset does not exist: {source_path}")
        actual_hash = _sha256(source_path)
        if actual_hash.lower() != metadata["sha256"].lower():
            raise ValueError(f"SHA-256 mismatch for source asset {asset_id}")
        source_paths[asset_id] = source_path

    try:
        from faster_whisper import WhisperModel
    except ImportError as error:
        raise ValueError("Run this tool with a Python environment that has faster-whisper installed") from error
    model = WhisperModel(
        args.whisper_model,
        device=args.device,
        compute_type=args.compute_type,
        download_root=str(args.model_cache),
        local_files_only=True,
    )

    output_dir = args.output_dir.resolve()
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(exist_ok=False)
    index = {
        "schema_version": 1,
        "asset_set": asset_map.get("asset_set"),
        "created_by": "tools/kpl_analysis_packets.py",
        "settings": {
            "whisper_model": args.whisper_model,
            "device": args.device,
            "compute_type": args.compute_type,
            "language": "zh",
            "frame_interval_sec": args.frame_interval_sec,
            "packet_duration_sec": args.packet_duration_sec,
            "frame_width": args.frame_width,
        },
        "assets": [],
        "packets": [],
    }

    for asset_id in selected_ids:
        metadata = assets[asset_id]
        duration = float(metadata["duration_sec"])
        asset_dir = output_dir / asset_id
        frames_dir = asset_dir / "frames"
        asset_dir.mkdir()
        print(f"{asset_id}: extracting timestamped frames", flush=True)
        frame_started = time.monotonic()
        frames = _extract_frames(
            ffmpeg, source_paths[asset_id], frames_dir,
            args.frame_interval_sec, args.frame_width,
        )
        frame_seconds = time.monotonic() - frame_started
        expected_count = len(frame_timestamps(duration, args.frame_interval_sec))
        if len(frames) != expected_count:
            raise ValueError(
                f"FFmpeg extracted {len(frames)} frames for {asset_id}; expected {expected_count}"
            )
        print(f"{asset_id}: transcribing with local faster-whisper", flush=True)
        transcription_started = time.monotonic()
        transcript, detected_language = _transcribe(
            model, source_paths[asset_id], duration, asset_id,
            lambda message: print(message, flush=True),
        )
        transcription_seconds = time.monotonic() - transcription_started
        packets = build_analysis_packets(
            asset_id=asset_id,
            duration_sec=duration,
            frame_interval_sec=args.frame_interval_sec,
            packet_duration_sec=args.packet_duration_sec,
            frames=frames,
            transcript=transcript,
        )
        _write_json(asset_dir / "transcript.json", {
            "asset_id": asset_id,
            "duration_sec": duration,
            "detected_language": detected_language,
            "segments": transcript,
        })
        _write_json(asset_dir / "packets.json", packets)
        index["assets"].append({
            "asset_id": asset_id,
            "sha256": metadata["sha256"],
            "duration_sec": duration,
            "frame_count": len(frames),
            "transcript_segment_count": len(transcript),
            "detected_language": detected_language,
            "frame_extraction_seconds": round(frame_seconds, 3),
            "transcription_seconds": round(transcription_seconds, 3),
        })
        index["packets"].extend({
            "packet_id": packet["packet_id"],
            "asset_id": asset_id,
            "start_sec": packet["start_sec"],
            "end_sec": packet["end_sec"],
            "frame_count": len(packet["frames"]),
            "transcript_segment_count": len(packet["transcript"]),
            "path": str((asset_dir / "packets.json").resolve()),
        } for packet in packets)
        print(
            f"{asset_id}: ready ({len(frames)} frames, {len(transcript)} transcript segments)",
            flush=True,
        )

    index["processing_seconds"] = round(time.monotonic() - run_started, 3)
    _write_json(output_dir / "index.json", index)
    return output_dir


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Prepare timestamped local frames and transcript packets for KPL analysis."
    )
    parser.add_argument("--asset-map", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--asset-id", action="append", help="Limit the run to this asset ID; repeatable")
    parser.add_argument("--ffmpeg", help="FFmpeg executable; defaults to imageio-ffmpeg or PATH")
    parser.add_argument("--whisper-model", default="Systran/faster-whisper-small")
    parser.add_argument(
        "--model-cache", type=Path,
        default=Path.home() / ".cache" / "faster-whisper",
    )
    parser.add_argument("--device", default="cpu", choices=("cpu", "cuda"))
    parser.add_argument("--compute-type", default="int8")
    parser.add_argument("--frame-interval-sec", type=int, default=15)
    parser.add_argument("--packet-duration-sec", type=int, default=300)
    parser.add_argument("--frame-width", type=int, default=960)
    args = parser.parse_args(argv)
    if args.frame_interval_sec <= 0 or args.packet_duration_sec <= 0 or args.frame_width <= 0:
        parser.error("frame interval, packet duration, and frame width must be positive")

    try:
        output_dir = prepare_analysis(args)
    except (OSError, KeyError, TypeError, ValueError, RuntimeError, json.JSONDecodeError) as error:
        print(f"Analysis preparation failed: {error}", file=sys.stderr)
        return 2
    print(f"Wrote timestamped analysis packets: {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
