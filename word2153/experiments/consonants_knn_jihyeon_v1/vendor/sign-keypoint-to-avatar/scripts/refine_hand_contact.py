"""Offline symmetric smoothing and two-arm IK contact correction on a new copy."""
import argparse
import json
from math import acos, degrees
from pathlib import Path
import sys
import bpy
from mathutils import Vector, Quaternion

args_parser=argparse.ArgumentParser()
args_parser.add_argument('--output',type=Path,required=True)
args=args_parser.parse_args(sys.argv[sys.argv.index('--')+1:])
args.output=args.output.resolve()
if args.output.exists(): raise FileExistsError(args.output)
scene=bpy.context.scene
arm=max((o for o in scene.objects if o.type=='ARMATURE'),key=lambda a:sum(m.type=='ARMATURE' and m.object==a for o in scene.objects for m in o.modifiers))
names=[n for n in arm.pose.bones.keys() if n.startswith(('J_Bip_L_','J_Bip_R_')) and any(s in n for s in ('UpperArm','LowerArm','Hand','Thumb','Index','Middle','Ring','Little')) and not n.endswith('_end')]
frames=list(range(scene.frame_start,scene.frame_end+1))
raw=[]
for f in frames:
    scene.frame_set(f)
    raw.append({n:arm.pose.bones[n].rotation_quaternion.copy() for n in names})

def apply_world(n,desired):
    pb=arm.pose.bones[n]
    base=pb.parent.matrix @ pb.parent.bone.matrix_local.inverted() @ pb.bone.matrix_local
    pb.rotation_quaternion=(base.to_3x3().normalized().transposed() @ desired).to_quaternion()
    bpy.context.view_layer.update()

def move_wrist(side,target):
    pre='J_Bip_'+side+'_'
    ua,la,hand=(arm.pose.bones[pre+n] for n in ('UpperArm','LowerArm','Hand'))
    a,b,c=ua.head.copy(),la.head.copy(),hand.head.copy()
    hand_rotation=hand.matrix.to_3x3().normalized()
    l1,l2=(b-a).length,(c-b).length
    direction=target-a
    distance=max(abs(l1-l2)+.0001,min(direction.length,l1+l2-.0001))
    axis=direction.normalized()
    bend=b-a-axis*(b-a).dot(axis)
    if bend.length<1e-6:
        bend=axis.cross(Vector((0,0,1)))
    bend.normalize()
    along=(l1*l1+distance*distance-l2*l2)/(2*distance)
    elbow=a+axis*along+bend*max(0,l1*l1-along*along)**.5
    swing=(b-a).rotation_difference(elbow-a).to_matrix()
    apply_world(ua.name,swing @ ua.matrix.to_3x3().normalized())
    swing=(hand.head-la.head).rotation_difference(a+axis*distance-la.head).to_matrix()
    apply_world(la.name,swing @ la.matrix.to_3x3().normalized())
    apply_world(hand.name,hand_rotation)

def closest(a,b,c,d):
    u,v,w=b-a,d-c,a-c
    aa,bb,cc,dd,ee=u.dot(u),u.dot(v),v.dot(v),u.dot(w),v.dot(w)
    denominator=aa*cc-bb*bb
    s=max(0,min(1,(bb*ee-cc*dd)/denominator)) if denominator>1e-12 else 0
    t=(bb*s+ee)/max(cc,1e-12)
    if t<0: t=0; s=max(0,min(1,-dd/max(aa,1e-12)))
    elif t>1: t=1; s=max(0,min(1,(bb-dd)/max(aa,1e-12)))
    return a+u*s,c+v*t

def capsules(side):
    pre='J_Bip_'+side+'_'
    pb=arm.pose.bones
    wrist=pb[pre+'Hand'].head.copy()
    result=[]
    # Geometry scales with this model's palm width; no per-word coordinates.
    width=(pb[pre+'Index1'].head-pb[pre+'Little1'].head).length
    for finger in ('Index','Middle','Ring','Little'):
        result.append((wrist,pb[pre+finger+'1'].head.copy(),width*.26))
    for finger in ('Thumb','Index','Middle','Ring','Little'):
        for j in (1,2,3):
            p=pb[pre+finger+str(j)]
            end=pb[pre+finger+str(j+1)].head.copy() if j<3 else p.head+p.matrix.to_3x3() @ (p.bone.matrix_local.to_3x3().transposed() @ (p.bone.head_local-p.parent.bone.head_local))*.8
            result.append((p.head.copy(),end,width*(.15 if finger=='Thumb' else .125)))
    return result

def penetration():
    deepest=0; normal=Vector((0,0,0))
    for a,b,r in capsules('L'):
        for c,d,s in capsules('R'):
            p,q=closest(a,b,c,d)
            delta=p-q
            depth=r+s+.001-delta.length
            if depth>deepest:
                deepest=depth
                normal=delta.normalized() if delta.length>1e-6 else (arm.pose.bones['J_Bip_L_Hand'].head-arm.pose.bones['J_Bip_R_Hand'].head).normalized()
    return deepest,normal

