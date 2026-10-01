import bpy
import json
import os
from pathlib import Path
from mathutils import Vector


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

FACE_OBJECT_NAME = "Face"

WORD_ID = os.environ.get("KSL_WORD_ID", MOTION_JSON_PATH.stem.split("_3d")[0])
ACTION_NAME = WORD_ID + "_FACE_RETARGET"

SMOOTH_RADIUS = 1

EPS = 1e-8


# ============================================================
# 강도 조절
#
# 얼굴이 너무 세면 아래 숫자를 낮추면 됨.
# ============================================================

BLINK_GAIN = 1.0

MOUTH_OPEN_GAIN = 0.85
MOUTH_WIDTH_GAIN = 0.65

BROW_UP_GAIN = 0.70
BROW_DOWN_GAIN = 0.45


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
print("WORD2153 FACE RETARGET")
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
        "WORD2153_FACE"
    )
):

    key_data.animation_data.action = None

    bpy.data.actions.remove(
        current_action
    )


new_action = bpy.data.actions.new(
    ACTION_NAME
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
print("WORD2153 FACE RETARGET 완료")
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
    ACTION_NAME
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
