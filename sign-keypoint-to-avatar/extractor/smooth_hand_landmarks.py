"""One-Euro-filter the hand landmark channels that actually drive retargeting.

Why this exists
----------------
mediapipe_to_blender_aligned.py reads `{side}_shape` (image-space finger
geometry) and `{side}_orientation` (image-space palm orientation) per frame.
Those come from prepare_stable_hands.py, which picks - independently, frame
by frame - between the Holistic landmarks and a separate crop-refined
re-detection (see refine_hands.py). Both detectors run with no memory of
neighboring frames (single-image inference), so consecutive frames can come
from two different, independently-noisy estimates of the same real hand.
Checked on leave_hands_stable_v1.json: the left hand's detection source
("holistic" vs "crop_consensus") flips on 46 of the 57 tracked frames, and
the source is "missing" (no detection at all) for the last 16 frames of the
clip - both are exactly the kind of frame-to-frame inconsistency that reads
as trembling once played back, even though the Blender-side smoothing
(profile rotation_filter: a small radius-2 median + response gain) already
runs afterward - that stage only softens bone-rotation swings, it does not
fix noisy per-landmark input.

A One-Euro filter (Casiez et al. 2012) is the standard fix for exactly this
signal shape: it suppresses small jitter when the signal is nearly still,
but relaxes automatically (low lag) once real, fast motion starts, based on
the estimated velocity - unlike a fixed-radius median, it does not blur a
fast hand movement to fight jitter in a still one. Applied here per landmark,
per x/y/z, independently for each of the four fields the retargeter reads:
{left,right}_hand_shape and {left,right}_hand_orientation.

Usage:
  python extractor/smooth_hand_landmarks.py --input keypoints/leave_hands_stable_v1.json --output keypoints/leave_hands_stable_v1_smoothed.json
"""
import argparse
import json
from pathlib import Path


class OneEuroFilter:
    """Casiez et al. 2012. Smooths noisy jitter while tracking fast motion with low lag."""

    def __init__(self, min_cutoff=1.0, beta=0.3, d_cutoff=1.0):
        self.min_cutoff = min_cutoff
        self.beta = beta
        self.d_cutoff = d_cutoff
        self.x_prev = None
        self.dx_prev = 0.0
        self.t_prev = None

    @staticmethod
    def _alpha(cutoff, dt):
        tau = 1.0 / (2 * 3.141592653589793 * cutoff)
        return 1.0 / (1.0 + tau / dt)

    def __call__(self, t, x):
        if self.t_prev is None:
            self.x_prev = x
            self.t_prev = t
            return x
        dt = max(t - self.t_prev, 1e-6)
        dx = (x - self.x_prev) / dt
        a_d = self._alpha(self.d_cutoff, dt)
        dx_hat = a_d * dx + (1 - a_d) * self.dx_prev
        cutoff = self.min_cutoff + self.beta * abs(dx_hat)
        a = self._alpha(cutoff, dt)
        x_hat = a * x + (1 - a) * self.x_prev
        self.x_prev, self.dx_prev, self.t_prev = x_hat, dx_hat, t
        return x_hat


FIELDS = ['left_hand_shape', 'right_hand_shape', 'left_hand_orientation', 'right_hand_orientation']


def smooth(data, min_cutoff, beta):
    # One filter chain per (field, landmark index, axis) so each of the
    # 21*3 signals per hand gets its own velocity-adaptive cutoff.
    filters = {}

    def get_filter(key):
        if key not in filters:
            filters[key] = OneEuroFilter(min_cutoff=min_cutoff, beta=beta)
        return filters[key]

    for row in data['frames']:
        t = row['time']
        for field in FIELDS:
            points = row.get(field)
            if not points or len(points) != 21:
                continue
            for i, p in enumerate(points):
                for axis in ('x', 'y', 'z'):
                    key = (field, i, axis)
                    p[axis] = get_filter(key)(t, p[axis])
    return data


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--min-cutoff', type=float, default=1.0,
                    help='Lower = smoother when still, but more lag on slow motion.')
    p.add_argument('--beta', type=float, default=0.3,
                    help='Higher = less lag during fast motion, but less smoothing.')
    args = p.parse_args()
    if args.output.exists():
        p.error('Output exists; choose a new filename')
    data = json.loads(args.input.read_text(encoding='utf-8'))
    data = smooth(data, args.min_cutoff, args.beta)
    data['hand_smoothing'] = {'method': 'one_euro_filter', 'min_cutoff': args.min_cutoff,
                               'beta': args.beta, 'fields': FIELDS, 'source_json': args.input.name}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, allow_nan=False, separators=(',', ':'))
    print(args.output)


if __name__ == '__main__':
    main()
