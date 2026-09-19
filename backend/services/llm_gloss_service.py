"""Backend compatibility layer for the team's fine-tuned local mT5 model.

The existing job router imports ``convert_to_gloss`` and handles
``GlossConversionError``. Keeping that public interface avoids backend changes while
removing the Gemini dependency from the translation path.
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ai.mt5_gloss_service import GlossModelError, convert_to_gloss as _convert_to_gloss


class GlossConversionError(GlossModelError):
    """Raised when the local, fine-tuned model cannot perform a conversion."""


def convert_to_gloss(korean_text: str) -> list[str]:
    """Convert with the local mT5 model using the backend's existing contract."""
    try:
        return _convert_to_gloss(korean_text)
    except GlossModelError as error:
        raise GlossConversionError(str(error)) from error
