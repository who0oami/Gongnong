"""Combine the two corrections by joint type, based on measured per-joint
results on leave.mp4:
  - proximal/MCP-level joints (Thumb2, Index1, Middle1, Ring1, Little1):
    the real-pairs-trained denoiser (extractor/run_hand_motion_denoiser_real_pairs.py)
    measured BETTER than both the uncorrected baseline and the KNN prior
    correction on this joint type.
  - the remaining joints (Thumb3, {Index,Middle,Ring,Little}{2,3}):
    the KNN statistical prior correction (scripts/correct_hand_shape_prior.py)
    measured better - the denoiser's SYN-video training domain gap shows up
    more on these finer joints.

Starts from an already KNN-corrected .blend (so those joints are untouched)
and overwrites only the proximal-joint bones' rotation with the denoiser's
angle for that frame - same "keep rotation axis, replace angle magnitude"
mechanism as the other correction scripts.

Only tested on leave.mp4 so far - re-verify this joint-type split on a
second clip (e.g. love.mp4) before treating it as a general rule.

Usage:
  blender --background --python scripts/apply_hybrid_correction.py -- \\
      --input output/leave_M10_prior_corrected_v2.blend \\
      --output output/leave_M10_hybrid_v1.blend \\
      --denoiser-corrections keypoints/leave_denoised_angles_real_pairs.json
"""
import argparse
import json
import sys
from pathlib import Path

import bpy
from mathutils import Quaternion

PROXIMAL_JOINTS = ['Thumb2', 'Index1', 'Middle1', 'Ring1', 'Little1']


def main():
    argv = sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--denoiser-corrections', type=Path, required=True)
    parser.add_argument('--side', choices=['L', 'R', 'both'], default='both')
    args = parser.parse_args(argv)

    if args.output.exists():
        raise FileExistsError(args.output)

    corrections = json.loads(args.denoiser_corrections.read_text(encoding='utf-8'))
    sides = ['L', 'R'] if args.side == 'both' else [args.side]

    bpy.ops.wm.open_mainfile(filepath=str(args.input))
    scene = bpy.context.scene
    arm = [o for o in scene.objects if o.type == 'ARMATURE'][0]

    for side in sides:
        side_data = corrections['sides'].get(side)
        if side_data is None:
            print(f'{side}: no denoiser correction data, skipping')
            continue
        joint_order = corrections['joint_order']
        proximal_positions = [i for i, j in enumerate(joint_order) if j in PROXIMAL_JOINTS]
        bone_names = [f'J_Bip_{side}_{joint_order[i]}' for i in proximal_positions]

        applied = 0
        for local_i, frame in enumerate(side_data['frame_indices']):
            scene.frame_set(frame)
            angles = side_data['angles_rad']
            for pos, name in zip(proximal_positions, bone_names):
                pb = arm.pose.bones[name]
                axis = pb.rotation_quaternion.axis
                pb.rotation_quaternion = Quaternion(axis, float(angles[local_i][pos]))
                pb.keyframe_insert(data_path='rotation_quaternion', frame=frame)
            applied += 1
        print(f'{side}: overrode {len(bone_names)} proximal-joint bones on {applied} frames '
              f'({bone_names}); all other joints kept from --input as-is')

    args.output.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(args.output))
    print('SAVED', args.output)


if __name__ == '__main__':
    main()
