---
name: animateur
description: Work with the Animateur/Animator static browser 3D animation toolset. Use when an agent needs to run, inspect, modify, test, or explain Fast Poser (`Index.html`), Motion Ripper (`ripper.html`), Playground (`Playground.html`), Auto Rig Scene (`AutoRigScene.html`), bundled `Animations/*.animation.json` assets, shared browser libraries, animation/pose JSON interchange, MediaPipe capture, Three.js scenes, or GLB auto-rig export behavior.
---

# Animateur

## Start Here

Read `README.md` for complete user-facing workflows, then identify which page owns the requested behavior:

- `Index.html`: Fast Poser, the main manual posing, scene staging, timeline, pose library, and animation library editor.
- `ripper.html`: Motion Ripper, the screen-share and MediaPipe pose-capture tool that saves Fast Poser-compatible animation JSON.
- `Playground.html`: runtime arena for testing bundled/imported clips, player actions, NPC interactions, and summon effects.
- `AutoRigScene.html`: auto-rig preview/export tool that turns compatible animation JSON plus generated cubes or imported meshes into skinned GLB exports.
- `Animations/`: bundled `.animation.json` samples used by Playground, Auto Rig Scene, and manual imports.
- `3D models/`: local model assets exposed by Auto Rig Scene.

This repo is a no-build static site. There is no backend, package install, or bundler. The browser app remains static, but the rig compiler now has stdlib Python `unittest` coverage.

## Run The App

Serve the repository root through a local static server so fetches, CDN imports, screen sharing, and same-origin `localStorage` work correctly.

Useful commands:

```powershell
python -m http.server 8000
```

Open the exact page names:

- `http://localhost:8000/Index.html`
- `http://localhost:8000/ripper.html`
- `http://localhost:8000/Playground.html`
- `http://localhost:8000/AutoRigScene.html`

Use the same browser and origin when testing shared libraries. Fast Poser uses `fast-poser:pose-library` and `fast-poser:animation-library`; Motion Ripper and Auto Rig Scene read/write the animation library key.

## Technical Shape

Keep changes sympathetic to the existing structure:

- Use inline HTML, CSS, and JavaScript modules inside the owning `.html` file.
- Use existing Three.js patterns and import maps instead of adding a build system.
- Preserve CDN dependencies unless the task explicitly asks for dependency changes.
- Keep UI copy and controls consistent with each page's current style.
- Avoid large cross-page rewrites unless the shared asset contract or user request requires it.

Rig data now has a compiled source of truth:

- `animateur_rig/`: stdlib-only Python package that authors, validates, and compiles rig data.
- `generated/rig-spec.mjs`: checked-in generated ESM artifact consumed by browser and Node code. Do not hand-edit it.
- `lib/rig-runtime.mjs`: handwritten shared runtime helpers for joint naming, default poses, character-count inference, and clip normalization.

Primary external dependencies:

- Three.js `0.160.0` through jsDelivr import maps.
- Tailwind CDN in Motion Ripper.
- MediaPipe Tasks Vision Pose Landmarker in Motion Ripper.
- Browser `localStorage`, file APIs, blob downloads, WebGL, screen capture, and canvas.
- For standalone Python rotation math, prefer `scipy.spatial.transform.Rotation` for composition, inversion, and vector rotation. It uses scalar-last `(x, y, z, w)` quaternions, which match Animateur assets; do not add new local `q_mul` / `q_rotate` helpers.

## Rig Compiler API

Use the rig compiler when a task touches authored rig layout, default transforms, preview pose defaults, Auto Rig segment metadata, or shared normalization behavior.

Authored source:

- `r11_core` is the only hand-authored editor/runtime rig source.
- `autorig_r18` is derived from the same authored source and keeps the current Auto Rig topology and extras.
- `neutral_bind` is the fallback/default normalization pose.
- `relaxed_preview` is viewport-only and must not replace `neutral_bind` in exported assets.

CLI entrypoint:

- `python3 -m animateur_rig compile`
  Writes checked-in generated artifacts such as `generated/rig-spec.mjs`.
- `python3 -m animateur_rig compile --check`
  Exits non-zero when generated artifacts are stale.

Public Python module surface from `animateur_rig`:

- Canonical authoring flow: `new_pose()` / `new_animation()` produce `PoseAsset` / `AnimationAsset`, `Pose` authors joint transforms, `Keyframe` represents timeline entries, and `ArcaneSummonEffect` is the typed effect payload.
- Core authoring helpers: `get_joint_name()`, `build_default_pose()`, `infer_character_count()`, `normalize_pose()`, `normalize_keyframes()`
- Asset/constants surface: `FAST_POSER_ASSET_FORMAT`, `FAST_POSER_ASSET_VERSION`, `POSE_ASSET_TYPE`, `ANIMATION_ASSET_TYPE`
- Rig identifiers remain available when you need to select a rig explicitly: `R11_CORE_ID`, `AUTORIG_R18_ID`, `NEUTRAL_BIND_ID`, `RELAXED_PREVIEW_ID`
- Compiler internals still exist for rig-source changes, but they are secondary to asset authoring: `python3 -m animateur_rig compile`, `build_authored_spec()`, `compile_repo()`, `validate_spec()`
- Package-local docs: `animateur_rig/AGENTS.md` for maintainers and `animateur_rig/API_CHEATSHEET.md` for consumers of the authoring API
- Machine-readable JSON Schema: `animateur_rig/fast-poser-asset.schema.json`

Generated ESM surface from `generated/rig-spec.mjs`:

- `R11_CORE`
- `AUTORIG_R18`
- `AUTORIG_UAL_HINTS`
- `NEUTRAL_BIND_POSE`
- `RELAXED_PREVIEW_POSE`
- `AUTORIG_SEGMENTS`
- `AUTORIG_AUTO_SKIN_SEGMENTS`

