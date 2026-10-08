# 프로젝트 소개 — 공농 (Gongnong)

> AI 기반 YouTube 한국수어 영상 변환 서비스

YouTube URL을 입력하면 영상의 자막·음성을 분석해 한국수어(KSL) Gloss로 변환하고, 수어 Avatar 클립을 원본 타이밍에 맞춰 합성하는 콘텐츠 접근성 프로젝트입니다.

## 작업 소개

AI·3D Avatar 연구부터 KSL Gloss 변환 실험, Frontend·Backend 배포, 영상 변환 성능 개선까지 담당했습니다. 개발 환경의 기능을 실제 서비스로 연결하면서 발생한 자막 수집, AWS 인증, 영상 합성 성능, 결과 파일 보존 문제를 해결하고 전체 변환 과정을 검증했습니다.

## AI · 3D Avatar

### 손 모양 보정 데이터와 모델 실험

기존 3D 수어 데이터에서 손·신체 키포인트를 추출하고, Avatar의 손 모양이 무너지거나 프레임마다 흔들리는 문제를 줄이기 위한 보정 실험을 진행했습니다.

- 기존 3D 수어 데이터를 가공해 손 모양 보정용 데이터셋 구축
- 합성 노이즈와 실제 추출–정답 Pair 기반 손 모션 학습 데이터 제작
- BiGRU 손 모션 디노이저 학습 및 KNN 방식과 성능 비교
- 1,500개 수어 단어·약 21.6만 손 프레임 기반 KNN 손 모양 보정 구현
- 손 재검출, 좌우 손 판별, 랜드마크 스무딩과 손가락 방향·회전 보정 검증
- Baseline·KNN·최종 보정 결과를 Blender 영상으로 렌더링해 비교

BiGRU는 시계열 보정 가능성을 확인하기 위한 실험으로 진행했습니다. 제한된 데이터에서도 결과를 재현하고 비교하기 쉬운 KNN 방식을 최종 손 보정 과정에 적용했습니다.

### 미지원 자음 18종 Avatar Asset 제작

기존 약 3,000개 수어 Asset에 없던 자음 손 모양을 서비스에서 사용할 수 있도록 신규 Asset으로 제작했습니다.

- 자음 18종을 WORD3002~WORD3019 코드로 정의
- 총 1,454프레임의 키포인트를 추출하고 손 형태·방향 보정
- F10·F20 VRM Avatar 리타게팅 프로파일 적용
- Baseline/KNN/손가락 방향 보정 결과 비교
- Blender 렌더링과 프레임 보존 검증
- 키포인트 보정 → Avatar 리타게팅 → 렌더링 → 결과 검증 One-shot 자동화

관련 코드는 [KNN·자음 Avatar 실험](experiments/consonants_knn_jihyeon_v1/)에서 확인할 수 있습니다.

