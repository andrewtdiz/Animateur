"""Optional public IK authoring helpers for animateur_rig.

This module is the package's isolated advanced-pose layer. It helps author
world-space end-effector poses, then bakes the result back into ordinary local
joint rotations on a normal ``Pose``. It does not change the asset JSON
contract or runtime requirements.
"""
from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Literal

from .authoring import AssetValidationError, Pose, SerializedPoseDict, get_joint_name, get_rig

Vector3 = tuple[float, float, float]
Quaternion = tuple[float, float, float, float]
ArmSide = Literal["left", "right"]
OrientationMode = Literal["maintain", "target"]

_EPSILON = 1e-8


@dataclass(frozen=True)
class _ArmChainSpec:
    rig_id: str
    side: ArmSide
    shoulder_joint: str | None
    root_joint: str
    mid_joint: str
    end_joint: str | None
    default_tip_offset: Vector3
    default_pole_axis: Vector3
    local_side_axis: Vector3


@dataclass(frozen=True)
class _JointWorldTransform:
    position: Vector3
    quaternion: Quaternion


_CHAIN_SPECS: dict[tuple[str, ArmSide], _ArmChainSpec] = {
    ("r11_core", "left"): _ArmChainSpec(
        rig_id="r11_core",
        side="left",
        shoulder_joint=None,
        root_joint="Left_Upper_Arm",
        mid_joint="Left_Lower_Arm",
        end_joint=None,
        default_tip_offset=(0.0, -0.9, 0.0),
        default_pole_axis=(1.0, 0.0, 0.0),
        local_side_axis=(1.0, 0.0, 0.0),
    ),
    ("r11_core", "right"): _ArmChainSpec(
        rig_id="r11_core",
        side="right",
        shoulder_joint=None,
        root_joint="Right_Upper_Arm",
        mid_joint="Right_Lower_Arm",
        end_joint=None,
        default_tip_offset=(0.0, -0.9, 0.0),
        default_pole_axis=(-1.0, 0.0, 0.0),
        local_side_axis=(-1.0, 0.0, 0.0),
    ),
    ("autorig_r18", "left"): _ArmChainSpec(
        rig_id="autorig_r18",
        side="left",
        shoulder_joint="Left_Shoulder",
        root_joint="Left_Upper_Arm",
        mid_joint="Left_Lower_Arm",
        end_joint="Left_Hand",
        default_tip_offset=(0.0, -0.88, 0.02),
        default_pole_axis=(1.0, 0.0, 0.0),
        local_side_axis=(1.0, 0.0, 0.0),
    ),
    ("autorig_r18", "right"): _ArmChainSpec(
        rig_id="autorig_r18",
        side="right",
        shoulder_joint="Right_Shoulder",
        root_joint="Right_Upper_Arm",
        mid_joint="Right_Lower_Arm",
        end_joint="Right_Hand",
        default_tip_offset=(0.0, -0.88, 0.02),
        default_pole_axis=(-1.0, 0.0, 0.0),
        local_side_axis=(-1.0, 0.0, 0.0),
    ),
}


