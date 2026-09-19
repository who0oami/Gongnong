"""Run the supplied legacy retargeter unchanged apart from its input path."""
import ast,hashlib,json
from pathlib import Path
import bpy,addon_utils
from mathutils import Vector
root=Path(__file__).resolve().parents[1]
out=root/'output/WORD0021_F10_legacy_reference_v1.blend'
diag=root/'diagnostics/WORD0021_F10_legacy_reference_v1'
if out.exists() or diag.exists():raise FileExistsError(out)
diag.mkdir()
for obj in bpy.context.scene.objects:
    obj.hide_render=True
    obj.hide_set(True)
source=Path('C:/New_test/retarget_avatar_real_v2.py')
motion=Path('C:/Users/ESTsoft/Downloads/WORD0021_3d_approx.json')
model=Path('C:/Users/ESTsoft/Downloads/AvatarSample_F10.vrm')
code=source.read_text(encoding='utf8')
(diag/source.name).write_text(code,encoding='utf8')
addon_utils.enable('bl_ext.blender_org.vrm',default_set=True,persistent=True)
bpy.ops.import_scene.vrm(filepath=str(model))
scene=bpy.context.scene
arm=max((o for o in scene.objects if o.type=='ARMATURE'),key=lambda a:sum(m.type=='ARMATURE' and m.object==a for o in scene.objects for m in o.modifiers))
arm.name='Armature'
face=max((o for o in scene.objects if o.type=='MESH' and o.data.shape_keys),key=lambda o:sum(k.name.startswith('Fcl_') for k in o.data.shape_keys.key_blocks))
face.name='Face'
tree=ast.parse(code,str(source))
changes=0
for node in tree.body:
    if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='WORD_ID' for t in node.targets) and isinstance(node.value,ast.Constant):
        node.value=ast.Constant('WORD0021')
    if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='MOTION_JSON_PATH' for t in node.targets):
        node.value=ast.Call(func=ast.Name(id='Path',ctx=ast.Load()),args=[ast.Constant(str(motion))],keywords=[])
        changes+=1
assert changes==1
ast.fix_missing_locations(tree)
exec(compile(tree,str(source),'exec'),{'__file__':str(source),'__name__':'__main__'})
data=bpy.data.cameras.new('ReferenceCamera');camera=bpy.data.objects.new('ReferenceCamera',data);scene.collection.objects.link(camera)
heads=arm.data.bones
x=(heads['J_Bip_L_UpperArm'].head_local-heads['J_Bip_R_UpperArm'].head_local).normalized()
up=(heads['J_Bip_C_Neck'].head_local-heads['J_Bip_C_Hips'].head_local).normalized()
front=(arm.matrix_world.to_3x3() @ x.cross(up)).normalized()
center=arm.matrix_world @ ((heads['J_Bip_C_Neck'].head_local+heads['J_Bip_C_Hips'].head_local)/2)
camera.location=center+front*3;camera.rotation_euler=(center-camera.location).to_track_quat('-Z','Y').to_euler();data.type='ORTHO';data.ortho_scale=1.2;scene.camera=camera
scene.render.engine='BLENDER_EEVEE';scene.view_settings.view_transform='Standard';scene.view_settings.look='None'
world=bpy.data.worlds.new('ReferenceWorld');scene.world=world;world.use_nodes=True
bg=world.node_tree.nodes.new('ShaderNodeBackground');wo=world.node_tree.nodes.new('ShaderNodeOutputWorld');world.node_tree.links.new(bg.outputs[0],wo.inputs['Surface']);bg.inputs[0].default_value=(.35,.35,.35,1);bg.inputs[1].default_value=.8
light=bpy.data.lights.new('Key','AREA');light.energy=300;light.size=4;ob=bpy.data.objects.new('Key',light);scene.collection.objects.link(ob);ob.location=center+front*3+Vector((0,0,2));ob.rotation_euler=(center-ob.location).to_track_quat('-Z','Y').to_euler()
for screen in bpy.data.screens:
    for area in screen.areas:
        if area.type=='VIEW_3D':
            area.spaces.active.shading.type='MATERIAL';area.spaces.active.region_3d.view_perspective='CAMERA';area.spaces.active.overlay.show_overlays=False
scene.frame_set(0);bpy.ops.file.pack_all();bpy.ops.wm.save_as_mainfile(filepath=str(out))
(diag/'provenance.json').write_text(json.dumps({'source_code':str(source),'source_sha256':hashlib.sha256(code.encode()).hexdigest(),'motion':str(motion),'motion_sha256':hashlib.sha256(motion.read_bytes()).hexdigest(),'model':str(model),'only_code_override':'MOTION_JSON_PATH','frame_count':107,'original_video':'not yet located'},indent=2),encoding='utf8')
scene.render.resolution_x=640;scene.render.resolution_y=640;scene.render.resolution_percentage=100
scene.render.engine='BLENDER_WORKBENCH'
for f in (0,17,34,51,67,85,106):
    scene.frame_set(f);scene.render.filepath=str(diag/f'frame_{f:03d}.png');bpy.ops.render.render(write_still=True)
print('REFERENCE_SAVED',out)

