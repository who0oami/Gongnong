# V6.3: adjustable forward hand offset plus V6.1 rest clearance (Blender).
# JSON is read-only. Torso/face and V5 finger solvers are retained.
# Finger roll is transported from the palm/parent, rather than rebuilt
# from a palm normal that becomes singular during a 90-degree curl.
# No anatomical angle clamp: source bends and sign-language poses survive.
# This does not repair inaccurate source landmarks or skin weights.

import bpy
import json
import math
from pathlib import Path
from mathutils import Vector, Matrix, Quaternion


# ============================================================
# RETARGET 설정
# ============================================================
# Blender에서 다른 단어를 테스트할 때 이 값만 바꾸면 됩니다.
# 예: "WORD0001", "WORD0552", "WORD1202", "WORD2153"
WORD_ID = "WORD1584"

# V6: solve wrist positions using the target's actual arm lengths.
# Source coordinates remain read-only; V5 finger rotations are retained.
ARM_POSITION_IK = True
ARM_IK_PREVIOUS_POLE = {}
ARM_IK_CLAMPED = 0
ARM_IK_MAX_ERROR = 0.0

# V6.3: small forward translation of both wrist IK goals throughout the clip.
# 0.60 = 60% of wrist-to-middle-MCP length (roughly 6 cm for a 10 cm palm).
# Set to 0.30 to restore V6.2 offset, or 0.0 for V6.1 offset.
# Applied in torso-forward direction, not camera direction; requires ARM_POSITION_IK.
# This can separate body-contact signs from the body; tune per word if needed.
HAND_FORWARD_PALM_LENGTHS = 0.60

# V6.1: forward clearance only near low resting poses at clip boundaries.
# Multiplier of the target wrist-to-middle-MCP length (about 10 cm here).
# This is a configurable heuristic, not mesh collision detection.
REST_HAND_CLEARANCE = True
REST_FORWARD_PALM_LENGTHS = 1.6
REST_MATCH_FULL = 0.12
REST_MATCH_ZERO = 0.45

ARMATURE_NAME = "Armature"
FACE_OBJECT_NAME = "Face"

# 0 = 원본 그대로
# 1 = 앞뒤 1프레임까지 평균 = 3프레임 smoothing
SMOOTH_RADIUS = 1
EPS = 1e-8

# 몸통 / 머리 분배 조절
# 몸통 회전은 Spine -> Chest -> UpperChest로 나눠서 적용합니다.
TORSO_BONE_FACTORS = {
    "J_Bip_C_Spine": 0.20,
    "J_Bip_C_Chest": 0.55,
    "J_Bip_C_UpperChest": 1.00,
}

# Neck은 몸통 방향과 Head 방향의 중간 회전을 사용합니다.
NECK_HEAD_BLEND = 0.45

# ============================================================
# SYN 머리 방향 안정화
# ============================================================
# Face70가 BODY25 기준 움직임과 너무 다르면 이상치로 판단합니다.
HEAD_FACE_BODY_MAX_DIFF_DEG = 15.0

# 직전 정상 Head에서 한 프레임 만에 너무 크게 튀면 이상치로 판단합니다.
HEAD_MAX_FRAME_JUMP_DEG = 12.0

# 이상치 제거 후에도 남는 정상 범위 안의 잔떨림을 줄입니다.
# 4 = 앞뒤 4프레임, 총 최대 9프레임 quaternion smoothing
HEAD_SMOOTH_RADIUS = 4

# Face 기반 상대 머리 움직임 반영량
# 1.0 = Face 움직임 100%
# 0.0 = 몸통 방향만 따라감
HEAD_FACE_MOTION_GAIN = 0.45

# 디버그 로그
HEAD_STABILIZE_DEBUG = True

# ============================================================
# SYN 손가락 회전 안정화
# ============================================================
# V5 chain solver에서도 정상적인 손가락 굽힘을 죽이지 않기 위해
# "몇 도 이상이면 이전 자세 유지" 같은 hard reject는 사용하지 않습니다.
#
# 대신 작은 잔떨림만 약하게 smoothing합니다.
# 1 = 앞뒤 1프레임, 총 최대 3프레임
FINGER_SMOOTH_RADIUS = 1

# raw 회전과 smoothed 회전을 섞는 비율
# 0.0 = 원본 그대로
# 1.0 = smoothing 100%
# 0.30 정도면 굽힘 동작은 대부분 유지하면서 미세 떨림만 줄어듭니다.
FINGER_SMOOTH_STRENGTH = 0.30

# 빠르게 움직이는 구간에서는 smoothing을 더 약하게 적용합니다.
# 인접 프레임 회전량이 이 값 이상이면 거의 원본을 보존합니다.
FINGER_FAST_MOTION_DEG = 10.0
FINGER_FAST_MOTION_STRENGTH = 0.08

# 디버그 로그
FINGER_STABILIZE_DEBUG = True

# Shoulder는 원본 Neck -> Shoulder 방향 변화를 그대로 반영합니다.
SHOULDER_ROTATION_GAIN = 0.85

# Face 강도 조절
BLINK_GAIN = 0.0
MOUTH_OPEN_GAIN = 0.85
MOUTH_WIDTH_GAIN = 0.65
BROW_UP_GAIN = 0.70
BROW_DOWN_GAIN = 0.45


def normalize_word_id(value):
    text = str(value).strip().upper()
    if text.startswith("WORD"):
        number = text[4:]
    else:
        number = text
    if not number.isdigit():
        raise ValueError(f"잘못된 WORD_ID: {value}")
    return f"WORD{int(number):04d}"


WORD_ID = normalize_word_id(WORD_ID)
PREFIX = WORD_ID
ACTION_NAME = f"{WORD_ID}_RETARGET"
FACE_ACTION_NAME = f"{WORD_ID}_FACE_RETARGET"


def get_script_dir():
    """
    retarget_avatar.py의 실제 파일 폴더를 찾습니다.

    Blender Text Editor에서는 __file__이
    ".../Untitled.blend/retarget_avatar.py"처럼 잘못 잡힐 수 있으므로,
    Text Editor가 알고 있는 실제 외부 파일 경로를 가장 먼저 사용합니다.
    """

    # 1) Blender Text Editor에서 Open으로 연 실제 .py 파일 경로 우선
    try:
        space_data = getattr(bpy.context, "space_data", None)
        text = getattr(space_data, "text", None)
        filepath = getattr(text, "filepath", "") if text else ""

        if filepath:
            path = Path(bpy.path.abspath(filepath)).resolve()

            # 실제 retarget_avatar.py 파일이면 이 위치를 사용
            if path.suffix.lower() == ".py":
                return path.parent
    except Exception:
        pass

    # 2) 일반 Python 실행 / Blender에서 __file__이 정상인 경우
    try:
        path = Path(__file__).resolve()

        # Blender가 "Untitled.blend/retarget_avatar.py" 같은 가짜 경로를
        # 만들어 준 경우는 제외
        fake_blend_parent = any(
            parent.suffix.lower() == ".blend"
            for parent in path.parents
        )

        if path.suffix.lower() == ".py" and not fake_blend_parent:
            return path.parent
    except Exception:
        pass

    raise RuntimeError(
        "retarget_avatar.py의 실제 파일 위치를 찾을 수 없습니다.\n"
        "Blender Scripting > Text Editor에서 저장소의 "
        "avatar_retarget/retarget/retarget_avatar.py 파일을 Open한 뒤 다시 실행하세요."
    )


SCRIPT_DIR = get_script_dir()

print("Script dir:", SCRIPT_DIR)


def find_data_file(filename):
    """
    retarget/retarget_avatar.py 기준으로
    ../keypoint_to_3d/output_3d/의 motion JSON을 우선 탐색합니다.
    """
    candidates = [
        SCRIPT_DIR / filename,
        SCRIPT_DIR.parent / filename,
        SCRIPT_DIR.parent / "keypoint_to_3d" / "output_3d" / filename,
    ]

    # 혹시 저장소 루트 또는 다른 실행 위치에서 실행한 경우를 위한 fallback
    candidates.extend(SCRIPT_DIR.glob(f"*/keypoint_to_3d/output_3d/{filename}"))

    seen = set()
    unique_candidates = []
    for path in candidates:
        key = str(path)
        if key not in seen:
            seen.add(key)
            unique_candidates.append(path)

    for path in unique_candidates:
        if path.is_file():
            return path.resolve()

    checked = "\n".join(str(path) for path in unique_candidates)
    raise FileNotFoundError(
        f"\n{filename} 파일을 찾을 수 없습니다.\n"
        f"확인한 위치:\n{checked}\n"
    )


MOTION_JSON_PATH = find_data_file(f"{WORD_ID}_3d_approx.json")


print()
print("============================================================")
print(f"{WORD_ID} AVATAR RETARGET (BODY + FACE)")
print("============================================================")
print("Motion:", MOTION_JSON_PATH)
print("============================================================")

# ============================================================
# BODY_25
# ============================================================

POSE = {
    "NOSE": 0,
    "NECK": 1,

    "R_SHOULDER": 2,
    "R_ELBOW": 3,
    "R_WRIST": 4,

    "L_SHOULDER": 5,
    "L_ELBOW": 6,
    "L_WRIST": 7,

    "MID_HIP": 8,

    "R_HIP": 9,
    "L_HIP": 12,

    "R_EYE": 15,
    "L_EYE": 16,
    "R_EAR": 17,
    "L_EAR": 18,
}


# ============================================================
# 손가락
#
# OpenPose Hand
#
# 0 = Wrist
#
# Thumb  : 1 2 3 4
# Index  : 5 6 7 8
# Middle : 9 10 11 12
# Ring   : 13 14 15 16
# Little : 17 18 19 20
# ============================================================

FINGER_SPECS = {

    "L": [

        ("J_Bip_L_Thumb1",  "left_hand", 1, 2),
        ("J_Bip_L_Thumb2",  "left_hand", 2, 3),
        ("J_Bip_L_Thumb3",  "left_hand", 3, 4),

        ("J_Bip_L_Index1",  "left_hand", 5, 6),
        ("J_Bip_L_Index2",  "left_hand", 6, 7),
        ("J_Bip_L_Index3",  "left_hand", 7, 8),

        ("J_Bip_L_Middle1", "left_hand", 9, 10),
        ("J_Bip_L_Middle2", "left_hand", 10, 11),
        ("J_Bip_L_Middle3", "left_hand", 11, 12),

        ("J_Bip_L_Ring1",   "left_hand", 13, 14),
        ("J_Bip_L_Ring2",   "left_hand", 14, 15),
        ("J_Bip_L_Ring3",   "left_hand", 15, 16),

        ("J_Bip_L_Little1", "left_hand", 17, 18),
        ("J_Bip_L_Little2", "left_hand", 18, 19),
        ("J_Bip_L_Little3", "left_hand", 19, 20),
    ],

    "R": [

        ("J_Bip_R_Thumb1",  "right_hand", 1, 2),
        ("J_Bip_R_Thumb2",  "right_hand", 2, 3),
        ("J_Bip_R_Thumb3",  "right_hand", 3, 4),

        ("J_Bip_R_Index1",  "right_hand", 5, 6),
        ("J_Bip_R_Index2",  "right_hand", 6, 7),
        ("J_Bip_R_Index3",  "right_hand", 7, 8),

        ("J_Bip_R_Middle1", "right_hand", 9, 10),
        ("J_Bip_R_Middle2", "right_hand", 10, 11),
        ("J_Bip_R_Middle3", "right_hand", 11, 12),

        ("J_Bip_R_Ring1",   "right_hand", 13, 14),
        ("J_Bip_R_Ring2",   "right_hand", 14, 15),
        ("J_Bip_R_Ring3",   "right_hand", 15, 16),

        ("J_Bip_R_Little1", "right_hand", 17, 18),
        ("J_Bip_R_Little2", "right_hand", 18, 19),
        ("J_Bip_R_Little3", "right_hand", 19, 20),
    ],
}


