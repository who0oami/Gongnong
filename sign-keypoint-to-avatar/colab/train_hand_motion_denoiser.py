"""
Google Colab용: 불안정한(노이즈 있는) 손 모션 -> 안정된 손 모션 학습 스크립트.

=====================================================================
왜 이렇게 설계했는지 (입력/출력 정의)
=====================================================================

문제: 실제 영상(love.mp4, leave.mp4 등)에서 MediaPipe로 뽑은 손 키포인트를
아바타에 리타게팅하면 손가락이 떨리거나 부자연스러운 모양이 됨. 이걸 고치는
모델을 학습시키고 싶음.

  INPUT  (모델 입력)  : 노이즈가 섞인 손 모양 시퀀스
                        - 한 프레임 = 관절 굽힘각 14개 (라디안)
                          [Thumb IP, Thumb TIP,
                           Index MCP/PIP/DIP,
                           Middle MCP/PIP/DIP,
                           Ring MCP/PIP/DIP,
                           Little MCP/PIP/DIP]
                        - 시퀀스 = (프레임 수, 14) 형태, 한쪽 손 기준
                          (왼손/오른손은 독립적으로 같은 모델에 넣음)

  OUTPUT (모델 출력)  : 같은 shape (프레임 수, 14)의 "보정된" 굽힘각 시퀀스

  즉 모델은 "(T, 14) 시퀀스 -> (T, 14) 시퀀스"를 배우는 시퀀스 디노이징
  모델입니다. 각도만 다루기 때문에 좌우 반전/카메라 각도/손 크기에 영향을
  받지 않고, sign-keypoint-to-avatar/extractor/build_hand_shape_prior.py 에서 이미 쓰던
  표현과 동일해서 기존 파이프라인과 바로 연결됩니다.

=====================================================================
학습 데이터 쌍(pair)을 어떻게 만드는가 - 여기가 핵심
=====================================================================

문제: "노이즈 있는 진짜 영상 손모양" <-> "그것의 정답(자연스러운) 손모양"
짝이 실제로는 없습니다. 실제 영상에는 정답이 없고, SYN 데이터셋(사용자가
알려준 경로)에는 이미 깨끗한 값만 있습니다.

해결: SYN 키포인트(합성 아바타를 5대 카메라로 찍어 만든 데이터라 노이즈가
거의 없음)를 "정답(clean)"으로 놓고, 여기에 우리가 직접 실제 MediaPipe
노이즈를 흉내낸 가짜 노이즈를 입혀서 "입력(noisy)"을 만듭니다.
    clean (SYN 정답) --[가짜 노이즈 주입]--> noisy (모델 입력)
    모델이 noisy를 보고 clean을 복원하도록 학습 (지도학습, MSE loss)

가짜 노이즈는 아무렇게나 만든 게 아니라, 이번 세션에서 leave.mp4를 실제로
분석해서 측정한 값을 그대로 반영합니다:
  1) 프레임마다 독립적인 작은 흔들림 (관절당 표준편차 2~4도 정도)
     -> holistic 탐지와 crop 재탐지가 매 프레임 번갈아 선택되면서 생기는 떨림
  2) 이따금 더 큰 프레임 단위 튐 (약 10~15%의 프레임, 최대 20~30도)
     -> 탐지기가 통째로 바뀌는 프레임
  3) 구간 결측 후 마지막 값 고정 (5~20프레임 구간을 무작위로 골라 고정)
     -> leave.mp4 마지막 0.5초처럼 탐지가 아예 안 되는 구간

=====================================================================
학습 후 실제로 어떻게 쓰는가
=====================================================================

1) 이 노트북에서 모델을 학습시키고 .pt 파일로 저장
2) 로컬(Blender가 있는 PC)에서 실제 leave/love 등 영상의 _shape 랜드마크를
   같은 14차원 굽힘각으로 변환
3) (이 저장소로 옮겨서) scripts/apply_hand_motion_denoiser.py 로 모델을
   로드해 보정된 굽힘각을 뽑고, 그 값을 본 회전에 그대로 대입
   (기존 scripts/correct_hand_shape_prior.py와 동일한 "축은 유지, 각도만
   교체" 방식이라 파이프라인에 바로 끼워넣을 수 있음)

=====================================================================
Colab 사용법
=====================================================================
1) 로컬에서 sign-keypoint-to-avatar/colab/prepare_dataset_zip.ps1 로 F뷰만 골라 압축한
   zip 파일 하나를 만들어 Google Drive에 올려둔다 (압축 풀지 말고 zip
   그대로 - 파일 수만 개를 개별 업로드하면 몇 시간씩 걸린다).
2) 이 파일 내용을 Colab 새 노트북에 그대로 붙여넣기 (# %% 로 셀 구분)
3) 아래 ZIP_PATH 를 본인이 Drive에 올린 실제 zip 경로로 수정
4) 런타임 -> 런타임 유형 변경 -> GPU(T4) 선택 (없어도 CPU로 돌아가지만 느림)
5) 위에서부터 순서대로 실행 (Cell 1이 자동으로 압축을 풀고 DATASET_ROOT를
   그 결과 폴더로 잡아준다)
"""

