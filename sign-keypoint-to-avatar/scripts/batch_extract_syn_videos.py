"""Run the exact same extract -> refine -> stabilize -> smooth pipeline used for
love.mp4/leave.mp4 across every D:/rendered_video/WORD####.mp4, to build REAL
(noisy-from-our-pipeline, true-answer) training pairs instead of synthetic noise.

Each rendered_video/WORD####.mp4 is the identical render used to produce the
matching output_3d/WORD####_3d_approx.json ground truth (verified: same frame
count, fps, resolution) - so frames line up 1:1 with no alignment step needed.

Resumable: skips a word/stage whose output file already exists, so a drive
disconnect or interruption can just be re-run.

Usage:
  python scripts/batch_extract_syn_videos.py --video-root "D:/rendered_video" --limit 5   # smoke test
  python scripts/batch_extract_syn_videos.py --video-root "D:/rendered_video"             # full run
"""
import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_ROOT = ROOT / 'keypoints/syn_training'


def run(cmd):
    result = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return result.returncode, result.stdout, result.stderr


def process_word(video_path, download_model_once):
    word_id = video_path.stem  # e.g. WORD0001
    raw = OUT_ROOT / 'raw' / f'{word_id}.json'
    refined = OUT_ROOT / 'refined' / f'{word_id}.json'
    stable = OUT_ROOT / 'stable' / f'{word_id}.json'
    smoothed = OUT_ROOT / 'smoothed' / f'{word_id}.json'

    for p in (raw, refined, stable, smoothed):
        p.parent.mkdir(parents=True, exist_ok=True)

    if smoothed.exists():
        return 'already_done'

    if not raw.exists():
        cmd = [sys.executable, str(ROOT / 'extractor/extract_keypoints.py'), str(video_path),
               '--output', str(raw), '--sign-id', word_id]
        if download_model_once:
            cmd.append('--download-model')
        rc, out, err = run(cmd)
        if rc != 0:
            return f'FAILED at extract_keypoints: {err[-500:]}'

    if not refined.exists():
        cmd = [sys.executable, str(ROOT / 'extractor/refine_hands.py'), str(video_path),
               '--input', str(raw), '--output', str(refined)]
        rc, out, err = run(cmd)
        if rc != 0:
            return f'FAILED at refine_hands: {err[-500:]}'

    if not stable.exists():
        cmd = [sys.executable, str(ROOT / 'scripts/prepare_stable_hands.py'),
               '--base', str(raw), '--refined', str(refined), '--output', str(stable)]
        rc, out, err = run(cmd)
        if rc != 0:
            return f'FAILED at prepare_stable_hands: {err[-500:]}'

    cmd = [sys.executable, str(ROOT / 'extractor/smooth_hand_landmarks.py'),
           '--input', str(stable), '--output', str(smoothed)]
    rc, out, err = run(cmd)
    if rc != 0:
        return f'FAILED at smooth_hand_landmarks: {err[-500:]}'

    return 'ok'


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--video-root', type=Path, required=True)
    p.add_argument('--limit', type=int, default=None)
    args = p.parse_args()

    videos = sorted(args.video_root.glob('WORD*.mp4'))
    if args.limit:
        videos = videos[:args.limit]
    print(f'{len(videos)} videos to process')

    # extract_keypoints.py downloads the MediaPipe model once and caches it locally;
    # refine_hands.py needs its own separate hand_landmarker model too.
    counts = {}
    for i, video_path in enumerate(videos, 1):
        status = process_word(video_path, download_model_once=True)
        counts[status.split(':')[0]] = counts.get(status.split(':')[0], 0) + 1
        print(f'[{i}/{len(videos)}] {video_path.stem}: {status}', flush=True)

    print('SUMMARY:', counts)


if __name__ == '__main__':
    main()