# ============================================================
# 좌/우 Arm 설정
# ============================================================

SIDE_INFO = {

    "L": {
        "group": "left_hand",

        "shoulder_pose": POSE["L_SHOULDER"],
        "elbow_pose": POSE["L_ELBOW"],
        "wrist_pose": POSE["L_WRIST"],

        "upperarm": "J_Bip_L_UpperArm",
        "lowerarm": "J_Bip_L_LowerArm",
        "hand": "J_Bip_L_Hand",

        "index1": "J_Bip_L_Index1",
        "middle1": "J_Bip_L_Middle1",
        "little1": "J_Bip_L_Little1",
    },

    "R": {
        "group": "right_hand",

        "shoulder_pose": POSE["R_SHOULDER"],
        "elbow_pose": POSE["R_ELBOW"],
        "wrist_pose": POSE["R_WRIST"],

        "upperarm": "J_Bip_R_UpperArm",
        "lowerarm": "J_Bip_R_LowerArm",
        "hand": "J_Bip_R_Hand",

        "index1": "J_Bip_R_Index1",
        "middle1": "J_Bip_R_Middle1",
        "little1": "J_Bip_R_Little1",
    },
}


# ============================================================
# 파일 확인
# ============================================================

if not MOTION_JSON_PATH.exists():

    raise FileNotFoundError(
        f"\n{WORD_ID} Motion JSON 없음:\n"
        + str(MOTION_JSON_PATH)
    )


# ============================================================
# JSON 읽기
# ============================================================

with open(
    MOTION_JSON_PATH,
    "r",
    encoding="utf-8"
) as f:

    motion_data = json.load(f)


frames = motion_data.get(
    "frames",
    []
)


if not frames:

    raise RuntimeError(
        f"{WORD_ID} JSON에 frames가 없습니다."
    )


frames = sorted(
    frames,
    key=lambda x: int(x["frame"])
)


fps = int(
    motion_data.get(
        "fps",
        30
    )
)


print()
print("==========================================")
print(f"{WORD_ID} BODY RETARGET")
print("==========================================")

print()
print("Motion:")
print(MOTION_JSON_PATH)

print()
print("Frames:", len(frames))
print("FPS:", fps)


# ============================================================
# Armature
# ============================================================

arm = bpy.data.objects.get(
    ARMATURE_NAME
)


if arm is None:

    raise RuntimeError(
        f"Armature '{ARMATURE_NAME}' 없음"
    )


print()
print("Armature:", arm.name)


# ============================================================
# Bone 목록
# ============================================================

TARGET_BONES = [

    # 몸통 / 목 / 머리
    "J_Bip_C_Spine",
    "J_Bip_C_Chest",
    "J_Bip_C_UpperChest",
    "J_Bip_C_Neck",
    "J_Bip_C_Head",

    # 어깨
    "J_Bip_L_Shoulder",
    "J_Bip_R_Shoulder",

    # 팔 / 손
    "J_Bip_L_UpperArm",
    "J_Bip_L_LowerArm",
    "J_Bip_L_Hand",

    "J_Bip_R_UpperArm",
    "J_Bip_R_LowerArm",
    "J_Bip_R_Hand",
]


for side in ("L", "R"):

    for spec in FINGER_SPECS[side]:

        TARGET_BONES.append(
            spec[0]
        )


TARGET_BONES = list(
    dict.fromkeys(
        TARGET_BONES
    )
)


# ============================================================
# Bone 존재 확인
# ============================================================

missing = []


for bone_name in TARGET_BONES:

    if bone_name not in arm.pose.bones:

        missing.append(
            bone_name + " [pose bone]"
        )

    if bone_name not in arm.data.bones:

        missing.append(
            bone_name + " [armature bone]"
        )


if missing:

    print()
    print("없는 Bone:")

    for name in missing:

        print(" -", name)

    raise RuntimeError(
        "필요 Bone이 없습니다."
    )


print()
print(
    "Retarget Bone:",
    len(TARGET_BONES),
    "개 확인 완료"
)


# ============================================================
# Blender Armature Rest Bone helper
#
# vroid_rig_info.json을 따로 읽지 않고, 현재 Blender에 로드된
# Armature의 rest bone 정보를 직접 사용합니다.
# ============================================================

def rig_head(bone_name):

    bone = arm.data.bones.get(
        bone_name
    )

    if bone is None:
        raise RuntimeError(
            f"Armature에 Bone이 없습니다: {bone_name}"
        )

    return bone.head_local.copy()


def rig_tail(bone_name):

    bone = arm.data.bones.get(
        bone_name
    )

    if bone is None:
        raise RuntimeError(
            f"Armature에 Bone이 없습니다: {bone_name}"
        )

    return bone.tail_local.copy()


# ============================================================
# Frame Point 읽기
# ============================================================

def get_raw_point(
    frame_data,
    group_name,
    point_index
):

    points = frame_data.get(
        group_name,
        []
    )

    if point_index >= len(points):

        return None

    point = points[
        point_index
    ]

    if point is None:

        return None

    if len(point) < 3:

        return None

    try:

        return Vector(
            (
                float(point[0]),
                float(point[1]),
                float(point[2]),
            )
        )

    except Exception:

        return None


# ============================================================
# 간단한 시간축 smoothing
# ============================================================

def get_smoothed_point(
    frame_index,
    group_name,
    point_index
):

    start_index = max(
        0,
        frame_index - SMOOTH_RADIUS
    )

    end_index = min(
        len(frames) - 1,
        frame_index + SMOOTH_RADIUS
    )

    values = []


    for i in range(
        start_index,
        end_index + 1
    ):

        point = get_raw_point(
            frames[i],
            group_name,
            point_index
        )

        if point is not None:

            values.append(
                point
            )


    if not values:

        return None


    result = Vector(
        (0.0, 0.0, 0.0)
    )


    for point in values:

        result += point


    result /= len(values)

    return result


# ============================================================
# 첫 프레임 Source Body 기준
# ============================================================

first_frame = frames[0]


source_neck = get_raw_point(
    first_frame,
    "pose",
    POSE["NECK"]
)

source_midhip = get_raw_point(
    first_frame,
    "pose",
    POSE["MID_HIP"]
)

source_left_shoulder = get_raw_point(
    first_frame,
    "pose",
    POSE["L_SHOULDER"]
)

source_right_shoulder = get_raw_point(
    first_frame,
    "pose",
    POSE["R_SHOULDER"]
)


if (
    source_neck is None
    or source_midhip is None
    or source_left_shoulder is None
    or source_right_shoulder is None
):

    raise RuntimeError(
        "Source body 기준점을 읽을 수 없습니다."
    )


# ============================================================
# Source Body Basis
# ============================================================

source_x = (
    source_left_shoulder
    -
    source_right_shoulder
)


source_up = (
    source_neck
    -
    source_midhip
)


if (
    source_x.length < EPS
    or source_up.length < EPS
):

    raise RuntimeError(
        "Source body basis 계산 실패"
    )


source_x.normalize()
source_up.normalize()


source_front = source_x.cross(
    source_up
)


if source_front.length < EPS:

    raise RuntimeError(
        "Source Front 계산 실패"
    )


source_front.normalize()


# 다시 직교화
source_up = source_front.cross(
    source_x
)

source_up.normalize()


source_basis = Matrix(
    (
        source_x,
        source_up,
        source_front,
    )
).transposed()


# ============================================================
# Target VRM Body 기준
# ============================================================

target_left_shoulder = rig_head(
    "J_Bip_L_UpperArm"
)

target_right_shoulder = rig_head(
    "J_Bip_R_UpperArm"
)

target_neck = rig_head(
    "J_Bip_C_Neck"
)

target_hips = rig_head(
    "J_Bip_C_Hips"
)


target_x = (
    target_left_shoulder
    -
    target_right_shoulder
)


target_up = (
    target_neck
    -
    target_hips
)


if (
    target_x.length < EPS
    or target_up.length < EPS
):

    raise RuntimeError(
        "Target body basis 계산 실패"
    )


target_x.normalize()
target_up.normalize()


target_front = target_x.cross(
    target_up
)


if target_front.length < EPS:

    raise RuntimeError(
        "Target Front 계산 실패"
    )


target_front.normalize()


target_up = target_front.cross(
    target_x
)

target_up.normalize()


target_basis = Matrix(
    (
        target_x,
        target_up,
        target_front,
    )
).transposed()


# ============================================================
# Source -> VRM 좌표계 Rotation
# ============================================================

source_to_target_rotation = (
    target_basis
    @
    source_basis.transposed()
)


# ============================================================
# Scale
# ============================================================

source_shoulder_width = (
    source_left_shoulder
    -
    source_right_shoulder
).length


target_shoulder_width = (
    target_left_shoulder
    -
    target_right_shoulder
).length


scale = (
    target_shoulder_width
    /
    source_shoulder_width
)


print()
print(
    "Source Shoulder Width:",
    round(
        source_shoulder_width,
        6
    )
)

print(
    "VRM Shoulder Width:",
    round(
        target_shoulder_width,
        6
    )
)

print(
    "Scale:",
    round(
        scale,
        6
    )
)


# ============================================================
# Source point -> VRM Armature Local point
# ============================================================

def source_to_armature(
    point
):

    relative = (
        point
        -
        source_neck
    )


    rotated = (
        source_to_target_rotation
        @
        relative
    )


    return (
        target_neck
        +
        rotated * scale
    )


# ============================================================
# Smoothed Source point -> Armature Local
# ============================================================

def mapped_point(
    frame_index,
    group_name,
    point_index
):

    point = get_smoothed_point(
        frame_index,
        group_name,
        point_index
    )


    if point is None:

        return None


    return source_to_armature(
        point
    )


# ============================================================
# 방향 Y + Hint로 직교 Basis 만들기
#
# Blender Bone의 길이 방향 = Local Y
# ============================================================

def make_semantic_basis(
    y_direction,
    z_hint
):

    y = y_direction.copy()


    if y.length < EPS:

        return None


    y.normalize()


    z = (
        z_hint
        -
        y * z_hint.dot(y)
    )


    # Hint가 Y와 거의 평행하면 fallback
    if z.length < EPS:

        candidates = [
            Vector((1.0, 0.0, 0.0)),
            Vector((0.0, 1.0, 0.0)),
            Vector((0.0, 0.0, 1.0)),
        ]


        found = False


        for candidate in candidates:

            test = (
                candidate
                -
                y * candidate.dot(y)
            )


            if test.length >= EPS:

                z = test
                found = True
                break


        if not found:

            return None


    z.normalize()


    x = y.cross(
        z
    )


    if x.length < EPS:

        return None


    x.normalize()


    # 다시 완전 직교화
    z = x.cross(
        y
    )

    z.normalize()


    return Matrix(
        (
            x,
            y,
            z,
        )
    ).transposed()


