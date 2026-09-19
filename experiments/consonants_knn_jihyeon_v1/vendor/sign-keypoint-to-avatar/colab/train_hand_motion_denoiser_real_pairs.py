"""
Google Colab용: 진짜 (노이즈, 정답) 짝으로 손 모션 디노이저 학습.

=====================================================================
이전 버전(train_hand_motion_denoiser.py)과 무엇이 다른가
=====================================================================
이전 버전은 SYN 데이터셋의 "정답"만 가지고, 거기에 우리가 직접 상상한 가짜
노이즈(가우시안 잔떨림 + 가끔 큰 튐 + 결측 구간)를 입혀서 학습 쌍을 만들었음.
-> 실제 leave.mp4에 적용해보니 오히려 흔들림이 2배 이상 심해짐 (측정 완료).
원인: 가짜 노이즈가 실제 MediaPipe 파이프라인이 만드는 진짜 오차 패턴과
통계적으로 안 닮았기 때문.

이번 버전은 노이즈를 상상하지 않는다. 대신:
  1) D:/rendered_video/WORD####.mp4 는 output_3d/WORD####_3d_approx.json
     (5카메라 삼각측량 정답)을 만드는 데 쓰인 바로 그 렌더링 영상임
     (검증됨: 프레임 수/fps/해상도 완전 동일).
  2) 이 영상에 leave.mp4/love.mp4와 완전히 동일한 우리 추출 파이프라인
     (extract_keypoints -> refine_hands -> prepare_stable_hands ->
     smooth_hand_landmarks)을 돌려서, "우리 파이프라인이 실제로 만들어내는
     노이즈 있는 결과"를 얻음 (scripts/batch_extract_syn_videos.py).
  3) 같은 영상이므로 프레임이 1:1로 정확히 대응 -> (진짜 노이즈, 진짜 정답)
     쌍이 자연스럽게 만들어짐. 가짜로 흉내낼 필요가 없음
     (extractor/build_real_denoiser_pairs.py).

=====================================================================
입력/출력 (이전과 동일한 표현, 데이터 출처만 다름)
=====================================================================
INPUT  : 우리 파이프라인이 실제 영상에서 뽑은 손 굽힘각 시퀀스 (T, 14) - 2D 기반이라
         카메라 쪽으로 굽는 손가락은 원근 단축 때문에 실제보다 덜 굽은 것처럼 보임
         (이게 이번 학습의 진짜 어려움 - 단순 노이즈 제거가 아니라, 2D로는 안
         보이는 깊이 방향 굽힘 정도를 다른 관절들의 문맥으로 추정 복원하는 문제).
OUTPUT : 같은 shape (T, 14)의 진짜 3D 삼각측량 정답 굽힘각 시퀀스.

=====================================================================
Colab 사용법
=====================================================================
1) 로컬에서 이미 만들어진 extractor/real_denoiser_pairs.npz (1.7MB, 356개
   시퀀스)를 Google Drive에 그대로 업로드 (작은 파일이라 zip/압축 불필요)
2) 이 파일 내용을 Colab 새 노트북에 붙여넣기 (# %% 로 셀 구분)
3) 아래 PAIRS_PATH를 본인이 Drive에 올린 실제 경로로 수정
4) 런타임 -> 런타임 유형 변경 -> GPU(T4) 선택 (없어도 CPU로 충분)
5) 순서대로 실행
"""

# %% [Cell 1] Google Drive 마운트 + 경로 설정 -------------------------------
from google.colab import drive
drive.mount('/content/drive')

import math
import random
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader

# vvv 본인이 Drive에 올린 real_denoiser_pairs.npz의 실제 경로로 바꾸세요 vvv
PAIRS_PATH = Path('/content/drive/MyDrive/real_denoiser_pairs.npz')
CHECKPOINT_PATH = Path('/content/drive/MyDrive/hand_motion_denoiser_real_pairs.pt')

if not PAIRS_PATH.is_file():
    raise FileNotFoundError(
        f'못 찾음: {PAIRS_PATH}\n'
        "Drive에 올린 실제 경로로 PAIRS_PATH를 수정하세요. 위치를 모르면:\n"
        "list(Path('/content/drive/MyDrive').rglob('real_denoiser_pairs.npz'))")

MAX_LEN = 120  # 이보다 긴 시퀀스는 자르고, 짧은 건 마지막 프레임으로 패딩
JOINTS = 14


