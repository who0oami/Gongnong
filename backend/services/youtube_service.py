import json
import logging
import os
import re

import requests
from dotenv import load_dotenv
from googleapiclient.discovery import build
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    IpBlocked,
    NoTranscriptFound,
    RequestBlocked,
    TranscriptsDisabled,
    VideoUnavailable,
    YouTubeTranscriptApiException,
)

load_dotenv()

SPELLER_URL = "https://nara-speller.co.kr/old_speller/results"

logger = logging.getLogger(__name__)


class TranscriptAccessBlocked(ValueError):
    """YouTube refused transcript access from the server's network."""


def correct_spelling(text: str) -> str:
    if not text.strip():
        return text

    try:
        response = requests.post(
            SPELLER_URL,
            data={"text1": text, "chkKey": ""},
            timeout=5,
        )
        response.raise_for_status()
    except requests.RequestException:
        return text

    match = re.search(
        r"data\s*=\s*(\[.*?\]);",
        response.text,
        re.DOTALL,
    )

    if not match:
        return text

    try:
        result_list = json.loads(match.group(1))
    except (json.JSONDecodeError, ValueError):
        return text

    corrected = text

    for result in result_list:
        error_list = result.get("errInfo", [])

        for error in reversed(error_list):
            orgstr = error.get("orgStr", "")
            candword = error.get("candWord", "")

            if not orgstr or not candword:
                continue

            first_candidate = candword.split("|")[0]
            corrected = corrected.replace(
                orgstr,
                first_candidate,
                1,
            )

    return corrected


def clean_text(text: str) -> str:
    text = re.sub(r"\[.*?\]", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def extract_video_id(url: str) -> str | None:
    patterns = [
        r"(?:v=)([a-zA-Z0-9_-]{11})",
        r"(?:youtu\.be/)([a-zA-Z0-9_-]{11})",
        r"(?:youtube\.com/shorts/)([a-zA-Z0-9_-]{11})",
    ]

    for pattern in patterns:
        match = re.search(pattern, url)

        if match:
            return match.group(1)

    return None


def _parse_youtube_duration(value: str | None) -> float | None:
    """Convert an ISO-8601 YouTube duration (for example PT3M2S) to seconds."""
    if not value:
        return None
    match = re.fullmatch(
        r"P(?:(?P<days>\d+)D)?T(?:(?P<hours>\d+)H)?(?:(?P<minutes>\d+)M)?(?:(?P<seconds>\d+(?:\.\d+)?)S)?",
        value,
    )
    if match is None:
        return None
    parts = {name: float(number or 0) for name, number in match.groupdict().items()}
    duration = (
        parts["days"] * 86400
        + parts["hours"] * 3600
        + parts["minutes"] * 60
        + parts["seconds"]
    )
    return duration if duration > 0 else None


def get_video_metadata(url: str) -> dict[str, str | float | None]:
    """YouTube Data API를 사용해 영상 제목과 설명을 조회한다."""

    api_key = os.getenv("YOUTUBE_API_KEY")

    if not api_key:
        logger.warning("YOUTUBE_API_KEY가 설정되지 않았습니다.")
        return {
            "title": "",
            "description": "",
            "duration_sec": None,
        }

    video_id = extract_video_id(url)

    if not video_id:
        logger.warning(
            "YouTube video ID 추출 실패: %s",
            url,
        )
        return {
            "title": "",
            "description": "",
            "duration_sec": None,
        }

    try:
        youtube = build(
            "youtube",
            "v3",
            developerKey=api_key,
        )

        response = youtube.videos().list(
            part="snippet,contentDetails",
            id=video_id,
        ).execute()

        items = response.get("items", [])

        if not items:
            logger.warning(
                "YouTube 영상을 찾을 수 없습니다: %s",
                video_id,
            )
            return {
                "title": "",
                "description": "",
                "duration_sec": None,
            }

        snippet = items[0].get("snippet", {})
        content_details = items[0].get("contentDetails", {})

        return {
            "title": snippet.get("title") or "",
            "description": snippet.get("description") or "",
            "duration_sec": _parse_youtube_duration(content_details.get("duration")),
        }

    except Exception as e:
        logger.warning(
            "YouTube API 메타데이터 조회 실패: %s",
            e,
        )

        return {
            "title": "",
            "description": "",
            "duration_sec": None,
        }


def group_into_sentences(raw_entries: list) -> list[dict]:
    sentence_endings = (".", "?", "!")

    ending_words = (
        "요",
        "다",
        "죠",
        "네요",
        "가요",
        "까요",
        "습니다",
        "니다",
    )

    MAX_SEGMENT_DURATION = 6.0
    MAX_FRAGMENTS = 4

    segments = []
    buffer_texts = []
    buffer_start = None
    buffer_end = None

    for entry in raw_entries:
        text = clean_text(entry.text)

        if not text:
            continue

        if buffer_start is None:
            buffer_start = entry.start

        buffer_texts.append(text)
        buffer_end = entry.start + entry.duration

        is_sentence_end = (
            text.endswith(sentence_endings)
            or text.rstrip(".!?").endswith(ending_words)
        )

        duration_so_far = buffer_end - buffer_start

        is_forced_break = (
            duration_so_far >= MAX_SEGMENT_DURATION
            or len(buffer_texts) >= MAX_FRAGMENTS
        )

        if is_sentence_end or is_forced_break:
            joined = " ".join(buffer_texts)

            segments.append(
                {
                    "start": buffer_start,
                    "end": buffer_end,
                    "text": joined,
                }
            )

            buffer_texts = []
            buffer_start = None
            buffer_end = None

    if buffer_texts:
        joined = " ".join(buffer_texts)

        segments.append(
            {
                "start": buffer_start,
                "end": buffer_end,
                "text": joined,
            }
        )

    return segments


def get_transcript_data(video_id: str) -> tuple[str, list[dict]]:
    """YouTubeTranscriptApi를 사용해 한국어 자막을 가져온다."""

    ytt_api = YouTubeTranscriptApi()

    try:
        transcript = ytt_api.fetch(
            video_id,
            languages=["ko"],
        )

    except VideoUnavailable:
        raise ValueError(
            "존재하지 않거나 재생할 수 없는 영상입니다."
        )

    except (RequestBlocked, IpBlocked, TranscriptsDisabled, NoTranscriptFound) as exc:
        raise TranscriptAccessBlocked(
            "YouTube 자막을 직접 가져올 수 없어 영상 음성 전사로 대체합니다."
        ) from exc

    except YouTubeTranscriptApiException as exc:
        logger.warning("YouTube 자막 조회 실패 (%s)", type(exc).__name__)
        raise TranscriptAccessBlocked(
            "YouTube 자막 조회가 실패하여 영상 음성 전사로 대체합니다."
        ) from exc

    segments = group_into_sentences(transcript)

    full_text = " ".join(
        seg["text"] for seg in segments
    )

    return full_text, segments
