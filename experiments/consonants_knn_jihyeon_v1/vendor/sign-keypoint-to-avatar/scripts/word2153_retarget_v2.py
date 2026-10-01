import json
import bpy
import os

from pathlib import Path
from math import acos, asin, radians
from mathutils import Vector, Matrix, Quaternion


# ============================================================
# 설정
# ============================================================

def find_sample_file(filename):
    """스크립트 주변에서 word2153/sample의 데이터 파일을 찾습니다."""
    script_dir = Path(__file__).resolve().parent

    candidates = [
        script_dir.parent / "sample" / filename,        # word2153/scripts
        script_dir / "sample" / filename,               # word2153
        script_dir / "word2153" / "sample" / filename, # 저장소 루트
        script_dir.parent / "word2153" / "sample" / filename,
    ]

    # GitHub ZIP: 다운로드폴더/ksl-tube-브랜치/word2153/sample
    candidates.extend(script_dir.glob(f"*/word2153/sample/{filename}"))

    for path in candidates:
        if path.is_file():
            return path.resolve()

    checked = "\n".join(str(path) for path in candidates)
    raise FileNotFoundError(
        f"\n{filename} 파일을 찾을 수 없습니다.\n"
        f"확인한 위치:\n{checked}\n\n"
        f"권장 위치: word2153/sample/{filename}"
    )


MOTION_JSON_PATH = Path(os.environ.get("KSL_MOTION_JSON", str(find_sample_file("WORD2153_3d_approx.json"))))
RIG_JSON_PATH = find_sample_file("vroid_rig_info.json")

ARMATURE_NAME = "Armature"

PREFIX = os.environ.get("KSL_WORD_ID", MOTION_JSON_PATH.stem.split("_3d")[0])

ACTION_NAME = PREFIX + "_RETARGET_V2"

# 0 = 원본 그대로
# 1 = 앞뒤 1프레임까지 평균 = 3프레임 smoothing
PROFILE_PATH = Path(os.environ.get("KSL_RETARGET_PROFILE", ""))
if PROFILE_PATH.is_file():
    with open(PROFILE_PATH, "r", encoding="utf-8") as profile_file:
        RETARGET_PROFILE = json.load(profile_file)
else:
    RETARGET_PROFILE = {}

FINGER_PROFILE = RETARGET_PROFILE.get("finger", {})
PALM_NORMAL_SIGN = RETARGET_PROFILE.get("palm_normal_sign", {"L": 1.0, "R": -1.0})
SMOOTH_RADIUS = int(RETARGET_PROFILE.get("smoothing_radius", 1))
FINGER_MIN_BEND = radians(float(FINGER_PROFILE.get("min_bend_degrees", 0.0)))
FINGER_MAX_BEND = radians(float(FINGER_PROFILE.get("max_bend_degrees", 82.0)))
FINGER_GAIN = float(FINGER_PROFILE.get("gain", 1.0))
THUMB_GAIN = float(FINGER_PROFILE.get("thumb_gain", 0.85))
FINGER_BEND_SIGN = FINGER_PROFILE.get("bend_sign", {"L": -1.0, "R": -1.0})
FINGER_MIN_SEGMENT_RATIO = float(FINGER_PROFILE.get("reject_segment_ratio_below", 0.08))

EPS = 1e-8


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
        "\nWORD2153 Motion JSON 없음:\n"
        + str(MOTION_JSON_PATH)
    )


