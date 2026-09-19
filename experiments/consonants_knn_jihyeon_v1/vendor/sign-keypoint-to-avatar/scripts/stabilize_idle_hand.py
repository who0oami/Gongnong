"""Freeze a word's idle (non-signing) hand into a fixed natural relaxed curl.

Background / root cause
------------------------
Some legacy-retargeted words (built by running C:/New_test/retarget_avatar_real_v2.py
unchanged against a *_3d_approx.json motion) show a hand whose fingers look
bent/splayed in an unnatural way, e.g. WORD2551 on both Model_M3 and
AvatarSample_F10 (see diagnostics/WORD2551_F10_legacy_reference_v4 and
diagnostics/WORD2551_M3_legacy_compare_v1 - the SAME artifact reproduces
identically on both models, proving it is not caused by switching avatars).

Investigation showed:
- The finger-basis math in retarget_avatar_real_v2.py (make_semantic_basis /
  make_desired_rotation) never hits its own degenerate-hint fallback for this
  data (checked: every finger's angle to the palm-normal hint stays > 25 deg),
  so it is not a bug in that math either.
- WORD2551's json has "source": "real_precomputed_3d_f_view",
  "triangulation_performed": false - for REAL (recorded, not synthetic) words,
  make_real_words_3d.py passes through the AI-Hub dataset's own front-view 3D
  hand keypoints as-is. That per-joint 3D is good enough for the actively
  signing hand (large, unambiguous motion) but for the hand that just rests
  at the hip for the whole clip, small/ambiguous real depth differences
  between fingers become an implausible pose once retargeted onto a 3D
  avatar and rotated/lit - an artifact invisible in the flat source video.

Fix
---
For the hand identified as idle (near-zero wrist displacement across the
whole clip), hold its fingers in one fixed relaxed curl for every frame,
expressed as a small rotation around each finger bone's own LOCAL X axis
(relative to its bind pose) - not a world-space "desired direction", since
the wrist itself is already correctly rotated by the legacy retarget and a
world-space target re-derived from the model's T-pose rest frame ignores
that and produces a claw/hyperextension mess (see the first, discarded
attempt in this file's git history / diagnostics/WORD2551_F10_idle_hand_fix_v1).
Local-axis rotation is rig-agnostic (works for any VRM humanoid skeleton)
and was verified empirically on both WORD2551 and (spot-checked) other
resting-hand cases.

Usage: edit SRC / MOTION / OUT below and run with Blender:
  blender --background --python scripts/stabilize_idle_hand.py
"""
import json
import math
from pathlib import Path

import bpy
from mathutils import Quaternion, Vector

ROOT = Path(__file__).resolve().parents[1]

# ---- edit these three for a new word/model -----------------------------
SRC = ROOT / "output/WORD2551_F10_legacy_reference_v4.blend"
MOTION = Path("C:/Users/ESTsoft/Downloads/WORD2551_3d_approx.json")
OUT = ROOT / "output/WORD2551_F10_idle_hand_fix_v2.blend"
# --------------------------------------------------------------------------

DIAG = ROOT / f"diagnostics/{OUT.stem}"

# how idle a hand's wrist path must be (relative to the other hand) to be
# treated as "resting" and have its fingers frozen
IDLE_RATIO_THRESHOLD = 0.3

# relaxed-curl angles in degrees, per joint (proximal, middle, distal)
FINGER_CURL_DEG = {
    "Thumb": (10, 15, 10),
    "Index": (20, 35, 20),
    "Middle": (20, 35, 20),
    "Ring": (22, 38, 20),
    "Little": (24, 40, 20),
}

# bend axis/sign in each finger bone's own local space - verified on the
# F10 rig; VRM humanoid rigs share this bone-axis convention (Y = head->tail)
# so this should transfer, but re-check visually on a new rig family.
BEND_AXIS = Vector((1, 0, 0))
BEND_SIGN = 1.0


def wrist_path_length(frames, side_key):
    pts = [fr[side_key][0] for fr in frames if fr.get(side_key)]
    if len(pts) < 2:
        return 0.0
    return sum(math.dist(a, b) for a, b in zip(pts, pts[1:]))


def main():
    if OUT.exists() or DIAG.exists():
        raise FileExistsError(OUT)
    DIAG.mkdir(parents=True)

    data = json.loads(MOTION.read_text(encoding="utf-8"))
    frames = data["frames"]

    paths = {
        "L": wrist_path_length(frames, "left_hand"),
        "R": wrist_path_length(frames, "right_hand"),
    }
    idle_side = min(paths, key=paths.get)
    active_side = "R" if idle_side == "L" else "L"
    print("wrist path length:", paths, "-> idle side:", idle_side)
    if paths[idle_side] >= paths[active_side] * IDLE_RATIO_THRESHOLD:
        raise RuntimeError(
            "No clearly idle hand found (both hands move) - "
            "this fix does not apply to this word, skipping."
        )

    bpy.ops.wm.open_mainfile(filepath=str(SRC))
    scene = bpy.context.scene
    arm = bpy.data.objects["Armature"]

    target_bones = []
    for finger, angles in FINGER_CURL_DEG.items():
        for n in (1, 2, 3):
            bone_name = f"J_Bip_{idle_side}_{finger}{n}"
            target_bones.append((bone_name, math.radians(angles[n - 1])))

    fixed_quats = {
        bone_name: Quaternion(BEND_AXIS, BEND_SIGN * angle)
        for bone_name, angle in target_bones
    }

    for f in range(scene.frame_start, scene.frame_end + 1):
        scene.frame_set(f)
        for bone_name, _ in target_bones:
            pose_bone = arm.pose.bones[bone_name]
            pose_bone.rotation_mode = "QUATERNION"
            pose_bone.rotation_quaternion = fixed_quats[bone_name]
            pose_bone.keyframe_insert(data_path="rotation_quaternion", frame=f)

    scene.frame_set(0)
    bpy.ops.file.pack_all()
    bpy.ops.wm.save_as_mainfile(filepath=str(OUT))

    scene.render.engine = "BLENDER_WORKBENCH"
    scene.render.resolution_x = 800
    scene.render.resolution_y = 800
    for f in (scene.frame_start, scene.frame_end):
        scene.frame_set(f)
        scene.render.filepath = str(DIAG / f"frame_{f:03d}.png")
        bpy.ops.render.render(write_still=True)

    (DIAG / "provenance.json").write_text(json.dumps({
        "source_blend": str(SRC),
        "motion": str(MOTION),
        "idle_side": idle_side,
        "wrist_path_length": paths,
    }, indent=2), encoding="utf-8")

    print("SAVED", OUT)


if __name__ == "__main__":
    main()

