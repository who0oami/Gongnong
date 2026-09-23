# Idle 마지막 프레임 연장

`video_merger.merge_timeline_to_video()`는 실제 수어 파일이 있는 segment의
trailing idle을 `_extend_last_frame()`으로 처리한다. gap과 missing clip
자리의 fallback은 기존 idle 생성 및 duration 캐시를 그대로 사용한다.
실제 수어 파일이 하나도 없으면 trailing idle도 기존 방식을 사용한다.
혼합 segment가 missing fallback으로 끝나는 경우 그 마지막 출력 프레임을
연장하여 기존 fallback 순서를 보존한다.

배속 없는 segment는 마지막 part만 연장한 뒤 앞 part와 stream copy
concat한다. normalize 캐시 파일은 덮어쓰지 않으며, 이후 segment가 같은
원본을 참조해도 idle이 중복 삽입되지 않는다. 배속이 있으면 기존 segment
전체 배속 결과를 만든 뒤 연장한다. `setpts`와 `tpad`를 한 필터로 합치면
기존 speed 단계의 muxer 프레임 반올림까지 같다는 보장이 없어서 합치지
않았다. 현재 timeline 정책상 배속 증가와 trailing idle은 보통 동시에
발생하지 않지만 이 입력도 회귀 테스트한다.

```text
ffmpeg -y -hide_banner -loglevel error -i <last-part-or-speed-output>
  -vf tpad=stop_mode=clone:stop=<N>
  -an -c:v libx264 -preset veryfast -pix_fmt yuv420p <extended.mp4>
```

`extended.mp4`는 sign과 연장 프레임이 함께 있는 파일이다. 별도의 idle
파일을 만들지 않는다. preset은 이 추가 인코딩에만 적용하며 normalize와
speed의 설정은 바꾸지 않는다. 기존 기본 CRF는 유지하지만 preset과 추가
손실 인코딩으로 바이트/픽셀 결과나 파일 크기는 달라질 수 있다. idle 구간의
시각적 내용은 의도적으로 기본 포즈에서 마지막 출력 프레임으로 바뀐다.

## 프레임 수

기존 idle 생성에 전달하던 `f"{duration:.3f}"`를 그대로 기준으로 삼는다.
실측상 이미지 `-t` 경로는 30fps 시간 단위로 반올림(최소 1프레임), 이미지가
없을 때의 lavfi color 경로는 올림이었다. `_idle_frame_count()`가 이 차이를
보존한다. `stop_duration` 대신 정수 `stop=N`을 사용해 짧은 idle이 0프레임이
되거나 기존보다 한 프레임씩 늘어나는 누적 오차를 막는다.
FFmpeg 버전을 바꿀 때에는 실제 FFmpeg 회귀 테스트를 다시 실행한다.

## 로그

- `idle_extended_count`: trailing idle을 프레임 연장으로 처리한 segment 수.
- `idle_fallback_count`: 실제 sign이 없어 기존 trailing idle 경로를 쓴 segment 수.
  캐시 hit도 포함하며 FFmpeg 실행 수와 다르다.
- `idle_extension: count=... total=...s`: 연장 FFmpeg 호출 수와 전체 실행 시간.
  sign part 재인코딩 비용도 포함한다.
- `idle_extension_total`: 위 total과 같은 값. 합산할 때 이중 집계하지 않는다.
- `idle_pose`: fallback뿐 아니라 gap/missing 자리 생성도 포함한 실제 호출 수.
- 기존 normalize/idle/probe 캐시 통계, VIDEO_MERGE, TOTAL은 유지한다.

성능 비교에서는 `idle_pose` 시간만 비교하지 말고 `idle_extension`, `concat`,
`merge_total`도 함께 비교한다. 마지막 sign이 길거나 동일 duration의 idle
캐시 적중률이 높으면 이 방식의 이득이 작거나 느려질 수 있다.

## 검증

```powershell
.venv\Scripts\python.exe -m pytest tests/test_idle_extension.py tests/test_render_timing.py tests/test_clip_probe.py tests/test_timeline_builder.py tests/test_job_clips.py tests/test_timing.py -q
```

단일/다중 sign, sign 없음, missing fallback, idle 없음, speed 후 idle,
매우 짧은 idle, 긴 idle, 이미지 없음, 캐시 독립성을 검증한다.
실제 FFmpeg로 기존 sign+idle concat과 연장 결과를 비교한다. 뒤에 다른
클립도 붙여 최종 duration/프레임 수/디코딩된 PTS가 같은지 검사하고 전체
디코딩의 경고가 없는지 확인한다. 입력 timeline은 수정하지 않는다.

H.264 B-frame에서는 패킷 저장 순서의 PTS가 단조 증가할 필요는 없다.
검증 대상은 디코딩된 프레임 PTS와 DTS 순서이며 전체 디코딩 시 DTS 경고도
확인한다. 전체 파이프라인에 기존부터 있던 프레임 단위 오차는 이 변경으로
재설계하지 않는다.

## 로컬 측정 결과

운영 자산이 아닌 로컬 demo WORD0058/WORD0179/WORD0313을 반복 사용하는
17-segment 비교 입력:
14개 sign segment, 3개 sign 없는 segment, 각 idle은 `0.2 + index * 0.073`초,
speed=1, gap 없음. 기존 trailing idle 생성 분기와 새 분기를 순차 실행했다.
사용자가 제시한 운영 영상 자체를 재실행한 결과는 아니다.

| 항목 | 기존 | 변경 후 |
| --- | --- | --- |
| idle_pose | 17회 / 9.69초 | 3회 / 1.92초 |
| idle_extension | 0회 | 14회 / 7.52초 |
| concat | 15회 / 3.08초 | 1회 / 0.33초 |
| merge_total | 14.68초 | 11.90초 |
| 영상 duration | 39.566667초 | 39.566667초 |
| 프레임 수 | 1187 | 1187 |

병합 약 2.78초(19%) 감소. extension 인코딩 비용이 발생하므로 idle 생성
시간 감소를 그대로 전체 절감으로 계산하면 안 된다. timeline 종료는
39.561332초로 최종 영상과 약 0.0053초 차이이며 변경 전후 같다.
양쪽 전체 디코딩에 경고가 없었다. 운영 VIDEO_MERGE 45.54초, TOTAL 65.08초의
변경 후 수치는 실제 동일 작업 재실행이 필요하다.

처음에는 extension에도 기본 preset을 사용했지만 같은 구성에서 merge가
16.25→16.22초로 사실상 같았다. extension에만 veryfast를 적용한 후 위
결과를 얻었다. 단일 비교 실행이므로 부하·캐시·영상 구성에 따라 달라진다.
