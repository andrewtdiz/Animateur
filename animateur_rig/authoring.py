from __future__ import annotations

import copy
import json
import math
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from functools import lru_cache
from typing import Literal, TypeAlias, TypedDict

from .compiler import validate_spec
from .model import PosePreset, PoseTransform, RigSpec
from .spec import (
    NEUTRAL_BIND_ID,
    R11_CORE_ID,
    axis_angle_quaternion,
    build_authored_spec,
)

FAST_POSER_ASSET_FORMAT = "fast-poser-asset"
FAST_POSER_ASSET_VERSION = 1
POSE_ASSET_TYPE = "pose"
ANIMATION_ASSET_TYPE = "animation"

Vector3List: TypeAlias = list[float]
QuaternionList: TypeAlias = list[float]


class SerializedTransformDict(TypedDict):
    position: Vector3List
    quaternion: QuaternionList


SerializedPoseDict: TypeAlias = dict[str, SerializedTransformDict]


class KeyframeDict(TypedDict):
    time: float
    pose: SerializedPoseDict


class SceneDict(TypedDict):
    characterCount: int
    characterColors: list[str]


class PoseAssetDict(TypedDict):
    format: Literal["fast-poser-asset"]
    version: Literal[1]
    type: Literal["pose"]
    name: str
    savedAt: str
    scene: SceneDict
    pose: SerializedPoseDict


class AnimationAssetDict(TypedDict):
    format: Literal["fast-poser-asset"]
    version: Literal[1]
    type: Literal["animation"]
    name: str
    savedAt: str
    scene: SceneDict
    playbackSpeed: float
    effects: dict[str, object] | None
    keyframes: list[KeyframeDict]


JointTransformInput: TypeAlias = PoseTransform | Mapping[str, object]
PoseInput: TypeAlias = "Pose | Mapping[str, JointTransformInput]"
KeyframeInput: TypeAlias = "Keyframe | Mapping[str, object]"
EffectInput: TypeAlias = "ArcaneSummonEffect | Mapping[str, object] | None"

_JOINT_NAME_PATTERN = re.compile(r"^(.+)_(\d+)$")


class AssetValidationError(ValueError):
    pass


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _clone_position(position: object, fallback: Iterable[float] = (0.0, 0.0, 0.0)) -> Vector3List:
    fallback_values = [float(value) for value in tuple(fallback)[:3]]
    if not isinstance(position, (list, tuple)) or len(position) < 3:
        return fallback_values

    values: list[float] = []
    for value in position[:3]:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return fallback_values
        if not math.isfinite(number):
            return fallback_values
        values.append(number)
    return values


def _normalize_quaternion(
    quaternion: object,
    fallback: Iterable[float] = (0.0, 0.0, 0.0, 1.0),
) -> QuaternionList:
    fallback_values = [float(value) for value in tuple(fallback)[:4]]
    if not isinstance(quaternion, (list, tuple)) or len(quaternion) < 4:
        return fallback_values

    values: list[float] = []
    for value in quaternion[:4]:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return fallback_values
        if not math.isfinite(number):
            return fallback_values
        values.append(number)

    length = math.hypot(values[0], values[1], values[2], values[3])
    if length == 0:
        return [0.0, 0.0, 0.0, 1.0]

    return [value / length for value in values]


def _parse_count(value: object) -> int | None:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= 0 else None


def _parse_time(value: object) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return 0.0
    if not math.isfinite(parsed):
        return 0.0
    return max(0.0, parsed)


def _parse_transform_input(transform: object) -> tuple[object, object]:
    if isinstance(transform, PoseTransform):
        return transform.position, transform.quaternion
    if isinstance(transform, Mapping):
        return transform.get("position"), transform.get("quaternion")
    return None, None


def _normalize_transform(
    transform: object,
    fallback: object | None = None,
) -> SerializedTransformDict:
    fallback_position, fallback_quaternion = _parse_transform_input(fallback)
    position, quaternion = _parse_transform_input(transform)
    return {
        "position": _clone_position(position, _clone_position(fallback_position)),
        "quaternion": _normalize_quaternion(quaternion, _normalize_quaternion(fallback_quaternion)),
    }


def _clone_transform(transform: Mapping[str, object]) -> SerializedTransformDict:
    return _normalize_transform(transform)


