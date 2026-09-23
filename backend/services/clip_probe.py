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
                 "-show_packets", "-show_entries", "packet=stream_index,pts,dts,duration,flags",
                 "-of", "json", str(path)],
                capture_output=True, text=True, check=True,
                timeout=_ffprobe_timeout_seconds(),
            )
        cache[path] = json.loads(result.stdout)
    return cache[path]


def clip_concat_readiness_reason(metadata: dict) -> str | None:
    """Match the current libx264/MP4 output, including its two-frame DTS delay.

    Average FPS alone cannot establish CFR. Inspect packet timing in the same
    probe (no decoding) to reject VFR, edit-list offsets and duration padding.
    Different SPS/PPS bytes are allowed: concat's default MP4-to-Annex-B
    conversion supplies each clip's parameter sets at its initial keyframe.
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
        packets = metadata["packets"]
        if not packets or "K" not in packets[0]["flags"] or packets[0]["pts"] != 0:
            return "missing_initial_keyframe"
        if len(packets) != int(video["nb_frames"]):
            return "frame_count_mismatch"
        for i, packet in enumerate(packets):
            if (packet["stream_index"] != video["index"] or packet["duration"] != 512
                    or packet["dts"] != (i - 2) * 512):
                return "unexpected_packet_timing"
        if sorted(packet["pts"] for packet in packets) != list(range(0, len(packets) * 512, 512)):
            return "non_cfr_pts"
        # ffprobe prints duration rounded to microseconds.
        duration = Fraction(len(packets), 30)
        if not all(abs(Fraction(data["duration"]) - duration) <= Fraction(1, 1000000)
                   for data in (video, container)):
            return "duration_frame_count_mismatch"
        return None
    except (KeyError, TypeError, ValueError, ZeroDivisionError, OverflowError):
        return "missing_or_invalid_metadata"


def is_clip_concat_ready(metadata: dict) -> bool:
    return clip_concat_readiness_reason(metadata) is None
