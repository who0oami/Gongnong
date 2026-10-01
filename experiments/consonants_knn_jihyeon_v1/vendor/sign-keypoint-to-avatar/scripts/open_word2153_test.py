from datetime import datetime
from pathlib import Path
import json
import os
import runpy
import traceback

import bpy

scripts_dir = Path(__file__).resolve().parent
word_dir = scripts_dir.parent
config_path = word_dir / "retarget_config.json"
config = json.loads(config_path.read_text(encoding="utf-8"))

def resolve_config_path(value):
    path = Path(value)
    return path if path.is_absolute() else word_dir / path

model_path = resolve_config_path(os.environ.get("KSL_MODEL_FILE", config["model_file"]))
motion_path = resolve_config_path(os.environ.get("KSL_MOTION_JSON", config["motion_file"]))
word_id = motion_path.stem.split("_3d")[0]
log_path = scripts_dir / "blender_run.log"
output_dir = resolve_config_path(config.get("output_dir", "output"))
output_path = resolve_config_path(
    os.environ.get(
        "KSL_OUTPUT_FILE",
        config.get("output_file", str(output_dir / f"{word_id}_{model_path.stem}.blend")),
    )
)

try:
    if not model_path.is_file():
        raise FileNotFoundError(f"Avatar model not found: {model_path}")
    if not motion_path.is_file():
        raise FileNotFoundError(f"Motion JSON not found: {motion_path}")

    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    if model_path.suffix.lower() == ".vrm":
        try:
            bpy.ops.import_scene.vrm(filepath=str(model_path))
        except (AttributeError, RuntimeError):
            # VRM은 glTF 기반이므로 VRM 애드온이 없을 때 기본 importer로 fallback
            bpy.ops.import_scene.gltf(filepath=str(model_path))
    else:
        bpy.ops.import_scene.gltf(filepath=str(model_path))

    armatures = [obj for obj in bpy.context.scene.objects if obj.type == "ARMATURE"]
    if not armatures:
        raise RuntimeError("Imported GLB has no armature")

    # glTF에 skin이 여러 개 있으면 같은 본을 가진 Armature가 복수 생성될 수 있다.
    # 실제 캐릭터 Mesh의 Armature modifier가 참조하는 대상을 선택한다.
    bound_counts = {arm: 0 for arm in armatures}
    for obj in bpy.context.scene.objects:
        if obj.type != "MESH":
            continue
        for modifier in obj.modifiers:
            if modifier.type == "ARMATURE" and modifier.object in bound_counts:
                bound_counts[modifier.object] += 1
    armature = max(armatures, key=lambda item: bound_counts[item])

    # 리타기팅 스크립트가 정확히 하나의 `Armature`를 찾도록 미사용 복제본 제거
    for other in armatures:
        if other != armature:
            bpy.data.objects.remove(other, do_unlink=True)
    armature.name = "Armature"
    armature.data.name = "Armature"

    # 모델이 바뀌면 rest pose와 본 행렬도 반드시 새로 추출해야 한다.
    runpy.run_path(str(scripts_dir / "export_vroid_rig_info.py"), run_name="__main__")
    runpy.run_path(str(scripts_dir / "export_vroid_face_info.py"), run_name="__main__")
    os.environ["KSL_MOTION_JSON"] = str(motion_path)
    os.environ["KSL_WORD_ID"] = word_id
    if config.get("profile_file"):
        os.environ["KSL_RETARGET_PROFILE"] = str(resolve_config_path(config["profile_file"]))
    runpy.run_path(str(scripts_dir / "word2153_retarget_v2.py"), run_name="__main__")
    runpy.run_path(str(scripts_dir / "word2153_face_retarget.py"), run_name="__main__")
    bpy.context.scene.frame_set(1)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(output_path))

    log_path.write_text(
        f"SUCCESS {datetime.now().isoformat()}\nmodel={model_path}\nmotion={motion_path}\noutput={output_path}\n",
        encoding="utf-8",
    )
except Exception:
    log_path.write_text(
        f"FAILED {datetime.now().isoformat()}\n{traceback.format_exc()}",
        encoding="utf-8",
    )
    raise

