# MediaPipe Holistic → JSON → Babylon.js

현재 폴더(sign-keypoint-to-avatar, 이전 이름 word2153)에서 실행합니다. 기존 Blender 결과, 코드, retarget_profile.json은 유지합니다.

## 추출

Python 3.13.15 / MediaPipe 1.0.1 / OpenCV 5.0.0 환경에서 love.mp4를 실제 처리했습니다.
새 환경은 `python -m pip install -r extractor/requirements.txt`로 설치합니다.
MediaPipe가 설치하는 opencv-contrib-python에 cv2가 포함되므로 opencv-python을 중복 설치할 필요는 없습니다.

```powershell
python extractor/extract_keypoints.py "C:\Users\ESTsoft\Desktop\TEST\love.mp4" --output keypoints/love_v2.json --sign-id love --label 사랑 --download-model
```

최초 한 번 공식 모델을 내려받습니다. 이후 로컬 모델을 재사용합니다.
기존 출력 파일명이 있으면 오류로 중단합니다. 단어별 코드를 수정하지 않고 영상, 출력 경로, ID와 라벨만 바꿉니다.
한 영상은 한 사람을 대상으로 합니다. 거울 반전은 자동 적용하지 않습니다.
얼굴 포인트와 blendshape 점수가 필요하면 `--include-face`를 추가합니다.

JSON의 `pose`(33), `left_hand`(21), `right_hand`(21)는 정규화 영상 좌표입니다.
각각의 `_world` 필드는 미터 단위 3D 추정 좌표이며 몸과 손의 원점은 서로 다릅니다.
미검출은 빈 배열로 남깁니다. 프레임 시간은 디코더의 타임스탬프를 우선하고, 사용할 수 없으면 FPS로 계산합니다.
모델 SHA256, 라이브러리 버전, 검출 프레임 수를 메타데이터에 기록합니다.

## 테스트 화면

`scripts/run_mediapipe_preview.cmd`를 실행합니다. 로컬 서버와 브라우저가 열립니다.
재생 버튼 또는 Space로 재생하며 슬라이더로 개별 프레임을 확인합니다.
상단에서 다른 영상과 해당 JSON을 선택할 수 있습니다.
Babylon.js와 로더는 공식 CDN을 사용하므로 화면 최초 로딩에 인터넷 연결이 필요합니다.

`mediapipe-preview/profile.json`은 Model_M3용 고정 팔 프로필입니다.
기본 뼈 방향은 로딩한 모델에서 계산하고 부모 좌표계에서 상완, 하완, 손목 방향을 맞춥니다.
손목은 손의 0→9 방향을 사용하며 손바닥 법선에 따른 완전한 비틀림은 아직 적용하지 않습니다.
손가락은 JSON/오버레이에만 포함되며 아바타 손가락과 얼굴은 움직이지 않습니다.
팔 미검출 또는 낮은 visibility 구간은 기본 자세로 돌아갑니다. 이 단계에서는 보간으로 가리지 않습니다.

`assets/Model_M3.glb`는 `Downloads/Model_M3.vrm`의 바이너리 복사본입니다.
VRM의 glTF 뼈대·스킨을 Babylon glTF 로더로 읽습니다. VRM 전용 셰이더, 표정, 스프링본 지원은 포함하지 않습니다.
원본 영상과 아바타 복사본, 다운로드한 추론 모델, 로컬 검증 도구는 각 폴더의 .gitignore에 포함했습니다.

## 실제 검증 및 남은 한계

- `keypoints/love.json`: 296프레임, 30 FPS. 몸 292, 왼손 151, 오른손 114프레임 검출.
- Edge에서 모델 로딩, 실제 재생, 0/17/34/51/67/148/220/295 프레임 탐색을 확인했습니다.
- 비교 이미지와 실행 보고서: `diagnostics/mediapipe-love-v1/20260910-110814/`.
- 원본 파일에는 플레이어 UI, 로딩 표시, 검은 화면이 녹화되어 있습니다. 예를 들어 51프레임에서 사람이 없고 아바타는 기본 자세입니다.
- 초기 카메라/탐색 오류가 있던 검증 이미지는 상위 `diagnostics/mediapipe-love-v1/`에 보존했습니다. 최종 비교는 위 타임스탬프 폴더를 사용합니다.
- 실행 경로 검증 결과이며 완성된 수어 품질을 의미하지 않습니다. 손가락 모양, 손바닥 비틀림, 양손 접촉, 미검출 구간 처리는 후속 작업입니다.
- 기존 Blender 입력은 BODY_25 및 별도 얼굴 배열입니다. 새 JSON을 `run_motion.cmd`에 바로 넣으면 안 됩니다. Blender 연결에는 별도 좌표/인덱스 변환기가 필요합니다.

공식 자료:
- https://developers.google.com/edge/mediapipe/solutions/vision/holistic_landmarker/python
- https://developers.google.com/edge/mediapipe/solutions/vision/holistic_landmarker/index

검증 재실행(로컬 Playwright 설치 필요): `python scripts/verify_mediapipe_preview.py`.
새 검증 결과는 시간별 새 폴더에 저장합니다.
