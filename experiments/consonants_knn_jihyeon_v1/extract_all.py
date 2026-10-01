"""Extract all 18 recorded consonants into a new experiment, never overwrite."""
import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
WORK = ROOT.parents[1]
SOURCE_ROOT = WORK / 'word2153'
VENDOR = ROOT / 'vendor/sign-keypoint-to-avatar'


def run(item):
    folder = ROOT / 'runs' / item['word_id']
    folder.mkdir(parents=True, exist_ok=False)
    commands = [
        [sys.executable, str(VENDOR/'extractor/extract_keypoints.py'), item['video'], '--output', str(folder/'raw.json'), '--sign-id', item['word_id'], '--label', item['letter']],
        [sys.executable, str(VENDOR/'extractor/refine_hands.py'), item['video'], '--input', str(folder/'raw.json'), '--output', str(folder/'refined.json')],
        [sys.executable, str(VENDOR/'scripts/prepare_stable_hands.py'), '--base', str(folder/'raw.json'), '--refined', str(folder/'refined.json'), '--output', str(folder/'stable.json')],
        [sys.executable, str(VENDOR/'extractor/smooth_hand_landmarks.py'), '--input', str(folder/'stable.json'), '--output', str(folder/'smoothed.json')],
    ]
    try:
        for i, command in enumerate(commands):
            print(item['word_id'], 'extract stage', i, flush=True)
            with (folder/f'extract_{i}.log').open('w', encoding='utf-8') as log:
                subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, check=True)
        return {**item, 'status': 'extracted'}
    except Exception as error:
        return {**item, 'status': 'failed', 'error': str(error)}


def main():
    models = VENDOR/'extractor/models'
    models.mkdir(exist_ok=True)
    for name in ('hand_landmarker.task', 'holistic_landmarker.task'):
        if not (models/name).exists():
            shutil.copy2(WORK/'extractor/models'/name, models/name)
    items = []
    for number in range(3002, 3020):
        word = f'WORD{number}'
        directory = SOURCE_ROOT/'output'/('consonant_replacements' if number < 3005 else 'consonant_recordings')
        metadata = json.loads((directory/f'{word}.json').read_text(encoding='utf-8'))
        video = directory/f'{word}.mp4'
        items.append({'word_id': word, 'letter': metadata['letter'], 'video': str(video), 'sha256': hashlib.sha256(video.read_bytes()).hexdigest()})
    with (ROOT/'inputs.json').open('x', encoding='utf-8') as f:
        json.dump(items, f, ensure_ascii=False, indent=2)
    os.environ['PYTHONIOENCODING'] = 'utf-8'
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(run, items))
    with (ROOT/'extraction_results.json').open('x', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(json.dumps(results, ensure_ascii=False), flush=True)
    if any(r['status'] != 'extracted' for r in results):
        raise SystemExit(1)


if __name__ == '__main__':
    main()

