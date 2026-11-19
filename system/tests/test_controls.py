import os
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

import ast
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import numpy as np
import pygame

from setting import control_settings as settings
from setting import hand_controls
from system.camera import HandCamera
from system.controls import GameControls, preset_state
from system.game import Game
from system import app as main


def make_hand(side, gesture="กำมือ"):
    points = [SimpleNamespace(x=0.5, y=0.85, z=0.0) for _ in range(21)]
    for finger, joint, tip, x in ((0, 6, 8, 0.38), (1, 10, 12, 0.46),
                                   (2, 14, 16, 0.54), (3, 18, 20, 0.62)):
        opened = gesture == "แบมือ" or (gesture == "ชูนิ้วชี้" and finger == 0)
        opened = opened or (gesture == "ชูสองนิ้ว" and finger in (0, 1))
        points[joint] = SimpleNamespace(x=x, y=0.55, z=0.0)
        points[tip] = SimpleNamespace(x=x, y=0.2 if opened else 0.72, z=0.0)
    points[5] = SimpleNamespace(x=0.35, y=0.65, z=0.0)
    points[17] = SimpleNamespace(x=0.65, y=0.65, z=0.0)
    points[4] = SimpleNamespace(x=0.25, y=0.6, z=0.0)
    if gesture == "จีบนิ้ว":
        points[8] = SimpleNamespace(x=0.39, y=0.5, z=0.0)
        points[4] = SimpleNamespace(x=0.40, y=0.5, z=0.0)
    return {"side": side, "landmarks": points, "confidence": 0.99}


def make_pose(gesture="กลาง", side="Left"):
    points = [SimpleNamespace(x=0.5, y=0.5, z=0.0, visibility=0.99) for _ in range(33)]
    for index, x, y in ((11, 0.65, 0.4), (12, 0.35, 0.4), (23, 0.62, 0.75),
                        (24, 0.38, 0.75), (15, 0.7, 0.65), (16, 0.3, 0.65),
                        (7, 0.56, 0.18), (8, 0.44, 0.18)):
        points[index].x = x
        points[index].y = y
    if gesture == "ยกแขน":
        points[15 if side == "Left" else 16].y = 0.25
    elif gesture == "เอียงตัว":
        offset = 0.08 if side == "Left" else -0.08
        points[11].x += offset
        points[12].x += offset
    elif gesture == "เอียงศีรษะ":
        points[7 if side == "Left" else 8].y += 0.06
    return points


