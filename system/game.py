import random

import pygame

from setting import game_settings as settings

ROAD = pygame.Rect(40, 100, 440, 620)
LANE_CENTERS = (150, 370)
CAR_Y = 660


def validate_settings():
    if settings.START_SPEED <= 0 or settings.MAX_SPEED < settings.START_SPEED:
        raise ValueError("setting/game_settings.py: START_SPEED > 0 and MAX_SPEED >= START_SPEED required")
    if settings.ACCELERATION < 0 or settings.SCORE_PER_SECOND < 0:
        raise ValueError("setting/game_settings.py: ACCELERATION and SCORE_PER_SECOND must be >= 0")
    if settings.FIRST_OBSTACLE_DELAY < 0 or settings.REACTION_SECONDS <= 0:
        raise ValueError("setting/game_settings.py: FIRST_OBSTACLE_DELAY >= 0 and REACTION_SECONDS > 0 required")
    if settings.START_LANE not in (0, 1):
        raise ValueError("setting/game_settings.py: START_LANE must be 0 (left) or 1 (right)")
    if not (40 <= settings.CAR_WIDTH <= 180 and 60 <= settings.CAR_HEIGHT <= 100):
        raise ValueError("setting/game_settings.py: CAR_WIDTH must be 40-180 and CAR_HEIGHT 60-100")
    if not (80 <= settings.OBSTACLE_WIDTH <= 180 and 40 <= settings.OBSTACLE_HEIGHT <= 120):
        raise ValueError("setting/game_settings.py: OBSTACLE_WIDTH must be 80-180 and OBSTACLE_HEIGHT 40-120")


def obstacle_spacing():

    return settings.CAR_HEIGHT + settings.OBSTACLE_HEIGHT + settings.MAX_SPEED * settings.REACTION_SECONDS


def travel_distance(elapsed):
    if settings.ACCELERATION == 0:
        return settings.START_SPEED * elapsed
    acceleration_time = min(elapsed, (settings.MAX_SPEED - settings.START_SPEED) / settings.ACCELERATION)
    return (
        settings.START_SPEED * acceleration_time + 0.5 * settings.ACCELERATION * acceleration_time ** 2
        + settings.MAX_SPEED * (elapsed - acceleration_time)
    )


class Game:
    def __init__(self):
        validate_settings()
        self.reset()
        self.state = "MENU"

    def reset(self):
        self.state = "PLAYING"
        self.lane = settings.START_LANE
        self.elapsed = 0.0
        self.speed = settings.START_SPEED
        self.obstacles = []
        self.road_scroll = 0.0
        self.distance_since_spawn = 0.0
        self.first_spawn = True

    @property
    def score(self):
        return int(self.elapsed * settings.SCORE_PER_SECOND + 0.0000001)

    def player_rect(self):
        return pygame.Rect(LANE_CENTERS[self.lane] - settings.CAR_WIDTH // 2, CAR_Y - settings.CAR_HEIGHT // 2,
                           settings.CAR_WIDTH, settings.CAR_HEIGHT)

    def apply_command(self, command):
        if self.state == "PLAYING":
            if command == "LEFT":
                self.lane = 0
            elif command == "RIGHT":
                self.lane = 1

    def update(self, delta_seconds, command=None):
        if self.state != "PLAYING":
            return
        self.apply_command(command)


        time_left = max(0.0, delta_seconds)
        while time_left > 0.000000001 and self.state == "PLAYING":
            step = min(time_left, 1 / 120)
            old_distance = travel_distance(self.elapsed)
            self.elapsed += step
            movement = travel_distance(self.elapsed) - old_distance
            self.speed = min(settings.MAX_SPEED, settings.START_SPEED + settings.ACCELERATION * self.elapsed)
            self.road_scroll = (self.road_scroll + movement) % 90
            self.distance_since_spawn += movement

            for obstacle in self.obstacles:
                obstacle["y"] += movement

            if self.first_spawn and self.elapsed >= settings.FIRST_OBSTACLE_DELAY:
                self.spawn_obstacle()
            elif not self.first_spawn and self.distance_since_spawn >= obstacle_spacing():
                self.spawn_obstacle()

            player = self.player_rect()
            for obstacle in self.obstacles:
                obstacle_rect = pygame.Rect(
                    LANE_CENTERS[obstacle["lane"]] - settings.OBSTACLE_WIDTH // 2,
                    round(obstacle["y"]), settings.OBSTACLE_WIDTH, settings.OBSTACLE_HEIGHT,
                )
                if player.colliderect(obstacle_rect):
                    self.state = "GAME_OVER"
                    break
            self.obstacles = [obstacle for obstacle in self.obstacles if obstacle["y"] < ROAD.bottom]
            time_left -= step

    def spawn_obstacle(self):

        self.obstacles.append({"lane": random.randint(0, 1), "y": float(ROAD.top - settings.OBSTACLE_HEIGHT)})
        self.distance_since_spawn = 0.0
        self.first_spawn = False

    def draw(self, screen):
        pygame.draw.rect(screen, settings.GRASS_COLOR, ROAD.inflate(24, 0), border_radius=14)
        pygame.draw.rect(screen, settings.ROAD_COLOR, ROAD, border_radius=12)
        pygame.draw.line(screen, settings.ROAD_EDGE_COLOR, (ROAD.left + 12, ROAD.top + 8),
                         (ROAD.left + 12, ROAD.bottom - 8), 4)
        pygame.draw.line(screen, settings.ROAD_EDGE_COLOR, (ROAD.right - 12, ROAD.top + 8),
                         (ROAD.right - 12, ROAD.bottom - 8), 4)
        old_clip = screen.get_clip()
        screen.set_clip(ROAD)
        for y in range(ROAD.top - 90, ROAD.bottom, 90):
            pygame.draw.rect(screen, settings.LANE_MARKER_COLOR, (257, y + self.road_scroll, 6, 46), border_radius=3)
        for obstacle in self.obstacles:
            x = LANE_CENTERS[obstacle["lane"]] - settings.OBSTACLE_WIDTH // 2
            rect = pygame.Rect(x, round(obstacle["y"]), settings.OBSTACLE_WIDTH, settings.OBSTACLE_HEIGHT)
            pygame.draw.rect(screen, settings.OBSTACLE_COLOR, rect, border_radius=8)
            pygame.draw.rect(screen, (59, 47, 49), rect.inflate(-12, -26), border_radius=3)
            for offset in range(8, settings.OBSTACLE_WIDTH - 20, 32):
                pygame.draw.line(screen, (255, 221, 160), (x + offset, rect.y + 7),
                                 (x + offset + 15, rect.y + 7), 4)
        car = self.player_rect()
        for wheel_x in (car.left - 5, car.right - 3):
            for wheel_y in (car.top + 12, car.bottom - 28):
                pygame.draw.rect(screen, (15, 21, 33), (wheel_x, wheel_y, 8, 18), border_radius=3)
        pygame.draw.rect(screen, settings.CAR_COLOR, car, border_radius=13)
        pygame.draw.rect(screen, (24, 66, 88), car.inflate(-16, -44).move(0, -7), border_radius=6)
        for light_x in (car.left + 8, car.right - 16):
            pygame.draw.rect(screen, (255, 245, 180), (light_x, car.top + 5, 8, 5), border_radius=2)
        screen.set_clip(old_clip)