기술 블로그: [수어 Avatar의 손 모양을 KNN으로 보정한 과정](https://who0oami.github.io/posts/knn-hand-correction.html)

## KSL Gloss 모델 실험

### Gemini 비용 문제에서 Local LLM까지

초기 파이프라인은 Gemini API로 한국어 문장을 KSL Gloss로 변환했습니다. 기능 검증에는 적합했지만 반복 호출 시 API 비용과 사용량 제한에 영향을 받는 문제가 있어, 외부 API 의존도를 줄이기 위한 모델 실험을 진행했습니다.

1. **mT5 딥러닝 모델 실험**
   - 한국어–KSL Gloss 데이터로 mT5 파인튜닝·평가 파이프라인 구축
   - 저메모리 학습, 저장 모델 재로딩, Gloss token F1 검증 구현
   - 학습 데이터의 양과 품질이 충분하지 않아 실서비스 수준의 변환 정확도를 안정적으로 확보하기 어렵다는 한계 확인

2. **Ollama/Qwen Local LLM 전환**
   - 별도 API 과금 없이 로컬에서 실행 가능한 Ollama/Qwen 적용
   - KSL 문법과 보유 Asset을 반영한 프롬프트 개선
   - 조사·부정 표현 정규화와 의미 검증 로직 구현
   - 미지원 단어·고유명사를 캡션으로 유지하는 Fallback 처리
   - Gloss Matcher와 WORD/SEN Asset 매핑, S3 수어 영상 연결 검증

3. **다중 Provider 통합**
   - Backend에서 KSL_GLOSS_PROVIDER 설정으로 Gemini, Local LLM, mT5 중 선택 가능
   - 배포 환경은 안정성이 검증된 Gemini를 기본값으로 유지
   - Local LLM과 mT5는 비용·성능 비교와 후속 개선을 위한 실험 경로로 보존

기술 블로그: [Gemini에서 Local LLM까지: KSL Gloss 변환 실험](https://who0oami.github.io/posts/gemini-to-local-llm.html)

관련 코드는 [mT5 학습·추론](ai/)과 [Local LLM 검증](experiments/local_llm_validation/)에서 확인할 수 있습니다.

## 서비스 배포와 E2E 통합

Frontend와 Backend를 각각 Vercel과 Render에 배포하고, Supabase·Gemini·YouTube·AWS S3·FFmpeg를 연결한 실제 영상 변환 과정을 검증했습니다.

~~~text
YouTube URL
  → 자막 수집 또는 Gemini 영상 전사
  → 자막 교정과 KSL Gloss 변환
  → WORD/SEN Asset 매핑
  → S3 수어 클립 조회
  → Timeline 계산과 FFmpeg 합성
  → S3 결과 저장
  → Frontend 원본·수어 영상 재생
~~~

담당한 배포 작업:

- Vercel Frontend·Render Backend 배포 설정
- Render 환경변수 기반 AWS 인증 구성
- S3 수어 클립 조회와 결과 영상 저장 연결
- 변환 Job 상태와 실패 단계별 오류 처리 검증
- 최종 MP4 생성, S3 업로드, 서명 URL 발급, Frontend 재생까지 E2E 확인
- Vercel SPA /processing 직접 접근과 새로고침 404 해결

## 주요 트러블슈팅

### 1. Render에서 YouTube 자막 조회 차단

**문제**

로컬에서는 정상적으로 가져오던 YouTube 자막이 Render에서는 RequestBlocked·IpBlocked 오류로 실패했습니다. YouTube Data API 전체의 문제가 아니라, 클라우드 서버 IP에서 youtube-transcript-api로 자막을 조회하는 경로가 차단된 상황이었습니다.

**해결**

- 기존 방식으로 한국어 자막을 먼저 조회
- IP 차단, 자막 비활성화, 자막 미제공 오류 감지
- 실패 시 공개 YouTube URL을 Gemini에 전달해 영상 음성을 직접 전사
- start, end, text 형식의 Segment를 생성하고 실제 영상 길이에 맞게 타임스탬프 보정
- 생성한 Segment를 기존 Gloss 변환·수어 영상 생성 파이프라인에 전달

**결과**

Render에서도 자막 제공 여부와 서버 IP 차단에 관계없이 영상 전사부터 Gloss 변환까지 이어지는 Fallback 경로를 확보했습니다. 영상 제목·설명·재생시간은 YouTube Data API를 계속 사용해 자막 조회와 메타데이터 조회의 책임도 분리했습니다.

### 2. Render와 로컬의 AWS 인증 방식 차이

**문제**

로컬에서는 AWS CLI 프로필 파일을 사용했지만 Render 컨테이너에는 해당 파일이 없어 S3 수어 클립 조회가 실패했습니다.

**해결**

- 로컬에서는 AWS_PROFILE 사용 방식 유지
- Render에서는 AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_DEFAULT_REGION 환경변수 사용
- S3 클립 조회 실패와 결과 영상 업로드 실패를 서로 다른 단계의 오류로 구분

**결과**

Render에서 WORD 수어 클립 다운로드, Timeline 생성, 최종 MP4 업로드와 서명 URL 발급까지 정상 동작하는 것을 확인했습니다.

### 3. FFmpeg 영상 합성 병목

**문제**

Render 무료 인스턴스의 제한된 CPU·메모리 환경에서 약 3분 영상을 변환하는 데 약 33분이 걸렸습니다. 개별 클립을 반복해서 분석·재인코딩하고 FFmpeg를 여러 번 실행하는 과정이 주요 병목이었습니다.

**해결**

- 인접한 수어 구간을 묶어 FFmpeg 실행 횟수 축소
- 표준화된 1080p·30fps 클립은 재인코딩하지 않고 concat copy 적용
- FFprobe 결과, 정규화 클립, Idle 영상을 캐시해 중복 처리 제거
- FFprobe 패킷 전체 조회 제거
- FFmpeg 스레드·preset·timeout을 무료 인스턴스 환경에 맞게 조정
- 렌더링 동시 실행을 1개로 제한해 메모리 초과 방지

**결과**

동일한 약 3분 영상 기준 전체 변환 시간을 약 33분에서 **8분 27초**로 줄였습니다. 목표였던 10~15분 이내 변환을 달성하고 Render 512MB 메모리 환경에서 최종 영상 생성을 완료했습니다.

### 4. Render 재배포 후 결과 영상 404

**문제**

완성된 MP4를 Render 로컬 디스크에만 저장해 재배포나 재시작 후 파일이 사라졌습니다. DB에는 작업이 COMPLETED로 남지만 영상 재생은 404로 실패할 수 있었습니다.

**해결**

- 완성 영상을 S3 results/{job_id}.mp4에 업로드
- Backend 영상 API에서 S3 서명 URL을 생성해 리다이렉트
- S3 업로드 실패를 RESULT_STORAGE 단계 오류로 분리
- 업로드 완료 후 Render의 임시 결과 파일 삭제

**결과**

Render가 재배포되더라도 기존 결과 영상을 계속 재생할 수 있게 했습니다. 실제 배포 환경에서 MP4 업로드, Backend 307 리다이렉트, 최종 video/mp4 응답까지 확인했습니다.

### 5. Vercel /processing 새로고침 404

**문제**

React Router의 Client-side route에 직접 접근하거나 새로고침하면 Vercel이 실제 파일을 찾으려 해 404를 반환했습니다.

**해결 및 결과**

Vercel rewrite 설정으로 모든 경로를 index.html에 연결해 SPA Router가 경로를 처리하도록 수정했습니다. 배포 환경에서 변환 페이지를 새로고침해도 화면과 Job 조회가 이어지는 것을 확인했습니다.

기술 블로그: [Render 무료 서버에서 FFmpeg를 4배 빠르게 만들기](https://who0oami.github.io/posts/render-ffmpeg.html)

## 작업 결과

| 구분 | 결과 |
| --- | --- |
| 영상 변환 속도 | 약 33분 → **8분 27초** |
| 신규 수어 Asset | 미지원 자음 **18종** 제작 |
| KNN 기준 데이터 | 수어 1,500단어·손 프레임 약 21.6만 개 |
| 자음 검증 데이터 | 18종·총 1,454프레임 |
| 배포 연동 | Vercel · Render · Supabase · Gemini · AWS S3 |
| 결과 보존 | S3 영구 저장 및 서명 URL 재생 |

## 사용 기술

| 영역 | 기술 |
| --- | --- |
| AI · NLP | Gemini API, Ollama/Qwen, mT5 |
| Motion 보정 | BiGRU, KNN, MediaPipe |
| 3D Avatar | Blender, VRM, Python 자동화 |
| Frontend | React 19, TypeScript, Vite, React Router |
| Backend | FastAPI, SQLAlchemy, Alembic |
| Video | FFmpeg, ffprobe |
| Infra | Vercel, Render, Supabase PostgreSQL, AWS S3, Docker |

## 저장소에서 확인할 수 있는 작업

~~~text
Gongnong/
├── ai/                                      # mT5 학습·평가·추론
├── experiments/
│   ├── consonants_knn_jihyeon_v1/          # KNN 손 보정·자음 Avatar
│   └── local_llm_validation/                # Local LLM·S3 연결 검증
├── backend/services/
│   ├── gemini_transcript_service.py         # Gemini 영상 전사 Fallback
│   ├── llm_gloss_service.py                 # Gloss provider 선택
│   ├── result_storage.py                    # 결과 MP4 S3 저장
│   └── video_merger.py                      # FFmpeg 합성 최적화
├── frontend/vercel.json                     # SPA 새로고침 404 해결
└── tests/                                   # 변환·저장·Fallback 검증
~~~

모델 가중치, 원본 학습 영상, S3 수어 클립은 저장소에 포함하지 않습니다.

## 실행 및 검증

환경변수는 [.env.example](.env.example)과 [frontend/.env.example](frontend/.env.example)에 정리되어 있습니다.

~~~bash
# Backend
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
alembic upgrade head
cd backend
uvicorn main:app --reload
~~~

~~~bash
# Frontend
cd frontend
cp .env.example .env.local
npm install
npm run dev
~~~

Backend 테스트:

~~~bash
DATABASE_URL=sqlite:// JWT_SECRET=unit-test-only-not-a-real-secret \
python -m unittest discover -s tests -v
~~~

Frontend 검증:

~~~bash
cd frontend
npm run build
node --test tests/synchronizedPlayback.test.mjs
~~~
