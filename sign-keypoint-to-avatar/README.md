# sign-keypoint-to-avatar

수어 영상(또는 기존 3D 데이터셋)에서 손·몸 키포인트를 뽑아 VRM 아바타의 본(bone)
회전과 표정으로 옮기는 파이프라인입니다. (이전 폴더명: `word2153` — 맨 처음 테스트했던
단어 ID `WORD2153`에서 따온 이름이라 지금 하는 일 전체를 설명하지 못해서 바꿨습니다.)

`ksl-tube` 모노레포 안의 독립적인 실험 트랙입니다. 상위의 `backend/`(YouTube 자막
`/translate` API), `frontend/`(별개의 OpenPose 데모)와는 서로 연결돼 있지 않습니다.
텍스트→글로스(gloss) 모델 작업은 `ai/text-to-gloss/`로 따로 분리했습니다(이 폴더가
다루는 "키포인트→아바타"와는 다른 파이프라인입니다).

더 자세한 개발자용 가이드(정확한 재현 명령, 아키텍처 단계별 설명, 지켜야 할 관례)는
**`CLAUDE.md`**를 보세요. 이 README는 처음 보는 사람이 "뭐가 어디 있고 뭐부터 실행하면
되는지" 빠르게 파악하기 위한 것입니다.

## 폴더 구조

```
sign-keypoint-to-avatar/
├─ extractor/          영상 → MediaPipe 키포인트 추출, 손 재검출/정제/스무딩,
│                       KNN 통계 보정(README_hand_shape_prior.md), 딥러닝 실험 코드
├─ scripts/             Blender 리타게팅 스크립트, 레거시 WORD2153 경로,
│                       진단/검증용 스크립트 다수 (README.md 참고)
├─ colab/               Google Colab에서 돌리는 학습 노트북(.ipynb/.py)
├─ mediapipe-preview/    Blender 없이 브라우저(Babylon.js)로 보는 미리보기 화면
├─ keypoints/            추출된 키포인트 JSON (영상별, 단계별로 버전이 나뉨)
├─ output/               Blender 결과물(.blend) — 용량이 커서 git에 안 올라감
├─ diagnostics/          검증용 렌더 이미지, 감사(audit) 리포트
├─ sample/               레거시 WORD2153 테스트용 고정 3D 데이터
├─ retarget_config.json / retarget_profile.json   레거시 WORD2153 경로 설정
├─ CLAUDE.md             전체 아키텍처와 명령어 레퍼런스 (가장 자세함)
└─ HAND_DENOISER_ML_EXPERIMENTS.md   손 모션 보정 관련 실험 기록(성공/실패 모두)
```

`output/`, `diagnostics/`, `keypoints/`의 대부분, `extractor/models/`,
`extractor/*.npz`(코드로 재생성 가능한 큰 데이터 파일)는 각 폴더의 `.gitignore`로
git에서 제외되어 있습니다 — 로컬에만 있고 다른 사람 컴퓨터에는 없을 수 있습니다.

## 필요한 것

- Python 3.13 (다른 3.x 버전에서도 대체로 동작하지만 검증된 건 3.13)
- Blender 5.2 (`C:\Program Files\Blender Foundation\Blender 5.2\blender.exe` 경로가
  스크립트 기본값입니다. 다르면 각 스크립트의 `--blender` 옵션으로 바꾸세요.)
- `python -m pip install -r extractor/requirements.txt` (MediaPipe 등)
- (딥러닝 실험 코드를 로컬에서 돌리려면) `pip install torch`
- 원본 영상 파일, 기존 3D 데이터셋(`output_3d/` 등)은 용량 문제로 git에 없습니다 —
  로컬 경로를 직접 맞춰서 스크립트 인자로 넘겨야 합니다.

## 빠른 시작 (영상 → 아바타)