# %% [Cell 1] Google Drive 마운트 + zip 압축 해제 + 경로 설정 ----------------
from google.colab import drive
drive.mount('/content/drive')

import json
import math
import random
import re
import zipfile
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader

# vvv 본인이 Drive에 올린 zip의 실제 경로로 바꾸세요 vvv
ZIP_PATH = Path('/content/drive/MyDrive/syn_F_only_300.zip')
# 어디 올렸는지 모르면 이 줄의 주석을 풀고 실행해서 먼저 찾아보세요:
# list(Path('/content/drive/MyDrive').rglob(ZIP_PATH.name))

EXTRACT_ROOT = Path('/content/dataset')  # 압축은 Drive가 아니라 Colab 로컬 디스크에 풂 (훨씬 빠름)
if not ZIP_PATH.is_file():
    raise FileNotFoundError(
        f'zip을 못 찾음: {ZIP_PATH}\n'
        "Drive에 올린 실제 경로로 ZIP_PATH를 수정하세요. 위치를 모르면:\n"
        "list(Path('/content/drive/MyDrive').rglob('*.zip')) 로 먼저 찾아보세요.")

# zip 안의 목록만으로 먼저 검사 - Drive의 다른 파일이 섞여 들어올 길이 없는지
# (extractall이 여기서 쓰는 경로 밖으로는 못 나가고, zip 안에 있는 것만 풀림)
# 확실히 하기 위해 직접 항목을 확인한다.
with zipfile.ZipFile(ZIP_PATH) as z:
    names = z.namelist()
    bad = [n for n in names if not n.endswith('.json') and not n.endswith('/')]
    print(f'zip 안 항목 수: {len(names)}개')
    if bad:
        print(f'경고: .json이 아닌 항목 {len(bad)}개 발견 (예: {bad[:5]}) - '
              'zip 자체에 다른 파일이 들어있을 수 있음')

# 매번 깨끗하게: 이전에 다른 걸로 풀어놓은 게 남아 있으면 섞일 수 있으므로,
# 항상 지우고 이 zip 내용만 새로 푼다.
import shutil
if EXTRACT_ROOT.exists():
    print(f'기존 {EXTRACT_ROOT} 삭제 후 이 zip 내용만 새로 풂')
    shutil.rmtree(EXTRACT_ROOT)
print(f'압축 해제 중... ({ZIP_PATH.name} -> {EXTRACT_ROOT})')
with zipfile.ZipFile(ZIP_PATH) as z:
    z.extractall(EXTRACT_ROOT)

top_level = sorted(p.name for p in EXTRACT_ROOT.iterdir())
print(f'압축 해제 완료. 최상위 폴더/파일 {len(top_level)}개 (이 zip에서 나온 것만 있어야 함):')
print(top_level[:10], '...' if len(top_level) > 10 else '')