smoothed=[]
weights=(1,6,15,20,15,6,1)
for i in range(len(raw)):
    pose={}
    for n in names:
        ref=raw[i][n]
        accum=Vector((0,0,0,0))
        for k,w in enumerate(weights):
            q=raw[max(0,min(len(raw)-1,i+k-3))][n].copy()
            if q.dot(ref)<0:q.negate()
            accum+=Vector(q)*w
        pose[n]=Quaternion(accum).normalized()
    # A weak DIP/PIP coupling suppresses isolated tip spikes while retaining curls.
    for side in ('L','R'):
        for finger in ('Index','Middle','Ring','Little'):
            pre='J_Bip_'+side+'_'+finger
            q=pose[pre+'3']; pip=pose[pre+'2']
            if q.w<0:q.negate()
            angle=.8*q.angle+.2*min(1.396,.65*min(pip.angle,6.283185-pip.angle))
            pose[pre+'3']=Quaternion(q.axis,angle)
    smoothed.append(pose)

def set_pose(i):
    scene.frame_set(frames[i])
    for n,q in smoothed[i].items():
        arm.pose.bones[n].rotation_mode='QUATERNION'
        arm.pose.bones[n].rotation_quaternion=q
    bpy.context.view_layer.update()

# First solve individual poses, then smooth the correction trajectory symmetrically.
offsets=[]; before=[]
for i in range(len(frames)):
    set_pose(i)
    start={s:arm.pose.bones['J_Bip_'+s+'_Hand'].head.copy() for s in ('L','R')}
    before.append(penetration()[0])
    for iteration in range(24):
        depth,normal=penetration()
        if depth<.0003:break
        for side,sign in (('L',1),('R',-1)):
            move_wrist(side,arm.pose.bones['J_Bip_'+side+'_Hand'].head+normal*sign*min(.008,depth*.55))
    offsets.append({s:arm.pose.bones['J_Bip_'+s+'_Hand'].head-start[s] for s in start})
    if i%50==0: print('CONTACT_PASS',i,flush=True)

report=[]; last={}
for i,f in enumerate(frames):
    set_pose(i)
    for s in ('L','R'):
        offset=sum((offsets[max(0,min(len(frames)-1,i+k-3))][s]*w for k,w in enumerate(weights)),Vector())/sum(weights)
        move_wrist(s,arm.pose.bones['J_Bip_'+s+'_Hand'].head+offset)
    for iteration in range(16):
        depth,normal=penetration()
        if depth<.0003:break
        for s,sign in (('L',1),('R',-1)):
            move_wrist(s,arm.pose.bones['J_Bip_'+s+'_Hand'].head+normal*sign*min(.006,depth*.55))
    jumps=[]
    for n in names:
        p=arm.pose.bones[n]
        q=p.rotation_quaternion.normalized()
        if n in last:
            if q.dot(last[n])<0:q.negate()
            jumps.append(degrees(last[n].rotation_difference(q).angle))
        p.rotation_quaternion=q
        p.keyframe_insert(data_path='rotation_quaternion',frame=f)
        last[n]=q.copy()
    report.append({'frame':f,'proxy_penetration_before_m':before[i],'proxy_penetration_after_m':penetration()[0],'max_rotation_step_degrees':max(jumps,default=0)})
scene.frame_set(0)
scene['hand_contact_method']='7-frame symmetric quaternion smoothing; weak DIP coupling; scaled hand capsules and two-bone arm IK. Proxy clearance is not exact mesh clearance.'
args.output.parent.mkdir(parents=True,exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=str(args.output.resolve()))
directory=args.output.parent.parent/'diagnostics'/args.output.stem
directory.mkdir(exist_ok=False)
(directory/'contact_audit.json').write_text(json.dumps(report,indent=2),encoding='utf8')
# Preserve the colored file; workbench is only used for fast diagnostic geometry renders.
scene.render.engine='BLENDER_WORKBENCH'
scene.render.resolution_x=800;scene.render.resolution_y=800
camera=scene.camera
view=(camera.location-Vector((0,0,1.2))).normalized()
for f in (0,17,34,51,67,180,190,200,203,210,220):
    scene.frame_set(f)
    center=arm.matrix_world @ ((arm.pose.bones['J_Bip_L_Hand'].head+arm.pose.bones['J_Bip_R_Hand'].head)/2)
    camera.location=center+view*2.8
    camera.rotation_euler=(center-camera.location).to_track_quat('-Z','Y').to_euler()
    camera.data.ortho_scale=.65
    scene.render.filepath=str(directory/f'frame_{f:03d}.png')
    bpy.ops.render.render(write_still=True)
print('CONTACT_RESULT',json.dumps({'max_before':max(before),'max_after':max(r['proxy_penetration_after_m'] for r in report),'max_step':max(r['max_rotation_step_degrees'] for r in report)}),flush=True)

