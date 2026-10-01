"""Apply the trained denoiser's corrected joint-bend angles (from
extractor/run_hand_motion_denoiser.py) onto an already-retargeted Blender
file's finger bones - same "keep rotation axis, replace angle magnitude"
mechanism as scripts/correct_hand_shape_prior.py, so it drops into the same
pipeline slot. No PyTorch needed here; this script only reads the exported
JSON of already-computed angles.

Usage:
  blender --background --python scripts/apply_denoiser_correction.py -- \\
      --input output/leave_M10_smoothed_v1.blend \\
      --output output/leave_M10_denoised_v1.blend \\
      --corrections keypoints/leave_denoised_angles.json \\
      --side L
"""
import argparse
import json
import sys
from pathlib import Path

import bpy
from mathutils import Quaternion


def main():
    argv = sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--corrections', type=Path, required=True)
    parser.add_argument('--side', choices=['L', 'R', 'both'], default='both')
    args = parser.parse_args(argv)

    if args.output.exists():
        raise FileExistsError(args.output)

    corrections = json.loads(args.corrections.read_text(encoding='utf-8'))
    joint_order = corrections['joint_order']
    sides = ['L', 'R'] if args.side == 'both' else [args.side]

    bpy.ops.wm.open_mainfile(filepath=str(args.input))
    scene = bpy.context.scene
    arm = [o for o in scene.objects if o.type == 'ARMATURE'][0]

    for side in sides:
        side_data = corrections['sides'].get(side)
        if side_data is None:
            print(f'{side}: no correction data, skipping')
            continue
        bone_names = [f'J_Bip_{side}_{j}' for j in joint_order]
        for local_i, frame in enumerate(side_data['frame_indices']):
            scene.frame_set(frame)
            angles = side_data['angles_rad'][local_i]
            for name, angle in zip(bone_names, angles):
                pb = arm.pose.bones[name]
                axis = pb.rotation_quaternion.axis
                pb.rotation_quaternion = Quaternion(axis, float(angle))
                pb.keyframe_insert(data_path='rotation_quaternion', frame=frame)
        print(f'{side}: applied {len(side_data["frame_indices"])} frames')

    args.output.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(args.output))
    print('SAVED', args.output)


if __name__ == '__main__':
    main()
