from __future__ import annotations

import math
import unittest

from animateur_rig import Pose, new_animation
from animateur_rig.ik import solve_arm_to_target, solve_mirrored_arms_to_targets


def _q_mul(a, b):
    return (
        a[3] * b[0] + a[0] * b[3] + a[1] * b[2] - a[2] * b[1],
        a[3] * b[1] - a[0] * b[2] + a[1] * b[3] + a[2] * b[0],
        a[3] * b[2] + a[0] * b[1] - a[1] * b[0] + a[2] * b[3],
        a[3] * b[3] - a[0] * b[0] - a[1] * b[1] - a[2] * b[2],
    )


def _q_conj(quaternion):
    return (-quaternion[0], -quaternion[1], -quaternion[2], quaternion[3])


def _q_rotate(quaternion, vector):
    rotated = _q_mul(
        _q_mul(quaternion, (vector[0], vector[1], vector[2], 0.0)),
        _q_conj(quaternion),
    )
    return rotated[:3]


def _axis_angle(axis, angle_radians):
    half_angle = angle_radians * 0.5
    sin_half = math.sin(half_angle)
    return (
        axis[0] * sin_half,
        axis[1] * sin_half,
        axis[2] * sin_half,
        math.cos(half_angle),
    )


def _world_transforms(pose, rig_id):
    from animateur_rig import get_rig

    rig = get_rig(rig_id)
    normalized = pose.normalized()
    world_positions = {}
    world_quaternions = {}
    for joint in rig.joints:
        local = normalized[f"{joint.base_name}_0"]
        local_position = tuple(local["position"])
        local_quaternion = tuple(local["quaternion"])
        if joint.parent is None:
            world_positions[joint.base_name] = local_position
            world_quaternions[joint.base_name] = local_quaternion
            continue
        parent_position = world_positions[joint.parent]
        parent_quaternion = world_quaternions[joint.parent]
        world_positions[joint.base_name] = tuple(
            parent_position[index] + _q_rotate(parent_quaternion, local_position)[index]
            for index in range(3)
        )
        world_quaternions[joint.base_name] = _q_mul(parent_quaternion, local_quaternion)
    return world_positions, world_quaternions


def _r11_tip_position(pose, side):
    world_positions, world_quaternions = _world_transforms(pose, "r11_core")
    joint_name = f"{side}_Lower_Arm"
    tip_offset = (0.0, -0.9, 0.0)
    return tuple(
        world_positions[joint_name][index] + _q_rotate(world_quaternions[joint_name], tip_offset)[index]
        for index in range(3)
    )


def _autorig_hand_pose(pose, side):
    world_positions, world_quaternions = _world_transforms(pose, "autorig_r18")
    joint_name = f"{side}_Hand"
    return world_positions[joint_name], world_quaternions[joint_name]


def _same_rotation(a, b, tolerance=1e-6):
    magnitude_a = math.sqrt(sum(component * component for component in a))
    magnitude_b = math.sqrt(sum(component * component for component in b))
    normalized_a = tuple(component / magnitude_a for component in a)
    normalized_b = tuple(component / magnitude_b for component in b)
    dot = sum(normalized_a[index] * normalized_b[index] for index in range(4))
    return abs(dot) >= 1.0 - tolerance


class AnimateurRigIkTests(unittest.TestCase):
    def test_r11_core_arm_target_reach_within_tolerance(self):
        pose = Pose.default(rig_id="r11_core", character_count=1)
        target = (0.22, 2.68, 0.26)

        solve_arm_to_target(pose, "left", target)

        solved_tip = _r11_tip_position(pose, "Left")
        self.assertLess(math.dist(solved_tip, target), 1e-5)

    def test_autorig_r18_reaches_target_orientation_and_tip_offset(self):
        pose = Pose.default(rig_id="autorig_r18", character_count=1)
        target = (0.18, 2.48, 0.34)
        tip_offset = (0.0, -0.18, 0.04)
        target_orientation = _axis_angle((0.0, 0.0, 1.0), 0.35)

        solve_arm_to_target(
            pose,
            "left",
            target,
            orient="target",
            tip_offset=tip_offset,
            target_orientation=target_orientation,
        )

        hand_position, hand_quaternion = _autorig_hand_pose(pose, "Left")
        solved_contact = tuple(
            hand_position[index] + _q_rotate(hand_quaternion, tip_offset)[index]
            for index in range(3)
        )
        self.assertLess(math.dist(solved_contact, target), 1e-5)
        self.assertTrue(_same_rotation(hand_quaternion, target_orientation))

    def test_mirrored_arm_solve_is_symmetric(self):
        pose = Pose.default(rig_id="r11_core", character_count=1)
        left_target = (0.14, 2.56, 0.30)
        right_target = (-0.14, 2.56, 0.30)

        solve_mirrored_arms_to_targets(pose, left_target, right_target)

        left_tip = _r11_tip_position(pose, "Left")
        right_tip = _r11_tip_position(pose, "Right")
        self.assertLess(math.dist(left_tip, left_target), 1e-5)
        self.assertLess(math.dist(right_tip, right_target), 1e-5)
        self.assertAlmostEqual(left_tip[0], -right_tip[0], places=5)
        self.assertAlmostEqual(left_tip[1], right_tip[1], places=5)
        self.assertAlmostEqual(left_tip[2], right_tip[2], places=5)

    def test_maintain_orient_preserves_hand_local_quaternion(self):
        pose = Pose.default(rig_id="autorig_r18", character_count=1)
        pose.set_rotation("Left_Hand", quaternion=_axis_angle((1.0, 0.0, 0.0), 0.27))
        before = tuple(pose.normalized()["Left_Hand_0"]["quaternion"])

        solve_arm_to_target(pose, "left", (0.26, 2.70, 0.18), orient="maintain")

        after = tuple(pose.normalized()["Left_Hand_0"]["quaternion"])
        self.assertTrue(_same_rotation(before, after))

    def test_baked_output_is_deterministic(self):
        def build_clip_dict():
            clip = new_animation(
                "ik-clap",
                rig="r11_core",
                character_count=1,
                saved_at="2026-04-20T00:00:00.000Z",
            )
            for time, left_target, right_target in (
                (0.0, (0.48, 2.58, 0.16), (-0.48, 2.58, 0.16)),
                (0.12, (0.10, 2.54, 0.34), (-0.10, 2.54, 0.34)),
            ):
                pose = Pose.default(rig_id="r11_core", character_count=1)
                solve_mirrored_arms_to_targets(pose, left_target, right_target)
                clip.add_keyframe(time, pose)
            return clip.to_dict()

        self.assertEqual(build_clip_dict(), build_clip_dict())

    def test_json_contract_remains_unchanged(self):
        pose = Pose.default(rig_id="r11_core", character_count=1)
        solve_arm_to_target(pose, "left", (0.20, 2.66, 0.24))

        clip = new_animation("ik-pose", rig="r11_core", character_count=1)
        clip.add_keyframe(0.0, pose)
        asset = clip.to_dict()

        self.assertEqual(
            set(asset.keys()),
            {"format", "version", "type", "name", "savedAt", "scene", "playbackSpeed", "effects", "keyframes"},
        )
        self.assertEqual(set(asset["keyframes"][0]["pose"]["Left_Upper_Arm_0"].keys()), {"position", "quaternion"})
        self.assertEqual(set(asset["keyframes"][0]["pose"]["Left_Lower_Arm_0"].keys()), {"position", "quaternion"})


if __name__ == "__main__":
    unittest.main()
