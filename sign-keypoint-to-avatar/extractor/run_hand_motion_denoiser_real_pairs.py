"""Run the real-pairs-trained hand-motion denoiser
(colab/train_hand_motion_denoiser_real_pairs.py) on a real video's extracted
hand shape, and export corrected joint-bend angles as JSON for
scripts/apply_denoiser_correction.py to apply in Blender.

Differs from extractor/run_hand_motion_denoiser.py only in the model's
forward() - the real-pairs model has no residual connection (noisy 2D input
and true 3D output are on different systematic scales, since 2D foreshortens
depth-wise bend, so "predict the residual from input" doesn't apply here;
the model predicts the answer directly). Loading a real-pairs checkpoint into
the old script's model class would run, but silently produce wrong output
(the input would get added back in on top of an already-direct prediction).

Needs PyTorch - run this wherever the checkpoint's environment lives (locally
if you installed torch, or in the same Colab notebook after training).

Usage:
  python extractor/run_hand_motion_denoiser_real_pairs.py \
      --motion keypoints/leave_hands_stable_v1_smoothed.json \
      --checkpoint hand_motion_denoiser_real_pairs.pt \
      --output keypoints/leave_denoised_angles_real_pairs.json
"""
import argparse
import json
import math
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn

FINGERS = ['Thumb', 'Index', 'Middle', 'Ring', 'Little']
STARTS = {'Thumb': 1, 'Index': 5, 'Middle': 9, 'Ring': 13, 'Little': 17}
JOINT_NAMES = ['Thumb2', 'Thumb3', 'Index1', 'Index2', 'Index3', 'Middle1', 'Middle2',
               'Middle3', 'Ring1', 'Ring2', 'Ring3', 'Little1', 'Little2', 'Little3']


def to_xy(p, aspect_ratio):
    # See extractor/run_hand_motion_denoiser.py for why this correction is needed:
    # MediaPipe normalizes x/y independently by width/height, which distorts
    # angles on a non-square video unless corrected back to true proportions.
    x, y = (p['x'], p['y']) if isinstance(p, dict) else tuple(p[:2])
    return (x, y * aspect_ratio)


def angle_between(u, v):
    lu, lv = math.hypot(*u), math.hypot(*v)
    if lu < 1e-6 or lv < 1e-6:
        return None
    cos = (u[0]*v[0] + u[1]*v[1]) / (lu*lv)
    return math.acos(max(-1.0, min(1.0, cos)))


def hand_bend_vector(hand, aspect_ratio):
    if not hand or len(hand) != 21:
        return None
    h = [to_xy(p, aspect_ratio) for p in hand]
    out = []
    for finger in FINGERS:
        start = STARTS[finger]
        joints = (2, 3) if finger == 'Thumb' else (1, 2, 3)
        for j in joints:
            a, b, c = h[start+j-1], h[0] if j == 1 else h[start+j-2], h[start+j]
            inc = (a[0]-b[0], a[1]-b[1])
            outv = (c[0]-h[start+j-1][0], c[1]-h[start+j-1][1])
            ang = angle_between(inc, outv)
            if ang is None:
                return None
            out.append(ang)
    return out


class HandMotionDenoiser(nn.Module):
    """Must match colab/train_hand_motion_denoiser_real_pairs.py exactly -
    no residual connection (see module docstring)."""

    def __init__(self, in_dim=14, hidden=64, layers=2, dropout=0.2):
        super().__init__()
        self.input_proj = nn.Linear(in_dim, hidden)
        self.gru = nn.GRU(hidden, hidden, num_layers=layers, batch_first=True,
                           bidirectional=True, dropout=dropout)
        self.output_proj = nn.Sequential(
            nn.Linear(hidden * 2, hidden), nn.ReLU(), nn.Linear(hidden, in_dim))

    def forward(self, x):
        h = self.input_proj(x)
        h, _ = self.gru(h)
        return self.output_proj(h)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--motion', type=Path, required=True,
                   help='e.g. keypoints/leave_hands_stable_v1_smoothed.json')
    p.add_argument('--checkpoint', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    if args.output.exists():
        p.error('Output exists; choose a new filename')

    ckpt = torch.load(args.checkpoint, map_location='cpu')
    model = HandMotionDenoiser()
    model.load_state_dict(ckpt['model_state'])
    model.eval()

    data = json.loads(args.motion.read_text(encoding='utf-8'))
    frames = data['frames']
    aspect_ratio = data['height'] / data['width']
    print(f'aspect ratio correction: height/width = {aspect_ratio:.4f} '
          f'({data["width"]}x{data["height"]})')

    result = {'joint_order': JOINT_NAMES, 'sides': {}}
    for side_key, side in (('left_hand_shape', 'L'), ('right_hand_shape', 'R')):
        seq = []
        valid_frames = []
        for i, fr in enumerate(frames):
            v = hand_bend_vector(fr.get(side_key), aspect_ratio)
            if v is not None:
                seq.append(v)
                valid_frames.append(i)
        if len(seq) < 4:
            print(f'{side}: not enough valid frames ({len(seq)}), skipping')
            continue
        arr = np.array(seq, dtype=np.float32)
        with torch.no_grad():
            corrected = model(torch.from_numpy(arr).unsqueeze(0))[0].numpy()
        corrected = np.clip(corrected, 0.0, math.pi)
        result['sides'][side] = {'frame_indices': valid_frames,
                                  'angles_rad': corrected.tolist()}
        print(f'{side}: corrected {len(valid_frames)} frames')

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2), encoding='utf-8')
    print('SAVED', args.output)


if __name__ == '__main__':
    main()
