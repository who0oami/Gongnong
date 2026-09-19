# 자음 18개 손 모양 보정 실험

## 결론

자음 18개(`WORD3002`~`WORD3019`)에 기존 리타게팅, KNN 보정, Jihyeon 손가락 방향 보정을 각각 적용해 비교했다. 최종 테스트 결과는 `KNN + Jihyeon 보정`으로 정리했다.

| 처리 방식 | 평균 오차 |
| --- | ---: |
| 기존 리타게팅 | 27.98° |
| KNN만 적용 | 29.13° |
| KNN + Jihyeon 보정 | 20.69° |

이번 자음 세트에서는 KNN만 적용했을 때 기준 결과보다 좋아지지 않았다. KNN 결과 위에 Jihyeon 방식의 손가락 방향 계산을 적용한 결과는 18개 모두 KNN 결과보다 낮은 오차를 보였다. 급격한 손가락 튐을 막기 위해 최종 프레임 회전 변화는 16°/frame 이하로 제한했다.

## 처리 과정

1. MediaPipe Holistic으로 몸과 손 좌표를 추출했다.
2. 손 crop 재검출, 좌우 손 확인, 좌표 안정화를 적용했다.
3. 기존 아바타 리타게팅 결과를 `baseline`으로 저장했다.
4. baseline에 KNN hand-shape prior 보정을 적용해 `knn` 결과를 만들었다.
5. KNN 결과에 Jihyeon 방식의 손가락 chain/minimum-swing 방향 계산을 적용해 최종 결과를 만들었다.
6. 세 결과를 Blender에서 렌더링해 원본 영상과 비교할 수 있도록 저장했다.

팔, 손목, 몸통, 표정은 baseline을 유지하고 손가락 bone만 보정했다. 기존 브랜치의 코드와 결과 파일은 수정하지 않았다.

## 결과 위치

- 실행 코드와 검증 기록: [`experiments/consonants_knn_jihyeon_v1`](.)
- Blender 결과: [`output/consonant_final_v4`](../../output/consonant_final_v4)
- 팀 확인용 영상: [`output/consonant_jihyeon_test_v1/videos`](../../output/consonant_jihyeon_test_v1/videos)
- 브라우저 비교 화면: [`index.html`](index.html)

`consonant_final_v4`는 Blender에서 다시 열어 수정할 수 있는 `.blend` 결과를 보관하고, `consonant_jihyeon_test_v1/videos`는 원본·baseline·KNN·Jihyeon 결과를 MP4로 비교하기 위한 폴더다. 같은 결과를 중복으로 만든 것이 아니다.

## 기존 브랜치와의 관계

기존 KNN 작업 브랜치 `feature/knn-hand-shape-correction-jihyeon`은 삭제하거나 수정하지 않았다. 이 실험은 해당 브랜치와 Robin 리타게팅 브랜치의 코드를 읽기 전용으로 참고해 새 경로에서 실행한 것이다.

현재 공유 브랜치는 [`feature/consonants-knn-jihyeon-v1`](https://github.com/ssica16/ksl-tube/tree/feature/consonants-knn-jihyeon-v1)이고, 기존 KNN 브랜치는 [`feature/knn-hand-shape-correction-jihyeon`](https://github.com/ssica16/ksl-tube/tree/feature/knn-hand-shape-correction-jihyeon)에서 그대로 확인할 수 있다.

## 다음 작업

다음 단계에서는 흔들림을 줄이는 temporal filtering, 손목·팔과 손가락의 연동, 배경·카메라·조명·최종 렌더 설정을 별도 커밋으로 추가한다. 기존 결과를 덮어쓰지 않고 새 버전 폴더를 사용한다.

수치상 오차는 추출된 좌표와의 기하학적 일치도이므로 수어 의미의 정답을 보장하지 않는다. 최종 채택 전에는 비교 영상에서 원본과 아바타를 함께 확인한다.
