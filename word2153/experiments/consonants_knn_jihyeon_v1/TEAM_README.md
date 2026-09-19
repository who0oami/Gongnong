# 자음 수어 아바타 손 모양 보정 실험

팀 공유용 기록입니다. 이 브랜치는 기존 자음 결과를 덮어쓰지 않고, `ㄴ`부터 `ㅉ`까지 18개 동작을 대상으로 손 모양 보정 결과를 별도 생성한 실험 브랜치입니다.

## 브랜치

`feature/consonants-knn-jihyeon-v1`

비교한 기준 커밋은 다음과 같습니다.

- KNN 손 모양 보정: `feature/knn-hand-shape-correction-jihyeon` / `1a695fa01001631bb20b39b08d8ab72e63e5b176`
- 기존 리타게팅 참고: `ksl-tube-Robin` / `0148313d112b64a679f12e0082b872633370c582`

## 이번에 한 작업

1. `WORD3002`~`WORD3019` 원본 자음 영상 18개를 대상으로 MediaPipe Holistic 손·몸 키포인트를 추출했습니다.
2. 손 crop 재검출과 해부학적 좌우 손 확인을 거쳐 안정화된 손 좌표를 만들었습니다.
3. 기존 아바타 리타게팅 결과를 기준으로 KNN hand-shape prior 보정을 적용했습니다.
4. Robin 브랜치의 손가락 chain/minimum-swing 방향 계산 아이디어를 MediaPipe 손 좌표에 연결했습니다.
5. KNN 결과에서 관측 손 모양과 더 멀어지는 보정은 거부하고, 보정 회전량과 프레임 간 회전 변화를 제한했습니다.
6. Blender 결과를 동작별 `.blend`와 MP4로 저장했습니다. `baseline`, `knn`, `jihyeon` 세 결과와 손 확대 영상을 함께 비교할 수 있습니다.

## 결과 위치

- 코드와 실험 기록: `experiments/consonants_knn_jihyeon_v1/`
- Blender 결과: `output/consonant_final_v4/`
- 팀 확인용 MP4: `output/consonant_jihyeon_test_v1/videos/`
- 원본/기존/KNN/Jihyeon 결과 비교: `experiments/consonants_knn_jihyeon_v1/index.html`
- 보존 검증: `experiments/consonants_knn_jihyeon_v1/preservation_verification.json`

## 확인된 수치

18개, 총 1,454 프레임을 처리했습니다. 추출된 손가락 방향과의 평균 오차는 기존 방식 28.0°, KNN 29.1°, KNN+Jihyeon 20.7°였습니다. KNN+Jihyeon 결과는 18개 모두 KNN 결과보다 이 지표가 낮았습니다. 최종 보정의 프레임 간 손가락 회전 변화는 16° 이내로 제한했습니다.

이 지표는 추출 키포인트와의 기하학적 일치도이며 수어 의미 정확도 점수가 아닙니다. 원본 영상과 아바타 영상을 함께 보고 손가락 방향, 손바닥 방향, 두 손 접촉을 확인해야 합니다.

## 로빈이 이어서 볼 부분

이번 브랜치에서는 손 모양과 손가락 방향 보정까지만 다뤘습니다. 흔들림의 원인이 되는 원본 검출 노이즈, 몸통·손목과 손가락 사이의 연동, 배경·카메라·조명·렌더 스타일은 최종 처리로 확정하지 않았습니다. 로빈은 다음을 이어서 확인하면 됩니다.

- 원본 영상 대비 프레임 흔들림과 손목 roll 안정화
- 손가락 보정이 빠른 동작을 늦추거나 과하게 펴는 프레임 검토
- 배경, 카메라 구도, 조명, 렌더 출력 통일
- 18개 중 실제 수어 형태가 개선되지 않은 동작의 개별 제외 또는 파라미터 조정

## 재실행

Blender와 추출 모델이 준비된 환경에서 `extract_all.py`, `process_all.py`, `render_all.py` 순서로 실행합니다. 기존 결과를 덮어쓰지 않도록 각 단계는 이미 존재하는 결과를 거부하거나 검증된 결과를 재사용합니다. 대용량 `.blend`와 `.mp4`는 저장소의 ignore 규칙상 Git 커밋에 포함하지 않고 로컬 결과 폴더에 보관합니다.
