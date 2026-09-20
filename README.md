# ksl-tube
Description AI-powered Korean Sign Language translation for YouTube videos

---

## 🤝 GitHub 협업 규칙

### 1. 작업 시작 전 최신 코드 받기

작업을 시작하기 전에 `main` 브랜치의 최신 코드를 받아주세요.

```bash
git pull origin main
```

### 2. main 브랜치 직접 작업 최소화

가능하면 개인 작업은 별도의 브랜치에서 진행하고, 작업 완료 후 Pull Request를 통해 `main`에 반영합니다.

브랜치 이름 예시:

- `feature/frontend`
- `feature/backend`
- `feature/text-to-gloss`
- `feature/avatar`

### 3. Commit 메시지 작성

무엇을 작업했는지 알 수 있도록 간단하게 작성합니다.

```text
feat: 새로운 기능 추가
fix: 오류 수정
docs: 문서 수정
chore: 프로젝트 설정 및 기타 작업
```

예시:

```text
feat: 자막 추출 기능 추가
fix: 영상 재생 오류 수정
docs: README 수정
chore: 프로젝트 설정 수정
```

### 4. 대용량 파일 업로드 금지

AI Hub 원본 데이터, 영상, 모델 가중치 등 대용량 파일은 GitHub에 업로드하지 않습니다.

- MP4 등 영상 파일
- ZIP 등 압축 데이터셋
- AI 모델 가중치
- 개인 가상환경
- 기타 대용량 원본 데이터

### 5. 환경변수 및 API Key 업로드 금지

`.env` 파일, API Key, 비밀번호 등 민감한 정보는 GitHub에 업로드하지 않습니다.

환경변수를 팀원과 공유해야 하는 경우 실제 값은 제외하고 `.env.example` 파일을 사용합니다.

---

## 🤖 Local LLM Gloss 변환

외부 LLM API quota에 의존하지 않고 개발 및 E2E 테스트를 진행할 수 있도록
한국어 문장을 KSL Gloss 문자열 배열로 변환하는 로컬 LLM 경로를 제공합니다.

기존 Backend 계약인 `convert_to_gloss(korean_text: str) -> list[str]`은 유지하며,
후단의 Gloss Matcher / Timeline 코드는 변경하지 않습니다.

### 처리 흐름

```text
한국어 자막
  → Local LLM (Ollama + Qwen)
  → KSL Gloss 문자열 배열
  → Gloss Matcher
  → WORD / SEN asset code
  → Timeline / Avatar
```

### 1. Ollama 및 모델 준비

Ollama가 설치되어 있는지 확인합니다.

```bash
ollama --version
```

기본 모델을 내려받습니다.

```bash
ollama pull qwen2.5:3b
ollama list
```

### 2. 환경변수

`.env.example`을 참고해 설정합니다.

```env
KSL_GLOSS_PROVIDER=local
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_GLOSS_MODEL=qwen2.5:3b
```

별도 설정이 없으면 Gloss 변환 provider는 `local`, 모델은 `qwen2.5:3b`을 기본값으로 사용합니다.

기존 Gemini Gloss 경로로 비교 또는 롤백하려면:

```env
KSL_GLOSS_PROVIDER=gemini
GEMINI_API_KEY=your_api_key
GEMINI_GLOSS_MODEL=gemini-flash-lite-latest
```

> 기존 자막 보정 서비스(`llm_subtitle_correction_service.py`)는 별도로 Gemini를 사용하므로,
> 전체 E2E 실행 시에는 Gloss provider를 local로 설정해도 Gemini API key/quota가 필요할 수 있습니다.

### 3. Local Gloss 단독 실행 테스트

프로젝트의 `backend` 디렉터리에서 실행합니다.

```bash
cd backend
python -c "from services.llm_gloss_service import convert_to_gloss; print(convert_to_gloss('나는 학교에 가요.'))"
```

예시 출력:

```text
['나', '학교', '가다']
```

### 4. 테스트

프로젝트 루트에서:

```bash
PYTHONPATH=backend python -m unittest tests/test_local_llm_gloss_service.py -v
```

### 구현 위치

- `backend/services/llm_gloss_service.py`: Local/Gemini provider facade 및 기존 호출 계약 유지
- `backend/services/local_llm_gloss_service.py`: Ollama 호출, structured JSON 출력 및 Gloss 파싱
- `backend/services/gloss_matcher.py`: 생성된 Gloss를 기존 WORD/SEN asset으로 매핑
- `tests/test_local_llm_gloss_service.py`: Local LLM 응답 파싱/요청 계약 테스트

### 현재 검증 범위 및 한계

로컬 환경에서 Ollama + `qwen2.5:3b` 호출과 한국어 → Gloss 변환이 동작하는 것을 확인했습니다.
예를 들어 `나는 학교에 가요.`는 `['나', '학교', '가다']`,
`나는 커피를 마시지 않아요.`는 `['나', '커피', '마시다', '않다']` 형태로 변환됩니다.

다만 LLM이 생성한 자연스러운 Gloss가 현재 WORD/SEN asset vocabulary와 항상 일치하는 것은 아닙니다.
따라서 Local LLM 연결 및 Gloss 생성 경로는 구현되어 있으나,
asset coverage를 높이기 위한 Gloss 정규화/후보 검색 및 매칭 품질 개선은 후속 작업 대상입니다.