def _clone_pose(pose: Mapping[str, object] | None) -> SerializedPoseDict:
    clone: SerializedPoseDict = {}
    for name, transform in (pose or {}).items():
        clone[str(name)] = _normalize_transform(transform)
    return clone


@lru_cache(maxsize=1)
def _authored_spec():
    spec = build_authored_spec()
    validate_spec(spec)
    return spec


@lru_cache(maxsize=1)
def _rigs_by_id() -> dict[str, RigSpec]:
    spec = _authored_spec()
    return {
        spec.r11_core.rig_id: spec.r11_core,
        spec.autorig_r18.rig_id: spec.autorig_r18,
    }


@lru_cache(maxsize=1)
def _presets_by_id() -> dict[str, PosePreset]:
    spec = _authored_spec()
    return {
        spec.neutral_bind.preset_id: spec.neutral_bind,
        spec.relaxed_preview.preset_id: spec.relaxed_preview,
    }


@lru_cache(maxsize=1)
def _known_base_names() -> set[str]:
    names: set[str] = set()
    for rig in _rigs_by_id().values():
        names.update(joint.base_name for joint in rig.joints)
    return names


def get_rig(rig_id: str = R11_CORE_ID) -> RigSpec:
    rig = _rigs_by_id().get(rig_id)
    if rig is None:
        raise AssetValidationError(f'Unknown rig "{rig_id}".')
    return rig


def _get_preset(preset_id: str = NEUTRAL_BIND_ID) -> PosePreset:
    preset = _presets_by_id().get(preset_id)
    if preset is None:
        raise AssetValidationError(f'Unknown rig preset "{preset_id}".')
    return preset


def get_joint_name(base_name: str, character_index: int) -> str:
    return f"{base_name}_{int(character_index)}"


def _parse_joint_name(joint_name: object) -> tuple[str, int] | None:
    match = _JOINT_NAME_PATTERN.match(str(joint_name or ""))
    if not match or match.group(1) not in _known_base_names():
        return None
    return match.group(1), int(match.group(2))


def _infer_character_index_from_pose(serialized_pose: Mapping[str, object] | None) -> int:
    current_max = -1
    for joint_name in (serialized_pose or {}):
        parsed = _parse_joint_name(joint_name)
        if parsed is not None:
            current_max = max(current_max, parsed[1])
    return current_max


def infer_character_count(asset_or_pose: object) -> int:
    if not isinstance(asset_or_pose, Mapping):
        return 0

    scene = asset_or_pose.get("scene")
    explicit_count = _parse_count(scene.get("characterCount")) if isinstance(scene, Mapping) else None
    if explicit_count is None:
        explicit_count = _parse_count(asset_or_pose.get("characterCount"))
    if explicit_count is not None:
        return explicit_count

    keyframes = asset_or_pose.get("keyframes")
    if isinstance(keyframes, list):
        current_max = -1
        for frame in keyframes:
            if isinstance(frame, Mapping):
                current_max = max(current_max, _infer_character_index_from_pose(frame.get("pose")))
        return current_max + 1

    pose = asset_or_pose.get("pose")
    if isinstance(pose, Mapping):
        return _infer_character_index_from_pose(pose) + 1

    return _infer_character_index_from_pose(asset_or_pose) + 1


def build_default_pose(
    character_count: int,
    rig_id: str = R11_CORE_ID,
    preset: str = NEUTRAL_BIND_ID,
) -> SerializedPoseDict:
    count = max(0, int(character_count))
    rig = get_rig(rig_id)
    preset_data = _get_preset(preset)
    pose: SerializedPoseDict = {}

    for character_index in range(count):
        for joint in rig.joints:
            transform = preset_data.joints.get(joint.base_name)
            pose[get_joint_name(joint.base_name, character_index)] = _normalize_transform(
                transform if transform is not None else {"position": joint.position, "quaternion": joint.quaternion},
            )

    return pose


def _resolve_pose_input(pose: PoseInput | None) -> Mapping[str, object]:
    if isinstance(pose, Pose):
        return pose._overrides
    if isinstance(pose, Mapping):
        return pose
    return {}


