# 자음 18개 · KNN + Jihyeon 손 모양 보정

자음 수어 영상 18개를 대상으로 손 키포인트를 추출하고, 기존 리타게팅 결과에 KNN 손 모양 보정과 Jihyeon 손가락 방향 보정을 적용해 비교하는 독립 실험입니다.

기존 `word2153/` 파이프라인, `feature/knn-hand-shape-correction-jihyeon` 브랜치, Robin 리타게팅 코드는 수정하지 않습니다. 이 실험의 코드는 `experiments/consonants_knn_jihyeon_v1/` 안에서만 실행하며, 결과도 별도 폴더에 저장합니다.

## 폴더 구조

```text
word2153/
├─ experiments/consonants_knn_jihyeon_v1/
│  ├─ extract_all.py       영상 18개 → raw/refined/stable/smoothed JSON
│  ├─ process_all.py       baseline/knn/knn+Jihyeon .blend 생성
│  ├─ render_all.py        Blender 렌더 → 비교 MP4
│  ├─ verify_all.py        저장 결과 보존 검증
│  ├─ build_review.py      비교 화면과 요약 생성
│  ├─ vendor/              참고 브랜치 코드의 읽기 전용 스냅샷
│  ├─ runs/                실행 결과 — 용량 문제로 git 미포함
│  └─ TEAM_README.md       이 실험 설명
├─ output/consonant_final_v4/
│                          Blender에서 다시 여는 .blend 결과
└─ output/consonant_jihyeon_test_v1/videos/
                           원본/기존/KNN/Jihyeon 비교용 MP4
```

`consonant_final_v4`와 `consonant_jihyeon_test_v1/videos`는 같은 파일을 중복한 폴더가 아닙니다. 전자는 Blender 편집용 `.blend`, 후자는 영상 검토용 `.mp4`를 보관합니다.

## 처리 대상

`output/consonant_replacements`, `output/consonant_recordings`의 `WORD3002`~`WORD3019`입니다.

```text
ㄴ ㄷ ㄹ ㅁ ㅂ ㅅ ㅇ ㅈ ㅊ ㅋ ㅌ ㅍ ㅎ ㄲ ㄸ ㅃ ㅆ ㅉ
```

## 처리 과정

1. MediaPipe Holistic으로 몸·손 키포인트를 추출합니다.
2. 손 crop 재검출, 좌우 손 확인, 시간 평활을 적용합니다.
3. 기존 per-video 리타게팅 결과를 `baseline`으로 생성합니다.
4. baseline에 hand-shape KNN prior 보정을 적용해 `knn` 결과를 생성합니다.
5. knn 결과에 손바닥 기준 chain/minimum-swing 손가락 방향 보정을 적용해 `knn + Jihyeon` 결과를 생성합니다.
6. 세 결과를 Blender에서 렌더해 원본 영상과 비교합니다.

팔·손목·몸통·표정은 baseline을 유지하고 손가락 bone만 보정합니다. KNN 보정이 관측 손 모양에서 더 멀어지는 경우에는 baseline으로 되돌립니다. 최종 손가락 회전 변화는 30fps 기준 16°/frame 이하로 제한합니다.

## 빠른 시작

PowerShell에서 `word2153` 디렉터리 기준으로 실행합니다.

```powershell
python experiments/consonants_knn_jihyeon_v1/extract_all.py
python experiments/consonants_knn_jihyeon_v1/process_all.py
python experiments/consonants_knn_jihyeon_v1/render_all.py
& "C:\Program Files\Blender Foundation\Blender 5.2\blender.exe" --background --python-exit-code 1 --python experiments/consonants_knn_jihyeon_v1/verify_all.py
python experiments/consonants_knn_jihyeon_v1/build_review.py
```

각 단계는 이미 검증된 `runs/<word_id>/` 결과를 다시 덮어쓰지 않습니다. 새 결과를 만들 때는 새 버전 폴더를 사용합니다.

## 결과 확인

- 비교 화면: `experiments/consonants_knn_jihyeon_v1/index.html`
- 영상: `output/consonant_jihyeon_test_v1/videos/WORDxxxx_*.mp4`
- Blender 파일: `output/consonant_final_v4/WORDxxxx_knn_jihyeon_v4.blend`
- 검증 결과: `experiments/consonants_knn_jihyeon_v1/preservation_verification.json`

Blender 파일은 Blender 5.2에서 열고 3D 뷰포트에 마우스를 둔 뒤 Space bar로 재생합니다. MP4는 원본, baseline, KNN, Jihyeon 결과를 같은 동작 번호로 비교합니다.

## 확인 결과

18개, 총 1,454프레임을 처리했습니다. 손 좌표와 아바타 손가락 방향의 평균 오차는 baseline 27.98°, KNN 29.13°, KNN + Jihyeon 20.69°였습니다. 저장된 blend를 다시 열어 정수·중간 프레임을 검사했으며, 손가락 이외의 bone·오브젝트·얼굴 shape key 최대 오차는 0.0이었습니다.

이번 자음 세트에서는 KNN 단독 결과가 baseline보다 좋아지지 않았습니다. KNN + Jihyeon 결과는 18개 모두 KNN보다 낮은 오차를 보였습니다.

## 브랜치와 참고 코드

- 현재 실험 브랜치: `feature/consonants-knn-jihyeon-v1`
- KNN 참고 브랜치: `feature/knn-hand-shape-correction-jihyeon`
- 리타게팅 참고 코드: `vendor/robin/`

참고 코드는 읽기 전용으로 복사했으며 원래 브랜치 파일을 덮어쓰지 않았습니다.

## 명시적으로 확인하지 않은 것

- 오차 수치는 추출 키포인트와의 기하학적 일치도이지 수어 의미 정확도 점수가 아닙니다.
- MediaPipe 검출 자체가 틀린 프레임을 자동으로 복원하지는 않습니다.
- 흔들림의 최종 보정, 손목·팔 연동, 배경·카메라·조명·최종 렌더 설정은 다음 작업 범위입니다.
- 최종 채택 전에는 원본 영상과 MP4를 함께 재생해 사람이 직접 확인해야 합니다.
