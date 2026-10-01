import bpy
from pathlib import Path
from mathutils import Vector

output_dir = Path(__file__).resolve().parent.parent / "diagnostics" / Path(bpy.data.filepath).stem
output_dir.mkdir(parents=True, exist_ok=True)

scene = bpy.context.scene
scene.render.engine = "BLENDER_WORKBENCH"
scene.render.resolution_x = 900
scene.render.resolution_y = 900
scene.render.resolution_percentage = 100
scene.display.shading.light = "STUDIO"
scene.display.shading.show_shadows = True
scene.display.shading.show_cavity = True
scene.display.shading.cavity_type = "WORLD"
scene.display.shading.color_type = "MATERIAL"

camera_data = bpy.data.cameras.new("DiagnosticCamera")
camera = bpy.data.objects.new("DiagnosticCamera", camera_data)
scene.collection.objects.link(camera)
scene.camera = camera
camera.data.lens = 58

def point_camera(location, target):
    camera.location = location
    camera.rotation_euler = (Vector(target) - camera.location).to_track_quat("-Z", "Y").to_euler()

views = {
    "front": ((0.0, -3.4, 1.35), (0.0, 0.0, 1.25)),
    "hands": ((0.0, -2.0, 1.42), (0.0, 0.0, 1.36)),
    "hands_top": ((0.0, -1.5, 2.45), (0.0, 0.0, 1.35)),
}

for frame in (0, 17, 34, 51, 67):
    scene.frame_set(frame)
    for name, (location, target) in views.items():
        point_camera(location, target)
        scene.render.filepath = str(output_dir / f"frame_{frame:03d}_{name}.png")
        bpy.ops.render.render(write_still=True)

print(f"Diagnostic renders saved to {output_dir}")
