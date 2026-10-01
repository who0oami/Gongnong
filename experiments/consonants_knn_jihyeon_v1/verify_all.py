"""Independent saved-file preservation check across all 18 final clips."""
import json
import math
from pathlib import Path
import bpy

ROOT=Path(__file__).resolve().parent
FINGER_TOKENS=('Thumb','Index','Middle','Ring','Little')


def snapshot(path):
    bpy.ops.wm.open_mainfile(filepath=str(path))
    scene=bpy.context.scene
    arm=max((o for o in scene.objects if o.type=='ARMATURE'),key=lambda a:len(a.pose.bones))
    values={}
    min_norm=1.0
    for half in range(scene.frame_start*2,scene.frame_end*2+1):
        scene.frame_set(half//2,subframe=(half%2)/2)
        state={}
        for b in arm.pose.bones:
            finger=any(token in b.name for token in FINGER_TOKENS)
            if finger:
                state['trs/'+b.name]=[*b.location,*b.scale]
                q=b.rotation_quaternion
                assert all(math.isfinite(v) for v in q),(half,b.name)
                min_norm=min(min_norm,q.magnitude)
            else:
                state['bone/'+b.name]=[v for row in b.matrix_basis for v in row]
        for obj in scene.objects:
            state['object/'+obj.name]=[v for row in obj.matrix_world for v in row]
            if obj.type=='MESH' and obj.data.shape_keys:
                state['face/'+obj.name]=[k.value for k in obj.data.shape_keys.key_blocks]
        values[half]=state
    return values,min_norm,(scene.frame_start,scene.frame_end,scene.render.fps,scene.render.fps_base)


results=[]
for folder in sorted((ROOT/'runs').iterdir()):
    report=json.loads((folder/'result_v4.json').read_text())
    before,_,timeline=snapshot(folder/report['output_files']['baseline'])
    after,min_norm,final_timeline=snapshot(folder/report['output_files']['knn_jihyeon'])
    assert timeline==final_timeline
    assert before.keys()==after.keys()
    error=0.0
    for frame,original in before.items():
        current=after[frame]
        assert original.keys()==current.keys()
        for name,values in original.items():
            assert len(values)==len(current[name])
            error=max(error,max((abs(a-b) for a,b in zip(values,current[name])),default=0))
    assert error < 1e-6,(folder,error)
    assert min_norm > .99,(folder,min_norm)
    results.append({'word':folder.name,'status':'PASS','integer_and_half_frames':len(before),'protected_transform_and_face_max_error':error,'min_finger_quaternion_norm':min_norm})
    print('VERIFIED',folder.name,flush=True)
with (ROOT/'preservation_verification.json').open('x') as f:
    json.dump(results,f,indent=2)

