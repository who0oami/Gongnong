# Architecture

Reference doc for this pipeline's structure, script-by-script. Also read by
Claude Code (claude.ai/code) as project context when working in this
repository.

## What this directory is

`sign-keypoint-to-avatar/` (formerly `word2153/`) is an experimental R&D track inside the `ksl-tube` monorepo (KSL = Korean
Sign Language). It is a from-video-to-VRM-avatar retargeting pipeline: extract 2D/3D
hand and body keypoints from a signer's video, clean/stabilize them, and drive a VRM
avatar's bone rotations and face shape keys in Blender (or live in a browser via
Babylon.js) so the avatar reproduces the sign.

It is **not wired into** the sibling `backend/` (FastAPI) or `frontend/` dirs one level
up — those cover an unrelated YouTube-transcript `/translate` endpoint and a separate,
simpler OpenPose-keypoint Babylon.js demo (`frontend/babylon-keypoint-test/`). Treat
`sign-keypoint-to-avatar/` as a standalone pipeline unless a task explicitly says otherwise.

There is no build system, linter, or test runner (no package.json/pytest.ini). The
closest things to tests are `scripts/check_hand_identity.py` (pure-Python assertions)
and `scripts/verify_mediapipe_preview.py` (Playwright browser check) — see Commands.

## Commands

All commands run from this directory (`sign-keypoint-to-avatar/`) unless noted. PowerShell is assumed.

**Extract keypoints from a video (MediaPipe Holistic):**
```powershell
python -m pip install -r extractor/requirements.txt
python extractor/extract_keypoints.py "<path-to-video>.mp4" --output keypoints/<id>.json --sign-id <id> --label <한글 라벨> --download-model
```
- Refuses to run if the output path already exists — never overwrite an existing
  extraction, use a new filename instead.
- `--download-model` fetches the official MediaPipe model once; later runs reuse the
  local copy. Add `--include-face` for face points/blendshapes.
- One video = one signer; no automatic mirroring.

**Full extract → hand-refine → Blender pipeline for one clip:**
```powershell
python scripts/run_hands_pipeline.py "<path-to-video>.mp4" --sign-id <id> --label <라벨> [--profile mediapipe-preview/blender_natural_profile.json] [--blender "C:/Program Files/Blender Foundation/Blender 5.2/blender.exe"]
```
Writes a new `output/<sign-id>_hands_<timestamp>/` folder — never reuses/overwrites one.

**Run a Blender retargeting script directly (headless):**
```powershell
& "C:\Program Files\Blender Foundation\Blender 5.2\blender.exe" --background --factory-startup --python-exit-code 1 --python scripts/mediapipe_to_blender_natural.py -- --motion keypoints/<id>_hands_v3.json --output output/<new_name>.blend --render
```
`scripts/refine_hand_contact_stable.py` instead opens an existing `.blend` as its
starting scene (`blender --background output/<existing>.blend --python scripts/refine_hand_contact_stable.py -- --output output/<new>.blend`). All Blender scripts refuse to
run if `--output` already exists.

**Legacy/parallel WORD2153 path** (fixed sample data in `sample/`, not per-video):
```powershell
"C:\Program Files\Blender Foundation\Blender 5.2\blender.exe" --python scripts/open_word2153_test.py   # reads retarget_config.json
scripts\run_motion.cmd <motion-json-file>
```
or run `scripts/word2153_retarget_v2.py` then `scripts/word2153_face_retarget.py` via
`scripts/run_word2153.py` (logs to `scripts/blender_run.log`).

**Browser preview (no Blender needed — Babylon.js + GLB/VRM in-browser):**
```powershell
scripts\run_mediapipe_preview.cmd          # or: python scripts/open_mediapipe_preview.py
```
Serves this whole workspace on loopback and opens `mediapipe-preview/index.html`.
Requires internet on first load (Babylon.js + loader come from the official CDN).

**Regression / verification checks:**
```powershell
python scripts/check_hand_identity.py          # 6 pure-Python anatomical L/R assertions, no video/Blender needed
python scripts/verify_mediapipe_preview.py     # Playwright + local Edge; screenshots into diagnostics/mediapipe-love-v1/<timestamp>/
```

**Hand-shape prior / denoiser (optional ML side path, needs PyTorch):**
```powershell
python extractor/build_hand_shape_prior.py --dataset "<path-to-SYN-3d-dataset>" --output extractor/hand_shape_prior.npz
# train in colab/train_hand_motion_denoiser.py (Google Colab), then locally:
python extractor/run_hand_motion_denoiser.py --motion keypoints/<id>_hands_stable_v1_smoothed.json --checkpoint hand_motion_denoiser.pt --output keypoints/<id>_denoised_angles.json
python scripts/apply_denoiser_correction.py --input output/<retargeted>.blend --output output/<new>.blend --corrections keypoints/<id>_denoised_angles.json --side L
```

## Architecture: the pipeline, stage by stage

Everything is keyed by a `--sign-id` (e.g. `love`, `leave`) and versioned by filename
suffix (`_v1`, `_v2`, `_stable_v3`, ...) — nothing is edited/overwritten in place, and
outputs from every stage are kept side by side so a comparison document
(`diagnostics/<name>/<timestamp>/comparison.html` or `playback.html`) can reference
both. Follow this convention for new work: new filename, never mutate an existing
result.

1. **`extractor/extract_keypoints.py`** — video → MediaPipe Holistic → per-frame JSON
   in `keypoints/`. Records `pose`/`left_hand`/`right_hand` (normalized 2D) plus
   `*_world` (independent-origin 3D meter estimates); undetected points are left empty,
   not interpolated.
