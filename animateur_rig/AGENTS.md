# animateur_rig Maintainer Notes

This package is the Python source of truth for Fast Poser-style pose and animation assets.

## Scope

Treat `animateur_rig/__init__.py` as the public boundary. Anything not exported there is internal implementation detail unless a file explicitly says otherwise.
`animateur_rig/ik.py` is the explicit exception: it is an optional public authoring module for isolated pose math.

## File Map

- `authoring.py`: asset models, normalization, validation, and JSON emission.
- `ik.py`: optional public SDK-only IK authoring helpers that bake results back into `Pose`.
- `spec.py`: authored rig source and generated rig constants.
- `compiler.py`: validation and generated-module rendering.
- `model.py`: typed spec and transform data structures.
- `__main__.py`: CLI entry point.

## Maintain These Invariants

- Keep the shared asset contract stable: `format`, `version`, `type`, `scene`, `pose`, `keyframes`, and `effects`.
- Treat `fast-poser-asset.schema.json` as the machine-readable source of truth for that contract.
- Keep `new_pose()` / `new_animation()` as the canonical constructors.
- Keep `normalize_pose()` and `normalize_keyframes()` as the canonical normalization helpers.
- Keep `__init__.py` exports minimal and aligned with the consumer docs.
- Do not reintroduce pose-ops math into the core authoring API. Keep advanced pose math isolated in `ik.py` or another optional module.
- Keep `generated/rig-spec.mjs` committed and in sync with the authored spec.

## When Editing

- If you change serialized JSON shape, update tests and the consumer cheat sheet together.
- If you add or remove exports, update `__init__.py`, this file, and the cheat sheet together.
- If you change the optional IK API, update `ik.py`, this file, the cheat sheet, and SDK tests together.
- If you change authored rig data, rerun the compiler and keep generated output current.
- Prefer small, readable changes over compatibility wrappers unless there is a concrete call site that needs them.

## Validation

- `python3 -m unittest tests.test_animateur_rig`
- `python3 -m animateur_rig compile --check`
