#!/usr/bin/env python3
"""Build a stable stylized clapping clip for the r11_core rig."""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from animateur_rig import Pose, new_animation

RIG_ID = "r11_core"
DEFAULT_OUTPUT = REPO_ROOT / "Animations" / "clapping.animation.json"

READY = {
    "top_lift": 1.00,
    "top_swing": 0.06,
    "top_elbow": 0.55,
    "bot_lift": 0.92,
    "bot_swing": 0.06,
    "bot_elbow": 0.50,
    "spine_lean": 0.05,
    "head_tilt": 0.06,
}

WINDUP = {
    "top_lift": 0.92,
    "top_swing": 0.00,
    "top_elbow": 0.35,
    "bot_lift": 0.86,
    "bot_swing": 0.00,
    "bot_elbow": 0.30,
    "spine_lean": 0.03,
    "head_tilt": 0.04,
}

CLAP = {
    "top_lift": 1.32,
    "top_swing": 0.40,
    "top_elbow": 0.60,
    "bot_lift": 1.26,
    "bot_swing": 0.40,
    "bot_elbow": 0.60,
    "spine_lean": 0.10,
    "head_tilt": 0.12,
}

FIRM = {
    "top_lift": 1.36,
    "top_swing": 0.42,
    "top_elbow": 0.60,
    "bot_lift": 1.26,
    "bot_swing": 0.42,
    "bot_elbow": 0.55,
    "spine_lean": 0.12,
    "head_tilt": 0.14,
}


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


def multiply_quaternions(
    left: tuple[float, float, float, float],
    right: tuple[float, float, float, float],
) -> tuple[float, float, float, float]:
    return (
        left[3] * right[0] + left[0] * right[3] + left[1] * right[2] - left[2] * right[1],
        left[3] * right[1] - left[0] * right[2] + left[1] * right[3] + left[2] * right[0],
        left[3] * right[2] + left[0] * right[1] - left[1] * right[0] + left[2] * right[3],
        left[3] * right[3] - left[0] * right[0] - left[1] * right[1] - left[2] * right[2],
    )


def upper_arm_quaternion(is_left: bool, lift: float, swing: float) -> tuple[float, float, float, float]:
    sign = 1.0 if is_left else -1.0
    lift_quaternion = axis_angle_quaternion((1.0, 0.0, 0.0), -lift)
    swing_quaternion = axis_angle_quaternion((0.0, 0.0, 1.0), -sign * swing)
    return multiply_quaternions(swing_quaternion, lift_quaternion)


def elbow_quaternion(is_left: bool, bend: float) -> tuple[float, float, float, float]:
    sign = 1.0 if is_left else -1.0
    return axis_angle_quaternion((0.0, 0.0, 1.0), -sign * bend)


def build_clap_pose(
    *,
    top_lift: float,
    top_swing: float,
    top_elbow: float,
    bot_lift: float,
    bot_swing: float,
    bot_elbow: float,
    spine_lean: float,
    head_tilt: float,
) -> Pose:
    pose = Pose.default(rig_id=RIG_ID, character_count=1)
    pose.set_rotation("Left_Upper_Arm", quaternion=upper_arm_quaternion(True, top_lift, top_swing))
    pose.set_rotation("Right_Upper_Arm", quaternion=upper_arm_quaternion(False, bot_lift, bot_swing))
    pose.set_rotation("Left_Lower_Arm", quaternion=elbow_quaternion(True, top_elbow))
    pose.set_rotation("Right_Lower_Arm", quaternion=elbow_quaternion(False, bot_elbow))
    pose.set_rotation("Spine", axis=(1.0, 0.0, 0.0), angle_radians=spine_lean)
    pose.set_rotation("Head", axis=(1.0, 0.0, 0.0), angle_radians=head_tilt)
    return pose


def stabilize_quaternion_signs(clip) -> None:
    previous_pose = None
    for frame in clip.keyframes:
        current_pose = frame.pose.normalized()
        if previous_pose is None:
            previous_pose = current_pose
            continue
        for joint_name, transform in current_pose.items():
            previous_quaternion = previous_pose[joint_name]["quaternion"]
            current_quaternion = transform["quaternion"]
            dot = sum(previous_quaternion[index] * current_quaternion[index] for index in range(4))
            if dot >= 0.0:
                continue
            base_name, character_index_text = joint_name.rsplit("_", 1)
            frame.pose.set_rotation(
                base_name,
                quaternion=tuple(-value for value in current_quaternion),
                character_index=int(character_index_text),
            )
            current_pose[joint_name]["quaternion"] = [-value for value in current_quaternion]
        previous_pose = current_pose


def build_clip():
    clip = new_animation(
        "Clapping",
        rig=RIG_ID,
        character_count=1,
        character_colors=["#fcd34d"],
        playback_speed=1.0,
        saved_at="2026-04-20T00:00:00.000Z",
    )
    for time, params in (
        (0.00, READY),
        (0.18, WINDUP),
        (0.32, CLAP),
        (0.50, WINDUP),
        (0.64, CLAP),
        (0.82, WINDUP),
        (0.96, CLAP),
        (1.20, FIRM),
        (1.60, FIRM),
    ):
        clip.add_keyframe(time, build_clap_pose(**params))
    stabilize_quaternion_signs(clip)
    return clip


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Where to write the animation JSON. Defaults to {DEFAULT_OUTPUT}.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    clip = build_clip()
    output_path = args.output.resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(clip.to_json() + "\n", encoding="utf-8")
    print(f"Wrote {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
