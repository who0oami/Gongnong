# ksl-tube
Description AI-powered Korean Sign Language translation for YouTube videos

## 📂 프로젝트 구성

- `backend/` — YouTube 자막 `/translate` API
- `frontend/` — OpenPose 키포인트 데모
- `sign-keypoint-to-avatar/` — 수어 영상 → 키포인트 추출 → VRM 아바타 리타게팅 파이프라인 ([README](sign-keypoint-to-avatar/README.md))
- `ai/text-to-gloss/` — 텍스트 → 글로스(gloss) 변환 모델

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