# ============================================================
# 몸통 / 머리 Orientation Helper
# ============================================================

def make_orientation_basis(
    x_direction,
    up_direction
):
    """
    좌우(X), 위(Y) 두 방향으로 직교 좌표계를 만듭니다.
    Z(앞/뒤)는 X cross Y로 계산합니다.
    """

    x = x_direction.copy()
    up = up_direction.copy()

    if x.length < EPS or up.length < EPS:
        return None

    x.normalize()
    up.normalize()

    front = x.cross(up)

    if front.length < EPS:
        return None

    front.normalize()

    # 완전히 직교하도록 up을 다시 계산
    up = front.cross(x)

    if up.length < EPS:
        return None

    up.normalize()

    return Matrix(
        (
            x,
            up,
            front,
        )
    ).transposed()


def rotation_fraction(
    rotation_matrix,
    factor
):
    """회전량의 일부만 사용합니다. 0=회전 없음, 1=전체 회전."""

    factor = max(
        0.0,
        min(1.0, float(factor))
    )

    q = (
        rotation_matrix
        .to_quaternion()
    )
    q.normalize()

    # 같은 회전의 두 Quaternion 부호 중 짧은 쪽 사용
    if q.w < 0.0:
        q = Quaternion(
            (-q.w, -q.x, -q.y, -q.z)
        )

    identity = Quaternion(
        (1.0, 0.0, 0.0, 0.0)
    )

    return identity.slerp(
        q,
        factor
    ).to_matrix()


def blend_rotations(
    rotation_a,
    rotation_b,
    factor
):
    """두 absolute rotation 사이를 Quaternion slerp로 보간합니다."""

    factor = max(
        0.0,
        min(1.0, float(factor))
    )

    qa = rotation_a.to_quaternion()
    qb = rotation_b.to_quaternion()

    qa.normalize()
    qb.normalize()

    dot = (
        qa.w * qb.w
        + qa.x * qb.x
        + qa.y * qb.y
        + qa.z * qb.z
    )

    if dot < 0.0:
        qb = Quaternion(
            (-qb.w, -qb.x, -qb.y, -qb.z)
        )

    return qa.slerp(
        qb,
        factor
    ).to_matrix()


def mapped_average(
    frame_index,
    group_name,
    indices
):
    points = []

    for index in indices:
        point = mapped_point(
            frame_index,
            group_name,
            index
        )

        if point is not None:
            points.append(point)

    if not points:
        return None

    result = Vector(
        (0.0, 0.0, 0.0)
    )

    for point in points:
        result += point

    result /= len(points)
    return result


def get_torso_frame_info(
    frame_index
):
    """
    BODY_25의 양 어깨 + Hip 계열 점으로 현재 몸통 좌표계를 계산합니다.
    Spine 점 자체는 없기 때문에 몸통 회전은 이 점들에서 추정합니다.
    """

    neck = mapped_point(
        frame_index,
        "pose",
        POSE["NECK"]
    )

    left_shoulder = mapped_point(
        frame_index,
        "pose",
        POSE["L_SHOULDER"]
    )

    right_shoulder = mapped_point(
        frame_index,
        "pose",
        POSE["R_SHOULDER"]
    )

    mid_hip = mapped_point(
        frame_index,
        "pose",
        POSE["MID_HIP"]
    )

    left_hip = mapped_point(
        frame_index,
        "pose",
        POSE["L_HIP"]
    )

    right_hip = mapped_point(
        frame_index,
        "pose",
        POSE["R_HIP"]
    )

    if (
        neck is None
        or left_shoulder is None
        or right_shoulder is None
        or mid_hip is None
    ):
        return None

    shoulder_center = (
        left_shoulder
        + right_shoulder
    ) / 2.0

    if (
        left_hip is not None
        and right_hip is not None
    ):
        hip_center = (
            left_hip
            + right_hip
        ) / 2.0
    else:
        hip_center = mid_hip

    x_direction = (
        left_shoulder
        - right_shoulder
    )

    up_direction = (
        shoulder_center
        - hip_center
    )

    basis = make_orientation_basis(
        x_direction,
        up_direction
    )

    if basis is None:
        return None

    return {
        "basis": basis,
        "front": basis.col[2].copy(),
        "up": basis.col[1].copy(),
        "neck": neck,
        "left_shoulder": left_shoulder,
        "right_shoulder": right_shoulder,
        "shoulder_center": shoulder_center,
        "hip_center": hip_center,
    }


def get_face_head_basis(
    frame_index
):
    """
    Face70 landmark만 사용한 raw 머리 방향.
    """

    right_eye_center = mapped_average(
        frame_index,
        "face",
        range(36, 42)
    )

    left_eye_center = mapped_average(
        frame_index,
        "face",
        range(42, 48)
    )

    mouth_center = mapped_average(
        frame_index,
        "face",
        (48, 51, 54, 57)
    )

    if (
        right_eye_center is None
        or left_eye_center is None
        or mouth_center is None
    ):
        return None

    eye_center = (
        right_eye_center
        + left_eye_center
    ) / 2.0

    return make_orientation_basis(
        left_eye_center - right_eye_center,
        eye_center - mouth_center
    )


def get_body_head_basis(
    frame_index
):
    """
    BODY25의 양 눈 + Neck으로 만든 보조 머리 방향.
    Face70가 튀는 프레임에서 fallback으로 사용합니다.
    """

    right_eye = mapped_point(
        frame_index,
        "pose",
        POSE["R_EYE"]
    )

    left_eye = mapped_point(
        frame_index,
        "pose",
        POSE["L_EYE"]
    )

    neck = mapped_point(
        frame_index,
        "pose",
        POSE["NECK"]
    )

    if (
        right_eye is None
        or left_eye is None
        or neck is None
    ):
        return None

    eye_center = (
        right_eye
        + left_eye
    ) / 2.0

    return make_orientation_basis(
        left_eye - right_eye,
        eye_center - neck
    )


def basis_angle_deg(
    basis_a,
    basis_b
):
    """
    두 orientation matrix 사이 회전 차이를 degree로 반환합니다.
    """

    if basis_a is None or basis_b is None:
        return None

    qa = basis_a.to_quaternion()
    qb = basis_b.to_quaternion()

    qa.normalize()
    qb.normalize()

    dot = abs(
        qa.w * qb.w
        + qa.x * qb.x
        + qa.y * qb.y
        + qa.z * qb.z
    )

    dot = max(
        -1.0,
        min(1.0, dot)
    )

    return math.degrees(
        2.0 * math.acos(dot)
    )


def find_first_valid_basis(
    getter
):
    for frame_index in range(len(frames)):
        basis = getter(frame_index)

        if basis is not None:
            return basis.copy()

    return None


def build_stable_head_bases():
    """
    SYN Head 안정화.

    1) Face70 방향을 기본 사용
    2) BODY25 방향과 상대 움직임을 비교
    3) Face70가 크게 튀면 BODY25 fallback
    4) 둘 다 튀면 직전 정상 방향 유지

    절대 방향을 직접 비교하지 않고,
    Face/BODY 각각 첫 정상 프레임 대비 delta를 비교합니다.
    """

    face_base = find_first_valid_basis(
        get_face_head_basis
    )

    body_base = find_first_valid_basis(
        get_body_head_basis
    )

    if face_base is None and body_base is None:
        return [None for _ in frames]

    output_base = (
        face_base.copy()
        if face_base is not None
        else body_base.copy()
    )

    stable_bases = []

    face_rejected_count = 0
    body_fallback_count = 0
    hold_previous_count = 0

    max_face_body_diff = 0.0
    max_raw_face_jump = 0.0

    previous_stable = None
    previous_raw_face = None

    for frame_index in range(len(frames)):

        face_basis = get_face_head_basis(
            frame_index
        )

        body_basis = get_body_head_basis(
            frame_index
        )

        face_candidate = None

        if face_basis is not None:
            if face_base is not None:
                face_delta = (
                    face_basis
                    @ face_base.transposed()
                )

                face_candidate = (
                    face_delta
                    @ output_base
                )
            else:
                face_candidate = face_basis.copy()

        body_candidate = None

        if body_basis is not None:
            if body_base is not None:
                body_delta = (
                    body_basis
                    @ body_base.transposed()
                )

                body_candidate = (
                    body_delta
                    @ output_base
                )
            else:
                body_candidate = body_basis.copy()

        # raw Face의 순간 변화 로그
        if (
            face_candidate is not None
            and previous_raw_face is not None
        ):
            raw_face_jump = basis_angle_deg(
                previous_raw_face,
                face_candidate
            )

            if raw_face_jump is not None:
                max_raw_face_jump = max(
                    max_raw_face_jump,
                    raw_face_jump
                )

        if face_candidate is not None:
            previous_raw_face = (
                face_candidate.copy()
            )

        # Face 우선
        candidate = face_candidate

        if candidate is None:
            candidate = body_candidate

            if candidate is not None:
                body_fallback_count += 1

        # Face/BODY 상대 움직임이 너무 다르면 Face reject
        if (
            face_candidate is not None
            and body_candidate is not None
        ):
            face_body_diff = basis_angle_deg(
                face_candidate,
                body_candidate
            )

            if face_body_diff is not None:
                max_face_body_diff = max(
                    max_face_body_diff,
                    face_body_diff
                )

                if (
                    face_body_diff
                    > HEAD_FACE_BODY_MAX_DIFF_DEG
                ):
                    candidate = (
                        body_candidate.copy()
                    )

                    face_rejected_count += 1
                    body_fallback_count += 1

        # 직전 정상 방향에서 순간적으로 크게 튀면 다시 검사
        if (
            candidate is not None
            and previous_stable is not None
        ):
            jump = basis_angle_deg(
                previous_stable,
                candidate
            )

            if (
                jump is not None
                and jump > HEAD_MAX_FRAME_JUMP_DEG
            ):
                body_jump = None

                if body_candidate is not None:
                    body_jump = basis_angle_deg(
                        previous_stable,
                        body_candidate
                    )

                if (
                    body_candidate is not None
                    and body_jump is not None
                    and body_jump
                    <= HEAD_MAX_FRAME_JUMP_DEG
                ):
                    candidate = (
                        body_candidate.copy()
                    )

                    body_fallback_count += 1

                else:
                    candidate = (
                        previous_stable.copy()
                    )

                    hold_previous_count += 1

        if candidate is not None:
            previous_stable = candidate.copy()

            stable_bases.append(
                candidate.copy()
            )

        elif previous_stable is not None:
            stable_bases.append(
                previous_stable.copy()
            )

            hold_previous_count += 1

        else:
            stable_bases.append(None)

    if HEAD_STABILIZE_DEBUG:
        print()
        print("==========================================")
        print("SYN HEAD STABILIZE")
        print("==========================================")
        print(
            "Face/BODY 차이 기준:",
            HEAD_FACE_BODY_MAX_DIFF_DEG,
            "deg"
        )
        print(
            "Frame jump 기준:",
            HEAD_MAX_FRAME_JUMP_DEG,
            "deg"
        )
        print(
            "Head smooth radius:",
            HEAD_SMOOTH_RADIUS,
            "frames"
        )
        print(
            "Head Face motion gain:",
            HEAD_FACE_MOTION_GAIN
        )
        print(
            "Face 이상치 reject:",
            face_rejected_count
        )
        print(
            "BODY fallback:",
            body_fallback_count
        )
        print(
            "이전 Head 유지:",
            hold_previous_count
        )
        print(
            "최대 Face/BODY 차이:",
            round(max_face_body_diff, 3),
            "deg"
        )
        print(
            "최대 raw Face 1-frame jump:",
            round(max_raw_face_jump, 3),
            "deg"
        )
        print("==========================================")

    return stable_bases


