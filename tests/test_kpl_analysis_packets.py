import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from kpl_analysis_packets import _extract_frames, build_analysis_packets, frame_timestamps


class AnalysisPacketTests(unittest.TestCase):
    def test_frame_timestamps_cover_source_without_passing_duration(self):
        self.assertEqual(frame_timestamps(31, 10), [0, 10, 20, 30])
        self.assertEqual(frame_timestamps(30, 10), [0, 10, 20])

    def test_analysis_packets_keep_frames_and_transcript_in_source_time(self):
        packets = build_analysis_packets(
            asset_id="P1",
            duration_sec=125,
            frame_interval_sec=15,
            packet_duration_sec=60,
            frames=[
                {"timestamp_sec": 0, "path": "frame-000000.jpg"},
                {"timestamp_sec": 15, "path": "frame-000001.jpg"},
                {"timestamp_sec": 60, "path": "frame-000002.jpg"},
                {"timestamp_sec": 120, "path": "frame-000003.jpg"},
            ],
            transcript=[
                {"start_sec": 59.5, "end_sec": 61.0, "text": "跨包边界解说"},
                {"start_sec": 60.0, "end_sec": 62.0, "text": "第二包解说"},
                {"start_sec": 120.0, "end_sec": 124.0, "text": "末包解说"},
            ],
        )

        self.assertEqual([(packet["start_sec"], packet["end_sec"]) for packet in packets], [
            (0, 60), (60, 120), (120, 125),
        ])
        self.assertEqual([frame["timestamp_sec"] for frame in packets[0]["frames"]], [0, 15])
        self.assertEqual([frame["timestamp_sec"] for frame in packets[1]["frames"]], [60])
        self.assertEqual([frame["timestamp_sec"] for frame in packets[2]["frames"]], [120])
        self.assertEqual([row["text"] for row in packets[0]["transcript"]], ["跨包边界解说"])
        self.assertEqual([row["text"] for row in packets[1]["transcript"]], ["第二包解说"])
        self.assertEqual([row["text"] for row in packets[2]["transcript"]], ["末包解说"])

    def test_packet_builder_rejects_timestamps_outside_source(self):
        with self.assertRaisesRegex(ValueError, "frame timestamp"):
            build_analysis_packets(
                asset_id="P1", duration_sec=20, frame_interval_sec=10,
                packet_duration_sec=10,
                frames=[{"timestamp_sec": 20, "path": "frame.jpg"}],
                transcript=[],
            )

        with self.assertRaisesRegex(ValueError, "transcript timestamp"):
            build_analysis_packets(
                asset_id="P1", duration_sec=20, frame_interval_sec=10,
                packet_duration_sec=10, frames=[],
                transcript=[{"start_sec": -1, "end_sec": 1, "text": "越界"}],
            )

    def test_packet_builder_rejects_nonpositive_intervals(self):
        with self.assertRaisesRegex(ValueError, "positive"):
            frame_timestamps(20, 0)
        with self.assertRaisesRegex(ValueError, "positive"):
            build_analysis_packets(
                asset_id="P1", duration_sec=20, frame_interval_sec=10,
                packet_duration_sec=0, frames=[], transcript=[],
            )

    def test_ffmpeg_extracts_timestamped_frames_from_synthetic_video(self):
        try:
            import imageio_ffmpeg
        except ImportError:
            self.skipTest("imageio-ffmpeg is available only in the configured local ASR environment")

        ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "synthetic.mp4"
            result = subprocess.run([
                ffmpeg, "-nostdin", "-hide_banner", "-loglevel", "error",
                "-f", "lavfi", "-i", "color=c=red:s=320x180:r=30:d=35",
                "-an", "-c:v", "mpeg4", "-pix_fmt", "yuv420p", str(source),
            ], capture_output=True, text=True, check=False)
            self.assertEqual(result.returncode, 0, result.stderr)

            frames = _extract_frames(ffmpeg, source, root / "frames", 10, 160)

            self.assertEqual([frame["timestamp_sec"] for frame in frames], [0, 10, 20, 30])
            self.assertTrue(all(Path(frame["path"]).is_file() for frame in frames))


if __name__ == "__main__":
    unittest.main()
