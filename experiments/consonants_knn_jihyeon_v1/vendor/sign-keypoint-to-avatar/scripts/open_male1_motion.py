"""Preserve the source scene and transfer its motion to a fresh VRM import."""
import bpy,addon_utils,json
from pathlib import Path
from mathutils import Matrix
root=Path(__file__).resolve().parents[1]
output=root/'output/love_Model_Male1_contact_color_v1.blend'
if output.exists():raise FileExistsError(output)
source=bpy.context.scene
def bound_arm(scene):
    return max((o for o in scene.objects if o.type=='ARMATURE'),key=lambda a:sum(m.type=='ARMATURE' and m.object==a for o in scene.objects for m in o.modifiers))
old=bound_arm(source)
names=[p.name for p in old.pose.bones if p.name.startswith(('J_Bip_L_','J_Bip_R_')) and any(s in p.name for s in ('UpperArm','LowerArm','Hand','Thumb','Index','Middle','Ring','Little')) and not p.name.endswith('_end')]
samples=[]
for f in range(source.frame_start,source.frame_end+1):
    source.frame_set(f)
    samples.append({n:old.pose.bones[n].matrix.to_3x3().normalized() @ old.data.bones[n].matrix_local.to_3x3().normalized().transposed() for n in names})
addon_utils.enable('bl_ext.blender_org.vrm',default_set=False,persistent=True)
scene=bpy.data.scenes.new('Male1_Motion')
bpy.context.window.scene=scene
bpy.ops.import_scene.vrm(filepath='C:/Users/ESTsoft/Downloads/Model_Male (1).vrm')
arm=bound_arm(scene)
assert all(n in arm.pose.bones for n in names),'Missing target bones'
for obj in scene.objects:
    for m in obj.modifiers:
        if m.type=='ARMATURE':m.use_deform_preserve_volume=True
previous={}
for i,sample in enumerate(samples):
    frame=source.frame_start+i
    scene.frame_set(frame)
    for n in names:
        pb=arm.pose.bones[n]
        desired=sample[n] @ pb.bone.matrix_local.to_3x3().normalized()
        base=pb.parent.matrix @ pb.parent.bone.matrix_local.inverted() @ pb.bone.matrix_local
        q=(base.to_3x3().normalized().transposed() @ desired).to_quaternion()
        if n in previous and q.dot(previous[n])<0:q.negate()
        pb.rotation_mode='QUATERNION';pb.rotation_quaternion=q
        pb.keyframe_insert(data_path='rotation_quaternion',frame=frame)
        previous[n]=q.copy()
        bpy.context.view_layer.update()
action=arm.animation_data.action
for layer in action.layers:
    for strip in layer.strips:
        for bag in strip.channelbags:
            for fc in bag.fcurves:
                for k in fc.keyframe_points:k.interpolation='LINEAR'
for obj in source.objects:
    if obj.type in ('CAMERA','LIGHT'):
        copy=obj.copy();copy.data=obj.data.copy();scene.collection.objects.link(copy)
        if obj==source.camera:scene.camera=copy
scene.world=source.world.copy()
scene.render.engine='BLENDER_EEVEE'
scene.view_settings.view_transform='Standard';scene.view_settings.look='None'
scene.render.fps=source.render.fps;scene.render.fps_base=source.render.fps_base
scene.frame_start=source.frame_start;scene.frame_end=source.frame_end
scene.render.resolution_x=700;scene.render.resolution_y=700;scene.render.resolution_percentage=100
scene.frame_set(0)
for screen in bpy.data.screens:
    for area in screen.areas:
        if area.type=='VIEW_3D':
            area.spaces.active.shading.type='MATERIAL'
            area.spaces.active.shading.use_scene_world=False
            area.spaces.active.shading.use_scene_lights=False
            area.spaces.active.region_3d.view_perspective='CAMERA'
            area.spaces.active.overlay.show_overlays=False
bpy.ops.file.pack_all()
bpy.ops.wm.save_as_mainfile(filepath=str(output))
out=root/'diagnostics/love_Model_Male1_contact_color_v1'
out.mkdir(exist_ok=False)
scene.frame_set(200)
scene.render.filepath=str(out/'frame_200_color.png')
bpy.ops.render.render(write_still=True)
print('NEW_MODEL_SAVED',output)

