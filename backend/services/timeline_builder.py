import math
from typing import Callable
from services.gloss_matcher import build_display_sequence

SPEEDUP_THRESHOLD = 1.2


def build_timeline(stt_segments: list[dict], get_duration: Callable[[str], float]) -> list[dict]:
    """Schedule sequential clips; carry overflow forward instead of losing time.

    Captions overlay the segment and consume no additional clip time. A caption
    only segment retains its original reading duration even if earlier clips
    delayed it. actual_start/end are the physical output positions.
    """
    timeline = []
    cursor = 0.0
    previous_start = -1.0
    for segment in stt_segments:
        start, end = segment["start"], segment["end"]
        if not all(math.isfinite(x) for x in (start, end)) or start < 0 or end <= start or start < previous_start:
            raise ValueError("Segments require finite, ordered starts and positive durations")
        previous_start = start
        original = segment.get("display_sequence")
        if original is None:
            original = build_display_sequence(segment["gloss_sequence"])
        items = [dict(item) for item in original]
        total = 0.0
        for item in items:
            if item["type"] == "avatar":
                duration = get_duration(item["code"])
                if not math.isfinite(duration) or duration <= 0:
                    raise ValueError("Clip durations must be finite and positive")
                item["duration"] = duration
                total += duration
        actual_start = max(start, cursor)
        available = max(0.0, end - actual_start)
        speed = total / available if available > 0 and available < total <= available * SPEEDUP_THRESHOLD else 1.0
        content_duration = total / speed
        duration = max(available, content_duration) if total else end - start
        idle = max(0.0, duration - content_duration)
        cursor = actual_start + duration
        entry = {"stt_start": start, "stt_end": end, "actual_start": actual_start,
                 "actual_end": cursor, "speed": speed, "idle_duration": idle,
                 "overflow_seconds": max(0.0, cursor - end), "items": items}
        if "caption_text" in segment:
            entry["caption_text"] = segment["caption_text"]
        timeline.append(entry)
    return timeline