# %% [Cell 2] 짝지어진 데이터 불러오기 ---------------------------------------
data = np.load(PAIRS_PATH, allow_pickle=True)
noisy_seqs_all = list(data['noisy'])   # 각 원소: (T_i, 14) - 우리 파이프라인 결과
clean_seqs_all = list(data['clean'])   # 각 원소: (T_i, 14) - 3D 삼각측량 정답
meta_all = list(data['meta'])          # 'WORD0001_left_hand' 같은 식별자

print(f'{len(noisy_seqs_all)}개 (노이즈, 정답) 시퀀스 쌍 로드됨')
word_ids_all = [m.rsplit('_', 2)[0] for m in meta_all]  # 'WORD0001_left_hand' -> 'WORD0001'


# %% [Cell 3] 단어 단위로 train/val 분리 (같은 단어의 왼손/오른손이 train과 val에
# 걸쳐 나뉘지 않도록 - 안 그러면 같은 손 모양을 이미 본 채로 "검증"하게 됨) ------
random.seed(0)
unique_words = sorted(set(word_ids_all))
random.shuffle(unique_words)
split = int(len(unique_words) * 0.85)
train_words = set(unique_words[:split])
val_words = set(unique_words[split:])

train_idx = [i for i, w in enumerate(word_ids_all) if w in train_words]
val_idx = [i for i, w in enumerate(word_ids_all) if w in val_words]
print(f'train 단어 {len(train_words)}개 ({len(train_idx)}개 시퀀스) / '
      f'val 단어 {len(val_words)}개 ({len(val_idx)}개 시퀀스)')


# %% [Cell 4] Dataset / DataLoader - 노이즈를 만들지 않고, 미리 짝지어진 -----
# (noisy, clean) 쌍을 그대로 사용. 매 epoch 랜덤 크롭만 적용(짧은 시퀀스가
# 많으므로 데이터 증강 효과), 노이즈 자체는 절대 합성하지 않는다.
class PairedHandMotionDataset(Dataset):
    def __init__(self, indices, max_len=MAX_LEN, seed=0):
        self.indices = indices
        self.max_len = max_len
        self.rng = np.random.default_rng(seed)

    def __len__(self):
        return len(self.indices)

    def __getitem__(self, i):
        idx = self.indices[i]
        noisy = noisy_seqs_all[idx]
        clean = clean_seqs_all[idx]
        T = noisy.shape[0]

        if T >= self.max_len:
            start = self.rng.integers(0, T - self.max_len + 1)
            noisy = noisy[start:start + self.max_len]
            clean = clean[start:start + self.max_len]
            mask = np.ones(self.max_len, dtype=np.float32)
        else:
            pad = self.max_len - T
            noisy = np.concatenate([noisy, np.repeat(noisy[-1:], pad, axis=0)], axis=0)
            clean = np.concatenate([clean, np.repeat(clean[-1:], pad, axis=0)], axis=0)
            mask = np.concatenate([np.ones(T, dtype=np.float32), np.zeros(pad, dtype=np.float32)])

        return torch.from_numpy(noisy.astype(np.float32)), torch.from_numpy(clean.astype(np.float32)), torch.from_numpy(mask)


train_loader = DataLoader(PairedHandMotionDataset(train_idx, seed=1), batch_size=16, shuffle=True)
val_loader = DataLoader(PairedHandMotionDataset(val_idx, seed=2), batch_size=16, shuffle=False)


# %% [Cell 5] 모델: 양방향 GRU 디노이저 (이전과 동일한 구조) -----------------
class HandMotionDenoiser(nn.Module):
    """(T,14) 실제 파이프라인 결과 -> (T,14) 3D 정답에 가깝게 보정.
    양방향이라 미래 프레임 정보도 써서 과거 프레임을 고칠 수 있음 - 실시간이
    아니라 "다 찍힌 영상 전체를 나중에 보정"하는 우리 상황에 맞는 선택."""

    def __init__(self, in_dim=JOINTS, hidden=64, layers=2, dropout=0.2):
        super().__init__()
        self.input_proj = nn.Linear(in_dim, hidden)
        self.gru = nn.GRU(hidden, hidden, num_layers=layers, batch_first=True,
                           bidirectional=True, dropout=dropout)
        self.output_proj = nn.Sequential(
            nn.Linear(hidden * 2, hidden), nn.ReLU(), nn.Linear(hidden, in_dim))

    def forward(self, x):
        h = self.input_proj(x)
        h, _ = self.gru(h)
        # 잔차 연결은 이번엔 안 씀: noisy와 clean은 이제 스케일 자체가 다를 수
        # 있음(2D 원근 단축 때문에 clean이 noisy보다 체계적으로 더 크게 굽음).
        # "입력에서 얼마나 벗어날지"가 아니라 "정답이 뭘지"를 직접 배워야 함.
        return self.output_proj(h)