2. **`extractor/refine_hands.py`** — second-pass hand re-detection on square crops
   around each wrist at two crop sizes, replacing the Holistic hand estimate only when
   both crop sizes agree in 2D and 3D palm/finger direction. Left/right identity is
   decided anatomically (`wrist_association`, keyed to the *pose* wrist/elbow, not
   image x-position or the hand model's own L/R classifier score) — this is the
   invariant `scripts/check_hand_identity.py` regression-tests.
3. **`scripts/prepare_stable_hands.py`** — per frame, independently picks between the
   Holistic landmark and the crop-refined re-detection (`extractor/refine_hands.py`)
   for orientation vs. finger shape.
4. **`extractor/smooth_hand_landmarks.py`** — One-Euro filter over the picked
   landmarks, because the source flips frame-to-frame (documented: 46/57 frames flip
   source on one real clip), which reads as trembling if left unfiltered before the
   Blender-side rotation smoothing runs.
5. **`scripts/mediapipe_to_blender*.py`** (`.py`, `_natural.py`, `_aligned.py`,
   `_stable.py` — kept as parallel iterations, not superseding each other in git) —
   fresh VRM/GLB import into Blender, anatomically assigns MediaPipe hands to bones,
   builds per-bone rest-relative rotations, and bakes an animation into a new
   `output/*.blend` plus a JSON audit. Per-model calibration (rest arm angle, bend/gain
   limits, palm-normal sign) lives in `mediapipe-preview/blender_*_profile.json`, never
   in per-word code changes.
6. **`scripts/refine_hand_contact_stable.py`** — opens an already-retargeted `.blend`,
   applies a symmetric temporal filter to arm/hand rotation, and resolves two-hand mesh
   interpenetration via two-joint IK on the shoulder/elbow (never by translating the
   wrist, which would stretch the arm).
7. **`extractor/build_hand_shape_prior.py`** + **`colab/train_hand_motion_denoiser.py`**
   + **`extractor/run_hand_motion_denoiser.py`** + **`scripts/apply_denoiser_correction.py`**
   — optional ML side path: build a statistical prior of plausible per-joint bend
   angles from the triangulated multi-view SYN dataset, train a sequence denoiser
   against it, run it on a real clip's noisy hand-bend angles, and re-apply the
   corrected angles onto an existing retargeted `.blend` (keeps rotation axis, replaces
   only the bend magnitude).
8. **Legacy/parallel path** — `scripts/export_vroid_rig_info.py` /
   `export_vroid_face_info.py` dump a VRM's bone/shape-key structure to
   `sample/vroid_rig_info.json` / `vroid_face_info.json`; `scripts/word2153_retarget_v2.py`
   / `word2153_face_retarget.py` (invoked together via `run_word2153.py`) retarget the
   fixed `sample/WORD2153_3d_approx.json` motion (5-viewpoint-triangulated 3D) onto
   those bones/shape keys directly, driven by `retarget_config.json` /
   `retarget_profile.json`. This predates the per-video pipeline above and uses its own
   config format.
9. **`mediapipe-preview/`** (`index.html` + `app.js`, Babylon.js from CDN) — browser
   equivalent of steps 1–5 without Blender: overlays a `keypoints/*.json` clip on its
   source video and retargets live onto a GLB/VRM avatar using the same
   `blender_*_profile.json` rest-pose calibration.

## Conventions worth preserving

- **Anatomical, not positional, left/right.** Left/right hand identity always traces
  back to the pose-model's wrist/elbow association, never to on-screen x-position or a
  hand-only detector's own L/R confidence score. Crossed arms and occluded/overlapping
  wrists must stay ambiguous (rejected) rather than get silently swapped.
- **No per-word numeric tuning in code.** Calibration (rest bone angle, bend/spread
  limits, gain, palm-normal sign) lives in model-specific profile JSON
  (`mediapipe-preview/blender_*_profile.json`, `retarget_profile.json`), so the same
  code runs unchanged across every sign. Don't add per-sign-id special-casing to a
  pipeline script.
- **Missing detections hold briefly, then fall back — never long-interpolate.** A gap
  in tracking holds the last known rotation for at most ~2 frames, then returns to the
  rest pose; long occlusions are not papered over with interpolation.
- **Never overwrite a result.** Every script that produces a `.blend`/JSON output
  refuses to run if the target path already exists; pick a new version suffix instead
  of forcing/deleting.
- **Document experiments like the existing `*.md` files do.** `BLENDER_HANDS.md`,
  `HAND_CONTACT.md`, `NATURAL_HANDS.md`, `NEW_TEST_CODE_REVIEW.md` each record the exact
  repro command, what was actually verified (specific frames/files/diagnostics paths),
  and explicit non-claims (e.g. "detection count did not increase," "this is not a
  sign-language-accuracy guarantee"). Follow the same rigor for new experiments —
  state only what was checked, and call out what wasn't.
- **Hardcoded local paths appear throughout** (e.g. Blender at
  `C:\Program Files\Blender Foundation\Blender 5.2\blender.exe`, test videos under
  `C:\Users\ESTsoft\Desktop\TEST\`, dataset paths under `D:\...`). Most scripts expose
  `--blender`/similar flags to override; dataset paths referenced only in docs may not
  exist in every environment.
- **Large binaries are gitignored per-folder**, not committed: videos (`*.mp4`),
  `.blend`/`.blend1`, downloaded MediaPipe models, and VRM/GLB avatar copies
  (`extractor/.gitignore`, `mediapipe-preview/.gitignore`, `diagnostics/.gitignore`).
  Place them locally per each folder's README/docs instead of adding them to git.

