from __future__ import annotations

import math

from .model import (
    AuthoredRigSpec,
    AutoSkinSegmentSpec,
    GroundSegmentSpec,
    JointSpec,
    PosePreset,
    PoseTransform,
    PreviewGeometryHint,
    RigSpec,
    SegmentLayoutSpec,
    UalConversionSpec,
)

R11_CORE_ID = "r11_core"
AUTORIG_R18_ID = "autorig_r18"
NEUTRAL_BIND_ID = "neutral_bind"
RELAXED_PREVIEW_ID = "relaxed_preview"


def axis_angle_quaternion(axis: tuple[float, float, float], angle_radians: float) -> tuple[float, float, float, float]:
    axis_x, axis_y, axis_z = axis
    half_angle = angle_radians * 0.5
    sin_half = math.sin(half_angle)
    return (
        axis_x * sin_half,
        axis_y * sin_half,
        axis_z * sin_half,
        math.cos(half_angle),
    )


R11_CORE_JOINTS: tuple[JointSpec, ...] = (
    JointSpec("Hips", None, (0.0, 2.6, 0.0), (0.0, 0.0, 0.0, 1.0)),
    JointSpec("Spine", "Hips", (0.0, 0.2, 0.0), (0.0, 0.0, 0.0, 1.0)),
    JointSpec("Head", "Spine", (0.0, 1.2, 0.0), (0.0, 0.0, 0.0, 1.0)),
    JointSpec("Left_Upper_Arm", "Spine", (0.6, 1.1, 0.0), (0.0, 0.0, 0.0, 1.0)),
    JointSpec("Left_Lower_Arm", "Left_Upper_Arm", (0.0, -0.9, 0.0), (0.0, 0.0, 0.0, 1.0)),
    JointSpec("Right_Upper_Arm", "Spine", (-0.6, 1.1, 0.0), (0.0, 0.0, 0.0, 1.0)),
    JointSpec("Right_Lower_Arm", "Right_Upper_Arm", (0.0, -0.9, 0.0), (0.0, 0.0, 0.0, 1.0)),
    JointSpec("Left_Upper_Leg", "Hips", (0.25, -0.2, 0.0), (0.0, 0.0, 0.0, 1.0)),
    JointSpec("Left_Lower_Leg", "Left_Upper_Leg", (0.0, -1.1, 0.0), (0.0, 0.0, 0.0, 1.0)),
    JointSpec("Right_Upper_Leg", "Hips", (-0.25, -0.2, 0.0), (0.0, 0.0, 0.0, 1.0)),
    JointSpec("Right_Lower_Leg", "Right_Upper_Leg", (0.0, -1.1, 0.0), (0.0, 0.0, 0.0, 1.0)),
)

R11_CORE_PREVIEW_GEOMETRY = {
    "Hips": PreviewGeometryHint((1.0, 0.4, 0.6), 0.0),
    "Spine": PreviewGeometryHint((0.9, 1.2, 0.5), 0.6),
    "Head": PreviewGeometryHint((0.7, 0.8, 0.7), 0.4),
    "Left_Upper_Arm": PreviewGeometryHint((0.25, 0.9, 0.25), -0.45),
    "Left_Lower_Arm": PreviewGeometryHint((0.225, 0.9, 0.225), -0.45),
    "Right_Upper_Arm": PreviewGeometryHint((0.25, 0.9, 0.25), -0.45),
    "Right_Lower_Arm": PreviewGeometryHint((0.225, 0.9, 0.225), -0.45),
    "Left_Upper_Leg": PreviewGeometryHint((0.35, 1.1, 0.35), -0.55),
    "Left_Lower_Leg": PreviewGeometryHint((0.315, 1.1, 0.315), -0.55),
    "Right_Upper_Leg": PreviewGeometryHint((0.35, 1.1, 0.35), -0.55),
    "Right_Lower_Leg": PreviewGeometryHint((0.315, 1.1, 0.315), -0.55),
}

