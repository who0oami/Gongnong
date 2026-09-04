import re
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    TranscriptsDisabled,
    NoTranscriptFound,
    VideoUnavailable,
)


def extract_video_id(url: str) -> str | None:
    match = re.search(r"(?:v=|youtu\.be/)([a-zA-Z0-9_-]{11})", url)

    if match:
        return match.group(1)

    return None


def get_transcript_text(video_id: str) -> str:
    ytt_api = YouTubeTranscriptApi()

    try:
        transcript = ytt_api.fetch(video_id, languages=["ko"])
    except (TranscriptsDisabled, NoTranscriptFound):
        raise ValueError("이 영상에서 한국어 자막을 찾을 수 없습니다.")
    except VideoUnavailable:
        raise ValueError("존재하지 않거나 재생할 수 없는 영상입니다.")

    full_text = " ".join([entry.text for entry in transcript])
    return full_text