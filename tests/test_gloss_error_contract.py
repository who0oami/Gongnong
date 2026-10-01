import importlib.util
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from services.local_llm_gloss_service import LocalGlossConversionError, LocalGlossValidationError


class GlossErrorContractTest(unittest.TestCase):
    def setUp(self):
        # dotenv only loads deployment configuration; this test exercises the
        # actual provider facade without requiring API/DB dependencies.
        spec = importlib.util.spec_from_file_location("facade_under_test", Path(__file__).resolve().parents[1] / "backend/services/llm_gloss_service.py")
        self.facade = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {"dotenv": SimpleNamespace(load_dotenv=lambda: None)}):
            spec.loader.exec_module(self.facade)
        self.facade._PROVIDER = "local"

    def test_validation_failure_is_distinguishable_for_caption_recovery(self):
        with patch.object(self.facade,"convert_to_gloss_local",side_effect=LocalGlossValidationError("invalid content")):
            with self.assertRaises(self.facade.GlossValidationError):
                self.facade.convert_to_gloss("원문")

    def test_provider_outage_is_not_reclassified_as_caption_recovery(self):
        with patch.object(self.facade,"convert_to_gloss_local",side_effect=LocalGlossConversionError("offline")):
            with self.assertRaises(self.facade.GlossConversionError) as caught:
                self.facade.convert_to_gloss("원문")
        self.assertNotIsInstance(caught.exception,self.facade.GlossValidationError)
