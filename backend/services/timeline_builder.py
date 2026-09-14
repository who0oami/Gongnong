from typing import Callable

from services.gloss_matcher import build_display_sequence

# total_sign_duration / target_duration 이 이 배율 이하면 배속으로 흡수한다.
SPEEDUP_THRESHOLD = 1.2


def _raw_stats(segment: dict, items: list[dict], get_duration: Callable[[str], float]) -> dict:
    """borrowing(다음 segment의 idle 빌려오기)을 고려하지 않은, segment 단독 계산 결과."""
    target_duration = segment["end"] - segment["start"]

    total_sign_duration = sum(
        get_duration(item["code"]) for item in items if item["type"] == "avatar"
    )

    if total_sign_duration <= target_duration:
        case = 1
    elif target_duration > 0 and total_sign_duration / target_duration <= SPEEDUP_THRESHOLD:
        case = 2
    else:
        case = 3

    return {
        "target_duration": target_duration,
        "total_sign_duration": total_sign_duration,
        "case": case,
        # case 1일 때만 의미 있음: segment 자체가 갖는 여유 시간
        "raw_idle": max(0.0, target_duration - total_sign_duration),
        # case 3일 때만 의미 있음: target을 벗어나는 초과분(속도 조절 없이 그대로 재생했을 때)
        "raw_overage": max(0.0, total_sign_duration - target_duration),
    }


def build_timeline(
    stt_segments: list[dict],
    get_duration: Callable[[str], float],
) -> list[dict]:
    """STT segment별로 build_display_sequence를 호출해 avatar/caption 시퀀스를 얻고,
    segment 재생 시간 정책(그대로 재생 / 배속 조절 / overflow)에 따라
    최종 타임라인을 계산한다."""

    n = len(stt_segments)
    items_per_segment = [
        seg["display_sequence"] if "display_sequence" in seg
        else build_display_sequence(seg["gloss_sequence"])
        for seg in stt_segments
    ]
    raw = [
        _raw_stats(stt_segments[i], items_per_segment[i], get_duration)
        for i in range(n)
    ]

    # case 3 segment가 바로 다음 segment(case 1)의 여유 시간을 빌려오는 만큼을
    # 미리 계산해서, 빌려준 쪽의 idle_duration에서 차감한다.
    consumed_idle = [0.0] * n
    borrowed = [0.0] * n
    overflow = [0.0] * n

    for i in range(n):
        if raw[i]["case"] != 3:
            continue

        overage = raw[i]["raw_overage"]
        next_idx = i + 1

        if next_idx < n and raw[next_idx]["case"] == 1:
            available = raw[next_idx]["raw_idle"] - consumed_idle[next_idx]
            lend = min(overage, max(0.0, available))
            consumed_idle[next_idx] += lend
        else:
            lend = 0.0

        borrowed[i] = lend
        overflow[i] = overage - lend

    timeline: list[dict] = []

    for i in range(n):
        stt_start = stt_segments[i]["start"]
        stt_end = stt_segments[i]["end"]
        case = raw[i]["case"]

        if case == 1:
            idle_duration = raw[i]["raw_idle"] - consumed_idle[i]
            entry = {
                "stt_start": stt_start,
                "stt_end": stt_end,
                "actual_end": stt_end,
                "speed": 1.0,
                "idle_duration": idle_duration,
                "overflow_seconds": 0.0,
                "items": items_per_segment[i],
            }
        elif case == 2:
            speed = raw[i]["total_sign_duration"] / raw[i]["target_duration"]
            entry = {
                "stt_start": stt_start,
                "stt_end": stt_end,
                "actual_end": stt_end,
                "speed": speed,
                "idle_duration": 0.0,
                "overflow_seconds": 0.0,
                "items": items_per_segment[i],
            }
        else:  # case 3
            entry = {
                "stt_start": stt_start,
                "stt_end": stt_end,
                "actual_end": stt_end + overflow[i],
                "speed": 1.0,
                "idle_duration": 0.0,
                "overflow_seconds": overflow[i],
                "items": items_per_segment[i],
            }

        timeline.append(entry)

    return timeline


if __name__ == "__main__":
    import json

    dummy_durations = {
        "SEN0253": 1.8,
        "WORD0009": 2.0,
        "WORD1140": 1.5,
    }

    def dummy_get_duration(code):
        return dummy_durations.get(code, 1.0)

    cases = {
        "case1_idle": [{"start": 0.0, "end": 6.0, "gloss_sequence": ["오늘", "슬프다"]}],
        "case2_over_1.2_should_become_case3": [
            {"start": 0.0, "end": 3.0, "gloss_sequence": ["오늘", "슬프다"]}
        ],
        "case2_speedup_within_1.2": [
            {"start": 0.0, "end": 3.3, "gloss_sequence": ["오늘", "슬프다"]}
        ],
        "case3_overflow": [{"start": 0.0, "end": 2.0, "gloss_sequence": ["오늘", "슬프다"]}],
    }

    for name, segs in cases.items():
        result = build_timeline(segs, dummy_get_duration)
        print(f"--- {name} ---")
        print(json.dumps(result, ensure_ascii=False, indent=2))
