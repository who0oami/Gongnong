import bpy
from pathlib import Path
from mathutils import Vector
scene=bpy.context.scene
arm=max((o for o in scene.objects if o.type=='ARMATURE'),key=lambda a:sum(m.type=='ARMATURE' and m.object==a for o in scene.objects for m in o.modifiers))
out=Path(bpy.data.filepath).parent.parent/'diagnostics'/Path(bpy.data.filepath).stem
out.mkdir(exist_ok=True)
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
    scene.render.filepath=str(out/f'frame_{f:03d}.png')
    if Path(scene.render.filepath).exists():raise FileExistsError(scene.render.filepath)
    bpy.ops.render.render(write_still=True)