AUTORIG_EXTRA_JOINTS = {
    "Neck": JointSpec("Neck", "Spine", (0.0, 1.02, 0.0), (0.0, 0.0, 0.0, 1.0)),
    "Left_Shoulder": JointSpec("Left_Shoulder", "Spine", (0.42, 1.02, 0.0), (0.0, 0.0, 0.0, 1.0)),
    "Left_Hand": JointSpec("Left_Hand", "Left_Lower_Arm", (0.0, -0.88, 0.02), (0.0, 0.0, 0.0, 1.0)),
    "Right_Shoulder": JointSpec("Right_Shoulder", "Spine", (-0.42, 1.02, 0.0), (0.0, 0.0, 0.0, 1.0)),
    "Right_Hand": JointSpec("Right_Hand", "Right_Lower_Arm", (0.0, -0.88, 0.02), (0.0, 0.0, 0.0, 1.0)),
    "Left_Foot": JointSpec("Left_Foot", "Left_Lower_Leg", (0.0, -1.05, 0.18), (0.0, 0.0, 0.0, 1.0)),
    "Right_Foot": JointSpec("Right_Foot", "Right_Lower_Leg", (0.0, -1.05, 0.18), (0.0, 0.0, 0.0, 1.0)),
}

AUTORIG_R18_ORDER = (
    "Hips",
    "Spine",
    "Neck",
    "Head",
    "Left_Shoulder",
    "Left_Upper_Arm",
    "Left_Lower_Arm",
    "Left_Hand",
    "Right_Shoulder",
    "Right_Upper_Arm",
    "Right_Lower_Arm",
    "Right_Hand",
    "Left_Upper_Leg",
    "Left_Lower_Leg",
    "Left_Foot",
    "Right_Upper_Leg",
    "Right_Lower_Leg",
    "Right_Foot",
)


def build_autorig_r18_joints() -> tuple[JointSpec, ...]:
    core_by_name = {joint.base_name: joint for joint in R11_CORE_JOINTS}
    combined = {**core_by_name, **AUTORIG_EXTRA_JOINTS}
    return tuple(combined[name] for name in AUTORIG_R18_ORDER)


AUTORIG_SEGMENTS: tuple[SegmentLayoutSpec, ...] = (
    SegmentLayoutSpec("Hips", None, None, (1.0, 0.42, 0.6), "center", 0.42, 1, 0.0),
    SegmentLayoutSpec("Spine", "Hips", "Head", (0.9, 1.2, 0.5), "positive", 1.2, 6, 0.24),
    SegmentLayoutSpec("Neck", "Spine", "Head", (0.34, 0.3, 0.34), "positive", 0.3, 2, 0.2),
    SegmentLayoutSpec("Head", "Spine", None, (0.7, 0.8, 0.7), "positive", 0.8, 4, 0.22),
    SegmentLayoutSpec("Left_Shoulder", "Spine", "Left_Upper_Arm", (0.34, 0.24, 0.32), "center", 0.24, 1, 0.0),
    SegmentLayoutSpec("Left_Upper_Arm", "Spine", "Left_Lower_Arm", (0.25, 0.9, 0.25), "negative", 0.9, 6, 0.26),
    SegmentLayoutSpec("Left_Lower_Arm", "Left_Upper_Arm", "Left_Hand", (0.22, 0.9, 0.22), "negative", 0.9, 6, 0.24),
    SegmentLayoutSpec("Left_Hand", "Left_Lower_Arm", None, (0.26, 0.22, 0.28), "negative", 0.22, 1, 0.08),
    SegmentLayoutSpec("Right_Shoulder", "Spine", "Right_Upper_Arm", (0.34, 0.24, 0.32), "center", 0.24, 1, 0.0),
    SegmentLayoutSpec("Right_Upper_Arm", "Spine", "Right_Lower_Arm", (0.25, 0.9, 0.25), "negative", 0.9, 6, 0.26),
    SegmentLayoutSpec("Right_Lower_Arm", "Right_Upper_Arm", "Right_Hand", (0.22, 0.9, 0.22), "negative", 0.9, 6, 0.24),
    SegmentLayoutSpec("Right_Hand", "Right_Lower_Arm", None, (0.26, 0.22, 0.28), "negative", 0.22, 1, 0.08),
    SegmentLayoutSpec("Left_Upper_Leg", "Hips", "Left_Lower_Leg", (0.35, 1.1, 0.35), "negative", 1.1, 7, 0.24),
    SegmentLayoutSpec("Left_Lower_Leg", "Left_Upper_Leg", "Left_Foot", (0.31, 1.1, 0.31), "negative", 1.1, 7, 0.24),
    SegmentLayoutSpec("Left_Foot", "Left_Lower_Leg", None, (0.32, 0.22, 0.54), "center", 0.22, 1, 0.0),
    SegmentLayoutSpec("Right_Upper_Leg", "Hips", "Right_Lower_Leg", (0.35, 1.1, 0.35), "negative", 1.1, 7, 0.24),
    SegmentLayoutSpec("Right_Lower_Leg", "Right_Upper_Leg", "Right_Foot", (0.31, 1.1, 0.31), "negative", 1.1, 7, 0.24),
    SegmentLayoutSpec("Right_Foot", "Right_Lower_Leg", None, (0.32, 0.22, 0.54), "center", 0.22, 1, 0.0),
)

