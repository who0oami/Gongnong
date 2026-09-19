# 자음 18개 · KNN + jihyeon 손 모양 보정 v2

기존 코드/브랜치/결과를 수정하지 않는 별도 실험입니다. `vendor/`는 두 브랜치를
읽기 전용으로 복사한 스냅샷이며, 비교한 커밋은 `sources.json`에 기록했습니다.

- KNN 보정: `jihyeon` 브랜치 `1a695fa01001631bb20b39b08d8ab72e63e5b176`
  (`extractor/build_hand_shape_prior.py` 계열, 14개 관절 회전 크기를 코퍼스 이웃
  평균으로 보정, Thumb1 제외)
- jihyeon 리타게팅: `ksl-tube-jihyeon` 브랜치 `0148313d112b64a679f12e0082b872633370c582`
  (`retarget_avatar_real_v6_3.py` / `retarget_avatar_v6_3.py`, chain/minimum-swing
  방식으로 손가락 방향·roll 계산)

대상은 `output/consonant_replacements`, `output/consonant_recordings`의 자음
18개(ㄴㄷㄹㅁㅂㅅㅇㅈㅊㅋㅌㅍㅎ, 쌍자음 ㄲㄸㅃㅆㅉ = WORD3002–WORD3019) 전부입니다.
원본 영상은 실행 전/후 SHA-256이 동일함을 `build_review.py`에서 매번 검증합니다.

## 방법

같은 클립에 대해 세 버전을 같은 blend 파일에서 만듭니다.

1. **baseline** — 기존 per-video 파이프라인 그대로 (KNN/jihyeon 미적용).
2. **knn** — baseline에 KNN 보정만 적용.
3. **knn_jihyeon** — knn 결과 위에 jihyeon이 계산한 손가락 목표 방향을 프레임별로
   덧붙입니다 (`process_clip.py`):
   - 신뢰도(`trust`, 앞뒤 2프레임 관측 비율)에 따라 혼합 강도(`alpha = 0.45 × trust`,
     `--strength` 기본값)를 낮춥니다. 관측이 없으면 alpha=0.
   - **KNN 반려**: jihyeon 목표 대비 KNN 결과가 baseline(보정 전 관측치)보다 더
     멀어지면 KNN을 버리고 baseline으로 되돌립니다. "코퍼스에서 드문 자세 = 잘못된
     자세"로 단정하지 않기 위함입니다.
   - jihyeon 방향으로의 추가 보정은 프레임당 최대 25°(`max_extra_correction_deg`)로
     제한하고, 이전 프레임 대비 보정량 변화도 4°/frame(`correction_step_limit_deg`)
     으로 완만하게 만듭니다.
   - 그 위에 전체 결과에 30fps 기준 **16°/frame** 회전 속도 상한을 최종적으로
     한 번 더 겁니다(`output_rate_limit_deg_per_frame_at_30fps`). ㄷ(WORD3003)에서
     교정 전 63°/frame급 급변이 관측되어 추가한 안전장치입니다.
   - 손가락 bone만 건드립니다. 팔/손목/몸통/표정은 baseline 그대로 유지합니다.

## 실행 (PowerShell, `word2153` 디렉터리에서)

```powershell
python experiments/consonants_knn_jihyeon_v2/extract_all.py     # 18개 키포인트 추출/정제/평활 (raw/refined/stable/smoothed.json)
python experiments/consonants_knn_jihyeon_v2/process_all.py     # blender로 baseline/knn/knn_jihyeon 3버전 생성 (result_v4.json)
python experiments/consonants_knn_jihyeon_v2/render_all.py      # 원본 영상 위 오버레이 mp4 렌더 (preview_v4/)
& 'C:/Program Files/Blender Foundation/Blender 5.2/blender.exe' --background --python-exit-code 1 --python experiments/consonants_knn_jihyeon_v2/verify_all.py   # 저장 파일 재오픈 보존 검증
python experiments/consonants_knn_jihyeon_v2/build_review.py    # index.html / summary.json 생성
```

각 단계는 `runs/<word_id>/result_v4.json` 등 기존 산출물이 이미 검증된 상태면
건너뜁니다. 새 출력 폴더(`runs/`)만 만들며 `output/`, 다른 브랜치는 건드리지
않습니다.

## 확인한 것 (구체적 수치, `summary.json` / `preservation_verification.json`)

- 18개 클립, 총 1454프레임. 처리 전후 원본 영상 SHA-256 불변.
- 저장된 blend를 다시 열어 정수+반(half) 프레임 전수 검사 — **18/18 PASS**
  (`verify_all.py`): 손가락이 아닌 bone의 local matrix, 오브젝트 world matrix,
  얼굴 shape key 값 최대 오차 **0.0**. 손가락 quaternion 유한성 확인, 최소 norm
  약 0.9976 이상(정규화 열화 없음).
- 손가락 방향 오차(추출된 손 좌표 기준 `mean_source_segment_error_deg`) —
  baseline 27.98° → knn 단독 29.13°(오히려 악화) → knn_jihyeon **20.69°**.
  18개 클립 전부에서 knn_jihyeon이 baseline 대비, knn 대비 각각 개선.
- 최종 결과의 프레임당 최대 회전 변화 16.00°/frame(@30fps) — 상한 그대로 도달,
  초과 없음.
- 비교 화면 `index.html`: 원본 영상 + baseline/knn/knn_jihyeon을 같은 시간축으로
  동시 재생, 손 확대/상체 전체 토글, 재생 속도 조절, 클립 18개 선택.

## 명시적으로 확인하지 않은 것 / 주의

- `mean_source_segment_error_deg`는 **추출기(MediaPipe + refine_hands)가 뽑아낸
  손 좌표와의 일치도**이지 실제 수어(지문자) 정확성이 아닙니다. 추출기 자체가
  틀린 프레임이 있다면 이 지표는 그 오류 쪽으로 맞춰진 것으로 보일 수 있습니다.
  네이티브 수어 사용자의 육안 검토는 하지 않았습니다 — `index.html`로 사람이
  직접 봐야 합니다.
- 이번 18개 자음에서는 **KNN 단독이 baseline보다 나빴습니다**(29.13° > 27.98°).
  이 자음 세트에는 KNN 단독 적용을 권장하지 않으며, jihyeon 보정을 반드시 함께
  써야 한다는 뜻은 아니고 이번 조합에서 그렇게 나왔다는 관측입니다.
- jihyeon 리타게팅 코드 전체를 새 파이프라인으로 채택할지에 대한 비교가 아닙니다.
  기존 KNN 결과 위에 jihyeon의 손가락 방향 계산만 보정치로 얹은 것입니다.
- ㅏ·ㅑ·ㅓ·ㅕ 등 모음 지문자는 이번 작업 범위가 아닙니다(별도 팀원 결과가
  기준 미달이라 제외). 확인이 필요하면 해당 결과의 `.blend`와 생성에 쓰인
  모션 JSON 경로를 알려주면 이 실험과 같은 방식으로 검증하겠습니다.