class PresetTests(unittest.TestCase):
    def setUp(self):
        self.config = patch.multiple(settings, USE_PRESET=True, LEFT_ACTION="กำมือซ้าย",
                                     RIGHT_ACTION="กำมือขวา", SENSITIVITY=1.0, HOLD_SECONDS=0.0)
        self.config.start()
        self.addCleanup(self.config.stop)

    def test_easy_file_contains_only_literal_settings(self):
        for statement in ast.parse(Path(settings.__file__).read_text(encoding="utf-8")).body:
            if isinstance(statement, ast.Expr):
                self.assertIsInstance(statement.value.value, str)
            else:
                self.assertIsInstance(statement, ast.Assign)
                ast.literal_eval(statement.value)

    def test_all_hand_presets_and_simultaneous_conflict(self):
        for gesture in ("กำมือ", "แบมือ", "ชูนิ้วชี้", "ชูสองนิ้ว", "จีบนิ้ว"):
            with self.subTest(gesture=gesture), patch.multiple(
                settings, LEFT_ACTION=gesture + "ซ้าย", RIGHT_ACTION=gesture + "ขวา",
            ):
                control = GameControls()
                self.assertTrue(control.detect_hands)
                self.assertFalse(control.detect_pose)
                left, right = make_hand("Left", gesture), make_hand("Right", gesture)
                self.assertEqual(control.update([left], [], 0), "LEFT")
                self.assertEqual(control.update([right], [], 0), "RIGHT")
                self.assertIsNone(control.update([left, right], [], 0))
                self.assertIsNone(control.update([], [], 0))

    def test_one_hand_can_choose_two_lanes_with_different_gestures(self):
        with patch.object(settings, "RIGHT_ACTION", "ชูนิ้วชี้ซ้าย"):
            control = GameControls()
            self.assertEqual(control.update([make_hand("Left")], [], 0), "LEFT")
            self.assertEqual(control.update([make_hand("Left", "ชูนิ้วชี้")], [], 0), "RIGHT")
            self.assertIsNone(control.update([make_hand("Left", "แบมือ")], [], 0))
            self.assertIsNone(control.update([make_hand("Right")], [], 0))

    def test_low_confidence_hand_does_not_trigger(self):
        hand = make_hand("Left")
        hand["confidence"] = 0.2
        control = GameControls()
        self.assertIsNone(control.update([hand], [], 0))
        self.assertFalse(control.left_seen)

    def test_all_pose_presets_use_subject_left_and_right(self):
        for gesture in ("ยกแขน", "เอียงตัว", "เอียงศีรษะ"):
            with self.subTest(gesture=gesture), patch.multiple(
                settings, LEFT_ACTION=gesture + "ซ้าย", RIGHT_ACTION=gesture + "ขวา",
            ):
                control = GameControls()
                self.assertFalse(control.detect_hands)
                self.assertTrue(control.detect_pose)
                self.assertEqual(control.update([], make_pose(gesture, "Left"), 0), "LEFT")
                self.assertEqual(control.update([], make_pose(gesture, "Right"), 0), "RIGHT")
                self.assertIsNone(control.update([], make_pose(), 0))
                self.assertIsNone(control.update([], [], 0))

    def test_both_raised_arms_and_hidden_points_hold_lane(self):
        with patch.multiple(settings, LEFT_ACTION="ยกแขนซ้าย", RIGHT_ACTION="ยกแขนขวา"):
            control = GameControls()
            pose = make_pose("ยกแขน", "Left")
            pose[16].y = 0.25
            self.assertIsNone(control.update([], pose, 0))
            pose[16].y = 0.65
            self.assertEqual(control.update([], pose, 0), "LEFT")
            pose[15].visibility = 0.1
            self.assertIsNone(control.update([], pose, 0))
            self.assertFalse(control.left_seen)

    def test_mixed_hand_and_pose_loads_both_and_handles_conflict(self):
        with patch.object(settings, "RIGHT_ACTION", "ยกแขนขวา"):
            control = GameControls()
            self.assertTrue(control.detect_hands and control.detect_pose)
            self.assertIsNone(control.update([make_hand("Left")], make_pose("ยกแขน", "Right"), 0))
            self.assertEqual(control.update([], make_pose("ยกแขน", "Right"), 0), "RIGHT")

    def test_sensitivity_changes_head_tilt_threshold(self):
        pose = make_pose("เอียงศีรษะ", "Left")
        with patch.object(settings, "SENSITIVITY", 0.5):
            self.assertFalse(preset_state("เอียงศีรษะซ้าย", [], pose)[0])
        with patch.object(settings, "SENSITIVITY", 1.5):
            self.assertTrue(preset_state("เอียงศีรษะซ้าย", [], pose)[0])

    def test_hold_uses_seconds_at_different_frame_rates(self):
        with patch.object(settings, "HOLD_SECONDS", 0.15):
            for fps in (10, 30, 60, 144):
                control = GameControls()
                hands = [make_hand("Left")]
                self.assertIsNone(control.update(hands, [], 10))
                elapsed = 0
                while control.command is None:
                    elapsed += 1 / fps
                    control.update(hands, [], 1 / fps)
                self.assertGreaterEqual(elapsed + 0.0000001, 0.15)
                self.assertLessEqual(elapsed, 0.15 + 1 / fps + 0.000001)
                self.assertIsNone(control.update([make_hand("Left"), make_hand("Right")], [], 1 / fps))
                self.assertEqual(control.held_seconds, 0)
                self.assertIsNone(control.update(hands, [], 1 / fps))

    def test_release_direction_change_and_restart_clear_old_hold(self):
        with patch.object(settings, "HOLD_SECONDS", 0.15):
            control = GameControls()
            control.update([make_hand("Left")], [], 0)
            self.assertEqual(control.update([make_hand("Left")], [], 0.2), "LEFT")
            self.assertIsNone(control.update([make_hand("Right")], [], 0.2))
            self.assertIsNone(control.update([], [], 0.2))
            self.assertIsNone(control.update([make_hand("Right")], [], 0.2))
            self.assertEqual(control.update([make_hand("Right")], [], 0.2), "RIGHT")
            control.reset()
            self.assertIsNone(control.command)
            self.assertIsNone(control.pending_command)
            self.assertEqual(control.held_seconds, 0)

    def test_invalid_action_and_ranges_are_explained(self):
        for key, value in (("LEFT_ACTION", "misspelled"),
                           ("RIGHT_ACTION", "กำมือซ้าย"), ("HOLD_SECONDS", -1), ("SENSITIVITY", 0)):
            with self.subTest(key=key), patch.object(settings, key, value):
                with self.assertRaisesRegex(ValueError, "control_settings.py"):
                    GameControls()


