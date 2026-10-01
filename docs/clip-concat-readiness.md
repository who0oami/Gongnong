# 조건부 normalize 조사 및 운용

## 실제 파일 조사

로컬 `backend/static/videos/WORD*.mp4` 임시/demo 파일 13개를 ffprobe로 조사했다.
이 파일들은 운영 자산이 아니며 조사 결과를 production S3 WORD 규격으로
일반화할 수 없다. 운영 S3 migration은 수행되지 않았다.
S3 다운로드는 현재 환경의 AWS 자격증명 부재(`NoCredentialsError`)로
검증하지 못했다. 로컬 파일이 S3 객체와 동일하다고 가정하지 않는다.
로컬 SEN 파일은 없었다. S3 변경/업로드는 수행하지 않았다.

| 속성 | 로컬 WORD 13개 | 현재 normalize 출력 표본 |
| --- | --- | --- |
| 크기 | 1920×1080 | 1920×1080 |
| r_frame_rate / avg_frame_rate | 30/1 / 30/1 | 30/1 / 30/1 |
| 코덱 / profile / level | H.264 / High / 40 | H.264 / High / 40 |
| 픽셀 형식 / field order | yuv420p / progressive | yuv420p / progressive |
| 오디오 | 없음 | 없음 |
| time_base | 1/15360 | 1/15360 |
| SAR / DAR | 1:1 / 16:9 | 1:1 / 16:9 |
| 시작 시각 | 0 | 0 |
| has_b_frames | 0 | 2 |
| 첫 PTS / DTS | 0 / 0 | 0 / -1024 |
| extradata | 50 bytes (WORD0058 표본) | SPS/PPS 내용이 원본과 다름 |

| 파일 | duration (초) |
| --- | --- |
| WORD0058 | 1.633333 |
| WORD0179 | 1.433333 |
| WORD0313 | 2.466667 |
| WORD0500 | 1.966667 |
| WORD0949 | 2.266667 |
| WORD1130 | 1.333333 |
| WORD1144 | 1.533333 |
| WORD1149 | 1.433333 |
| WORD1157 | 1.600000 |
| WORD1193 | 1.666667 |
| WORD1351 | 1.466667 |
| WORD1584 | 1.800000 |
| WORD2551 | 3.400000 |

`_normalize_clip()`은 scale/pad로 화면 크기를 맞추고 fps 필터로 30fps를
만들며 오디오를 제거하고 libx264/yuv420p로 재인코딩한다. 이 과정은
MP4 time_base와 패킷의 프레젠테이션/디코딩 타이밍도 새로 생성한다.

기본 규격만 보고 로컬 WORD의 normalize를 강제로 생략한 실험에서는
idle/speed 출력과 혼합 concat한 영상이 7.366667초에서 7.233333초로 변했고,
디코딩 시 non-monotonic DTS 경고가 발생했다. 따라서 B-frame이 없는
현재 로컬 WORD를 바로 재사용하는 것은 이 파이프라인에서 안전하지 않다.

## 생략 조건과 probe 공유

`services/clip_probe.py`의 `is_clip_concat_ready(metadata)`는 비디오 스트림
하나, 기본 출력 규격, High/Level 4.0, SAR 1:1, progressive, time_base
1/15360, 시작 시각 0, AVC extradata 존재를 확인한다. 회전 등의 side data가
있거나 정보가 부족하면 기존 normalize 경로를 사용한다.

추가로 모든 패킷의 duration=512 ticks, 연속적인 30fps PTS,
첫 keyframe PTS=0, DTS=-1024에서 시작하는 512-tick 간격을 검사한다.
이는 평균 FPS가 30으로 보이는 VFR이나 B-frame 재정렬 차이를 제외한다.
container/stream duration도 프레임 수/30과 일치해야 한다(출력 문자열의
소수점 오차 1µs 허용). metadata 검사만으로 손상된 비트스트림까지
검증하는 것은 아니므로 업로드 전 전체 디코딩 검사도 필요하다.

