import json
import unittest
from pathlib import Path
from unittest.mock import patch
from services.gloss_output_validation import validation_issues, normalize_observed_forms
from services.local_llm_gloss_service import convert_to_gloss_local, LocalGlossConversionError
from tests.test_local_llm_gloss_service import _FakeResponse


class GlossOutputValidationTest(unittest.TestCase):
    def test_known_direction_reversal_is_rejected(self):
        self.assertIn("direction_changed", validation_issues("이 나무 구멍 아래로 들어가면", ["이", "나무", "구멍", "위에", "들어가다"]))

    def test_numeric_quantity_loss_is_rejected(self):
        self.assertIn("quantity_changed", validation_issues("내일 사과 3개를 가져와요", ["내일", "사과", "가져오다"]))

    def test_unnecessary_is_not_meaningless(self):
        self.assertIn("modality_changed", validation_issues("겁먹을 필요 없어", ["겁먹다", "의미없다"]))

    def test_scoped_negation_is_not_certified_by_marker_presence(self):
        for words in (["문", "열다", "창문", "닫다"], ["문", "열다", "말다", "창문", "닫다", "말다"]):
            self.assertTrue(validation_issues("문을 열지 말고 창문을 닫으세요.", words))

    def test_supported_single_predicate_and_nouns(self):
        for source, words in [("오늘 비가 와요.", ["오늘", "비", "오다"]), ("나는 커피를 마시지 않아요.", ["나", "커피", "마시다", "않다"]), ("안경을 가져와요.", ["안경", "가져오다"]), ("내일 사과 3개를 가져와요.", ["내일", "사과", "3개", "가져오다"])]:
            with self.subTest(source=source): self.assertEqual(validation_issues(source, words), [])

    def test_valid_compound_sentences_are_not_blanket_rejected(self):
        self.assertEqual(validation_issues("문을 열지 말고 창문을 닫으세요.", ["문", "열다", "금지", "창문", "닫다"]), [])
        self.assertEqual(validation_issues("문을 열고 창문은 닫지 마세요.", ["문", "열다", "창문", "닫다", "금지"]), [])

    def test_dictionary_repairs_require_source_evidence(self):
        self.assertEqual(normalize_observed_forms("오늘 비가 와요.", ["비", "와다"]), ["비", "오다"])
        self.assertEqual(normalize_observed_forms("운동을 해요.", ["해다"]), ["하다"])
        self.assertEqual(normalize_observed_forms("가도 돼요.", ["돼다"]), ["되다"])
        self.assertEqual(normalize_observed_forms("와다 씨가 왔어요.", ["와다"]), ["와다"])
        self.assertEqual(normalize_observed_forms("이를 갈아요.", ["갈다"]), ["갈다"])
        self.assertEqual(normalize_observed_forms("학교에 가요.", ["와다"]), ["와다"])

    @patch("services.local_llm_gloss_service.request.urlopen")
    def test_actual_conversion_does_not_return_reversed_direction(self, urlopen):
        urlopen.return_value = _FakeResponse({"message": {"content": json.dumps(["상자", "위", "공", "놓다"])}})
        with self.assertRaisesRegex(LocalGlossConversionError, "direction_changed"):
            convert_to_gloss_local("상자 아래에 공을 놓으세요.")

    def test_empty_result_for_nonempty_input_is_rejected(self):
        self.assertIn("empty_output", validation_issues("부싯돌", []))


class RegenerationTest(unittest.TestCase):
    @patch("services.local_llm_gloss_service.request.urlopen")
    def test_failed_generation_is_retried_once_and_revalidated(self, urlopen):
        bad = ["상자", "위", "공", "놓다"]
        good = ["상자", "아래", "공", "놓다"]
        urlopen.side_effect = [_FakeResponse({"message":{"content":json.dumps(x)}}) for x in [bad, good]]
        self.assertEqual(convert_to_gloss_local("상자 아래에 공을 놓으세요."), good)
        self.assertEqual(urlopen.call_count, 2)

    @patch("services.local_llm_gloss_service.request.urlopen")
    def test_repeat_failure_is_bounded(self, urlopen):
        urlopen.return_value = _FakeResponse({"message":{"content":json.dumps(["위"])}})
        with self.assertRaisesRegex(LocalGlossConversionError, "재생성 후에도"):
            convert_to_gloss_local("아래로 가요.")
        self.assertEqual(urlopen.call_count, 2)

    @patch("services.local_llm_gloss_service.request.urlopen")
    def test_network_error_is_not_retried(self, urlopen):
        from urllib.error import URLError
        urlopen.side_effect = URLError("offline")
        with self.assertRaises(LocalGlossConversionError):
            convert_to_gloss_local("학교에 가요.")
        self.assertEqual(urlopen.call_count, 1)


class RetryBudgetTest(unittest.TestCase):
    @patch("services.local_llm_gloss_service.time.monotonic", side_effect=[0, 0, 100])
    @patch("services.local_llm_gloss_service.request.urlopen")
    def test_retry_uses_remaining_timeout(self, urlopen, clock):
        urlopen.side_effect = [_FakeResponse({"message":{"content":json.dumps(x)}})
                              for x in [["위"], ["아래", "가다"]]]
        self.assertEqual(convert_to_gloss_local("아래로 가요."), ["아래", "가다"])
        self.assertEqual([c.kwargs["timeout"] for c in urlopen.call_args_list], [120, 20])

    @patch("services.local_llm_gloss_service.time.monotonic", side_effect=[0, 0, 121])
    @patch("services.local_llm_gloss_service.request.urlopen")
    def test_expired_budget_prevents_second_request(self, urlopen, clock):
        urlopen.return_value = _FakeResponse({"message":{"content":json.dumps(["위"])}})
        with self.assertRaisesRegex(LocalGlossConversionError, "시간 예산"):
            convert_to_gloss_local("아래로 가요.")
        self.assertEqual(urlopen.call_count, 1)
