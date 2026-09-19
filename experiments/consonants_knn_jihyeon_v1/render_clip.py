"""Matching animated previews of all three saved variants, 15 fps."""
import argparse
import json
from pathlib import Path
import sys
import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parent


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--word', required=True)
    args = p.parse_args(sys.argv[sys.argv.index('--')+1:])
    folder = ROOT/'runs'/args.word
    data = json.loads((folder/'result_v4.json').read_text(encoding='utf-8'))
    out = folder/'preview_v4'
    out.mkdir(exist_ok=False)
    centers = {}
    camera_back = None
    active_side = None
    for variant,filename in data['output_files'].items():
        bpy.ops.wm.open_mainfile(filepath=str(folder/filename))
        scene = bpy.context.scene
        scene.render.engine = 'BLENDER_WORKBENCH'
        scene.render.resolution_x = 512
        scene.render.resolution_y = 512
        scene.render.resolution_percentage = 100
        scene.render.image_settings.file_format = 'PNG'
        scene.display.shading.light = 'STUDIO'
        scene.display.shading.color_type = 'MATERIAL'
        scene.display.shading.show_cavity = True
        arm = max((o for o in scene.objects if o.type=='ARMATURE'),key=lambda a:len(a.pose.bones))
        up = (arm.matrix_world @ arm.data.bones['J_Bip_C_Neck'].head_local)-(arm.matrix_world @ arm.data.bones['J_Bip_C_Hips'].head_local)
        up.normalize()
        camera = scene.camera
        camera.location += up*.15
        camera.data.ortho_scale = .85
        main_location = camera.location.copy()
        if variant == 'baseline':
            camera_back = camera.rotation_euler.to_quaternion() @ Vector((0,0,1))
            heights = {'L':0.0,'R':0.0}
            for frame in range(scene.frame_start,scene.frame_end+1):
                scene.frame_set(frame)
                for side in heights:
                    heights[side] += (arm.matrix_world @ arm.pose.bones[f'J_Bip_{side}_Hand'].head).dot(up)
            active_side = max(heights,key=heights.get)
            raw = []
            for frame in range(scene.frame_start,scene.frame_end+1):
                scene.frame_set(frame)
                names = [f'J_Bip_{active_side}_{finger}{j}' for finger in ('Thumb','Index','Middle','Ring','Little') for j in (1,2,3)]
                raw.append(sum((arm.matrix_world @ arm.pose.bones[n].head for n in names),Vector())/len(names))
            for i in range(len(raw)):
                window=raw[max(0,i-5):min(len(raw),i+6)]
                centers[i+scene.frame_start]=sum(window,Vector())/len(window)
        seq = out/variant
        seq.mkdir()
        hands = out/(variant+'_hand')
        hands.mkdir()
        for index,frame in enumerate(range(scene.frame_start,scene.frame_end+1,2)):
            scene.frame_set(frame)
            camera.location = main_location
            camera.data.ortho_scale = .85
            scene.render.filepath = str(seq/f'{index:04d}.png')
            bpy.ops.render.render(write_still=True)
            camera.location = centers[frame]+camera_back*2.8
            camera.data.ortho_scale = .34
            scene.render.filepath = str(hands/f'{index:04d}.png')
            bpy.ops.render.render(write_still=True)
    with (out/'render_complete.json').open('x') as f:
        json.dump({'fps':data['fps']/2,'variants':[v+s for v in data['output_files'] for s in ('','_hand')],'frames':(data['frames']+1)//2,'closeup_side':active_side},f)


if __name__ == '__main__':
    main()

