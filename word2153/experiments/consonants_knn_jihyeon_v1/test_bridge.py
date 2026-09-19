"""Blender regression checks for the palm-local jihyeon adapter."""
import importlib.util
import json
from pathlib import Path
import bpy
from mathutils import Quaternion

ROOT=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('bridge',ROOT/'process_clip.py')
bridge=importlib.util.module_from_spec(spec)
spec.loader.exec_module(bridge)
report=json.loads((ROOT/'runs/WORD3002/result_v3.json').read_text())
bpy.ops.wm.open_mainfile(filepath=str(ROOT/'runs/WORD3002'/report['output_files']['baseline']))
arm=bridge.primary_arm()
row={'hand_quality':{}}
for side,group in [('L','left_hand'),('R','right_hand')]:
    prefix=f'J_Bip_{side}_'
    points=[arm.data.bones[prefix+'Hand'].head_local.copy()]
    for finger in bridge.FINGERS:
        heads=[arm.data.bones[prefix+finger+str(j)].head_local.copy() for j in (1,2,3)]
        points.extend([*heads,heads[2]+(heads[2]-heads[1])])
    row[group+'_shape']=[dict(zip(('x','y','z'),p)) for p in points]
    row['hand_quality'][group]={'identity':'pose_wrist_confirmed'}
motion={'width':1,'height':1,'frames':[row]}
targets,valid,*_=bridge.jihyeon_targets(arm,motion)
assert all(valid[s]==[True] for s in ('L','R'))
assert all(bridge.angle(Quaternion(),values[0])<.1 for values in targets.values()), 'Rest pose must remain identity'
# A rigid rotation of all source points must not become a finger shape change.
rot=Quaternion((.3,.4,.5),1.2)
for group in ('left_hand','right_hand'):
    for p in row[group+'_shape']:
        vector=rot @ bridge.Vector((p['x'],p['y'],p['z']))
        p.update(zip(('x','y','z'),vector))
targets,valid,*_=bridge.jihyeon_targets(arm,motion)
assert all(bridge.angle(Quaternion(),values[0])<.1 for values in targets.values()), 'Wrist orientation leaked into finger correction'
row['hand_quality']['left_hand']['identity']='unverified'
targets,valid,*_=bridge.jihyeon_targets(arm,motion)
assert not valid['L'][0] and valid['R'][0]
assert all(values[0] is None for n,values in targets.items() if n.startswith('J_Bip_L_'))
for p in row['right_hand_shape']:
    p.update(x=0,y=0,z=0)
targets,valid,*_=bridge.jihyeon_targets(arm,motion)
assert not valid['R'][0]
result={'status':'PASS','checks':['identity rest pose','rigid source orientation invariance','unverified identity skipped','degenerate palm skipped']}
with (ROOT/'bridge_tests.json').open('x') as f:
    json.dump(result,f,indent=2)
print(result)