Shared JS runtime surface from `lib/rig-runtime.mjs`:

- `R11_CORE`
- `AUTORIG_R18`
- `AUTORIG_UAL_HINTS`
- `AUTORIG_SEGMENTS`
- `AUTORIG_AUTO_SKIN_SEGMENTS`
- `NEUTRAL_BIND_POSE`
- `RELAXED_PREVIEW_POSE`
- `getJointNames(rig)`
- `getJointParents(rig)`
- `getJointName(baseName, characterIndex)`
- `buildDefaultPose(characterCount, rig, preset = 'neutral_bind')`
- `inferCharacterCount(assetOrPose)`
- `normalizePose(serializedPose, { rig, characterCount, fallbackPose })`
- `normalizeKeyframes(keyframes, { rig, characterCount })`

Legacy compatibility surface:

- none. Canonical callers should use `normalizePose()` and `normalizeKeyframes()` from `lib/rig-runtime.mjs`.

Consumer expectations:

- `Index.html`, `Playground.html`, and `ripper.html` consume `r11_core` and use `relaxed_preview` only for viewport construction/default standing pose.
- `AutoRigScene.html` consumes `autorig_r18`, `AUTORIG_UAL_HINTS`, compiled segment layout data, and compiled auto-skin segment data.
- `scripts/convert-ual1-standard.mjs` imports compiled `autorig_r18` metadata and named UAL hints instead of hand-authored rig constants or a consumerExtras bag.
- When changing authored rig data, re-run the compiler and keep generated artifacts committed.

Programmatic authoring example:

```python
from animateur_rig import ArcaneSummonEffect, Pose, new_animation

clip = new_animation("wave", rig="r11_core", character_count=1)

start = Pose(rig_id="r11_core", character_count=1)
start.set_rotation("Left_Upper_Arm", axis=(0, 0, 1), angle_radians=0.2)
clip.add_keyframe(0.0, start)

end = Pose(rig_id="r11_core", character_count=1)
end.set_rotation("Left_Upper_Arm", axis=(0, 0, 1), angle_radians=0.7)
clip.transition(end, 0.4)
clip.hold(0.3)
clip.effects = ArcaneSummonEffect(target_character=0, start_time=0.0, peak_time=0.8, end_time=1.6)

animation_json = clip.to_json()
```

## Asset Contract

Preserve the shared JSON contract. Compatible assets use:

```json
{
  "format": "fast-poser-asset",
  "version": 1,
  "type": "animation"
}
```

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

Joint names follow `<JointName>_<CharacterIndex>`, such as `Hips_0`, `Spine_0`, `Left_Upper_Arm_0`, or `Right_Lower_Leg_1`. This suffix is how multi-character clips work.

Optional effect metadata is currently runtime-playable but not fully authorable in the UI. The known preset is `arcane-summon` with fields such as `targetCharacter`, `startTime`, `peakTime`, `endTime`, `radius`, `columnHeight`, and effect colors.

## Common Changes

When changing Fast Poser:

- Preserve `ASSET_FORMAT`, `ASSET_VERSION`, and `STORAGE_KEYS`.
- Keep animation interpolation compatible with existing keyframes.
- When adding new serialized fields, normalize missing values so old bundled assets still load.
- Confirm exported pose/animation JSON can be imported back into Fast Poser.

When changing Motion Ripper:

- Preserve output compatibility with Fast Poser animation assets.
- Keep MediaPipe failure states clear; offline use can fail because MediaPipe assets are network-loaded.
- Maintain root motion, smoothing, sample-rate, and color behavior unless the user asks to change capture semantics.

When changing Playground:

- Keep `ASSET_MANIFEST` aligned with files in `Animations/`.
- If adding a new action group, update grouping, trigger behavior, and motion scaling together.
- Verify single-character actions, two-character interactions, and summon effects still load.

When changing Auto Rig Scene:

- Keep bundled animation catalog entries aligned with `Animations/`.
- Keep `LOCAL_MODELS` aligned with files under `3D models/`.
- Preserve tolerant asset normalization; imported clips may omit poses for some joints or omit explicit character counts.
- Remember that non-skeletal `effects` metadata is preview/runtime data and is skipped for GLB export.

When adding or editing bundled animations:

- Keep filenames ending in `.animation.json`.
- Use the shared asset contract.
- Update `README.md` sample lists when samples change.
- Update `Playground.html` manifest/grouping and `AutoRigScene.html` bundled catalog when samples should auto-load.

## Validation

For rig/compiler changes, run:

- `python3 -m unittest tests.test_animateur_rig`
- `python3 -m animateur_rig compile --check`

Then validate in the browser according to the touched surface:

- Fast Poser: load `Index.html`, add/select a character, record keyframes, play, save/export/import an animation, and check the timeline.
- Motion Ripper: load `ripper.html`, confirm MediaPipe initializes or shows a useful error, and verify captured/exported JSON imports into Fast Poser.
- Playground: load `Playground.html`, confirm bundled assets fetch, move with `WASD`, trigger `Space`, `H`, and `E`, and check console errors.
- Auto Rig Scene: load `AutoRigScene.html`, build a bundled clip, scrub/play it, toggle mesh/rig helpers, import a JSON clip if relevant, and test GLB export when export code changed.

For visual or interaction changes, use a real browser when possible. Check the JavaScript console because most regressions in this repo appear as runtime errors rather than build failures.

## Boundaries

Do not introduce a backend, package manager, build step, framework migration, or persistent project-file format unless the user explicitly asks. Prefer small, page-local edits that preserve the shared JSON format and keep all four tools interoperable.
