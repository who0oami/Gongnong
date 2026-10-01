"""Video -> MediaPipe Holistic Tasks JSON. Never overwrites existing output."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parent
MODEL_URL = ('https://storage.googleapis.com/mediapipe-models/'
             'holistic_landmarker/holistic_landmarker/float16/latest/holistic_landmarker.task')


def points(values):
    return [{key: getattr(p, key, None) for key in
             ('x', 'y', 'z', 'visibility', 'presence')} for p in values or []]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('video', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--sign-id')
    parser.add_argument('--label', default='')
    parser.add_argument('--model', type=Path, default=ROOT / 'models/holistic_landmarker.task')
    parser.add_argument('--download-model', action='store_true')
    parser.add_argument('--include-face', action='store_true')
    args = parser.parse_args()
    if not args.video.is_file():
        parser.error(f'Video does not exist: {args.video}')
    if args.output.exists():
        parser.error(f'Output exists; choose a new name: {args.output}')
    if not args.model.is_file():
        if not args.download_model:
            parser.error('Model missing. Pass --download-model or --model PATH.')
        args.model.parent.mkdir(parents=True, exist_ok=True)
        print(f'Downloading model: {MODEL_URL}', flush=True)
        with urlopen(MODEL_URL, timeout=120) as response:
            model_bytes = response.read()
        with args.model.open('xb') as target:
            target.write(model_bytes)
    os.environ.setdefault('MPLCONFIGDIR', str(ROOT / '.mplconfig'))
    import cv2
    import mediapipe as mp

    cap = cv2.VideoCapture(str(args.video.resolve()))
    if not cap.isOpened():
        raise ValueError(f'Cannot decode video: {args.video}')
    frames = []
    counts = dict(pose=0, left_hand=0, right_hand=0)
    try:
        fps = float(cap.get(cv2.CAP_PROP_FPS))
        if not math.isfinite(fps) or fps <= 0:
            raise ValueError('Video has no valid FPS')
        width, height = (int(cap.get(prop)) for prop in
                         (cv2.CAP_PROP_FRAME_WIDTH, cv2.CAP_PROP_FRAME_HEIGHT))
        options = mp.tasks.vision.HolisticLandmarkerOptions(
            base_options=mp.tasks.BaseOptions(model_asset_path=str(args.model.resolve())),
            running_mode=mp.tasks.vision.RunningMode.VIDEO,
            output_face_blendshapes=args.include_face)
        last_ms = -1
        with mp.tasks.vision.HolisticLandmarker.create_from_options(options) as detector:
            while True:
                ok, bgr = cap.read()
                if not ok:
                    break
                index = len(frames)
                pts = float(cap.get(cv2.CAP_PROP_POS_MSEC))
                # Prefer decoded timestamps for variable-frame-rate videos.
                timestamp_ms = round(pts) if math.isfinite(pts) else -1
                if timestamp_ms <= last_ms:
                    timestamp_ms = max(last_ms + 1, round(index * 1000 / fps))
                last_ms = timestamp_ms
                result = detector.detect_for_video(mp.Image(
                    image_format=mp.ImageFormat.SRGB,
                    data=cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)), timestamp_ms)
                row = dict(frame=index, time=timestamp_ms / 1000, timestamp_ms=timestamp_ms)
                for group in counts:
                    row[group] = points(getattr(result, group + '_landmarks'))
                    row[group + '_world'] = points(getattr(result, group + '_world_landmarks'))
                    counts[group] += bool(row[group])
                if args.include_face:
                    row['face'] = points(result.face_landmarks)
                    row['face_blendshapes'] = {v.category_name: v.score
                                             for v in result.face_blendshapes or []}
                frames.append(row)
                if index % 30 == 0:
                    print(f'Processed {index + 1} frames', flush=True)
    finally:
        cap.release()
    if not frames:
        raise ValueError('No frames decoded; output was not created')
    output = dict(schema='mediapipe-holistic-v1', sign_id=args.sign_id or args.video.stem,
                  label=args.label, fps=fps, frame_count=len(frames), width=width, height=height,
                  source_video=args.video.name, mediapipe_version=mp.__version__,
                  model_sha256=hashlib.sha256(args.model.read_bytes()).hexdigest(),
                  coordinates={'image': 'x right, y down; normalized; z relative to each group',
                               'world': 'meters; pose and hands have separate origins',
                               'handedness': 'anatomical; input is not mirrored'},
                  detected_frames=counts, frames=frames)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    # Serialize before exclusive creation so serialization failures leave no output.
    payload = json.dumps(output, ensure_ascii=False, allow_nan=False, separators=(',', ':'))
    with args.output.open('x', encoding='utf-8') as target:
        target.write(payload)
    print(json.dumps({'output': str(args.output), 'frames': len(frames),
                      'fps': fps, 'detected_frames': counts}, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