AUTORIG_AUTO_SKIN_SEGMENTS: tuple[AutoSkinSegmentSpec, ...] = (
    AutoSkinSegmentSpec("Hips", "Right_Upper_Leg", "Left_Upper_Leg", (-0.46, 2.48, 0.0), (0.46, 2.48, 0.0), 0.66, "core"),
    AutoSkinSegmentSpec("Spine", "Hips", "Spine", (0.0, 2.68, 0.0), (0.0, 3.52, 0.0), 0.62, "core"),
    AutoSkinSegmentSpec("Neck", "Spine", "Neck", (0.0, 3.48, 0.0), (0.0, 3.78, 0.0), 0.34, "neck"),
    AutoSkinSegmentSpec("Head", "Neck", "Head", (0.0, 3.76, 0.0), (0.0, 4.34, 0.0), 0.48, "head"),
    AutoSkinSegmentSpec("Left_Shoulder", "Spine", "Left_Shoulder", (0.26, 3.58, 0.0), (0.72, 3.66, 0.0), 0.34, "leftShoulder"),
    AutoSkinSegmentSpec("Left_Upper_Arm", "Left_Shoulder", "Left_Lower_Arm", (0.66, 3.58, 0.0), (0.7, 2.94, 0.0), 0.36, "leftArm"),
    AutoSkinSegmentSpec("Left_Lower_Arm", "Left_Lower_Arm", "Left_Hand", (0.7, 2.94, 0.0), (0.58, 2.22, 0.03), 0.34, "leftArm"),
    AutoSkinSegmentSpec("Left_Hand", "Left_Lower_Arm", "Left_Hand", (0.58, 2.26, 0.03), (0.5, 2.02, 0.08), 0.42, "leftHand"),
    AutoSkinSegmentSpec("Right_Shoulder", "Spine", "Right_Shoulder", (-0.26, 3.58, 0.0), (-0.72, 3.66, 0.0), 0.34, "rightShoulder"),
    AutoSkinSegmentSpec("Right_Upper_Arm", "Right_Shoulder", "Right_Lower_Arm", (-0.66, 3.58, 0.0), (-0.7, 2.94, 0.0), 0.36, "rightArm"),
    AutoSkinSegmentSpec("Right_Lower_Arm", "Right_Lower_Arm", "Right_Hand", (-0.7, 2.94, 0.0), (-0.58, 2.22, 0.03), 0.34, "rightArm"),
    AutoSkinSegmentSpec("Right_Hand", "Right_Lower_Arm", "Right_Hand", (-0.58, 2.26, 0.03), (-0.5, 2.02, 0.08), 0.42, "rightHand"),
    AutoSkinSegmentSpec("Left_Upper_Leg", "Left_Upper_Leg", "Left_Lower_Leg", (0.28, 2.38, 0.0), (0.3, 1.34, 0.0), 0.4, "leftLeg"),
    AutoSkinSegmentSpec("Left_Lower_Leg", "Left_Lower_Leg", "Left_Foot", (0.3, 1.34, 0.0), (0.26, 0.3, 0.02), 0.34, "leftLeg"),
    AutoSkinSegmentSpec("Left_Foot", "Left_Lower_Leg", "Left_Foot", (0.26, 0.28, 0.02), (0.26, 0.08, 0.34), 0.36, "leftFoot"),
    AutoSkinSegmentSpec("Right_Upper_Leg", "Right_Upper_Leg", "Right_Lower_Leg", (-0.28, 2.38, 0.0), (-0.3, 1.34, 0.0), 0.4, "rightLeg"),
    AutoSkinSegmentSpec("Right_Lower_Leg", "Right_Lower_Leg", "Right_Foot", (-0.3, 1.34, 0.0), (-0.26, 0.3, 0.02), 0.34, "rightLeg"),
    AutoSkinSegmentSpec("Right_Foot", "Right_Lower_Leg", "Right_Foot", (-0.26, 0.28, 0.02), (-0.26, 0.08, 0.34), 0.36, "rightFoot"),
)

