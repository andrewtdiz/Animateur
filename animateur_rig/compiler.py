from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Iterable

from .model import AuthoredRigSpec, JointSpec, RigSpec
from .spec import build_authored_spec


class RigSpecError(ValueError):
    pass


class StaleGeneratedArtifactError(RuntimeError):
    pass


REPO_ROOT = Path(__file__).resolve().parent.parent
GENERATED_SPEC_PATH = REPO_ROOT / "generated" / "rig-spec.mjs"


def _joint_names(rig: RigSpec) -> list[str]:
    return [joint.base_name for joint in rig.joints]


def _parents_by_name(rig: RigSpec) -> dict[str, str | None]:
    return {joint.base_name: joint.parent for joint in rig.joints}


def _preview_geometry(rig: RigSpec) -> dict[str, dict[str, object]]:
    return {
        name: {
            "size": list(hint.size),
            "pivotYOffset": hint.pivot_y_offset,
        }
        for name, hint in rig.preview_geometry.items()
    }


def _pose_export(preset_id: str, joints: dict[str, object]) -> dict[str, object]:
    return {
        "id": preset_id,
        "joints": {
            base_name: {
                "position": list(transform.position),
                "quaternion": list(transform.quaternion),
            }
            for base_name, transform in joints.items()
        },
    }


def _rig_export(rig: RigSpec) -> dict[str, object]:
    return {
        "id": rig.rig_id,
        "derivedFrom": rig.derived_from,
        "joints": [
            {
                "baseName": joint.base_name,
                "parent": joint.parent,
                "position": list(joint.position),
                "quaternion": list(joint.quaternion),
            }
            for joint in rig.joints
        ],
        "previewGeometry": _preview_geometry(rig),
    }


def _ual_hints_export(rig: RigSpec) -> dict[str, object]:
    if rig.ual_conversion is None:
        return {}

    return {
        "directionalTargets": dict(rig.ual_conversion.directional_targets),
        "groundSegments": [asdict(segment) for segment in rig.ual_conversion.ground_segments],
    }


def build_export_data(spec: AuthoredRigSpec) -> dict[str, object]:
    return {
        "R11_CORE": _rig_export(spec.r11_core),
        "AUTORIG_R18": _rig_export(spec.autorig_r18),
        "AUTORIG_UAL_HINTS": _ual_hints_export(spec.autorig_r18),
        "NEUTRAL_BIND_POSE": _pose_export(spec.neutral_bind.preset_id, dict(spec.neutral_bind.joints)),
        "RELAXED_PREVIEW_POSE": _pose_export(spec.relaxed_preview.preset_id, dict(spec.relaxed_preview.joints)),
        "AUTORIG_SEGMENTS": [asdict(segment) for segment in spec.autorig_segments],
        "AUTORIG_AUTO_SKIN_SEGMENTS": [asdict(segment) for segment in spec.autorig_auto_skin_segments],
    }


def _validate_parent_graph(rig: RigSpec) -> None:
    joint_names = _joint_names(rig)
    joint_set = set(joint_names)
    if len(joint_names) != len(joint_set):
        raise RigSpecError(f"{rig.rig_id} contains duplicate joint names.")

    for joint in rig.joints:
        if joint.parent is not None and joint.parent not in joint_set:
            raise RigSpecError(f"{rig.rig_id} joint {joint.base_name} references missing parent {joint.parent}.")

    parents = _parents_by_name(rig)
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(name: str) -> None:
        if name in visited:
            return
        if name in visiting:
            raise RigSpecError(f"{rig.rig_id} contains a cycle involving {name}.")
        visiting.add(name)
        parent = parents[name]
        if parent is not None:
            visit(parent)
        visiting.remove(name)
        visited.add(name)

    for name in joint_names:
        visit(name)