def smooth_orientation_bases(
    bases,
    radius
):
    """
    offline 전용 대칭 quaternion smoothing.
    이상치 제거 후 정상 범위 안의 잔떨림을 줄입니다.
    """

    radius = max(
        0,
        int(radius)
    )

    if radius <= 0:
        return [
            basis.copy()
            if basis is not None
            else None
            for basis in bases
        ]

    result = []

    for center_index, center_basis in enumerate(
        bases
    ):

        if center_basis is None:
            result.append(None)
            continue

        center_q = (
            center_basis.to_quaternion()
        )
        center_q.normalize()

        start = max(
            0,
            center_index - radius
        )

        end = min(
            len(bases) - 1,
            center_index + radius
        )

        accum_w = 0.0
        accum_x = 0.0
        accum_y = 0.0
        accum_z = 0.0
        total_weight = 0.0

        for i in range(
            start,
            end + 1
        ):
            basis = bases[i]

            if basis is None:
                continue

            q = basis.to_quaternion()
            q.normalize()

            dot = (
                q.w * center_q.w
                + q.x * center_q.x
                + q.y * center_q.y
                + q.z * center_q.z
            )

            if dot < 0.0:
                q = Quaternion(
                    (
                        -q.w,
                        -q.x,
                        -q.y,
                        -q.z,
                    )
                )

            distance = abs(
                i - center_index
            )

            weight = float(
                radius + 1 - distance
            )

            accum_w += q.w * weight
            accum_x += q.x * weight
            accum_y += q.y * weight
            accum_z += q.z * weight
            total_weight += weight

        if total_weight <= EPS:
            result.append(
                center_basis.copy()
            )
            continue

        q = Quaternion(
            (
                accum_w / total_weight,
                accum_x / total_weight,
                accum_y / total_weight,
                accum_z / total_weight,
            )
        )

        q.normalize()

        result.append(
            q.to_matrix()
        )

    return result


STABLE_HEAD_BASES = None


def get_head_basis(
    frame_index
):
    if STABLE_HEAD_BASES is not None:
        if (
            0 <= frame_index
            < len(STABLE_HEAD_BASES)
        ):
            basis = STABLE_HEAD_BASES[
                frame_index
            ]

            if basis is not None:
                return basis.copy()

    # precompute 전 안전 fallback
    face_basis = get_face_head_basis(
        frame_index
    )

    if face_basis is not None:
        return face_basis

    return get_body_head_basis(
        frame_index
    )


# ============================================================
# Palm Normal
# ============================================================

def make_palm_normal(
    wrist,
    index_mcp,
    middle_mcp,
    little_mcp
):

    long_axis = (
        middle_mcp
        -
        wrist
    )


    across_axis = (
        index_mcp
        -
        little_mcp
    )


    if (
        long_axis.length < EPS
        or across_axis.length < EPS
    ):

        return None


    long_axis.normalize()
    across_axis.normalize()


    normal = across_axis.cross(
        long_axis
    )


    if normal.length < EPS:

        return None


    normal.normalize()

    return normal


# ============================================================
# Target VRM Rest Palm 정보
# ============================================================

TARGET_PALM_NORMAL = {}

TARGET_REST_POINTS = {}


for side in ("L", "R"):

    info = SIDE_INFO[
        side
    ]


    rest_wrist = rig_head(
        info["hand"]
    )

    rest_index = rig_head(
        info["index1"]
    )

    rest_middle = rig_head(
        info["middle1"]
    )

    rest_little = rig_head(
        info["little1"]
    )


    palm_normal = make_palm_normal(
        rest_wrist,
        rest_index,
        rest_middle,
        rest_little
    )


    if palm_normal is None:

        raise RuntimeError(
            f"{side} Target Palm Normal 계산 실패"
        )


    TARGET_PALM_NORMAL[
        side
    ] = palm_normal


    TARGET_REST_POINTS[
        side
    ] = {

        "shoulder": rig_head(
            info["upperarm"]
        ),

        "elbow": rig_head(
            info["lowerarm"]
        ),

        "wrist": rest_wrist,

        "middle": rest_middle,
    }


# ============================================================
# Source 현재 Palm Normal
# ============================================================

def source_palm_normal(
    frame_index,
    side
):

    group_name = SIDE_INFO[
        side
    ][
        "group"
    ]


    wrist = mapped_point(
        frame_index,
        group_name,
        0
    )

    index_mcp = mapped_point(
        frame_index,
        group_name,
        5
    )

    middle_mcp = mapped_point(
        frame_index,
        group_name,
        9
    )

    little_mcp = mapped_point(
        frame_index,
        group_name,
        17
    )


    if (
        wrist is None
        or index_mcp is None
        or middle_mcp is None
        or little_mcp is None
    ):

        return None


    return make_palm_normal(
        wrist,
        index_mcp,
        middle_mcp,
        little_mcp
    )


# ============================================================
# 몸통 / 머리 / 어깨 첫 프레임 기준
# ============================================================
# 첫 프레임을 VRM의 neutral(rest) 자세 기준으로 잡습니다.
# 따라서 특정 WORD의 촬영 시작 자세가 조금 달라도 첫 프레임에서
# 갑자기 몸/머리가 돌아가지 않습니다.

# SYN 전체 프레임 Head 방향을 먼저 안정화합니다.
STABLE_HEAD_BASES = build_stable_head_bases()

# 이상치 제거 후 남는 잔떨림을 quaternion smoothing으로 줄입니다.
STABLE_HEAD_BASES = smooth_orientation_bases(
    STABLE_HEAD_BASES,
    HEAD_SMOOTH_RADIUS
)

BASE_TORSO_INFO = get_torso_frame_info(0)

if BASE_TORSO_INFO is None:
    raise RuntimeError(
        "첫 프레임의 Torso 기준 계산 실패"
    )

BASE_TORSO_BASIS = (
    BASE_TORSO_INFO["basis"]
    .copy()
)

BASE_HEAD_BASIS = get_head_basis(0)

if BASE_HEAD_BASIS is None:
    # 머리 landmark가 불완전할 때는 첫 몸통 방향을 중립 머리 방향으로 사용
    BASE_HEAD_BASIS = BASE_TORSO_BASIS.copy()

BASE_SHOULDER_DIRECTION = {
    "L": (
        BASE_TORSO_INFO["left_shoulder"]
        - BASE_TORSO_INFO["neck"]
    ),
    "R": (
        BASE_TORSO_INFO["right_shoulder"]
        - BASE_TORSO_INFO["neck"]
    ),
}

BASE_SHOULDER_FRONT = (
    BASE_TORSO_INFO["front"]
    .copy()
)


# ============================================================
# Bone Rest Rotation
# ============================================================

def get_bone_rest_rotation(
    bone_name
):

    rotation = (
        arm.data.bones[
            bone_name
        ]
        .matrix_local
        .to_3x3()
        .normalized()
    )

    return rotation


# ============================================================
# Rest semantic -> Current semantic
#
# 그 rotation을 VRM Bone rest rotation에 적용
# ============================================================

def make_desired_rotation(
    bone_name,
    rest_direction,
    rest_hint,
    current_direction,
    current_hint
):

    rest_basis = make_semantic_basis(
        rest_direction,
        rest_hint
    )


    current_basis = make_semantic_basis(
        current_direction,
        current_hint
    )


    if (
        rest_basis is None
        or current_basis is None
    ):

        return None


    delta = (
        current_basis
        @
        rest_basis.transposed()
    )


    bone_rest_rotation = (
        get_bone_rest_rotation(
            bone_name
        )
    )


    desired_rotation = (
        delta
        @
        bone_rest_rotation
    )


    return desired_rotation



# ============================================================
# Finger Rotation Precompute + 안정화
# ============================================================

def build_rest_clearance_weights():
    """Recognize only prefix/suffix low-hand poses similar to their endpoint.

    Avoid moving low signs in the middle of a clip. Both hands share one
    translation; relative wrist spacing and finger orientations are preserved.
    A raised-hand start/end is never treated as a rest pose.
    """
    weights = [0.0] * len(frames)
    width = max(target_shoulder_width, EPS)
    signatures = []
    for i in range(len(frames)):
        points = []
        for side in ("L", "R"):
            info = SIDE_INFO[side]
            s = mapped_point(i, "pose", info["shoulder_pose"])
            w = mapped_point(i, "pose", info["wrist_pose"])
            if s is None or w is None:
                points = []
                break
            points.append(w - s)
        signatures.append(points if len(points) == 2 else None)
    for indices in (range(len(frames)), range(len(frames) - 1, -1, -1)):
        ref = signatures[indices[0]]
        if ref is None or min(-v.dot(target_up) / width for v in ref) < 0.90:
            continue
        for i in indices:
            sig = signatures[i]
            if sig is None:
                break
            distance = max((a - b).length for a, b in zip(sig, ref)) / width
            t = max(0.0, min(1.0, (REST_MATCH_ZERO - distance) /
                              (REST_MATCH_ZERO - REST_MATCH_FULL)))
            weight = t * t * (3.0 - 2.0 * t)
            if weight == 0.0:
                break
            weights[i] = max(weights[i], weight)
    return weights


REST_CLEARANCE_WEIGHTS = build_rest_clearance_weights()
TARGET_MEAN_PALM_LENGTH = sum(
    (TARGET_REST_POINTS[side]["middle"] - TARGET_REST_POINTS[side]["wrist"]).length
    for side in ("L", "R")
) / 2.0
REST_FORWARD_DISTANCE = REST_FORWARD_PALM_LENGTHS * TARGET_MEAN_PALM_LENGTH
HAND_FORWARD_DISTANCE = HAND_FORWARD_PALM_LENGTHS * TARGET_MEAN_PALM_LENGTH