UAL_DIRECTIONAL_TARGETS = {
    "Left_Shoulder": "Left_Upper_Arm",
    "Left_Upper_Arm": "Left_Lower_Arm",
    "Left_Lower_Arm": "Left_Hand",
    "Right_Shoulder": "Right_Upper_Arm",
    "Right_Upper_Arm": "Right_Lower_Arm",
    "Right_Lower_Arm": "Right_Hand",
    "Left_Upper_Leg": "Left_Lower_Leg",
    "Left_Lower_Leg": "Left_Foot",
    "Right_Upper_Leg": "Right_Lower_Leg",
    "Right_Lower_Leg": "Right_Foot",
}

UAL_GROUND_SEGMENTS = (
    GroundSegmentSpec("Right_Upper_Leg", "Left_Upper_Leg", 0.62),
    GroundSegmentSpec("Hips", "Spine", 0.58),
    GroundSegmentSpec("Spine", "Neck", 0.34),
    GroundSegmentSpec("Neck", "Head", 0.48),
    GroundSegmentSpec("Spine", "Left_Shoulder", 0.34),
    GroundSegmentSpec("Left_Shoulder", "Left_Lower_Arm", 0.36),
    GroundSegmentSpec("Left_Lower_Arm", "Left_Hand", 0.34),
    GroundSegmentSpec("Left_Lower_Arm", "Left_Hand", 0.42),
    GroundSegmentSpec("Spine", "Right_Shoulder", 0.34),
    GroundSegmentSpec("Right_Shoulder", "Right_Lower_Arm", 0.36),
    GroundSegmentSpec("Right_Lower_Arm", "Right_Hand", 0.34),
    GroundSegmentSpec("Right_Lower_Arm", "Right_Hand", 0.42),
    GroundSegmentSpec("Left_Upper_Leg", "Left_Lower_Leg", 0.4),
    GroundSegmentSpec("Left_Lower_Leg", "Left_Foot", 0.36),
    GroundSegmentSpec("Right_Upper_Leg", "Right_Lower_Leg", 0.4),
    GroundSegmentSpec("Right_Lower_Leg", "Right_Foot", 0.36),
)


def build_pose_presets() -> tuple[PosePreset, PosePreset]:
    autorig_joints = build_autorig_r18_joints()
    neutral_joints = {
        joint.base_name: PoseTransform(position=joint.position, quaternion=joint.quaternion)
        for joint in autorig_joints
    }
    relaxed_joints = dict(neutral_joints)
    relaxed_joints["Left_Upper_Arm"] = PoseTransform(
        position=neutral_joints["Left_Upper_Arm"].position,
        quaternion=axis_angle_quaternion((0.0, 0.0, 1.0), 0.2),
    )
    relaxed_joints["Right_Upper_Arm"] = PoseTransform(
        position=neutral_joints["Right_Upper_Arm"].position,
        quaternion=axis_angle_quaternion((0.0, 0.0, 1.0), -0.2),
    )
    relaxed_joints["Left_Upper_Leg"] = PoseTransform(
        position=neutral_joints["Left_Upper_Leg"].position,
        quaternion=axis_angle_quaternion((1.0, 0.0, 0.0), 0.05),
    )
    relaxed_joints["Right_Upper_Leg"] = PoseTransform(
        position=neutral_joints["Right_Upper_Leg"].position,
        quaternion=axis_angle_quaternion((1.0, 0.0, 0.0), -0.05),
    )
    return (
        PosePreset(NEUTRAL_BIND_ID, neutral_joints),
        PosePreset(RELAXED_PREVIEW_ID, relaxed_joints),
    )


def build_authored_spec() -> AuthoredRigSpec:
    autorig_r18_joints = build_autorig_r18_joints()
    neutral_bind, relaxed_preview = build_pose_presets()
    return AuthoredRigSpec(
        r11_core=RigSpec(
            rig_id=R11_CORE_ID,
            joints=R11_CORE_JOINTS,
            preview_geometry=R11_CORE_PREVIEW_GEOMETRY,
        ),
        autorig_r18=RigSpec(
            rig_id=AUTORIG_R18_ID,
            joints=autorig_r18_joints,
            preview_geometry={},
            derived_from=R11_CORE_ID,
            ual_conversion=UalConversionSpec(
                directional_targets=UAL_DIRECTIONAL_TARGETS,
                ground_segments=UAL_GROUND_SEGMENTS,
            ),
        ),
        neutral_bind=neutral_bind,
        relaxed_preview=relaxed_preview,
        autorig_segments=AUTORIG_SEGMENTS,
        autorig_auto_skin_segments=AUTORIG_AUTO_SKIN_SEGMENTS,
    )
