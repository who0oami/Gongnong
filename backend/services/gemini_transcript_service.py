"""Fallback transcription for cloud hosts blocked by YouTube transcript endpoints."""

import json
import math
import os

from google.genai import types

from services.gemini_client import generate_content


_DEFAULT_MODEL = "gemini-flash-lite-latest"

_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "segments": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "start": {"type": "number"},
                    "end": {"type": "number"},
                    "text": {"type": "string"},
                },
                "required": ["start", "end", "text"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["segments"],
    "additionalProperties": False,
}

_PROMPT = """이 공개 YouTube 영상의 한국어 음성을 빠짐없이 전사하세요.
각 구간은 start, end를 영상 시작 기준 초 단위 숫자로, text를 한국어 문자열로 반환하세요.
구간은 가능한 한 완결된 짧은 문장으로 나누되 원래 순서와 의미를 유지하세요.
요약, 번역, 설명, 화면에만 보이는 문구, 음악 표시는 추가하지 마세요.
말이 없는 구간은 제외하고 JSON 스키마만 반환하세요."""


def transcribe_youtube_video(url: str) -> tuple[str, list[dict]]:
    """Transcribe a public YouTube URL through Gemini with timestamped segments."""
    model = os.getenv("GEMINI_TRANSCRIPT_MODEL", _DEFAULT_MODEL).strip() or _DEFAULT_MODEL
    contents = types.Content(parts=[
        types.Part(file_data=types.FileData(file_uri=url)),
        types.Part(text=_PROMPT),
    ])
    response = generate_content(
        model=model,
        contents=contents,
        config=types.GenerateContentConfig(
            temperature=0,
            response_mime_type="application/json",
            response_json_schema=_RESPONSE_SCHEMA,
        ),
    )

    raw_text = response.text
    if not isinstance(raw_text, str) or not raw_text.strip():
        raise ValueError("Gemini 영상 자막 응답이 비어 있습니다.")

    try:
        payload = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise ValueError("Gemini 영상 자막 응답을 해석하지 못했습니다.") from exc

    raw_segments = payload.get("segments") if isinstance(payload, dict) else None
    if not isinstance(raw_segments, list):
        raise ValueError("Gemini 영상 자막 응답에 segments가 없습니다.")

    segments: list[dict] = []
    for item in raw_segments:
        if not isinstance(item, dict):
            continue
        try:
            start = float(item.get("start"))
            end = float(item.get("end"))
        except (TypeError, ValueError):
            continue
        text = item.get("text")
        if (
            not math.isfinite(start)
            or not math.isfinite(end)
            or start < 0
            or end <= start
            or not isinstance(text, str)
            or not text.strip()
        ):
            continue
        segments.append({"start": start, "end": end, "text": text.strip()})

    segments.sort(key=lambda segment: (segment["start"], segment["end"]))
    if not segments:
        raise ValueError("Gemini가 유효한 영상 자막 구간을 생성하지 못했습니다.")

    return " ".join(segment["text"] for segment in segments), segments
