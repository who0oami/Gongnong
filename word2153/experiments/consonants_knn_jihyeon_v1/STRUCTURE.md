# 브랜치 구조와 작업 분리

이 브랜치는 기존 `word2153/` 파이프라인의 파일을 수정하지 않고 자음 실험만 별도 경로에 둡니다.

```text
word2153/
├─ experiments/consonants_knn_jihyeon_v1/
│  ├─ extract_all.py          # 18개 원본 영상 → Holistic/손 crop/안정화 좌표
│  ├─ process_clip.py         # baseline → KNN → Jihyeon 보완 → .blend
│  ├─ process_all.py          # 18개 일괄 실행
│  ├─ render_clip.py          # Blender 결과를 상체/손 확대 PNG로 렌더
│  ├─ render_all.py            # PNG → MP4
│  ├─ verify_all.py            # 정수/중간 프레임 보존 검사
│  ├─ build_review.py          # 팀 공유용 비교 페이지/요약
│  ├─ vendor/                  # 참조한 외부 브랜치 코드의 고정 사본
│  ├─ runs/WORDxxxx/           # 로컬 실행 산출물; Git 제외
│  └─ TEAM_README.md
├─ output/consonant_final_v4/  # 최종 .blend 링크/manifest; 기존 output과 분리
└─ output/consonant_jihyeon_test_v1/videos/
   ├─ WORDxxxx_source.mp4
   ├─ WORDxxxx_baseline.mp4
   ├─ WORDxxxx_knn.mp4
   └─ WORDxxxx_jihyeon.mp4     # KNN + Jihyeon 손가락 방향 보완
```

## 작업 경계

- 이 브랜치가 담당하는 부분: 손 검출 안정화, KNN 손 모양 보정, 손가락 방향 보완, 결과 비교용 렌더.
- Robin에게 남긴 부분: 원본 검출 흔들림의 추가 안정화, 손목·팔과 손가락의 연동, 배경·카메라·조명·최종 렌더 스타일.
- `avatar_retarget/retarget/`의 Robin 코드를 원본 위치에 덮어쓰지 않았습니다. 필요한 solver만 `vendor/`에서 참조합니다.
- 다른 브랜치의 `frontend/`, `ai/`, `sign-keypoint-to-avatar/` 변경은 이 브랜치에 포함하지 않습니다.

## 팀원이 확인할 순서

1. `output/consonant_jihyeon_test_v1/videos/`에서 `*_source.mp4`와 `*_jihyeon.mp4`를 같은 동작으로 재생합니다.
2. 손 확대 파일에서 손가락 방향과 손바닥 회전이 원본과 맞는지 확인합니다.
3. 흔들림·배경·카메라를 수정할 때는 `runs/` 결과를 직접 덮지 말고 새 버전 폴더를 사용합니다.
4. 최종 채택 전에는 `.blend`를 Blender에서 열어 표정, 팔, 손목, 배경까지 확인합니다.