device = 'cuda' if torch.cuda.is_available() else 'cpu'
model = HandMotionDenoiser().to(device)
print('device:', device, '| 파라미터 수:', sum(p.numel() for p in model.parameters()))


# %% [Cell 6] 학습 루프 ------------------------------------------------------
def masked_mse(pred, target, mask):
    diff = (pred - target) ** 2
    diff = diff.mean(dim=-1)
    return (diff * mask).sum() / mask.sum().clamp(min=1)


def temporal_smoothness_penalty(pred, mask):
    d = pred[:, 1:] - pred[:, :-1]
    m = mask[:, 1:] * mask[:, :-1]
    return ((d ** 2).mean(dim=-1) * m).sum() / m.sum().clamp(min=1)


optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)
scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(optimizer, patience=5, factor=0.5)
SMOOTH_WEIGHT = 0.2
best_val = float('inf')
EPOCHS = 150

for epoch in range(1, EPOCHS + 1):
    model.train()
    train_loss = 0.0
    for noisy, clean, mask in train_loader:
        noisy, clean, mask = noisy.to(device), clean.to(device), mask.to(device)
        pred = model(noisy)
        loss = masked_mse(pred, clean, mask) + SMOOTH_WEIGHT * temporal_smoothness_penalty(pred, mask)
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()
        train_loss += loss.item() * noisy.size(0)
    train_loss /= len(train_loader.dataset)

    model.eval()
    val_loss = 0.0
    # baseline: "고치지 않고 그대로 쓰면" 정답과 얼마나 차이나는지 - 모델이
    # 실제로 뭔가 배웠는지 비교할 기준선.
    baseline_loss = 0.0
    with torch.no_grad():
        for noisy, clean, mask in val_loader:
            noisy, clean, mask = noisy.to(device), clean.to(device), mask.to(device)
            pred = model(noisy)
            val_loss += masked_mse(pred, clean, mask).item() * noisy.size(0)
            baseline_loss += masked_mse(noisy, clean, mask).item() * noisy.size(0)
    val_loss /= len(val_loader.dataset)
    baseline_loss /= len(val_loader.dataset)
    scheduler.step(val_loss)

    if val_loss < best_val:
        best_val = val_loss
        torch.save({'model_state': model.state_dict(), 'joints': JOINTS, 'max_len': MAX_LEN},
                   CHECKPOINT_PATH)

    if epoch % 5 == 0 or epoch == 1:
        print(f'epoch {epoch:3d} | train {train_loss:.5f} | val {val_loss:.5f} '
              f'(deg rmse ~{math.degrees(math.sqrt(val_loss)):.2f}) | '
              f'baseline(고치지 않음) deg rmse ~{math.degrees(math.sqrt(baseline_loss)):.2f} | '
              f'best {best_val:.5f}')
        # val이 baseline보다 낮아야 모델이 실제로 도움이 되는 것. 그 반대면
        # (모델이 오히려 더 나쁘면) 지난번 가짜 노이즈 버전과 같은 문제.

print('학습 완료. 체크포인트:', CHECKPOINT_PATH)


# %% [Cell 7] 정성적 확인 - held-out 단어 하나로 비교 -------------------------
import matplotlib.pyplot as plt

sample_idx = val_idx[0]
sample_noisy = noisy_seqs_all[sample_idx]
sample_clean = clean_seqs_all[sample_idx]
with torch.no_grad():
    model.eval()
    pred = model(torch.from_numpy(sample_noisy.astype(np.float32)).unsqueeze(0).to(device))[0].cpu().numpy()

joint_to_plot = 4  # Middle1 example
plt.figure(figsize=(9, 4))
plt.plot(np.degrees(sample_clean[:, joint_to_plot]), label='true 3D answer')
plt.plot(np.degrees(sample_noisy[:, joint_to_plot]), label='our real 2D pipeline output', alpha=0.7)
plt.plot(np.degrees(pred[:, joint_to_plot]), label='model output (corrected)', linewidth=2)
plt.legend(); plt.xlabel('frame'); plt.ylabel('bend angle (deg)')
plt.title(f'Held-out word ({meta_all[sample_idx]}) - real-pair denoiser check')
plt.show()

