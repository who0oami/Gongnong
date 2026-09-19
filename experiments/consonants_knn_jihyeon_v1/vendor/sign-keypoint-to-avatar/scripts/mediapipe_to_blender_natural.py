"""Fresh VRM import -> anatomically assigned MediaPipe hands -> new .blend + audit."""
import argparse
from collections import Counter
from datetime import datetime
import hashlib
import json
from pathlib import Path
import sys
from math import atan2, radians, sin, cos, degrees
from statistics import median

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


def stable_basis(longitudinal, transverse, prev_x=None):
    # An anatomical axis has a meaning. Negating x and z rotates a hand 180 degrees;
    # it is NOT equivalent to negating every component of a quaternion (q == -q).
    # Preserve index->little ordering and let bounded quaternion filtering handle noise.
    result=basis(longitudinal,transverse)
    return result,result.col[0].copy()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--motion', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--profile', type=Path, default=ROOT/'mediapipe-preview/blender_natural_profile.json')
    parser.add_argument('--render', action='store_true')
    parser.add_argument('--render-all', action='store_true')
    args = parser.parse_args(sys.argv[sys.argv.index('--')+1:])
    if args.output.exists():
        raise FileExistsError(args.output)
    profile = json.loads(args.profile.read_text(encoding='utf-8'))
    motion = json.loads(args.motion.read_text(encoding='utf-8'))
    if motion['schema'] != 'mediapipe-holistic-v1' or profile['input_mirrored']:
        raise ValueError('Requires unmirrored MediaPipe input; automatic side swapping is disabled')
    # Above ~32 degrees, Blender's per-component (non-slerp) quaternion keyframe
    # interpolation can collapse toward zero magnitude at the halfway subframe.
    # Keep every per-frame rate cap safely under that regardless of the profile
    # tuned for a given video, so a looser cap for faster signing never silently
    # breaks subframe interpolation.
    for kind in ('arm', 'hand', 'finger'):
        if profile['rotation_filter'][kind+'_degrees_per_frame'] > 32:
            raise ValueError(f'{kind}_degrees_per_frame over 32 risks quaternion subframe collapse')
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
    for obj in bpy.context.scene.objects:
        for modifier in obj.modifiers:
            if modifier.type=='ARMATURE':
                modifier.use_deform_preserve_volume=True
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
    hand_vec = lambda p: mapping @ Vector((p['x'],p['y']*motion['height']/motion['width'],p['z']))
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
    palm_x_previous = {}
    arm_x_previous = {}
    hint_previous = {}
    holds = Counter()
    report_frames = []
    direction_errors = []
    limit_events = Counter()
    pose_previous = {}
    shape_cache = {}

    def shape_parameters(row, side, prev_x):
        group=rigs[side]['spec']['group']
        values=row[group+'_shape']
        if len(values)!=21:
            return None, prev_x
        h=[hand_vec(v) for v in values]
        try:
            palm,prev_x=stable_basis(h[9]-h[0],h[5]-h[17],prev_x)
        except ValueError:
            return None, prev_x
        result={}
        for finger,start in FINGERS.items():
            for j in (1,2,3):
                inc=h[start+j-1]-h[0 if j==1 else start+j-2]
                out=h[start+j]-h[start+j-1]
                if min(inc.length,out.length)<EPS:
                    return None, prev_x
                u=palm.transposed() @ inc.normalized()
                v=palm.transposed() @ out.normalized()
                if finger=='Thumb' and j==1:
                    result[(finger,j)]=tuple(v)
                elif j==1:
                    sign=profile['finger']['palmward_sign'][side]
                    bend=atan2(sign*v.z,(v.x*v.x+v.y*v.y)**.5)-atan2(sign*u.z,(u.x*u.x+u.y*u.y)**.5)
                    spread=atan2(v.x,v.y)-atan2(u.x,u.y)
                    result[(finger,j)]=(bend,atan2(sin(spread),cos(spread)))
                else:
                    result[(finger,j)]=(inc.angle(out),0)
        return result, prev_x

    for side in rigs:
        measurements=[]
        prev_x=None
        for row in motion['frames']:
            result,prev_x=shape_parameters(row,side,prev_x)
            measurements.append(result)
        shape_cache[side]=[]
        for i,own in enumerate(measurements):
            if own is None:
                shape_cache[side].append(None)
                continue
            # Robust scalar median; never smooth coordinates from opposite hands together.
            radius=profile['rotation_filter']['shape_median_radius']
            neighbors=[v for v in measurements[max(0,i-radius):i+radius+1] if v is not None]
            shape_cache[side].append({key:tuple(median(v[key][k] for v in neighbors) for k in range(len(own[key]))) for key in own})

    # Raw landmarks are noisy frame to frame; average them over a short window before
    # any direction/angle math, rather than only damping the resulting bone rotation.
    # That damping alone (previous 'response'<1 plus a low degrees_per_frame cap) was
    # chronically capping arm/wrist rotation on ~15-30% of frames, producing a laggy,
    # rubbery look even during ordinary continuous motion.
    landmark_radius = profile['rotation_filter'].get('landmark_smoothing_radius', 0)

    def smooth_vectors(points):
        # Per-component median, not mean: a plain average still gets dragged around by
        # a source that alternates between two differently-biased detectors frame to
        # frame (e.g. Holistic's own hand landmarks vs. the cropped re-detection), which
        # showed up as several tens of degrees of arm/wrist wobble even after averaging.
        cache = []
        for i in range(len(points)):
            window = [v for v in points[max(0,i-landmark_radius):i+landmark_radius+1] if v is not None]
            if not window:
                cache.append(None)
                continue
            cache.append(tuple(Vector(median(w[k][c] for w in window) for c in range(3)) for k in range(len(window[0]))))
        return cache

    pose_cache = {}
    orient_cache = {}
    for side, rig in rigs.items():
        spec = rig['spec']
        ids, group = spec['pose'], spec['group']
        pose_points, orient_points = [], []
        for row in motion['frames']:
            p = row['pose_world']
            if len(p)==33 and all((row['pose'][i].get('visibility') or 0)>=profile['min_pose_visibility'] for i in ids):
                pose_points.append(tuple(vec(p[i]) for i in ids))
            else:
                pose_points.append(None)
            orientation_raw = row.get(group+'_orientation', [])
            hq = row.get('hand_quality', {}).get(group, {})
            identity_ok = not profile['require_verified_hand_identity'] or hq.get('identity')=='pose_wrist_confirmed'
            if len(orientation_raw)==21 and identity_ok:
                orient_points.append(tuple(hand_vec(orientation_raw[k]) for k in (0,5,9,17)))
            else:
                orient_points.append(None)
        pose_cache[side] = smooth_vectors(pose_points)
        orient_cache[side] = smooth_vectors(orient_points)

    def segment(name, end=None):
        # glTF leaf tails are Blender display axes, not the skinned fingertip axis.
        return head(end)-head(name) if end else head(name)-head(bone[name].parent.name)

    def limited(q, limit):
        q=q.normalized()
        if q.w<0:
            q.negate()
        if q.angle>limit:
            return Quaternion(q.axis,limit)
        return q

    def apply_local(name, q):
        q=q.normalized()
        old=previous.get(name)
        if old is not None:
            if old.dot(q)<0:
                q.negate()
            change=old.rotation_difference(q).angle
            change=min(change,2*3.141592653589793-change)
            kind='hand' if name.endswith('_Hand') else 'arm' if name.endswith(('UpperArm','LowerArm')) else 'finger'
            max_step=radians(profile['rotation_filter'][kind+'_degrees_per_frame'])*30/motion['fps']
            amount=min(profile['rotation_filter']['response'],max_step/max(change,EPS))
            if change>max_step:
                limit_events[name]+=1
            q=old.slerp(q,amount)
        pb=arm.pose.bones[name]
        pb.rotation_mode='QUATERNION'
        pb.rotation_quaternion=q
        bpy.context.view_layer.update()
        return q

    def set_absolute(name, desired):
        pb = arm.pose.bones[name]
        base = pb.parent.matrix @ pb.parent.bone.matrix_local.inverted() @ pb.bone.matrix_local if pb.parent else pb.bone.matrix_local
        local = base.to_3x3().normalized().transposed() @ desired
        q=local.to_quaternion().normalized()
        if name.endswith(('_Hand','_LowerArm')):
            # Swing/twist around the actual wrist->MCP axis, not the display bone Y.
            endpoint=name.replace('Hand','Middle1') if name.endswith('_Hand') else name.replace('LowerArm','Hand')
            axis=rest(name).transposed() @ (head(endpoint)-head(name)).normalized()
            axis.normalize()
            vector=Vector((q.x,q.y,q.z))
            projected=axis*vector.dot(axis)
            twist=Quaternion((q.w,*projected))
            if twist.magnitude<EPS:
                twist=Quaternion()
            twist.normalize()
            swing=q @ twist.conjugated()
            limits=profile['wrist'] if name.endswith('_Hand') else profile['forearm']
            q=limited(swing,radians(limits['max_swing_degrees'])) @ limited(twist,radians(limits['max_twist_degrees']))
        apply_local(name,q)

    def aim(name, end, direction, delta=Matrix.Identity(3)):
        if direction.length < EPS:
            return
        rest_dir = segment(name,end)
        predicted = delta @ rest_dir
        swing = predicted.rotation_difference(direction).to_matrix()
        set_absolute(name, swing @ delta @ rest(name))
        actual = arm.pose.bones[name].matrix.to_3x3() @ (rest(name).transposed() @ rest_dir)
        direction_errors.append(actual.angle(direction))

    # Seed the palm sign-continuity anchor with a majority vote over the first ~20
    # observed frames, not with whichever single frame happens to run first. With no
    # earlier frame to compare against, stable_basis() otherwise keeps whichever sign
    # that very first (still noisy) frame produced for the rest of the whole clip - if
    # that lone pick disagreed with almost every other frame, the hand stayed rotated
    # ~180 degrees off for the entire animation, visible before any real motion starts.
    def bootstrap_x(side):
        ref, votes, checked = None, 0, 0
        for cached in orient_cache[side]:
            if cached is None:
                continue
            o0, o5, o9, o17 = cached
            longitudinal = o9 - o0
            if longitudinal.length < EPS:
                continue
            transverse = o5 - o17
            x = transverse - longitudinal.normalized() * transverse.dot(longitudinal.normalized())
            if x.length < EPS:
                continue
            x.normalize()
            if ref is None:
                ref = x
            votes += 1 if x.dot(ref) >= 0 else -1
            checked += 1
            if checked >= 20:
                break
        return ref if ref is None or votes >= 0 else -ref

    for side, rig in rigs.items():
        palm_x_previous[side] = bootstrap_x(side) or rig['palm'].col[0].copy()
        rd0 = segment(rig['prefix']+'LowerArm', rig['prefix']+'Hand')
        arm_x_previous[side] = basis(rd0, rig['palm'].col[0]).col[0]

    for row_index,row in enumerate(motion['frames']):
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
            h = [hand_vec(v) for v in row[spec['group']+'_shape']] if valid else []
            orientation=[hand_vec(v) for v in row.get(spec['group']+'_orientation',[])]
            valid=valid and len(orientation)==21
            parameters=shape_cache[side][row_index]
            valid=valid and parameters is not None
            palm_delta = None
            palm_basis = None
            if valid:
                cached_orient = orient_cache[side][row_index]
                o0,o5,o9,o17 = cached_orient if cached_orient else (orientation[0],orientation[5],orientation[9],orientation[17])
            if h and valid:
                length = (h[9]-h[0]).length
                if length<EPS or any((h[i+1]-h[i]).length < length*profile['finger_segment_ratio_min']
                    for start in FINGERS.values() for i in range(start,start+3)):
                    valid = False
                else:
                    try:
                        palm_basis,palm_x=stable_basis(o9-o0, o5-o17, palm_x_previous.get(side))
                        palm_x_previous[side] = palm_x
                        palm_delta = palm_basis @ rig['palm'].transposed()
                    except ValueError:
                        valid = False
            if visible:
                cached_pose = pose_cache[side][row_index]
                a,b,c = cached_pose if cached_pose else tuple(vec(p[i]) for i in ids)
                aim(prefix+'UpperArm', prefix+'LowerArm', b-a)
                # Fix forearm roll with a projected palm transverse axis. Shortest-arc
                # alignment of nearly opposite vectors previously caused 180-degree flips.
                rd=segment(prefix+'LowerArm',prefix+'Hand')
                hint=rig['palm'].col[0]
                if valid:
                    current_hint = palm_delta @ hint
                    hint_previous[side] = current_hint
                else:
                    # No hand data to derive a roll reference from: hold the last
                    # confidently-known one instead of re-deriving it from the upper
                    # arm's own just-applied matrix each frame, which fed back into
                    # itself and made the forearm roll flip back and forth every
                    # frame for the whole gap (frames 35-55, 139-159, ... here).
                    current_hint = hint_previous.get(side,
                        arm.pose.bones[prefix+'UpperArm'].matrix.to_3x3() @ rest(prefix+'UpperArm').transposed() @ hint)
                try:
                    # current_hint (from the hand) drifts close to parallel with the
                    # forearm axis (c-b) whenever the wrist points nearly straight at or
                    # away from the elbow; stabilize the same way as the palm basis so
                    # the whole forearm doesn't roll 180 degrees back and forth there.
                    forearm_basis,arm_x=stable_basis(c-b,current_hint,arm_x_previous.get(side))
                    arm_x_previous[side]=arm_x
                    desired=forearm_basis @ basis(rd,hint).transposed() @ rest(prefix+'LowerArm')
                    set_absolute(prefix+'LowerArm',desired)
                except ValueError:
                    apply_local(prefix+'LowerArm',previous.get(prefix+'LowerArm',Quaternion()))
                for n in (prefix+'UpperArm',prefix+'LowerArm'):
                    pose_previous[n]=arm.pose.bones[n].rotation_quaternion.copy()
            else:
                for n in (prefix+'UpperArm',prefix+'LowerArm'):
                    apply_local(n,pose_previous.get(n,Quaternion()))
            if visible and valid:
                set_absolute(prefix+'Hand', palm_delta @ rest(prefix+'Hand'))
                # Thumb: full 3D opposition. Other fingers: MCP flex/splay + PIP/DIP hinges.
                for finger, start in FINGERS.items():
                    for j in (1,2,3):
                        name = prefix+finger+str(j)
                        end = prefix+finger+str(j+1) if j<3 else None
                        if finger == 'Thumb':
                            if j==1:
                                # CMC cone follows thumb opposition without introducing roll.
                                observed=palm_basis @ Vector(parameters[(finger,j)])
                                pb=arm.pose.bones[name]
                                base=pb.parent.matrix @ pb.parent.bone.matrix_local.inverted() @ pb.bone.matrix_local
                                target_local=base.to_3x3().normalized().transposed() @ observed
                                rest_local=rest(name).transposed() @ segment(name,end)
                                q=limited(rest_local.rotation_difference(target_local),radians(profile['thumb']['cmc_max_degrees']))
                            else:
                                incoming=h[j]-h[j-1]
                                outgoing=h[j+1]-h[j]
                                bend=min(parameters[(finger,j)][0],radians(profile['thumb']['mcp_max_degrees' if j==2 else 'ip_max_degrees']))
                                # Thumb hinges close across the palm toward the index base.
                                # Using the other fingers' palmward axis made the thumb stick
                                # out sideways or dive under the fist.
                                across_palm=head(prefix+'Index1')-head(prefix+'Thumb2')
                                axis=segment(name,end).cross(across_palm).normalized()
                                q=Quaternion(rest(name).transposed() @ axis,bend)
                            apply_local(name,q)
                            continue
                        finger_profile = profile['finger']
                        palmward_sign = finger_profile['palmward_sign'][side]
                        # bend/spread come from the temporally median-smoothed shape_cache,
                        # not recomputed from this single frame's (noisier) landmarks.
                        bend,spread=parameters[(finger,j)]
                        spread=max(-radians(finger_profile['spread_max_degrees']),min(radians(finger_profile['spread_max_degrees']),spread))
                        limit_key='mcp_max_degrees' if j==1 else 'pip_dip_max_degrees' if j==2 else 'dip_max_degrees'
                        bend = max(0,min(radians(finger_profile[limit_key]),bend))
                        rest_dir = segment(name,end)
                        normal = rig['palm'].col[2]
                        palmward = normal*palmward_sign
                        axis = rest_dir.cross(palmward).normalized()
                        # Hinges constrain PIP/DIP roll; MCP additionally preserves signed splay.
                        qflex = Quaternion(rest(name).transposed() @ axis, bend)
                        qsplay = Quaternion(rest(name).transposed() @ normal, -spread)
                        apply_local(name,qsplay @ qflex)
                holds[side] = 0
                state['applied'] = 'observed'
            else:
                holds[side] += 1
                hand_names = [prefix+'Hand']+[prefix+f+str(j) for f in FINGERS for j in (1,2,3)]
                # Hold the last confidently observed hand shape for the whole gap, however
                # long. Snapping to the rig's rest pose after max_hold_frames (previously
                # gated on `visible`, so even a single dropped body-pose frame triggered it)
                # produced a hooked/clawed look mid-gesture whenever the arm kept moving on
                # stale pose data while the fingers slammed to bind pose.
                held = all(n in previous for n in hand_names)
                for n in hand_names:
                    apply_local(n,previous[n] if held else Quaternion())
                state['applied'] = 'held_gap' if held else 'missing_no_prior_neutral'
                if holds[side] > profile['max_hold_frames']:
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
    report['rotation_rate_limit_events']=dict(limit_events)
    report['leaf_axis_policy']='terminal segment continues parent->joint direction; imported display tail ignored'
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
                area.spaces.active.overlay.show_overlays=False
    scene.frame_set(0)
    # audit_hand_animation.py reads this back so its QA limits always match the
    # profile that actually produced the file, instead of separately hardcoded
    # numbers going stale whenever a profile (e.g. for a different video) changes.
    scene['ksl_retarget_profile'] = json.dumps(profile)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(args.output.resolve()))
    if args.render:
        for frame in (0,17,21,34,51,67,180,200,203,220,221):
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
    if args.render_all:
        sequence=outdir/'sequence'
        sequence.mkdir()
        scene.render.resolution_x=640
        scene.render.resolution_y=640
        for frame in range(scene.frame_start,scene.frame_end+1):
            scene.frame_set(frame)
            scene.render.filepath=str(sequence/f'{frame:04d}.png')
            bpy.ops.render.render(write_still=True)
    print(json.dumps({'output': str(args.output), 'diagnostics': str(outdir),
        'determinant': report['determinant'], 'max_direction_error_degrees': report['max_direction_error_degrees']}), flush=True)


if __name__ == '__main__':
    main()

