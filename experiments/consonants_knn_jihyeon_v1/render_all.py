"""Render and encode completed clips without replacing existing outputs."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT.parents[1]/'word2153/.recording-deps'))
import imageio_ffmpeg
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
BLENDER = 'C:/Program Files/Blender Foundation/Blender 5.2/blender.exe'


def run(item):
    word=item['word_id']
    folder=ROOT/'runs'/word
    if not (folder/'result_v4.json').exists():
        return {'word':word,'status':'not_processed'}
    out=folder/'preview_v4'
    if not (out/'render_complete.json').exists():
        print('RENDER',word,flush=True)
        with (folder/('render_'+datetime.now().strftime('%H%M%S_%f')+'.log')).open('x',encoding='utf-8') as log:
            result=subprocess.run([BLENDER,'--background','--threads','2','--python-exit-code','1','--python',str(ROOT/'render_clip.py'),'--','--word',word],stdout=log,stderr=subprocess.STDOUT)
        if result.returncode:
            return {'word':word,'status':'render_failed'}
    data=json.loads((out/'render_complete.json').read_text())
    for variant in data['variants']:
        target=out/(variant+'.mp4')
        if not target.exists():
            subprocess.run([FFMPEG,'-hide_banner','-loglevel','error','-n','-framerate',str(data['fps']),'-i',str(out/variant/'%04d.png'),'-c:v','libx264','-threads','2','-crf','19','-pix_fmt','yuv420p','-movflags','+faststart',str(target)],check=True)
        subprocess.run([FFMPEG,'-hide_banner','-loglevel','error','-i',str(target),'-f','null','-'],check=True,stdout=subprocess.DEVNULL)
    print('PREVIEW_COMPLETE',word,flush=True)
    return {'word':word,'status':'complete'}


if __name__=='__main__':
    items=json.loads((ROOT/'inputs.json').read_text(encoding='utf-8'))
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(run,items))
    with (ROOT/('render_results_'+datetime.now().strftime('%Y%m%d_%H%M%S')+'.json')).open('x') as f:
        json.dump(results,f,indent=2)
    if any(x['status']!='complete' for x in results):
        raise SystemExit(1)