def solve_two_bone_positions(root, goal, pole_hint, upper_length, lower_length,
                             previous_pole=None):
    """Analytic two-bone IK in armature space; no bone stretching.

    pole_hint is a direction from source shoulder toward source elbow.
    An unreachable goal is projected into the reachable spherical shell.
    The previous pole is used only near a degenerate source elbow plane.
    """
    if min(upper_length, lower_length) <= EPS:
        raise ValueError("Arm IK requires nonzero segment lengths")
    delta = goal - root
    distance = delta.length
    if distance > EPS:
        axis = delta.normalized()
    elif pole_hint.length > EPS:
        axis = pole_hint.normalized()
    else:
        axis = Vector((0.0, 0.0, 1.0))
    margin = min(upper_length, lower_length) * 1e-5
    reach = max(abs(upper_length - lower_length) + margin,
                min(upper_length + lower_length - margin, distance))
    pole = pole_hint - axis * pole_hint.dot(axis)
    if pole.length < max(EPS, pole_hint.length * 0.03):
        if previous_pole is not None:
            pole = previous_pole - axis * previous_pole.dot(axis)
        if pole.length < EPS:
            candidate = min((Vector((1, 0, 0)), Vector((0, 1, 0)),
                             Vector((0, 0, 1))), key=lambda v: abs(v.dot(axis)))
            pole = candidate - axis * candidate.dot(axis)
    pole.normalize()
    along = (upper_length ** 2 - lower_length ** 2 + reach ** 2) / (2 * reach)
    height = math.sqrt(max(0.0, upper_length ** 2 - along ** 2))
    elbow = root + axis * along + pole * height
    wrist = root + axis * reach
    return elbow, wrist, pole, abs(reach - distance)


def finger_minimum_swing(from_direction, to_direction, axis_hint):
    """Shortest swing; an explicit parent axis resolves exact 180-degree ambiguity."""
    if from_direction.length < EPS or to_direction.length < EPS:
        return None
    a = from_direction.normalized()
    b = to_direction.normalized()
    dot = max(-1.0, min(1.0, a.dot(b)))
    if dot > 1.0 - 1e-14:
        return Matrix.Identity(3)
    if dot < -1.0 + 1e-7:
        axis = axis_hint - a * axis_hint.dot(a)
        if axis.length < EPS:
            candidate = min(
                (Vector((1, 0, 0)), Vector((0, 1, 0)), Vector((0, 0, 1))),
                key=lambda v: abs(v.dot(a)),
            )
            axis = candidate - a * candidate.dot(a)
        half_turn = Quaternion(axis.normalized(), math.pi).to_matrix()
        # Also align near-antiparallel inputs exactly after the stable half-turn.
        correction = (half_turn @ a).rotation_difference(b).to_matrix()
        return correction @ half_turn
    return a.rotation_difference(b).to_matrix()


def build_chain_finger_raw_rotations():
    """Palm -> proximal -> intermediate -> distal, in armature space.

    Each child inherits its parent's rotation relative to rest, then adds
    only the minimum swing required to point at its source segment.
    This preserves target rest roll and source segment directions without
    independently projecting the palm normal onto each finger segment.
    Thumb uses the same chain, with its own target rest orientation.
    """
    result = {
        spec[0]: [None] * len(frames)
        for side in ("L", "R") for spec in FINGER_SPECS[side]
    }
    for side in ("L", "R"):
        info = SIDE_INFO[side]
        rest = TARGET_REST_POINTS[side]
        rest_palm = make_semantic_basis(
            rest["middle"] - rest["wrist"], TARGET_PALM_NORMAL[side]
        )
        if rest_palm is None:
            raise RuntimeError(f"{side}: invalid target rest palm")
        specs = FINGER_SPECS[side]
        for frame_index in range(len(frames)):
            wrist = mapped_point(frame_index, info["group"], 0)
            middle = mapped_point(frame_index, info["group"], 9)
            normal = source_palm_normal(frame_index, side)
            if wrist is None or middle is None or normal is None:
                continue
            current_palm = make_semantic_basis(middle - wrist, normal)
            if current_palm is None:
                continue
            palm_delta = current_palm @ rest_palm.transposed()
            for chain_start in range(0, len(specs), 3):
                parent_delta = palm_delta.copy()
                for bone_name, group, start, end in specs[chain_start:chain_start + 3]:
                    p0 = mapped_point(frame_index, group, start)
                    p1 = mapped_point(frame_index, group, end)
                    if p0 is None or p1 is None:
                        break  # descendants require a valid parent
                    direction = p1 - p0
                    rest_direction = rig_tail(bone_name) - rig_head(bone_name)
                    rest_rotation = get_bone_rest_rotation(bone_name)
                    inherited = parent_delta @ rest_rotation
                    swing = finger_minimum_swing(
                        parent_delta @ rest_direction,
                        direction,
                        inherited @ Vector((1, 0, 0)),
                    )
                    if swing is None:
                        break
                    desired = swing @ inherited
                    result[bone_name][frame_index] = desired
                    parent_delta = desired @ rest_rotation.transposed()
    return result


def build_stable_finger_rotations():
    """V5 chain solver, followed by V4's mild temporal smoothing.

    Re-aim after smoothing so segment directions are preserved.
    Missing rotations alone are filled; large valid bends are not rejected.
    """

    chain_raw = build_chain_finger_raw_rotations()

    result = {}

    total_missing = 0
    fast_motion_frames = 0
    smoothed_frames = 0

    for side in ("L", "R"):

        target_palm_normal = (
            TARGET_PALM_NORMAL[
                side
            ]
        )

        for (
            bone_name,
            finger_group,
            start_index,
            end_index
        ) in FINGER_SPECS[
            side
        ]:

            raw_rotations = chain_raw[bone_name]
            total_missing += sum(r is None for r in raw_rotations)

            # ----------------------------------------------------
            # 결측 frame만 이전/다음 정상 rotation으로 메움
            # 정상적인 큰 회전은 절대 reject하지 않습니다.
            # ----------------------------------------------------

            filled = [
                rotation.copy()
                if rotation is not None
                else None
                for rotation in raw_rotations
            ]

            # forward fill
            previous = None

            for i in range(len(filled)):
                if filled[i] is not None:
                    previous = filled[i].copy()
                elif previous is not None:
                    filled[i] = previous.copy()

            # backward fill
            following = None

            for i in range(
                len(filled) - 1,
                -1,
                -1
            ):
                if filled[i] is not None:
                    following = filled[i].copy()
                elif following is not None:
                    filled[i] = following.copy()

            # ----------------------------------------------------
            # 약한 3-frame quaternion smoothing 후보 생성
            # ----------------------------------------------------

            smooth_candidates = (
                smooth_orientation_bases(
                    filled,
                    FINGER_SMOOTH_RADIUS
                )
            )

            adaptive = []

            for i, raw_rotation in enumerate(
                filled
            ):

                if raw_rotation is None:
                    adaptive.append(None)
                    continue

                smooth_rotation = (
                    smooth_candidates[i]
                )

                if smooth_rotation is None:
                    adaptive.append(
                        raw_rotation.copy()
                    )
                    continue

                # 현재 프레임 주변에서 실제로 얼마나 빠르게
                # finger rotation이 변하고 있는지 측정
                local_motion = 0.0

                if (
                    i > 0
                    and filled[i - 1] is not None
                ):
                    angle_prev = basis_angle_deg(
                        filled[i - 1],
                        raw_rotation
                    )

                    if angle_prev is not None:
                        local_motion = max(
                            local_motion,
                            angle_prev
                        )

                if (
                    i + 1 < len(filled)
                    and filled[i + 1] is not None
                ):
                    angle_next = basis_angle_deg(
                        raw_rotation,
                        filled[i + 1]
                    )

                    if angle_next is not None:
                        local_motion = max(
                            local_motion,
                            angle_next
                        )

                # 빠른 굽힘/펴기 구간은 거의 원본 보존
                if (
                    local_motion
                    >= FINGER_FAST_MOTION_DEG
                ):
                    strength = (
                        FINGER_FAST_MOTION_STRENGTH
                    )
                    fast_motion_frames += 1

                else:
                    strength = (
                        FINGER_SMOOTH_STRENGTH
                    )

                final_rotation = blend_rotations(
                    raw_rotation,
                    smooth_rotation,
                    strength
                )

                # Smoothing may alter swing. Restore the source direction,
                # retaining only its mild effect on roll.
                rest_rotation = get_bone_rest_rotation(bone_name)
                local_direction = rest_rotation.transposed() @ (
                    rig_tail(bone_name) - rig_head(bone_name)
                )
                correction = finger_minimum_swing(
                    final_rotation @ local_direction,
                    raw_rotation @ local_direction,
                    final_rotation @ Vector((1, 0, 0)),
                )
                if correction is not None:
                    final_rotation = correction @ final_rotation
                adaptive.append(final_rotation)

                smoothed_frames += 1

            result[
                bone_name
            ] = adaptive

    if FINGER_STABILIZE_DEBUG:
        print()
        print("==========================================")
        print("SYN FINGER RETARGET v5 (CHAIN / MINIMUM SWING)")
        print("==========================================")
        print(
            "Finger smooth radius:",
            FINGER_SMOOTH_RADIUS,
            "frames"
        )
        print(
            "Normal smooth strength:",
            FINGER_SMOOTH_STRENGTH
        )
        print(
            "Fast motion threshold:",
            FINGER_FAST_MOTION_DEG,
            "deg/frame"
        )
        print(
            "Fast motion smooth strength:",
            FINGER_FAST_MOTION_STRENGTH
        )
        print(
            "빠른 손가락 동작 프레임:",
            fast_motion_frames
        )
        print(
            "처리된 Finger rotation:",
            smoothed_frames
        )
        print(
            "Finger rotation missing/fallback:",
            total_missing
        )
        print("==========================================")

    return result


# 실제 animation loop에서는 이 cache를 사용합니다.
STABLE_FINGER_ROTATIONS = (
    build_stable_finger_rotations()
)


# ============================================================
# Quaternion 연속성
# ============================================================

last_quaternion = {}


def ensure_quaternion_continuity(
    bone_name,
    quaternion
):

    q = quaternion.copy()
    q.normalize()


    previous = last_quaternion.get(
        bone_name
    )


    if previous is not None:

        dot = (
            q.w * previous.w
            +
            q.x * previous.x
            +
            q.y * previous.y
            +
            q.z * previous.z
        )


        if dot < 0.0:

            q = Quaternion(
                (
                    -q.w,
                    -q.x,
                    -q.y,
                    -q.z,
                )
            )


    last_quaternion[
        bone_name
    ] = q.copy()


    return q


# ============================================================
# 원하는 Absolute Rotation을
# PoseBone Local Basis Rotation으로 변환
# ============================================================

def apply_absolute_rotation(
    bone_name,
    desired_rotation,
    frame_number
):

    pose_bone = arm.pose.bones[
        bone_name
    ]


    parent_pose = pose_bone.parent


    if parent_pose is None:

        base_matrix = (
            pose_bone
            .bone
            .matrix_local
            .copy()
        )


    else:

        parent_rest = (
            parent_pose
            .bone
            .matrix_local
        )


        child_rest = (
            pose_bone
            .bone
            .matrix_local
        )


        rest_relative = (
            parent_rest.inverted()
            @
            child_rest
        )


        base_matrix = (
            parent_pose.matrix
            @
            rest_relative
        )


    base_rotation = (
        base_matrix
        .to_3x3()
        .normalized()
    )


    local_rotation = (
        base_rotation.inverted()
        @
        desired_rotation
    )


    quaternion = (
        local_rotation
        .to_quaternion()
    )


    quaternion = ensure_quaternion_continuity(
        bone_name,
        quaternion
    )


    pose_bone.rotation_mode = "QUATERNION"

    pose_bone.location = (
        0.0,
        0.0,
        0.0
    )

    pose_bone.scale = (
        1.0,
        1.0,
        1.0
    )

    pose_bone.rotation_quaternion = (
        quaternion
    )


    # 부모 pose 변화를 즉시 child 계산에 반영
    bpy.context.view_layer.update()


    pose_bone.keyframe_insert(
        data_path="rotation_quaternion",
        frame=frame_number
    )


    return True


