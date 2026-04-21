---
name: animateur
description: Use Animateur, the local browser-based 3D posing and animation toolset at `C:\Users\canva\Desktop\Animateur`. Use when the user asks OpenClaw to open, run, inspect, edit, generate assets for, validate, or operate Animateur/Fast Poser, Motion Ripper, Playground, Auto Rig Scene, bundled animation JSON, pose JSON, localStorage animation libraries, Three.js scenes, MediaPipe capture, or GLB export workflows.
---

# Animateur

Before acting, verify the path exists. If neither path exists, ask the user for the Animateur folder path.

## What This Software Is

Animateur is a no-build static browser toolset for 3D humanoid posing, lightweight animation, motion capture from reference video, runtime preview, and simple rig export. It has four HTML entry points:

- `Index.html`: Fast Poser, the main manual pose, scene staging, timeline, pose library, and animation library editor.
- `ripper.html`: Motion Ripper, a screen-share and MediaPipe pose-capture tool that saves Fast Poser-compatible animation JSON.
- `Playground.html`: runtime arena for testing bundled/imported clips, player actions, NPC interactions, and summon effects.
- `AutoRigScene.html`: auto-rig preview/export tool that turns compatible animation JSON plus generated cubes or imported meshes into skinned GLB exports.

Important folders:

- `Animations/`: bundled `.animation.json` files consumed by Fast Poser imports, Playground, and Auto Rig Scene.
- `3D models/`: local model assets exposed by Auto Rig Scene.

There is no backend, package install, build step, or formal automated test suite.

## Running It

Serve the project root with any simple static server. Prefer an existing local tool; do not add a package manager or build system.

From PowerShell:

```powershell
cd C:\Users\canva\Desktop\Animateur
python -m http.server 8000
```

From WSL or bash:

```bash
cd /mnt/c/Users/canva/Desktop/Animateur
python3 -m http.server 8000
```

If Python is unavailable, use another installed static server such as `npx serve .` only if Node/npm is already available and the user is comfortable with network/package use.

Open these exact URLs from the same browser and origin:

- `http://localhost:8000/Index.html`
- `http://localhost:8000/ripper.html`
- `http://localhost:8000/Playground.html`
- `http://localhost:8000/AutoRigScene.html`

Use the exact uppercase `Index.html`. Shared pose and animation libraries live in browser `localStorage`, so changing port, protocol, host, or browser creates a separate library.

## Browser Operation Notes

Use browser tools when available to operate the UI. For file import/export tasks, prefer the app's own buttons unless the user asks for direct JSON editing.

Motion Ripper has human-in-the-loop limits:

- It needs browser screen sharing.
- It loads MediaPipe code/model assets from the internet.
- It tracks one clearly visible performer.
- The user may need to choose a screen/window in the browser permission prompt.

Do not claim Motion Ripper capture was validated unless tracking and recording actually ran.

## Shared Asset Format

Preserve the shared JSON contract. Compatible assets use:

```json
{
  "format": "fast-poser-asset",
  "version": 1,
  "type": "animation"
}
```

For the machine-readable reference, see `animateur_rig/fast-poser-asset.schema.json`.

Pose assets include:

- `name`
- `savedAt`
- `scene.characterCount`
- `scene.characterColors`
- `pose`

Animation assets include:

- `name`
- `savedAt`
- `scene.characterCount`
- `scene.characterColors`
- `playbackSpeed`
- `effects` or `null`
- `keyframes`

Each keyframe has `time` and `pose`. Joint entries use:

```json
{
  "position": [0, 2.6, 0],
  "quaternion": [0, 0, 0, 1]
}
```

Joint names follow `<JointName>_<CharacterIndex>`, such as `Hips_0`, `Spine_0`, `Left_Upper_Arm_0`, or `Right_Lower_Leg_1`. This suffix stores multi-character scenes in one asset.

Optional effect metadata is currently runtime-playable but not fully authorable in the UI. The known preset is `arcane-summon` with fields such as `targetCharacter`, `startTime`, `peakTime`, `endTime`, `radius`, `columnHeight`, and effect colors.

