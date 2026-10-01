from pathlib import Path
import bpy
from mathutils import Vector
scene=bpy.context.scene
scene.frame_set(200)
arm=max((o for o in scene.objects if o.type=='ARMATURE'),key=lambda a:sum(m.type=='ARMATURE' and m.object==a for o in scene.objects for m in o.modifiers))
camera=scene.camera
view=(camera.location-Vector((0,0,1.2))).normalized()
center=arm.matrix_world @ ((arm.pose.bones['J_Bip_L_Hand'].head+arm.pose.bones['J_Bip_R_Hand'].head)/2)
camera.location=center+view*2.8
camera.rotation_euler=(center-camera.location).to_track_quat('-Z','Y').to_euler()
camera.data.ortho_scale=.65
scene.render.resolution_x=640;scene.render.resolution_y=640
path=Path(bpy.data.filepath).parent.parent/'diagnostics'/Path(bpy.data.filepath).stem/'frame_200_color.png'
if path.exists():raise FileExistsError(path)
scene.render.filepath=str(path)
bpy.ops.render.render(write_still=True)