def normalize_pose(
    serialized_pose: PoseInput | None,
    fallback_pose: PoseInput | None,
    rig_id: str = R11_CORE_ID,
) -> SerializedPoseDict:
    source = _resolve_pose_input(serialized_pose)
    fallback = _resolve_pose_input(fallback_pose)
    rig = get_rig(rig_id)
    character_count = max(infer_character_count(source), infer_character_count(fallback))
    if character_count <= 0:
        return {}

    neutral_fallback = build_default_pose(character_count, rig_id, NEUTRAL_BIND_ID)
    pose: SerializedPoseDict = {}
    for character_index in range(character_count):
        for joint in rig.joints:
            joint_name = get_joint_name(joint.base_name, character_index)
            fallback_transform = fallback.get(joint_name) or neutral_fallback[joint_name]
            pose[joint_name] = _normalize_transform(source.get(joint_name), fallback_transform)
    return pose


def normalize_keyframes(
    frames: Iterable[KeyframeInput] | Mapping[str, object] | None,
    rig_id: str = R11_CORE_ID,
    *,
    character_count: int | None = None,
) -> list[KeyframeDict]:
    frame_values: Iterable[KeyframeInput]
    explicit_count = character_count

    if isinstance(frames, Mapping):
        if explicit_count is None:
            explicit_count = infer_character_count(frames)
        raw_frames = frames.get("keyframes")
        frame_values = raw_frames if isinstance(raw_frames, list) else []
    else:
        frame_values = frames or []

    sorted_frames: list[KeyframeDict] = []
    for frame in frame_values:
        if isinstance(frame, Keyframe):
            sorted_frames.append({"time": _parse_time(frame.time), "pose": _clone_pose(frame._pose._overrides)})
            continue
        if isinstance(frame, Mapping):
            pose = frame.get("pose") if isinstance(frame.get("pose"), Mapping) else {}
            sorted_frames.append({"time": _parse_time(frame.get("time")), "pose": _clone_pose(pose)})

    sorted_frames.sort(key=lambda frame: frame["time"])
    resolved_count = explicit_count if explicit_count is not None else infer_character_count({"keyframes": sorted_frames})
    if resolved_count <= 0:
        return []

    rolling_pose = build_default_pose(resolved_count, rig_id, NEUTRAL_BIND_ID)
    normalized_frames: list[KeyframeDict] = []
    for frame in sorted_frames:
        pose = normalize_pose(frame["pose"], rolling_pose, rig_id)
        rolling_pose = _clone_pose(pose)
        normalized_frames.append({"time": frame["time"], "pose": pose})
    return normalized_frames


def _normalize_character_colors(character_colors: Iterable[object] | None, character_count: int) -> list[str]:
    if character_count <= 0:
        return []

    colors: list[str] = []
    for value in character_colors or []:
        text = str(value).strip()
        if text:
            colors.append(text)
        if len(colors) >= character_count:
            break
    return colors


def _build_scene(character_count: int, character_colors: Iterable[object] | None = None) -> SceneDict:
    resolved_count = max(0, int(character_count))
    return {
        "characterCount": resolved_count,
        "characterColors": _normalize_character_colors(character_colors, resolved_count),
    }


def _normalize_playback_speed(playback_speed: object) -> float:
    try:
        value = float(playback_speed)
    except (TypeError, ValueError):
        return 1.0
    return value if math.isfinite(value) and value > 0 else 1.0


def _normalize_color(value: object, fallback: str) -> str:
    text = str(value or fallback).strip()
    if not text:
        return fallback
    return text


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return min(maximum, max(minimum, value))


def _round_effect_time(value: float) -> float:
    return round(value * 10.0) / 10.0


