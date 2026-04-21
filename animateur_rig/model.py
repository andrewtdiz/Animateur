from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

Vector3 = tuple[float, float, float]
Quaternion = tuple[float, float, float, float]


@dataclass(frozen=True)
class JointSpec:
    base_name: str
    parent: str | None
    position: Vector3
    quaternion: Quaternion


@dataclass(frozen=True)
class PreviewGeometryHint:
    size: Vector3
    pivot_y_offset: float


@dataclass(frozen=True)
class PoseTransform:
    position: Vector3
    quaternion: Quaternion


@dataclass(frozen=True)
class PosePreset:
    preset_id: str
    joints: Mapping[str, PoseTransform]


@dataclass(frozen=True)
class SegmentLayoutSpec:
    bone: str
    parent: str | None
    child: str | None
    size: Vector3
    anchor: str
    length: float
    divisions: int
    blend: float


@dataclass(frozen=True)
class AutoSkinSegmentSpec:
    bone: str
    start: str
    end: str
    a: Vector3
    b: Vector3
    radius: float
    region: str


@dataclass(frozen=True)
class GroundSegmentSpec:
    start: str
    end: str
    radius: float


@dataclass(frozen=True)
class UalConversionSpec:
    directional_targets: Mapping[str, str]
    ground_segments: tuple[GroundSegmentSpec, ...]


@dataclass(frozen=True)
class RigSpec:
    rig_id: str
    joints: tuple[JointSpec, ...]
    preview_geometry: Mapping[str, PreviewGeometryHint]
    derived_from: str | None = None
    ual_conversion: UalConversionSpec | None = None


@dataclass(frozen=True)
class AuthoredRigSpec:
    r11_core: RigSpec
    autorig_r18: RigSpec
    neutral_bind: PosePreset
    relaxed_preview: PosePreset
    autorig_segments: tuple[SegmentLayoutSpec, ...]
    autorig_auto_skin_segments: tuple[AutoSkinSegmentSpec, ...]