DATASET_ROOT = EXTRACT_ROOT  # prepare_dataset_zip.ps1 결과는 WORD#### 폴더가 바로 이 밑에 옴
print(f'DATASET_ROOT = {DATASET_ROOT.resolve()} (이 폴더 안, 이 zip에서 나온 파일만 검색함)')
CHECKPOINT_PATH = Path('/content/drive/MyDrive/hand_motion_denoiser.pt')  # 학습 결과는 Drive에 저장 (세션 끊겨도 안 날아감)

VIEW = 'F'  # 실제 영상은 카메라 한 대뿐이므로, 학습도 정면(F) 뷰만 사용
MAX_LEN = 150  # 이보다 긴 시퀀스는 자르고, 짧은 건 마지막 프레임으로 패딩
JOINTS = 14  # Thumb2,Thumb3, (Index/Middle/Ring/Little)1,2,3


# %% [Cell 2] 원본 keypoint JSON -> 14차원 굽힘각 시퀀스 ---------------------
# NIA_SL_WORD####_SYN##_F_000000000000_keypoints.json 형태 파일을 찾아,
# OpenPose 포맷(people[0].hand_left_keypoints_2d 등, stride=3: x,y,confidence)을
# 읽어서 sign-keypoint-to-avatar/extractor/build_hand_shape_prior.py 와 같은 방식으로
# 관절 굽힘각 14개를 계산합니다.

FRAME_PATTERN = re.compile(r'(WORD\d{4})_(SYN\d{2})_([FUDLR])_(\d+)_keypoints\.json$', re.IGNORECASE)
FINGERS = ['Thumb', 'Index', 'Middle', 'Ring', 'Little']
STARTS = {'Thumb': 1, 'Index': 5, 'Middle': 9, 'Ring': 13, 'Little': 17}
MIN_CONF = 0.15


def get_person(data):
    people = data.get('people')
    if isinstance(people, list):
        return people[0] if people else None
    if isinstance(people, dict):
        return people
    return None


def parse_hand(values):
    """OpenPose stride-3 (x,y,confidence) 21-point 배열 -> [(x,y), ...] 또는 None."""
    if not values or len(values) < 21 * 3:
        return None
    pts = []
    for i in range(21):
        x, y, c = values[i*3], values[i*3+1], values[i*3+2]
        if c < MIN_CONF:
            return None
        pts.append((x, y))
    return pts


def angle_between(u, v):
    lu = math.hypot(*u)
    lv = math.hypot(*v)
    if lu < 1e-6 or lv < 1e-6:
        return None
    cos = (u[0]*v[0] + u[1]*v[1]) / (lu * lv)
    return math.acos(max(-1.0, min(1.0, cos)))


def hand_bend_vector(hand):
    """21점 손 -> 14개 관절 굽힘각(라디안). 결측/저신뢰 시 None."""
    if hand is None:
        return None
    out = []
    for finger in FINGERS:
        start = STARTS[finger]
        joints = (2, 3) if finger == 'Thumb' else (1, 2, 3)
        for j in joints:
            a = hand[start+j-1]
            b = hand[0] if j == 1 else hand[start+j-2]
            c = hand[start+j]
            inc = (a[0]-b[0], a[1]-b[1])
            outv = (c[0]-hand[start+j-1][0], c[1]-hand[start+j-1][1])
            ang = angle_between(inc, outv)
            if ang is None:
                return None
            out.append(ang)
    return out


def find_word_files(root, view=VIEW):
    """word_id -> {frame_no: path} 형태로 정리 (재귀 탐색, 폴더 구조에 의존하지 않음)."""
    words = {}
    for path in root.rglob('*_keypoints.json'):
        m = FRAME_PATTERN.search(path.name)
        if not m or m.group(3).upper() != view:
            continue
        word_id = m.group(1).upper()
        frame_no = int(m.group(4))
        words.setdefault(word_id, {})[frame_no] = path
    return words