def validate_spec(spec: AuthoredRigSpec) -> None:
    _validate_parent_graph(spec.r11_core)
    _validate_parent_graph(spec.autorig_r18)

    core_names = _joint_names(spec.r11_core)
    autorig_names = _joint_names(spec.autorig_r18)
    core_set = set(core_names)
    autorig_set = set(autorig_names)

    if not core_set.issubset(autorig_set):
        raise RigSpecError("autorig_r18 must contain every r11_core joint.")

    if set(spec.r11_core.preview_geometry) != core_set:
        raise RigSpecError("r11_core preview geometry hints must cover every core joint exactly once.")

    preset_names = set(spec.neutral_bind.joints)
    if preset_names != autorig_set:
        raise RigSpecError("neutral_bind must cover every autorig_r18 joint exactly once.")
    if set(spec.relaxed_preview.joints) != autorig_set:
        raise RigSpecError("relaxed_preview must cover every autorig_r18 joint exactly once.")

    for segment in spec.autorig_segments:
        for field in (segment.bone, segment.parent, segment.child):
            if field is not None and field not in autorig_set:
                raise RigSpecError(f"AutoRig segment references unknown joint {field}.")

    for segment in spec.autorig_auto_skin_segments:
        for field in (segment.bone, segment.start, segment.end):
            if field not in autorig_set:
                raise RigSpecError(f"Auto-skin segment references unknown joint {field}.")

    if spec.autorig_r18.ual_conversion is None:
        raise RigSpecError("autorig_r18 is missing UAL conversion metadata.")

    for name, target in spec.autorig_r18.ual_conversion.directional_targets.items():
        if name not in autorig_set or target not in autorig_set:
            raise RigSpecError(f"UAL directional target {name} -> {target} references an unknown joint.")

    for segment in spec.autorig_r18.ual_conversion.ground_segments:
        if segment.start not in autorig_set or segment.end not in autorig_set:
            raise RigSpecError(f"UAL ground segment {segment.start} -> {segment.end} references an unknown joint.")


def render_generated_module(spec: AuthoredRigSpec | None = None) -> str:
    authored = spec or build_authored_spec()
    validate_spec(authored)
    payload = build_export_data(authored)
    rendered = json.dumps(payload, indent=2, sort_keys=False)
    lines = [
        "// This file is generated by `python3 -m animateur_rig compile`.",
        "// Do not edit by hand.",
        "",
        "const deepFreeze = value => {",
        "  if (!value || typeof value !== 'object' || Object.isFrozen(value)) {",
        "    return value;",
        "  }",
        "  Object.freeze(value);",
        "  for (const child of Object.values(value)) {",
        "    deepFreeze(child);",
        "  }",
        "  return value;",
        "};",
        "",
        f"const DATA = {rendered};",
        "",
        "export const R11_CORE = deepFreeze(DATA.R11_CORE);",
        "export const AUTORIG_R18 = deepFreeze(DATA.AUTORIG_R18);",
        "export const AUTORIG_UAL_HINTS = deepFreeze(DATA.AUTORIG_UAL_HINTS);",
        "export const NEUTRAL_BIND_POSE = deepFreeze(DATA.NEUTRAL_BIND_POSE);",
        "export const RELAXED_PREVIEW_POSE = deepFreeze(DATA.RELAXED_PREVIEW_POSE);",
        "export const AUTORIG_SEGMENTS = deepFreeze(DATA.AUTORIG_SEGMENTS);",
        "export const AUTORIG_AUTO_SKIN_SEGMENTS = deepFreeze(DATA.AUTORIG_AUTO_SKIN_SEGMENTS);",
        "",
    ]
    return "\n".join(lines)


def build_generated_outputs(spec: AuthoredRigSpec | None = None, output_path: Path | None = None) -> dict[Path, str]:
    return {
        (output_path or GENERATED_SPEC_PATH): render_generated_module(spec),
    }


def write_outputs(outputs: dict[Path, str], *, check: bool = False) -> list[Path]:
    stale_paths: list[Path] = []
    for path, content in outputs.items():
        if path.exists():
            current = path.read_text(encoding="utf8")
            if current == content:
                continue
        if check:
            stale_paths.append(path)
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf8")
    if stale_paths:
        raise StaleGeneratedArtifactError(
            "Generated rig artifacts are stale: "
            + ", ".join(str(path) for path in stale_paths)
            + ". Run `python3 -m animateur_rig compile`."
        )
    return list(outputs)


def compile_repo(*, check: bool = False, output_path: Path | None = None) -> list[Path]:
    outputs = build_generated_outputs(output_path=output_path)
    return write_outputs(outputs, check=check)
