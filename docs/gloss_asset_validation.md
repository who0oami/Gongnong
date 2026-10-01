# Gloss 및 영상 매핑 검증

현재 조사 제거는 완전 일치 실패 시에만 적용한다. 문자열 유사도 매칭은 사용하지 않는다.
`match_type`은 진단용이며 avatar/caption 표시 계약은 유지한다.

## 실행

저장소 루트에서 추가 의존성 없이 실행한다.

```powershell
$env:PYTHONPATH = "backend"
python -m unittest tests.test_gloss_matcher tests.test_local_llm_gloss_service -v
python scripts/audit_gloss_assets.py --output results/gloss-audit.json
python scripts/audit_gloss_assets.py --videos "D:\final-videos" --output results/video-audit.json
```

기본 사례는 시스템 프롬프트의 예시이며 실제 모델 추론 결과가 아니다.
저장된 실제 출력은 `--cases path/to/cases.json`으로 전달한다.
형식: `[{"input":"원문", "glosses":["모델 출력"]}]`.
이미 존재하는 보고서는 덮어쓰지 않는다.

## 검토 기준

- WORD/SEN 코드 수, 완전 일치·정규화·미매칭, SEN 원문을 함께 확인한다.
- SEN은 CSV 전체 표현이 일치할 때만 선택한다. 입력 segment의 Gloss 배열 전체가 일치하면 문장 클립 하나로 합친다. 부분 구간이나 어순을 바꾼 매칭은 하지 않는다. 감정단어 대체어도 SEN 전체 표현과 코드가 일치해야 한다. 코드 일치를 의미 정확도로 계산하지 않는다.
- 부정·금지·수량의 누락 및 입력에 없던 의미가 재생되는지 사람이 검토한다.
- 영상 후보는 파일명에서 코드를 추출한다. 중복 후보, CSV 외 코드, 누락, 코드 불명 파일, 빈 파일을 별도로 보고한다.
- REAL/SYN, 시점, 보정 버전 중 최종본을 확정한 후 배치한다. 도구는 자동 선택·복사·이동하지 않는다.
- 현재 백엔드는 `backend/static/videos/{code}.mp4`를 읽는다. CSV의 morpheme_path/source_file은 영상 경로가 아니다.
- 파일 존재는 재생 가능성이나 의미 정확성을 보장하지 않는다. 최종 영상은 ffprobe와 실제 재생으로 추가 검증한다.
- 시연용 DEMO_GLOSS_OVERRIDE 문장은 일반 모델/매처 평가와 분리한다.

완성 영상 폴더를 전달받아 감사 보고서를 검토한 뒤 코드별 최종 영상 연결을 진행한다.

문장 일부만으로 선택하던 SEN 연결을 제거했으므로 캡션 비율이 증가할 수 있다. `match_gloss_sequence`는 전체 문장 일치 시 결과 한 개를 반환한다. avatar/caption 항목 필드와 영상 경로 규칙은 유지한다.