def load_word_sequences(path_by_frame):
    """한 단어의 프레임 파일들을 순서대로 읽어 (left_seq, right_seq) 반환.
    각 seq는 유효한 (14,) 벡터들의 리스트 (결측 프레임은 건너뜀 - SYN 데이터는
    합성이라 결측이 거의 없어야 정상이고, 있으면 그 프레임만 제외)."""
    left_seq, right_seq = [], []
    for frame_no in sorted(path_by_frame):
        try:
            data = json.loads(path_by_frame[frame_no].read_text(encoding='utf-8'))
        except Exception:
            continue
        person = get_person(data)
        if person is None:
            continue
        lh = hand_bend_vector(parse_hand(person.get('hand_left_keypoints_2d')))
        rh = hand_bend_vector(parse_hand(person.get('hand_right_keypoints_2d')))
        if lh is not None:
            left_seq.append(lh)
        if rh is not None:
            right_seq.append(rh)
    return left_seq, right_seq


print(f'키포인트 파일 인덱싱 중... (검색 대상: {DATASET_ROOT.resolve()}, 수 분 걸릴 수 있음)')
word_files = find_word_files(DATASET_ROOT)
print(f'{len(word_files)}개 단어 발견')

clean_sequences = []  # 각 원소: (word_id, side, np.ndarray shape (T,14))
for i, (word_id, frames) in enumerate(word_files.items()):
    left_seq, right_seq = load_word_sequences(frames)
    if len(left_seq) >= 8:
        clean_sequences.append((word_id, 'L', np.array(left_seq, dtype=np.float32)))
    if len(right_seq) >= 8:
        clean_sequences.append((word_id, 'R', np.array(right_seq, dtype=np.float32)))
    if (i+1) % 100 == 0:
        print(f'{i+1}/{len(word_files)} 단어 처리, 현재 {len(clean_sequences)}개 시퀀스')

print(f'최종 학습용 시퀀스: {len(clean_sequences)}개 (단어x손)')


# %% [Cell 3] 단어 단위로 train/val 분리 -------------------------------------
random.seed(0)
all_word_ids = sorted(set(w for w, _, _ in clean_sequences))
random.shuffle(all_word_ids)
split = int(len(all_word_ids) * 0.9)
train_words = set(all_word_ids[:split])
val_words = set(all_word_ids[split:])

train_seqs = [s for w, side, s in clean_sequences if w in train_words]
val_seqs = [s for w, side, s in clean_sequences if w in val_words]
print(f'train 단어 {len(train_words)}개 ({len(train_seqs)}개 시퀀스) / '
      f'val 단어 {len(val_words)}개 ({len(val_seqs)}개 시퀀스)')


