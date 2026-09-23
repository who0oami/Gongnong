from services.timing import ffmpeg_metrics, measure_ffmpeg, profile_merge
from services.clip_probe import is_clip_concat_ready, probe_clip

import itertools
import os
from decimal import Decimal, ROUND_CEILING, ROUND_HALF_UP
import subprocess
import tempfile
from pathlib import Path

RESULTS_DIR = Path(__file__).resolve().parent.parent / "static" / "results"
IDLE_IMAGE_PATH = Path(__file__).resolve().parent.parent / "static" / "images" / "idle_pose.png"

# 사전 표준화된 1080p 클립은 재인코딩하지 않고 concat copy로 연결한다.
# 개별 클립을 360p로 다시 인코딩하던 비용이 무료 Render의 주 병목이었다.
WIDTH, HEIGHT, FPS = 1920, 1080, 30

# job._get_clip_duration()과 병합 단계가 같은 missing-clip 길이를 사용한다.
MISSING_CLIP_FALLBACK_SECONDS = 1.0

_GAP_EPSILON = 1e-3


def _ffmpeg_timeout_seconds() -> int:
    try:
        return max(30, int(os.getenv("FFMPEG_TIMEOUT_SECONDS", "600")))
    except ValueError:
        return 600


def _run_ffmpeg(args: list[str]) -> None:
    try:
        result = subprocess.run(
            ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", *args],
            capture_output=True,
            text=True,
            timeout=_ffmpeg_timeout_seconds(),
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("ffmpeg 작업 시간이 제한을 초과했습니다.") from exc
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {' '.join(args)}\n{result.stderr}")


@measure_ffmpeg("black")
def _make_black(tmp: Path, duration: float, idx: int) -> Path:
    out = tmp / f"black_{idx}.mp4"
    _run_ffmpeg([
        "-f", "lavfi",
        "-i", f"color=c=black:s={WIDTH}x{HEIGHT}:r={FPS}:d={duration:.3f}",
        "-an", "-c:v", "libx264", "-preset", "ultrafast", "-threads", "1", "-pix_fmt", "yuv420p",
        str(out),
    ])
    return out


@measure_ffmpeg("idle_pose")
def _make_idle_pose(tmp: Path, duration: float, idx: int) -> Path:
    """기본 포즈 정지 이미지를 duration만큼 재생되는 영상으로 만든다.

    이미지가 없으면 검은 화면(_make_black)으로 자동 대체한다.
    """
    if not IDLE_IMAGE_PATH.is_file():
        return _make_black(tmp, duration, idx)

    out = tmp / f"idle_{idx}.mp4"
    vf = (
        f"scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=decrease,"
        f"pad={WIDTH}:{HEIGHT}:(ow-iw)/2:(oh-ih)/2,fps={FPS}"
    )
    _run_ffmpeg([
        "-loop", "1", "-i", str(IDLE_IMAGE_PATH), "-t", f"{duration:.3f}",
        "-vf", vf, "-an", "-c:v", "libx264", "-preset", "ultrafast", "-threads", "1", "-pix_fmt", "yuv420p",
        str(out),
    ])
    return out


@measure_ffmpeg("normalize")
def _normalize_clip(tmp: Path, src: Path, idx: int) -> Path:
    """실제 클립을 WIDTH x HEIGHT/FPS/무음으로 통일해서 concat이 가능하게 만든다."""
    out = tmp / f"norm_{idx}.mp4"
    vf = (
        f"scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=decrease,"
        f"pad={WIDTH}:{HEIGHT}:(ow-iw)/2:(oh-ih)/2,fps={FPS}"
    )
    _run_ffmpeg([
        "-i", str(src),
        "-vf", vf, "-an", "-c:v", "libx264", "-preset", "ultrafast", "-threads", "1", "-pix_fmt", "yuv420p",
        str(out),
    ])
    return out


@measure_ffmpeg("speed")
def _apply_speed(tmp: Path, src: Path, speed: float, idx: int) -> Path:
    out = tmp / f"speed_{idx}.mp4"
    _run_ffmpeg([
        "-i", str(src),
        "-vf", f"setpts=PTS/{speed}", "-an", "-c:v", "libx264", "-preset", "ultrafast", "-threads", "1", "-pix_fmt", "yuv420p",
        str(out),
    ])
    return out


@measure_ffmpeg("concat")
def _concat(tmp: Path, parts: list[Path], idx: int, out_path: Path | None = None) -> Path:
    out = out_path if out_path is not None else tmp / f"concat_{idx}.mp4"
    list_file = tmp / f"concat_{idx}.txt"
    lines = []
    for part in parts:
        escaped = str(part.resolve()).replace("\\", "/").replace("'", "'\\''")
        lines.append(f"file '{escaped}'")
    list_file.write_text("\n".join(lines), encoding="utf-8")

    _run_ffmpeg(["-f", "concat", "-safe", "0", "-i", str(list_file), "-c", "copy", str(out)])
    return out


def _idle_frame_count(duration: float) -> int:
    # Preserve the existing .3f duration and its encoder rounding. Image -t
    # rounds to the output time base; lavfi color ends on the next frame.
    frames = Decimal(f"{duration:.3f}") * FPS
    rounding = ROUND_HALF_UP if IDLE_IMAGE_PATH.is_file() else ROUND_CEILING
    return max(1, int(frames.to_integral_value(rounding=rounding)))


@measure_ffmpeg("idle_extension")
def _extend_last_frame(tmp: Path, src: Path, duration: float, idx: int) -> Path:
    out = tmp / f"extended_{idx}.mp4"
    _run_ffmpeg([
        "-i", str(src), "-vf", f"tpad=stop_mode=clone:stop={_idle_frame_count(duration)}",
        "-an", "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p", str(out),
    ])
    return out


@profile_merge
def merge_timeline_to_video(
    timeline: list[dict], output_filename: str, clip_paths: dict[str, Path | None],
    probe_cache: dict[Path, dict] | None = None,
) -> str:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    output_path = RESULTS_DIR / output_filename
    counter = itertools.count()
    if probe_cache is None:
        probe_cache = {}

    with tempfile.TemporaryDirectory(prefix="video_merger_") as tmp_str:
        tmp = Path(tmp_str)
        normalized_cache: dict[Path, Path] = {}
        idle_cache: dict[str, Path] = {}
        metrics = ffmpeg_metrics.get()

        def idle_pose(duration: float) -> Path:
            # Match the existing FFmpeg duration argument exactly, including
            # the black fallback; do not introduce any additional rounding.
            key = f"{duration:.3f}"
            if key in idle_cache:
                if metrics is not None:
                    metrics.counts["idle_cache_hits"] += 1
            else:
                if metrics is not None:
                    metrics.counts["idle_cache_misses"] += 1
                idle_cache[key] = _make_idle_pose(tmp, duration, next(counter))
            return idle_cache[key]

        master_parts: list[Path] = []
        prev_end = 0.0

        for segment in timeline:
            gap = segment["stt_start"] - prev_end
            if gap > _GAP_EPSILON:
                master_parts.append(idle_pose(gap))

            item_parts: list[Path] = []
            has_sign = False
            for item in segment["items"]:
                if item["type"] != "avatar":
                    continue

                src = clip_paths.get(item["code"])
                if src is None:
                    item_parts.append(idle_pose(MISSING_CLIP_FALLBACK_SECONDS))
                else:
                    has_sign = True
                    if src in normalized_cache:
                        if metrics is not None:
                            metrics.counts["normalize_cache_hits"] += 1
                    else:
                        if metrics is not None:
                            metrics.counts["normalize_cache_misses"] += 1
                        ready = is_clip_concat_ready(probe_clip(src, probe_cache))
                        if metrics is not None:
                            metrics.counts["normalize_skipped" if ready else "normalize_required"] += 1
                        normalized_cache[src] = src if ready else _normalize_clip(tmp, src, next(counter))
                    item_parts.append(normalized_cache[src])

            extend_idle = has_sign and segment["idle_duration"] > _GAP_EPSILON
            speed_changed = abs(segment["speed"] - 1.0) > 1e-6
            if extend_idle and not speed_changed:
                # New output only: never overwrite a normalized/cache entry.
                item_parts[-1] = _extend_last_frame(
                    tmp, item_parts[-1], segment["idle_duration"], next(counter),
                )

            seg_base = None
            if item_parts:
                seg_base = _concat(tmp, item_parts, next(counter)) if len(item_parts) > 1 else item_parts[0]
                if speed_changed:
                    seg_base = _apply_speed(tmp, seg_base, segment["speed"], next(counter))
                    if extend_idle:
                        seg_base = _extend_last_frame(tmp, seg_base, segment["idle_duration"], next(counter))

            if extend_idle and metrics is not None:
                metrics.counts["idle_extended_count"] += 1

            trailing = [p for p in (seg_base,) if p is not None]
            if segment["idle_duration"] > _GAP_EPSILON and not extend_idle:
                if metrics is not None:
                    metrics.counts["idle_fallback_count"] += 1
                trailing.append(idle_pose(segment["idle_duration"]))

            if trailing:
                seg_final = _concat(tmp, trailing, next(counter)) if len(trailing) > 1 else trailing[0]
                master_parts.append(seg_final)

            prev_end = segment["actual_end"]

        if not master_parts:
            master_parts.append(_make_black(tmp, MISSING_CLIP_FALLBACK_SECONDS, next(counter)))

        _concat(tmp, master_parts, next(counter), out_path=output_path)

    return f"/static/results/{output_filename}"


if __name__ == "__main__":
    from routers.job import _render_job_video

    print(_render_job_video("demo_result", [
        {"start": 0.5, "end": 6.0, "gloss_sequence": ["첫번째", "고민", "나"]},
        {"start": 7.0, "end": 9.0, "gloss_sequence": ["두번째"]},
    ]))
