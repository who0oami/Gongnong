"""Blender pipeline: pinned baseline -> pinned KNN -> jihyeon chain hand bridge."""
import argparse
import ast
import json
import math
from pathlib import Path
import runpy
import sys

import bpy
from mathutils import Matrix, Quaternion, Vector

ROOT = Path(__file__).resolve().parent
VENDOR = ROOT/'vendor/sign-keypoint-to-avatar'
FINGERS = {'Thumb': 1, 'Index': 5, 'Middle': 9, 'Ring': 13, 'Little': 17}
NAMES = [f'J_Bip_{s}_{f}{j}' for s in ('L', 'R') for f in FINGERS for j in (1, 2, 3)]


def script(path, args):
    old = sys.argv
    try:
        sys.argv = [str(path), '--', *map(str, args)]
        runpy.run_path(str(path), run_name='__main__')
    finally:
        sys.argv = old


def primary_arm():
    return max((o for o in bpy.context.scene.objects if o.type == 'ARMATURE'),
               key=lambda a: sum(m.type == 'ARMATURE' and m.object == a for o in bpy.context.scene.objects for m in o.modifiers))


def basis(y, x):
    if y.length < 1e-8:
        return None
    y = y.normalized()
    x = x - y * x.dot(y)
    if x.length < 1e-8:
        return None
    x.normalize()
    return Matrix((x, y, x.cross(y).normalized())).transposed()


def jihyeon_targets(arm, motion):
    """Execute the exact upstream chain solver with MediaPipe palm-local inputs.

    The adapter preserves anatomical identity and does not synthesize BODY_25.
    glTF terminal tails are display axes: extrapolate the last real segment.
    """
    source = ROOT/'vendor/jihyeon/retarget_avatar_real_v6_3.py'
    tree = ast.parse(source.read_text(encoding='utf-8-sig'))
    wanted = {'make_semantic_basis', 'finger_minimum_swing', 'build_chain_finger_raw_rotations'}
    definitions = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in wanted]
    assert {n.name for n in definitions} == wanted
    rest = {b.name: b.matrix_local.to_3x3().normalized() for b in arm.data.bones}
    heads = {b.name: b.head_local.copy() for b in arm.data.bones}
    head = lambda n: heads[n].copy()
    def tail(n):
        return head(n[:-1]+str(int(n[-1])+1)) if n[-1] != '3' else head(n)+(head(n)-head(n[:-1]+'2'))
    specs, points, normals, rest_points, valid = {}, {}, {}, {}, {}
    for side, group in [('L', 'left_hand'), ('R', 'right_hand')]:
        prefix = f'J_Bip_{side}_'
        wrist = head(prefix+'Hand')
        palm = basis(head(prefix+'Middle1')-wrist, head(prefix+'Index1')-head(prefix+'Little1'))
        if palm is None:
            raise ValueError('Degenerate rig palm')
        rest_points[side] = {'wrist': wrist, 'middle': head(prefix+'Middle1')}
        normals[side] = palm.col[2].copy()
        specs[side] = [(prefix+f+str(j), group, start+j-1, start+j) for f, start in FINGERS.items() for j in (1,2,3)]
        points[group], valid[side] = [], []
        for row in motion['frames']:
            raw = row.get(group+'_shape', [])
            quality = row.get('hand_quality', {}).get(group, {})
            good = len(raw) == 21 and quality.get('identity') == 'pose_wrist_confirmed'
            mapped = None
            if good:
                h = [Vector((p['x'], p['y']*motion['height']/motion['width'], p['z'])) for p in raw]
                source_palm = basis(h[9]-h[0], h[5]-h[17])
                length = (h[9]-h[0]).length
                good = source_palm is not None and all(math.isfinite(c) for v in h for c in v)
                good = good and all((h[i+1]-h[i]).length >= length*.04 for start in FINGERS.values() for i in range(start,start+3))
                if good:
                    rotation = palm @ source_palm.transposed()
                    mapped = [wrist + rotation @ (v-h[0]) for v in h]
            points[group].append(mapped)
            valid[side].append(bool(good))
    namespace = {
        'math': math, 'Matrix': Matrix, 'Vector': Vector, 'Quaternion': Quaternion, 'EPS': 1e-8,
        'frames': motion['frames'], 'FINGER_SPECS': specs,
        'SIDE_INFO': {'L': {'group': 'left_hand'}, 'R': {'group': 'right_hand'}},
        'TARGET_REST_POINTS': rest_points, 'TARGET_PALM_NORMAL': normals,
        'rig_head': head, 'rig_tail': tail, 'get_bone_rest_rotation': lambda n: rest[n],
        'mapped_point': lambda i,g,k: points[g][i][k] if points[g][i] is not None else None,
        'source_palm_normal': lambda i,s: normals[s] if valid[s][i] else None,
    }
    exec(compile(ast.Module(body=definitions, type_ignores=[]), str(source), 'exec'), namespace)
    absolute = namespace['build_chain_finger_raw_rotations']()
    local = {}
    for name, rotations in absolute.items():
        parent = arm.data.bones[name].parent.name
        local[name] = []
        for i, desired in enumerate(rotations):
            if desired is None:
                local[name].append(None)
                continue
            parent_rotation = absolute[parent][i] if parent in absolute else rest[parent]
            inherited = parent_rotation @ rest[parent].transposed() @ rest[name]
            local[name].append((inherited.transposed() @ desired).to_quaternion().normalized())
    return local, valid, absolute, rest, tail