def solve_arm_to_target(
    pose: Pose,
    side: Literal["left", "right"],
    target: Iterable[float],
    *,
    character_index: int = 0,
    pole: Iterable[float] | None = None,
    tip_offset: Iterable[float] | None = None,
    orient: Literal["maintain", "target"] = "maintain",
    target_orientation: Iterable[float] | None = None,
) -> Pose:
    """Solve one authored arm chain to a world-space target.

    The function mutates and returns ``pose``. Only local joint rotations are
    written back into the pose; serialization remains unchanged.
    """

    resolved_side = _normalize_side(side)
    resolved_orient = _normalize_orient(orient)
    resolved_character_index = int(character_index)
    if resolved_character_index < 0:
        raise AssetValidationError("character_index must be >= 0.")
    chain = _CHAIN_SPECS.get((pose.rig_id, resolved_side))
    if chain is None:
        raise AssetValidationError(f'Rig "{pose.rig_id}" does not support arm IK authoring.')

    pose.character_count = max(int(pose.character_count), resolved_character_index + 1)
    rig = get_rig(pose.rig_id)
    joint_specs = {joint.base_name: joint for joint in rig.joints}
    target_position = _vector3(target, label="target")
    tip_vector = _resolve_tip_offset(chain, tip_offset, orient=resolved_orient)

    if chain.end_joint is None:
        if resolved_orient != "maintain":
            raise AssetValidationError(f'Rig "{pose.rig_id}" arm IK does not support hand orientation targeting.')
        if target_orientation is not None:
            raise AssetValidationError("target_orientation is only valid on rigs with hand joints.")
        effector_target = target_position
        target_orientation_quaternion = None
    else:
        if resolved_orient == "target":
            if target_orientation is None:
                raise AssetValidationError('orient="target" requires target_orientation.')
            target_orientation_quaternion = _quaternion(target_orientation, label="target_orientation")
            if tip_offset is None:
                effector_target = target_position
            else:
                effector_target = _subtract(target_position, _rotate_vector(target_orientation_quaternion, tip_vector))
        else:
            if target_orientation is not None:
                raise AssetValidationError('target_orientation requires orient="target".')
            if tip_offset is not None:
                raise AssetValidationError(
                    f'Rig "{pose.rig_id}" only accepts tip_offset with orient="target" when a hand joint exists.',
                )
            effector_target = target_position
            target_orientation_quaternion = None

    normalized_pose = pose.normalized()
    world_transforms = _build_world_transforms(normalized_pose, rig, resolved_character_index)

    parent_name = joint_specs[chain.root_joint].parent
    if parent_name is None:
        raise AssetValidationError(f'Joint "{chain.root_joint}" must have a parent for IK solving.')

    root_world = world_transforms[chain.root_joint]
    parent_world = world_transforms[parent_name]
    root_local_forward = _joint_local_position(normalized_pose, chain.mid_joint, resolved_character_index)
    mid_local_forward = (
        _joint_local_position(normalized_pose, chain.end_joint, resolved_character_index)
        if chain.end_joint is not None
        else tip_vector
    )

    upper_length = _length(root_local_forward)
    lower_length = _length(mid_local_forward)
    if upper_length <= _EPSILON or lower_length <= _EPSILON:
        raise AssetValidationError(f'Rig "{pose.rig_id}" has a zero-length arm segment and cannot be solved.')

    current_root_forward = _normalize(_rotate_vector(root_world.quaternion, root_local_forward))
    resolved_pole = _resolve_pole_point(
        pole,
        root_position=root_world.position,
        parent_quaternion=parent_world.quaternion,
        default_pole_axis=chain.default_pole_axis,
    )

    elbow_position, effector_position = _solve_two_bone_positions(
        root_position=root_world.position,
        target_position=effector_target,
        pole_position=resolved_pole,
        upper_length=upper_length,
        lower_length=lower_length,
        direction_fallback=current_root_forward,
    )

    upper_forward = _normalize(_subtract(elbow_position, root_world.position))
    lower_forward = _normalize(_subtract(effector_position, elbow_position))
    current_parent_side = _rotate_vector(parent_world.quaternion, chain.local_side_axis)
    upper_world_quaternion = _solve_bone_world_quaternion(
        local_forward=root_local_forward,
        local_side_axis=chain.local_side_axis,
        desired_forward=upper_forward,
        joint_position=root_world.position,
        pole_position=resolved_pole,
        fallback_side=current_parent_side,
    )
    lower_world_quaternion = _solve_bone_world_quaternion(
        local_forward=mid_local_forward,
        local_side_axis=chain.local_side_axis,
        desired_forward=lower_forward,
        joint_position=elbow_position,
        pole_position=resolved_pole,
        fallback_side=_rotate_vector(upper_world_quaternion, chain.local_side_axis),
    )

    root_local_quaternion = _canonicalize_quaternion(
        _normalize_quaternion(_multiply_quaternions(_conjugate(parent_world.quaternion), upper_world_quaternion)),
    )
    mid_local_quaternion = _canonicalize_quaternion(
        _normalize_quaternion(_multiply_quaternions(_conjugate(upper_world_quaternion), lower_world_quaternion)),
    )

    pose.set_rotation(chain.root_joint, quaternion=root_local_quaternion, character_index=resolved_character_index)
    pose.set_rotation(chain.mid_joint, quaternion=mid_local_quaternion, character_index=resolved_character_index)
    if chain.shoulder_joint is not None:
        pose.set_rotation(chain.shoulder_joint, quaternion=root_local_quaternion, character_index=resolved_character_index)

    if chain.end_joint is not None and resolved_orient == "target" and target_orientation_quaternion is not None:
        end_local_quaternion = _canonicalize_quaternion(
            _normalize_quaternion(
                _multiply_quaternions(_conjugate(lower_world_quaternion), target_orientation_quaternion),
            ),
        )
        pose.set_rotation(chain.end_joint, quaternion=end_local_quaternion, character_index=resolved_character_index)

    return pose


