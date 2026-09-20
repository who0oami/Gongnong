import json
import unittest
from unittest.mock import patch

from services.local_llm_gloss_service import (
    LocalGlossConversionError,
    _extract_gloss_list,
    convert_to_gloss_local,
)


class _FakeResponse:
    def __init__(self, payload):
        self._body = json.dumps(payload, ensure_ascii=False).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return self._body


class LocalGlossServiceTest(unittest.TestCase):
    def test_extracts_array_without_changing_order(self):
        payload = {"message": {"content": '["오늘", "학교", "가다"]'}}
        self.assertEqual(_extract_gloss_list(payload), ["오늘", "학교", "가다"])

    def test_accepts_single_glosses_wrapper_for_small_model_compatibility(self):
        payload = {"message": {"content": '{"glosses":["나","학교","가다"]}'}}
        self.assertEqual(_extract_gloss_list(payload), ["나", "학교", "가다"])

    def test_rejects_non_string_items(self):
        payload = {"message": {"content": '["오늘", 123]'}}
        with self.assertRaises(LocalGlossConversionError):
            _extract_gloss_list(payload)

    @patch("services.local_llm_gloss_service.request.urlopen")
    def test_local_request_contract(self, mock_urlopen):
        mock_urlopen.return_value = _FakeResponse(
            {"message": {"content": '["오늘","비","오다"]'}}
        )

        result = convert_to_gloss_local("오늘 비가 와요.")

        self.assertEqual(result, ["오늘", "비", "오다"])
        sent_request = mock_urlopen.call_args.args[0]
        body = json.loads(sent_request.data.decode("utf-8"))
        self.assertFalse(body["stream"])
        self.assertEqual(body["format"], "json")
        self.assertEqual(body["messages"][-1]["role"], "user")


if __name__ == "__main__":
    unittest.main()
