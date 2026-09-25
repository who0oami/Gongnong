from services.timing import measure_ffmpeg, profile_merge

import itertools
import subprocess
import tempfile
from pathlib import Path

RESULTS_DIR = Path(__file__).resolve().parent.parent / "static" / "results"
IDLE_IMAGE_PATH = Path(__file__).resolve().parent.parent / "static" / "images" / "idle_pose.png"

# Render 무료 티어(0.1 vCPU)에서 1080p 인코딩은 사실상 끝나지 않는 수준으로 느려서,
# 이 사양에서 합리적인 시간 내에 끝나도록 해상도를 낮춰뒀다. 더 강한 인스턴스로
# 옮기면 다시 올려도 된다.
WIDTH, HEIGHT, FPS = 640, 360, 30

# ponytail: build_timeline()의 items에는 code만 있고 개별 클립의 재생 시간이
# 없어서, 파일이 없는 avatar 항목을 얼마나 긴 검은 화면으로 대체해야 하는지
# 알 방법이 없다. 실제 duration 메타데이터를 items에 싣거나 get_duration을
# merge_timeline_to_video에도 전달하게 되면 이 고정값 대신 그 값을 쓰도록 교체.
MISSING_CLIP_FALLBACK_SECONDS = 1.0

_GAP_EPSILON = 1e-3


def _run_ffmpeg(args: list[str]) -> None:
    result = subprocess.run(
        ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", *args],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {' '.join(args)}\n{result.stderr}")


@measure_ffmpeg("black")
def _make_black(tmp: Path, duration: float, idx: int) -> Path:
    out = tmp / f"black_{idx}.mp4"
    _run_ffmpeg([
        "-f", "lavfi",
        "-i", f"color=c=black:s={WIDTH}x{HEIGHT}:r={FPS}:d={duration:.3f}",
        "-an", "-c:v", "libx264", "-pix_fmt", "yuv420p",
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
        "-vf", vf, "-an", "-c:v", "libx264", "-pix_fmt", "yuv420p",
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
        "-vf", vf, "-an", "-c:v", "libx264", "-pix_fmt", "yuv420p",
        str(out),
    ])
    return out


@measure_ffmpeg("speed")
def _apply_speed(tmp: Path, src: Path, speed: float, idx: int) -> Path:
    out = tmp / f"speed_{idx}.mp4"
    _run_ffmpeg([
        "-i", str(src),
        "-vf", f"setpts=PTS/{speed}", "-an", "-c:v", "libx264", "-pix_fmt", "yuv420p",
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


@profile_merge
def merge_timeline_to_video(
    timeline: list[dict], output_filename: str, clip_paths: dict[str, Path | None],
) -> str:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    output_path = RESULTS_DIR / output_filename
    counter = itertools.count()

    with tempfile.TemporaryDirectory(prefix="video_merger_") as tmp_str:
        tmp = Path(tmp_str)
        master_parts: list[Path] = []
        prev_end = 0.0

        for segment in timeline:
            gap = segment["stt_start"] - prev_end
            if gap > _GAP_EPSILON:
                master_parts.append(_make_idle_pose(tmp, gap, next(counter)))

            item_parts: list[Path] = []
            for item in segment["items"]:
                if item["type"] != "avatar":
                    continue

                src = clip_paths.get(item["code"])
                if src is None:
                    item_parts.append(_make_idle_pose(tmp, MISSING_CLIP_FALLBACK_SECONDS, next(counter)))
                else:
                    item_parts.append(_normalize_clip(tmp, src, next(counter)))

            seg_base = None
            if item_parts:
                seg_base = _concat(tmp, item_parts, next(counter)) if len(item_parts) > 1 else item_parts[0]
                if abs(segment["speed"] - 1.0) > 1e-6:
                    seg_base = _apply_speed(tmp, seg_base, segment["speed"], next(counter))

            trailing = [p for p in (seg_base,) if p is not None]
            if segment["idle_duration"] > _GAP_EPSILON:
                trailing.append(_make_idle_pose(tmp, segment["idle_duration"], next(counter)))

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
