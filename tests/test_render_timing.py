import os
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

from botocore.exceptions import ClientError

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from routers import job
from services import clip_probe
from services import timing, clip_resolver as resolver, video_merger as merger


def avatar(code):
    return {"type": "avatar", "code": code}


class RenderTimingTests(unittest.TestCase):
    def setUp(self):
        probe = patch.object(merger, "probe_clip", return_value={})
        probe.start()
        self.addCleanup(probe.stop)

    def test_s3_counts_attempts_success_failure_and_unique_words(self):
        items = [avatar("WORD0001"), avatar("WORD0001"), avatar("WORD0002"), avatar("SEN0001")]
        with tempfile.TemporaryDirectory() as directory, \
                patch.dict(os.environ, S3_CLIP_BUCKET="test-bucket"), \
                patch.object(resolver.boto3, "client") as factory, \
                patch("builtins.print") as log:
            factory.return_value.download_file.side_effect = [
                None,
                ClientError({"Error": {"Code": "404"}}, "GetObject"),
            ]
            result = resolver.resolve_clips(items, Path(directory))
        self.assertIsNotNone(result["WORD0001"])
        self.assertIsNone(result["WORD0002"])
        factory.return_value.download_file.assert_called()
        self.assertEqual(factory.return_value.download_file.call_count, 2)
        message = log.call_args.args[0]
        self.assertIn("avatar_items=4 unique_words=2 downloads=2 success=1 failed=1", message)
        self.assertEqual(log.call_count, 1)

    def test_missing_bucket_is_not_counted_as_download_attempt(self):
        with tempfile.TemporaryDirectory() as directory, \
                patch.dict(os.environ, S3_CLIP_BUCKET=""), patch("builtins.print") as log:
            with self.assertRaises(resolver.ClipStorageUnavailable):
                resolver.resolve_clips([avatar("WORD0001")], Path(directory))
        self.assertIn("downloads=0 success=0 failed=0", log.call_args.args[0])

    def test_probe_cache_and_missing_item_counters(self):
        items = [avatar("WORD0001"), avatar("WORD0001"), avatar("WORD0002")]
        with patch.object(job, "resolve_clips", return_value={"WORD0001": Path("test.mp4"), "WORD0002": None}), \
                patch.object(clip_probe.subprocess, "run", return_value=Mock(stdout=json.dumps({"format": {"duration": "1.0"}}))) as probe, \
                patch.object(job, "merge_timeline_to_video", return_value="result.mp4"), \
                patch("builtins.print") as log:
            self.assertEqual(job._render_job_video("counter-job", [{"start": 0, "end": 4, "display_sequence": items}]), "result.mp4")
        probe.assert_called_once()
        messages = "\n".join(c.args[0] for c in log.call_args_list)
        self.assertIn("executions=1 cache_hits=1", messages)
        self.assertIn("segments=1 avatar_items=3 unique_avatar_codes=2 missing_clips=1", messages)
        for name in ("DISPLAY_SEQUENCE_PREP", "S3_CLIP_RESOLVE", "FFPROBE_DURATION", "TIMELINE_CALC", "VIDEO_MERGE"):
            self.assertIn(f"[Render Timing][counter-job] {name}", messages)
        self.assertIsNone(timing.render_metrics.get())

    def test_ffmpeg_repeated_sources_speed_concat_and_black_fallback(self):
        timeline = [{"stt_start": 1, "actual_end": 5, "speed": 1.1, "idle_duration": 1,
                     "items": [avatar("WORD0001"), avatar("WORD0001"), avatar("WORD0002")]}]
        with tempfile.TemporaryDirectory() as directory, \
                patch.object(merger, "RESULTS_DIR", Path(directory)), \
                patch.object(merger, "IDLE_IMAGE_PATH", Path(directory) / "absent.png"), \
                patch.object(merger, "_run_ffmpeg") as ffmpeg, patch("builtins.print") as log:
            result = merger.merge_timeline_to_video(timeline, "result.mp4", {"WORD0001": Path("source.mp4"), "WORD0002": None})
        self.assertEqual(result, "/static/results/result.mp4")
        self.assertEqual(ffmpeg.call_count, 6)
        self.assertEqual(log.call_count, 1)
        message = log.call_args.args[0]
        for expected in ("normalize: count=1", "idle_pose: count=1", "black: count=1", "speed: count=1", "concat: count=2",
                         "normalize_calls=1 normalize_unique_sources=1", "normalize_cache_hits=1",
                         "normalize_cache_misses=1", "idle_cache_hits=1", "idle_cache_misses=1",
                          "idle_extended_count=1", "idle_extension: count=1", "merge_total="):
            self.assertIn(expected, message)
        self.assertIsNone(timing.ffmpeg_metrics.get())

    def test_ffmpeg_failure_still_emits_summary_and_propagates(self):
        timeline = [{"stt_start": 0, "actual_end": 1, "speed": 1, "idle_duration": 0,
                     "items": [avatar("WORD0001")]}]
        with tempfile.TemporaryDirectory() as directory, \
                patch.object(merger, "RESULTS_DIR", Path(directory)), \
                patch.object(merger, "_run_ffmpeg", side_effect=RuntimeError("private-path")), \
                patch("builtins.print") as log:
            with self.assertRaisesRegex(RuntimeError, "private-path"):
                merger.merge_timeline_to_video(timeline, "result.mp4", {"WORD0001": Path("source.mp4")})
        self.assertIn("normalize: count=1", log.call_args.args[0])
        self.assertNotIn("private-path", log.call_args.args[0])
        self.assertIsNone(timing.ffmpeg_metrics.get())

    def test_cache_preserves_order_segment_speed_and_is_local_to_merge(self):
        source = Path("source.mp4")
        other = Path("other.mp4")
        timeline = [
            {"stt_start": 0, "actual_end": 3, "speed": 1.2, "idle_duration": 0,
             "items": [avatar("A"), avatar("B"), avatar("ALIAS")]},
            {"stt_start": 3, "actual_end": 4, "speed": 0.8, "idle_duration": 0,
             "items": [avatar("A")]},
        ]
        with tempfile.TemporaryDirectory() as directory, \
                patch.object(merger, "RESULTS_DIR", Path(directory)), \
                patch.object(merger, "_run_ffmpeg"), \
                patch.object(merger, "_normalize_clip", wraps=merger._normalize_clip) as normalize, \
                patch.object(merger, "_apply_speed", wraps=merger._apply_speed) as speed, \
                patch.object(merger, "_concat", wraps=merger._concat) as concat, \
                patch("builtins.print"):
            for filename in ("first.mp4", "second.mp4"):
                merger.merge_timeline_to_video(timeline, filename, {"A": source, "ALIAS": source, "B": other})
            self.assertEqual([c.args[1] for c in normalize.call_args_list], [source, other, source, other])
            self.assertEqual([c.args[2] for c in speed.call_args_list], [1.2, 0.8, 1.2, 0.8])
            for offset in (0, 2):
                parts = concat.call_args_list[offset].args[1]
                self.assertEqual(parts[0], parts[2])
                self.assertNotEqual(parts[0], parts[1])
                self.assertEqual(speed.call_args_list[offset + 1].args[1], parts[0])
                master = concat.call_args_list[offset + 1].args[1]
                self.assertEqual(master, [c.args[0] / f"speed_{c.args[3]}.mp4"
                                          for c in speed.call_args_list[offset:offset + 2]])
            first_tmp = normalize.call_args_list[0].args[0]
            second_tmp = normalize.call_args_list[2].args[0]
            self.assertNotEqual(first_tmp, second_tmp)
            self.assertFalse(first_tmp.exists())
            self.assertFalse(second_tmp.exists())

    def test_idle_cache_matches_ffmpeg_precision_without_crossing_boundary(self):
        durations = [1.0001, 1.0004, 1.0006]
        timeline = [{"stt_start": i * 2, "actual_end": (i + 1) * 2, "speed": 1,
                     "idle_duration": duration, "items": []} for i, duration in enumerate(durations)]
        with tempfile.TemporaryDirectory() as directory, \
                patch.object(merger, "RESULTS_DIR", Path(directory)), \
                patch.object(merger, "IDLE_IMAGE_PATH", Path(directory) / "idle.png"), \
                patch.object(merger, "_run_ffmpeg") as ffmpeg, \
                patch.object(merger, "_concat", wraps=merger._concat) as concat, \
                patch("builtins.print") as log:
            merger.IDLE_IMAGE_PATH.touch()
            merger.merge_timeline_to_video(timeline, "result.mp4", {})
            idle_args = [c.args[0] for c in ffmpeg.call_args_list if "-loop" in c.args[0]]
            self.assertEqual([args[args.index("-t") + 1] for args in idle_args], ["1.000", "1.001"])
            parts = concat.call_args.args[1]
            self.assertEqual(parts[0], parts[1])
            self.assertNotEqual(parts[1], parts[2])
        self.assertIn("idle_cache_hits=1", log.call_args.args[0])
        self.assertIn("idle_cache_misses=2", log.call_args.args[0])

    def test_accumulation_uses_perf_counter_on_success_and_failure(self):
        metrics = timing.Metrics()
        with patch.object(timing.time, "perf_counter", side_effect=[1, 3, 4, 7]):
            with metrics.measure("operation"):
                pass
            with self.assertRaises(ValueError):
                with metrics.measure("operation"):
                    raise ValueError()
        self.assertEqual(metrics.counts["operation"], 2)
        self.assertEqual(metrics.seconds["operation"], 5)


if __name__ == "__main__":
    unittest.main()