# ============================================================
# 이전 테스트 Constraint / Empty 제거
# ============================================================

print()
print(
    f"기존 {WORD_ID} 테스트 Constraint 정리..."
)


for pose_bone in arm.pose.bones:

    remove_constraints = [

        constraint

        for constraint in pose_bone.constraints

        if constraint.name.startswith(
            PREFIX
        )
    ]


    for constraint in remove_constraints:

        pose_bone.constraints.remove(
            constraint
        )


for obj in list(
    bpy.data.objects
):

    if obj.name.startswith(
        PREFIX + "_TGT_"
    ):

        bpy.data.objects.remove(
            obj,
            do_unlink=True
        )


old_collection = bpy.data.collections.get(
    PREFIX + "_TARGETS"
)


if old_collection is not None:

    bpy.data.collections.remove(
        old_collection
    )


# ============================================================
# Pose 초기화
# ============================================================

RESET_BONES = list(
    dict.fromkeys(
        TARGET_BONES
    )
)


for bone_name in RESET_BONES:

    pose_bone = arm.pose.bones.get(
        bone_name
    )

    if pose_bone is not None:

        pose_bone.matrix_basis = (
            Matrix.Identity(4)
        )


bpy.context.view_layer.update()


# ============================================================
# 새 Action
# ============================================================

arm.animation_data_create()


old_action = bpy.data.actions.get(
    ACTION_NAME
)


if old_action is not None:

    if arm.animation_data.action == old_action:

        arm.animation_data.action = None


    bpy.data.actions.remove(
        old_action
    )


action = bpy.data.actions.new(
    ACTION_NAME
)


arm.animation_data.action = action


# ============================================================
# Scene
# ============================================================

scene = bpy.context.scene


scene.render.fps = fps


frame_numbers = [

    int(
        frame[
            "frame"
        ]
    )

    for frame in frames
]


scene.frame_start = min(
    frame_numbers
)

scene.frame_end = max(
    frame_numbers
)


# ============================================================
# Animation 생성
# ============================================================

print()
print(
    "Bone Rotation Animation 생성 중..."
)


keyframe_count = 0
skip_count = 0


for frame_index, frame_data in enumerate(
    frames
):

    frame_number = int(
        frame_data[
            "frame"
        ]
    )


    scene.frame_set(
        frame_number
    )


    # ========================================================
    # TORSO / NECK / HEAD
    # ========================================================

    torso_info = get_torso_frame_info(
        frame_index
    )

    if torso_info is not None:

        # 첫 프레임 몸통 기준 -> 현재 몸통 방향의 absolute delta
        torso_delta = (
            torso_info["basis"]
            @ BASE_TORSO_BASIS.transposed()
        )

        # ----------------------------------------------------
        # Spine / Chest / UpperChest
        # ----------------------------------------------------
        # 같은 torso delta를 단계별로 나눠서 적용합니다.
        # UpperChest가 최종 몸통 방향에 도달하고, 부모 Bone은 일부를 분담합니다.

        for torso_bone, factor in TORSO_BONE_FACTORS.items():

            partial_delta = rotation_fraction(
                torso_delta,
                factor
            )

            desired = (
                partial_delta
                @ get_bone_rest_rotation(
                    torso_bone
                )
            )

            apply_absolute_rotation(
                torso_bone,
                desired,
                frame_number
            )

            keyframe_count += 1


        # ----------------------------------------------------
        # Head orientation
        # ----------------------------------------------------

        head_basis = get_head_basis(
            frame_index
        )

        if head_basis is not None:

            raw_head_delta = (
                head_basis
                @ BASE_HEAD_BASIS.transposed()
            )

            # Face 기반 머리 회전을 그대로 100% 쓰지 않고
            # 몸통 회전과 섞어 정상 범위의 잔떨림을 줄입니다.
            head_delta = blend_rotations(
                torso_delta,
                raw_head_delta,
                HEAD_FACE_MOTION_GAIN
            )

            # Neck은 몸통과 머리 사이의 중간 방향을 담당
            neck_delta = blend_rotations(
                torso_delta,
                head_delta,
                NECK_HEAD_BLEND
            )

            neck_desired = (
                neck_delta
                @ get_bone_rest_rotation(
                    "J_Bip_C_Neck"
                )
            )

            apply_absolute_rotation(
                "J_Bip_C_Neck",
                neck_desired,
                frame_number
            )

            keyframe_count += 1


            # Head는 Face landmark가 가리키는 최종 머리 방향
            head_desired = (
                head_delta
                @ get_bone_rest_rotation(
                    "J_Bip_C_Head"
                )
            )

            apply_absolute_rotation(
                "J_Bip_C_Head",
                head_desired,
                frame_number
            )

            keyframe_count += 1

        else:
            skip_count += 2


        # ----------------------------------------------------
        # Left / Right Shoulder
        # ----------------------------------------------------
        # OpenPose에는 쇄골 안쪽 점은 없으므로
        # Neck -> Shoulder 벡터의 변화로 Shoulder Bone을 추정합니다.

        for side, shoulder_bone, point_name in (
            ("L", "J_Bip_L_Shoulder", "left_shoulder"),
            ("R", "J_Bip_R_Shoulder", "right_shoulder"),
        ):

            current_direction = (
                torso_info[point_name]
                - torso_info["neck"]
            )

            desired = make_desired_rotation(
                shoulder_bone,
                BASE_SHOULDER_DIRECTION[side],
                BASE_SHOULDER_FRONT,
                current_direction,
                torso_info["front"]
            )

            if desired is not None:

                # Shoulder는 추정값이라 과도한 회전을 조금 줄입니다.
                shoulder_rest = get_bone_rest_rotation(
                    shoulder_bone
                )

                shoulder_delta = (
                    desired
                    @ shoulder_rest.transposed()
                )

                shoulder_delta = rotation_fraction(
                    shoulder_delta,
                    SHOULDER_ROTATION_GAIN
                )

                desired = (
                    shoulder_delta
                    @ shoulder_rest
                )

                apply_absolute_rotation(
                    shoulder_bone,
                    desired,
                    frame_number
                )

                keyframe_count += 1

            else:
                skip_count += 1

    else:
        # Torso 정보가 없는 프레임에서는 기존 팔/손 로직은 계속 진행
        skip_count += 7


    # ========================================================
    # LEFT / RIGHT ARM / HAND / FINGERS
    # ========================================================

    for side in (
        "L",
        "R"
    ):

        info = SIDE_INFO[
            side
        ]


        group_name = info[
            "group"
        ]


        # ----------------------------------------------------
        # 현재 Source 관절
        # ----------------------------------------------------

        shoulder = mapped_point(
            frame_index,
            "pose",
            info["shoulder_pose"]
        )

        elbow = mapped_point(
            frame_index,
            "pose",
            info["elbow_pose"]
        )

        wrist = mapped_point(
            frame_index,
            "pose",
            info["wrist_pose"]
        )

        hand_middle = mapped_point(
            frame_index,
            group_name,
            9
        )


        current_palm_normal = (
            source_palm_normal(
                frame_index,
                side
            )
        )


        if current_palm_normal is None:

            current_palm_normal = (
                TARGET_PALM_NORMAL[
                    side
                ]
            )


        target_palm_normal = (
            TARGET_PALM_NORMAL[
                side
            ]
        )


        rest = TARGET_REST_POINTS[
            side
        ]

        # Keep hand orientation tied to its source wrist, even if IK clamps
        # an unreachable arm goal. Do not use the solved wrist for this vector.
        source_hand_wrist = mapped_point(frame_index, group_name, 0)
        if source_hand_wrist is None:
            source_hand_wrist = wrist

        if (ARM_POSITION_IK and shoulder is not None
                and elbow is not None and wrist is not None):
            bpy.context.view_layer.update()
            actual_root = arm.pose.bones[info["upperarm"]].matrix.translation.copy()
            upper_length = (rest["elbow"] - rest["shoulder"]).length
            lower_length = (rest["wrist"] - rest["elbow"]).length
            # Shift the IK goal only: source palm direction and finger bends
            # are retained. Both hands receive the same desired translation;
            # unreachable goals can still be clamped independently by arm IK.
            forward_distance = HAND_FORWARD_DISTANCE
            if REST_HAND_CLEARANCE:
                forward_distance += (
                    REST_FORWARD_DISTANCE * REST_CLEARANCE_WEIGHTS[frame_index]
                )
            if abs(forward_distance) > EPS:
                front = torso_info["front"] if torso_info is not None else target_front
                wrist = wrist + front.normalized() * forward_distance
            elbow, wrist, pole, goal_error = solve_two_bone_positions(
                actual_root, wrist, elbow - shoulder,
                upper_length, lower_length, ARM_IK_PREVIOUS_POLE.get(side)
            )
            shoulder = actual_root
            ARM_IK_PREVIOUS_POLE[side] = pole
            ARM_IK_CLAMPED += int(goal_error > 1e-6)

        # ====================================================
        # UpperArm
        # ====================================================

        if (
            shoulder is not None
            and elbow is not None
        ):

            rest_direction = (
                rest["elbow"]
                -
                rest["shoulder"]
            )


            current_direction = (
                elbow
                -
                shoulder
            )


            desired = make_desired_rotation(
                info["upperarm"],
                rest_direction,
                target_front,
                current_direction,
                target_front
            )


            if desired is not None:

                apply_absolute_rotation(
                    info["upperarm"],
                    desired,
                    frame_number
                )

                keyframe_count += 1

            else:

                skip_count += 1


        # ====================================================
        # LowerArm
        # ====================================================

        if (
            elbow is not None
            and wrist is not None
        ):

            rest_direction = (
                rest["wrist"]
                -
                rest["elbow"]
            )


            current_direction = (
                wrist
                -
                elbow
            )


            desired = make_desired_rotation(
                info["lowerarm"],
                rest_direction,
                target_palm_normal,
                current_direction,
                current_palm_normal
            )


            if desired is not None:

                apply_absolute_rotation(
                    info["lowerarm"],
                    desired,
                    frame_number
                )

                keyframe_count += 1

            else:

                skip_count += 1


        # ====================================================
        # Hand
        # ====================================================

        if ARM_POSITION_IK and wrist is not None:
            bpy.context.view_layer.update()
            actual_wrist = arm.pose.bones[info["hand"]].matrix.translation
            ARM_IK_MAX_ERROR = max(ARM_IK_MAX_ERROR, (actual_wrist - wrist).length)

        if (
            source_hand_wrist is not None
            and hand_middle is not None
        ):

            rest_direction = (
                rest["middle"]
                -
                rest["wrist"]
            )


            current_direction = (
                hand_middle
                -
                source_hand_wrist
            )


            desired = make_desired_rotation(
                info["hand"],
                rest_direction,
                target_palm_normal,
                current_direction,
                current_palm_normal
            )


            if desired is not None:

                apply_absolute_rotation(
                    info["hand"],
                    desired,
                    frame_number
                )

                keyframe_count += 1

            else:

                skip_count += 1


        # ====================================================
        # Fingers
        # ====================================================

        for (
            bone_name,
            finger_group,
            start_index,
            end_index
        ) in FINGER_SPECS[
            side
        ]:

            start_point = mapped_point(
                frame_index,
                finger_group,
                start_index
            )


            end_point = mapped_point(
                frame_index,
                finger_group,
                end_index
            )


            if (
                start_point is None
                or end_point is None
            ):

                skip_count += 1
                continue


            current_direction = (
                end_point
                -
                start_point
            )


            rest_direction = (
                rig_tail(
                    bone_name
                )
                -
                rig_head(
                    bone_name
                )
            )


            # V5: use parent-transported finger rotations.
            # Mild roll smoothing preserves source segment directions.
            finger_rotations = (
                STABLE_FINGER_ROTATIONS.get(
                    bone_name
                )
            )

            desired = None

            if (
                finger_rotations is not None
                and frame_index
                < len(finger_rotations)
            ):
                desired = (
                    finger_rotations[
                        frame_index
                    ]
                )


            if desired is None:

                skip_count += 1
                continue


            apply_absolute_rotation(
                bone_name,
                desired,
                frame_number
            )


            keyframe_count += 1


