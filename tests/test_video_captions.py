import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from services import video_merger as v


class VideoCaptionTest(unittest.TestCase):
    def test_text_is_utf8_data_and_filter_expansion_is_disabled(self):
        with tempfile.TemporaryDirectory() as folder:
            tmp = Path(folder)
            (tmp / "caption-font.ttf").write_bytes(b"fixture-font")
            with patch.object(v, "_run_ffmpeg") as run:
                v._overlay_caption(tmp, tmp / "source.mp4", "학교에 갈 필요 없어요. 100% %{n} ' :", 0)
            self.assertIn("학교에 갈 필요 없어요.", (tmp / "caption_0.txt").read_text(encoding="utf-8"))
            self.assertIn("expansion=none", run.call_args.args[0][3])
            self.assertEqual(run.call_args.kwargs["cwd"], tmp)

    def test_missing_configured_font_fails_clearly(self):
        with patch.dict("os.environ", {"KSL_CAPTION_FONT":"Z:/nonexistent/caption.ttf"}):
            with self.assertRaisesRegex(RuntimeError, "KSL_CAPTION_FONT"):
                v._caption_font()

    def test_caption_only_segment_is_rendered_for_full_duration(self):
        segment = {"stt_start":0,"stt_end":3,"actual_end":3,"speed":1,"idle_duration":3,
                   "items":[{"type":"caption","text":"열다 금지"}],"caption_text":"문을 열지 마세요."}
        with tempfile.TemporaryDirectory() as folder, patch.object(v,"RESULTS_DIR",Path(folder)), \
             patch.object(v,"_make_idle_pose",return_value=Path(folder)/"base.mp4") as idle, \
             patch.object(v,"_overlay_caption",return_value=Path(folder)/"caption.mp4") as overlay, \
             patch.object(v,"_concat"):
            v.merge_timeline_to_video([segment],"result.mp4")
            self.assertEqual(idle.call_args.args[1],3)
            self.assertEqual(overlay.call_args.args[2],"열다 금지")
            self.assertEqual(idle.call_count,1)


class MixedRendererTest(unittest.TestCase):
    def test_caption_overlay_keeps_existing_avatar_clip(self):
        segment={"stt_start":0,"stt_end":3,"actual_start":0,"actual_end":3,"speed":1,"idle_duration":2,
                 "items":[{"type":"avatar","code":"A","gloss":"가다","duration":1}, {"type":"caption","text":"민수"}]}
        with tempfile.TemporaryDirectory() as folder, patch.object(v,"RESULTS_DIR",Path(folder)), \
             patch.object(v,"resolve_clip_path",return_value="/static/videos/A.mp4"), \
             patch.object(v,"_normalize_clip",return_value=Path(folder)/"sign.mp4") as normalize, \
             patch.object(v,"_make_idle_pose",return_value=Path(folder)/"idle.mp4"), \
             patch.object(v,"_concat",return_value=Path(folder)/"joined.mp4"), \
             patch.object(v,"_overlay_caption",return_value=Path(folder)/"caption.mp4") as overlay:
            v.merge_timeline_to_video([segment],"result.mp4")
            normalize.assert_called_once()
            self.assertEqual(overlay.call_args.args[2],"민수")


class LateMissingModalityTest(unittest.TestCase):
    def test_late_missing_negation_never_plays_affirmative_clip(self):
        segment={"stt_start":0,"stt_end":3,"actual_start":0,"actual_end":3,"speed":1,"idle_duration":1,
                 "caption_text":"학교에 가지 않아요.", "items":[
                 {"type":"avatar","code":"A","gloss":"가다","duration":1},
                 {"type":"avatar","code":"B","gloss":"않다","duration":1}]}
        with tempfile.TemporaryDirectory() as folder, patch.object(v,"RESULTS_DIR",Path(folder)), \
             patch.object(v,"resolve_clip_path",side_effect=lambda code: "/A.mp4" if code=="A" else None), \
             patch.object(v,"_normalize_clip") as normalize, \
             patch.object(v,"_make_idle_pose",return_value=Path(folder)/"idle.mp4"), \
             patch.object(v,"_concat"), \
             patch.object(v,"_overlay_caption",return_value=Path(folder)/"caption.mp4") as overlay:
            v.merge_timeline_to_video([segment],"result.mp4")
            normalize.assert_not_called()
            self.assertEqual(overlay.call_args.args[2],"학교에 가지 않아요.")
