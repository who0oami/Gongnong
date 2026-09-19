WORD2153 Avatar Retarget Test

WORD2153 수어 동작을 고정 VRM 아바타에 적용하기 위한 테스트 코드입니다.

파일 역할

export_vroid_rig_info.py

VRM 아바타의 뼈대 구조를 추출하는 스크립트입니다.

추출 정보:

Bone 이름

부모 Bone

Bone 시작/끝 위치

Bone 길이

기본 변환 행렬

실행 결과:

sample/vroid_rig_info.json

이 파일은 word2153_retarget_v2.py에서 아바타의 기본 뼈대 구조를 확인하는 데 사용합니다.

export_vroid_face_info.py

VRM 얼굴 Mesh에 존재하는 Shape Key 목록을 추출하는 스크립트입니다.

예:

눈 감기

눈썹 움직임

입 벌리기

입 모양

실행 결과:

sample/vroid_face_info.json

현재 word2153_face_retarget.py가 이 JSON을 직접 읽지는 않으며,
VRM이 어떤 얼굴 Shape Key를 가지고 있는지 확인하기 위한 참고/디버깅용 파일입니다.

word2153_retarget_v2.py

WORD2153의 3D 관절 좌표를 VRM Bone 회전 애니메이션으로 변환하는 핵심 스크립트입니다.

입력:

sample/WORD2153_3d_approx.json
sample/vroid_rig_info.json

적용 대상:

UpperArm

LowerArm

Hand

손가락 Bone

Blender Armature에 Rotation Keyframe을 생성하여
WORD2153의 팔, 손, 손가락 동작을 아바타에 적용합니다.

word2153_face_retarget.py

WORD2153의 얼굴 3D 포인트를 이용해 VRM 얼굴 Shape Key 애니메이션을 생성합니다.

입력:

sample/WORD2153_3d_approx.json

적용 대상:

좌/우 눈 감김

눈썹 위/아래

입 벌림

입 넓어짐/좁아짐

기존 팔/손 애니메이션은 유지하고 얼굴 표정 Keyframe만 추가합니다.

전체 흐름

VRM
 ├─ export_vroid_rig_info.py
 │      └─ vroid_rig_info.json
 │
 └─ export_vroid_face_info.py
        └─ vroid_face_info.json


WORD2153_3d_approx.json
 ├─ word2153_retarget_v2.py
 │      └─ 팔 / 손 / 손가락 애니메이션
 │
 └─ word2153_face_retarget.py
        └─ 얼굴 표정 애니메이션

폴더 구조

sign-keypoint-to-avatar/ (이전 이름 word2153/)
├─ scripts/
│  ├─ export_vroid_rig_info.py
│  ├─ export_vroid_face_info.py
│  ├─ word2153_retarget_v2.py
│  └─ word2153_face_retarget.py
│
└─ sample/
   ├─ WORD2153_3d_approx.json
   ├─ vroid_rig_info.json
   └─ vroid_face_info.json

참고

export_... 파일 2개는 VRM 구조 확인/정보 추출용입니다.

retarget... 파일 2개는 실제 애니메이션 생성용입니다.

현재 테스트 대상은 WORD2153입니다.

WORD2153_3d_approx.json은 다중 시점 2D keypoint를 이용해 근사 복원한 3D 데이터입니다.