# %% [Cell 4] 실측 기반 가짜 노이즈 주입 함수 --------------------------------
def add_synthetic_noise(clean, rng):
    """clean: (T,14). leave.mp4 분석에서 측정된 세 가지 노이즈 패턴을 재현.
    spike_mask(T,)도 같이 반환 - 학습 때 "드문 큰 튐" 프레임에 별도로
    가중치를 주기 위함. 이 마스크가 없으면 큰 튐은 전체 프레임의
    8~15%밖에 안 돼서, 평범한 loss로는 모델이 그 경우를 충분히
    못 배우고(관찰됨: 모델이 스스로 큰 오차를 만들어내는 프레임 발생)."""
    T = clean.shape[0]
    noisy = clean.copy()
    spike_mask = np.zeros(T, dtype=np.float32)

    # 1) 프레임별 독립적인 작은 흔들림 (관절당 표준편차 ~2~4도)
    jitter_std = math.radians(rng.uniform(2, 4))
    noisy += rng.normal(0, jitter_std, size=noisy.shape).astype(np.float32)

    # 2) 이따금 프레임 전체가 크게 튐 (탐지기 전환 시뮬레이션)
    n_spikes = int(T * rng.uniform(0.08, 0.15))
    spike_idx = rng.choice(T, size=min(n_spikes, T), replace=False)
    for idx in spike_idx:
        spike_std = math.radians(rng.uniform(10, 25))
        noisy[idx] += rng.normal(0, spike_std, size=JOINTS).astype(np.float32)
        spike_mask[idx] = 1.0

    # 3) 구간 결측 -> 마지막 값 고정 (0~1개 구간, 길이 5~20프레임)
    if rng.random() < 0.5 and T > 25:
        gap_len = int(rng.uniform(5, min(20, T // 3)))
        gap_start = int(rng.uniform(0, T - gap_len))
        hold_value = noisy[max(gap_start - 1, 0)].copy()
        noisy[gap_start:gap_start + gap_len] = hold_value

    return np.clip(noisy, 0, math.pi), spike_mask


# %% [Cell 5] Dataset / DataLoader ------------------------------------------
class HandMotionDataset(Dataset):
    """매 epoch, 매 샘플마다 새로운 가짜 노이즈를 씌워서
    (noisy, clean, mask, spike_mask) 반환.
    -> 모델이 "노이즈의 특정 형태"를 외우는 게 아니라 일반적인 디노이징을 배움."""

    def __init__(self, sequences, max_len=MAX_LEN, seed=0):
        self.sequences = sequences
        self.max_len = max_len
        self.rng = np.random.default_rng(seed)

    def __len__(self):
        return len(self.sequences)

    def __getitem__(self, idx):
        clean = self.sequences[idx]
        T = clean.shape[0]
        noisy, spike_mask = add_synthetic_noise(clean, self.rng)

        if T >= self.max_len:
            start = self.rng.integers(0, T - self.max_len + 1)
            clean = clean[start:start + self.max_len]
            noisy = noisy[start:start + self.max_len]
            spike_mask = spike_mask[start:start + self.max_len]
            mask = np.ones(self.max_len, dtype=np.float32)
        else:
            pad = self.max_len - T
            clean = np.concatenate([clean, np.repeat(clean[-1:], pad, axis=0)], axis=0)
            noisy = np.concatenate([noisy, np.repeat(noisy[-1:], pad, axis=0)], axis=0)
            spike_mask = np.concatenate([spike_mask, np.zeros(pad, dtype=np.float32)])
            mask = np.concatenate([np.ones(T, dtype=np.float32), np.zeros(pad, dtype=np.float32)])

        return (torch.from_numpy(noisy), torch.from_numpy(clean),
                torch.from_numpy(mask), torch.from_numpy(spike_mask))


train_loader = DataLoader(HandMotionDataset(train_seqs, seed=1), batch_size=32, shuffle=True)
val_loader = DataLoader(HandMotionDataset(val_seqs, seed=2), batch_size=32, shuffle=False)


# %% [Cell 6] 모델: 양방향 GRU 디노이저 --------------------------------------
class HandMotionDenoiser(nn.Module):
    """(T,14) 노이즈 시퀀스 -> (T,14) 보정 시퀀스.
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
        # 잔차 연결: 모델이 "전체를 새로 만들기"보다 "필요한 만큼만 고치기"를
        # 배우도록 유도 (입력에서 얼마나 벗어날지만 학습).
        return x + self.output_proj(h)


device = 'cuda' if torch.cuda.is_available() else 'cpu'
model = HandMotionDenoiser().to(device)
print('device:', device, '| 파라미터 수:', sum(p.numel() for p in model.parameters()))


# %% [Cell 7] 학습 루프 ------------------------------------------------------
def masked_mse(pred, target, mask):
    diff = (pred - target) ** 2
    diff = diff.mean(dim=-1)  # (B,T)
    return (diff * mask).sum() / mask.sum().clamp(min=1)


def temporal_smoothness_penalty(pred, mask):
    """출력이 프레임 간 급격히 튀지 않도록 - 우리가 실측한 '떨림'을 학습 단계에서도 직접 벌점."""
    d = pred[:, 1:] - pred[:, :-1]
    m = mask[:, 1:] * mask[:, :-1]
    return ((d ** 2).mean(dim=-1) * m).sum() / m.sum().clamp(min=1)


optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)
scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(optimizer, patience=5, factor=0.5)
# 이전 학습에서 확인된 문제: 큰 튐(spike) 프레임은 전체의 8~15%뿐이라
# 평범한 loss로는 충분히 배우지 못했고(빈도가 낮음), 모델이 스스로 큰
# 오차를 만들어내는 프레임도 있었음(출력 자체의 급변을 막는 벌점이 약함).
# -> SMOOTH_WEIGHT를 올리고, spike 프레임에 별도 가중치(SPIKE_WEIGHT)를 추가.
SMOOTH_WEIGHT = 0.3
SPIKE_WEIGHT = 2.0
best_val = float('inf')
EPOCHS = 100

for epoch in range(1, EPOCHS + 1):
    model.train()
    train_loss = 0.0
    for noisy, clean, mask, spike_mask in train_loader:
        noisy, clean, mask, spike_mask = (
            noisy.to(device), clean.to(device), mask.to(device), spike_mask.to(device))
        pred = model(noisy)
        spike_weighted_mask = mask * (1.0 + SPIKE_WEIGHT * spike_mask)
        loss = (masked_mse(pred, clean, spike_weighted_mask)
                + SMOOTH_WEIGHT * temporal_smoothness_penalty(pred, mask))
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()
        train_loss += loss.item() * noisy.size(0)
    train_loss /= len(train_loader.dataset)

    model.eval()
    val_loss = 0.0
    val_spike_loss, val_spike_count = 0.0, 0.0
    with torch.no_grad():
        for noisy, clean, mask, spike_mask in val_loader:
            noisy, clean, mask, spike_mask = (
                noisy.to(device), clean.to(device), mask.to(device), spike_mask.to(device))
            pred = model(noisy)
            loss = masked_mse(pred, clean, mask)
            val_loss += loss.item() * noisy.size(0)
            spike_only = mask * spike_mask
            diff = ((pred - clean) ** 2).mean(dim=-1)
            val_spike_loss += (diff * spike_only).sum().item()
            val_spike_count += spike_only.sum().item()
    val_loss /= len(val_loader.dataset)
    val_spike_rmse_deg = math.degrees(math.sqrt(val_spike_loss / max(val_spike_count, 1)))
    scheduler.step(val_loss)

    if val_loss < best_val:
        best_val = val_loss
        torch.save({'model_state': model.state_dict(), 'joints': JOINTS, 'max_len': MAX_LEN},
                   CHECKPOINT_PATH)

    if epoch % 5 == 0 or epoch == 1:
        print(f'epoch {epoch:3d} | train {train_loss:.5f} | val {val_loss:.5f} '
              f'(deg rmse ~{math.degrees(math.sqrt(val_loss)):.2f}) | '
              f'spike rmse ~{val_spike_rmse_deg:.2f} | best {best_val:.5f}')
        # spike rmse: "큰 튐" 프레임만 따로 잰 오차. 이게 안 줄면 SPIKE_WEIGHT를
        # 더 올리거나(예: 4.0) 학습 데이터를 늘리는 쪽으로 가야 함.

print('학습 완료. 체크포인트:', CHECKPOINT_PATH)


# %% [Cell 8] 정성적 확인 - held-out 단어 하나로 노이즈/복원 비교 -------------
import matplotlib.pyplot as plt

sample_clean = val_seqs[0]
sample_noisy, sample_spike_mask = add_synthetic_noise(sample_clean, np.random.default_rng(42))
with torch.no_grad():
    model.eval()
    pred = model(torch.from_numpy(sample_noisy).unsqueeze(0).to(device))[0].cpu().numpy()

joint_to_plot = 4  # Middle MCP example
plt.figure(figsize=(9, 4))
plt.plot(np.degrees(sample_clean[:, joint_to_plot]), label='clean (ground truth)')
plt.plot(np.degrees(sample_noisy[:, joint_to_plot]), label='noisy (synthetic noise added)', alpha=0.6)
plt.plot(np.degrees(pred[:, joint_to_plot]), label='model output (corrected)', linewidth=2)
spike_frames = np.where(sample_spike_mask > 0)[0]
plt.scatter(spike_frames, np.degrees(sample_noisy[spike_frames, joint_to_plot]),
            color='red', marker='x', label='spike-injected frame', zorder=5)
plt.legend(); plt.xlabel('frame'); plt.ylabel('bend angle (deg)')
plt.title('Held-out word - denoiser sanity check')
plt.show()