extradata의 바이트 동일성은 요구하지 않는다. 기존 concat demuxer의
기본 `auto_convert`는 MP4 H.264에 `h264_mp4toannexb` 변환을 적용한다.
정상적인 호환 SPS/PPS의 내용 차이 자체는 normalize 사유로 삼지 않는다.
근거: [FFmpeg concat 문서](https://ffmpeg.org/ffmpeg-formats.html#concat-1).

job 임시 디렉터리 수명 안의 `dict[Path, dict]`를 duration 조회와 merger에
공유한다. ffprobe는 unique Path당 한 번만 실행한다. 기존 duration-only
조회 대신 한 번의 JSON 조회에서 format/stream/packet metadata를 읽는다.
패킷 검사는 디코딩하지 않지만 기존 metadata-only 조회보다 읽기 비용은
증가할 수 있다. 캐시는 작업 간 공유하지 않는다.

## 로그 해석

- `normalize_skipped` / `normalize_required`: unique source별 최초 결정 수.
- `normalize_cache_hits`: 결정된 원본 또는 normalized 파일을 재사용한 수.
- `normalize_unique_sources`: 기존과 같이 실제 normalize를 호출한 unique source 수.
- `[FFmpeg Timing] probe_cache_*`: merge 단계의 조회 수. 일반 job에서는
  duration 단계에서 이미 채웠으므로 misses=0이 기대된다.
- `[FFprobe Timing] probe_cache_*`: duration과 merge를 포함한 job 전체 조회 수.
  `executions`는 실제 subprocess 실행 수이며, 기존 `cache_hits`는 code별
  duration 캐시의 hit 수다. 두 category의 probe hit 수를 합산하지 않는다.

## 검증과 예상 효과

`tests/test_clip_probe.py`는 실제 MP4로 정상 파일의 생략, 해상도/FPS/
pixel format/audio/B-frame 차이에 따른 normalize를 검증한다.
혼합 concat에 speed/idle/gap/missing fallback을 포함한 결과를 기존의
항상-normalize 경로와 비교해 duration, 프레임 수, PTS/DTS 일치 및
경고 없는 전체 디코딩을 확인한다. 추가로 실제 WORD를 한 번 normalize한
파일과 원본 WORD를 섞어 기존 경로와 디코딩된 프레임 시각을 비교했다.

로컬 demo 13개는 모두 normalize 필요 상태였지만 production runtime에는
사용되지 않는다. S3는 실제 실행 로그로 판단해야 한다. 제공된 26회/18.71초에서
26개 모두 생략 가능한 경우 이론적으로 VIDEO_MERGE 48.73→약 30.02초,
TOTAL 73.98→약 55.27초다. 이는 probe 추가 읽기 비용과 실행 변동을 제외한
상한 추정이며 현재 로컬 데이터에 대한 개선 실측이 아니다.

## 오프라인 사전 normalize 실험 (운영 미적용)

독립 CLI `scripts/preprocess_word_clips.py`와 전용 테스트는 구현되어 있다.
[실행 가이드](preprocess-word-clips.md)를 참고한다. 아래 운영 배포 절차는
제안이며 S3 업로드·runtime 경로 전환은 수행하지 않았다.

1. 원본은 읽기 전용으로 두고 별도 staging 디렉터리에 unique WORD를 준비한다.
2. 현재 `_normalize_clip()`과 같은 FFmpeg 설정으로 새 MP4를 생성한다.
3. 원본 해시, 생성 파일 해시, FFmpeg 버전, 원본/출력 duration, 프레임 수를
   manifest에 기록한다. 새 출력이 `is_clip_concat_ready()`를 통과하고
   기존 normalize 결과와 길이가 같으며 전체 디코딩이 성공하는지 검사한다.
4. 서로 다른 파일, idle, speed를 섞은 concat까지 검증한다.
5. 검토 후 별도 S3 저장 위치와 배포 전환 방식을 정한다. 기존 객체를
   덮어쓰거나 현재 resolver의 key 규칙을 즉시 바꾸지 않는다.

배포 환경과 같은 FFmpeg 설정으로 한 번만 인코딩하면, 현재 매 job마다
발생하는 재인코딩 비용을 사전 처리로 옮길 수 있다. 로컬 demo 전처리 검증만
진행했으며 운영 자산 전처리·업로드·S3 key 변경은 수행하지 않았다.