## Common Tasks

When asked to open or run Animateur:

1. Start or reuse a local static server rooted at the Animateur folder.
2. Open the relevant HTML page.
3. Keep all related pages on the same origin when using shared libraries.

When asked to create or edit an animation asset:

1. Prefer the Python authoring SDK in `animateur_rig` over hand-assembling raw dicts.
2. Use `new_pose()` / `new_animation()` plus `Pose`, `Keyframe`, and `ArcaneSummonEffect` when generating assets programmatically.
3. Let `Pose` helpers handle rig terms and character indices; do not manually construct `Hips_0`-style keys unless the task specifically needs raw JSON editing.
4. Serialize with `.to_dict()` or `.to_json()` so the top-level `format`, `version`, `type`, `scene`, `effects`, and `keyframes` contract stays correct.
5. Validate by importing into `Index.html`; if runtime behavior matters, also test `Playground.html` or `AutoRigScene.html`.

Programmatic example:

```python
from animateur_rig import Pose, new_animation

clip = new_animation("wave", rig="r11_core", character_count=1)
pose = Pose(rig_id="r11_core", character_count=1)
pose.set_rotation("Left_Upper_Arm", axis=(0, 0, 1), angle_radians=0.25)
clip.add_keyframe(0.0, pose)
clip.hold(0.2)

target = Pose(rig_id="r11_core", character_count=1)
target.set_rotation("Left_Upper_Arm", axis=(0, 0, 1), angle_radians=0.65)
clip.transition(target, 0.4)

animation_json = clip.to_json()
```

When changing Fast Poser (`Index.html`):

- Preserve `ASSET_FORMAT`, `ASSET_VERSION`, and storage keys.
- Keep existing animation interpolation compatible with old keyframes.
- Normalize missing serialized fields so older assets still load.
- Confirm exported pose/animation JSON can be imported again.

When changing Motion Ripper (`ripper.html`):

- Preserve output compatibility with Fast Poser animation assets.
- Keep MediaPipe loading/failure states clear.
- Preserve root motion, smoothing, sample-rate, and character color behavior unless the user asks to change capture semantics.

When changing Playground (`Playground.html`):

- Keep the animation manifest aligned with files in `Animations/`.
- If adding a new action group, update grouping, trigger behavior, and motion scaling together.
- Validate walk/action/summon/interaction paths as relevant.

When changing Auto Rig Scene (`AutoRigScene.html`):

- Keep bundled animation catalog entries aligned with `Animations/`.
- Keep local model entries aligned with `3D models/`.
- Preserve tolerant asset normalization because imported clips may omit some joints or explicit character counts.
- Remember that effect metadata is skipped for GLB export.

## Validation

There is no automated suite. Validate in the browser according to the touched surface:

- Fast Poser: load `Index.html`, add/select a character, record keyframes, play, save/export/import an animation, and inspect the timeline.
- Motion Ripper: load `ripper.html`, confirm MediaPipe initializes or gives a useful error, record only if the user can share a screen/window, then import exported JSON into Fast Poser.
- Playground: load `Playground.html`, confirm bundled assets fetch, move with `WASD`, trigger `Space`, `H`, and `E`, and check console errors.
- Auto Rig Scene: load `AutoRigScene.html`, build a bundled clip, scrub/play it, toggle mesh/rig helpers, import a JSON clip if relevant, and test GLB export if export code changed.

For visual or interaction changes, use a real browser and check the JavaScript console. Most regressions appear as runtime errors rather than build failures.

## Boundaries

Do not introduce a backend, framework migration, package install, build step, persistent project-file format, or cloud dependency unless the user explicitly asks. Prefer small, page-local edits that preserve the shared JSON format and keep all four tools interoperable.
- For standalone Python rotation math in scripts, prefer `scipy.spatial.transform.Rotation` for composition, inversion, and vector rotation. Keep quaternion values scalar-last `(x, y, z, w)`, and do not add local `q_mul`, `q_conj`, or `q_rotate` helpers unless you are intentionally building a reusable math module.
