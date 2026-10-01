"""Restore VRM-native materials without changing the animated rig or meshes."""
from pathlib import Path
import bpy
import addon_utils
import json

root=Path(__file__).resolve().parents[1]
output=root/'output/love_Model_M10_hands_aligned_color_v1.blend'
if output.exists():
    raise FileExistsError(output)
animated=bpy.context.scene
original_materials={m.name:m for obj in animated.objects if obj.type=='MESH' for m in obj.data.materials if m}
addon_utils.enable('bl_ext.blender_org.vrm',default_set=False,persistent=True)
reference=bpy.data.scenes.new('M10_Original_Material_Reference')
bpy.context.window.scene=reference
before=set(bpy.data.materials)
bpy.ops.import_scene.vrm(filepath='C:/Users/ESTsoft/Downloads/Model_M10.vrm')
imported=[m for m in bpy.data.materials if m not in before]
replacements={}
for name in original_materials:
    matches=[m for m in imported if m.name==name or m.name.startswith(name+'.')]
    if len(matches)!=1:
        raise ValueError((name,[m.name for m in matches]))
    replacements[name]=matches[0]
bpy.context.window.scene=animated
for obj in animated.objects:
    if obj.type=='MESH':
        for slot in obj.material_slots:
            if slot.material:
                slot.material=replacements[slot.material.name]
for scene in (animated,reference):
    scene.render.engine='BLENDER_EEVEE'
    scene.view_settings.view_transform='Standard'
    scene.view_settings.look='None'
    scene.view_settings.exposure=0
    scene.view_settings.gamma=1
    if not scene.world:
        scene.world=bpy.data.worlds.new(scene.name+'World')
    scene.world.use_nodes=True
    nodes=scene.world.node_tree.nodes
    background=next((n for n in nodes if n.type=='BACKGROUND'),None) or nodes.new('ShaderNodeBackground')
    world_output=next((n for n in nodes if n.type=='OUTPUT_WORLD'),None) or nodes.new('ShaderNodeOutputWorld')
    scene.world.node_tree.links.new(background.outputs[0],world_output.inputs['Surface'])
    background.inputs['Color'].default_value=(.35,.35,.35,1)
    background.inputs['Strength'].default_value=.8
    light=bpy.data.lights.new(scene.name+'_Key','AREA')
    light.energy=350
    light.shape='DISK'
    light.size=4
    obj=bpy.data.objects.new(light.name,light)
    scene.collection.objects.link(obj)
    obj.location=(0,-3,4)
    from mathutils import Vector
    obj.rotation_euler=(Vector((0,0,1))-obj.location).to_track_quat('-Z','Y').to_euler()
for screen in bpy.data.screens:
    for area in screen.areas:
        if area.type=='VIEW_3D':
            area.spaces.active.shading.type='MATERIAL'
            area.spaces.active.shading.use_scene_world=False
            area.spaces.active.shading.use_scene_lights=False
bpy.ops.file.pack_all()
animated.frame_set(0)
bpy.ops.wm.save_as_mainfile(filepath=str(output))
directory=root/'diagnostics/love_Model_M10_materials_v1'
directory.mkdir(exist_ok=False)
(directory/'materials.json').write_text(json.dumps({n:m.name for n,m in replacements.items()},indent=2),encoding='utf8')
animated.render.resolution_x=700
animated.render.resolution_y=700
animated.render.filepath=str(directory/'frame_000.png')
bpy.ops.render.render(write_still=True)
print('RESTORED_MATERIALS',len(replacements),'OUTPUT',output)