if not RIG_JSON_PATH.exists():

    raise FileNotFoundError(
        "\nVRM Rig JSON 없음:\n"
        + str(RIG_JSON_PATH)
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


with open(
    RIG_JSON_PATH,
    "r",
    encoding="utf-8"
) as f:

    rig_data = json.load(f)


frames = motion_data.get(
    "frames",
    []
)


if not frames:

    raise RuntimeError(
        "WORD2153 JSON에 frames가 없습니다."
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
print("WORD2153 RETARGET V2")
print("==========================================")

print()
print("Motion:")
print(MOTION_JSON_PATH)

print()
print("Rig:")
print(RIG_JSON_PATH)

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
            bone_name
        )

    if bone_name not in rig_data["bones"]:

        missing.append(
            bone_name + " [rig json]"
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
# Vector helper
# ============================================================

def vec3(values):

    return Vector(
        (
            float(values[0]),
            float(values[1]),
            float(values[2]),
        )
    )


# ============================================================
# Rig JSON helper
# ============================================================

def rig_head(bone_name):

    return vec3(
        rig_data[
            "bones"
        ][
            bone_name
        ][
            "head_local"
        ]
    )


def rig_tail(bone_name):

    return vec3(
        rig_data[
            "bones"
        ][
            bone_name
        ][
            "tail_local"
        ]
    )


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


    palm_normal *= float(PALM_NORMAL_SIGN.get(side, 1.0))
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


    normal = make_palm_normal(
        wrist,
        index_mcp,
        middle_mcp,
        little_mcp
    )

    if normal is not None:
        normal *= float(PALM_NORMAL_SIGN.get(side, 1.0))

    return normal

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
# Finger rest-relative bend
#
# 절대 3D 방향을 Bone에 덮어쓰지 않고 첫 프레임 대비 굽힘 변화만
# 대상 모델의 rest pose local 축에 적용한다. 모델별 bone roll 차이를
# 흡수하므로 같은 아바타에 여러 동작을 재사용할 수 있다.
# ============================================================

def finger_bend_angle(frame_index, group_name, previous_index, start_index, end_index, side):
    previous = mapped_point(frame_index, group_name, previous_index)
    start = mapped_point(frame_index, group_name, start_index)
    end = mapped_point(frame_index, group_name, end_index)
    palm_normal = source_palm_normal(frame_index, side)

    if previous is None or start is None or end is None or palm_normal is None:
        return None

    incoming = start - previous
    outgoing = end - start
    palm_width_start = mapped_point(frame_index, group_name, 5)
    palm_width_end = mapped_point(frame_index, group_name, 17)
    if palm_width_start is None or palm_width_end is None:
        return None
    palm_width = (palm_width_start - palm_width_end).length
    if palm_width < EPS:
        return None
    if incoming.length < palm_width * FINGER_MIN_SEGMENT_RATIO or outgoing.length < palm_width * FINGER_MIN_SEGMENT_RATIO:
        return None

    incoming.normalize()
    outgoing.normalize()

    # At an MCP joint, wrist->MCP is a ray across the palm rather than the
    # parent finger-bone direction. Comparing it with MCP->PIP mistakes finger
    # spread (abduction) for flexion and curls an otherwise open hand. Measure
    # only how far the proximal phalanx leaves the palm plane instead.
    if start_index in (1, 5, 9, 13, 17):
        plane_offset = max(-1.0, min(1.0, outgoing.dot(palm_normal)))
        return abs(asin(plane_offset))

    # PIP/DIP joints have real adjacent segments, so their anatomical joint
    # angle is the correct flexion value.
    # Palm normals reconstructed from multiple views can flip between frames.
    # An unsigned anatomical angle prevents fingers from bending backwards.
    dot = max(-1.0, min(1.0, incoming.dot(outgoing)))
    return acos(dot)


def apply_relative_finger_bend(bone_name, bend_angle, target_palm_normal, frame_number, side):
    pose_bone = arm.pose.bones[bone_name]
    rest_direction = rig_tail(bone_name) - rig_head(bone_name)
    if rest_direction.length < EPS:
        return False
    rest_direction.normalize()

    flex_axis_armature = rest_direction.cross(target_palm_normal)
    if flex_axis_armature.length < EPS:
        return False
    flex_axis_armature.normalize()

    rest_rotation = get_bone_rest_rotation(bone_name)
    flex_axis_local = rest_rotation.transposed() @ flex_axis_armature
    flex_axis_local.normalize()

    # 잘못된 키포인트 한 프레임이 손가락을 뒤집지 않도록 제한
    gain = THUMB_GAIN if "Thumb" in bone_name else FINGER_GAIN
    bend_angle = max(FINGER_MIN_BEND, min(FINGER_MAX_BEND, bend_angle * gain))
    bend_angle *= float(FINGER_BEND_SIGN.get(side, -1.0))
    quaternion = Quaternion(flex_axis_local, bend_angle)
    quaternion = ensure_quaternion_continuity(bone_name, quaternion)

    pose_bone.rotation_mode = "QUATERNION"
    pose_bone.location = (0.0, 0.0, 0.0)
    pose_bone.scale = (1.0, 1.0, 1.0)
    pose_bone.rotation_quaternion = quaternion
    pose_bone.keyframe_insert(data_path="rotation_quaternion", frame=frame_number)
    return True


# ============================================================
# 이전 WORD2153 Constraint / Empty 제거
# ============================================================

print()
print(
    "기존 WORD2153 테스트 Constraint 정리..."
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
    TARGET_BONES
)


RESET_BONES += [
    "J_Bip_L_Shoulder",
    "J_Bip_R_Shoulder",
]


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
    # LEFT / RIGHT
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

        if (
            wrist is not None
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
                wrist
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

            # 각 Bone 시작 관절의 이전 점. 첫 마디는 Wrist(0)를 사용한다.
            if "Thumb" in bone_name:
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

                if start_point is None or end_point is None:
                    skip_count += 1
                    continue

                desired = make_desired_rotation(
                    bone_name,
                    rig_tail(bone_name) - rig_head(bone_name),
                    target_palm_normal,
                    end_point - start_point,
                    current_palm_normal
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
                continue

            previous_index = (
                0
                if start_index in (1, 5, 9, 13, 17)
                else start_index - 1
            )

            current_bend = finger_bend_angle(
                frame_index,
                finger_group,
                previous_index,
                start_index,
                end_index,
                side
            )

            if current_bend is None:
                skip_count += 1
                continue

            if apply_relative_finger_bend(
                bone_name,
                current_bend,
                target_palm_normal,
                frame_number,
                side
            ):
                keyframe_count += 1
            else:
                skip_count += 1


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
print("WORD2153 RETARGET V2 완료")
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
    " - 각 마디별 3D 방향 적용"
)

print()
print(
    "주의:"
)

print(
    " - Shoulder / 몸통 / 머리 / 얼굴은 아직 고정"
)

print()
print(
    "Layout으로 돌아가서 Spacebar로 재생하세요."
)

print(
    "=========================================="
)

