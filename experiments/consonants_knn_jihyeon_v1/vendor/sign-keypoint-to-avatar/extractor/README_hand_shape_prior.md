# 손 모양 KNN 통계 보정

**작성자**: jihyeon (2026-09)

## 무엇을 하는가

영상에서 MediaPipe로 뽑은 손 관절 각도가 이상하게(비정상적으로) 나올 때, **1500개 단어의 기존 3D 데이터**를 참고 자료로 삼아 자연스러운 손 모양 쪽으로 살짝 당겨서 고치는 기능입니다.

**학습(가중치를 훈련)이 아닙니다.** 매번 코퍼스 데이터를 직접 대조하는 통계적 방법(최근접 이웃)입니다.

## 왜 필요했는가

leave.mp4/love.mp4처럼 실제 영상에서 손을 추출하면, 검출기가 프레임마다 다른 방식(홀리스틱 ↔ 크롭 재검출)으로 손을 잡아서 손가락이 떨리거나 기존 데이터 어디에도 없는 이상한 모양이 나오는 경우가 있습니다. 이걸 고치기 위해 "정상적인 손 모양이란 무엇인가"를 미리 기존 3D 데이터로 정리해두고, 이상치가 나오면 그쪽으로 보정합니다.

## 사용법

### 1) 코퍼스 만들기 (한 번만 실행, 결과는 git에 안 올림 — 아래 참고)

```powershell
python extractor/build_hand_shape_prior.py --dataset "C:/Users/ESTsoft/Desktop/output_3d/output_3d" --output extractor/hand_shape_prior.npz
```

- `--dataset`: 1500개 단어의 `WORD####_3d_approx.json` 파일이 있는 폴더. **이 3D 좌표는 아바타에 리타겟팅하기 이전의 원본 데이터**입니다 (5개 카메라로 삼각측량한 것 — `avatar_retarget/keypoint_to_3d/make_word_3d.py` 계열 스크립트의 결과물이지, `avatar_retarget/retarget/` 이후 단계의 리타겟팅 결과가 아닙니다).
- 결과: 21.6만 개 손-프레임 샘플(각 14차원 굽힘각)이 담긴 `hand_shape_prior.npz`.
- **이 `.npz` 파일은 git에 커밋하지 않습니다** (`extractor/.gitignore`에 `*.npz` 추가함 — 이 프로젝트 관례상 코드로 재생성 가능한 큰 데이터 파일은 로컬에만 둡니다). 위 명령으로 각자 로컬에서 다시 만드세요.

### 2) 실제 리타게팅 결과 보정하기

```powershell
& "C:\Program Files\Blender Foundation\Blender 5.2\blender.exe" --background --python scripts/correct_hand_shape_prior.py -- --input output/<스무딩까지 끝난 결과>.blend --output output/<새 이름>.blend --prior extractor/hand_shape_prior.npz
```

기존 출력 경로가 있으면 중단합니다(새 파일명 사용).

## 검증한 것

- leave.mp4, love.mp4 둘 다에서, 스무딩(One-Euro filter)만 적용한 버전 대비 관절 떨림(프레임 간 회전 변화의 2차 차분)이 줄었고 새로운 부작용(더 큰 튐 발생)이 없음을 확인했습니다.
- 최종 결과: `output/leave_AvatarSample_F10_prior_corrected_v2.blend`, `output/love_4to7s_AvatarSample_F10_final_v1.blend`.

## 명시적으로 주장하지 않는 것

- "떨림이 줄었다"는 프레임 간 회전 변화량 기준이며, 수어 의미·손 모양의 정확도를 보증하는 지표가 아닙니다.
- 코퍼스는 1500개 단어의 SYN(합성) 데이터 기준입니다. 실제 사람 영상과의 시각적 차이가 있을 수 있습니다.
- 같은 종류의 문제를 딥러닝(가짜 노이즈 학습, 진짜 짝 학습)으로도 시도했으나 결과가 일관되지 않아 폐기했습니다 — 자세한 내용과 재현 방법은 `../HAND_DENOISER_ML_EXPERIMENTS.md` 참고.