# ============================================================
# 첫 프레임
# ============================================================

scene.frame_set(
    scene.frame_start
)


# ============================================================
# Armature 선택
# ============================================================

bpy.ops.object.select_all(
    action="DESELECT"
)


arm.select_set(
    True
)


bpy.context.view_layer.objects.active = (
    arm
)


# ============================================================
# 완료
# ============================================================

print()
print("==========================================")
print(f"{WORD_ID} BODY RETARGET 완료")
print("V6 arm IK: unreachable goals clamped =", ARM_IK_CLAMPED)
print("V6 arm IK: max evaluated wrist residual (armature units) =", ARM_IK_MAX_ERROR)
if ARM_POSITION_IK and ARM_IK_MAX_ERROR > 0.005:
    print("V6: wrist residual is large; inspect rig constraints, scale and bone offsets.")
print("==========================================")

print()
print(
    "Frame:",
    scene.frame_start,
    "~",
    scene.frame_end
)

print(
    "FPS:",
    scene.render.fps
)

print(
    "Action:",
    ACTION_NAME
)

print(
    "Keyframe 처리:",
    keyframe_count
)

print(
    "Skip:",
    skip_count
)

print()
print(
    "UpperArm / LowerArm:"
)

print(
    " - 관절 방향으로 Bone 회전"
)

print()
print(
    "Hand:"
)

print(
    " - Wrist -> Middle 방향"
)

print(
    " - Index / Little을 이용한 Palm Normal 반영"
)

print()
print(
    "Finger:"
)

print(
    " - 각 마디별 3D 방향 + adaptive Finger quaternion smoothing 적용"
)

print()
print(
    "Torso / Shoulder / Neck / Head:"
)

print(
    " - 양 어깨 + Hip 계열점으로 몸통 방향 추정"
)

print(
    " - Neck -> Shoulder 방향으로 어깨 회전 추정"
)

print(
    " - Face70 + BODY25 이상치 제거 + quaternion smoothing으로 Neck / Head 안정화"
)

print()
print(
    "주의:"
)

print(
    " - Spine/Shoulder는 직접 회전 데이터가 아니라 keypoint 기하로 추정"
)

print()
print(
    "Layout으로 돌아가서 Spacebar로 재생하세요."
)

print(
    "=========================================="
)


# ============================================================
# BODY 완료 -> FACE RETARGET 시작
# ============================================================
print()
print("============================================================")
print(f"{WORD_ID} FACE RETARGET 시작")
print("============================================================")

# ============================================================
# 사용할 Shape Key
# ============================================================

SHAPE = {

    "EYE_CLOSE_R": "Fcl_EYE_Close_R",
    "EYE_CLOSE_L": "Fcl_EYE_Close_L",

    "BROW_UP": "Fcl_BRW_Surprised",
    "BROW_DOWN": "Fcl_BRW_Angry",

    "MOUTH_OPEN": "Fcl_MTH_A",
    "MOUTH_LARGE": "Fcl_MTH_Large",
    "MOUTH_SMALL": "Fcl_MTH_Small",
}


# ============================================================
# Helper
# ============================================================

def clamp(value, minimum=0.0, maximum=1.0):

    return max(
        minimum,
        min(maximum, value)
    )


def percentile(values, amount):

    values = sorted(values)

    if not values:
        return 0.0

    if len(values) == 1:
        return values[0]

    position = (
        len(values) - 1
    ) * amount

    low = int(position)

    high = min(
        low + 1,
        len(values) - 1
    )

    fraction = (
        position - low
    )

    return (
        values[low] * (1.0 - fraction)
        +
        values[high] * fraction
    )


def mean_vector(points):

    result = Vector(
        (0.0, 0.0, 0.0)
    )

    for point in points:
        result += point

    result /= len(points)

    return result


def mean_number(values):

    if not values:
        return 0.0

    return sum(values) / len(values)


# ============================================================
# Motion JSON 읽기
# ============================================================

if not MOTION_JSON_PATH.exists():

    raise FileNotFoundError(
        "\nMotion JSON 없음:\n"
        + str(MOTION_JSON_PATH)
    )


with open(
    MOTION_JSON_PATH,
    "r",
    encoding="utf-8"
) as f:

    motion_data = json.load(f)


frames = motion_data.get(
    "frames",
    []
)


if not frames:

    raise RuntimeError(
        "frames 데이터가 없습니다."
    )


frames = sorted(
    frames,
    key=lambda x: int(x["frame"])
)


fps = int(
    motion_data.get(
        "fps",
        30
    )
)


print()
print("========================================")
print(f"{WORD_ID} FACE RETARGET")
print("========================================")

print()
print("Frame:", len(frames))
print("FPS:", fps)


# ============================================================
# Face Object
# ============================================================

face_object = bpy.data.objects.get(
    FACE_OBJECT_NAME
)


if face_object is None:

    raise RuntimeError(
        f"'{FACE_OBJECT_NAME}' Object를 찾을 수 없습니다."
    )


if face_object.type != "MESH":

    raise RuntimeError(
        "Face Object가 Mesh가 아닙니다."
    )


key_data = face_object.data.shape_keys


if key_data is None:

    raise RuntimeError(
        "Face에 Shape Key가 없습니다."
    )


key_blocks = key_data.key_blocks


# ============================================================
# Shape Key 존재 확인
# ============================================================

missing = []


for key_name in SHAPE.values():

    if key_name not in key_blocks:

        missing.append(
            key_name
        )


if missing:

    print()
    print("없는 Shape Key:")

    for name in missing:
        print(" -", name)

    raise RuntimeError(
        "필요한 Shape Key가 없습니다."
    )


print()
print(
    "사용 Shape Key:",
    len(SHAPE),
    "개 확인 완료"
)


# ============================================================
# Face point 읽기
#
# OpenPose Face 70
#
# 0~16   턱선
# 17~21  오른쪽 눈썹
# 22~26  왼쪽 눈썹
# 27~35  코
# 36~41  오른쪽 눈
# 42~47  왼쪽 눈
# 48~59  바깥 입술
# 60~67  안쪽 입술
# ============================================================

def get_face_point(
    frame_data,
    index
):

    points = frame_data.get(
        "face",
        []
    )

    if index >= len(points):

        return None

    point = points[index]

    if point is None:
        return None

    if len(point) < 3:
        return None

    try:

        return Vector(
            (
                float(point[0]),
                float(point[1]),
                float(point[2]),
            )
        )

    except Exception:

        return None


# ============================================================
# 한 프레임의 얼굴 Metric
# ============================================================

def calculate_metrics(
    frame_data
):

    points = {}


    needed_indices = list(
        range(17, 68)
    )


    for index in needed_indices:

        point = get_face_point(
            frame_data,
            index
        )

        if point is None:

            return None

        points[index] = point


    # --------------------------------------------------------
    # 눈 중심
    # --------------------------------------------------------

    right_eye_center = mean_vector(
        [
            points[i]
            for i in range(36, 42)
        ]
    )


    left_eye_center = mean_vector(
        [
            points[i]
            for i in range(42, 48)
        ]
    )


    eye_distance = (
        left_eye_center
        -
        right_eye_center
    ).length


    if eye_distance < EPS:

        return None


    # --------------------------------------------------------
    # 눈 openness
    #
    # 오른눈:
    # width = 36 ↔ 39
    # height = 37↔41, 38↔40
    # --------------------------------------------------------

    right_eye_width = (
        points[36]
        -
        points[39]
    ).length


    right_eye_height = (
        (
            points[37]
            -
            points[41]
        ).length
        +
        (
            points[38]
            -
            points[40]
        ).length
    ) / 2.0


    left_eye_width = (
        points[42]
        -
        points[45]
    ).length


    left_eye_height = (
        (
            points[43]
            -
            points[47]
        ).length
        +
        (
            points[44]
            -
            points[46]
        ).length
    ) / 2.0


    right_eye_open = (
        right_eye_height
        /
        max(
            right_eye_width,
            EPS
        )
    )


    left_eye_open = (
        left_eye_height
        /
        max(
            left_eye_width,
            EPS
        )
    )


    # --------------------------------------------------------
    # 입
    # --------------------------------------------------------

    mouth_width = (
        points[48]
        -
        points[54]
    ).length / eye_distance


    # 안쪽 입술 opening
    inner_open = (
        (
            points[62]
            -
            points[66]
        ).length
        +
        (
            points[63]
            -
            points[65]
        ).length
    ) / 2.0


    # 바깥 입술 opening
    outer_open = (
        (
            points[50]
            -
            points[58]
        ).length
        +
        (
            points[51]
            -
            points[57]
        ).length
        +
        (
            points[52]
            -
            points[56]
        ).length
    ) / 3.0


    mouth_open = (
        inner_open * 0.7
        +
        outer_open * 0.3
    ) / eye_distance


    # --------------------------------------------------------
    # 얼굴 위쪽 방향
    #
    # head rotation 영향을 조금 줄이기 위해
    # 단순 y값 대신 얼굴 자체의 up 방향 사용
    # --------------------------------------------------------

    mouth_center = mean_vector(
        [
            points[48],
            points[54],
            points[51],
            points[57],
        ]
    )


    eye_center = (
        right_eye_center
        +
        left_eye_center
    ) / 2.0


    face_up = (
        eye_center
        -
        mouth_center
    )


    if face_up.length < EPS:

        return None


    face_up.normalize()


    # --------------------------------------------------------
    # 눈썹
    # --------------------------------------------------------

    right_brow_center = mean_vector(
        [
            points[i]
            for i in range(17, 22)
        ]
    )


    left_brow_center = mean_vector(
        [
            points[i]
            for i in range(22, 27)
        ]
    )


    right_brow_height = (
        (
            right_brow_center
            -
            right_eye_center
        ).dot(face_up)
        /
        eye_distance
    )


    left_brow_height = (
        (
            left_brow_center
            -
            left_eye_center
        ).dot(face_up)
        /
        eye_distance
    )


    return {
        "right_eye_open": right_eye_open,
        "left_eye_open": left_eye_open,

        "mouth_open": mouth_open,
        "mouth_width": mouth_width,

        "right_brow": right_brow_height,
        "left_brow": left_brow_height,
    }