def solve_mirrored_arms_to_targets(
    pose: Pose,
    left_target: Iterable[float],
    right_target: Iterable[float],
    *,
    character_index: int = 0,
    left_pole: Iterable[float] | None = None,
    right_pole: Iterable[float] | None = None,
    left_tip_offset: Iterable[float] | None = None,
    right_tip_offset: Iterable[float] | None = None,
    orient: Literal["maintain", "target"] = "maintain",
    left_target_orientation: Iterable[float] | None = None,
    right_target_orientation: Iterable[float] | None = None,
) -> Pose:
    """Solve both arms on the same pose and return it."""

    solve_arm_to_target(
        pose,
        "left",
        left_target,
        character_index=character_index,
        pole=left_pole,
        tip_offset=left_tip_offset,
        orient=orient,
        target_orientation=left_target_orientation,
    )
    solve_arm_to_target(
        pose,
        "right",
        right_target,
        character_index=character_index,
        pole=right_pole,
        tip_offset=right_tip_offset,
        orient=orient,
        target_orientation=right_target_orientation,
    )
    return pose


def _normalize_side(value: object) -> ArmSide:
    resolved = str(value or "").strip().lower()
    if resolved not in ("left", "right"):
        raise AssetValidationError('side must be "left" or "right".')
    return resolved  # type: ignore[return-value]


def _normalize_orient(value: object) -> OrientationMode:
    resolved = str(value or "").strip().lower()
    if resolved not in ("maintain", "target"):
        raise AssetValidationError('orient must be "maintain" or "target".')
    return resolved  # type: ignore[return-value]


def _resolve_tip_offset(
    chain: _ArmChainSpec,
    tip_offset: Iterable[float] | None,
    *,
    orient: OrientationMode,
) -> Vector3:
    if tip_offset is None:
        return chain.default_tip_offset
    resolved = _vector3(tip_offset, label="tip_offset")
    if _length(resolved) <= _EPSILON:
        raise AssetValidationError("tip_offset must not be zero-length.")
    if chain.end_joint is not None and orient != "target":
        raise AssetValidationError(
            f'Rig "{chain.rig_id}" only supports tip_offset with orient="target" on hand-enabled rigs.',
        )
    return resolved


def _joint_local_position(pose: SerializedPoseDict, base_name: str, character_index: int) -> Vector3:
    joint_name = get_joint_name(base_name, character_index)
    transform = pose.get(joint_name)
    if transform is None:
        raise AssetValidationError(f'Missing joint "{joint_name}" in normalized pose.')
    return _vector3(transform["position"], label=f"{joint_name}.position")


