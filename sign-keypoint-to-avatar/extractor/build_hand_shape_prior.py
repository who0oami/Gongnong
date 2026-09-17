"""Author: jihyeon (2026-09)

Build a natural-hand-shape statistical prior from the 1500 multiview-triangulated
SYN skeleton JSONs, for correcting noisy real-video MediaPipe hand shapes.

Why this representation
------------------------
Each hand frame is reduced to 14 per-joint bend angles (Thumb: MCP/IP/TIP -> 2 angles
since CMC direction is separate; Index/Middle/Ring/Little: MCP/PIP/DIP -> 3 angles
each). This mirrors the (bend, spread) decomposition mediapipe_to_blender_aligned.py
already computes internally for retargeting, but keeps just the bend/flexion
component per joint, which is what most distinguishes a plausible hand shape from an
implausible one (spread and overall orientation are comparatively well-constrained by
the wrist/arm tracking already). It is coordinate-frame invariant (computed from
consecutive segment vectors of the same hand), so it works identically whether the
source is the SYN dataset's absolute 3D meters or a real-video MediaPipe hand.

The 1500 SYN words are internally described as
"robust_approximate_multiview_triangulation" (5-camera DLT triangulation with
outlier rejection) - i.e. real triangulated 3D, not a single-view guess - so their
finger shapes are a much more reliable reference for "what does a real human hand
joint angle configuration look like" than anything derived from one front-view video.

Usage:
  python extractor/build_hand_shape_prior.py --dataset "C:/Users/ESTsoft/Desktop/output_3d/output_3d" --output extractor/hand_shape_prior.npz
"""
import argparse
import json
import math
from pathlib import Path

import numpy as np

FINGERS = ['Thumb', 'Index', 'Middle', 'Ring', 'Little']
STARTS = {'Thumb': 1, 'Index': 5, 'Middle': 9, 'Ring': 13, 'Little': 17}


def to_xyz(p):
    return (p['x'], p['y'], p['z']) if isinstance(p, dict) else tuple(p)


def sub(a, b):
    return (a[0]-b[0], a[1]-b[1], a[2]-b[2])


def norm(a):
    return math.sqrt(sum(v*v for v in a))


def angle_between(u, v):
    lu, lv = norm(u), norm(v)
    if lu < 1e-9 or lv < 1e-9:
        return None
    cos = sum(a*b for a, b in zip(u, v)) / (lu*lv)
    return math.acos(max(-1.0, min(1.0, cos)))


def hand_bend_vector(hand):
    """21-point hand -> 14 joint bend angles (radians), or None if degenerate."""
    if not hand or len(hand) != 21:
        return None
    h = [to_xyz(p) for p in hand]
    out = []
    for finger in FINGERS:
        start = STARTS[finger]
        # Thumb has 3 landmarks after the wrist (CMC/MCP/IP->TIP): 2 usable bend joints.
        joints = (2, 3) if finger == 'Thumb' else (1, 2, 3)
        for j in joints:
            inc = sub(h[start+j-1], h[0] if j == 1 else h[start+j-2])
            outv = sub(h[start+j], h[start+j-1])
            a = angle_between(inc, outv)
            if a is None:
                return None
            out.append(a)
    return out


def iter_syn_hand_frames(path):
    data = json.loads(path.read_text(encoding='utf-8'))
    for frame in data.get('frames', []):
        for side in ('left_hand', 'right_hand'):
            yield frame.get(side)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--dataset', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--limit', type=int, default=None, help='Optional cap on number of word files, for a quick test run.')
    args = p.parse_args()
    if args.output.exists():
        p.error('Output exists; choose a new filename')

    files = sorted(args.dataset.glob('*_3d_approx.json'))
    if args.limit:
        files = files[:args.limit]
    if not files:
        p.error(f'No *_3d_approx.json files found under {args.dataset}')

    vectors = []
    provenance = []
    for i, path in enumerate(files):
        try:
            for hand in iter_syn_hand_frames(path):
                v = hand_bend_vector(hand)
                if v is not None:
                    vectors.append(v)
                    provenance.append(path.stem)
        except Exception as e:
            print(f'skip {path.name}: {e}')
        if (i+1) % 100 == 0:
            print(f'{i+1}/{len(files)} files, {len(vectors)} hand-frames so far', flush=True)

    arr = np.array(vectors, dtype=np.float32)
    print('corpus shape:', arr.shape)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(args.output, vectors=arr,
                         word_ids=np.array(provenance),
                         joint_order=np.array([f'{f}_{j}' for f in FINGERS
                                               for j in ((2, 3) if f == 'Thumb' else (1, 2, 3))]))
    print('SAVED', args.output)


if __name__ == '__main__':
    main()
