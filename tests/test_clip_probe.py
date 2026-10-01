import copy
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from services import clip_probe, video_merger as merger
from routers import job


def metadata():
    return {
        "format": {"format_name": "mov,mp4,m4a,3gp,3g2,mj2", "start_time": "0", "duration": "1"},
        "streams": [{"index": 0, "codec_type": "video", "codec_name": "h264",
                     "codec_tag_string": "avc1", "width": 1920, "height": 1080,
                     "pix_fmt": "yuv420p", "profile": "High", "level": 40,
                     "field_order": "progressive", "sample_aspect_ratio": "1:1",
                     "has_b_frames": 2, "is_avc": "true", "nal_length_size": "4",
                     "extradata_size": 50, "r_frame_rate": "30/1", "avg_frame_rate": "30/1",
                     "time_base": "1/15360", "start_time": "0", "duration": "1", "nb_frames": "30"}],
    }


class ClipProbeTests(unittest.TestCase):
    def test_eligibility_rejects_incompatible_or_incomplete_metadata(self):
        self.assertTrue(clip_probe.is_clip_concat_ready(metadata()))
        for key, value in [("width", 1280), ("height", 720), ("r_frame_rate", "25/1"),
                           ("avg_frame_rate", "30000/1001"), ("pix_fmt", "yuv444p"),
                           ("codec_name", "hevc"), ("time_base", "1/90000"),
                           ("sample_aspect_ratio", "4:3"), ("has_b_frames", 0),
                           ("start_time", ".1"), ("profile", "Main"), ("level", 51),
                           ("side_data_list", [{"rotation": 90}]), ("duration", "1.1")]:
            with self.subTest(key=key):
                data = metadata()
                data["streams"][0][key] = value
                self.assertFalse(clip_probe.is_clip_concat_ready(data))
        data = metadata()
        data["streams"].append({"codec_type": "audio"})
        self.assertFalse(clip_probe.is_clip_concat_ready(data))
        for data in ({}, {"streams": []}, {"streams": [{}]}):
            self.assertFalse(clip_probe.is_clip_concat_ready(data))

    def test_frame_count_and_duration_must_match_constant_frame_rate(self):
        for key, value in [("nb_frames", "29"), ("nb_frames", "0"), ("duration", "1.1")]:
            data = metadata()
            data["streams"][0][key] = value
            self.assertFalse(clip_probe.is_clip_concat_ready(data))

    def test_probe_does_not_request_packet_metadata(self):
        path = Path("clip.mp4")
        with patch.object(clip_probe.subprocess, "run", return_value=Mock(stdout=json.dumps(metadata()))) as run:
            clip_probe.probe_clip(path, {})
        args = run.call_args.args[0]
        self.assertNotIn("-show_packets", args)

    def test_duration_and_merge_share_one_probe_and_cache_is_job_local(self):
        path = Path("clip.mp4")
        cache = {}
        timeline = [{"stt_start": 0, "actual_end": 2, "speed": 1, "idle_duration": 0,
                     "items": [{"type": "avatar", "code": code} for code in ("A", "ALIAS")]}]
        with tempfile.TemporaryDirectory() as directory, \
                patch.object(merger, "RESULTS_DIR", Path(directory)), \
                patch.object(clip_probe.subprocess, "run", return_value=Mock(stdout=json.dumps(metadata()))) as probe, \
                patch.object(merger, "_run_ffmpeg"), patch.object(merger, "_normalize_clip") as normalize, \
                patch("builtins.print") as log:
            mapping = {"A": path, "ALIAS": path}
            self.assertEqual(job._get_clip_duration("A", mapping, cache), 1)
            self.assertEqual(job._get_clip_duration("ALIAS", mapping, cache), 1)
            self.assertEqual(merger.merge_timeline_to_video(timeline, "job.mp4", mapping, cache),
                             "/static/results/job.mp4")
            probe.assert_called_once()
            normalize.assert_not_called()
            message = log.call_args.args[0]
            for expected in ("normalize_skipped=1", "normalize_required=0", "probe_cache_hits=1",
                             "probe_cache_misses=0", "normalize_cache_hits=1"):
                self.assertIn(expected, message)
            clip_probe.probe_clip(path, {})
            self.assertEqual(probe.call_count, 2)


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "FFmpeg tools required")
class ClipProbeFFmpegTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory(prefix="clip_probe_test_")
        cls.addClassCleanup(cls.directory.cleanup)
        cls.tmp = Path(cls.directory.name)
        cls.paths = {}
        cls.cache = {}
        for name, size, fps, pix_fmt, extra in [
            ("ready", "1920x1080", 30, "yuv420p", []),
            ("resolution", "320x180", 30, "yuv420p", []),
            ("fps", "1920x1080", 25, "yuv420p", []),
            ("pixels", "1920x1080", 30, "yuv444p", []),
            ("audio", "1920x1080", 30, "yuv420p", ["-c:a", "aac"]),
            ("no_b_frames", "1920x1080", 30, "yuv420p", ["-bf", "0"]),
        ]:
            path = cls.tmp / f"{name}.mp4"
            args = ["ffmpeg", "-v", "error", "-f", "lavfi", "-i", f"color=c=blue:s={size}:r={fps}"]
            if name == "audio":
                args += ["-f", "lavfi", "-i", "anullsrc=r=48000:cl=mono"]
            args += ["-t", "0.4", "-c:v", "libx264", "-pix_fmt", pix_fmt, *extra, str(path)]
            subprocess.run(args, capture_output=True, check=True)
            cls.paths[name] = path
            clip_probe.probe_clip(path, cls.cache)

    def test_real_mp4_normalize_decision_and_output_spec(self):
        for name, source in self.paths.items():
            with self.subTest(name=name), patch.object(merger, "RESULTS_DIR", self.tmp), \
                    patch.object(merger, "_normalize_clip", wraps=merger._normalize_clip) as normalize, \
                    patch("builtins.print"):
                timeline = [{"stt_start": 0, "actual_end": .8, "speed": 1, "idle_duration": 0,
                             "items": [{"type": "avatar", "code": "A"}] * 2}]
                merger.merge_timeline_to_video(timeline, f"output_{name}.mp4", {"A": source}, self.cache)
                self.assertEqual(normalize.call_count, 0 if name == "ready" else 1)
                data = clip_probe.probe_clip(self.tmp / f"output_{name}.mp4", {})
                self.assertEqual(len(data["streams"]), 1)
                video = data["streams"][0]
                self.assertEqual((video["width"], video["height"], video["codec_name"], video["pix_fmt"],
                                  video["r_frame_rate"], video["avg_frame_rate"]),
                                 (1920, 1080, "h264", "yuv420p", "30/1", "30/1"))

    def test_mixed_concat_speed_idle_gap_and_missing_keep_original_timing(self):
        mapping = {"READY": self.paths["ready"], "LOW": self.paths["resolution"], "MISSING": None}
        timeline = [
            {"stt_start": .2, "actual_end": 1.2, "speed": 1, "idle_duration": .2,
             "items": [{"type": "avatar", "code": code} for code in ("READY", "LOW")]},
            {"stt_start": 1.4, "actual_end": 2.3, "speed": 2, "idle_duration": .2,
             "items": [{"type": "avatar", "code": code} for code in ("MISSING", "READY")]},
            {"stt_start": 2.3, "actual_end": 2.7, "speed": 1, "idle_duration": 0,
             "items": [{"type": "avatar", "code": "READY"}]},
        ]
        snapshot = copy.deepcopy(timeline)
        results = []
        for name, force in (("baseline", True), ("optimized", False)):
            with patch.object(merger, "RESULTS_DIR", self.tmp), patch("builtins.print"), \
                    patch.object(merger, "is_clip_concat_ready",
                                 side_effect=lambda data: False if force else clip_probe.is_clip_concat_ready(data)):
                merger.merge_timeline_to_video(timeline, name + ".mp4", mapping, self.cache)
            path = self.tmp / (name + ".mp4")
            data = clip_probe.probe_clip(path, {})
            # Pixel hashes differ because the baseline performs a lossy encode.
            results.append((data["format"]["duration"], data["streams"][0]["nb_frames"]))
            decode = subprocess.run(["ffmpeg", "-v", "warning", "-xerror", "-i", str(path),
                                     "-f", "null", "-"], capture_output=True, text=True, check=True)
            self.assertEqual(decode.stderr, "")
        self.assertEqual(results[0], results[1])
        self.assertEqual(timeline, snapshot)
