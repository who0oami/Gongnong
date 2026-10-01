# Local LLM · S3 · Convert 통합 기록

## 기반 및 변경

- 작업 브랜치: `jihyun/local-llm-s3-integration`
- Local LLM 기반: `18147bb` (`jihyun/local-llm-semantic-integration`)
- 팀원 통합 기반: `3844430` (`jaeyeong/frontend-backend-convert`)
- 팀원 브랜치의 인증·History·Supabase 설정·S3 다운로드·프론트 변경을 병합하고, 추가 수정은 백엔드 연결·테스트·문서에 한정했다.

`ConfiguredKSLConverter`가 기존 provider 진입점을 호출한다. 기본은 Ollama `qwen2.5:3b`이며 Gemini 자막 교정은 그대로 사용한다. `GlossConversionError`는 팀 공통 `KSLConversionError`를 상속하고, `GlossValidationError`를 유지해 검증 실패와 모델 통신 실패를 구분한다.

CSV 매칭 단계에서 로컬 파일 유무를 검사하면 S3에만 있는 정상 영상까지 캡션으로 사라진다. 이를 수정해 매칭 단계는 코드를 유지하고, 이후 Job별 임시 폴더로 다운로드한 뒤 실제 파일 유무를 검사한다. ffprobe와 FFmpeg는 동일한 다운로드 파일을 사용한다.

- 일반 미매칭 또는 영상 누락: 해당 단어를 캡션으로 표시하고 나머지 영상 유지.
- 부정·금지 매칭 실패 또는 관련 영상 누락: 해당 구간 전체 문장 캡션으로 보호.
- Local LLM 최종 검증 실패: 해당 구간 캡션 처리.
- 모델 통신 실패: `FAILED` / `KSL_CONVERTING`.
- WORD: `s3://ksl-tube-avatar-clips/clips/word/{code}.mp4`.
- SEN: `backend/static/videos/{code}.mp4`. S3 규칙은 아직 없음.

## 자동 검증

2026-09-22, Windows / Python 3.13의 별도 가상환경에 팀 requirements를 설치해 테스트 94개 통과.

```powershell
$env:PYTHONPATH='backend'
$env:PYTHONDONTWRITEBYTECODE='1'
$env:DATABASE_URL='sqlite://'
$env:JWT_SECRET='unit-test-only-not-a-real-secret'
python -m unittest discover -s tests -q
```

위 값은 테스트 프로세스 전용이다. 실제 서버 실행 전 테스트 환경변수를 제거하고 개발 환경의 설정을 사용한다.

신규 `tests/test_local_s3_integration.py`는 FastAPI Job 생성·상태 조회, 실제 SQLite 저장, provider 예외 처리, 실제 CSV 매칭, 렌더러 연결을 함께 검사한다. 다음 네 경로를 검증했다.

1. Local gloss 결과 → WORD0001 매칭 → 다운로드 → 혼합 캡션 → 완료 URL 및 사용자·자막 저장.
2. 의미 검증 실패 → 다운로드 없이 원문 캡션으로 완료.
3. 모델 통신 실패 → Job 실패.
4. S3 인증 실패 → 누락 단어 캡션 유지.

자동 테스트의 모델·YouTube·Gemini·S3·FFmpeg 외부 호출은 mock이다. 이 결과를 실제 S3 다운로드·공용 PostgreSQL·수어 의미 검증 성공으로 해석하지 않는다. 기존 테스트는 임시 파일 중복 제거·동시 Job 격리·실패 후 정리, 캡션·부정 영상 누락, History 삭제도 검사한다.

## 실서비스 연결 전 남은 설정

별도 실행으로 실제 Ollama `qwen2.5:3b`에 `고민이 있어요.`를 요청해 `['고민', '있다']`를 받았다(모델 요청 1회, 24.527초; 로딩을 분리하지 않은 단일 측정). 실제 CSV에서 `WORD0001`, `SEN0133`으로 매핑됐다. S3 다운로드만 합성 색상 클립으로 대체하고 FFmpeg는 실제 실행해, 미매칭 한글 캡션과 SEN 누락 캡션을 포함한 1920×1080 H.264 2초 MP4를 생성했다(합성 9.397초). 이는 연결 확인용이며 실제 수어 영상·의미 검증이나 성능 벤치마크는 아니다.

확인 당시 원래 작업 폴더의 `.env`와 현재 프로세스에 AWS 인증·공용 DB 연결 설정이 없고, boto3가 찾은 AWS 프로필은 0개, 자격 증명도 없었다. 사용자가 제공한 파일은 실제 인증값이 없는 `.env.example`이다.

- 팀에서 S3 읽기 권한(`s3:GetObject`)과 AWS 프로필/SSO 설정 방법을 전달받아 로컬 인증 설정.
- 실제 버킷 리전 및 사용하는 `AWS_PROFILE` 설정. 프로필 이름만 적는 것으로 인증이 생성되지는 않음.
- 실제 Supabase PostgreSQL 연결 URL과 로컬 JWT secret 설정. 공용 DB migration 적용 여부는 팀과 확인.
- Gemini 자막 교정용 키 설정 및 Ollama 모델 준비.
- 실제 WORD 다운로드·SEN 로컬 자산·수어 의미 확인 후 로그인 → Job 생성 → polling → 결과 재생·History를 검증.

이번 작업에서 공용 DB migration, 실제 S3 다운로드, 공용 서비스 E2E는 수행하지 않았다. `COMPLETED`는 캡션 대체만으로도 나올 수 있으므로 결과 영상의 실제 수어 클립을 함께 확인해야 한다.
