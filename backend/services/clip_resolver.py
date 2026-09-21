from pathlib import Path

VIDEOS_DIR = Path(__file__).resolve().parent.parent / "static" / "videos"


def resolve_clip_path(code: str) -> str | None:
    if not (VIDEOS_DIR / f"{code}.mp4").is_file():
        return None
    return f"/static/videos/{code}.mp4"


def resolve_clips(display_sequence: list[dict]) -> list[dict]:
    resolved: list[dict] = []

    for item in display_sequence:
        clip_path = resolve_clip_path(item["code"]) if item["type"] == "avatar" else None
        resolved.append({**item, "clip_path": clip_path})

    return resolved


if __name__ == "__main__":
    import json

    from services.gloss_matcher import build_display_sequence

    sequence = build_display_sequence(["오늘", "슬프다", "미안", "기쁨"])
    result = resolve_clips(sequence)
    print(json.dumps(result, ensure_ascii=False, indent=2))
