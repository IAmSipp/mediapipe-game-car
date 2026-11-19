import os
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"

from pathlib import Path
import ast
import random
import runpy
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import numpy as np
import pygame

from setting import hand_controls
from setting import game_settings as settings
from system.camera import HandCamera, draw_hands, mirrored_point
from system.game import Game, CAR_Y, LANE_CENTERS, obstacle_spacing, travel_distance
from system import app as main


def hand(side, closed=True, pointing=False):
    points = [SimpleNamespace(x=0.5, y=0.8, z=0.0) for _ in range(21)]
    for joint, tip in ((6, 8), (10, 12), (14, 16), (18, 20)):
        points[joint] = SimpleNamespace(x=0.5, y=0.5, z=0.0)
        points[tip] = SimpleNamespace(x=0.5, y=0.66 if closed else 0.25, z=0.0)
    if pointing:
        points[8].y = 0.25
    return {"side": side, "landmarks": points, "confidence": 0.99}


class LauncherTests(unittest.TestCase):
    def test_root_launcher_passes_camera_argument_to_game(self):
        launcher_path = Path(__file__).resolve().parents[2] / "main.py"
        with patch("system.app.main") as run_game, patch("sys.argv", [str(launcher_path), "--camera", "2"]):
            runpy.run_path(str(launcher_path), run_name="__main__")
        run_game.assert_called_once_with(2)


class HandControlTests(unittest.TestCase):
    def test_all_control_combinations(self):
        for left in (None, False, True):
            for right in (None, False, True):
                with self.subTest(left=left, right=right):
                    hands = []
                    if left is not None:
                        hands.append(hand("Left", left))
                    if right is not None:
                        hands.append(hand("Right", right))
                    expected = None
                    if left is True and right is not True:
                        expected = "LEFT"
                    elif right is True and left is not True:
                        expected = "RIGHT"
                    self.assertEqual(hand_controls.get_lane_command(hands), expected)
                    self.assertEqual(hand_controls.get_lane_command(list(reversed(hands))), expected)

    def test_held_fist_repeatedly_selects_lane(self):
        for _ in range(10):
            self.assertEqual(hand_controls.get_lane_command([hand("Right")]), "RIGHT")

    def test_one_open_finger_is_not_a_fist(self):
        self.assertFalse(hand_controls.is_hand_closed(hand("Left", pointing=True)["landmarks"]))

    def test_pointing_example_changes_only_control_file(self):
        source = Path("README.md").read_text(encoding="utf-8")
        example = source.split("<!-- pointing-example -->")[1].split("```python\n")[1].split("```")[0]
        namespace = dict(vars(hand_controls))
        exec(example, namespace)
        replacement = namespace["is_control_gesture"]
        with patch.object(hand_controls, "is_control_gesture", replacement):
            self.assertEqual(hand_controls.get_lane_command([hand("Left", pointing=True)]), "LEFT")
            self.assertEqual(hand_controls.get_lane_command([hand("Right", pointing=True)]), "RIGHT")
            self.assertIsNone(hand_controls.get_lane_command([hand("Left")]))
            self.assertIsNone(hand_controls.get_lane_command([hand("Left", closed=False)]))
            self.assertIsNone(hand_controls.get_lane_command([
                hand("Left", pointing=True), hand("Right", pointing=True),
            ]))


