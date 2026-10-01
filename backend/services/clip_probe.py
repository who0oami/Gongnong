"""Job-local metadata shared by duration lookup and concat eligibility checks."""
import json
import os
import subprocess
from fractions import Fraction
from pathlib import Path

from services.timing import ffmpeg_metrics, measure, render_metrics


def _ffprobe_timeout_seconds() -> int:
    try:
        return max(10, int(os.getenv("FFPROBE_TIMEOUT_SECONDS", "30")))
    except ValueError:
        return 30


def probe_clip(path: Path, cache: dict[Path, dict]) -> dict:
    hit = path in cache
    for context in (render_metrics, ffmpeg_metrics):
        metrics = context.get()
        if metrics is not None:
            metrics.counts["probe_cache_hits" if hit else "probe_cache_misses"] += 1
    if not hit:
        with measure(render_metrics, "FFPROBE_DURATION"):
            result = subprocess.run(
                ["ffprobe", "-v", "error", "-show_streams", "-show_format",
                 "-of", "json", str(path)],
                capture_output=True, text=True, check=True,
                timeout=_ffprobe_timeout_seconds(),
            )
        cache[path] = json.loads(result.stdout)
    return cache[path]


def clip_concat_readiness_reason(metadata: dict) -> str | None:
    """Check the compact stream/container fields required by concat copy.

    Packet-by-packet metadata used hundreds of megabytes on the 512 MB Render
    instance when cached for a real job. The source clips are produced by the
    same preprocessing pipeline, so stream shape, frame count and duration are
    sufficient here and keep each cached probe result small.
    """
    try:
        streams = metadata["streams"]
        if len(streams) != 1:
            return "unexpected_stream_count"
        video = streams[0]
        expected = {
            "codec_type": "video", "codec_name": "h264", "codec_tag_string": "avc1",
            "width": 1920, "height": 1080, "pix_fmt": "yuv420p",
            "profile": "High", "level": 40, "field_order": "progressive",
            "sample_aspect_ratio": "1:1", "has_b_frames": 2,
            "is_avc": "true", "nal_length_size": "4",
        }
        for key, value in expected.items():
            if video.get(key) != value:
                return f"unexpected_{key}"
        if video.get("side_data_list") or video.get("tags", {}).get("rotate", "0") != "0":
            return "unsupported_side_data_or_rotation"
        if int(video["extradata_size"]) <= 0:
            return "missing_extradata"
        if any(Fraction(video[key]) != 30 for key in ("r_frame_rate", "avg_frame_rate")):
            return "unexpected_fps"
        if Fraction(video["time_base"]) != Fraction(1, 15360):
            return "unexpected_time_base"
        container = metadata["format"]
        if "mp4" not in container["format_name"].split(","):
            return "unexpected_container"
        if Fraction(video["start_time"]) != 0 or Fraction(container["start_time"]) != 0:
            return "unexpected_start_time"
        frame_count = int(video["nb_frames"])
        if frame_count <= 0:
            return "invalid_frame_count"
        # ffprobe prints duration rounded to microseconds.
        duration = Fraction(frame_count, 30)
        if not all(abs(Fraction(data["duration"]) - duration) <= Fraction(1, 1000000)
                   for data in (video, container)):
            return "duration_frame_count_mismatch"
        return None
    except (KeyError, TypeError, ValueError, ZeroDivisionError, OverflowError):
        return "missing_or_invalid_metadata"


def is_clip_concat_ready(metadata: dict) -> bool:
    return clip_concat_readiness_reason(metadata) is None
