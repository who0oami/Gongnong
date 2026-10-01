"""Fresh VRM import -> anatomically assigned MediaPipe hands -> new .blend + audit."""
import argparse
from collections import Counter
from datetime import datetime
import hashlib
import json
from pathlib import Path
import sys
from math import atan2, radians, sin, cos

import bpy
from mathutils import Matrix, Vector, Quaternion

ROOT = Path(__file__).resolve().parents[1]
FINGERS = {'Thumb': 1, 'Index': 5, 'Middle': 9, 'Ring': 13, 'Little': 17}
EPS = 1e-7


def basis(longitudinal, transverse):
    y = longitudinal.normalized()
    x = transverse - y * transverse.dot(y)
    if x.length < EPS or longitudinal.length < EPS:
        raise ValueError('Degenerate anatomical basis')
    x.normalize()
    z = x.cross(y).normalized()
    return Matrix((x, y, z)).transposed()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--motion', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--profile', type=Path, default=ROOT/'mediapipe-preview/blender_profile.json')
    parser.add_argument('--render', action='store_true')
    args = parser.parse_args(sys.argv[sys.argv.index('--')+1:])
    if args.output.exists():
        raise FileExistsError(args.output)
    profile = json.loads(args.profile.read_text(encoding='utf-8'))
    motion = json.loads(args.motion.read_text(encoding='utf-8'))
    if motion['schema'] != 'mediapipe-holistic-v1' or profile['input_mirrored']:
        raise ValueError('Requires unmirrored MediaPipe input; automatic side swapping is disabled')
    outdir = ROOT/'diagnostics'/args.output.stem/datetime.now().strftime('%Y%m%d-%H%M%S')
    outdir.mkdir(parents=True, exist_ok=False)
    # Separate background process, empty factory scene. No existing .blend is opened.
    bpy.ops.wm.read_factory_settings(use_empty=True)
    model = Path(profile['model_file'])
    bpy.ops.import_scene.gltf(filepath=str(model))
    arms = [o for o in bpy.context.scene.objects if o.type == 'ARMATURE']
    if not arms:
        raise ValueError('No armature')
    arm = max(arms, key=lambda a: sum(m.type=='ARMATURE' and m.object==a
              for o in bpy.context.scene.objects for m in o.modifiers))
    # Keep every imported object; duplicate bound rigs receive the same action below.
    arm.animation_data_create()
    action = bpy.data.actions.new(args.output.stem)
    arm.animation_data.action = action
    scene = bpy.context.scene
    scene.render.fps = round(motion['fps'])
    scene.render.fps_base = scene.render.fps/motion['fps']
    scene.frame_start = 0
    scene.frame_end = round(motion['frames'][-1]['time']*motion['fps'])
    bone = arm.data.bones
    head = lambda n: bone[n].head_local.copy()
    rest = lambda n: bone[n].matrix_local.to_3x3().normalized()
    x = (head('J_Bip_L_UpperArm')-head('J_Bip_R_UpperArm')).normalized()
    up = (head('J_Bip_C_Neck')-head('J_Bip_C_Hips')).normalized()
    front = x.cross(up).normalized()
    up = front.cross(x).normalized()
    target_body = Matrix((x, up, front)).transposed()
    source_body = Matrix(((1,0,0),(0,-1,0),(0,0,-1))).transposed()
    mapping = target_body @ source_body.transposed()
    assert abs(mapping.determinant()-1) < 1e-5, 'Reflection is forbidden'
    vec = lambda p: mapping @ Vector((p['x'], p['y'], p['z']))
    rigs = {}
    for side, spec in profile['anatomical_sides'].items():
        prefix = f'J_Bip_{side}_'
        required = [prefix+n for n in ('UpperArm','LowerArm','Hand')]
        required += [prefix+f+str(j) for f in FINGERS for j in (1,2,3)]
        missing = [n for n in required if n not in bone]
        if missing:
            raise ValueError(f'Missing bones: {missing}')
        wrist = head(prefix+'Hand')
        palm = basis(head(prefix+'Middle1')-wrist, head(prefix+'Index1')-head(prefix+'Little1'))
        rigs[side] = dict(prefix=prefix, spec=spec, names=required, palm=palm)
    previous = {}
    holds = Counter()
    report_frames = []
    direction_errors = []

    def set_absolute(name, desired):
        pb = arm.pose.bones[name]
        base = pb.parent.matrix @ pb.parent.bone.matrix_local.inverted() @ pb.bone.matrix_local if pb.parent else pb.bone.matrix_local
        local = base.to_3x3().normalized().transposed() @ desired
        pb.rotation_mode = 'QUATERNION'
        pb.rotation_quaternion = local.to_quaternion().normalized()
        bpy.context.view_layer.update()

    def aim(name, end, direction, delta=Matrix.Identity(3)):
        if direction.length < EPS:
            return
        rest_dir = head(end)-head(name) if end else bone[name].tail_local-head(name)
        predicted = delta @ rest_dir
        swing = predicted.rotation_difference(direction).to_matrix()
        set_absolute(name, swing @ delta @ rest(name))
        actual = arm.pose.bones[name].matrix.to_3x3() @ (rest(name).transposed() @ rest_dir)
        direction_errors.append(actual.angle(direction))

    for row in motion['frames']:
        frame = round(row['time']*motion['fps'])
        scene.frame_set(frame)
        for rig in rigs.values():
            for n in rig['names']:
                arm.pose.bones[n].matrix_basis = Matrix.Identity(4)
        bpy.context.view_layer.update()
        quality = {'frame': frame, 'sides': {}}
        for side, rig in rigs.items():
            prefix, spec = rig['prefix'], rig['spec']
            p = row['pose_world']
            ids = spec['pose']
            visible = len(p)==33 and all((row['pose'][i].get('visibility') or 0)>=profile['min_pose_visibility'] for i in ids)
            hand_quality = row.get('hand_quality', {}).get(spec['group'], {})
            valid = len(row[spec['group']+'_world'])==21 and (not profile['require_verified_hand_identity'] or hand_quality.get('identity')=='pose_wrist_confirmed')
            state = {'pose': bool(visible), 'hand_source': hand_quality.get('source','missing'),
                     'identity': hand_quality.get('identity','unverified')}
            quality['sides'][side] = state
            h = [vec(v) for v in row[spec['group']+'_world']] if valid else []
            palm_delta = None
            if h:
                length = (h[9]-h[0]).length
                if length<EPS or any((h[i+1]-h[i]).length < length*profile['finger_segment_ratio_min']
                    for start in FINGERS.values() for i in range(start,start+3)):
                    valid = False
                else:
                    try:
                        palm_delta = basis(h[9]-h[0], h[5]-h[17]) @ rig['palm'].transposed()
                    except ValueError:
                        valid = False
            if visible:
                a,b,c = [vec(p[i]) for i in ids]
                aim(prefix+'UpperArm', prefix+'LowerArm', b-a)
                aim(prefix+'LowerArm', prefix+'Hand', c-b, palm_delta if valid else Matrix.Identity(3))
            if visible and valid:
                set_absolute(prefix+'Hand', palm_delta @ rest(prefix+'Hand'))
                # Thumb: full 3D opposition. Other fingers: MCP flex/splay + PIP/DIP hinges.
                for finger, start in FINGERS.items():
                    for j in (1,2,3):
                        name = prefix+finger+str(j)
                        end = prefix+finger+str(j+1) if j<3 else None
                        if finger == 'Thumb':
                            aim(name, end, h[start+j]-h[start+j-1], palm_delta)
                            continue
                        current_palm = basis(h[9]-h[0], h[5]-h[17])
                        incoming = h[start+j-1] - h[0 if j==1 else start+j-2]
                        outgoing = h[start+j]-h[start+j-1]
                        u = current_palm.transposed() @ incoming.normalized()
                        v = current_palm.transposed() @ outgoing.normalized()
                        finger_profile = profile['finger']
                        palmward_sign = finger_profile['palmward_sign'][side]
                        if j==1:
                            bend = atan2(palmward_sign*v.z, (v.x*v.x+v.y*v.y)**.5) - atan2(palmward_sign*u.z,(u.x*u.x+u.y*u.y)**.5)
                            spread = atan2(v.x,v.y)-atan2(u.x,u.y)
                            spread = atan2(sin(spread),cos(spread))
                            spread_limit = radians(finger_profile['spread_max_degrees'])
                            spread = max(-spread_limit,min(spread_limit,spread))
                        else:
                            bend = incoming.angle(outgoing)
                            spread = 0
                        bend = max(0,min(radians(finger_profile['mcp_max_degrees' if j==1 else 'pip_dip_max_degrees']),bend))
                        rest_dir = (head(end)-head(name)) if end else bone[name].tail_local-head(name)
                        normal = rig['palm'].col[2]
                        palmward = normal*palmward_sign
                        axis = rest_dir.cross(palmward).normalized()
                        # Hinges constrain PIP/DIP roll; MCP additionally preserves signed splay.
                        qflex = Quaternion(rest(name).transposed() @ axis, bend)
                        qsplay = Quaternion(rest(name).transposed() @ normal, -spread)
                        pb = arm.pose.bones[name]
                        pb.rotation_mode='QUATERNION'
                        pb.rotation_quaternion = qsplay @ qflex
                        bpy.context.view_layer.update()
                holds[side] = 0
                state['applied'] = 'observed'
            else:
                holds[side] += 1
                hand_names = [prefix+'Hand']+[prefix+f+str(j) for f in FINGERS for j in (1,2,3)]
                held = visible and holds[side]<=profile['max_hold_frames'] and all(n in previous for n in hand_names)
                if held:
                    for n in hand_names:
                        arm.pose.bones[n].rotation_quaternion = previous[n].copy()
                state['applied'] = 'held_2_frames_max' if held else 'missing_neutral'
                state['review_required'] = True
            for name in rig['names']:
                pb = arm.pose.bones[name]
                pb.rotation_mode = 'QUATERNION'
                q = pb.rotation_quaternion.copy()
                if name in previous and q.dot(previous[name])<0:
                    q.negate()
                pb.rotation_quaternion = q
                pb.keyframe_insert(data_path='rotation_quaternion', frame=frame)
                previous[name] = q.copy()
        report_frames.append(quality)
        review_sides = ''.join(s for s,q in quality['sides'].items() if q.get('review_required'))
        if not report_frames[:-1] or review_sides != ''.join(s for s,q in report_frames[-2]['sides'].items() if q.get('review_required')):
            scene.timeline_markers.new('REVIEW_'+review_sides if review_sides else 'OBSERVED_L_R', frame=frame)
    for other in arms:
        if other != arm and all(n in other.pose.bones for r in rigs.values() for n in r['names']):
            other.animation_data_create()
            other.animation_data.action = action
            other.animation_data.action_slot = arm.animation_data.action_slot
    for layer in action.layers:
        for strip in layer.strips:
            for bag in strip.channelbags:
                for fc in bag.fcurves:
                    for key in fc.keyframe_points:
                        key.interpolation = 'LINEAR'
    rig_info = {n: {'head': list(b.head_local), 'tail': list(b.tail_local), 'matrix': [list(r) for r in b.matrix_local]} for n,b in bone.items()}
    (outdir/'rig_info.json').write_text(json.dumps(rig_info, indent=2), encoding='utf-8')
    report = dict(profile=profile, motion=str(args.motion), model_sha256=hashlib.sha256(model.read_bytes()).hexdigest(),
        mapping=[list(r) for r in mapping], determinant=mapping.determinant(),
        max_direction_error_degrees=max(direction_errors, default=0)*180/3.141592653589793,
        handedness='L -> left_hand -> pose 11/13/15; R -> right_hand -> pose 12/14/16; no swapping',
        frames=report_frames)
    (outdir/'audit.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    # Camera uses the same anatomical front, not a guessed fixed world side.
    target = arm.matrix_world @ Vector((0,0,1.2))
    front_world = (arm.matrix_world.to_3x3() @ front).normalized()
    cam_data = bpy.data.cameras.new('MediaPipe_VerificationCamera')
    camera = bpy.data.objects.new('MediaPipe_VerificationCamera', cam_data)
    scene.collection.objects.link(camera)
    camera.location = target+front_world*2.8
    camera.rotation_euler = (target-camera.location).to_track_quat('-Z','Y').to_euler()
    cam_data.type='ORTHO'
    cam_data.ortho_scale=1.3
    scene.camera=camera
    scene.render.engine='BLENDER_WORKBENCH'
    scene.render.resolution_x=1000
    scene.render.resolution_y=1000
    scene.render.resolution_percentage=100
    scene.display.shading.light='STUDIO'
    scene.display.shading.color_type='MATERIAL'
    scene.display.shading.show_cavity=True
    bpy.ops.object.select_all(action='DESELECT')
    arm.select_set(True)
    bpy.context.view_layer.objects.active=arm
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type=='VIEW_3D':
                area.spaces.active.region_3d.view_perspective='CAMERA'
                area.spaces.active.shading.type='SOLID'
                area.spaces.active.shading.color_type='MATERIAL'
    scene.frame_set(0)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(args.output.resolve()))
    if args.render:
        for frame in (0,17,34,51,67,180,200,220):
            if frame>scene.frame_end:
                continue
            scene.frame_set(frame)
            scene.render.filepath=str(outdir/f'frame_{frame:03d}_front.png')
            bpy.ops.render.render(write_still=True)
            hand_center = sum((arm.matrix_world @ arm.pose.bones[r['prefix']+'Hand'].head for r in rigs.values()),Vector())/2
            camera.location=hand_center+front_world*2.8
            camera.rotation_euler=(hand_center-camera.location).to_track_quat('-Z','Y').to_euler()
            camera.data.ortho_scale=.65
            scene.render.filepath=str(outdir/f'frame_{frame:03d}_hands.png')
            bpy.ops.render.render(write_still=True)
            camera.location=target+front_world*2.8
            camera.rotation_euler=(target-camera.location).to_track_quat('-Z','Y').to_euler()
            camera.data.ortho_scale=1.3
    print(json.dumps({'output': str(args.output), 'diagnostics': str(outdir),
        'determinant': report['determinant'], 'max_direction_error_degrees': report['max_direction_error_degrees']}), flush=True)


if __name__ == '__main__':
    main()
