import bpy
import json
from pathlib import Path


# ==========================================
# 현재 스크립트 위치 찾기
#
# 예상 구조:
#
# ksl-tube/
# └─ word2153/
#    ├─ scripts/
#    │  └─ export_vroid_face_info.py
#    └─ sample/
#       └─ vroid_face_info.json
# ==========================================

def get_script_dir():

    # 일반 .py 파일로 실행하는 경우
    if "__file__" in globals():

        return Path(
            __file__
        ).resolve().parent


    # Blender Text Editor에서 실행하는 경우
    try:

        text = bpy.context.space_data.text

        if text is not None and text.filepath:

            return Path(
                bpy.path.abspath(
                    text.filepath
                )
            ).resolve().parent

    except Exception:
        pass


    raise RuntimeError(
        "\n스크립트 파일 위치를 확인할 수 없습니다.\n"
        "export_vroid_face_info.py를 "
        "word2153/scripts 폴더에 저장한 뒤 다시 실행하세요."
    )


SCRIPT_DIR = get_script_dir()

WORD_DIR = SCRIPT_DIR.parent

SAMPLE_DIR = (
    WORD_DIR
    / "sample"
)

OUTPUT_PATH = (
    SAMPLE_DIR
    / "vroid_face_info.json"
)


# sample 폴더가 없으면 자동 생성
SAMPLE_DIR.mkdir(
    parents=True,
    exist_ok=True
)


# ==========================================
# 결과
# ==========================================

result = {
    "meshes": {}
}


# ==========================================
# Mesh / Shape Key 정보 추출
# ==========================================

for obj in bpy.data.objects:

    if obj.type != "MESH":
        continue

    mesh_info = {
        "mesh_name": obj.data.name,
        "shape_keys": []
    }

    shape_keys = obj.data.shape_keys

    if shape_keys is not None:

        for key_block in shape_keys.key_blocks:

            mesh_info["shape_keys"].append({
                "name": key_block.name,
                "value": float(key_block.value),
                "slider_min": float(key_block.slider_min),
                "slider_max": float(key_block.slider_max),
            })

    result["meshes"][obj.name] = mesh_info


# ==========================================
# JSON 저장
# ==========================================

with open(
    OUTPUT_PATH,
    "w",
    encoding="utf-8"
) as f:

    json.dump(
        result,
        f,
        ensure_ascii=False,
        indent=2
    )


# ==========================================
# 완료 출력
# ==========================================

print()
print("====================================")
print("VRM FACE 정보 저장 완료")
print("====================================")
print()

total = 0

for obj_name, mesh_info in result["meshes"].items():

    keys = mesh_info["shape_keys"]

    if not keys:
        continue

    print()
    print("Mesh:", obj_name)
    print("Shape Key:", len(keys))

    for item in keys:
        print(" -", item["name"])

    total += len(keys)


print()
print("전체 Shape Key:", total)

print()
print("스크립트 위치:")
print(SCRIPT_DIR)

print()
print("저장 위치:")
print(OUTPUT_PATH)

print()
print("====================================")

