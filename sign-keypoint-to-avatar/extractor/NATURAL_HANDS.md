# 손 관절 수정 결과 (2026-09-10)

현재 검토본: `output/love_Model_M3_hands_natural_v2.blend`.
이 문서는 BLENDER_HANDS.md의 이전 v4 결과 안내를 대체합니다. 이전 결과는 보존했으며 정상본으로 간주하지 않습니다.

사용 코드: `scripts/mediapipe_to_blender_natural.py`, 모델 고정 프로필: `mediapipe-preview/blender_natural_profile.json`, 입력: `keypoints/love_hands_stable_v3.json`.

- 표시용 bone tail 대신 실제 관절 위치로 손끝 방향을 계산합니다.
- 손바닥 축을 이전 프레임에 맞추려고 반전하지 않습니다. 해부학적 좌우 연결을 유지합니다.
- 엄지 첫 관절은 제한된 방향 회전, 나머지 두 관절은 손바닥 안쪽으로 접히는 축을 사용합니다.
- 검지~소지의 굽힘과 벌림을 분리하고 관절별 제한, 시간 필터를 적용합니다.
- 서로 다른 검출기의 손 방향을 섞지 않으며 손 모양 재추정은 원본과 일치할 때만 채택합니다.
- 단어별 좌표 수정은 없습니다. 새 영상은 `python scripts/run_hands_pipeline.py VIDEO --sign-id NAME`으로 실행하며 새 폴더에 저장합니다.

검증: 0/17/34/51/67 및 추가 프레임의 손 확대 렌더, 전체 296프레임 렌더를 비교했습니다. 저장된 파일을 다시 불러와 36개 뼈의 전체 프레임과 295개 중간 프레임에서 회전 변화량, 관절 제한, 보간 및 스케일을 검사했습니다.

렌더와 원본 동기 비교: `diagnostics/love_Model_M3_hands_natural_v2/20260910-154802/playback.html` (프로젝트 루트의 HTTP 서버로 열기).
수치 검사: `diagnostics/love_Model_M3_hands_natural_v2_motion_audit/audit.json`.

두 손의 접촉에는 겹침이 남습니다. 단일 영상의 가려진 손가락 깊이는 추정값이며 이 검사는 수어 의미의 정확성을 보장하지 않습니다. 입력 자체의 거울 반전 여부를 자동 판정하지 않으며 임의 좌우 반전은 적용하지 않았습니다.
