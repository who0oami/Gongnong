import bpy
from pathlib import Path
root=Path(__file__).resolve().parents[1]
out=root/'output/WORD2551_F10_legacy_reference_v4.blend'
diag=root/'diagnostics/WORD2551_F10_legacy_reference_v4'
if out.exists() or diag.exists():raise FileExistsError(out)
diag.mkdir()
cube=bpy.data.objects.get('Cube')
if cube and cube.type=='MESH' and not any(m.type=='ARMATURE' for m in cube.modifiers):
    cube.hide_render=True;cube.hide_set(True)
scene=bpy.context.scene
scene.frame_set(0)
bpy.ops.wm.save_as_mainfile(filepath=str(out))
scene.render.engine='BLENDER_WORKBENCH';scene.render.resolution_x=640;scene.render.resolution_y=640
for f in (0,17,34,51,67,85,101):
    scene.frame_set(f);scene.render.filepath=str(diag/f'frame_{f:03d}.png');bpy.ops.render.render(write_still=True)
