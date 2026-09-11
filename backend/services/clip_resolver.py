# TODO: 실제 Avatar 데이터 정리 완료 후, 이 함수 내부만 교체 예정
# word3000_mapping.csv의 morpheme_path, sen_sentence_mapping.csv의
# source_file 등을 참고해서 실제 경로 규칙 확정 필요
# (현재는 더미 경로 문자열만 생성)
def resolve_clip_path(code: str) -> str | None:
    return f"data/videos/{code}.mp4"


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
