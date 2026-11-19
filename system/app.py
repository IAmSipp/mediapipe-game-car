import time

import pygame

from system.controls import GameControls
from setting import game_settings as settings
from system.camera import HandCamera
from system.game import Game, ROAD


WINDOW_SIZE = (1120, 760)
BUTTON = pygame.Rect(100, 530, 320, 58)
BACKGROUND = (16, 24, 39)
WHITE = (236, 242, 250)
MUTED = (160, 178, 200)
TEAL = (58, 209, 199)


def text(screen, font, message, position, color=WHITE):
    screen.blit(font.render(message, True, color), position)


def handle_event(event, game, camera_ready):
    if event.type == pygame.QUIT:
        return False
    elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
        return False
    elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
        if BUTTON.collidepoint(event.pos) and camera_ready:
            if game.state == "MENU" or game.state == "GAME_OVER":
                game.reset()
    return True


def draw_screen(screen, game, camera_frame, hands, camera_error, font, small_font, title_font, control=None):
    if control is None:
        control = GameControls()
        control.update(hands, [], 0)
    screen.fill(BACKGROUND)
    text(screen, title_font, settings.GAME_TITLE, (40, 20))
    if game.state == "PLAYING":
        game.draw(screen)
        text(screen, font, f"คะแนน {game.score}", (540, 36))

    camera_rect = pygame.Rect(540, 128, 520, 390)
    if camera_frame is not None:
        image = pygame.image.frombuffer(camera_frame.tobytes(), (640, 480), "RGB")
        screen.blit(pygame.transform.smoothscale(image, camera_rect.size), camera_rect)
    else:
        pygame.draw.rect(screen, (25, 38, 57), camera_rect)
    if camera_error:
        if "camera" in camera_error.lower():
            text(screen, font, "เปิดกล้องไม่ได้", (560, 268))
            text(screen, small_font, "ปิดแอปอื่นที่ใช้กล้อง แล้วเปิดเกมใหม่", (560, 310), MUTED)
        else:
            text(screen, font, "ยังไม่พร้อมเริ่มเกม", (560, 268))
            text(screen, small_font, "แจ้งผู้สอนเพื่อตรวจการตั้งค่า", (560, 310), MUTED)
    elif camera_frame is None:
        text(screen, font, "กำลังเปิดกล้อง…", (560, 286), MUTED)
    else:
        if control.command == "LEFT":
            status = "ไปซ้าย"
        elif control.command == "RIGHT":
            status = "ไปขวา"
        elif not control.custom and control.pending_command is not None:
            status = "ค้างท่าอีกนิด"
        elif not control.left_seen and not control.right_seen:
            status = "ยังไม่พบท่าที่ใช้ควบคุม"
        else:
            status = "อยู่เลนเดิม"
        text(screen, font, status, (540, 542))

    if game.state == "PLAYING":
        text(screen, small_font, control.left_instruction, (540, 604), MUTED)
        text(screen, small_font, control.right_instruction, (540, 636), MUTED)
    else:
        if game.state == "MENU":
            text(screen, font, "วิธีเล่น", (92, 280))
            text(screen, small_font, control.left_instruction, (92, 344))
            text(screen, small_font, control.right_instruction, (92, 386))
            text(screen, small_font, "สั่งสองข้างพร้อมกัน = อยู่เลนเดิม", (92, 444), MUTED)
            button_label = "เริ่มเกม"
        else:
            text(screen, font, "จบเกม", (100, 280))
            text(screen, title_font, f"คะแนน {game.score}", (100, 350))
            button_label = "เล่นใหม่"
        ready = camera_frame is not None and not camera_error
        pygame.draw.rect(screen, TEAL if ready else (83, 98, 115), BUTTON, border_radius=4)
        label = font.render(button_label if ready else "ยังไม่พร้อม", True, BACKGROUND)
        screen.blit(label, label.get_rect(center=BUTTON.center))


def main(camera_index=0):
    pygame.init()
    camera = None
    try:
        screen = pygame.display.set_mode(WINDOW_SIZE)
        pygame.display.set_caption(settings.GAME_TITLE)
        font_names = "tahoma,leelawadeeui,notosansthai,thonburi,arial"
        font = pygame.font.SysFont(font_names, 24)
        small_font = pygame.font.SysFont(font_names, 20)
        title_font = pygame.font.SysFont(font_names, 42, bold=True)
        clock = pygame.time.Clock()
        game = Game()
        control = GameControls()

        draw_screen(screen, game, None, [], "", font, small_font, title_font, control)
        pygame.display.flip()
        camera = HandCamera(camera_index, detect_hands=control.detect_hands, detect_pose=control.detect_pose)
        reported_error = ""
        previous_time = time.perf_counter()
        running = True
        while running:
            clock.tick(60)
            camera_frame, hands = camera.read()
            now = time.perf_counter()
            delta_seconds = now - previous_time
            previous_time = now
            ready = camera_frame is not None and not camera.error
            state_before_events = game.state
            for event in pygame.event.get():
                if not handle_event(event, game, ready):
                    running = False
            if not running:
                break
            if state_before_events != "PLAYING" and game.state == "PLAYING":
                control.reset()
            else:
                control.update(hands, camera.pose_landmarks, delta_seconds)
            if camera.error:
                if camera.error != reported_error:
                    print(f"Camera/model: {camera.error}")
                    reported_error = camera.error
            elif state_before_events == "PLAYING" and game.state == "PLAYING":
                game.update(delta_seconds, control.command)

            draw_screen(screen, game, camera_frame, hands, camera.error, font, small_font, title_font, control)
            pygame.display.flip()
    finally:
        try:
            if camera is not None:
                camera.close()
        finally:
            pygame.quit()
