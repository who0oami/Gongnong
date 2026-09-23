from pathlib import Path
from copy import deepcopy
import sys
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from services import timeline_builder as builder


def segment(start, end, *codes):
    return {"start": start, "end": end,
            "display_sequence": [{"type": "avatar", "code": code} for code in codes]}


class TimelineBuilderTests(unittest.TestCase):
    def test_midpoint_normalization_cases_and_invariants(self):
        cases = [
            ([(0, 3), (3, 8)], [(0, 3), (3, 8)]),
            ([(5.319, 11.679), (8.519, 15.120)], [(5.319, 10.099), (10.099, 15.120)]),
            ([(5.319, 11.679), (8.519, 15.120), (11.679, 18.480)],
             [(5.319, 10.099), (10.099, 13.3995), (13.3995, 18.480)]),
            ([(0, 3), (5, 8)], [(0, 3), (5, 8)]),
            ([(0, 4), (2, 6), (8, 10)], [(0, 3), (3, 6), (8, 10)]),
            ([(0, 4), (0, 6)], [(0, 2), (2, 6)]),
            ([(0, 6), (2, 6)], [(0, 4), (4, 6)]),
            ([(0, 4), (0, 4)], [(0, 2), (2, 4)]),
            ([(1, 1.000002), (1.000001, 1.000003)],
             [(1, 1.0000015), (1.0000015, 1.000003)]),
            ([(5, 98.560)], [(5, 98.560)]),
            ([], []),
        ]
        for intervals, expected in cases:
            with self.subTest(intervals=intervals), patch("builtins.print"):
                originals = [dict(segment(start, end, str(i)), gloss_sequence=[str(i)],
                                  llm_result={"text": str(i)}) for i, (start, end) in enumerate(intervals)]
                snapshot = deepcopy(originals)
                result = builder.normalize_overlapping_segments(originals)
                self.assertEqual(originals, snapshot)
                self.assertEqual(len(result), len(expected))
                for original, adjusted, (start, end) in zip(originals, result, expected):
                    self.assertIsNot(original, adjusted)
                    self.assertAlmostEqual(adjusted["start"], start, places=12)
                    self.assertAlmostEqual(adjusted["end"], end, places=12)
                    self.assertLess(adjusted["start"], adjusted["end"])
                    for field in ("display_sequence", "gloss_sequence", "llm_result"):
                        self.assertEqual(adjusted[field], original[field])
                for left, right in zip(result, result[1:]):
                    self.assertLessEqual(left["end"], right["start"])
                if result:
                    self.assertEqual(result[0]["start"], originals[0]["start"])
                    self.assertEqual(result[-1]["end"], originals[-1]["end"])

    def test_invalid_midpoints_raise_instead_of_reordering_or_extending(self):
        for intervals in ([(0, 10), (1, 2)], [(0, 10), (1, 9), (2, 3)],
                          [(0, 4), (0, 4), (0, 4)]):
            with self.subTest(intervals=intervals):
                originals = [segment(start, end) for start, end in intervals]
                snapshot = deepcopy(originals)
                with self.assertRaisesRegex(ValueError, "Segment .*midpoint normalization"):
                    builder.normalize_overlapping_segments(originals)
                self.assertEqual(originals, snapshot)

    def test_render_timeline_uses_normalized_intervals_without_mutating_source(self):
        segments = [segment(5.319, 11.679, "A"), segment(8.519, 15.120, "B"),
                    segment(11.679, 18.480, "C")]
        snapshot = deepcopy(segments)
        with patch("builtins.print") as log:
            result = builder.build_timeline(segments, lambda _: 10)
        self.assertEqual(segments, snapshot)
        cursor = 0
        for entry in result:
            self.assertGreaterEqual(entry["stt_start"], cursor)
            cursor += entry["stt_start"] - cursor
            cursor += 10 / entry["speed"] + entry["idle_duration"]
            self.assertAlmostEqual(cursor, entry["stt_end"])
            self.assertEqual(entry["actual_end"], entry["stt_end"])
        self.assertAlmostEqual(cursor, 18.480)
        self.assertAlmostEqual(result[1]["speed"], 10 / (13.3995 - 10.099))
        messages = "\n".join(c.args[0] for c in log.call_args_list)
        self.assertIn("[Timeline Normalize] segment=2 original=8.519000-15.120000 normalized=10.099000-13.399500", messages)
        self.assertIn("original_last_end=18.480000 normalized_last_end=18.480000", messages)

    def test_speed_is_unlimited_and_short_sequences_keep_idle(self):
        for duration in (0, 2, 3.2, 3.52, 5.44, 320):
            with self.subTest(duration=duration), patch("builtins.print"):
                entry = builder.build_timeline([segment(9.3, 12.5, "A")], lambda _: duration)[0]
                target = 12.5 - 9.3
                self.assertAlmostEqual(entry["speed"], max(1, duration / target))
                self.assertAlmostEqual(entry["idle_duration"], max(0, target - duration))
                self.assertAlmostEqual(duration / entry["speed"] + entry["idle_duration"], target)
                self.assertEqual(entry["actual_end"], 12.5)
                self.assertEqual(entry["overflow_seconds"], 0)

    def test_long_sequences_do_not_borrow_idle_or_extend_90_second_timeline(self):
        segments = [segment(1, 3, "LONG"), segment(3, 10, "SHORT"), segment(12, 90, "LONG", "LONG")]
        durations = {"LONG": 60, "SHORT": 1}
        with patch("builtins.print") as log:
            result = builder.build_timeline(segments, durations.__getitem__)
        self.assertEqual(result[0]["speed"], 30)
        self.assertEqual(result[1]["idle_duration"], 6)
        cursor = 0
        for original, entry in zip(segments, result):
            self.assertEqual(entry["stt_start"], original["start"])
            self.assertEqual(entry["stt_end"], original["end"])
            self.assertEqual(entry["items"], original["display_sequence"])
            cursor += entry["stt_start"] - cursor
            cursor += sum(durations[item["code"]] for item in entry["items"]) / entry["speed"]
            cursor += entry["idle_duration"]
            self.assertAlmostEqual(cursor, entry["actual_end"])
        self.assertEqual(cursor, 90)
        messages = "\n".join(c.args[0] for c in log.call_args_list)
        for field in ("segment=1", "stt_start=", "stt_end=", "target_duration=", "total_sign_duration=",
                      "required_speed=", "applied_speed=", "idle_duration=", "actual_end=",
                      "final_timeline_end=90.000s last_subtitle_end=90.000s"):
            self.assertIn(field, messages)

    def test_caption_only_empty_and_gloss_input(self):
        caption = {"type": "caption", "text": "caption"}
        probe = Mock(side_effect=AssertionError("Caption must not be probed"))
        with patch("builtins.print"), patch.object(builder, "build_display_sequence", return_value=[caption]) as display:
            result = builder.build_timeline([{"start": 2, "end": 4, "gloss_sequence": ["word"]}], probe)
            display.assert_called_once_with(["word"])
            self.assertEqual(result[0]["idle_duration"], 2)
            self.assertEqual(builder.build_timeline([], probe), [])

    def test_invalid_intervals_fail_before_division_or_rendering(self):
        for end in (0, -1, float("nan"), float("inf")):
            with self.subTest(end=end), self.assertRaisesRegex(ValueError, "finite and positive"):
                builder.build_timeline([segment(0, end, "A")], lambda _: 1)


if __name__ == "__main__":
    unittest.main()
