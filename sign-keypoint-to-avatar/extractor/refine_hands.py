"""Second-pass unmirrored hand crops with anatomical wrist association and audit."""
import argparse
from collections import Counter
import copy
import hashlib
import json
import os
from math import hypot
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parent
os.environ.setdefault('MPLCONFIGDIR', str(ROOT / '.mplconfig'))
URL = 'https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task'
SIDES = {'left_hand': (15, 13, 16), 'right_hand': (16, 14, 15)}


def wrist_association(wrist, own_anchor, other_anchor, forearm):
    """Identity depends on anatomical anchors even when the arms cross."""
    own = hypot(wrist[0]-own_anchor[0], wrist[1]-own_anchor[1])
    other = hypot(wrist[0]-other_anchor[0], wrist[1]-other_anchor[1])
    return own < max(12., forearm*.6) and other-own > max(5., forearm*.12)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('video', type=Path)
    p.add_argument('--input', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--download-model', action='store_true')
    args = p.parse_args()
    if args.output.exists():
        p.error('Output exists; use a new filename')
    data = json.loads(args.input.read_text(encoding='utf-8'))
    if data['schema'] != 'mediapipe-holistic-v1':
        p.error('Expected mediapipe-holistic-v1')
    model = ROOT / 'models/hand_landmarker.task'
    if not model.exists():
        if not args.download_model:
            p.error('Use --download-model once')
        with urlopen(URL, timeout=120) as response:
            payload = response.read()
        model.parent.mkdir(exist_ok=True)
        with model.open('xb') as f:
            f.write(payload)
    import cv2
    import mediapipe as mp
    import numpy as np
    from extract_keypoints import points

    def xy(pts, w, h):
        return np.array([(v['x'] * w, v['y'] * h) for v in pts])

    options = mp.tasks.vision.HandLandmarkerOptions(
        base_options=mp.tasks.BaseOptions(model_asset_path=str(model.resolve())),
        running_mode=mp.tasks.vision.RunningMode.IMAGE, num_hands=2,
        min_hand_detection_confidence=.5, min_hand_presence_confidence=.6)
    cap = cv2.VideoCapture(str(args.video.resolve()))
    if not cap.isOpened():
        raise ValueError('Cannot open video')
    counts = Counter()
    try:
        with mp.tasks.vision.HandLandmarker.create_from_options(options) as detector:
            for row in data['frames']:
                ok, bgr = cap.read()
                if not ok:
                    raise ValueError('Video frame count differs from input JSON')
                h, w = bgr.shape[:2]
                if (w, h) != (data['width'], data['height']):
                    raise ValueError('Video dimensions differ from input JSON')
                row['hand_quality'] = {}
                for group, (wi, ei, oi) in SIDES.items():
                    baseline = copy.deepcopy(row[group])
                    audit = {'source': 'holistic' if baseline else 'missing',
                             'identity': 'unverified', 'crop_candidates': 0}
                    row['hand_quality'][group] = audit
                    pose = row['pose']
                    if not pose or (pose[wi].get('visibility') or 0) < .5:
                        audit['reason'] = 'pose_wrist_not_visible'
                        counts[group + ':' + audit['source']] += 1
                        continue
                    anchors = xy([pose[wi], pose[oi]], w, h)
                    forearm = float(np.linalg.norm(anchors[0] - xy([pose[ei]], w, h)[0]))

                    def association(hand):
                        # Never assign by screen x or the hand model's selfie label.
                        return wrist_association(xy(hand,w,h)[0],anchors[0],anchors[1],forearm)

                    if baseline and association(baseline):
                        audit['identity'] = 'pose_wrist_confirmed'
                    elif baseline:
                        audit['reason'] = 'ambiguous_or_conflicting_wrist'
                    if baseline:
                        b = xy(baseline, w, h)
                        center = (b.min(axis=0) + b.max(axis=0)) / 2
                        extent = max(float(np.ptp(b, axis=0).max()), forearm * .5, 24.)
                    else:
                        center = anchors[0] + (anchors[0] - xy([pose[ei]], w, h)[0]) * .25
                        extent = max(forearm * .9, 32.)
                    candidates = []
                    for scale in (1.7, 2.4):
                        size = int(round(extent * scale))
                        x0, y0 = (int(round(v - size / 2)) for v in center)
                        # Square padding preserves x/y metric and does not reflect pixels.
                        crop = np.zeros((size, size, 3), dtype=np.uint8)
                        xa, ya, xb, yb = max(0, x0), max(0, y0), min(w, x0+size), min(h, y0+size)
                        if xb <= xa or yb <= ya:
                            continue
                        crop[ya-y0:yb-y0, xa-x0:xb-x0] = bgr[ya:yb, xa:xb]
                        result = detector.detect(mp.Image(image_format=mp.ImageFormat.SRGB,
                            data=cv2.cvtColor(cv2.resize(crop, (512, 512)), cv2.COLOR_BGR2RGB)))
                        for image_hand, world_hand, labels in zip(result.hand_landmarks, result.hand_world_landmarks, result.handedness):
                            hand = points(image_hand)
                            for v in hand:
                                v['x'], v['y'], v['z'] = (x0+v['x']*size)/w, (y0+v['y']*size)/h, v['z']*size/w
                            if not association(hand):
                                continue
                            # World coordinates already have camera orientation: crops are not rotated.
                            world = points(world_hand)
                            candidates.append({'hand': hand, 'world': world, 'scale': scale,
                                'classifier_label': labels[0].category_name,
                                'classifier_score': labels[0].score})
                    audit['crop_candidates'] = len(candidates)
                    pairs = []
                    def world_shape(candidate):
                        v = np.array([[p[k] for k in ('x','y','z')] for p in candidate['world']])
                        normal = np.cross(v[5]-v[17], v[9]-v[0])
                        normal /= max(np.linalg.norm(normal), 1e-9)
                        segments = np.array([v[i+1]-v[i] for start in (1,5,9,13,17) for i in range(start,start+3)])
                        segments /= np.maximum(np.linalg.norm(segments,axis=1,keepdims=True),1e-9)
                        return normal, segments
                    for a in candidates:
                        for b in candidates:
                            if a['scale'] >= b['scale']:
                                continue
                            error = float(np.linalg.norm(xy(a['hand'], w, h)-xy(b['hand'], w, h), axis=1).mean()) / extent
                            na, sa = world_shape(a)
                            nb, sb = world_shape(b)
                            depth_agreement = float(np.mean(np.sum(sa*sb, axis=1)))
                            if error < .12 and float(na@nb) > .8 and depth_agreement > .85:
                                pairs.append((error, a, b))
                    if pairs:
                        error, a, b = min(pairs, key=lambda v: v[0])
                        # Handedness score is NOT landmark confidence. Prefer the tighter crop.
                        chosen = a
                        row[group], row[group+'_world'] = chosen['hand'], chosen['world']
                        audit.update(source='crop_consensus', identity='pose_wrist_confirmed',
                                     agreement_error=error, classifier_label=chosen['classifier_label'],
                                     classifier_score=chosen['classifier_score'])
                        audit.pop('reason', None)
                    counts[group + ':' + audit['source']] += 1
                if row['frame'] % 30 == 0:
                    print(f"Refined {row['frame']+1} frames", flush=True)
            if cap.read()[0]:
                raise ValueError('Video has more frames than input JSON')
    finally:
        cap.release()
    data['hand_refinement'] = {'method': 'two_scale_unmirrored_2d_3d_consensus_v2',
        'model_sha256': hashlib.sha256(model.read_bytes()).hexdigest(),
        'source_json': args.input.name, 'input_sha256': hashlib.sha256(args.input.read_bytes()).hexdigest(),
        'video_sha256': hashlib.sha256(args.video.read_bytes()).hexdigest(),
        'counts': dict(counts), 'interpolation': 'none',
        'identity_rule': 'anatomical pose wrist distance with ambiguity rejection; no x sorting or label swaps'}
    data['detected_frames'] = {g: sum(bool(f[g]) for f in data['frames']) for g in ('pose', *SIDES)}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(data, ensure_ascii=False, allow_nan=False, separators=(',', ':'))
    with args.output.open('x', encoding='utf-8') as f:
        f.write(payload)
    print(json.dumps({'output': str(args.output), 'counts': dict(counts)}, ensure_ascii=True), flush=True)


if __name__ == '__main__':
    main()
