"""KSL Gloss 변환의 공통 진입점.

기존 Backend가 import하는 `convert_to_gloss()` 시그니처를 유지하면서
실제 구현체만 환경변수로 교체한다.

기본값은 local(Ollama)이다. 기존 Gemini 구현도 rollback/비교 테스트용으로
남겨 두되, 프론트/DB/Job Pipeline의 계약은 변경하지 않는다.
"""

import json
import os

from dotenv import load_dotenv

from services.local_llm_gloss_service import (
    LocalGlossConversionError,
    LocalGlossValidationError,
    convert_to_gloss_local,
)

load_dotenv()

_PROVIDER = os.environ.get("KSL_GLOSS_PROVIDER", "local").strip().lower()
_GEMINI_MODEL_NAME = os.environ.get("GEMINI_GLOSS_MODEL", "gemini-flash-lite-latest")


class GlossConversionError(Exception):
    """Gloss 변환 provider 호출 또는 응답 처리 실패."""


class GlossValidationError(GlossConversionError):
    """Generated gloss failed validation, distinct from provider outages."""


def _convert_to_gloss_gemini(korean_text: str) -> list[str]:
    """기존 Gemini 경로.

    기본 실행 경로는 아니며, local 구현 비교/긴급 rollback을 위해 보존한다.
    google-genai import도 여기서 지연시켜 local 모드가 Gemini 초기화에 의존하지 않게 한다.
    """
    try:
        from google import genai
        from google.genai import types
    except ImportError as exc:
        raise GlossConversionError(
            "Gemini provider를 사용하려면 google-genai가 필요합니다."
        ) from exc

    prompt = (
        "Convert the following Korean sentence into a compact KSL gloss sequence. "
        "Return exactly one JSON array of strings. Do not output WORD/SEN IDs, "
        "explanations, Markdown, or extra fields. Preserve negation, questions, "
        "requests, time, quantity, and subject/object relations when meaningful. "
        "Do not invent information. Prefer short dictionary-like Korean gloss labels.\n"
        f"sentence: {korean_text}"
    )

    try:
        client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
        response = client.models.generate_content(
            model=_GEMINI_MODEL_NAME,
            contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json"),
        )
    except Exception as exc:
        raise GlossConversionError(f"Gemini API 호출 실패: {exc}") from exc

    raw_text = response.text
    if not isinstance(raw_text, str) or not raw_text.strip():
        raise GlossConversionError("Gemini 응답 본문이 비어 있습니다.")

    try:
        gloss_list = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise GlossConversionError(f"Gemini 응답 JSON 파싱 실패: {exc}") from exc

    if not isinstance(gloss_list, list) or not all(
        isinstance(item, str) for item in gloss_list
    ):
        raise GlossConversionError("Gemini 응답이 문자열 배열이 아닙니다.")

    return [item.strip() for item in gloss_list if item.strip()]


def convert_to_gloss(korean_text: str) -> list[str]:
    """한국어 문자열을 기존 Pipeline 계약인 Gloss 문자열 배열로 변환한다."""
    if not isinstance(korean_text, str):
        raise GlossConversionError("korean_text는 문자열이어야 합니다.")

    if not korean_text.strip():
        return []

    if _PROVIDER == "local":
        try:
            return convert_to_gloss_local(korean_text)
        except LocalGlossValidationError as exc:
            raise GlossValidationError(str(exc)) from exc
        except LocalGlossConversionError as exc:
            raise GlossConversionError(f"Local LLM Gloss 변환 실패: {exc}") from exc

    if _PROVIDER == "gemini":
        return _convert_to_gloss_gemini(korean_text)

    raise GlossConversionError(
        f"지원하지 않는 KSL_GLOSS_PROVIDER={_PROVIDER!r}. local 또는 gemini를 사용하세요."
    )
