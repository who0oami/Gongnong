"""Author: jihyeon (2026-09)

Nudge a retargeted hand's finger-joint bend angles toward the nearest plausible
shapes in the 1500-word SYN triangulated-skeleton prior, wherever the current
(video-derived) shape looks like an outlier relative to that corpus.

This is a lightweight statistical correction, not a trained model: for every frame
and side, it looks up the k nearest neighbors of the current 14-joint bend-angle
vector in extractor/hand_shape_prior.npz (216k real hand-frames from 1500 words,
multiview-triangulated - see build_hand_shape_prior.py for why that source is
trustworthy), and blends the current pose toward their distance-weighted average.
The blend strength scales with how far the current shape is from its nearest
neighbor: shapes that already resemble something in the natural corpus are left
alone; shapes that don't resemble anything in 1500 words of real signing (i.e.
likely tracking noise, not a real articulation) get pulled toward the closest
plausible one. Only the bend MAGNITUDE of each joint's rotation is adjusted - the
rotation axis (which carries orientation/twist, not modeled by the prior) is kept.

Usage:
  blender --background --python scripts/correct_hand_shape_prior.py -- \\
      --input output/leave_M10_smoothed_v1.blend \\
      --output output/leave_M10_prior_corrected_v1.blend \\
      --prior extractor/hand_shape_prior.npz
"""
import argparse
import sys
from pathlib import Path

import numpy as np
import bpy
from mathutils import Quaternion

ROOT = Path(__file__).resolve().parents[1]
FINGER_JOINTS = ['Thumb2', 'Thumb3', 'Index1', 'Index2', 'Index3', 'Middle1', 'Middle2',
                 'Middle3', 'Ring1', 'Ring2', 'Ring3', 'Little1', 'Little2', 'Little3']

# Below this nearest-neighbor distance (radians, L2 over 14 joints) a shape is
# considered already-plausible and is left untouched; above the upper bound it is
# corrected at full strength toward the neighbor-weighted target.
OUTLIER_LOW = 0.35
OUTLIER_HIGH = 1.1
MAX_ALPHA = 0.85
K_NEIGHBORS = 12


def bone_names(side):
    return [f'J_Bip_{side}_{j}' for j in FINGER_JOINTS]


def nearest_neighbor_target(corpus, query, k):
    d2 = np.sum((corpus - query[None, :]) ** 2, axis=1)
    idx = np.argpartition(d2, k)[:k]
    dists = np.sqrt(d2[idx])
    d0 = float(dists.min())
    weights = 1.0 / np.maximum(dists, 1e-4)
    weights /= weights.sum()
    target = (corpus[idx] * weights[:, None]).sum(axis=0)
    return target, d0


def main():
    args = argparse.Namespace()
    argv = sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--prior', type=Path, default=ROOT/'extractor/hand_shape_prior.npz')
    parser.add_argument('--report', type=Path, default=None)
    parser.parse_args(argv, namespace=args)

    if args.output.exists():
        raise FileExistsError(args.output)

    prior = np.load(args.prior)
    corpus = prior['vectors'].astype(np.float64)
    joint_order = list(prior['joint_order'])
    assert joint_order == [f'{j[:-1]}_{j[-1]}' for j in FINGER_JOINTS], (joint_order, FINGER_JOINTS)

    bpy.ops.wm.open_mainfile(filepath=str(args.input))
    scene = bpy.context.scene
    arm = [o for o in scene.objects if o.type == 'ARMATURE'][0]
    frames = list(range(scene.frame_start, scene.frame_end + 1))

    # Two passes: computing each frame's outlier-ness and neighbor target
    # independently (pass 1) and then applying it per frame (pass 2, after
    # smoothing) means the *correction itself* doesn't add new frame-to-frame
    # noise - a per-frame-independent alpha/target based on a per-frame-noisy
    # query was measured to slightly *increase* jitter versus not correcting
    # at all, because neighboring frames could land on different outlier
    # strengths or different corpus neighbors even when the real hand barely
    # moved between them.
    per_side = {}
    for side in ('L', 'R'):
        names = bone_names(side)
        currents, targets, d0s = [], [], []
        for frame in frames:
            scene.frame_set(frame)
            current = np.array([arm.pose.bones[n].rotation_quaternion.angle for n in names])
            target, d0 = nearest_neighbor_target(corpus, current, K_NEIGHBORS)
            currents.append(current)
            targets.append(target)
            d0s.append(d0)
        per_side[side] = {'names': names, 'currents': currents, 'targets': targets, 'd0s': d0s}

    def smooth_series(values, radius=2):
        arr = np.array(values)
        out = np.empty_like(arr)
        for i in range(len(arr)):
            lo, hi = max(0, i - radius), min(len(arr), i + radius + 1)
            out[i] = arr[lo:hi].mean(axis=0)
        return out

    report = {'low': OUTLIER_LOW, 'high': OUTLIER_HIGH, 'max_alpha': MAX_ALPHA, 'frames': []}
    frame_reports = {f: {'frame': f, 'sides': {}} for f in frames}
    for side in ('L', 'R'):
        data = per_side[side]
        smoothed_d0 = smooth_series(data['d0s'])
        smoothed_target = smooth_series(data['targets'])
        alphas = np.clip((smoothed_d0 - OUTLIER_LOW) / (OUTLIER_HIGH - OUTLIER_LOW) * MAX_ALPHA, 0.0, MAX_ALPHA)
        for i, frame in enumerate(frames):
            scene.frame_set(frame)
            alpha = float(alphas[i])
            if alpha > 0:
                corrected = data['currents'][i] + alpha * (smoothed_target[i] - data['currents'][i])
                for name, new_angle in zip(data['names'], corrected):
                    pb = arm.pose.bones[name]
                    axis = pb.rotation_quaternion.axis
                    pb.rotation_quaternion = Quaternion(axis, float(new_angle))
                    pb.keyframe_insert(data_path='rotation_quaternion', frame=frame)
            frame_reports[frame]['sides'][side] = {
                'nearest_neighbor_distance': round(float(smoothed_d0[i]), 4), 'alpha': round(alpha, 4)}
    report['frames'] = [frame_reports[f] for f in frames]

    args.output.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(args.output))
    if args.report:
        import json
        args.report.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print('SAVED', args.output)


if __name__ == '__main__':
    main()