@dataclass
class ArcaneSummonEffect:
    target_character: int = 0
    start_time: float = 0.0
    peak_time: float = 1.8
    end_time: float = 3.4
    radius: float = 3.2
    column_height: float = 6.2
    primary_color: str = "#63f3ff"
    secondary_color: str = "#5b36ff"
    accent_color: str = "#ffd36b"
    glow_color: str = "#f0f9ff"

    @classmethod
    def from_input(cls, value: EffectInput = None) -> ArcaneSummonEffect | None:
        if value is None:
            return None
        if isinstance(value, ArcaneSummonEffect):
            effect = copy.deepcopy(value)
            effect.validate()
            return effect
        if not isinstance(value, Mapping) or value.get("preset") != "arcane-summon":
            raise AssetValidationError("Unsupported effect payload. Only the arcane-summon preset is supported.")
        start_time = _parse_time(value.get("startTime"))
        peak_time = max(start_time + 0.1, _parse_time(value.get("peakTime")) or start_time + 1.8)
        end_time = max(peak_time + 0.1, _parse_time(value.get("endTime")) or peak_time + 1.6)
        effect = cls(
            target_character=max(0, _parse_count(value.get("targetCharacter")) or 0),
            start_time=_round_effect_time(start_time),
            peak_time=_round_effect_time(peak_time),
            end_time=_round_effect_time(end_time),
            radius=round(_clamp(float(value.get("radius") or 3.2), 1.5, 6.0), 2),
            column_height=round(_clamp(float(value.get("columnHeight") or 6.2), 2.5, 10.0), 2),
            primary_color=_normalize_color(value.get("primaryColor"), "#63f3ff"),
            secondary_color=_normalize_color(value.get("secondaryColor"), "#5b36ff"),
            accent_color=_normalize_color(value.get("accentColor"), "#ffd36b"),
            glow_color=_normalize_color(value.get("glowColor"), "#f0f9ff"),
        )
        effect.validate()
        return effect

    def validate(self) -> None:
        if self.target_character < 0:
            raise AssetValidationError("ArcaneSummonEffect.target_character must be >= 0.")
        if self.start_time < 0:
            raise AssetValidationError("ArcaneSummonEffect.start_time must be >= 0.")
        if self.peak_time < self.start_time + 0.1:
            raise AssetValidationError("ArcaneSummonEffect.peak_time must be at least 0.1 after start_time.")
        if self.end_time < self.peak_time + 0.1:
            raise AssetValidationError("ArcaneSummonEffect.end_time must be at least 0.1 after peak_time.")
        if self.radius < 1.5 or self.radius > 6.0:
            raise AssetValidationError("ArcaneSummonEffect.radius must be between 1.5 and 6.0.")
        if self.column_height < 2.5 or self.column_height > 10.0:
            raise AssetValidationError("ArcaneSummonEffect.column_height must be between 2.5 and 10.0.")

    def to_dict(self) -> dict[str, object]:
        self.validate()
        return {
            "preset": "arcane-summon",
            "targetCharacter": int(self.target_character),
            "startTime": _round_effect_time(self.start_time),
            "peakTime": _round_effect_time(self.peak_time),
            "endTime": _round_effect_time(self.end_time),
            "radius": round(float(self.radius), 2),
            "columnHeight": round(float(self.column_height), 2),
            "primaryColor": self.primary_color,
            "secondaryColor": self.secondary_color,
            "accentColor": self.accent_color,
            "glowColor": self.glow_color,
        }

    def to_json(self, *, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)


def _normalize_effect(effect: EffectInput = None) -> ArcaneSummonEffect | None:
    return ArcaneSummonEffect.from_input(effect)


