"""Process extracted clips; skip only completed and verified v4 results."""
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import subprocess
from datetime import datetime

ROOT = Path(__file__).resolve().parent
BLENDER = Path('C:/Program Files/Blender Foundation/Blender 5.2/blender.exe')


def run(item):
    word = item['word_id']
    folder = ROOT/'runs'/word
    report = folder/'result_v4.json'
    if report.exists():
        data = json.loads(report.read_text(encoding='utf-8'))
        if all(v['status'] == 'PASS' for v in data['verification'].values()) and all((folder/n).exists() for n in data['output_files'].values()):
            print('VERIFIED_EXISTING',word,flush=True)
            return {'word':word,'status':'complete'}
        raise ValueError('Unverified existing result: '+word)
    print('PROCESS',word,flush=True)
    with (folder/('process_'+datetime.now().strftime('%Y%m%d_%H%M%S_%f')+'.log')).open('x',encoding='utf-8') as log:
        result = subprocess.run([str(BLENDER),'--background','--threads','2','--python-exit-code','1','--python',str(ROOT/'process_clip.py'),'--','--word',word,'--resume-intermediates'],stdout=log,stderr=subprocess.STDOUT)
    status = 'complete' if result.returncode == 0 and report.exists() else 'failed'
    print(status.upper(),word,flush=True)
    return {'word':word,'status':status}


if __name__ == '__main__':
    items = json.loads((ROOT/'extraction_results.json').read_text(encoding='utf-8'))
    assert all(x['status'] == 'extracted' for x in items)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(run,items))
    with (ROOT/('processing_results_'+datetime.now().strftime('%Y%m%d_%H%M%S')+'.json')).open('x',encoding='utf-8') as f:
        json.dump(results,f,indent=2)
    if any(x['status'] != 'complete' for x in results):
        raise SystemExit(1)

