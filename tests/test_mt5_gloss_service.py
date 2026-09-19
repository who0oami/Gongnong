import sys
import unittest
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from services import llm_gloss_service
from ai.train_mt5_low_memory import gloss_f1, parse_glosses


class Mt5GlossServiceContractTests(unittest.TestCase):
    def test_gloss_serialization_and_f1(self):
        self.assertEqual(parse_glosses("오늘1 <g> 비내리다1#"), ["오늘1", "비내리다1#"])
        self.assertEqual(gloss_f1(["오늘1", "비내리다1#"], ["오늘1", "비내리다1#"]), 1.0)
        self.assertEqual(gloss_f1(["<extra_id_0>"], ["오늘1"]), 0.0)

    def test_preserves_gloss_list_contract(self):
        with patch.object(llm_gloss_service, "_convert_to_gloss", return_value=["오늘", "비", "오다"]):
            self.assertEqual(
                llm_gloss_service.convert_to_gloss("오늘 비가 옵니다."),
                ["오늘", "비", "오다"],
            )

    def test_local_model_error_becomes_backend_error(self):
        with patch.object(
            llm_gloss_service,
            "_convert_to_gloss",
            side_effect=llm_gloss_service.GlossModelError("가중치 없음"),
        ):
            with self.assertRaisesRegex(llm_gloss_service.GlossConversionError, "가중치 없음"):
                llm_gloss_service.convert_to_gloss("테스트")
