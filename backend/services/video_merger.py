import itertools
import subprocess
import tempfile
from pathlib import Path

from services.clip_resolver import VIDEOS_DIR, resolve_clip_path

RESULTS_DIR = Path(__file__).resolve().parent.parent / "static" / "results"
IDLE_IMAGE_PATH = Path(__file__).resolve().parent.parent / "static" / "images" / "idle_pose.png"

WIDTH, HEIGHT, FPS = 1920, 1080, 30

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


def _make_black(tmp: Path, duration: float, idx: int) -> Path:
    out = tmp / f"black_{idx}.mp4"
    _run_ffmpeg([
        "-f", "lavfi",
        "-i", f"color=c=black:s={WIDTH}x{HEIGHT}:r={FPS}:d={duration:.3f}",
        "-an", "-c:v", "libx264", "-pix_fmt", "yuv420p",
        str(out),
    ])
    return out


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


def _normalize_clip(tmp: Path, src: Path, idx: int) -> Path:
    """실제 클립을 1920x1080/30fps/무음으로 통일해서 concat이 가능하게 만든다."""
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


def _apply_speed(tmp: Path, src: Path, speed: float, idx: int) -> Path:
    out = tmp / f"speed_{idx}.mp4"
    _run_ffmpeg([
        "-i", str(src),
        "-vf", f"setpts=PTS/{speed}", "-an", "-c:v", "libx264", "-pix_fmt", "yuv420p",
        str(out),
    ])
    return out


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


def merge_timeline_to_video(timeline: list[dict], output_filename: str) -> str:
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

                clip_url = resolve_clip_path(item["code"])
                if clip_url is None:
                    item_parts.append(_make_idle_pose(tmp, MISSING_CLIP_FALLBACK_SECONDS, next(counter)))
                else:
                    src = VIDEOS_DIR / f"{item['code']}.mp4"
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
    import json
    import subprocess as sp

    from services.timeline_builder import build_timeline

    def get_duration(code: str) -> float:
        clip_url = resolve_clip_path(code)
        if clip_url is None:
            return MISSING_CLIP_FALLBACK_SECONDS
        probe = sp.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(VIDEOS_DIR / f"{code}.mp4")],
            capture_output=True, text=True, check=True,
        )
        return float(probe.stdout.strip())

    # "첫번째"(WORD0058)/"나"(WORD1157)는 static/videos/에 실제 파일이 있고,
    # "고민"(WORD0001)은 매칭은 되지만 파일이 없는 케이스(검은 화면 대체 확인용).
    stt_segments = [
        {"start": 0.5, "end": 6.0, "gloss_sequence": ["첫번째", "고민", "나"]},
        {"start": 7.0, "end": 9.0, "gloss_sequence": ["두번째"]},
    ]

    timeline = build_timeline(stt_segments, get_duration)
    print(json.dumps(timeline, ensure_ascii=False, indent=2))

    url = merge_timeline_to_video(timeline, "demo_result.mp4")
    print("output url:", url)

    output_path = RESULTS_DIR / "demo_result.mp4"
    print("exists:", output_path.is_file())

    probe = sp.run(
        ["ffprobe", "-v", "error", "-show_entries",
         "format=duration:stream=width,height,r_frame_rate,codec_name",
         "-of", "json", str(output_path)],
        capture_output=True, text=True, check=True,
    )
    print(probe.stdout)
