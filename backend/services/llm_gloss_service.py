"""KSL Gloss conversion with Gemini, Ollama, or a local mT5 model."""
import json
import os

from dotenv import load_dotenv
from google.genai import types
from services.ksl_converter import KSLConversionError
from .gemini_client import generate_content, _env_int, GeminiConfigurationError

load_dotenv()
_MODEL_NAME = "gemini-flash-lite-latest"


class GlossConversionError(Exception):
    """Gemini request or response validation failed."""


def get_gloss_batch_size() -> int:
    return _env_int("GEMINI_GLOSS_BATCH_SIZE", 5, 1)


def _provider() -> str:
    return os.getenv("KSL_GLOSS_PROVIDER", "gemini").strip().lower()


def _convert_local(text: str) -> list[str]:
    try:
        from .local_llm_gloss_service import convert_to_gloss_local

        return convert_to_gloss_local(text)
    except Exception as exc:
        raise GlossConversionError(f"Local LLM Gloss 변환 실패 ({type(exc).__name__})") from exc


def _convert_mt5(text: str) -> list[str]:
    try:
        from ai.mt5_gloss_service import convert_to_gloss as convert_to_gloss_mt5

        return convert_to_gloss_mt5(text)
    except Exception as exc:
        raise GlossConversionError(f"mT5 Gloss 변환 실패 ({type(exc).__name__})") from exc


def convert_batch(texts: list[str]) -> list[list[str]]:
    """One request per batch; validate and restore input order by index."""
    if not texts:
        return []
    provider = _provider()
    if provider == "local":
        return [_convert_local(text) for text in texts]
    if provider == "mt5":
        return [_convert_mt5(text) for text in texts]
    if provider != "gemini":
        raise GlossConversionError(
            f"지원하지 않는 KSL_GLOSS_PROVIDER={provider!r}; gemini, local, mt5 중 하나를 사용하세요"
        )
    schema = {
        "type": "object", "required": ["segments"],
        "properties": {"segments": {
            "type": "array", "minItems": len(texts), "maxItems": len(texts),
            "items": {"type": "object", "required": ["index", "glosses"],
                      "properties": {"index": {"type": "integer"},
                                     "glosses": {"type": "array", "items": {"type": "string"}}}},
        }},
    }
    try:
        response = generate_content(
            model=_MODEL_NAME,
            contents=json.dumps({"segments": [
                {"index": i, "text": text} for i, text in enumerate(texts)
            ]}, ensure_ascii=False),
            config=types.GenerateContentConfig(
                system_instruction=(
                    "각 한국어 segment를 한국수어(KSL) Gloss 배열로 변환하세요. "
                    "주변 segment는 문맥 파악에만 사용하고 서로 합치거나 옮기지 마세요. "
                    "모든 입력 index를 정확히 한 번씩 포함하고 해당 glosses를 반환하세요. "
                    "변환할 Gloss가 없으면 빈 배열을 반환하세요."
                ),
                response_mime_type="application/json", response_json_schema=schema,
            ),
        )
    except Exception as exc:
        # SDK error bodies or URLs can contain secrets; never propagate them to logs/DB.
        code = getattr(exc, "code", None)
        reason = str(exc) if isinstance(exc, GeminiConfigurationError) else (str(code) if isinstance(code, int) else type(exc).__name__)
        raise GlossConversionError(f"Gemini API 호출 실패 ({reason})") from exc
    try:
        payload = json.loads(response.text)
    except (TypeError, ValueError) as exc:
        raise GlossConversionError("응답 파싱 실패: 유효한 JSON이 아닙니다") from exc
    entries = payload.get("segments") if isinstance(payload, dict) else None
    if not isinstance(entries, list) or len(entries) != len(texts):
        raise GlossConversionError("응답 파싱 실패: 입력과 출력 segment 수가 다릅니다")
    ordered = {}
    for entry in entries:
        if not isinstance(entry, dict):
            raise GlossConversionError("응답 파싱 실패: segment 객체가 아닙니다")
        index, glosses = entry.get("index"), entry.get("glosses")
        if type(index) is not int or not 0 <= index < len(texts) or index in ordered:
            raise GlossConversionError("응답 파싱 실패: 중복 또는 잘못된 index")
        if not isinstance(glosses, list) or not all(isinstance(g, str) for g in glosses):
            raise GlossConversionError("응답 파싱 실패: glosses는 문자열 배열이어야 합니다")
        ordered[index] = glosses
    return [ordered[i] for i in range(len(texts))]


def convert_to_gloss(korean_text: str) -> list[str]:
    return convert_batch([korean_text])[0]


class GeminiKSLConverter:
    def convert(self, korean_text: str) -> list[str]:
        return self.convert_batch([korean_text])[0]

    def convert_batch(self, texts: list[str]) -> list[list[str]]:
        try:
            return convert_batch(texts)
        except GlossConversionError as exc:
            raise KSLConversionError(str(exc)) from exc
