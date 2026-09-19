# sign-keypoint-to-avatar

수어 영상(또는 기존 3D 데이터셋)에서 손·몸 키포인트를 추출해 VRM 아바타의 본(bone)
회전과 표정으로 옮기는 파이프라인입니다.

`ksl-tube` 모노레포 안의 독립 실험 트랙이며, 상위의 `backend/`(YouTube 자막
`/translate` API), `frontend/`(별개의 OpenPose 데모)와는 연결되어 있지 않습니다.
텍스트→글로스(gloss) 모델 작업은 `ai/text-to-gloss/`로 분리되어 있으며 이 폴더와는
별개 파이프라인입니다.

전체 아키텍처, 각 스크립트 옵션, 지켜야 할 규칙은 `ARCHITECTURE.md`에 정리되어 있습니다.

## 폴더 구조

```
sign-keypoint-to-avatar/
├─ extractor/          영상 → MediaPipe 키포인트 추출, 손 재검출/정제/스무딩,
│                       KNN 통계 보정(README_hand_shape_prior.md), 딥러닝 실험 코드
├─ scripts/             Blender 리타게팅 스크립트, 레거시 WORD2153 경로,
│                       진단/검증용 스크립트 (scripts/README.md 참고)
├─ colab/               Google Colab 학습 노트북(.ipynb/.py)
├─ mediapipe-preview/    Blender 없이 브라우저(Babylon.js)로 보는 미리보기 화면
├─ keypoints/            추출된 키포인트 JSON (영상별, 단계별 버전) — git 미포함
├─ output/               Blender 결과물(.blend) — git 미포함
├─ diagnostics/          검증용 렌더 이미지, 감사(audit) 리포트 — git 미포함
├─ sample/               레거시 WORD2153 테스트용 고정 3D 데이터
├─ retarget_config.json / retarget_profile.json   레거시 WORD2153 경로 설정
├─ ARCHITECTURE.md      전체 아키텍처와 명령어 레퍼런스
└─ HAND_DENOISER_ML_EXPERIMENTS.md   손 모션 보정 실험 기록(성공/실패 모두)
```

`keypoints/`, `output/`, `diagnostics/`는 용량 문제로 git에 포함되어 있지 않습니다.
아래 "빠른 시작"을 실행하면 로컬에 새로 생성됩니다.

## 필요한 것

- Python 3.13 (다른 3.x 버전에서도 대체로 동작하나 검증된 버전은 3.13)
- Blender 5.2 (`C:\Program Files\Blender Foundation\Blender 5.2\blender.exe`가 스크립트
  기본 경로. 다르면 각 스크립트의 `--blender` 옵션으로 지정)
- `python -m pip install -r extractor/requirements.txt` (MediaPipe 등)
- 딥러닝 실험 코드를 로컬에서 돌릴 경우 `pip install torch`
- 원본 영상, 기존 3D 데이터셋(`output_3d/` 등)은 용량 문제로 git에 없어 로컬 경로를
  스크립트 인자로 직접 지정해야 합니다.

## 빠른 시작 (영상 → 아바타)

```powershell
# 1) 영상에서 키포인트 추출
python extractor/extract_keypoints.py "<영상 경로>.mp4" --output keypoints/<id>.json --sign-id <id> --label <라벨> --download-model

# 2) 손 재검출로 정제
python extractor/refine_hands.py "<영상 경로>.mp4" --input keypoints/<id>.json --output keypoints/<id>_refined.json --download-model
python scripts/prepare_stable_hands.py --base keypoints/<id>.json --refined keypoints/<id>_refined.json --output keypoints/<id>_stable.json

# 3) 프레임 간 떨림 제거 (One-Euro filter)
python extractor/smooth_hand_landmarks.py --input keypoints/<id>_stable.json --output keypoints/<id>_stable_smoothed.json

# 4) Blender로 아바타에 리타게팅 (기본은 F20 여자 모델, 남자 모델은 blender_M10_profile_fist_v1.json)
& "C:\Program Files\Blender Foundation\Blender 5.2\blender.exe" --background --factory-startup --python-exit-code 1 --python scripts/mediapipe_to_blender_aligned.py -- --motion keypoints/<id>_stable_smoothed.json --profile mediapipe-preview/blender_F20_profile_v1.json --output output/<id>_v1.blend --render

# 5) (선택) 이상치 손 모양을 1500단어 데이터로 통계 보정
python extractor/build_hand_shape_prior.py --dataset "<3D 데이터셋 폴더>" --output extractor/hand_shape_prior.npz
& "C:\Program Files\Blender Foundation\Blender 5.2\blender.exe" --background --python scripts/correct_hand_shape_prior.py -- --input output/<id>_v1.blend --output output/<id>_v2.blend --prior extractor/hand_shape_prior.npz
```

