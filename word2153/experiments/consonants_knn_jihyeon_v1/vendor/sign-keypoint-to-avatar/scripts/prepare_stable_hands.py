"""Separate consistent Holistic orientation from crop-refined finger shape."""
import argparse
import copy
import json
from math import acos, degrees, sqrt
from pathlib import Path


def shape_signature(hand):
    def minus(a,b):
        return [a[k]-b[k] for k in ('x','y','z')]
    result=[]
    for start in (1,5,9,13,17):
        for j in range(3):
            i=start+j
            u=minus(hand[i],hand[0 if j==0 else i-1])
            v=minus(hand[i+1],hand[i])
            norm=sqrt(sum(x*x for x in u)*sum(x*x for x in v))
            result.append(degrees(acos(max(-1,min(1,sum(x*y for x,y in zip(u,v))/max(norm,1e-12))))))
    return result


def prepare(base, refined):
    if base['frame_count'] != refined['frame_count'] or base['fps'] != refined['fps']:
        raise ValueError('Motion timelines differ')
    result=copy.deepcopy(refined)
    for original,row in zip(base['frames'],result['frames']):
        if original['timestamp_ms'] != row['timestamp_ms'] or original['pose'] != row['pose']:
            raise ValueError('Motions are not from the same extraction')
        for group in ('left_hand','right_hand'):
            row[group+'_orientation_world']=copy.deepcopy(original[group+'_world'])
            row[group+'_orientation']=copy.deepcopy(original[group])
            row[group+'_shape']=copy.deepcopy(original[group])
            if len(original[group])==len(row[group])==21:
                ratio=base['height']/base['width']
                metric=lambda pts:[{'x':v['x'],'y':v['y']*ratio,'z':v['z']} for v in pts]
                errors=[abs(a-b) for a,b in zip(shape_signature(metric(original[group])),shape_signature(metric(row[group])))]
                if max(errors)<=30 and sum(errors)/len(errors)<=12:
                    row[group+'_shape']=copy.deepcopy(row[group])
                    row['hand_quality'][group]['image_shape_source']=row['hand_quality'][group]['source']
                else:
                    row['hand_quality'][group]['image_shape_source']='holistic_rejected_disagreeing_crop'
            # A different inferred handshape is not evidence of improved precision.
            old,new=original[group+'_world'],row[group+'_world']
            if len(old)==len(new)==21:
                differences=[abs(a-b) for a,b in zip(shape_signature(old),shape_signature(new))]
                if max(differences)>35 or sum(differences)/len(differences)>15:
                    row[group+'_world']=copy.deepcopy(old)
                    row['hand_quality'][group]['shape_source']='holistic_rejected_disagreeing_crop'
                else:
                    row['hand_quality'][group]['shape_source']=row['hand_quality'][group]['source']
    result['orientation_policy']='Holistic image-depth orientation; compatible crops for intrinsic shape; image aspect corrected; no reflection'
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--base',type=Path,required=True)
    p.add_argument('--refined',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    result=prepare(json.loads(a.base.read_text(encoding='utf-8')),json.loads(a.refined.read_text(encoding='utf-8')))
    with a.output.open('x',encoding='utf-8') as f:
        json.dump(result,f,ensure_ascii=False,allow_nan=False,separators=(',',':'))
    print(a.output)


if __name__=='__main__':
    main()