```powershell
# 1) 영상에서 키포인트 추출
python extractor/extract_keypoints.py "<영상 경로>.mp4" --output keypoints/<id>.json --sign-id <id> --label <라벨> --download-model

# 2) 손 재검출로 정제
python extractor/refine_hands.py "<영상 경로>.mp4" --input keypoints/<id>.json --output keypoints/<id>_refined.json --download-model
python scripts/prepare_stable_hands.py --base keypoints/<id>.json --refined keypoints/<id>_refined.json --output keypoints/<id>_stable.json

# 3) 프레임 간 떨림 제거 (One-Euro filter)
python extractor/smooth_hand_landmarks.py --input keypoints/<id>_stable.json --output keypoints/<id>_stable_smoothed.json

# 4) Blender로 아바타에 리타게팅
& "C:\Program Files\Blender Foundation\Blender 5.2\blender.exe" --background --factory-startup --python-exit-code 1 --python scripts/mediapipe_to_blender_aligned.py -- --motion keypoints/<id>_stable_smoothed.json --profile mediapipe-preview/blender_M10_profile_fist_v1.json --output output/<id>_v1.blend --render

# 5) (선택) 이상치 손 모양을 1500단어 데이터로 통계적 보정
python extractor/build_hand_shape_prior.py --dataset "<3D 데이터셋 폴더>" --output extractor/hand_shape_prior.npz
& "C:\Program Files\Blender Foundation\Blender 5.2\blender.exe" --background --python scripts/correct_hand_shape_prior.py -- --input output/<id>_v1.blend --output output/<id>_v2.blend --prior extractor/hand_shape_prior.npz
```

각 단계는 출력 파일명이 이미 있으면 실행을 거부합니다(기존 결과를 덮어쓰지 않음) —
다시 시도할 땐 새 파일명을 쓰세요. 정확한 옵션, 각 단계가 정확히 뭘 하는지는
`CLAUDE.md`의 "Architecture: the pipeline, stage by stage"에 더 자세히 있습니다.

## 결과 보는 법

위 4)/5) 단계로 만든 `output/*.blend`는 두 가지 방법으로 확인할 수 있습니다.

**A. Blender에서 직접 열기**
```powershell
& "C:\Program Files\Blender Foundation\Blender 5.2\blender.exe" output/<id>_v1.blend
```
3D 뷰포트에 마우스를 올려두고 Space bar를 누르면 애니메이션이 재생됩니다. 타임라인의
`REVIEW_L/R/LR` 마커는 검출/좌우 판별을 다시 확인해야 하는 구간, `OBSERVED_L_R`는 두
손 관측이 실제로 적용된 구간이라는 뜻입니다(수어 정확도 보증은 아닙니다).

**B. Blender 없이 브라우저에서 미리보기**
```powershell
scripts\run_mediapipe_preview.cmd
```
이 워크스페이스를 로컬 서버로 띄우고 `mediapipe-preview/index.html`을 자동으로 엽니다.
상단에서 원본 영상과 `keypoints/*.json`을 골라, 같은 화면에서 원본 영상과 GLB/VRM
아바타 리타게팅을 나란히 재생/탐색할 수 있습니다(1~4단계만 반영, 5단계 KNN 보정은
Blender `.blend` 쪽에만 적용됩니다). 최초 로딩 시 Babylon.js CDN 때문에 인터넷 연결이
필요합니다.

## 더 볼 곳

- `extractor/README_hand_shape_prior.md` — KNN 통계 보정 상세 (무엇을, 왜, 어떻게)
- `HAND_DENOISER_ML_EXPERIMENTS.md` — 딥러닝으로 같은 문제를 풀어본 기록 (성공/폐기 모두)
- `scripts/README.md` — 레거시 WORD2153 경로 설명
- `extractor/README.md`, `extractor/BLENDER_HANDS.md`, `extractor/NATURAL_HANDS.md`,
  `extractor/HAND_CONTACT.md` — 추출/정제/자연스러운 손 모양/접촉 보정 각 단계별 기록