# ============================================================
# 전체 프레임 Metric 계산
# ============================================================

raw_metrics = []


for frame_data in frames:

    metrics = calculate_metrics(
        frame_data
    )

    raw_metrics.append(
        metrics
    )


valid_count = sum(
    1
    for item in raw_metrics
    if item is not None
)


if valid_count == 0:

    raise RuntimeError(
        "Face Metric 계산에 실패했습니다."
    )


print()
print(
    "Face Metric:",
    valid_count,
    "/",
    len(frames),
    "프레임"
)


# ============================================================
# Metric smoothing
# ============================================================

METRIC_NAMES = [
    "right_eye_open",
    "left_eye_open",
    "mouth_open",
    "mouth_width",
    "right_brow",
    "left_brow",
]


def smoothed_metric(
    frame_index,
    metric_name
):

    start = max(
        0,
        frame_index - SMOOTH_RADIUS
    )

    end = min(
        len(raw_metrics) - 1,
        frame_index + SMOOTH_RADIUS
    )


    values = []


    for i in range(
        start,
        end + 1
    ):

        item = raw_metrics[i]

        if item is None:
            continue

        values.append(
            item[metric_name]
        )


    if not values:
        return 0.0


    return mean_number(
        values
    )


metrics = []


for frame_index in range(
    len(frames)
):

    item = {}

    for metric_name in METRIC_NAMES:

        item[metric_name] = smoothed_metric(
            frame_index,
            metric_name
        )

    metrics.append(
        item
    )


# ============================================================
# 범위 자동 Calibration
# ============================================================

right_eye_values = [
    x["right_eye_open"]
    for x in metrics
]

left_eye_values = [
    x["left_eye_open"]
    for x in metrics
]

mouth_open_values = [
    x["mouth_open"]
    for x in metrics
]

mouth_width_values = [
    x["mouth_width"]
    for x in metrics
]

right_brow_values = [
    x["right_brow"]
    for x in metrics
]

left_brow_values = [
    x["left_brow"]
    for x in metrics
]


# ------------------------------------------------------------
# 눈
#
# 90% 근처 = 평소 뜬 눈
# 5% 근처 = 가장 감긴 상태
# ------------------------------------------------------------

right_eye_open_ref = percentile(
    right_eye_values,
    0.90
)

right_eye_closed_ref = percentile(
    right_eye_values,
    0.05
)


left_eye_open_ref = percentile(
    left_eye_values,
    0.90
)

left_eye_closed_ref = percentile(
    left_eye_values,
    0.05
)


# 실제 blink가 있는지
right_eye_dynamic = (
    right_eye_open_ref
    -
    right_eye_closed_ref
)


left_eye_dynamic = (
    left_eye_open_ref
    -
    left_eye_closed_ref
)


right_has_blink = (
    right_eye_dynamic
    >
    right_eye_open_ref * 0.20
)


left_has_blink = (
    left_eye_dynamic
    >
    left_eye_open_ref * 0.20
)


# ------------------------------------------------------------
# 입
# ------------------------------------------------------------

mouth_closed_ref = percentile(
    mouth_open_values,
    0.10
)

mouth_open_ref = percentile(
    mouth_open_values,
    0.95
)


mouth_width_center = percentile(
    mouth_width_values,
    0.50
)

mouth_width_small_ref = percentile(
    mouth_width_values,
    0.10
)

mouth_width_large_ref = percentile(
    mouth_width_values,
    0.90
)


# ------------------------------------------------------------
# 눈썹
# ------------------------------------------------------------

right_brow_center = percentile(
    right_brow_values,
    0.50
)

left_brow_center = percentile(
    left_brow_values,
    0.50
)


right_brow_low = percentile(
    right_brow_values,
    0.10
)

right_brow_high = percentile(
    right_brow_values,
    0.90
)


left_brow_low = percentile(
    left_brow_values,
    0.10
)

left_brow_high = percentile(
    left_brow_values,
    0.90
)


print()
print("Calibration 완료")

print(
    "Right Blink:",
    right_has_blink
)

print(
    "Left Blink:",
    left_has_blink
)


# ============================================================
# 기존 얼굴 Action 정리
# ============================================================

key_data.animation_data_create()


current_action = (
    key_data.animation_data.action
)


if (
    current_action is not None
    and
    current_action.name.startswith(
        WORD_ID + "_FACE"
    )
):

    key_data.animation_data.action = None

    bpy.data.actions.remove(
        current_action
    )


new_action = bpy.data.actions.new(
    FACE_ACTION_NAME
)


key_data.animation_data.action = (
    new_action
)


# ============================================================
# 사용할 Shape Key 초기화
# ============================================================

for shape_name in SHAPE.values():

    key_blocks[
        shape_name
    ].value = 0.0


# ============================================================
# Keyframe 생성
# ============================================================

scene = bpy.context.scene

scene.render.fps = fps


frame_numbers = [
    int(frame["frame"])
    for frame in frames
]


scene.frame_start = min(
    frame_numbers
)

scene.frame_end = max(
    frame_numbers
)


print()
print(
    "Face Animation 생성 중..."
)


for frame_index, frame_data in enumerate(
    frames
):

    frame_number = int(
        frame_data["frame"]
    )


    item = metrics[
        frame_index
    ]


    # ========================================================
    # 눈 깜빡임
    # ========================================================

    right_close = 0.0

    if right_has_blink:

        denominator = max(
            right_eye_dynamic,
            EPS
        )

        right_close = (
            right_eye_open_ref
            -
            item["right_eye_open"]
        ) / denominator

        right_close = clamp(
            right_close
        )

        right_close *= BLINK_GAIN


    left_close = 0.0

    if left_has_blink:

        denominator = max(
            left_eye_dynamic,
            EPS
        )

        left_close = (
            left_eye_open_ref
            -
            item["left_eye_open"]
        ) / denominator

        left_close = clamp(
            left_close
        )

        left_close *= BLINK_GAIN


    # ========================================================
    # 입 벌림
    # ========================================================

    mouth_range = max(
        mouth_open_ref
        -
        mouth_closed_ref,
        EPS
    )


    mouth_open_value = (
        item["mouth_open"]
        -
        mouth_closed_ref
    ) / mouth_range


    mouth_open_value = clamp(
        mouth_open_value
    )


    mouth_open_value *= (
        MOUTH_OPEN_GAIN
    )


    # ========================================================
    # 입 가로 크기
    # ========================================================

    mouth_large = 0.0
    mouth_small = 0.0


    if (
        item["mouth_width"]
        >=
        mouth_width_center
    ):

        width_range = max(
            mouth_width_large_ref
            -
            mouth_width_center,
            EPS
        )

        mouth_large = (
            item["mouth_width"]
            -
            mouth_width_center
        ) / width_range

        mouth_large = clamp(
            mouth_large
        )

        mouth_large *= (
            MOUTH_WIDTH_GAIN
        )


    else:

        width_range = max(
            mouth_width_center
            -
            mouth_width_small_ref,
            EPS
        )

        mouth_small = (
            mouth_width_center
            -
            item["mouth_width"]
        ) / width_range

        mouth_small = clamp(
            mouth_small
        )

        mouth_small *= (
            MOUTH_WIDTH_GAIN
        )


    # ========================================================
    # 눈썹
    # ========================================================

    brow_up_values = []
    brow_down_values = []


    # 오른쪽
    if item["right_brow"] >= right_brow_center:

        value = (
            item["right_brow"]
            -
            right_brow_center
        ) / max(
            right_brow_high
            -
            right_brow_center,
            EPS
        )

        brow_up_values.append(
            clamp(value)
        )

    else:

        value = (
            right_brow_center
            -
            item["right_brow"]
        ) / max(
            right_brow_center
            -
            right_brow_low,
            EPS
        )

        brow_down_values.append(
            clamp(value)
        )


    # 왼쪽
    if item["left_brow"] >= left_brow_center:

        value = (
            item["left_brow"]
            -
            left_brow_center
        ) / max(
            left_brow_high
            -
            left_brow_center,
            EPS
        )

        brow_up_values.append(
            clamp(value)
        )

    else:

        value = (
            left_brow_center
            -
            item["left_brow"]
        ) / max(
            left_brow_center
            -
            left_brow_low,
            EPS
        )

        brow_down_values.append(
            clamp(value)
        )


    brow_up = (
        max(brow_up_values)
        if brow_up_values
        else 0.0
    )


    brow_down = (
        max(brow_down_values)
        if brow_down_values
        else 0.0
    )


    brow_up *= BROW_UP_GAIN
    brow_down *= BROW_DOWN_GAIN


    # 너무 동시에 싸우지 않도록
    if brow_up > brow_down:

        brow_down *= 0.25

    else:

        brow_up *= 0.25


    # ========================================================
    # Shape Key 값 적용
    # ========================================================

    values = {

        SHAPE["EYE_CLOSE_R"]:
            clamp(right_close),

        SHAPE["EYE_CLOSE_L"]:
            clamp(left_close),

        SHAPE["MOUTH_OPEN"]:
            clamp(mouth_open_value),

        SHAPE["MOUTH_LARGE"]:
            clamp(mouth_large),

        SHAPE["MOUTH_SMALL"]:
            clamp(mouth_small),

        SHAPE["BROW_UP"]:
            clamp(brow_up),

        SHAPE["BROW_DOWN"]:
            clamp(brow_down),
    }


    for shape_name, value in values.items():

        key_block = key_blocks[
            shape_name
        ]

        key_block.value = value

        key_block.keyframe_insert(
            data_path="value",
            frame=frame_number
        )


# ============================================================
# 첫 프레임
# ============================================================

scene.frame_set(
    scene.frame_start
)


# ============================================================
# 완료
# ============================================================

print()
print("========================================")
print(f"{WORD_ID} FACE RETARGET 완료")
print("========================================")

print()
print(
    "Frame:",
    scene.frame_start,
    "~",
    scene.frame_end
)

print(
    "FPS:",
    scene.render.fps
)

print(
    "Action:",
    FACE_ACTION_NAME
)

print()
print(
    "적용:"
)

print(
    " - 좌/우 눈 감김"
)

print(
    " - 눈썹 위/아래"
)

print(
    " - 입 벌림"
)

print(
    " - 입 넓어짐/좁아짐"
)

print()
print(
    "기존 팔/손 애니메이션은 그대로 유지됨."
)

print()
print(
    "Layout으로 돌아가서 Spacebar로 확인하세요."
)

print(
    "========================================"
)


print()
print("============================================================")
print(f"{WORD_ID} AVATAR RETARGET 전체 완료")
print("============================================================")
print(f"Body Action: {ACTION_NAME}")
print(f"Face Action: {FACE_ACTION_NAME}")
print(f"Frame: {bpy.context.scene.frame_start} ~ {bpy.context.scene.frame_end}")
print(f"FPS: {bpy.context.scene.render.fps}")
print("Layout으로 돌아가서 Spacebar로 재생하세요.")
print("============================================================")

