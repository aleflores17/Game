import pygame
import random

# Initialize Pygame
pygame.init()

# Screen dimensions
SCREEN_WIDTH = 800
SCREEN_HEIGHT = 600

# Colors
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
RED = (255, 0, 0)
YELLOW = (255, 255, 0)
GRAY = (128, 128, 128)
GREEN = (0, 255, 0)

# Screen setup
screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
pygame.display.set_caption("Race Game")
clock = pygame.time.Clock()
font = pygame.font.Font(None, 36)
big_font = pygame.font.Font(None, 74)

# Car class
class Car(pygame.sprite.Sprite):
    def __init__(self, x, y, is_player=True):
        super().__init__()
        self.image = pygame.Surface((40, 60))
        self.image.fill(RED if is_player else YELLOW)
        self.rect = self.image.get_rect()
        self.rect.x = x
        self.rect.y = y
        self.speed = 0
        self.max_speed = 10
        self.acceleration = 0.3
        self.friction = 0.15
        self.is_player = is_player

    def update(self, keys=None, obstacles=None):
        if self.is_player and keys:
            # Player controls
            if keys[pygame.K_UP]:
                self.speed = min(self.speed + self.acceleration, self.max_speed)
            elif keys[pygame.K_DOWN]:
                self.speed = max(self.speed - self.acceleration, -3)
            else:
                # Apply friction
                if self.speed > 0:
                    self.speed = max(self.speed - self.friction, 0)
                elif self.speed < 0:
                    self.speed = min(self.speed + self.friction, 0)

            # Steering
            if keys[pygame.K_LEFT]:
                self.rect.x = max(self.rect.x - 5, 100)
            if keys[pygame.K_RIGHT]:
                self.rect.x = min(self.rect.x + 5, SCREEN_WIDTH - 140)
        else:
            # AI movement
            if self.speed < self.max_speed * 0.7:
                self.speed += self.acceleration * 0.5
            
            # Avoid obstacles
            if obstacles:
                for obstacle in obstacles:
                    if abs(self.rect.x - obstacle.rect.x) < 100 and abs(self.rect.y - obstacle.rect.y) < 150:
                        if self.rect.x < SCREEN_WIDTH // 2:
                            self.rect.x += 8
                        else:
                            self.rect.x -= 8

        # Move forward/backward
        self.rect.y -= self.speed

        # Keep car on road
        self.rect.x = max(100, min(self.rect.x, SCREEN_WIDTH - 140))

        # Wrap around screen
        if self.rect.top > SCREEN_HEIGHT:
            self.rect.bottom = 0
        elif self.rect.bottom < 0:
            self.rect.top = SCREEN_HEIGHT

    def draw(self, surface):
        surface.blit(self.image, self.rect)


# Obstacle class
class Obstacle(pygame.sprite.Sprite):
    def __init__(self, x, y):
        super().__init__()
        self.image = pygame.Surface((60, 40))
        self.image.fill(GRAY)
        self.rect = self.image.get_rect()
        self.rect.x = x
        self.rect.y = y
        self.speed = 0

    def update(self):
        self.rect.y += 5
        if self.rect.top > SCREEN_HEIGHT:
            self.rect.bottom = 0
            self.rect.x = random.randint(120, SCREEN_WIDTH - 160)

    def draw(self, surface):
        surface.blit(self.image, self.rect)


# Game class
class RaceGame:
    def __init__(self):
        self.running = True
        self.player_car = Car(SCREEN_WIDTH // 2 - 20, SCREEN_HEIGHT - 100, is_player=True)
        self.ai_car = Car(SCREEN_WIDTH // 2 + 80, SCREEN_HEIGHT - 100, is_player=False)
        self.obstacles = [Obstacle(random.randint(120, SCREEN_WIDTH - 160), random.randint(-200, -50)) for _ in range(4)]
        self.distance = 0
        self.ai_distance = 0
        self.game_over = False
        self.winner = None

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

        # Check win condition (first to 3000 distance)
        if self.distance >= 3000:
            self.game_over = True
            self.winner = "PLAYER"
        elif self.ai_distance >= 3000:
            self.game_over = True
            self.winner = "AI"

    def draw(self):
        screen.fill(BLACK)

        # Draw road
        pygame.draw.rect(screen, GRAY, (100, 0, SCREEN_WIDTH - 200, SCREEN_HEIGHT))
        
        # Draw lane markers
        for y in range(-50, SCREEN_HEIGHT, 50):
            pygame.draw.line(screen, WHITE, (SCREEN_WIDTH // 2, y), (SCREEN_WIDTH // 2, y + 30), 2)

        # Draw game objects
        self.player_car.draw(screen)
        self.ai_car.draw(screen)

        for obstacle in self.obstacles:
            obstacle.draw(screen)

        # Draw UI
        distance_text = font.render(f"Your Distance: {int(self.distance)}", True, WHITE)
        ai_text = font.render(f"AI Distance: {int(self.ai_distance)}", True, WHITE)
        speed_text = font.render(f"Speed: {self.player_car.speed:.1f}", True, WHITE)

        screen.blit(distance_text, (10, 10))
        screen.blit(ai_text, (10, 50))
        screen.blit(speed_text, (10, 90))

        # Draw progress bars
        pygame.draw.rect(screen, RED, (SCREEN_WIDTH - 250, 20, 200, 20))
        pygame.draw.rect(screen, GREEN, (SCREEN_WIDTH - 250, 20, int(200 * (self.distance / 3000)), 20))
        
        pygame.draw.rect(screen, YELLOW, (SCREEN_WIDTH - 250, 50, 200, 20))
        pygame.draw.rect(screen, GREEN, (SCREEN_WIDTH - 250, 50, int(200 * (self.ai_distance / 3000)), 20))

        # Draw game over screen
        if self.game_over:
            overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
            overlay.set_alpha(200)
            overlay.fill(BLACK)
            screen.blit(overlay, (0, 0))

            winner_text = big_font.render(f"{self.winner} WINS!", True, WHITE)
            restart_text = font.render("Press SPACE to restart or ESC to exit", True, WHITE)

            screen.blit(winner_text, (SCREEN_WIDTH // 2 - winner_text.get_width() // 2, SCREEN_HEIGHT // 2 - 50))
            screen.blit(restart_text, (SCREEN_WIDTH // 2 - restart_text.get_width() // 2, SCREEN_HEIGHT // 2 + 50))

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
