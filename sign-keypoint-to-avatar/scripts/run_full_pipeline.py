"""Author: jihyeon (2026-09)

One-shot video -> avatar pipeline: chains extract_keypoints.py, refine_hands.py
+ prepare_stable_hands.py, smooth_hand_landmarks.py, mediapipe_to_blender_aligned.py,
and (if a prior corpus is available) correct_hand_shape_prior.py. This is the same
5-step sequence documented in the top-level README's "빠른 시작", just run back to
back instead of one command at a time.

Usage:
  python scripts/run_full_pipeline.py "<video path>.mp4" --sign-id love --label 사랑
"""
import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
SIGN_ID_CHARS = set('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('video', type=Path)
    p.add_argument('--sign-id', required=True)
    p.add_argument('--label', default='')
    p.add_argument('--profile', type=Path, default=ROOT / 'mediapipe-preview/blender_F10_profile_v1.json')
    p.add_argument('--blender', type=Path, default=Path('C:/Program Files/Blender Foundation/Blender 5.2/blender.exe'))
    p.add_argument('--prior', type=Path, default=ROOT / 'extractor/hand_shape_prior.npz')
    p.add_argument('--skip-prior-correction', action='store_true',
                    help='Skip step 5 even if --prior exists.')
    args = p.parse_args()

    if not args.video.is_file():
        p.error(f'Video not found: {args.video}')
    if not args.blender.is_file():
        p.error(f'Blender executable not found: {args.blender}')
    if not args.sign_id or any(c not in SIGN_ID_CHARS for c in args.sign_id):
        p.error('Use letters, digits, underscore or hyphen for sign-id')
    profile = json.loads(args.profile.read_text(encoding='utf-8'))
    if not Path(profile['model_file']).is_file():
        p.error(f"Model file in profile is missing: {profile['model_file']}")

    run = ROOT / 'output' / (args.sign_id + '_hands_' + datetime.now().strftime('%Y%m%d_%H%M%S'))
    run.mkdir(parents=True, exist_ok=False)
    raw = run / 'raw.json'
    refined = run / 'refined.json'
    stable = run / 'stable.json'
    smoothed = run / 'stable_smoothed.json'
    blend_v1 = run / (run.name + '_v1.blend')
    blend_v2 = run / (run.name + '_v2.blend')
    report = run / 'prior_correction_report.json'

    do_prior_correction = args.prior.is_file() and not args.skip_prior_correction

    commands = [
        [sys.executable, str(ROOT / 'extractor/extract_keypoints.py'), str(args.video.resolve()),
         '--output', str(raw), '--sign-id', args.sign_id, '--label', args.label, '--download-model'],
        [sys.executable, str(ROOT / 'extractor/refine_hands.py'), str(args.video.resolve()),
         '--input', str(raw), '--output', str(refined), '--download-model'],
        [sys.executable, str(ROOT / 'scripts/prepare_stable_hands.py'),
         '--base', str(raw), '--refined', str(refined), '--output', str(stable)],
        [sys.executable, str(ROOT / 'extractor/smooth_hand_landmarks.py'),
         '--input', str(stable), '--output', str(smoothed)],
        [str(args.blender), '--background', '--factory-startup', '--python-exit-code', '1',
         '--python', str(ROOT / 'scripts/mediapipe_to_blender_aligned.py'), '--',
         '--motion', str(smoothed), '--profile', str(args.profile.resolve()),
         '--output', str(blend_v1), '--render'],
    ]
    if do_prior_correction:
        commands.append(
            [str(args.blender), '--background', '--python', str(ROOT / 'scripts/correct_hand_shape_prior.py'), '--',
             '--input', str(blend_v1), '--output', str(blend_v2),
             '--prior', str(args.prior.resolve()), '--report', str(report)])
    elif not args.skip_prior_correction:
        print(f'No prior corpus at {args.prior} - skipping step 5 (KNN hand-shape correction).')

    # Git Bash sets HOME to a POSIX-style path (e.g. /c/Users/...), which the native
    # Windows Blender build cannot resolve as a cache directory; it then falls back to
    # dumping a garbled-named ".thumbnails" cache folder into ROOT (cwd). Only Blender
    # needs the corrected HOME - the Python steps are unaffected.
    blender_env = os.environ.copy()
    blender_env['HOME'] = os.environ.get('USERPROFILE', blender_env.get('HOME', ''))
    for cmd in commands:
        env = blender_env if Path(cmd[0]) == args.blender else None
        subprocess.run(cmd, cwd=ROOT, check=True, env=env)

    final = blend_v2 if do_prior_correction else blend_v1
    print(f'Created: {final}\nReview audit and renders before accepting sign quality.')


if __name__ == '__main__':
    main()
