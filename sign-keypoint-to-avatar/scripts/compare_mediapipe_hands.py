"""Save source / refined overlay / Blender comparison without reflecting pixels."""
import argparse
import json
from pathlib import Path
import cv2

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--video',type=Path,required=True)
p.add_argument('--motion',type=Path,required=True)
p.add_argument('--renders',type=Path,required=True)
args=p.parse_args()
data=json.loads(args.motion.read_text(encoding='utf-8'))
cap=cv2.VideoCapture(str(args.video))
items=[]
try:
    for i in (0,17,34,51,67,180,200,220):
        cap.set(cv2.CAP_PROP_POS_FRAMES,i)
        ok,frame=cap.read()
        if not ok:
            raise ValueError(f'Cannot decode {i}')
        raw=frame.copy()
        row=data['frames'][i]
        for group,color in (('left_hand',(0,215,255)),('right_hand',(190,80,255))):
            pts=row[group]
            if not pts:
                continue
            pts=[(round(v['x']*frame.shape[1]),round(v['y']*frame.shape[0])) for v in pts]
            for start in (1,5,9,13,17):
                chain=[0,*range(start,start+4)]
                for a,b in zip(chain,chain[1:]):
                    cv2.line(frame,pts[a],pts[b],color,2)
            for x,y in pts:
                cv2.circle(frame,(x,y),2,color,-1)
            cv2.putText(frame,'L' if group=='left_hand' else 'R',pts[0],cv2.FONT_HERSHEY_SIMPLEX,.6,color,2)
        for name,image in [('source',raw),('overlay',frame)]:
            path=args.renders/f'frame_{i:03d}_{name}.png'
            if path.exists():
                raise FileExistsError(path)
            if not cv2.imwrite(str(path),image):
                raise IOError(path)
        status=' | '.join(f"{s}: {row['hand_quality'][s]['source']} / {row['hand_quality'][s]['identity']}" for s in ('left_hand','right_hand'))
        items.append(f'<h2>Frame {i}</h2><p>{status}</p><div>'+''.join(f'<figure><img src="frame_{i:03d}_{suffix}.png"><figcaption>{label}</figcaption></figure>' for suffix,label in [('source','Source (not mirrored)'),('overlay','Yellow: anatomical L / Pink: anatomical R'),('hands','Blender articulated fingers')])+'</div>')
finally:
    cap.release()
html='<!doctype html><meta charset="utf-8"><title>Hand verification</title><style>body{background:#18212b;color:white;font:16px system-ui;padding:20px}div{display:flex}figure{margin:8px;flex:1}img{width:100%}p{color:#f9d28a}</style><h1>Source / landmarks / Blender comparison</h1><p>Unverified and missing observations require review. This is not linguistic validation.</p>'+''.join(items)
with (args.renders/'comparison.html').open('x',encoding='utf-8') as f:
    f.write(html)
print(args.renders/'comparison.html')