def _build_world_transforms(
    pose: SerializedPoseDict,
    rig,
    character_index: int,
) -> dict[str, _JointWorldTransform]:
    world: dict[str, _JointWorldTransform] = {}
    for joint in rig.joints:
        joint_name = get_joint_name(joint.base_name, character_index)
        local = pose[joint_name]
        local_position = _vector3(local["position"], label=f"{joint_name}.position")
        local_quaternion = _quaternion(local["quaternion"], label=f"{joint_name}.quaternion")
        if joint.parent is None:
            world[joint.base_name] = _JointWorldTransform(local_position, local_quaternion)
            continue
        parent_world = world[joint.parent]
        world[joint.base_name] = _JointWorldTransform(
            position=_add(parent_world.position, _rotate_vector(parent_world.quaternion, local_position)),
            quaternion=_normalize_quaternion(
                _multiply_quaternions(parent_world.quaternion, local_quaternion),
            ),
        )
    return world


def _resolve_pole_point(
    pole: Iterable[float] | None,
    *,
    root_position: Vector3,
    parent_quaternion: Quaternion,
    default_pole_axis: Vector3,
) -> Vector3:
    if pole is not None:
        return _vector3(pole, label="pole")
    return _add(root_position, _rotate_vector(parent_quaternion, default_pole_axis))


def _solve_two_bone_positions(
    *,
    root_position: Vector3,
    target_position: Vector3,
    pole_position: Vector3,
    upper_length: float,
    lower_length: float,
    direction_fallback: Vector3,
) -> tuple[Vector3, Vector3]:
    to_target = _subtract(target_position, root_position)
    distance = _length(to_target)
    if distance <= _EPSILON:
        direction = _normalize(direction_fallback)
    else:
        direction = _scale(to_target, 1.0 / distance)

    pole_vector = _reject(_subtract(pole_position, root_position), direction)
    if _length(pole_vector) <= _EPSILON:
        pole_vector = _reject(direction_fallback, direction)
    if _length(pole_vector) <= _EPSILON:
        pole_vector = _orthogonal(direction)
    bend_direction = _normalize(pole_vector)

    minimum_reach = max(abs(upper_length - lower_length) + 1e-6, 1e-6)
    maximum_reach = max(upper_length + lower_length - 1e-6, minimum_reach)
    solved_distance = min(max(distance, minimum_reach), maximum_reach)
    effector_position = _add(root_position, _scale(direction, solved_distance))

    upper_projection = (solved_distance * solved_distance + upper_length * upper_length - lower_length * lower_length)
    upper_projection /= max(2.0 * solved_distance, _EPSILON)
    bend_height_sq = max(upper_length * upper_length - upper_projection * upper_projection, 0.0)
    bend_height = math.sqrt(bend_height_sq)
    elbow_position = _add(
        root_position,
        _add(
            _scale(direction, upper_projection),
            _scale(bend_direction, bend_height),
        ),
    )
    return elbow_position, effector_position


def _solve_bone_world_quaternion(
    *,
    local_forward: Vector3,
    local_side_axis: Vector3,
    desired_forward: Vector3,
    joint_position: Vector3,
    pole_position: Vector3,
    fallback_side: Vector3,
) -> Quaternion:
    local_basis = _orthonormal_basis(local_forward, local_side_axis, fallback_side)
    desired_side_hint = _subtract(pole_position, joint_position)
    world_basis = _orthonormal_basis(desired_forward, desired_side_hint, fallback_side)
    return _canonicalize_quaternion(
        _normalize_quaternion(
            _multiply_quaternions(
                _quaternion_from_basis(*world_basis),
                _conjugate(_quaternion_from_basis(*local_basis)),
            ),
        ),
    )