class GameTests(unittest.TestCase):
    def test_mouse_start_collision_and_restart(self):
        game = Game()
        self.assertEqual(game.state, "MENU")
        click = pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=main.BUTTON.center)
        main.handle_event(click, game, False)
        self.assertEqual(game.state, "MENU")
        main.handle_event(click, game, True)
        self.assertEqual(game.state, "PLAYING")
        game.update(0.7, "RIGHT")
        game.obstacles = [{"lane": 1, "y": float(CAR_Y - settings.CAR_HEIGHT // 2)}]
        game.update(0.05)
        self.assertEqual(game.state, "GAME_OVER")
        final_score = game.score
        game.update(10, "LEFT")
        self.assertEqual(game.score, final_score)
        main.handle_event(click, game, True)
        self.assertEqual(game.state, "PLAYING")
        self.assertEqual(game.score, 0)
        self.assertEqual(game.elapsed, 0)
        self.assertEqual(game.speed, settings.START_SPEED)
        self.assertEqual(game.obstacles, [])
        self.assertEqual(game.lane, 0)
        self.assertEqual(game.distance_since_spawn, 0)
        self.assertTrue(game.first_spawn)
        self.assertEqual(game.road_scroll, 0)

    def test_no_hand_open_hand_and_both_fists_keep_current_lane(self):
        game = Game()
        game.reset()
        for lane in (0, 1):
            game.lane = lane
            for hands in ([], [hand("Left", False)], [hand("Left"), hand("Right")]):
                game.update(0.01, hand_controls.get_lane_command(hands))
                self.assertEqual(game.lane, lane)

    def test_fist_selects_absolute_lane_and_can_avoid_collision(self):
        game = Game()
        game.reset()
        game.obstacles = [{"lane": 0, "y": float(CAR_Y - settings.CAR_HEIGHT // 2)}]
        for _ in range(5):
            game.update(0.01, hand_controls.get_lane_command([hand("Right")]))
        self.assertEqual(game.state, "PLAYING")
        self.assertEqual(game.lane, 1)

    def test_large_frame_cannot_tunnel_through_obstacle(self):
        game = Game()
        game.reset()
        game.obstacles = [{"lane": 0, "y": 500.0}]
        game.update(2)
        self.assertEqual(game.state, "GAME_OVER")
        self.assertLess(game.elapsed, 2)

    def test_score_and_speed_follow_real_time_at_different_fps(self):
        outcomes = []
        for fps in (10, 30, 60, 144):
            game = Game()
            game.reset()
            with patch.object(game, "spawn_obstacle"):
                for _ in range(fps * 80):
                    game.update(1 / fps)
            outcomes.append((game.score, game.speed, travel_distance(game.elapsed)))
        self.assertEqual([score for score, _, _ in outcomes], [int(80 * settings.SCORE_PER_SECOND)] * 4)
        for _, speed, distance in outcomes:
            self.assertAlmostEqual(speed, min(settings.MAX_SPEED, settings.START_SPEED + settings.ACCELERATION * 80), places=6)
            self.assertAlmostEqual(distance, travel_distance(80), places=5)

    def test_spawn_spacing_leaves_reaction_time_including_at_speed_cap(self):
        random.seed(42)
        game = Game()
        game.reset()
        spawn_distances = []
        spawned_lanes = set()
        original_spawn = game.spawn_obstacle

        def record_spawn():
            original_spawn()
            spawn_distances.append(travel_distance(game.elapsed))
            spawned_lanes.add(game.obstacles[-1]["lane"])

        duration = 180
        if settings.ACCELERATION > 0:
            duration = max(duration, int((settings.MAX_SPEED - settings.START_SPEED) / settings.ACCELERATION) + 10)

        with patch.object(game, "player_rect", return_value=pygame.Rect(-100, -100, 10, 10)), patch.object(
            game, "spawn_obstacle", side_effect=record_spawn,
        ):
            for _ in range(30 * duration):
                game.update(1 / 30)
        gaps = [second - first for first, second in zip(spawn_distances, spawn_distances[1:])]
        self.assertGreater(len(gaps), 1)
        self.assertGreaterEqual(min(gaps) + 0.00001, obstacle_spacing())
        self.assertEqual(spawned_lanes, {0, 1})
        safe_time = (min(gaps) - settings.CAR_HEIGHT - settings.OBSTACLE_HEIGHT) / settings.MAX_SPEED
        self.assertGreaterEqual(safe_time + 0.00001, settings.REACTION_SECONDS)
        self.assertEqual(game.state, "PLAYING")

    def test_menu_does_not_accumulate_score(self):
        game = Game()
        game.update(20)
        self.assertEqual(game.score, 0)

    def test_quit_and_escape(self):
        game = Game()
        self.assertFalse(main.handle_event(pygame.event.Event(pygame.QUIT), game, True))
        self.assertFalse(main.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE), game, True))


class SettingsTests(unittest.TestCase):
    def test_settings_contain_only_literal_game_data(self):
        source = Path(settings.__file__).read_text(encoding="utf-8")
        for statement in ast.parse(source).body:
            if isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Constant):
                self.assertIsInstance(statement.value.value, str)
            else:
                self.assertIsInstance(statement, ast.Assign)
                ast.literal_eval(statement.value)

    def test_tuned_settings_affect_movement_score_delay_size_and_restart(self):
        with patch.multiple(settings, START_SPEED=180.0, MAX_SPEED=360.0, ACCELERATION=0.0,
                            SCORE_PER_SECOND=25, START_LANE=1, FIRST_OBSTACLE_DELAY=10.0,
                            CAR_WIDTH=72, CAR_HEIGHT=100, OBSTACLE_WIDTH=120, OBSTACLE_HEIGHT=80):
            game = Game()
            game.reset()
            game.update(1.2)
            self.assertEqual(game.score, 30)
            self.assertEqual(game.speed, 180)
            self.assertEqual(game.lane, 1)
            self.assertEqual(game.player_rect().size, (72, 100))
            self.assertEqual(game.obstacles, [])
            game.obstacles = [{"lane": 0, "y": 100.0}]
            game.update(1.0)
            self.assertAlmostEqual(game.obstacles[0]["y"], 280.0)
            game.reset()
            self.assertEqual((game.score, game.speed, game.lane, game.obstacles), (0, 180, 1, []))
            self.assertAlmostEqual(travel_distance(100), 18000)

    def test_invalid_game_settings_are_explained(self):
        for name, value in (("START_SPEED", 0), ("MAX_SPEED", -1), ("ACCELERATION", -1),
                            ("SCORE_PER_SECOND", -1), ("FIRST_OBSTACLE_DELAY", -1),
                            ("REACTION_SECONDS", 0), ("START_LANE", 2),
                            ("CAR_WIDTH", 500), ("OBSTACLE_HEIGHT", 500)):
            with self.subTest(setting=name), patch.object(settings, name, value):
                with self.assertRaisesRegex(ValueError, "game_settings.py"):
                    Game()


class CameraTests(unittest.TestCase):
    def test_mirror_maps_landmarks_without_swapping_hand_labels(self):
        point = SimpleNamespace(x=0.2, y=0.5)
        self.assertEqual(mirrored_point(point, 641, 481), (512, 240))
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        hands = [hand("Left"), hand("Right")]
        draw_hands(frame, hands)
        self.assertTrue(frame.any())
        self.assertEqual([h["side"] for h in hands], ["Left", "Right"])

    def test_real_inference_on_empty_frame_and_resource_cleanup(self):
        fake_capture = Mock()
        fake_capture.isOpened.return_value = True
        fake_capture.read.return_value = (True, np.zeros((480, 640, 3), dtype=np.uint8))
        with patch("system.camera.cv2.VideoCapture", return_value=fake_capture):
            camera = HandCamera()
            self.assertEqual(camera.error, "")
            frame, hands = camera.read()
            self.assertEqual(camera.error, "")
            self.assertEqual(frame.shape, (480, 640, 3))
            self.assertEqual(hands, [])
            first_timestamp = camera.last_timestamp_ms
            camera.read()
            self.assertGreater(camera.last_timestamp_ms, first_timestamp)
            camera.close()
            camera.close()
            fake_capture.release.assert_called_once()
            self.assertIsNone(camera.landmarker)

    def test_camera_open_failure_releases_resources(self):
        capture = Mock()
        capture.isOpened.return_value = False
        landmarker = Mock()
        with patch("system.camera.cv2.VideoCapture", return_value=capture), patch(
            "system.camera.vision.HandLandmarker.create_from_options", return_value=landmarker,
        ):
            camera = HandCamera()
            self.assertIn("Camera unavailable", camera.error)
            self.assertEqual(camera.read(), (None, []))
            capture.release.assert_called_once()
            landmarker.close.assert_called_once()

    def test_read_failure_clears_old_hands(self):
        capture = Mock()
        capture.isOpened.return_value = True
        capture.read.return_value = (False, None)
        landmarker = Mock()
        with patch("system.camera.cv2.VideoCapture", return_value=capture), patch(
            "system.camera.vision.HandLandmarker.create_from_options", return_value=landmarker,
        ):
            camera = HandCamera()
            self.assertEqual(camera.read(), (None, []))
            self.assertIn("disconnected", camera.error)
            capture.release.assert_called_once()
            landmarker.close.assert_called_once()

    def test_missing_model_is_explained(self):
        with patch("system.camera.MODEL_PATH") as model_path:
            model_path.is_file.return_value = False
            camera = HandCamera()
        self.assertIn("python -m system.download_model", camera.error)
        self.assertEqual(camera.read(), (None, []))


class ScreenTests(unittest.TestCase):
    def setUp(self):
        pygame.init()
        self.screen = pygame.display.set_mode(main.WINDOW_SIZE)
        names = "tahoma,leelawadeeui,notosansthai,arial"
        self.font = pygame.font.SysFont(names, 24)
        self.small_font = pygame.font.SysFont(names, 20)
        self.title_font = pygame.font.SysFont(names, 42, bold=True)

    def tearDown(self):
        pygame.quit()

    def test_render_all_screens(self):
        output = Path("system/artifacts")
        output.mkdir(exist_ok=True)
        frame = np.full((480, 640, 3), (28, 44, 65), dtype=np.uint8)
        game = Game()
        cases = [("menu", "MENU", ""), ("playing", "PLAYING", ""),
                 ("game_over", "GAME_OVER", ""), ("camera_error", "MENU", "Camera unavailable")]
        for filename, state, error in cases:
            with self.subTest(state=state, error=error):
                game.state = state
                main.draw_screen(self.screen, game, None if error else frame, [], error,
                                 self.font, self.small_font, self.title_font)
                pygame.image.save(self.screen, output / f"{filename}.png")

    def test_tuned_colors_are_used_in_rendered_game(self):
        with patch.multiple(settings, CAR_COLOR=(250, 20, 40), ROAD_COLOR=(35, 45, 55),
                            OBSTACLE_COLOR=(65, 75, 85)):
            game = Game()
            game.reset()
            game.obstacles = [{"lane": 1, "y": 200.0}]
            game.draw(self.screen)
            self.assertEqual(self.screen.get_at((LANE_CENTERS[0], game.player_rect().bottom - 10))[:3],
                             settings.CAR_COLOR)
            self.assertEqual(self.screen.get_at((80, 200))[:3], settings.ROAD_COLOR)
            self.assertEqual(self.screen.get_at((LANE_CENTERS[1], 210))[:3], settings.OBSTACLE_COLOR)

    def test_main_loop_closes_camera_and_window_on_quit(self):
        camera = Mock()
        camera.error = ""
        camera.read.return_value = (np.zeros((480, 640, 3), dtype=np.uint8), [])
        with patch("system.app.HandCamera", return_value=camera), patch(
            "system.app.pygame.event.get", return_value=[pygame.event.Event(pygame.QUIT)],
        ):
            main.main()
        camera.close.assert_called_once()
        self.assertFalse(pygame.get_init())

    def test_full_main_loop_start_crash_restart_without_menu_time(self):
        camera = Mock()
        camera.error = ""
        camera.read.return_value = (np.zeros((480, 640, 3), dtype=np.uint8), [])
        click = pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=main.BUTTON.center)
        quit_event = pygame.event.Event(pygame.QUIT)
        states = []

        def record_screen(screen, game, *args):
            states.append((game.state, game.score, game.lane, len(game.obstacles)))

        with patch("system.app.HandCamera", return_value=camera), patch(
            "system.app.pygame.time.Clock", return_value=Mock(),
        ), patch("system.app.time.perf_counter", side_effect=[0, 50, 51, 52, 53, 54, 55, 56]), patch(
            "system.app.pygame.event.get", side_effect=[[click], [], [], [], [], [click], [quit_event]],
        ), patch("system.app.draw_screen", side_effect=record_screen), patch("system.game.random.randint", return_value=0):
            main.main()

        self.assertEqual(states[0][:2], ("MENU", 0))
        self.assertEqual(states[1][:2], ("PLAYING", 0))
        self.assertEqual(states[2][:2], ("PLAYING", 10))
        self.assertEqual(states[-2][0], "GAME_OVER")
        self.assertGreater(states[-2][1], 0)
        self.assertEqual(states[-1], ("PLAYING", 0, 0, 0))
        camera.close.assert_called_once()
        self.assertFalse(pygame.get_init())

    def test_unexpected_error_still_closes_camera_and_window(self):
        camera = Mock()
        camera.read.side_effect = RuntimeError("simulated unexpected failure")
        with patch("system.app.HandCamera", return_value=camera):
            with self.assertRaisesRegex(RuntimeError, "unexpected failure"):
                main.main()
        camera.close.assert_called_once()
        self.assertFalse(pygame.get_init())


if __name__ == "__main__":
    unittest.main()
