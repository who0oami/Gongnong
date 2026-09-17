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
#    │  └─ export_vroid_rig_info.py
#    └─ sample/
#       └─ vroid_rig_info.json
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
        "export_vroid_rig_info.py를 "
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
    / "vroid_rig_info.json"
)


# sample 폴더가 없으면 자동 생성
SAMPLE_DIR.mkdir(
    parents=True,
    exist_ok=True
)


# ==========================================
# Armature 찾기
# ==========================================

arm = bpy.data.objects.get(
    "Armature"
)

if arm is None:

    raise RuntimeError(
        "Armature를 찾을 수 없습니다."
    )


# ==========================================
# 저장할 Bone
# ==========================================

TARGET_PREFIXES = (
    "J_Bip_C_",
    "J_Bip_L_",
    "J_Bip_R_",
)


# ==========================================
# Matrix -> list 변환
# ==========================================

def matrix_to_list(matrix):

    return [
        [
            float(value)
            for value in row
        ]
        for row in matrix
    ]


# ==========================================
# Vector -> list 변환
# ==========================================

def vector_to_list(vector):

    return [
        float(vector.x),
        float(vector.y),
        float(vector.z),
    ]


# ==========================================
# 결과
# ==========================================

result = {

    "armature_name": arm.name,

    "matrix_world": matrix_to_list(
        arm.matrix_world
    ),

    "bones": {}
}


# ==========================================
# Bone 정보 추출
# ==========================================

for bone in arm.data.bones:

    if not bone.name.startswith(
        TARGET_PREFIXES
    ):
        continue


    parent_name = None

    if bone.parent is not None:

        parent_name = bone.parent.name


    result["bones"][bone.name] = {

        "parent": parent_name,

        "head_local": vector_to_list(
            bone.head_local
        ),

        "tail_local": vector_to_list(
            bone.tail_local
        ),

        "length": float(
            bone.length
        ),

        "matrix_local": matrix_to_list(
            bone.matrix_local
        ),
    }


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
print("==============================")
print("VRM RIG 정보 저장 완료")
print("==============================")

print()
print("Armature:")
print(arm.name)

print()
print("Bone 개수:")
print(len(result["bones"]))

print()
print("스크립트 위치:")
print(SCRIPT_DIR)

print()
print("저장 위치:")
print(OUTPUT_PATH)

print()
print("==============================")
