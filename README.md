# ksl-tube
Description AI-powered Korean Sign Language translation for YouTube videos

---

## AI 모델: 한국어 → KSL Gloss

번역은 외부 생성형 AI API가 아니라, 팀 데이터로 파인튜닝한 **mT5 모델**로 수행합니다. 백엔드의 호출 형식은 아래처럼 고정되어 있습니다.

```python
convert_to_gloss("오늘 비가 옵니다.")
# ["오늘", "비", "오다"]  # 예시 형식
```

학습과 배포 전 검증은 아래 순서로 합니다.

```bash
python -m pip install -r requirements-ai.txt
python ai/train_mt5_low_memory.py \
  --train path/to/train.jsonl \
  --validation path/to/validation.jsonl \
  --output-dir ai/models/ksl-gloss-mt5 \
  --epochs 3
```

학습 스크립트는 가중치와 토크나이저를 `--output-dir`에 저장한 뒤, **저장된 파일만 사용해 새 모델 객체로 재로딩하여 추론**합니다. 재로딩 예측은 `verification_predictions.json`에 기록됩니다. 빈 예측, `<extra_id_*>` 같은 특수 토큰, 또는 평균 Gloss F1이 기준값보다 낮으면 실행을 실패 처리합니다. 이 경우 가중치를 공유하거나 백엔드에 연결하지 않습니다.

저메모리 환경에서는 `--smoke`로 데이터 256건·20 step만 실행할 수 있습니다. smoke 결과는 저장·재로딩 경로 확인용이며 모델 품질을 의미하지 않습니다. 실제 서비스 가중치는 전체 학습과 검증을 통과한 `model.safetensors` 또는 `pytorch_model.bin`을 별도 안전 저장소로 전달받아 `KSL_MT5_MODEL_DIR`에 배치해야 합니다. 가중치와 원본 데이터는 GitHub에 올리지 않습니다.

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
