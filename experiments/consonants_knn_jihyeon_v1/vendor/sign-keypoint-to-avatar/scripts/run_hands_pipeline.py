"""Reusable video -> Holistic -> hand refinement -> Blender pipeline."""
import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('video',type=Path)
    p.add_argument('--sign-id',required=True)
    p.add_argument('--label',default='')
    p.add_argument('--profile',type=Path,default=ROOT/'mediapipe-preview/blender_natural_profile.json')
    p.add_argument('--blender',type=Path,default=Path('C:/Program Files/Blender Foundation/Blender 5.2/blender.exe'))
    args=p.parse_args()
    if not args.video.is_file() or not args.blender.is_file():
        p.error('Video or Blender executable missing')
    if not args.sign_id or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-' for c in args.sign_id):
        p.error('Use letters, digits, underscore or hyphen for sign-id')
    profile=json.loads(args.profile.read_text(encoding='utf-8'))
    if not Path(profile['model_file']).is_file():
        p.error('Model file in profile is missing')
    run=ROOT/'output'/(args.sign_id+'_hands_'+datetime.now().strftime('%Y%m%d_%H%M%S'))
    run.mkdir(parents=True,exist_ok=False)
    raw,refined,blend=run/'holistic.json',run/'hands.json',run/(run.name+'.blend')
    stable=run/'hands_stable.json'
    commands=[
        [sys.executable,str(ROOT/'extractor/extract_keypoints.py'),str(args.video.resolve()),'--output',str(raw),'--sign-id',args.sign_id,'--label',args.label,'--download-model'],
        [sys.executable,str(ROOT/'extractor/refine_hands.py'),str(args.video.resolve()),'--input',str(raw),'--output',str(refined),'--download-model'],
        [sys.executable,str(ROOT/'scripts/prepare_stable_hands.py'),'--base',str(raw),'--refined',str(refined),'--output',str(stable)],
        [str(args.blender),'--background','--factory-startup','--python-exit-code','1','--python',str(ROOT/'scripts/mediapipe_to_blender_natural.py'),'--','--motion',str(stable),'--profile',str(args.profile.resolve()),'--output',str(blend),'--render']]
    # Git Bash sets HOME to a POSIX-style path (e.g. /c/Users/...), which the native
    # Windows Blender build cannot resolve as a cache directory; it then falls back to
    # dumping a garbled-named ".thumbnails" cache folder into ROOT (cwd). Only Blender
    # needs the corrected HOME - the Python steps are unaffected.
    blender_env = os.environ.copy()
    blender_env['HOME'] = os.environ.get('USERPROFILE', blender_env.get('HOME', ''))
    for cmd in commands:
        env = blender_env if Path(cmd[0]) == args.blender else None
        subprocess.run(cmd,cwd=ROOT,check=True,env=env)
    print(f'Created: {blend}\nReview audit and renders before accepting sign quality.')


if __name__=='__main__':
    main()

