# M10 손 떨림·양손 관통 보정

검토 파일: `output/love_Model_M10_contact_v2.blend`.
원본: `output/love_Model_M10_hands_aligned_color_v1.blend` (보존).

```powershell
& "C:\Program Files\Blender Foundation\Blender 5.2\blender.exe" --background output/love_Model_M10_hands_aligned_color_v1.blend --python-exit-code 1 --python scripts/refine_hand_contact_stable.py -- --output output/NEW_NAME.blend
```

기존 출력 경로가 있으면 중단합니다. 원본 컬러, 재질, 메시, 좌우 뼈 연결을 유지하고 애니메이션 회전만 새 파일에서 보정합니다. 이 단계는 현재 30fps 입력 기준이며 다른 fps의 영상에서는 시간 창 조정이 필요합니다.

방식:
- 앞뒤 3프레임의 대칭 필터로 팔·손목·손가락 회전을 완화합니다.
- 끝마디 굽힘에 가운데 마디 굽힘의 약한 연동(20%)을 적용합니다. 손가락 모양을 새로 생성하지 않습니다.
- 손바닥 너비에 비례한 충돌용 캡슐로 양손 겹침을 찾습니다.
- 기존 양손 위치 차이 방향으로 최소 분리량을 찾고, 앞뒤 프레임까지 보정량을 완만하게 연결합니다.
- 손목을 직접 이동시켜 팔을 늘리는 대신 두 관절 IK로 어깨·팔꿈치를 조정합니다. 손의 방향은 유지합니다.
- 단어별 프레임 번호나 좌표를 보정 규칙에 넣지 않았습니다. 렌더 프레임 목록만 현재 영상의 검토용입니다.

검증 자료: `diagnostics/love_Model_M10_contact_v2/`의 `contact_audit.json`, `saved_comparison.json`, `full_mesh_audit.json`, 프레임 렌더.

`saved_comparison.json`은 수정 전후 손목 위치의 이차 차분과 실제 양손 표면의 삼각형 교차 수를 비교합니다. 위치의 급변 감소량은 추출 정확도 향상률이 아닙니다. 손 표면은 해당 손/손가락 뼈 가중치가 0.5를 초과하는 정점의 삼각형으로 정의합니다. 같은 손 내부의 손가락끼리 충돌, 몸/옷과의 충돌, 검사하지 않은 중간 시점까지 포괄하는 보증은 아닙니다.

충돌 여유와 시간 필터 때문에 원본보다 양손 사이에 간격이 생길 수 있습니다. 수어의 정확한 접촉 위치를 복원한 결과로 간주하지 않습니다. `contact_v1`은 일부 구간에서 떨림이 증가한 중간 테스트이며 사용하지 않습니다.

