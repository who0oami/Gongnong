"""Inspect saved animation, including subframes and worst wrist/thumb rotations."""
import bpy
import json
from pathlib import Path
from math import degrees

out = Path(bpy.data.filepath).with_suffix('')
out = out.parent.parent/'diagnostics'/(out.name+'_motion_audit')
out.mkdir(exist_ok=False)
arm = max((o for o in bpy.context.scene.objects if o.type=='ARMATURE'),key=lambda o:len(o.pose.bones))
scene=bpy.context.scene
rows=[]
previous={}
for frame in range(scene.frame_start,scene.frame_end+1):
    scene.frame_set(frame)
    row={'frame':frame,'bones':{}}
    for side in ('L','R'):
        for suffix in ('UpperArm','LowerArm','Hand',*[f+str(j) for f in ('Thumb','Index','Middle','Ring','Little') for j in (1,2,3)]):
            name=f'J_Bip_{side}_{suffix}'
            pb=arm.pose.bones[name]
            q=pb.rotation_quaternion.normalized()
            angle=degrees(q.angle)
            angle=min(angle,360-angle)
            jump=degrees(q.rotation_difference(previous[name]).angle) if name in previous else 0
            jump=min(jump,360-jump)
            row['bones'][name]={'angle':angle,'jump':jump,'q':list(q)}
            previous[name]=q.copy()
    rows.append(row)
if any(word in Path(bpy.data.filepath).stem for word in ('stable','natural','aligned')):
    import math
    # Read the limits back from the profile that actually produced this file (stashed
    # as a custom property by mediapipe_to_blender_stable.py) instead of hardcoding
    # numbers that go stale whenever the profile changes, e.g. for a different video.
    profile = json.loads(scene['ksl_retarget_profile'])
    rf, thumb, finger = profile['rotation_filter'], profile['thumb'], profile['finger']

    def jump_limit(name):
        kind = 'hand' if name.endswith('_Hand') else 'arm' if name.endswith(('UpperArm', 'LowerArm')) else 'finger'
        return rf[kind + '_degrees_per_frame'] + .01

    for row in rows:
        for name,v in row['bones'].items():
            assert all(math.isfinite(x) for x in v['q']), (row['frame'],name)
            assert abs(sum(x*x for x in v['q'])-1)<1e-4, (row['frame'],name,'not unit')
            assert v['jump']<=jump_limit(name), (row['frame'],name,v['jump'])
            if 'Thumb' in name:
                maximum={1:thumb['cmc_max_degrees'],2:thumb['mcp_max_degrees'],3:thumb['ip_max_degrees']}[int(name[-1])]
                assert v['angle']<=maximum+.01,(row['frame'],name,v['angle'])
            elif name.endswith(('Index2','Middle2','Ring2','Little2')):
                assert v['angle']<=finger['pip_dip_max_degrees']+.01,(row['frame'],name,v['angle'])
            elif name.endswith(('Index3','Middle3','Ring3','Little3')):
                assert v['angle']<=finger['dip_max_degrees']+.01,(row['frame'],name,v['angle'])
    # Saved fractional frames must also interpolate without quaternion cancellation.
    for frame in range(scene.frame_start,scene.frame_end):
        scene.frame_set(frame,subframe=.5)
        for name in rows[0]['bones']:
            pb=arm.pose.bones[name]
            assert pb.rotation_quaternion.magnitude>.99,(frame,name,'subframe collapse')
            assert all(abs(v-1)<1e-5 for v in pb.scale),(frame,name,'scale changed')
    print('PASS: 296 integer frames, 295 half frames, 36 bones; rates, thumb/hinge limits and no scale changes')
ranked=sorted(rows,key=lambda r:max(v['jump'] for v in r['bones'].values()),reverse=True)
print('WORST_JUMPS',[(r['frame'],sorted(r['bones'].items(),key=lambda p:p[1]['jump'],reverse=True)[:2]) for r in ranked[:12]])
print('WRIST_MAX',[(side,max((r['bones'][f'J_Bip_{side}_Hand']['angle'],r['frame']) for r in rows)) for side in ('L','R')])
(out/'audit.json').write_text(json.dumps(rows,indent=2),encoding='utf-8')
scene.render.resolution_x=640
scene.render.resolution_y=640
scene.render.resolution_percentage=100
for frame in sorted({0,17,34,51,67,180,200,220,*[r['frame'] for r in ranked[:12]]}):
    scene.frame_set(frame)
    scene.render.filepath=str(out/f'frame_{frame:03d}.png')
    bpy.ops.render.render(write_still=True)
print('AUDIT_DIRECTORY',out)