class ModeTests(unittest.TestCase):
    def setUp(self):
        self.config = patch.multiple(settings, USE_PRESET=True, LEFT_ACTION="กำมือซ้าย", RIGHT_ACTION="กำมือขวา", HOLD_SECONDS=0, SENSITIVITY=1.0)
        self.config.start()
        self.addCleanup(self.config.stop)

    def test_preset_does_not_call_custom_rules(self):
        with patch.object(hand_controls, "get_lane_command", side_effect=AssertionError("custom called")), patch.object(
            hand_controls, "is_hand_closed", return_value=False,
        ):
            self.assertEqual(GameControls().update([make_hand("Right")], [], 0), "RIGHT")

    def test_custom_ignores_preset_names_sensitivity_and_hold(self):
        with patch.multiple(settings, USE_PRESET=False, LEFT_ACTION="ignored", RIGHT_ACTION="ignored", SENSITIVITY=0, HOLD_SECONDS=100), patch.object(
            hand_controls, "get_lane_command", return_value="RIGHT",
        ) as custom:
            control = GameControls()
            self.assertEqual(control.update([], [], 0), "RIGHT")
            custom.assert_called_once_with([], [])

    def test_invalid_boolean_is_explained(self):
        for value in ("False", 0, 1, None):
            with self.subTest(value=value), patch.object(settings, "USE_PRESET", value):
                with self.assertRaisesRegex(ValueError, "True หรือ False"):
                    GameControls()

    def test_invalid_custom_return_value_is_checked(self):
        with patch.object(settings, "USE_PRESET", False), patch.object(hand_controls, "get_lane_command", return_value="WRONG"):
            with self.assertRaisesRegex(ValueError, "hand_controls.py"):
                GameControls().update([], [], 0)

    def test_custom_requires_a_detector(self):
        with patch.object(settings, "USE_PRESET", False), patch.multiple(hand_controls, USE_HANDS=False, USE_POSE=False):
            with self.assertRaisesRegex(ValueError, "USE_HANDS"):
                GameControls()

    def test_documented_custom_pose_rules_and_model_selection(self):
        source = Path("system/docs/CONTROL_DETAILS.md").read_text(encoding="utf-8")
        example = source.split("<!-- pose-custom-example -->")[1].split("```python\n")[1].split("```")[0]
        namespace = dict(vars(hand_controls))
        exec(example, namespace)
        with patch.object(settings, "USE_PRESET", False), patch.multiple(hand_controls, USE_HANDS=False, USE_POSE=True), patch.object(
            hand_controls, "control_states", namespace["control_states"],
        ):
            control = GameControls()
            self.assertTrue(control.detect_pose)
            self.assertFalse(control.detect_hands)
            self.assertEqual(control.update([], make_pose("ยกแขน", "Left"), 0), "LEFT")
            self.assertEqual(control.update([], make_pose("ยกแขน", "Right"), 0), "RIGHT")
            self.assertEqual(control.update([make_hand("Left")], make_pose("ยกแขน", "Right"), 0), "RIGHT")
            self.assertIsNone(control.update([], [], 0))
            pose = make_pose("ยกแขน", "Left")
            pose[16].y = 0.25
            self.assertIsNone(control.update([], pose, 0))
            pose[16].y = 0.65
            pose[15].visibility = 0.2
            self.assertIsNone(control.update([], pose, 0))

    def test_preset_and_custom_rules_reach_real_game_loop(self):
        for extra_enabled in (False, True):
            camera = Mock()
            camera.error = ""
            camera.pose_landmarks = []
            hands = [] if extra_enabled else [make_hand("Right")]
            camera.read.return_value = (np.zeros((480, 640, 3), dtype=np.uint8), hands)
            game = Game()
            click = pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=main.BUTTON.center)
            with self.subTest(custom=extra_enabled), patch.object(settings, "USE_PRESET", not extra_enabled), patch("system.app.HandCamera", return_value=camera), patch(
                "system.app.Game", return_value=game,
            ), patch("system.app.pygame.time.Clock", return_value=Mock()), patch(
                "system.app.time.perf_counter", side_effect=[0, 0, 1, 2],
            ), patch("system.app.pygame.event.get", side_effect=[[click], [], [pygame.event.Event(pygame.QUIT)]]), patch.object(
                hand_controls, "control_states", return_value=(False, extra_enabled),
            ):
                main.main()
                self.assertEqual(game.lane, 1)
            camera.close.assert_called_once()
            self.assertFalse(pygame.get_init())


