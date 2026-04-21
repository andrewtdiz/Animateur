# animateur_rig API Cheat Sheet

Consumer-facing Python surface for authoring Fast Poser pose and animation assets.

## Preferred Imports

Use the canonical constructors and pose helpers:

```python
from animateur_rig import (
    Pose,
    new_animation,
    new_pose,
    normalize_keyframes,
    normalize_pose,
)
```

Use optional world-target arm posing from the separate IK module:

```python
from animateur_rig.ik import solve_arm_to_target, solve_mirrored_arms_to_targets
```

## Common Flow

```python
from animateur_rig import Pose, new_animation

clip = new_animation("wave", rig="r11_core", character_count=1)

pose = Pose.default(rig_id="r11_core", character_count=1)
pose.set_rotation("Left_Upper_Arm", axis=(0, 0, 1), angle_radians=0.2)
clip.add_keyframe(0.0, pose)

next_pose = Pose.default(rig_id="r11_core", character_count=1)
next_pose.set_rotation("Left_Upper_Arm", axis=(0, 0, 1), angle_radians=0.7)
clip.transition(next_pose, 0.4)
clip.hold(0.3)

animation_json = clip.to_json()
```

## IK Flow

Use IK when the authoring intent is world-space hand or forearm-tip placement such as clapping, praying, holding, or bracing.

```python
from animateur_rig import Pose
from animateur_rig.ik import solve_mirrored_arms_to_targets

pose = Pose.default(rig_id="r11_core", character_count=1)
solve_mirrored_arms_to_targets(
    pose,
    left_target=(0.10, 2.54, 0.34),
    right_target=(-0.10, 2.54, 0.34),
)

pose_json = pose.to_json()
```

## High-Value Surface

- `new_pose(...)`, `new_animation(...)`: canonical constructors for new assets.
- `Pose.default(...)`: full default pose for a rig and character count.
- `Pose.from_input(...)`: clone from a `Pose` or serialized mapping.
- `pose.set_rotation(...)`: write a local joint quaternion or axis-angle.
- `pose.set_position(...)`: write a local joint position. Usually only `Hips` should move.
- `clip.add_keyframe(...)`: add a keyed pose at a time.
- `clip.transition(...)`, `clip.hold(...)`: fast timeline authoring helpers.
- `pose.to_dict()`, `pose.to_json()`, `clip.to_dict()`, `clip.to_json()`: emit normalized asset data.
- `normalize_pose(...)`, `normalize_keyframes(...)`: canonical normalization helpers.

## IK Helper API

Both IK helpers mutate the provided `Pose` and return that same `Pose`.

```python
solve_arm_to_target(
    pose,
    side,
    target,
    *,
    character_index=0,
    pole=None,
    tip_offset=None,
    orient="maintain",
    target_orientation=None,
) -> Pose

solve_mirrored_arms_to_targets(
    pose,
    left_target,
    right_target,
    *,
    character_index=0,
    left_pole=None,
    right_pole=None,
    left_tip_offset=None,
    right_tip_offset=None,
    orient="maintain",
    left_target_orientation=None,
    right_target_orientation=None,
) -> Pose
```

Parameters:

- `target`: world-space end-effector target position.
- `pole`: optional world-space bend-direction point.
- `tip_offset`: optional local-space offset from the solved end joint to the desired contact point.
- `orient`: `"maintain"` or `"target"`.
- `target_orientation`: world-space quaternion used with `orient="target"`.

Rig behavior:

- `r11_core`: solves `Upper_Arm -> Lower_Arm` and targets a virtual lower-arm tip.
- `r11_core`: supports position solving only. Keep `orient="maintain"` and do not pass `target_orientation`.
- `r11_core`: `tip_offset` replaces the default virtual tip if needed.
- `autorig_r18`: solves `Upper_Arm -> Lower_Arm -> Hand` and targets the `Hand` joint origin by default.
- `autorig_r18`: `orient="maintain"` preserves the current hand local rotation.
- `autorig_r18`: `orient="target"` requires `target_orientation`.
- `autorig_r18`: `tip_offset` is only supported with `orient="target"` and is interpreted in hand-local space.
- `autorig_r18`: shoulder follow is written automatically as a visual companion to the solved arm.

## Authoring Rules

- Start from `Pose.default(...)` when building a full pose.
- Prefer `new_pose(...)` and `new_animation(...)` over hand-assembling raw dicts.
- Use `set_rotation(...)` for direct joint posing and polish.
- Use `animateur_rig.ik` for end-effector placement, not for serialization.
- Treat non-root joint `position` as a local bind offset, not a world-space control.
- Only move `Hips` for root motion unless you intentionally want to change local rig layout.
- Default to `r11_core` unless a pipeline explicitly needs another rig.
- `r11_core` has no shoulder or hand joints; arm IK targets a virtual forearm tip.

## JSON Contract

Compatible assets still use the existing Fast Poser shape:

```json
{
  "format": "fast-poser-asset",
  "version": 1,
  "type": "animation"
}
```

Joint transforms still serialize as:

```json
{
  "position": [0, 2.6, 0],
  "quaternion": [0, 0, 0, 1]
}
```

- Joint names use `<JointName>_<CharacterIndex>`, such as `Hips_0`.
- `position` is local to the parent joint.
- IK is SDK-only authoring help. No IK targets or solver metadata are serialized.

## Notes

- `normalize_pose()` and `normalize_keyframes()` are the canonical helper names.
- The machine-readable schema lives in `animateur_rig/fast-poser-asset.schema.json`.
- If a pose looks wrong, first check whether a child joint `position` was changed when a rotation was intended.
