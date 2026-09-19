# 자음 18개 · KNN + Jihyeon 손 모양 보정

**작성자**: Jihyeon (2026-09)

## 무엇을 하는가

`ㄴ`부터 `ㅉ`까지 자음 18개 영상의 손 모양을 기존 아바타 결과와 비교하고, 손가락 방향이 어긋나는 프레임을 보정하는 별도 테스트입니다.

기존 출력이나 기존 브랜치의 파일을 덮어쓰지 않습니다. 각 동작은 `baseline`, `knn`, `knn + Jihyeon` 세 결과로 새로 저장합니다.

## 왜 필요한가

단안 영상에서 손을 추출하면 손 crop 검출과 Holistic 검출이 프레임마다 다르게 잡힐 수 있습니다. 그 결과 손가락이 떨리거나, 손가락 방향과 손바닥 방향이 실제 영상과 다르게 보일 수 있습니다.

KNN은 기존 3D 손 모양 코퍼스에서 가까운 모양을 찾아 굽힘 크기를 보정합니다. Jihyeon 보정은 손바닥과 부모 마디를 기준으로 손가락 방향을 다시 계산합니다. 두 방법을 같은 입력 영상에 적용해 결과를 비교했습니다.

## 처리 대상

`output/consonant_replacements`, `output/consonant_recordings`의 다음 18개입니다.

```text
WORD3002 ㄴ   WORD3003 ㄷ   WORD3004 ㄹ   WORD3005 ㅁ
WORD3006 ㅂ   WORD3007 ㅅ   WORD3008 ㅇ   WORD3009 ㅈ
WORD3010 ㅊ   WORD3011 ㅋ   WORD3012 ㅌ   WORD3013 ㅍ
WORD3014 ㅎ   WORD3015 ㄲ   WORD3016 ㄸ   WORD3017 ㅃ
WORD3018 ㅆ   WORD3019 ㅉ
```

## 처리 순서

1. MediaPipe Holistic으로 몸·손 좌표를 추출합니다.
2. 손 crop 재검출, 좌우 손 확인, 시간 평활을 적용합니다.
3. 기존 per-video 리타게팅을 `baseline`으로 저장합니다.
4. `baseline`에 hand-shape KNN 보정을 적용해 `knn`을 저장합니다.
5. `knn` 결과에 손바닥 기준 손가락 chain/minimum-swing 방향 계산을 적용해 `knn + Jihyeon`을 저장합니다.
6. Blender에서 전체 동작과 손 확대 영상을 렌더해 원본 영상과 비교합니다.

팔·손목·몸통·표정은 baseline을 유지하고 손가락 bone만 보정합니다. KNN 보정이 관측 손 모양에서 더 멀어지는 경우에는 baseline으로 되돌립니다. 최종 손가락 회전 변화는 30fps 기준 16°/frame 이하로 제한했습니다.

## 결과

손 좌표와 아바타 손가락 방향의 평균 오차는 다음과 같습니다.

| 결과 | 평균 오차 |
| --- | ---: |
| baseline | 27.98° |
| knn | 29.13° |
| knn + Jihyeon | 20.69° |

이번 자음 18개에서는 KNN만 적용한 결과가 baseline보다 좋아지지 않았습니다. KNN 위에 Jihyeon 손가락 방향 보정을 적용한 결과는 18개 모두 KNN보다 낮은 오차를 보였습니다.

저장된 blend를 다시 열어 정수·중간 프레임을 검사했습니다. 손가락 이외의 bone, 오브젝트, 얼굴 shape key의 최대 오차는 0.0이었고, 18개 모두 보존 검사를 통과했습니다.

## 파일 위치

- 실행 코드·검증 기록: `experiments/consonants_knn_jihyeon_v1/`
- Blender 결과: `output/consonant_final_v4/`
- 비교용 영상: `output/consonant_jihyeon_test_v1/videos/`
- 비교 화면: `index.html`

`consonant_final_v4`는 Blender에서 다시 열 수 있는 `.blend` 파일입니다. `consonant_jihyeon_test_v1/videos`는 원본, baseline, KNN, Jihyeon 결과를 MP4로 확인하는 폴더입니다. 목적이 달라 두 폴더로 나누어 보관합니다.

## 기존 브랜치와의 관계

기존 KNN 브랜치 `feature/knn-hand-shape-correction-jihyeon`은 삭제하거나 수정하지 않았습니다. 이 실험은 해당 브랜치와 리타게팅 참고 코드를 `vendor/`에 읽기 전용 스냅샷으로 두고 별도 경로에서 실행합니다.

현재 브랜치:

`feature/consonants-knn-jihyeon-v1`

## 명시적으로 주장하지 않는 것

- 오차 수치는 MediaPipe에서 추출한 손 좌표와의 기하학적 일치도이며 수어 의미 정확도 점수가 아닙니다.
- 원본 검출이 잘못된 프레임을 자동으로 정답으로 바꾸지는 않습니다.
- 흔들림의 최종 보정, 손목·팔 연동, 배경·카메라·조명 설정은 이 실험의 범위가 아닙니다.
- 최종 채택 전에는 원본 영상과 MP4를 함께 재생해 사람이 직접 확인해야 합니다.

## 팀원 다음 작업

로빈은 이 결과를 기준으로 프레임 흔들림, 손목과 손가락의 연동, 배경·카메라·조명·최종 렌더 설정을 이어서 확인합니다. 기존 결과를 덮어쓰지 않고 새 버전 폴더와 새 커밋으로 작업합니다.