class PoseCameraTests(unittest.TestCase):
    def test_real_pose_model_on_empty_frame_without_loading_hand_model(self):
        capture = Mock()
        capture.isOpened.return_value = True
        capture.read.return_value = (True, np.zeros((480, 640, 3), dtype=np.uint8))
        with patch("system.camera.cv2.VideoCapture", return_value=capture), patch(
            "system.camera.vision.HandLandmarker.create_from_options",
        ) as hand_factory:
            camera = HandCamera(detect_hands=False, detect_pose=True)
            try:
                self.assertEqual(camera.error, "")
                frame, hands = camera.read()
                self.assertEqual(camera.error, "")
                self.assertEqual(frame.shape, (480, 640, 3))
                self.assertEqual(hands, [])
                self.assertEqual(camera.pose_landmarks, [])
                hand_factory.assert_not_called()
            finally:
                camera.close()
            self.assertIsNone(camera.pose_landmarker)
            capture.release.assert_called_once()

    def test_missing_pose_frame_clears_previous_pose(self):
        capture = Mock()
        capture.isOpened.return_value = True
        capture.read.return_value = (True, np.zeros((480, 640, 3), dtype=np.uint8))
        detector = Mock()
        detector.detect_for_video.side_effect = [SimpleNamespace(pose_landmarks=[make_pose()]),
                                               SimpleNamespace(pose_landmarks=[])]
        with patch("system.camera.cv2.VideoCapture", return_value=capture), patch(
            "system.camera.vision.PoseLandmarker.create_from_options", return_value=detector,
        ):
            camera = HandCamera(detect_hands=False, detect_pose=True)
            camera.read()
            self.assertEqual(len(camera.pose_landmarks), 33)
            camera.read()
            self.assertEqual(camera.pose_landmarks, [])
            camera.close()
            detector.close.assert_called_once()

    def test_pose_initialization_failure_closes_already_loaded_hand_model(self):
        hand_detector = Mock()
        with patch("system.camera.vision.HandLandmarker.create_from_options", return_value=hand_detector), patch(
            "system.camera.vision.PoseLandmarker.create_from_options", side_effect=RuntimeError("pose failed"),
        ):
            camera = HandCamera(detect_hands=True, detect_pose=True)
            self.assertIn("pose failed", camera.error)
            hand_detector.close.assert_called_once()
            self.assertEqual(camera.pose_landmarks, [])