def snapshot(arm):
    scene = bpy.context.scene
    result = {}
    for frame in range(scene.frame_start, scene.frame_end+1):
        scene.frame_set(frame)
        result[frame] = {b.name: b.matrix_basis.copy() for b in arm.pose.bones}
    return result


def angle(a, b):
    d = a.rotation_difference(b).angle
    return math.degrees(min(d, 2*math.pi-d))


def measurements(arm, absolute, rest, tail):
    scene = bpy.context.scene
    errors, jumps, prev = [], [], {}
    for frame in range(scene.frame_start, scene.frame_end+1):
        scene.frame_set(frame)
        for name in NAMES:
            q = arm.pose.bones[name].rotation_quaternion.copy()
            if name in prev:
                jumps.append(angle(prev[name], q))
            prev[name] = q
            target = absolute[name][frame]
            if target is not None:
                hand = name[:8]+'Hand'
                palm_delta_inverse = rest[hand] @ arm.pose.bones[hand].matrix.to_3x3().normalized().transposed()
                direction = rest[name].transposed() @ (tail(name)-arm.data.bones[name].head_local)
                actual = palm_delta_inverse @ arm.pose.bones[name].matrix.to_3x3().normalized() @ direction
                expected = target @ direction
                errors.append(math.degrees(actual.angle(expected)))
    return {'mean_source_segment_error_deg': sum(errors)/max(1,len(errors)), 'max_frame_rotation_change_deg': max(jumps,default=0), 'mean_frame_rotation_change_deg': sum(jumps)/max(1,len(jumps)), 'observed_segments':len(errors)}


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--word', required=True)
    p.add_argument('--strength', type=float, default=.45)
    p.add_argument('--resume-intermediates', action='store_true', help='Reuse this experiment baseline/KNN after an interrupted run')
    args = p.parse_args(sys.argv[sys.argv.index('--')+1:])
    if not 0 <= args.strength <= 1:
        raise ValueError('Strength out of range')
    folder = ROOT/'runs'/args.word
    baseline, knn, combined = [folder/(v+'.blend') for v in ('baseline', 'knn', 'knn_jihyeon_v4')]
    if not baseline.exists():
        baseline = folder/(args.word+'_baseline.blend')
    report_path = folder/'result_v4.json'
    if combined.exists() or report_path.exists() or (not args.resume_intermediates and any(path.exists() for path in (baseline, knn))):
        raise FileExistsError('Existing result; use a new run folder')
    motion = json.loads((folder/'smoothed.json').read_text(encoding='utf-8'))
    if [round(r['time']*motion['fps']) for r in motion['frames']] != list(range(len(motion['frames']))):
        raise ValueError('This adapter requires contiguous frames beginning at zero')
    if baseline.exists():
        bpy.ops.wm.open_mainfile(filepath=str(baseline))
    else:
        script(VENDOR/'scripts/mediapipe_to_blender_aligned.py', ['--motion', folder/'smoothed.json', '--profile', ROOT/'profile.json', '--output', baseline])
    arm = primary_arm()
    original = snapshot(arm)
    targets, valid, absolute, rest, tail = jihyeon_targets(arm, motion)
    metrics = {'baseline': measurements(arm, absolute, rest, tail)}
    if knn.exists():
        if not (folder/'knn_report.json').exists():
            raise ValueError('KNN intermediate has no completion report')
        bpy.ops.wm.open_mainfile(filepath=str(knn))
    else:
    script(VENDOR/'scripts/correct_hand_shape_prior.py', ['--input', baseline, '--output', knn, '--prior', ROOT.parents[1]/'word2153/extractor/hand_shape_prior.npz', '--report', folder/'knn_report.json'])
    arm = primary_arm()
    metrics['knn'] = measurements(arm, absolute, rest, tail)
    scene = bpy.context.scene
    currents = {}
    for frame in range(scene.frame_start, scene.frame_end+1):
        scene.frame_set(frame)
        currents[frame] = {n: arm.pose.bones[n].rotation_quaternion.copy() for n in NAMES}
    # Distance to a missing observation / clip boundary allows the correction
    # to fade to identity without filling missing tracking with invented poses.
    radii = {}
    for side in ('L','R'):
        distances = []
        streak = 0
        for good in valid[side]:
            streak = streak + 1 if good else 0
            distances.append(max(0,streak-1))
        streak = 0
        for i in range(len(distances)-1,-1,-1):
            streak = streak + 1 if valid[side][i] else 0
            distances[i] = min(distances[i],max(0,streak-1))
        radii[side] = [min(25.0, 4.0*d) for d in distances]
    previous, previous_delta, rows = {}, {}, []
    rejected_knn = 0
    rate_limited = 0
    for frame, poses in currents.items():
        scene.frame_set(frame)
        row = {'frame':frame,'sides':{}}
        for side in ('L','R'):
            # No long fill: skip missing observations and fade at validity boundaries.
            trust = sum(valid[side][max(0,frame-2):min(len(currents),frame+3)])/len(valid[side][max(0,frame-2):min(len(currents),frame+3)])
            alpha = args.strength*trust if valid[side][frame] else 0.0
            row['sides'][side] = {'valid': valid[side][frame], 'alpha':alpha}
            for n in (n for n in NAMES if n.startswith(f'J_Bip_{side}_')):
                q = poses[n].copy()
                target = targets[n][frame]
                baseline_q = original[frame][n].to_quaternion().normalized()
                # A corpus outlier is not necessarily a bad sign pose. Keep
                # baseline when KNN moves away from a verified observation;
                # without an observation, fade back to baseline below.
                if target is None or angle(q,target)>angle(baseline_q,target)+2.0:
                    q = baseline_q
                    rejected_knn += 1
                correction = Quaternion()
                if alpha and target is not None:
                    # Single-view depth can flip a segment. Bound the extra
                    # correction relative to KNN, never force a far-away pose.
                    delta = angle(q, target)
                    desired = q.slerp(target, min(alpha, radii[side][frame]/max(delta, 1e-8)))
                    correction = q.rotation_difference(desired).normalized()
                    old = previous_delta.get(n, Quaternion())
                    change = angle(old, correction)
                    correction = old.slerp(correction, min(1.0,4.0/max(change,1e-8)))
                    magnitude = angle(Quaternion(),correction)
                    correction = Quaternion().slerp(correction,min(1.0,radii[side][frame]/max(magnitude,1e-8)))
                previous_delta[n] = correction.copy()
                q = (q @ correction).normalized()
                if n in previous:
                    change = angle(previous[n], q)
                    limit = 16.0 * 30.0 / motion['fps']
                    if change > limit:
                        q = previous[n].slerp(q, limit/change).normalized()
                        rate_limited += 1
                if n in previous and previous[n].dot(q) < 0:
                    q.negate()
                arm.pose.bones[n].rotation_quaternion = q
                arm.pose.bones[n].keyframe_insert(data_path='rotation_quaternion', frame=frame)
                previous[n] = q.copy()
        rows.append(row)
    scene.frame_set(0)
    bpy.ops.wm.save_as_mainfile(filepath=str(combined))
    # Reopen saved variants to validate persistence and compare against baseline.
    checks = {}
    for variant,path in [('knn',knn),('knn_jihyeon',combined)]:
        bpy.ops.wm.open_mainfile(filepath=str(path))
        arm = primary_arm()
        scene = bpy.context.scene
        protected_error = 0.0
        min_norm = 1.0
        for frame, bones in original.items():
            scene.frame_set(frame)
            for n,matrix in bones.items():
                if n not in NAMES:
                    current = arm.pose.bones[n].matrix_basis
                    protected_error = max(protected_error,max(abs(current[r][c]-matrix[r][c]) for r in range(4) for c in range(4)))
            if frame < scene.frame_end:
                scene.frame_set(frame, subframe=.5)
                for n in NAMES:
                    q = arm.pose.bones[n].rotation_quaternion
                    assert all(math.isfinite(v) for v in q), (frame,n)
                    min_norm = min(min_norm,q.magnitude)
        assert protected_error < 1e-6, protected_error
        assert min_norm > .9, min_norm
        checks[variant] = {'protected_bone_max_error':protected_error,'min_half_frame_quaternion_norm':min_norm,'status':'PASS'}
    metrics['knn_jihyeon'] = measurements(arm, absolute, rest, tail)
    assert metrics['knn_jihyeon']['max_frame_rotation_change_deg'] <= 16.0*30.0/motion['fps']+.01
    report = {'word':args.word,'frames':len(currents),'fps':motion['fps'],'strength':args.strength,
              'max_extra_correction_deg':25.0, 'correction_step_limit_deg':4.0, 'output_files':{'baseline':baseline.name,'knn':knn.name,'knn_jihyeon':combined.name},
              'output_rate_limit_deg_per_frame_at_30fps':16.0,'knn_rejected_joint_frames':rejected_knn,'rate_limited_joint_frames':rate_limited,
              'valid_frames':{s:sum(v) for s,v in valid.items()},'metrics':metrics,'verification':checks,
              'sources':json.loads((ROOT/'sources.json').read_text()),'per_frame':rows,
              'metric_limit':'Segment error is consistency with detected landmarks, not sign correctness. Missing observations target baseline; rate limiting can briefly ease back to it.'}
    with report_path.open('x',encoding='utf-8') as f:
        json.dump(report,f,ensure_ascii=False,indent=2)
    print('CLIP_COMPLETE',args.word,flush=True)


if __name__ == '__main__':
    main()

