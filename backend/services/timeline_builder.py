import math
from typing import Callable

from services.gloss_matcher import build_display_sequence
from services.timing import emit_metrics


def normalize_overlapping_segments(segments: list[dict]) -> list[dict]:
    """Return rendering copies with overlap boundaries derived from original times."""
    timestamps = [(segment["start"], segment["end"]) for segment in segments]
    for i, (start, end) in enumerate(timestamps):
        if not (math.isfinite(start) and math.isfinite(end)) or end <= start:
            raise ValueError(f"Segment {i + 1}: STT segment duration must be finite and positive")

    # Compute every boundary before constructing any adjusted interval.
    boundaries = [
        (current_end + next_start) / 2 if next_start < current_end else None
        for (_, current_end), (next_start, _) in zip(timestamps, timestamps[1:])
    ]
    normalized = []
    for i, segment in enumerate(segments):
        start, end = timestamps[i]
        if i > 0 and boundaries[i - 1] is not None:
            start = boundaries[i - 1]
        if i < len(boundaries) and boundaries[i] is not None:
            end = boundaries[i]
        if not (math.isfinite(start) and math.isfinite(end)) or start >= end:
            raise ValueError(
                f"Segment {i + 1}: midpoint normalization produced an invalid interval "
                f"{start}-{end}; start must be less than end"
            )
        normalized.append({**segment, "start": start, "end": end})

    for i, (original, adjusted) in enumerate(zip(timestamps, normalized)):
        emit_metrics(
            "Timeline Normalize",
            f"segment={i + 1} original={original[0]:.6f}-{original[1]:.6f} "
            f"normalized={adjusted['start']:.6f}-{adjusted['end']:.6f}",
        )
    original_end = timestamps[-1][1] if timestamps else 0.0
    normalized_end = normalized[-1]["end"] if normalized else 0.0
    emit_metrics("Timeline Normalize", f"original_last_end={original_end:.6f} "
                 f"normalized_last_end={normalized_end:.6f}")
    return normalized


def _raw_stats(segment: dict, items: list[dict], get_duration: Callable[[str], float]) -> dict:
    """Calculate sign duration against the rendering subtitle interval."""
    target_duration = segment["end"] - segment["start"]
    if not math.isfinite(target_duration) or target_duration <= 0:
        raise ValueError("STT segment duration must be finite and positive")

    total_sign_duration = sum(
        get_duration(item["code"]) for item in items if item["type"] == "avatar"
    )
    if not math.isfinite(total_sign_duration) or total_sign_duration < 0:
        raise ValueError("Total sign duration must be finite and non-negative")
    required_speed = total_sign_duration / target_duration
    if not math.isfinite(required_speed):
        raise ValueError("Required sign speed must be finite")

    return {
        "target_duration": target_duration,
        "total_sign_duration": total_sign_duration,
        "required_speed": required_speed,
        "raw_idle": max(0.0, target_duration - total_sign_duration),
    }


def build_timeline(
    stt_segments: list[dict],
    get_duration: Callable[[str], float],
) -> list[dict]:
    """Group normalized rendering copies and fit signs exactly within each group."""
    normalized = normalize_overlapping_segments(stt_segments)
    prepared = []
    for segment in normalized:
        items = (segment["display_sequence"] if "display_sequence" in segment
                 else build_display_sequence(segment["gloss_sequence"]))
        # Probe each segment only once, even when a candidate group expands.
        stats = _raw_stats(segment, items, get_duration)
        prepared.append((items, stats["total_sign_duration"]))

    timeline: list[dict] = []
    first = 0
    while first < len(normalized):
        stop = min(first + 2, len(normalized))
        while True:
            start, end = normalized[first]["start"], normalized[stop - 1]["end"]
            total = sum(duration for _, duration in prepared[first:stop])
            target = end - start
            if not math.isfinite(target) or target <= 0:
                raise ValueError("Grouped segment duration must be finite and positive")
            required_speed = total / target
            if not math.isfinite(total) or not math.isfinite(required_speed):
                raise ValueError("Grouped sign duration and speed must be finite")
            # An empty segment already followed by another member is paired.
            # Pair a trailing empty segment forward when the size limit permits.
            trailing = normalized[stop - 1]
            empty_tail = (not trailing["gloss_sequence"] if "gloss_sequence" in trailing
                          else not prepared[stop - 1][0])
            if stop < len(normalized) and stop - first < 4 and (required_speed > 1.8 or empty_tail):
                stop += 1
                continue
            break

        items = [item for member_items, _ in prepared[first:stop] for item in member_items]
        stats = {"target_duration": target, "total_sign_duration": total,
                 "required_speed": required_speed, "raw_idle": max(0.0, target - total)}
        speed = max(1.0, stats["required_speed"])
        entry = {
            "stt_start": start,
            "stt_end": end,
            "actual_end": end,
            "speed": speed,
            "idle_duration": stats["raw_idle"],
            # Retain the existing result schema; overflow is no longer produced.
            "overflow_seconds": 0.0,
            "items": items,
        }
        timeline.append(entry)
        emit_metrics(
            "Timeline",
            f"segment={first + 1} stt_start={entry['stt_start']:.3f}s "
            f"stt_end={entry['stt_end']:.3f}s target_duration={stats['target_duration']:.3f}s "
            f"total_sign_duration={stats['total_sign_duration']:.3f}s "
            f"required_speed={stats['required_speed']:.6f} applied_speed={speed:.6f} "
            f"idle_duration={entry['idle_duration']:.3f}s actual_end={entry['actual_end']:.3f}s",
        )
        gloss_count = sum(len(segment.get("gloss_sequence", prepared[index][0]))
                          for index, segment in enumerate(normalized[first:stop], start=first))
        emit_metrics(
            "Render Group",
            f"segments={first + 1}-{stop} start={start:.6f} end={end:.6f} "
            f"segment_count={stop - first} gloss_count={gloss_count} "
            f"total_sign_duration={total:.6f} target_duration={target:.6f} "
            f"required_speed={required_speed:.6f} applied_speed={speed:.6f} "
            f"idle_duration={entry['idle_duration']:.6f}",
        )
        first = stop

    final_end = timeline[-1]["actual_end"] if timeline else 0.0
    subtitle_end = stt_segments[-1]["end"] if stt_segments else 0.0
    emit_metrics("Timeline", f"final_timeline_end={final_end:.3f}s last_subtitle_end={subtitle_end:.3f}s")
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
        "case2_speedup_over_1.2": [
            {"start": 0.0, "end": 3.0, "gloss_sequence": ["오늘", "슬프다"]}
        ],
        "case2_speedup_within_1.2": [
            {"start": 0.0, "end": 3.3, "gloss_sequence": ["오늘", "슬프다"]}
        ],
        "case2_speedup_without_limit": [{"start": 0.0, "end": 2.0, "gloss_sequence": ["오늘", "슬프다"]}],
    }

    for name, segs in cases.items():
        result = build_timeline(segs, dummy_get_duration)
        print(f"--- {name} ---")
        print(json.dumps(result, ensure_ascii=False, indent=2))
