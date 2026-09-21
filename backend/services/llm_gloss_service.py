# TODO: 프롬프트 내용/규칙은 다른 팀원이 설계 중.
# 여기 있는 프롬프트 문자열은 임시 더미이며,
# 확정되면 이 부분만 교체 예정. 함수 시그니처(입출력)는 변경 없음.

import json
import os

from dotenv import load_dotenv
from google import genai
from google.genai import types

from services.ksl_converter import KSLConversionError

load_dotenv()

_MODEL_NAME = "gemini-flash-lite-latest"


class GlossConversionError(Exception):
    """Gemini API 호출 또는 응답 처리 과정에서 변환에 실패했을 때 발생하는 예외.

    - API 호출 자체가 실패한 경우 (네트워크 오류, 인증 오류, API 키 없음 등)
    - 응답은 받았지만 JSON 형식이 아니거나 파싱에 실패한 경우
    둘 다 이 예외로 표현하되, 메시지로 원인을 구분한다.
    """


def convert_to_gloss(korean_text: str) -> list[str]:
    """한국어 문장을 Gemini API를 통해 KSL Gloss 배열로 변환한다.

    Args:
        korean_text: 변환할 한국어 문장.

    Returns:
        Gloss 문자열 리스트. 변환할 Gloss가 없는 정상 응답의 경우 빈 리스트를 반환한다.

    Raises:
        GlossConversionError: Gemini API 호출 자체가 실패했거나,
            응답을 JSON 형식의 문자열 배열로 파싱하지 못한 경우.
    """
    # TODO: 프롬프트는 더미. 팀원이 규칙 확정하면 교체 예정.
    prompt = (
        "다음 한국어 문장을 한국수어(KSL) Gloss 배열로 변환해서 "
        "JSON 배열 형식으로만 답하세요. 다른 설명은 붙이지 마세요. "
        f"문장: {korean_text}"
    )

    try:
        client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
        response = client.models.generate_content(
            model=_MODEL_NAME,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
            ),
        )
    except Exception as e:
        # 네트워크 오류, 인증 오류, API 키 없음, 잘못된 모델 이름 등
        # API 호출 자체의 실패는 모두 여기서 GlossConversionError로 변환한다.
        raise GlossConversionError(f"Gemini API 호출 실패: {e}") from e

    raw_text = response.text
    if raw_text is None:
        raise GlossConversionError("Gemini API 호출 실패: 응답 본문이 비어 있음")

    try:
        gloss_list = json.loads(raw_text)
    except json.JSONDecodeError as e:
        raise GlossConversionError(f"응답 파싱 실패: JSON이 아닌 응답입니다 ({e})") from e

    if not isinstance(gloss_list, list) or not all(
        isinstance(item, str) for item in gloss_list
    ):
        raise GlossConversionError(
            f"응답 파싱 실패: 문자열 배열이 아닙니다 (raw={raw_text!r})"
        )

    # 정상 응답이지만 변환할 Gloss가 없는 경우 -> 빈 리스트를 그대로 반환 (실패 아님)
    return gloss_list


class GeminiKSLConverter:
    """기존 Gemini 변환 함수를 KSLConverter 공통 계약에 연결한다."""

    def convert(self, korean_text: str) -> list[str]:
        """Gloss 리스트를 반환하고 변환 실패를 공통 예외로 전달한다."""
        try:
            return convert_to_gloss(korean_text)
        except GlossConversionError as exc:
            raise KSLConversionError(str(exc)) from exc