def _orthonormal_basis(
    forward: Vector3,
    side_hint: Vector3,
    fallback_side: Vector3,
) -> tuple[Vector3, Vector3, Vector3]:
    resolved_forward = _normalize(forward)
    side = _reject(side_hint, resolved_forward)
    if _length(side) <= _EPSILON:
        side = _reject(fallback_side, resolved_forward)
    if _length(side) <= _EPSILON:
        side = _orthogonal(resolved_forward)
    side = _normalize(side)
    up = _normalize(_cross(resolved_forward, side))
    side = _normalize(_cross(up, resolved_forward))
    return side, up, resolved_forward


def _quaternion_from_basis(side: Vector3, up: Vector3, forward: Vector3) -> Quaternion:
    matrix = (
        (side[0], up[0], forward[0]),
        (side[1], up[1], forward[1]),
        (side[2], up[2], forward[2]),
    )
    trace = matrix[0][0] + matrix[1][1] + matrix[2][2]
    if trace > 0.0:
        s = math.sqrt(trace + 1.0) * 2.0
        quaternion = (
            (matrix[2][1] - matrix[1][2]) / s,
            (matrix[0][2] - matrix[2][0]) / s,
            (matrix[1][0] - matrix[0][1]) / s,
            0.25 * s,
        )
    elif matrix[0][0] > matrix[1][1] and matrix[0][0] > matrix[2][2]:
        s = math.sqrt(1.0 + matrix[0][0] - matrix[1][1] - matrix[2][2]) * 2.0
        quaternion = (
            0.25 * s,
            (matrix[0][1] + matrix[1][0]) / s,
            (matrix[0][2] + matrix[2][0]) / s,
            (matrix[2][1] - matrix[1][2]) / s,
        )
    elif matrix[1][1] > matrix[2][2]:
        s = math.sqrt(1.0 + matrix[1][1] - matrix[0][0] - matrix[2][2]) * 2.0
        quaternion = (
            (matrix[0][1] + matrix[1][0]) / s,
            0.25 * s,
            (matrix[1][2] + matrix[2][1]) / s,
            (matrix[0][2] - matrix[2][0]) / s,
        )
    else:
        s = math.sqrt(1.0 + matrix[2][2] - matrix[0][0] - matrix[1][1]) * 2.0
        quaternion = (
            (matrix[0][2] + matrix[2][0]) / s,
            (matrix[1][2] + matrix[2][1]) / s,
            0.25 * s,
            (matrix[1][0] - matrix[0][1]) / s,
        )
    return _canonicalize_quaternion(_normalize_quaternion(quaternion))


def _vector3(value: object, *, label: str) -> Vector3:
    if isinstance(value, (str, bytes)):
        raise AssetValidationError(f"{label} must be a 3D vector.")
    try:
        values = tuple(value)
    except TypeError as error:
        raise AssetValidationError(f"{label} must be a 3D vector.") from error
    if len(values) < 3:
        raise AssetValidationError(f"{label} must contain 3 values.")
    numbers: list[float] = []
    for component in values[:3]:
        try:
            number = float(component)
        except (TypeError, ValueError) as error:
            raise AssetValidationError(f"{label} must contain finite numeric values.") from error
        if not math.isfinite(number):
            raise AssetValidationError(f"{label} must contain finite numeric values.")
        numbers.append(number)
    return (numbers[0], numbers[1], numbers[2])


def _quaternion(value: object, *, label: str) -> Quaternion:
    if isinstance(value, (str, bytes)):
        raise AssetValidationError(f"{label} must be a quaternion.")
    try:
        values = tuple(value)
    except TypeError as error:
        raise AssetValidationError(f"{label} must be a quaternion.") from error
    if len(values) < 4:
        raise AssetValidationError(f"{label} must contain 4 values.")
    numbers: list[float] = []
    for component in values[:4]:
        try:
            number = float(component)
        except (TypeError, ValueError) as error:
            raise AssetValidationError(f"{label} must contain finite numeric values.") from error
        if not math.isfinite(number):
            raise AssetValidationError(f"{label} must contain finite numeric values.")
        numbers.append(number)
    length = math.hypot(numbers[0], numbers[1], numbers[2], numbers[3])
    if length <= _EPSILON:
        raise AssetValidationError(f"{label} must not be zero-length.")
    return _canonicalize_quaternion((numbers[0] / length, numbers[1] / length, numbers[2] / length, numbers[3] / length))


