import pygame
import random
import math

# Initialize Pygame
pygame.init()

# Screen dimensions
SCREEN_WIDTH = 800
SCREEN_HEIGHT = 600


# Palette (matched to the arcade-racer reference: green shoulders, gray road,
# red/white + blue/white checkered curbs and pylons, punchy HUD panels)

BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
RED = (214, 40, 40)
DARK_RED = (150, 25, 25)
YELLOW = (255, 209, 51)
DARK_YELLOW = (196, 158, 25)
GRASS_GREEN = (58, 133, 58)
GRASS_GREEN_DARK = (48, 116, 48)
ROAD_GRAY = (90, 90, 94)
ROAD_GRAY_LINE = (255, 255, 255)
BLUE = (60, 110, 214)
SAND = (196, 168, 110)
UI_PANEL = (18, 18, 22)
UI_PANEL_BORDER = (240, 240, 240)
GREEN = (60, 200, 90)
CYAN_GLASS = (150, 210, 230)

# Screen setup
screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
pygame.display.set_caption("Race Game")
clock = pygame.time.Clock()
font = pygame.font.Font(None, 30)
big_font = pygame.font.Font(None, 74)
small_font = pygame.font.Font(None, 22)

ROAD_LEFT = 100
ROAD_RIGHT = SCREEN_WIDTH - 100
ROAD_WIDTH = ROAD_RIGHT - ROAD_LEFT
CURB_WIDTH = 14



# Helper: build a small pixel-art top-down car sprite on a transparent surface

