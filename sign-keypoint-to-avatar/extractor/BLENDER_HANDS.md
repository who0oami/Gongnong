# 손 정밀 추출과 Blender 연동

현재 확인용 결과는 `output/love_Model_M3_hands_v4.blend`입니다.
입력은 `keypoints/love_hands_v3.json`, 모델 고정 설정은 `mediapipe-preview/blender_profile.json`입니다.
이전 Blender 코드, retarget_profile.json, WORD2153 결과는 수정하지 않았습니다.

## 재사용

현재 sign-keypoint-to-avatar 폴더(이전 이름 word2153)에서 아래처럼 실행합니다. 단어마다 좌표나 코드를 수정하지 않습니다.

```powershell
python scripts/run_hands_pipeline.py "C:\Users\ESTsoft\Desktop\TEST\love.mp4" --sign-id love --label 사랑
```

출력은 `output/<sign-id>_hands_<실행시각>/` 아래 새 파일로 저장합니다.
처음 실행 시 Google 공식 Holistic/Hand 모델 다운로드에 네트워크가 필요합니다.
Blender 경로는 `--blender`, 모델 프로필은 `--profile`로 변경합니다.
현재 기본 프로필은 M3의 손 뼈 구조용입니다. 다른 모델은 해당 모델용 프로필 검증이 필요합니다.

이미 추출한 손 JSON만 Blender에 넣을 수도 있습니다.

```powershell
& "C:\Program Files\Blender Foundation\Blender 5.2\blender.exe" --background --factory-startup --python-exit-code 1 --python scripts/mediapipe_to_blender.py -- --motion keypoints/love_hands_v3.json --output output/love_Model_M3_hands_new.blend --render
```

Blender에서 3D 뷰 위에 마우스를 놓고 Space로 재생합니다. 타임라인의 `REVIEW_L/R/LR`는 검출이나 좌우 판별을 검토해야 하는 구간입니다. `OBSERVED_L_R`는 두 손의 관측을 적용했다는 뜻이며 수어 정확도를 보증하지 않습니다.

## 방식과 좌우 기준

- 원본 픽셀을 반전/회전하지 않고 손 주변을 정사각형으로 잘라 두 크기로 재추론합니다.
- 양 크기의 2D 관절 위치와 3D 손바닥 법선 및 손가락 방향이 일치할 때만 교체합니다.
- 사람의 왼팔은 Pose 11/13/15 → left_hand → J_Bip_L, 오른팔은 12/14/16 → right_hand → J_Bip_R로 고정합니다.
- 손 전용 모델의 Left/Right 분류 점수는 기록만 합니다. 손가락 좌표 신뢰도로 사용하거나 그 라벨만으로 좌우를 교환하지 않습니다.
- 손목 후보가 반대 손목과 더 가깝거나 두 손목이 겹쳐 구분하기 어려우면 재추론 채택을 거부합니다. 화면의 x좌표로 좌우를 정렬하지 않습니다.
- 원본 자체가 거울 영상인지 자동으로 판정하지는 않습니다. 현재 입력은 비반전 영상으로 취급하며 임의 반전 옵션을 적용하지 않았습니다.
- 원점이 다른 몸/손 world 좌표는 직접 합치지 않습니다. 팔은 몸 좌표 방향, 손목은 손바닥 기준 방향을 사용합니다.
- 모델 리그 정보를 매번 새로 읽습니다. 좌표변환 행렬식 +1을 검사해 변환 중 거울 반사를 금지합니다.
- 검지~소지는 MCP 굽힘/벌어짐, PIP/DIP 굽힘을 분리합니다. 엄지 3관절은 3D 방향으로 대립 운동을 적용합니다.
- 누락 시 손 회전은 최대 2프레임만 유지하고 이후 기본 자세로 돌아가며 모두 audit에 기록합니다. 긴 가림을 임의 보간하지 않습니다.
- 손가락 최대 굽힘과 벌어짐은 모델 프로필에서 조정합니다. 단어별 수치 보정은 없습니다.

## 현재 실제 결과와 한계

296프레임에서 기존 Holistic 결과 중 왼손 19프레임, 오른손 55프레임을 2D/3D 합의가 있는 확대 추론으로 교체했습니다. 검출 수는 늘지 않았습니다. 정답 좌표가 없어 정밀도 향상률을 수치로 주장할 수 없습니다.

확대 추론에 따른 월드 좌표의 깊이 및 손바닥 자세도 추정치입니다. 단일 영상에서 가려진 손가락, 양손 접촉 위치, 손끝 충돌을 정확하게 복원했다고 볼 수 없습니다. 영상 자체에 로딩/검은 화면이 포함됩니다. 수어 의미와 자연스러움은 원본 및 수어 사용자 검토가 필요합니다.

`diagnostics/love_Model_M3_hands_v4/20260910-112132/comparison.html`에서 원본, 좌우 표시 오버레이, Blender 손 확대 렌더를 비교할 수 있습니다. 0/17/34/51/67 및 180/200/220 프레임을 저장했습니다.

같은 폴더 `audit.json`은 좌우 관측/유지/누락 상태와 좌표변환을, `rig_info.json`은 실제 모델의 기본 뼈 구조를 기록합니다. 방향 오차 항목은 직접 방향을 적용한 팔/엄지의 내부 매핑 검사이며 검지~소지 또는 추출 정답 오차를 뜻하지 않습니다.

회귀 검사: `python scripts/check_hand_identity.py` (팔 교차, 반대 손 후보, 겹친 손목, 먼 오검출 등 6개 검사).

v2 Blender는 모든 손가락을 독립 3D 방향으로 적용한 중간 결과이며 일부 비틀림이 있습니다. v3에서 관절 굽힘으로 수정했고 v4는 같은 자세에 프로필 설정과 검토 타임라인을 추가했습니다. 모두 보존했습니다.

공식 Hand Landmarker 모델/API: https://developers.google.com/edge/mediapipe/solutions/vision/hand_landmarker/index
