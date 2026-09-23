import copy
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from services import video_merger as merger
from services.clip_probe import probe_clip


def segment(codes, idle, speed=1):
    return {"stt_start": 0, "actual_end": 3, "speed": speed, "idle_duration": idle,
            "items": [{"type": "avatar", "code": code} for code in codes]}


class IdleExtensionTests(unittest.TestCase):
    def test_branching_last_clip_cache_and_speed_order(self):
        cases = [(["A"], .3, 1, 1, 0), (["A", "B"], .3, 1, 1, 0),
                 ([], .3, 1, 0, 1), (["A"], 0, 1, 0, 0),
                 (["A", "B"], .3, 2, 1, 0), (["MISSING"], .3, 1, 0, 2)]
        for codes, idle, speed, extensions, fallbacks in cases:
            with self.subTest(codes=codes, idle=idle, speed=speed), tempfile.TemporaryDirectory() as directory, \
                    patch.object(merger, "RESULTS_DIR", Path(directory)), \
                    patch.object(merger, "probe_clip", return_value={}), \
                    patch.object(merger, "_run_ffmpeg"), patch("builtins.print"), \
                    patch.object(merger, "_extend_last_frame", wraps=merger._extend_last_frame) as extend, \
                    patch.object(merger, "_make_idle_pose", wraps=merger._make_idle_pose) as pose, \
                    patch.object(merger, "_concat", wraps=merger._concat) as concat, \
                    patch.object(merger, "_apply_speed", wraps=merger._apply_speed) as apply_speed:
                merger.merge_timeline_to_video([segment(codes, idle, speed)], "test.mp4",
                                               {"A": Path("a.mp4"), "B": Path("b.mp4")})
                self.assertEqual(extend.call_count, extensions)
                self.assertEqual(pose.call_count, fallbacks)
                if extensions:
                    extended_source = extend.call_args.args[1]
                    if speed == 1:
                        self.assertTrue(extended_source.name.startswith("norm_"))
                        if len(codes) > 1:
                            self.assertTrue(concat.call_args_list[0].args[1][0].name.startswith("norm_"))
                            self.assertTrue(concat.call_args_list[0].args[1][-1].name.startswith("extended_"))
                    else:
                        self.assertEqual(extended_source.name, f"speed_{apply_speed.call_args.args[3]}.mp4")

    def test_extension_does_not_replace_cached_clip(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(merger, "RESULTS_DIR", Path(directory)), \
                patch.object(merger, "probe_clip", return_value={}), patch.object(merger, "_run_ffmpeg"), \
                patch.object(merger, "_normalize_clip", wraps=merger._normalize_clip) as normalize, \
                patch.object(merger, "_concat", wraps=merger._concat) as concat, patch("builtins.print"):
            entries = [segment(["A"], .3), {**segment(["A"], 0), "stt_start": 3}]
            merger.merge_timeline_to_video(entries, "test.mp4", {"A": Path("a.mp4")})
            normalize.assert_called_once()
            master = concat.call_args.args[1]
            self.assertTrue(master[0].name.startswith("extended_"))
            self.assertTrue(master[1].name.startswith("norm_"))


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "FFmpeg tools required")
class IdleExtensionFFmpegTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory(prefix="idle_extension_test_")
        cls.addClassCleanup(cls.directory.cleanup)
        cls.tmp = Path(cls.directory.name)
        source = cls.tmp / "source.mp4"
        subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i",
                        "color=c=red:s=1920x1080:r=30:d=0.4", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                        str(source)], capture_output=True, check=True)
        cls.source = source

    def test_old_idle_and_extension_duration_and_decoded_pts_match(self):
        for image_exists in (True, False):
            image = merger.IDLE_IMAGE_PATH if image_exists else self.tmp / "absent.png"
            for idle, speed in [(.0011, 1), (.034, 1), (.05, 1), (.101, 1),
                                (2.37, 1), (.3, 1.7), (.3, .8)]:
                with self.subTest(image=image_exists, idle=idle, speed=speed), patch.object(merger, "IDLE_IMAGE_PATH", image):
                    src = self.source
                    if speed != 1:
                        src = merger._apply_speed(self.tmp, src, speed, 100)
                    pose = merger._make_idle_pose(self.tmp, idle, 101)
                    baseline = merger._concat(self.tmp, [src, pose], 102)
                    result = merger._extend_last_frame(self.tmp, src, idle, 103)
                    # Include a following clip: catches boundary DTS regressions.
                    before = merger._concat(self.tmp, [baseline, self.source], 104)
                    after = merger._concat(self.tmp, [result, self.source], 105)
                    a, b = (probe_clip(path, {}) for path in (before, after))
                    self.assertEqual(a["format"]["duration"], b["format"]["duration"])
                    self.assertEqual(a["streams"][0]["nb_frames"], b["streams"][0]["nb_frames"])
                    video = b["streams"][0]
                    self.assertEqual((video["width"], video["height"], video["codec_name"],
                                      video["pix_fmt"], video["r_frame_rate"], len(b["streams"])),
                                     (1920, 1080, "h264", "yuv420p", "30/1", 1))
                    decoded_pts = []
                    for path in (before, after):
                        frames = json.loads(subprocess.check_output([
                            "ffprobe", "-v", "error", "-select_streams", "v:0", "-show_frames",
                            "-show_entries", "frame=best_effort_timestamp", "-of", "json", str(path)]))["frames"]
                        pts = [f["best_effort_timestamp"] for f in frames]
                        self.assertTrue(all(x < y for x, y in zip(pts, pts[1:])))
                        decoded_pts.append(pts)
                        decoded = subprocess.run(["ffmpeg", "-v", "warning", "-xerror", "-i", str(path),
                                                  "-f", "null", "-"], capture_output=True, text=True, check=True)
                        self.assertEqual(decoded.stderr, "")
                    self.assertEqual(*decoded_pts)
                    # All padded frames must still show the red sign frame,
                    # not idle_pose.png. Reduce to one RGB pixel per frame.
                    pixels = subprocess.check_output(["ffmpeg", "-v", "error", "-i", str(result),
                        "-vf", "scale=1:1", "-pix_fmt", "rgb24", "-f", "rawvideo", "-"])
                    self.assertTrue(all(pixels[i] > 200 and pixels[i + 1] < 30 and pixels[i + 2] < 30
                                        for i in range(0, len(pixels), 3)))

    def test_mixed_timeline_matches_legacy_concat_length(self):
        # A reference adapter substitutes the previous sign + separate idle
        # operation at each extension point without changing other stages.
        def legacy(tmp, src, duration, idx):
            idle = merger._make_idle_pose(tmp, duration, idx)
            return merger._concat(tmp, [src, idle], idx)
        speed_end = 1.7 + .4 / 1.7 + .2
        entries = [{**segment(["A", "A"], .3), "actual_end": 1.1},
                   {**segment([], .4), "stt_start": 1.3, "actual_end": 1.7},
                   {**segment(["A"], .2, 1.7), "stt_start": 1.7, "actual_end": speed_end},
                   {**segment(["A"], 0), "stt_start": speed_end, "actual_end": speed_end + .4}]
        snapshot = copy.deepcopy(entries)
        durations = []
        extend = merger._extend_last_frame
        for mode in ("legacy", "extended"):
            with patch.object(merger, "RESULTS_DIR", self.tmp), patch("builtins.print"), \
                    patch.object(merger, "_extend_last_frame", side_effect=legacy if mode == "legacy" else extend):
                merger.merge_timeline_to_video(entries, mode + ".mp4", {"A": self.source})
            durations.append(probe_clip(self.tmp / (mode + ".mp4"), {})["format"]["duration"])
        self.assertEqual(*durations)
        self.assertLess(abs(float(durations[1]) - entries[-1]["actual_end"]), .1)
        self.assertEqual(entries, snapshot)