def make_car_sprite(body_color, dark_color, width=40, height=62):
    surf = pygame.Surface((width, height), pygame.SRCALPHA)

    # Rear + front wheels (dark blocks poking out the sides)
    wheel_w, wheel_h = 8, 16
    pygame.draw.rect(surf, (25, 25, 25), (0, 6, wheel_w, wheel_h), border_radius=2)
    pygame.draw.rect(surf, (25, 25, 25), (width - wheel_w, 6, wheel_w, wheel_h), border_radius=2)
    pygame.draw.rect(surf, (25, 25, 25), (0, height - 22, wheel_w, wheel_h), border_radius=2)
    pygame.draw.rect(surf, (25, 25, 25), (width - wheel_w, height - 22, wheel_w, wheel_h), border_radius=2)

    # Main body (tapered hexagon-ish shape for a top-down car silhouette)
    body_rect = (6, 4, width - 12, height - 8)
    pygame.draw.rect(surf, body_color, body_rect, border_radius=10)

    # Nose highlight (front of car, pointing "up")
    nose_points = [(width // 2 - 9, 4), (width // 2 + 9, 4), (width // 2, 0)]
    pygame.draw.polygon(surf, body_color, nose_points)

    # Racing stripe
    pygame.draw.rect(surf, dark_color, (width // 2 - 4, 4, 8, height - 8))

    # Cockpit / windshield
    pygame.draw.ellipse(surf, CYAN_GLASS, (width // 2 - 9, 14, 18, 22))
    pygame.draw.ellipse(surf, (30, 30, 30), (width // 2 - 9, 14, 18, 22), 2)

    # Rear spoiler
    pygame.draw.rect(surf, dark_color, (8, height - 10, width - 16, 5), border_radius=2)

    return surf


# Pre-build sprites
PLAYER_SPRITE = make_car_sprite(RED, DARK_RED)
AI_SPRITE = make_car_sprite(YELLOW, DARK_YELLOW)



# Car class

class Car(pygame.sprite.Sprite):
    def __init__(self, x, y, is_player=True):
        super().__init__()
        self.base_image = PLAYER_SPRITE if is_player else AI_SPRITE
        self.image = self.base_image
        self.rect = self.image.get_rect()
        self.rect.x = x
        self.rect.y = y
        self.speed = 0
        self.max_speed = 10
        self.acceleration = 0.3
        self.friction = 0.15
        self.is_player = is_player

        # For steering "lean" visuals + smoothed AI avoidance
        self.tilt = 0
        self.target_tilt = 0
        self.ai_dodge_target = 0  # -1 left, 0 none, 1 right (smoothed, not instant)

    def update(self, keys=None, obstacles=None):
        steer_dir = 0

        if self.is_player and keys:
            # Player controls
            if keys[pygame.K_UP]:
                self.speed = min(self.speed + self.acceleration, self.max_speed)
            elif keys[pygame.K_DOWN]:
                self.speed = max(self.speed - self.acceleration, -3)
            else:
                if self.speed > 0:
                    self.speed = max(self.speed - self.friction, 0)
                elif self.speed < 0:
                    self.speed = min(self.speed + self.friction, 0)

            # Steering
            if keys[pygame.K_LEFT]:
                self.rect.x = max(self.rect.x - 5, ROAD_LEFT)
                steer_dir = -1
            if keys[pygame.K_RIGHT]:
                self.rect.x = min(self.rect.x + 5, ROAD_RIGHT - self.rect.width)
                steer_dir = 1
        else:
            # AI acceleration
            if self.speed < self.max_speed * 0.7:
                self.speed += self.acceleration * 0.5

            # Smooth obstacle avoidance: pick a dodge direction, then ease
            # toward it over several frames instead of snapping instantly.
            desired = 0
            if obstacles:
                for obstacle in obstacles:
                    if abs(self.rect.x - obstacle.rect.x) < 100 and abs(self.rect.y - obstacle.rect.y) < 150:
                        desired = 1 if self.rect.x < SCREEN_WIDTH // 2 else -1
                        break

            # Ease the dodge target toward the desired direction
            self.ai_dodge_target += (desired - self.ai_dodge_target) * 0.15
            move = self.ai_dodge_target * 4
            self.rect.x += move
            steer_dir = 1 if move > 0.5 else (-1 if move < -0.5 else 0)

        # Move forward/backward
        self.rect.y -= self.speed

        # Keep car on road
        self.rect.x = max(ROAD_LEFT, min(self.rect.x, ROAD_RIGHT - self.rect.width))

        # Wrap around screen
        if self.rect.top > SCREEN_HEIGHT:
            self.rect.bottom = 0
        elif self.rect.bottom < 0:
            self.rect.top = SCREEN_HEIGHT

        # Smooth tilt toward steering direction for a subtle "lean" effect
        self.target_tilt = steer_dir * -8
        self.tilt += (self.target_tilt - self.tilt) * 0.25
        self.image = pygame.transform.rotate(self.base_image, self.tilt)
        self.image_rect = self.image.get_rect(center=self.rect.center)

    def draw(self, surface):
        surface.blit(self.image, self.image_rect if hasattr(self, "image_rect") else self.rect)



class Obstacle(pygame.sprite.Sprite):
    def __init__(self, x, y):
        super().__init__()
        size = 40
        self.image = pygame.Surface((size, size), pygame.SRCALPHA)
        colors = random.choice([(RED, WHITE), (BLUE, WHITE)])
        half = size // 2
        pygame.draw.polygon(self.image, colors[0], [(half, 0), (size, half), (half, size), (0, half)])
        # Checker quarters
        pygame.draw.polygon(self.image, colors[1], [(half, 0), (size, half), (half, half)])
        pygame.draw.polygon(self.image, colors[1], [(half, half), (0, half), (half, size)])
        pygame.draw.polygon(self.image, (30, 30, 30), [(half, 0), (size, half), (half, size), (0, half)], 2)

        self.rect = self.image.get_rect()
        self.rect.x = x
        self.rect.y = y

    def update(self):
        self.rect.y += 5
        if self.rect.top > SCREEN_HEIGHT:
            self.rect.bottom = 0
            self.rect.x = random.randint(ROAD_LEFT + 20, ROAD_RIGHT - 60)

    def draw(self, surface):
        surface.blit(self.image, self.rect)



# HUD helpers: rounded translucent panels like the reference UI

def draw_panel(surface, rect, alpha=170):
    panel = pygame.Surface((rect[2], rect[3]), pygame.SRCALPHA)
    pygame.draw.rect(panel, (*UI_PANEL, alpha), (0, 0, rect[2], rect[3]), border_radius=8)
    pygame.draw.rect(panel, UI_PANEL_BORDER, (0, 0, rect[2], rect[3]), width=2, border_radius=8)
    surface.blit(panel, (rect[0], rect[1]))


def draw_progress_bar(surface, x, y, width, height, pct, fill_color, label):
    draw_panel(surface, (x, y, width, height), alpha=140)
    inner_pad = 3
    fill_w = int((width - inner_pad * 2) * max(0, min(pct, 1)))
    pygame.draw.rect(surface, fill_color, (x + inner_pad, y + inner_pad, fill_w, height - inner_pad * 2), border_radius=4)
    label_surf = small_font.render(label, True, WHITE)
    surface.blit(label_surf, (x + 6, y - 18))



# Game class

class RaceGame:
    def __init__(self):
        self.running = True
        self.player_car = Car(SCREEN_WIDTH // 2 - 20, SCREEN_HEIGHT - 100, is_player=True)
        self.ai_car = Car(SCREEN_WIDTH // 2 + 80, SCREEN_HEIGHT - 100, is_player=False)
        self.obstacles = [Obstacle(random.randint(ROAD_LEFT + 20, ROAD_RIGHT - 60), random.randint(-200, -50)) for _ in range(4)]
        self.distance = 0
        self.ai_distance = 0
        self.game_over = False
        self.winner = None
        self.scroll = 0  # for animating road dashes / curb stripes
        self.start_ticks = pygame.time.get_ticks()

    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.running = False
                if event.key == pygame.K_SPACE and self.game_over:
                    self.__init__()  # Restart game

    def handle_input(self):
        keys = pygame.key.get_pressed()
        self.player_car.update(keys=keys, obstacles=self.obstacles)

    def check_collisions(self):
        for obstacle in self.obstacles:
            if self.player_car.rect.colliderect(obstacle.rect):
                self.player_car.speed *= 0.5
                self.player_car.rect.y += 20

            if self.ai_car.rect.colliderect(obstacle.rect):
                self.ai_car.speed *= 0.5
                self.ai_car.rect.y += 20

    def update(self):
        if self.game_over:
            return

        self.ai_car.update(obstacles=self.obstacles)

        for obstacle in self.obstacles:
            obstacle.update()

        self.check_collisions()

        # Track distance
        self.distance += self.player_car.speed
        self.ai_distance += self.ai_car.speed
        self.scroll = (self.scroll + max(self.player_car.speed, 1)) % 50

        # Check win condition (first to 3000 distance)
        if self.distance >= 3000:
            self.game_over = True
            self.winner = "PLAYER"
        elif self.ai_distance >= 3000:
            self.game_over = True
            self.winner = "AI"

    def draw_track(self):
        screen.fill(GRASS_GREEN)

        # Alternating dark/light grass stripes for movement feel
        stripe_h = 50
        offset = int(self.scroll)
        for y in range(-stripe_h, SCREEN_HEIGHT + stripe_h, stripe_h):
            yy = y + offset
            color = GRASS_GREEN_DARK if (y // stripe_h) % 2 == 0 else GRASS_GREEN
            pygame.draw.rect(screen, color, (0, yy, ROAD_LEFT, stripe_h))
            pygame.draw.rect(screen, color, (ROAD_RIGHT, yy, SCREEN_WIDTH - ROAD_RIGHT, stripe_h))

        # Road surface
        pygame.draw.rect(screen, ROAD_GRAY, (ROAD_LEFT, 0, ROAD_WIDTH, SCREEN_HEIGHT))

        # Checkered curbs on both edges
        curb_h = 20
        for y in range(-curb_h, SCREEN_HEIGHT + curb_h, curb_h):
            yy = y + offset
            idx = y // curb_h
            c = WHITE if idx % 2 == 0 else RED
            pygame.draw.rect(screen, c, (ROAD_LEFT - CURB_WIDTH, yy, CURB_WIDTH, curb_h))
            pygame.draw.rect(screen, c, (ROAD_RIGHT, yy, CURB_WIDTH, curb_h))

        # Center dashed lane marker
        dash_h = 30
        for y in range(-dash_h, SCREEN_HEIGHT + dash_h, dash_h * 2):
            yy = y + offset
            pygame.draw.rect(screen, ROAD_GRAY_LINE, (SCREEN_WIDTH // 2 - 3, yy, 6, dash_h))

    def draw_hud(self):
        # Timer (top center)
        elapsed_ms = pygame.time.get_ticks() - self.start_ticks
        secs = elapsed_ms // 1000
        millis = (elapsed_ms % 1000) // 10
        timer_str = f"{secs:02}.{millis:02}"
        timer_surf = font.render(timer_str, True, WHITE)
        draw_panel(screen, (SCREEN_WIDTH // 2 - 60, 10, 120, 36))
        screen.blit(timer_surf, (SCREEN_WIDTH // 2 - timer_surf.get_width() // 2, 18))

        # Position panel (top left) — who's ahead based on distance
        leading = "YOU" if self.distance >= self.ai_distance else "AI"
        pos_str = "1ST" if leading == "YOU" else "2ND"
        draw_panel(screen, (14, 10, 90, 36))
        pos_surf = font.render(pos_str, True, YELLOW if leading == "YOU" else WHITE)
        screen.blit(pos_surf, (24, 18))

        # Speed panel (top right, small)
        speed_str = f"{self.player_car.speed:4.1f}"
        draw_panel(screen, (SCREEN_WIDTH - 110, 10, 96, 36))
        speed_surf = small_font.render(f"SPD {speed_str}", True, WHITE)
        screen.blit(speed_surf, (SCREEN_WIDTH - 100, 20))

        # Distance progress bars (right side, like the reference's meters)
        draw_progress_bar(screen, SCREEN_WIDTH - 230, 70, 200, 22, self.distance / 3000, RED, "YOU")
        draw_progress_bar(screen, SCREEN_WIDTH - 230, 118, 200, 22, self.ai_distance / 3000, YELLOW, "AI")

    def draw(self):
        self.draw_track()

        for obstacle in self.obstacles:
            obstacle.draw(screen)

        self.player_car.draw(screen)
        self.ai_car.draw(screen)

        self.draw_hud()

        # Game over screen
        if self.game_over:
            overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 190))
            screen.blit(overlay, (0, 0))

            draw_panel(screen, (SCREEN_WIDTH // 2 - 220, SCREEN_HEIGHT // 2 - 90, 440, 180), alpha=210)

            color = YELLOW if self.winner == "PLAYER" else RED
            winner_text = big_font.render(f"{self.winner} WINS!", True, color)
            restart_text = font.render("Press SPACE to restart or ESC to exit", True, WHITE)

            screen.blit(winner_text, (SCREEN_WIDTH // 2 - winner_text.get_width() // 2, SCREEN_HEIGHT // 2 - 60))
            screen.blit(restart_text, (SCREEN_WIDTH // 2 - restart_text.get_width() // 2, SCREEN_HEIGHT // 2 + 30))

        pygame.display.flip()

    def run(self):
        while self.running:
            self.handle_events()
            self.handle_input()
            self.update()
            self.draw()
            clock.tick(60)  # 60 FPS

        pygame.quit()


# Run the game
if __name__ == "__main__":
    game = RaceGame()
    game.run()