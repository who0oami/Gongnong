"""Pair up REAL (noisy-from-our-own-pipeline, true-answer) hand-bend-angle
sequences, for training colab/train_hand_motion_denoiser.py without any
synthetic/guessed noise.

Why this instead of synthetic noise
------------------------------------
The synthetic-noise-trained denoiser (SPIKE_WEIGHT etc.) was verified to make
real leave.mp4 jitter WORSE, not better - the guessed noise model (Gaussian
jitter + occasional big frame swings + held gaps) doesn't match what our own
extraction pipeline actually does to a real video closely enough to transfer.

Fix: D:/rendered_video/WORD####.mp4 is the exact render used to produce
output_3d/WORD####_3d_approx.json (verified: identical frame count/fps/
resolution for WORD0001 - 61 frames, 30fps, 1920x1080 in both). So running our
OWN extract -> refine -> stabilize -> smooth pipeline
(scripts/batch_extract_syn_videos.py) on that same video gives REAL noisy
output that is frame-for-frame aligned with a REAL verified answer - an
actual (noisy, clean) pair, not a simulated one.

Usage:
  python extractor/build_real_denoiser_pairs.py \
      --extracted-root keypoints/syn_training/smoothed \
      --ground-truth-root "C:/Users/ESTsoft/Desktop/output_3d/output_3d" \
      --output extractor/real_denoiser_pairs.npz
"""
import argparse
import json
import math
from pathlib import Path

import numpy as np

FINGERS = ['Thumb', 'Index', 'Middle', 'Ring', 'Little']
STARTS = {'Thumb': 1, 'Index': 5, 'Middle': 9, 'Ring': 13, 'Little': 17}
JOINT_NAMES = ['Thumb2', 'Thumb3', 'Index1', 'Index2', 'Index3', 'Middle1', 'Middle2',
               'Middle3', 'Ring1', 'Ring2', 'Ring3', 'Little1', 'Little2', 'Little3']


def angle_between(u, v):
    lu = math.sqrt(sum(c * c for c in u))
    lv = math.sqrt(sum(c * c for c in v))
    if lu < 1e-9 or lv < 1e-9:
        return None
    cos = sum(a * b for a, b in zip(u, v)) / (lu * lv)
    return math.acos(max(-1.0, min(1.0, cos)))


def bend_vector(points, dims):
    """points: 21 coordinate tuples (2D or 3D, already in an undistorted space)."""
    if not points or len(points) != 21:
        return None
    out = []
    for finger in FINGERS:
        start = STARTS[finger]
        joints = (2, 3) if finger == 'Thumb' else (1, 2, 3)
        for j in joints:
            a = points[start + j - 1]
            b = points[0] if j == 1 else points[start + j - 2]
            c = points[start + j]
            inc = tuple(a[k] - b[k] for k in range(dims))
            outv = tuple(c[k] - points[start + j - 1][k] for k in range(dims))
            ang = angle_between(inc, outv)
            if ang is None:
                return None
            out.append(ang)
    return out


def our_hand_2d(entry, aspect_ratio):
    if not entry or len(entry) != 21:
        return None
    pts = []
    for p in entry:
        x, y = (p['x'], p['y']) if isinstance(p, dict) else tuple(p[:2])
        pts.append((x, y * aspect_ratio))
    return bend_vector(pts, dims=2)


def truth_hand_3d(entry):
    if not entry or len(entry) != 21:
        return None
    pts = [((p['x'], p['y'], p['z']) if isinstance(p, dict) else tuple(p)) for p in entry]
    return bend_vector(pts, dims=3)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--extracted-root', type=Path, required=True,
                    help='keypoints/syn_training/smoothed - our own pipeline output per word')
    p.add_argument('--ground-truth-root', type=Path, required=True,
                    help='the 1500-word output_3d folder')
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    if args.output.exists():
        p.error('Output exists; choose a new filename')

    noisy_seqs, clean_seqs, meta = [], [], []
    extracted_files = sorted(args.extracted_root.glob('WORD*.json'))
    print(f'{len(extracted_files)} extracted words found')

    skipped_no_truth = 0
    skipped_frame_mismatch = 0
    for path in extracted_files:
        word_id = path.stem
        truth_path = args.ground_truth_root / f'{word_id}_3d_approx.json'
        if not truth_path.is_file():
            skipped_no_truth += 1
            continue

        ours = json.loads(path.read_text(encoding='utf-8'))
        truth = json.loads(truth_path.read_text(encoding='utf-8'))
        our_frames = ours['frames']
        truth_frames = truth['frames']
        if len(our_frames) != len(truth_frames):
            skipped_frame_mismatch += 1
            continue

        aspect_ratio = ours['height'] / ours['width']
        for side_key, side in (('left_hand_shape', 'left_hand'), ('right_hand_shape', 'right_hand')):
            noisy, clean = [], []
            for of, tf in zip(our_frames, truth_frames):
                n = our_hand_2d(of.get(side_key), aspect_ratio)
                c = truth_hand_3d(tf.get(side))
                if n is None or c is None:
                    continue
                noisy.append(n)
                clean.append(c)
            if len(noisy) >= 8:
                noisy_seqs.append(np.array(noisy, dtype=np.float32))
                clean_seqs.append(np.array(clean, dtype=np.float32))
                meta.append(f'{word_id}_{side}')

    print(f'skipped (no ground truth file): {skipped_no_truth}')
    print(f'skipped (frame count mismatch): {skipped_frame_mismatch}')
    print(f'paired sequences: {len(noisy_seqs)}')

    args.output.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        args.output,
        noisy=np.array(noisy_seqs, dtype=object),
        clean=np.array(clean_seqs, dtype=object),
        meta=np.array(meta),
        joint_order=np.array(JOINT_NAMES),
    )
    print('SAVED', args.output)


if __name__ == '__main__':
    main()
