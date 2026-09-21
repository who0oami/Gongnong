import unittest
from unittest.mock import patch
from services.gloss_display_service import build_complete_display_sequence
from services.timeline_builder import build_timeline


class CompleteDisplayTest(unittest.TestCase):
    @patch("services.gloss_display_service.resolve_clip_path", return_value="/static/videos/A.mp4")
    @patch("services.gloss_display_service.build_display_sequence")
    def test_missing_negation_keeps_full_source(self, match, resolve):
        match.return_value = [{"type":"avatar","gloss":"가다","code":"A"}, {"type":"caption","text":"않다"}]
        self.assertEqual(build_complete_display_sequence("학교에 가지 않아요.", ["가다","않다"]),
                         [{"type":"caption","text":"학교에 가지 않아요."}])

    @patch("services.gloss_display_service.resolve_clip_path", return_value=None)
    @patch("services.gloss_display_service.build_display_sequence")
    def test_missing_file_captions_only_that_item(self, match, resolve):
        match.return_value = [{"type":"avatar","gloss":"가다","code":"A"}]
        self.assertEqual(build_complete_display_sequence("학교에 가요.", ["가다"]),
                         [{"type":"caption","text":"가다"}])

    @patch("services.gloss_display_service.resolve_clip_path", return_value="/static/videos/A.mp4")
    @patch("services.gloss_display_service.build_display_sequence")
    def test_complete_sequence_stays_avatar(self, match, resolve):
        items = [{"type":"avatar","gloss":"가다","code":"A"}]
        match.return_value = items
        self.assertEqual(build_complete_display_sequence("가요", ["가다"]), items)

    def test_caption_time_is_not_borrowed_and_source_reaches_renderer(self):
        result = build_timeline([
            {"start":0,"end":1,"display_sequence":[{"type":"avatar","code":"A"}]},
            {"start":1,"end":4,"display_sequence":[{"type":"caption","text":"원문"}],"caption_text":"전체 원문"},
        ], lambda code: 2)
        self.assertEqual(result[0]["overflow_seconds"], 1)
        self.assertEqual(result[1]["idle_duration"], 3)
        self.assertEqual(result[1]["caption_text"], "전체 원문")
        self.assertEqual(result[1]["actual_start"], 2)
        self.assertEqual(result[1]["actual_end"], 5)


class MixedItemsTest(unittest.TestCase):
    @patch("services.gloss_display_service.resolve_clip_path", return_value="/static/videos/A.mp4")
    @patch("services.gloss_display_service.build_display_sequence")
    def test_unknown_noun_does_not_remove_matched_sign(self, match, resolve):
        items = [{"type":"caption","text":"민수"}, {"type":"avatar","gloss":"가다","code":"A"}]
        match.return_value = items
        self.assertEqual(build_complete_display_sequence("민수가 가요.", ["민수","가다"]), items)

    def test_overflow_propagates_and_later_gap_absorbs_delay(self):
        timeline = build_timeline([
            {"start":0,"end":1,"display_sequence":[{"type":"avatar","code":"A"}]},
            {"start":1,"end":2,"display_sequence":[{"type":"avatar","code":"B"}]},
            {"start":8,"end":9,"display_sequence":[{"type":"caption","text":"끝"}]},
        ], lambda code: 3)
        self.assertEqual([(x["actual_start"],x["actual_end"]) for x in timeline], [(0,3),(3,6),(8,9)])

    def test_invalid_duration_and_order_are_rejected(self):
        with self.assertRaises(ValueError):
            build_timeline([{"start":1,"end":1,"display_sequence":[]}],lambda code:1)