각 단계는 출력 파일명이 이미 있으면 실행을 거부하도록 되어 있어 기존 결과를 덮어쓰지
않습니다. 재시도할 때는 새 파일명을 사용하면 됩니다. 각 단계가 정확히 하는 일은
`ARCHITECTURE.md`의 "Architecture: the pipeline, stage by stage"에서 확인할 수 있습니다.

위 1)~5)를 한 번에 실행하는 스크립트도 있습니다.

```powershell
python scripts/run_full_pipeline.py "<영상 경로>.mp4" --sign-id <id> --label <라벨>
```

`output/<id>_hands_<실행시각>/` 폴더를 새로 만들고 그 안에 중간 결과(raw/refined/stable/
smoothed json)와 최종 `.blend`를 저장합니다. 기본 아바타는 F20(여자) 모델이고, 남자
모델(M10)로 돌리려면 `--profile mediapipe-preview/blender_M10_profile_fist_v1.json`을
넘기면 됩니다. `extractor/hand_shape_prior.npz`가 이미 있으면 5단계(KNN 보정)까지
자동으로 이어서 실행하고, 없으면 4단계 결과만 만들고 5단계는 건너뜁니다.
`--skip-prior-correction`으로 5단계를 강제로 끌 수 있고, `--profile`/
`--blender`/`--prior`로 각각 다른 값을 줄 수 있습니다.

## 결과 확인 (팀원 테스트용)

위 4)/5) 단계 결과물은 아래 두 가지 방법으로 확인하면 됩니다.

**A. Blender에서 직접 열기**
```powershell
& "C:\Program Files\Blender Foundation\Blender 5.2\blender.exe" output/<id>_v1.blend
```
3D 뷰포트에 마우스를 두고 Space bar를 누르면 애니메이션이 재생됩니다. 타임라인의
`REVIEW_L/R/LR` 마커는 검출/좌우 판별을 다시 확인해야 하는 구간, `OBSERVED_L_R`는 두
손 관측이 실제로 적용된 구간을 표시한 것입니다(수어 정확도를 보증하는 표시는 아닙니다).

**B. 브라우저 미리보기 (Blender 불필요)**
```powershell
scripts\run_mediapipe_preview.cmd
```
워크스페이스를 로컬 서버로 띄우고 `mediapipe-preview/index.html`을 엽니다. 화면
상단에서 원본 영상과 `keypoints/*.json`을 선택하면 원본 영상과 아바타 리타게팅 결과를
같은 화면에서 나란히 재생/탐색할 수 있습니다. 1~4단계까지만 반영되며, 5단계 KNN
보정은 Blender `.blend` 쪽에만 적용되어 이 화면에는 나타나지 않습니다. 최초 로딩 시
Babylon.js CDN을 불러오므로 인터넷 연결이 필요합니다.

## 더 볼 곳

- `extractor/README_hand_shape_prior.md` — KNN 통계 보정 상세 (무엇을, 왜, 어떻게)
- `HAND_DENOISER_ML_EXPERIMENTS.md` — 딥러닝으로 같은 문제를 풀어본 기록 (성공/폐기 모두)
- `scripts/README.md` — 레거시 WORD2153 경로 설명
- `extractor/README.md`, `extractor/BLENDER_HANDS.md`, `extractor/NATURAL_HANDS.md`,
  `extractor/HAND_CONTACT.md` — 추출/정제/자연스러운 손 모양/접촉 보정 각 단계별 기록

