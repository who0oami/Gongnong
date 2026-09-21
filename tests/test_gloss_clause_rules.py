import unittest
from unittest.mock import patch
from services.gloss_clause_rules import source_grounded_glosses
from services.local_llm_gloss_service import convert_to_gloss_local
from services.gloss_output_validation import validation_issues
from services.gloss_matcher import build_display_sequence


class ClauseRulesTest(unittest.TestCase):
    @patch("services.local_llm_gloss_service.request.urlopen")
    def test_prohibition_is_tied_to_its_action_without_llm(self, call):
        self.assertEqual(convert_to_gloss_local("문을 열지 말고 창문을 닫으세요."),
                         ["문을", "열다 금지", "창문을", "닫으세요"])
        call.assert_not_called()

    def test_unnecessary_keeps_verb_form_and_meaning(self):
        self.assertEqual(convert_to_gloss_local("학교에 갈 필요가 없어요."), ["학교에", "갈 필요 없다"])
        self.assertEqual(convert_to_gloss_local("상자를 지키고 있지만 겁먹을 필요는 없어요."),
                         ["상자를", "지키고", "있지만", "겁먹을 필요 없다"])

    def test_unseen_nouns_quantities_directions_and_multiple_prohibitions(self):
        for text, expected in [
            ("민수는 초록상자 3개를 열지 마세요.", ["민수는", "초록상자", "3개를", "열다 금지"]),
            ("밖으로 나가지 말고 안에서 기다리세요.", ["밖으로", "나가다 금지", "안에서", "기다리세요"]),
            ("책을 버리지 말고 접지도 마세요.", None),
            ("문을 열지 말고 창문을 닫지 마세요.", ["문을", "열다 금지", "창문을", "닫다 금지"]),
        ]:
            with self.subTest(text=text):
                result = source_grounded_glosses(text)
                self.assertEqual(result, expected)
                if result is not None: self.assertEqual(validation_issues(text, result), [])

    def test_unhandled_grammar_falls_back_to_existing_path(self):
        for text in ["오늘 비가 와요.", "학교에 갈 필요가 있나요?", "문을 열지 말라고 했어요.",
                     "학교에 갈 필요가 없었어요.", '"문을 열지 마세요"라고 했어요.',
                     "문을 열지 말고", "문을 열지 말고 기다리면 돼요."]:
            with self.subTest(text=text): self.assertIsNone(source_grounded_glosses(text))

    def test_prohibition_is_not_split_into_affirmative_video_and_missing_marker(self):
        glosses = convert_to_gloss_local("음악은 듣지 말고 책을 읽으세요.")
        self.assertIn("듣다 금지", glosses)
        items = build_display_sequence(glosses)
        self.assertNotIn("WORD1143", [item.get("code") for item in items])
        self.assertIn({"type": "caption", "text": "듣다 금지"}, items)
