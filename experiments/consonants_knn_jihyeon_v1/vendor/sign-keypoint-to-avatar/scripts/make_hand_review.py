"""Create contact sheets and synchronized source/render playback for all frames."""
import argparse
import json
from pathlib import Path
import cv2
import numpy as np

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('renders',type=Path)
args=p.parse_args()
paths=sorted((args.renders/'sequence').glob('*.png'))
if not paths:
    raise ValueError('No rendered sequence')
for offset in range(0,len(paths),64):
    sheet=np.full((8*200,8*224,3),28,np.uint8)
    for k,path in enumerate(paths[offset:offset+64]):
        im=cv2.imread(str(path))
        tile=cv2.resize(im[190:550,100:540],(224,180))
        x,y=(k%8)*224,(k//8)*200
        sheet[y:y+180,x:x+224]=tile
        cv2.putText(sheet,path.stem,(x+8,y+195),cv2.FONT_HERSHEY_SIMPLEX,.45,(235,235,235),1)
    target=args.renders/f'contact_{offset:03d}.jpg'
    if target.exists():
        raise FileExistsError(target)
    cv2.imwrite(str(target),sheet)
html='''<!doctype html><html lang="ko"><meta charset="utf-8"><title>손 동작 원본 비교</title>
<style>body{background:#151b24;color:#eef3fa;font:17px system-ui;padding:20px}main{display:flex;gap:12px}section{width:50%}video,img{width:100%;height:65vh;object-fit:contain;background:#000}input{width:75%}p{color:#bdd0e5}button{font:inherit;padding:6px}</style>
<h1>손 동작 · 원본과 수정 결과</h1><p>원본 좌우를 반전하지 않았습니다. 움직임의 의미와 손 접촉은 원본과 비교해 확인하세요.</p>
<main><section><h2>원본</h2><video id="v" controls muted></video></section><section><h2>Blender 수정 결과</h2><img id="r" src="sequence/0000.png"></section></main>
<button id="play">재생 / 정지</button><input id="seek" type="range" min="0" max="295" value="0"><span id="no">0</span><p id="quality"></p>
<script>
const v=document.getElementById('v'),r=document.getElementById('r'),seek=document.getElementById('seek');let last=-1,audit;
Promise.all([fetch('../../../mediapipe-preview/assets/love.mp4').then(r=>r.blob()),fetch('audit.json').then(r=>r.json())]).then(([blob,a])=>{v.src=URL.createObjectURL(blob);audit=a});
function tick(){const f=Math.min(295,Math.max(0,Math.round(v.currentTime*30)));if(f!==last){r.src='sequence/'+String(f).padStart(4,'0')+'.png';seek.value=f;document.getElementById('no').textContent=f+'/295';if(audit)document.getElementById('quality').textContent=Object.entries(audit.frames[f].sides).map(([side,q])=>side+': '+q.applied).join(' / ');last=f}requestAnimationFrame(tick)}tick();
document.getElementById('play').onclick=()=>v.paused?v.play():v.pause();seek.oninput=()=>{v.pause();v.currentTime=Number(seek.value)/30};
</script></html>'''
with (args.renders/'playback.html').open('x',encoding='utf-8') as f:
    f.write(html)
print(f'{len(paths)} rendered frames; contact sheets and playback saved in {args.renders}')

