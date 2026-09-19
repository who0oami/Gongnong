# 손 모션 딥러닝 보정 실험 기록

결론부터: **세 가지 딥러닝/통계 접근 중 KNN 통계 보정만 채택.** 나머지 둘은 시도했고 측정도 했지만 실사용에 넣지 않음.

## 채택: KNN 통계 보정 (`scripts/correct_hand_shape_prior.py`)

```powershell
python extractor/build_hand_shape_prior.py --dataset "C:/Users/ESTsoft/Desktop/output_3d/output_3d" --output extractor/hand_shape_prior.npz
& "C:\Program Files\Blender Foundation\Blender 5.2\blender.exe" --background --python scripts/correct_hand_shape_prior.py -- --input output/<smoothed>.blend --output output/<new>.blend --prior extractor/hand_shape_prior.npz
```

1500단어 SYN 삼각측량 데이터에서 21.6만 개 손-프레임 굽힘각(14차원) 코퍼스를 만들고, 현재 손 모양이 이 코퍼스 어디에도 비슷한 예가 없을 때만(이상치일 때만) 가장 가까운 이웃 쪽으로 시간축으로 부드럽게 당긴다. 가중치를 학습시키지 않는다 — 매번 코퍼스를 직접 대조하는 방식.

**검증**: leave.mp4, love.mp4 둘 다에서 스무딩만 한 버전보다 관절 떨림(second-diff)이 줄었고, 두 영상 모두 부작용(새로운 큰 튐 발생) 없음을 확인. → `output/leave_M10_prior_corrected_v2.blend`, `output/love_4to7s_M10_prior_corrected_v1.blend`가 현재 실사용 결과.

## 시도했으나 폐기 1: 가짜 노이즈로 학습한 디노이저

`colab/train_hand_motion_denoiser.py` — SYN 정답 데이터에 직접 상상한 가짜 노이즈(가우시안 잔떨림 + 가끔 큰 프레임 튐 + 결측 구간 홀드)를 입혀서 (노이즈, 정답) 쌍을 만들고 BiGRU로 학습.

**검증 결과**: leave.mp4에 적용했더니 관절 떨림이 스무딩만 한 버전보다 **오히려 약 2배 커짐** (Index1 second-diff jitter 2.24도 → 4.85도, 프레임당 최대 변화 12도 → 41도). 단어 수를 300 → 500으로 늘려도 거의 그대로.

**원인 진단**: 가짜로 만든 노이즈가 실제 MediaPipe 파이프라인이 만드는 진짜 오차 패턴과 통계적으로 안 닮음. **폐기.** 관련 파일(`output/leave_M10_denoised_v1.blend`, `output/leave_M10_denoised_500w_v1.blend`)은 참고용으로만 남겨두고 실사용하지 않음.

## 시도했으나 폐기 2: 진짜 (노이즈, 정답) 짝으로 학습한 디노이저

`colab/train_hand_motion_denoiser_real_pairs.py` — `D:/rendered_video/WORD####.mp4`가 `output_3d/WORD####_3d_approx.json` 정답을 만든 바로 그 렌더링 영상임을 확인(프레임 수/fps/해상도 동일, WORD0001 기준 61프레임 일치). 이 영상에 leave.mp4/love.mp4와 동일한 추출 파이프라인(`scripts/batch_extract_syn_videos.py`)을 돌려 "우리 파이프라인이 실제로 만드는 노이즈"를 얻고, 같은 프레임의 정답과 짝지음(`extractor/build_real_denoiser_pairs.py`, 181개 단어·356개 시퀀스, `extractor/real_denoiser_pairs.npz`).

```powershell
python scripts/batch_extract_syn_videos.py --video-root "D:/rendered_video"
python extractor/build_real_denoiser_pairs.py --extracted-root keypoints/syn_training/smoothed --ground-truth-root "C:/Users/ESTsoft/Desktop/output_3d/output_3d" --output extractor/real_denoiser_pairs.npz
# 학습은 colab/train_hand_motion_denoiser_real_pairs.ipynb (Colab)
python extractor/run_hand_motion_denoiser_real_pairs.py --motion keypoints/<id>_hands_stable_v1_smoothed.json --checkpoint hand_motion_denoiser_real_pairs.pt --output keypoints/<id>_denoised_angles_real_pairs.json
```

**검증 결과 (held-out SYN 단어, 합성 검증셋)**: baseline(안 고침) RMSE 30.6도 → 모델 보정 후 19.2도. 가짜 노이즈 버전과 달리 학습 곡선도 깔끔하게 수렴. 가설(가짜 노이즈보다 진짜 짝이 낫다)은 이 기준으로 확인됨.

**실제 영상 적용 결과는 영상마다 다름**:
- leave.mp4: 첫마디(MCP, 예 Index1) 관절은 KNN보다도 좋아짐(3.97도→3.13도). 중간·끝마디는 KNN보다 나빠짐.
- love.mp4: **정반대.** 첫마디(Index1, Middle1) 관절에서 순간 최대 71~81도까지 튀는 심각한 오작동 발생. "첫마디는 모델이 낫다"는 leave.mp4 하나에 한정된 우연이었음 — 검증 실패.

**결론**: SYN(합성) 영상에서 학습했기 때문에 실제(비-SYN) 영상에 적용할 때 남는 시각적 도메인 차이가 영상마다 다르게 나타나는 것으로 추정. 일관성이 없어서 **폐기, 실사용 금지.** 관련 파일(`*_denoised_real_pairs_v1.blend`, `*_hybrid_v1.blend`)은 참고용으로만 보존.

## 명시적으로 주장하지 않는 것

- "가짜 노이즈보다 진짜 짝이 낫다"는 검증됐지만, "진짜 짝 모델이 KNN보다 낫다"는 검증되지 않았음(오히려 영상에 따라 크게 나쁨).
- 이 실험들의 SYN 학습 데이터는 181개 단어뿐이며, 전체 1500단어 중 일부. 더 많은 단어로 재학습하면 결과가 달라질 수 있으나 확인하지 않았음.
- "관절 종류별로 다른 보정 방법을 섞는다"는 아이디어 자체가 틀렸다는 근거는 없음 — 이번에 쓴 "첫마디/나머지" 구분 기준이 일반화되지 않았을 뿐, 다른 기준(예: 관절이 아니라 프레임 단위 신뢰도)으로는 다시 시도해볼 여지가 있음.