def _normalize(vector: Vector3) -> Vector3:
    length = _length(vector)
    if length <= _EPSILON:
        return (0.0, 0.0, 0.0)
    return (vector[0] / length, vector[1] / length, vector[2] / length)


def _normalize_quaternion(quaternion: Quaternion) -> Quaternion:
    length = math.hypot(quaternion[0], quaternion[1], quaternion[2], quaternion[3])
    if length <= _EPSILON:
        return (0.0, 0.0, 0.0, 1.0)
    return (
        quaternion[0] / length,
        quaternion[1] / length,
        quaternion[2] / length,
        quaternion[3] / length,
    )


def _canonicalize_quaternion(quaternion: Quaternion) -> Quaternion:
    x, y, z, w = quaternion
    if w < 0.0 or (
        abs(w) <= _EPSILON
        and (x < 0.0 or (abs(x) <= _EPSILON and (y < 0.0 or (abs(y) <= _EPSILON and z < 0.0))))
    ):
        return (-x, -y, -z, -w)
    return quaternion


def _length(vector: Vector3) -> float:
    return math.sqrt(_dot(vector, vector))


def _dot(a: Vector3, b: Vector3) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a: Vector3, b: Vector3) -> Vector3:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _scale(vector: Vector3, scalar: float) -> Vector3:
    return (vector[0] * scalar, vector[1] * scalar, vector[2] * scalar)


def _add(a: Vector3, b: Vector3) -> Vector3:
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def _subtract(a: Vector3, b: Vector3) -> Vector3:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _reject(vector: Vector3, axis: Vector3) -> Vector3:
    axis_length_sq = _dot(axis, axis)
    if axis_length_sq <= _EPSILON:
        return vector
    return _subtract(vector, _scale(axis, _dot(vector, axis) / axis_length_sq))


def _orthogonal(vector: Vector3) -> Vector3:
    if abs(vector[0]) < abs(vector[1]):
        if abs(vector[0]) < abs(vector[2]):
            return _normalize(_cross(vector, (1.0, 0.0, 0.0)))
        return _normalize(_cross(vector, (0.0, 0.0, 1.0)))
    if abs(vector[1]) < abs(vector[2]):
        return _normalize(_cross(vector, (0.0, 1.0, 0.0)))
    return _normalize(_cross(vector, (0.0, 0.0, 1.0)))


def _multiply_quaternions(a: Quaternion, b: Quaternion) -> Quaternion:
    return (
        a[3] * b[0] + a[0] * b[3] + a[1] * b[2] - a[2] * b[1],
        a[3] * b[1] - a[0] * b[2] + a[1] * b[3] + a[2] * b[0],
        a[3] * b[2] + a[0] * b[1] - a[1] * b[0] + a[2] * b[3],
        a[3] * b[3] - a[0] * b[0] - a[1] * b[1] - a[2] * b[2],
    )


def _conjugate(quaternion: Quaternion) -> Quaternion:
    return (-quaternion[0], -quaternion[1], -quaternion[2], quaternion[3])


def _rotate_vector(quaternion: Quaternion, vector: Vector3) -> Vector3:
    vector_quaternion = (vector[0], vector[1], vector[2], 0.0)
    rotated = _multiply_quaternions(
        _multiply_quaternions(quaternion, vector_quaternion),
        _conjugate(quaternion),
    )
    return (rotated[0], rotated[1], rotated[2])


__all__ = [
    "solve_arm_to_target",
    "solve_mirrored_arms_to_targets",
]