@dataclass
class Pose:
    rig_id: str = R11_CORE_ID
    character_count: int = 1
    preset: str = NEUTRAL_BIND_ID
    _overrides: SerializedPoseDict = field(default_factory=dict)

    @classmethod
    def default(
        cls,
        *,
        rig_id: str = R11_CORE_ID,
        character_count: int = 1,
        preset: str = NEUTRAL_BIND_ID,
    ) -> Pose:
        pose = cls(rig_id=rig_id, character_count=max(0, int(character_count)), preset=preset)
        pose._overrides = build_default_pose(pose.character_count, rig_id, preset)
        return pose

    @classmethod
    def from_input(
        cls,
        value: PoseInput | None = None,
        *,
        rig_id: str = R11_CORE_ID,
        character_count: int | None = None,
        preset: str = NEUTRAL_BIND_ID,
    ) -> Pose:
        if isinstance(value, Pose):
            clone = value.copy()
            if character_count is not None:
                clone.character_count = max(clone.character_count, int(character_count))
            return clone

        resolved_count = character_count
        if resolved_count is None:
            resolved_count = infer_character_count({"pose": value}) if isinstance(value, Mapping) else 0
        if resolved_count <= 0:
            resolved_count = 1

        pose = cls(rig_id=rig_id, character_count=resolved_count, preset=preset)
        pose._overrides = _clone_pose(value if isinstance(value, Mapping) else {})
        return pose

    def copy(self) -> Pose:
        return Pose(
            rig_id=self.rig_id,
            character_count=self.character_count,
            preset=self.preset,
            _overrides=_clone_pose(self._overrides),
        )

    def validate(self) -> None:
        rig = get_rig(self.rig_id)
        valid_base_names = {joint.base_name for joint in rig.joints}
        for joint_name, transform in self._overrides.items():
            parsed = _parse_joint_name(joint_name)
            if parsed is None or parsed[0] not in valid_base_names:
                raise AssetValidationError(f'Unknown joint "{joint_name}" for rig "{self.rig_id}".')
            if parsed[1] < 0:
                raise AssetValidationError(f'Joint "{joint_name}" has a negative character index.')
            _normalize_transform(transform)

    def _resolved_character_count(self) -> int:
        return max(self.character_count, infer_character_count({"pose": self._overrides}))

    def normalized(self) -> SerializedPoseDict:
        count = self._resolved_character_count()
        fallback = build_default_pose(count, self.rig_id, self.preset)
        return normalize_pose(self._overrides, fallback, self.rig_id)

    def to_dict(self) -> SerializedPoseDict:
        self.validate()
        return self.normalized()

    def to_json(self, *, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    def _set_transform(self, joint_name: str, *, position: object | None = None, quaternion: object | None = None) -> Pose:
        current = self._overrides.get(joint_name, {})
        next_position = position if position is not None else current.get("position")
        next_quaternion = quaternion if quaternion is not None else current.get("quaternion")
        self._overrides[joint_name] = _normalize_transform(
            {"position": next_position, "quaternion": next_quaternion},
            current,
        )
        return self

    def set_position(
        self,
        base_name: str,
        position: Iterable[float],
        *,
        character_index: int = 0,
    ) -> Pose:
        self._set_transform(get_joint_name(base_name, character_index), position=position)
        self.character_count = max(self.character_count, character_index + 1)
        return self

    def set_rotation(
        self,
        base_name: str,
        quaternion: Iterable[float] | None = None,
        *,
        character_index: int = 0,
        axis: Iterable[float] | None = None,
        angle_radians: float | None = None,
    ) -> Pose:
        resolved_quaternion = quaternion
        if resolved_quaternion is None:
            if axis is None or angle_radians is None:
                raise AssetValidationError("set_rotation requires a quaternion or both axis and angle_radians.")
            resolved_quaternion = axis_angle_quaternion(
                tuple(float(value) for value in axis),
                float(angle_radians),
            )
        self._set_transform(get_joint_name(base_name, character_index), quaternion=resolved_quaternion)
        self.character_count = max(self.character_count, character_index + 1)
        return self

    def offset_root_motion(
        self,
        offset: Iterable[float],
        *,
        character_index: int = 0,
    ) -> Pose:
        normalized = self.normalized()
        joint_name = get_joint_name("Hips", character_index)
        current = normalized[joint_name]["position"]
        delta = _clone_position(offset)
        return self.set_position(
            "Hips",
            [current[index] + delta[index] for index in range(3)],
            character_index=character_index,
        )

    def copy_character_pose(self, source_index: int, target_index: int) -> Pose:
        normalized = self.normalized()
        rig = get_rig(self.rig_id)
        for joint in rig.joints:
            source_name = get_joint_name(joint.base_name, source_index)
            target_name = get_joint_name(joint.base_name, target_index)
            self._overrides[target_name] = _clone_transform(normalized[source_name])
        self.character_count = max(self.character_count, source_index + 1, target_index + 1)
        return self


@dataclass
class Keyframe:
    time: float
    pose: Pose

    @classmethod
    def from_input(
        cls,
        time: float,
        pose: PoseInput | None = None,
        *,
        rig_id: str = R11_CORE_ID,
        character_count: int | None = None,
    ) -> Keyframe:
        return cls(
            time=_parse_time(time),
            pose=Pose.from_input(pose, rig_id=rig_id, character_count=character_count),
        )

    @property
    def _pose(self) -> Pose:
        return self.pose

    def validate(self) -> None:
        if self.time < 0:
            raise AssetValidationError("Keyframe.time must be >= 0.")
        self.pose.validate()

    def to_dict(self) -> KeyframeDict:
        self.validate()
        return {
            "time": _parse_time(self.time),
            "pose": self.pose.to_dict(),
        }

    def to_json(self, *, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)


@dataclass
class PoseAsset:
    name: str
    rig_id: str = R11_CORE_ID
    character_count: int = 1
    character_colors: list[str] = field(default_factory=list)
    saved_at: str = field(default_factory=_timestamp)
    pose: Pose = field(default_factory=Pose.default)

    @classmethod
    def new(
        cls,
        name: str,
        *,
        rig: str = R11_CORE_ID,
        character_count: int = 1,
        character_colors: Iterable[object] | None = None,
        saved_at: str | None = None,
        preset: str = NEUTRAL_BIND_ID,
        pose: PoseInput | None = None,
    ) -> PoseAsset:
        resolved_count = max(1, int(character_count))
        resolved_pose = (
            Pose.default(rig_id=rig, character_count=resolved_count, preset=preset)
            if pose is None
            else Pose.from_input(pose, rig_id=rig, character_count=resolved_count, preset=preset)
        )
        return cls(
            name=str(name).strip() or "Untitled Pose",
            rig_id=rig,
            character_count=resolved_count,
            character_colors=_normalize_character_colors(character_colors, resolved_count),
            saved_at=str(saved_at or _timestamp()),
            pose=resolved_pose,
        )

    def validate(self) -> None:
        if not self.name:
            raise AssetValidationError("PoseAsset.name must not be empty.")
        normalized_pose = self.pose.to_dict()
        validate_pose_dict(normalized_pose, self.rig_id, self.character_count)

    def to_dict(self) -> PoseAssetDict:
        self.validate()
        return {
            "format": FAST_POSER_ASSET_FORMAT,
            "version": FAST_POSER_ASSET_VERSION,
            "type": POSE_ASSET_TYPE,
            "name": self.name,
            "savedAt": self.saved_at,
            "scene": _build_scene(self.character_count, self.character_colors),
            "pose": self.pose.to_dict(),
        }

    def to_json(self, *, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)


@dataclass
class AnimationAsset:
    name: str
    rig_id: str = R11_CORE_ID
    character_count: int = 1
    character_colors: list[str] = field(default_factory=list)
    playback_speed: float = 1.0
    effects: ArcaneSummonEffect | None = None
    saved_at: str = field(default_factory=_timestamp)
    keyframes: list[Keyframe] = field(default_factory=list)

    @classmethod
    def new(
        cls,
        name: str,
        *,
        rig: str = R11_CORE_ID,
        character_count: int = 1,
        character_colors: Iterable[object] | None = None,
        playback_speed: float = 1.0,
        effects: EffectInput = None,
        saved_at: str | None = None,
    ) -> AnimationAsset:
        resolved_count = max(1, int(character_count))
        return cls(
            name=str(name).strip() or "Untitled Animation",
            rig_id=rig,
            character_count=resolved_count,
            character_colors=_normalize_character_colors(character_colors, resolved_count),
            playback_speed=_normalize_playback_speed(playback_speed),
            effects=_normalize_effect(effects),
            saved_at=str(saved_at or _timestamp()),
        )

    def add_keyframe(self, time: float, pose: PoseInput | None = None) -> Keyframe:
        if pose is None:
            if self.keyframes:
                resolved_pose = self.keyframes[-1].pose.copy()
            else:
                resolved_pose = Pose.default(rig_id=self.rig_id, character_count=self.character_count)
        else:
            resolved_pose = Pose.from_input(
                pose,
                rig_id=self.rig_id,
                character_count=self.character_count,
            )
        frame = Keyframe.from_input(
            time,
            resolved_pose,
            rig_id=self.rig_id,
            character_count=self.character_count,
        )
        self.keyframes.append(frame)
        self.keyframes.sort(key=lambda item: item.time)
        self.character_count = max(self.character_count, frame.pose._resolved_character_count())
        return frame

    def hold(self, duration: float) -> AnimationAsset:
        if duration <= 0:
            return self
        current_time = self.keyframes[-1].time if self.keyframes else 0.0
        return self.add_keyframe(current_time + duration)

    def transition(self, target_pose: PoseInput, duration: float) -> AnimationAsset:
        current_time = self.keyframes[-1].time if self.keyframes else 0.0
        self.add_keyframe(current_time + max(0.0, float(duration)), target_pose)
        return self

    def retime(self, *, scale: float = 1.0, offset: float = 0.0) -> AnimationAsset:
        if scale <= 0:
            raise AssetValidationError("AnimationAsset.retime scale must be > 0.")
        for frame in self.keyframes:
            frame.time = _parse_time(frame.time * scale + offset)
        self.keyframes.sort(key=lambda item: item.time)
        return self

    def append_clip(self, clip: AnimationAsset, *, gap: float = 0.0) -> AnimationAsset:
        if clip.rig_id != self.rig_id:
            raise AssetValidationError("append_clip requires both clips to use the same rig.")
        start_time = self.keyframes[-1].time if self.keyframes else 0.0
        offset = start_time + max(0.0, float(gap))
        base_time = clip.keyframes[0].time if clip.keyframes else 0.0
        for frame in clip.keyframes:
            self.add_keyframe(offset + (frame.time - base_time), frame.pose)
        self.character_count = max(self.character_count, clip.character_count)
        return self

    def validate(self) -> None:
        if not self.name:
            raise AssetValidationError("AnimationAsset.name must not be empty.")
        normalized_frames = self.normalized_keyframes()
        if self.effects is not None:
            self.effects.validate()
            if self.effects.target_character >= self.character_count:
                raise AssetValidationError(
                    "AnimationAsset.effects.target_character must be within scene.characterCount.",
                )
        validate_keyframes(normalized_frames, self.rig_id, self.character_count)

    def normalized_keyframes(self) -> list[KeyframeDict]:
        return normalize_keyframes(self.keyframes, self.rig_id, character_count=self.character_count)

    def to_dict(self) -> AnimationAssetDict:
        self.validate()
        return {
            "format": FAST_POSER_ASSET_FORMAT,
            "version": FAST_POSER_ASSET_VERSION,
            "type": ANIMATION_ASSET_TYPE,
            "name": self.name,
            "savedAt": self.saved_at,
            "scene": _build_scene(self.character_count, self.character_colors),
            "playbackSpeed": self.playback_speed,
            "effects": self.effects.to_dict() if self.effects is not None else None,
            "keyframes": self.normalized_keyframes(),
        }

    def to_json(self, *, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)


def validate_pose_dict(
    pose: Mapping[str, object],
    rig_id: str,
    character_count: int,
) -> None:
    rig = get_rig(rig_id)
    expected = {
        get_joint_name(joint.base_name, character_index)
        for character_index in range(max(0, character_count))
        for joint in rig.joints
    }
    actual = set(pose)
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        message = []
        if missing:
            message.append(f"missing joints: {', '.join(missing[:6])}")
        if extra:
            message.append(f"unexpected joints: {', '.join(extra[:6])}")
        raise AssetValidationError(f"Pose joint coverage is invalid for {rig_id}: {'; '.join(message)}")

    for joint_name, transform in pose.items():
        parsed = _parse_joint_name(joint_name)
        if parsed is None or parsed[1] >= character_count:
            raise AssetValidationError(f"Invalid joint name '{joint_name}' for character_count={character_count}.")
        _normalize_transform(transform)


def validate_keyframes(
    keyframes: Iterable[Mapping[str, object]],
    rig_id: str,
    character_count: int,
) -> None:
    previous_time = -1.0
    for frame in keyframes:
        if not isinstance(frame, Mapping):
            raise AssetValidationError("Each keyframe must be a mapping.")
        time = _parse_time(frame.get("time"))
        if time < previous_time:
            raise AssetValidationError("Animation keyframes must be sorted by ascending time.")
        previous_time = time
        pose = frame.get("pose")
        if not isinstance(pose, Mapping):
            raise AssetValidationError("Each keyframe must include a pose mapping.")
        validate_pose_dict(pose, rig_id, character_count)


def new_pose(
    name: str,
    *,
    rig: str = R11_CORE_ID,
    character_count: int = 1,
    character_colors: Iterable[object] | None = None,
    saved_at: str | None = None,
    preset: str = NEUTRAL_BIND_ID,
    pose: PoseInput | None = None,
) -> PoseAsset:
    return PoseAsset.new(
        name,
        rig=rig,
        character_count=character_count,
        character_colors=character_colors,
        saved_at=saved_at,
        preset=preset,
        pose=pose,
    )


def new_animation(
    name: str,
    *,
    rig: str = R11_CORE_ID,
    character_count: int = 1,
    character_colors: Iterable[object] | None = None,
    playback_speed: float = 1.0,
    effects: EffectInput = None,
    saved_at: str | None = None,
) -> AnimationAsset:
    return AnimationAsset.new(
        name,
        rig=rig,
        character_count=character_count,
        character_colors=character_colors,
        playback_speed=playback_speed,
        effects=effects,
        saved_at=saved_at,
    )
