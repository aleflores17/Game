"""
TURBO CIRCUIT - a retro arcade racer (behind-the-car view) made with Pygame.

Goal:   Finish 3 laps ahead of 3 AI rivals. Grab coins, collect nitro,
        dodge the obstacles and don't drive on the grass.

Controls
    UP / W            accelerate
    DOWN / S          brake
    LEFT / RIGHT/A/D  steer
    SHIFT / SPACE     nitro boost
    P                 pause
    M                 mute / unmute
    ESC               quit (menu) / resume (pause) / menu (results)

All sounds are generated in code, so no extra files are needed.
Best times and scores are saved to race_records.json next to this file.
"""

import array
import json
import math
import os
import random

import pygame

pygame.mixer.pre_init(22050, -16, 1, 512)
pygame.init()

# ----------------------------------------------------------------------------
# Constants
# ----------------------------------------------------------------------------
SCREEN_WIDTH = 800
SCREEN_HEIGHT = 600
FPS = 60


PLAYER_Y = 500  # screen row of the player's car

ROAD_LEFT = 130
ROAD_RIGHT = SCREEN_WIDTH - 130
ROAD_WIDTH = ROAD_RIGHT - ROAD_LEFT
CURB_WIDTH = 14

# --- pseudo-3D camera (classic OutRun / Need for Speed style) ---
HORIZON = 250          # screen row of the horizon
CAM_BACK = 200         # camera sits this far behind the player's car
PROJ_A = 320.0         # scale at distance z is PROJ_A / z   (pixels per world unit)
PROJ_B = 44000.0       # a ground point at distance z is drawn at row HORIZON + PROJ_B / z
CAM_H = PROJ_B / PROJ_A
DRAW_DIST = 4200
Z_MIN = 60
CX = SCREEN_WIDTH // 2
ROAD_HALF = (ROAD_RIGHT - ROAD_LEFT) / 2
RUMBLE = 30            # curb width in world units
SEG_LEN = 150          # length of one curve segment
KAPPA = 1.8e-4         # curve strength
CENTRIFUGAL = 800      # how hard curves push cars outward

TOTAL_LAPS = 3
LAP_LENGTH = 15000  # world units (pixels) per lap
TOTAL_DIST = LAP_LENGTH * TOTAL_LAPS
BASE_MAX_SPEED = 14.0
NITRO_DRAIN = 0.6
KMH = 12  # speed -> km/h for the HUD

# Palette (same family as the original: green shoulders, gray road, red/white curbs)
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
RED = (214, 40, 40)
DARK_RED = (150, 25, 25)
YELLOW = (255, 209, 51)
DARK_YELLOW = (196, 158, 25)
BLUE = (60, 110, 214)
DARK_BLUE = (35, 70, 150)
GREEN = (60, 200, 90)
DARK_GREEN = (30, 130, 55)
GRASS_LIGHT = (62, 138, 62)
GRASS_DARK = (50, 120, 50)
ROAD_GRAY = (84, 84, 90)
CYAN_GLASS = (150, 210, 230)
UI_PANEL = (18, 18, 22)
UI_PANEL_BORDER = (240, 240, 240)
NITRO_BLUE = (70, 170, 255)
ORANGE = (255, 140, 30)

screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
pygame.display.set_caption("Turbo Circuit")
clock = pygame.time.Clock()

small_font = pygame.font.Font(None, 22)
font = pygame.font.Font(None, 30)
med_font = pygame.font.Font(None, 44)
big_font = pygame.font.Font(None, 74)
title_font = pygame.font.Font(None, 92)

DIFFICULTIES = [
    {"name": "EASY", "speed": 12.4, "reaction": 20, "look": 0.70, "rubber": 1.0, "boost": 0.004},
    {"name": "NORMAL", "speed": 13.4, "reaction": 10, "look": 0.90, "rubber": 0.8, "boost": 0.008},
    {"name": "HARD", "speed": 14.2, "reaction": 5, "look": 1.10, "rubber": 0.4, "boost": 0.014},
]

RECORDS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "race_records.json")


# ----------------------------------------------------------------------------
# Small helpers
# ----------------------------------------------------------------------------
def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def lerp_color(a, b, t):
    t = clamp(t, 0.0, 1.0)
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def fmt_time(t):
    return f"{int(t // 60)}:{t % 60:05.2f}"


def ordinal(n):
    return {1: "1ST", 2: "2ND", 3: "3RD"}.get(n, f"{n}TH")


def draw_text(surface, text, fnt, color, pos, anchor="topleft", shadow=True):
    img = fnt.render(text, True, color)
    rect = img.get_rect(**{anchor: pos})
    if shadow:
        sh = fnt.render(text, True, (0, 0, 0))
        surface.blit(sh, rect.move(2, 2))
    surface.blit(img, rect)
    return rect


def draw_panel(surface, rect, alpha=170, border=UI_PANEL_BORDER):
    panel = pygame.Surface((rect[2], rect[3]), pygame.SRCALPHA)
    pygame.draw.rect(panel, (*UI_PANEL, alpha), (0, 0, rect[2], rect[3]), border_radius=8)
    pygame.draw.rect(panel, border, (0, 0, rect[2], rect[3]), width=2, border_radius=8)
    surface.blit(panel, (rect[0], rect[1]))


def draw_bar(surface, x, y, w, h, pct, color, label=None):
    draw_panel(surface, (x, y, w, h), alpha=140)
    fill_w = int((w - 6) * clamp(pct, 0, 1))
    if fill_w > 0:
        pygame.draw.rect(surface, color, (x + 3, y + 3, fill_w, h - 6), border_radius=4)
        pygame.draw.rect(surface, lerp_color(color, WHITE, 0.45), (x + 3, y + 3, fill_w, (h - 6) // 3), border_radius=4)
    if label:
        draw_text(surface, label, small_font, WHITE, (x + 4, y - 17))


# ----------------------------------------------------------------------------
# Graphics: sprites and pre-rendered tiles (everything is drawn in code)
# ----------------------------------------------------------------------------
def make_car_sprite(body, dark, width=44, height=72):
    s = pygame.Surface((width, height), pygame.SRCALPHA)
    light = lerp_color(body, WHITE, 0.4)

    # wheels
    for wx in (0, width - 9):
        for wy in (9, height - 27):
            pygame.draw.rect(s, (18, 18, 20), (wx, wy, 9, 18), border_radius=3)
            pygame.draw.rect(s, (70, 70, 76), (wx + 2, wy + 3, 5, 12), border_radius=2)

    # front + rear wings
    pygame.draw.rect(s, dark, (3, 2, width - 6, 6), border_radius=2)
    pygame.draw.rect(s, dark, (2, height - 10, width - 4, 8), border_radius=2)
    pygame.draw.rect(s, body, (5, height - 9, width - 10, 4), border_radius=2)

    # body
    pygame.draw.rect(s, body, (8, 6, width - 16, height - 16), border_radius=12)
    pygame.draw.polygon(s, body, [(width // 2 - 10, 8), (width // 2 + 10, 8), (width // 2, 0)])
    # shading
    pygame.draw.rect(s, light, (11, 14, 5, height - 34), border_radius=3)
    pygame.draw.rect(s, dark, (width - 15, 14, 4, height - 34), border_radius=3)
    # racing stripe
    pygame.draw.rect(s, dark, (width // 2 - 3, 6, 6, height - 16))
    # cockpit
    pygame.draw.ellipse(s, (25, 25, 30), (width // 2 - 10, 25, 20, 26))
    pygame.draw.ellipse(s, CYAN_GLASS, (width // 2 - 8, 27, 16, 20))
    pygame.draw.ellipse(s, WHITE, (width // 2 - 5, 29, 5, 8))
    # lights
    pygame.draw.rect(s, (255, 250, 200), (13, 5, 6, 3), border_radius=1)
    pygame.draw.rect(s, (255, 250, 200), (width - 19, 5, 6, 3), border_radius=1)
    pygame.draw.rect(s, (255, 60, 60), (13, height - 15, 6, 3))
    pygame.draw.rect(s, (255, 60, 60), (width - 19, height - 15, 6, 3))
    return s


def make_shadow(width=44, height=72):
    s = pygame.Surface((width + 6, height + 6), pygame.SRCALPHA)
    pygame.draw.rect(s, (0, 0, 0, 70), (3, 3, width, height), border_radius=14)
    return s


def make_tree(radius, seed):
    rng = random.Random(seed)
    size = radius * 2 + 12
    s = pygame.Surface((size, size), pygame.SRCALPHA)
    c = size // 2
    pygame.draw.circle(s, (0, 0, 0, 60), (c + 5, c + 6), radius)
    base = rng.choice([(34, 92, 40), (40, 100, 44), (30, 85, 50)])
    pygame.draw.circle(s, base, (c, c), radius)
    for _ in range(6):
        ox, oy = rng.randint(-radius // 2, radius // 2), rng.randint(-radius // 2, radius // 2)
        pygame.draw.circle(s, lerp_color(base, (120, 200, 90), rng.uniform(0.15, 0.4)),
                           (c + ox, c + oy), max(3, radius // 3))
    pygame.draw.circle(s, lerp_color(base, WHITE, 0.25), (c - radius // 4, c - radius // 4), max(2, radius // 5))
    return s


def make_rock():
    s = pygame.Surface((22, 20), pygame.SRCALPHA)
    pygame.draw.ellipse(s, (0, 0, 0, 60), (2, 6, 20, 14))
    pygame.draw.polygon(s, (120, 120, 126), [(3, 14), (7, 3), (16, 2), (20, 11), (14, 17)])
    pygame.draw.polygon(s, (160, 160, 166), [(7, 3), (16, 2), (12, 9)])
    return s


def make_obstacle_sprites():
    sprites = {}

    # cone
    s = pygame.Surface((36, 36), pygame.SRCALPHA)
    pygame.draw.rect(s, (0, 0, 0, 70), (7, 7, 26, 26), border_radius=5)
    pygame.draw.rect(s, (225, 105, 20), (5, 5, 26, 26), border_radius=4)
    pygame.draw.circle(s, ORANGE, (18, 18), 12)
    pygame.draw.circle(s, WHITE, (18, 18), 8)
    pygame.draw.circle(s, (255, 110, 20), (18, 18), 5)
    pygame.draw.circle(s, (255, 200, 130), (16, 16), 2)
    sprites["cone"] = s

    # tire stack
    s = pygame.Surface((46, 46), pygame.SRCALPHA)
    pygame.draw.circle(s, (0, 0, 0, 70), (25, 25), 19)
    pygame.draw.circle(s, (28, 28, 30), (23, 23), 19)
    pygame.draw.circle(s, (70, 70, 76), (23, 23), 13)
    pygame.draw.circle(s, (28, 28, 30), (23, 23), 8)
    pygame.draw.arc(s, RED, (6, 6, 34, 34), 0.3, 1.6, 4)
    pygame.draw.arc(s, WHITE, (6, 6, 34, 34), 3.4, 4.7, 4)
    sprites["tires"] = s

    # barrier
    s = pygame.Surface((92, 32), pygame.SRCALPHA)
    pygame.draw.rect(s, (0, 0, 0, 70), (5, 6, 84, 22), border_radius=4)
    bar = pygame.Surface((84, 22))
    bar.fill(WHITE)
    for x in range(-22, 90, 22):
        pygame.draw.polygon(bar, RED, [(x, 22), (x + 11, 22), (x + 22, 0), (x + 11, 0)])
    mask = pygame.Surface((84, 22), pygame.SRCALPHA)
    pygame.draw.rect(mask, WHITE, (0, 0, 84, 22), border_radius=4)
    bar = bar.convert_alpha()
    bar.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
    s.blit(bar, (3, 3))
    pygame.draw.rect(s, (40, 40, 44), (3, 3, 84, 22), width=2, border_radius=4)
    sprites["barrier"] = s
    return sprites


def build_road_tile():
    tw, th = ROAD_WIDTH + CURB_WIDTH * 2, 160
    tile = pygame.Surface((tw, th))
    tile.fill(ROAD_GRAY)
    rng = random.Random(7)
    for _ in range(2200):
        x, y = rng.randrange(tw), rng.randrange(th)
        v = rng.randint(-10, 10)
        tile.set_at((x, y), (ROAD_GRAY[0] + v, ROAD_GRAY[1] + v, ROAD_GRAY[2] + v))
    # curbs (red / white)
    for i in range(th // 40):
        c = WHITE if i % 2 == 0 else RED
        pygame.draw.rect(tile, c, (0, i * 40, CURB_WIDTH, 40))
        pygame.draw.rect(tile, c, (tw - CURB_WIDTH, i * 40, CURB_WIDTH, 40))
    pygame.draw.line(tile, (30, 30, 30), (CURB_WIDTH, 0), (CURB_WIDTH, th), 2)
    pygame.draw.line(tile, (30, 30, 30), (tw - CURB_WIDTH - 1, 0), (tw - CURB_WIDTH - 1, th), 2)
    # solid edge lines + dashed lane lines
    pygame.draw.rect(tile, (235, 235, 235), (CURB_WIDTH + 6, 0, 4, th))
    pygame.draw.rect(tile, (235, 235, 235), (tw - CURB_WIDTH - 10, 0, 4, th))
    for i in (1, 2):
        x = CURB_WIDTH + ROAD_WIDTH * i // 3 - 2
        pygame.draw.rect(tile, (235, 235, 235), (x, 0, 4, 70))
    return tile


def build_grass_tile():
    tile = pygame.Surface((SCREEN_WIDTH, 200))
    tile.fill(GRASS_LIGHT)
    pygame.draw.rect(tile, GRASS_DARK, (0, 100, SCREEN_WIDTH, 100))
    rng = random.Random(3)
    for _ in range(900):
        x, y = rng.randrange(SCREEN_WIDTH), rng.randrange(200)
        base = GRASS_LIGHT if y < 100 else GRASS_DARK
        c = lerp_color(base, (20, 70, 25) if rng.random() < 0.5 else (110, 180, 90), 0.4)
        pygame.draw.line(tile, c, (x, y), (x + rng.randint(-1, 1), y - rng.randint(2, 4)), 1)
    return tile


def build_vignette():
    small = pygame.Surface((80, 60), pygame.SRCALPHA)
    for x in range(80):
        for y in range(60):
            d = math.hypot((x - 40) / 40, (y - 30) / 30)
            a = int(clamp((d - 0.6) / 0.7, 0, 1) * 110)
            small.set_at((x, y), (0, 0, 0, a))
    return pygame.transform.smoothscale(small, (SCREEN_WIDTH, SCREEN_HEIGHT))


def blit_tiled(surface, tile, x, offset_y):
    h = tile.get_height()
    y = offset_y % h - h
    while y < SCREEN_HEIGHT:
        surface.blit(tile, (x, y))
        y += h


ROAD_TILE = build_road_tile()
GRASS_TILE = build_grass_tile()
VIGNETTE = build_vignette()
OBSTACLE_SPRITES = make_obstacle_sprites()
CAR_SHADOW = make_shadow()

CAR_STYLES = {
    "player": {"name": "YOU", "color": RED, "dark": DARK_RED},
    "ai": [
        {"name": "VIPER", "color": YELLOW, "dark": DARK_YELLOW},
        {"name": "BLAZE", "color": BLUE, "dark": DARK_BLUE},
        {"name": "NOVA", "color": GREEN, "dark": DARK_GREEN},
    ],
}
for _style in [CAR_STYLES["player"]] + CAR_STYLES["ai"]:
    _style["sprite"] = make_car_sprite(_style["color"], _style["dark"])

# Roadside scenery repeats every SCENERY_PERIOD world units
SCENERY_PERIOD = 1200
SCENERY = []
_rng = random.Random(11)
_tree_sprites = [make_tree(r, i) for i, r in enumerate((18, 22, 26, 20, 24))]
_rock_sprite = make_rock()
for _y in range(0, SCENERY_PERIOD, 55):
    for _side in (0, 1):
        roll = _rng.random()
        if roll < 0.62:
            img, x = _rng.choice(_tree_sprites), _rng.randint(16, 40)
        elif roll < 0.80:
            img, x = _rock_sprite, _rng.randint(44, 56)
        else:
            continue
        if _side:
            x = SCREEN_WIDTH - x
        SCENERY.append((_y + _rng.randint(-15, 15), x, img))

_finish_label_cache = {}


def finish_label(text):
    if text not in _finish_label_cache:
        _finish_label_cache[text] = big_font.render(text, True, (235, 235, 235))
    return _finish_label_cache[text]


# ----------------------------------------------------------------------------
# Audio: every sound is synthesised at start-up
# ----------------------------------------------------------------------------
class Audio:
    def __init__(self):
        self.enabled = False
        self.muted = False
        self.level = -1
        info = pygame.mixer.get_init()
        if not info or info[1] != -16:
            return
        self.sr, _, self.nch = info
        try:
            pygame.mixer.set_num_channels(16)
            pygame.mixer.set_reserved(3)
            self.ch_engine = pygame.mixer.Channel(0)
            self.ch_boost = pygame.mixer.Channel(1)
            self.ch_gravel = pygame.mixer.Channel(2)
            self._build()
            self.enabled = True
        except Exception:
            self.enabled = False

    # -- synthesis helpers ---------------------------------------------------
    def _sound(self, samples, volume=1.0):
        buf = array.array("h")
        for v in samples:
            buf.extend([int(clamp(v, -1, 1) * 30000)] * self.nch)
        snd = pygame.mixer.Sound(buffer=buf.tobytes())
        snd.set_volume(volume)
        return snd

    def _tone(self, freq, dur, vol=0.5, decay=5.0, sweep=0.0, square=False):
        out, phase = [], 0.0
        for i in range(int(self.sr * dur)):
            t = i / self.sr
            phase += 2 * math.pi * (freq + sweep * t) / self.sr
            w = math.sin(phase)
            if square:
                w = 0.6 if w >= 0 else -0.6
            out.append(w * vol * math.exp(-decay * t) * min(1.0, t / 0.004))
        return out

    def _noise(self, dur, vol=0.5, decay=0.0, smooth=0.3):
        out, y = [], 0.0
        for i in range(int(self.sr * dur)):
            t = i / self.sr
            y += smooth * (random.uniform(-1, 1) - y)
            out.append(y * vol * math.exp(-decay * t))
        return out

    def _build(self):
        sr = self.sr
        # engine loops: 13 pitch levels, each an exact number of cycles so it loops cleanly
        n = int(sr * 0.1)
        self.engine = []
        for k in range(5, 18):
            samples = []
            for i in range(n):
                ph = 2 * math.pi * k * i / n
                s = (math.sin(ph) + 0.55 * math.sin(2 * ph + 0.6) + 0.35 * math.sin(3 * ph + 1.2)
                     + 0.2 * math.sin(4 * ph) + 0.1 * math.sin(6 * ph))
                s *= 1 + 0.35 * math.sin(2 * math.pi * (k // 2) * i / n)
                samples.append(0.5 * math.tanh(1.2 * s) + random.uniform(-0.03, 0.03))
            self.engine.append(self._sound(samples, 1.0))

        self.boost_loop = self._sound(self._noise(0.6, 0.5, 0, 0.35), 0.5)
        self.gravel_loop = self._sound(self._noise(0.6, 0.9, 0, 0.12), 0.5)

        crash = self._noise(0.35, 0.8, 9, 0.25)
        thump = self._tone(70, 0.35, 0.8, 10)
        self.sfx = {
            "crash": self._sound([a + b for a, b in zip(crash, thump)], 0.9),
            "bump": self._sound([a + b for a, b in zip(self._noise(0.15, 0.6, 18, 0.3),
                                                       self._tone(120, 0.15, 0.7, 18))], 0.7),
            "coin": self._sound(self._tone(988, 0.07, 0.5, 8, square=True)
                                + self._tone(1319, 0.14, 0.5, 8, square=True), 0.35),
            "nitro": self._sound(self._tone(400, 0.28, 0.6, 2, sweep=2800), 0.5),
            "beep": self._sound(self._tone(440, 0.22, 0.7, 3), 0.6),
            "go": self._sound(self._tone(880, 0.6, 0.7, 2.5), 0.6),
            "lap": self._sound(self._tone(523, 0.1, 0.6, 4) + self._tone(659, 0.1, 0.6, 4)
                               + self._tone(784, 0.25, 0.6, 4), 0.5),
            "win": self._sound(self._tone(523, 0.14, 0.6, 3) + self._tone(659, 0.14, 0.6, 3)
                               + self._tone(784, 0.14, 0.6, 3) + self._tone(1047, 0.6, 0.6, 3), 0.55),
            "finish": self._sound(self._tone(523, 0.18, 0.6, 4) + self._tone(392, 0.4, 0.6, 4), 0.5),
            "tick": self._sound(self._tone(660, 0.05, 0.5, 12), 0.4),
        }

    # -- runtime -------------------------------------------------------------
    def play(self, name):
        if self.enabled and not self.muted:
            self.sfx[name].play()

    def silence(self):
        if self.enabled:
            self.ch_engine.stop()
            self.ch_boost.stop()
            self.ch_gravel.stop()
            self.level = -1

    def toggle_mute(self):
        self.muted = not self.muted
        if self.muted:
            self.silence()

    def update(self, car, throttle):
        """Called every frame: engine pitch follows speed, plus boost/gravel loops."""
        if not self.enabled or self.muted:
            return
        ratio = clamp(car.speed / (BASE_MAX_SPEED * 1.4), 0, 1)
        level = int(ratio * (len(self.engine) - 1))
        if level != self.level or not self.ch_engine.get_busy():
            self.ch_engine.play(self.engine[level], loops=-1)
            self.level = level
        self.ch_engine.set_volume(0.18 + (0.16 if throttle else 0.0) + 0.1 * ratio)

        if car.boosting:
            if not self.ch_boost.get_busy():
                self.ch_boost.play(self.boost_loop, loops=-1)
        else:
            self.ch_boost.stop()

        if car.off_road and car.speed > 1:
            if not self.ch_gravel.get_busy():
                self.ch_gravel.play(self.gravel_loop, loops=-1)
            self.ch_gravel.set_volume(clamp(car.speed / 10, 0.2, 0.8))
        else:
            self.ch_gravel.stop()


# ----------------------------------------------------------------------------
# World objects
# ----------------------------------------------------------------------------
class Particle:
    """A short-lived dot living in world coordinates (so it scrolls with the road)."""

    def __init__(self, x, wy, vx, vy, life, color, size, fade_to=None, grow=0.0, square=False):
        self.x, self.wy, self.vx, self.vy = x, wy, vx, vy
        self.life = self.max_life = life
        self.color, self.size, self.fade_to = color, size, fade_to
        self.grow, self.square = grow, square

    def update(self):
        self.x += self.vx
        self.wy += self.vy
        self.vx *= 0.96
        self.life -= 1

    def draw(self, surface, cam):
        sy = PLAYER_Y + cam - self.wy
        if not -20 < sy < SCREEN_HEIGHT + 20:
            return
        t = self.life / self.max_life
        col = lerp_color(self.color, self.fade_to, 1 - t) if self.fade_to else self.color
        r = max(1, int(self.size * (0.4 + 0.6 * t) + self.grow * (1 - t)))
        if self.square:
            pygame.draw.rect(surface, col, (int(self.x), int(sy), r, r))
        else:
            pygame.draw.circle(surface, col, (int(self.x), int(sy)), r)


class Obstacle:
    SPECS = {"cone": (28, 30, 0.65), "tires": (38, 38, 0.5), "barrier": (84, 24, 0.35)}

    def __init__(self, x, wy, kind):
        self.kind = kind
        self.w, self.h, self.slow = self.SPECS[kind]
        self.x, self.wy = x, wy
        self.rect = pygame.Rect(0, 0, self.w - 4, self.h - 4)
        self.rect.center = (int(x), int(-wy))
        self.active = True
        self.life = 0

    def knock(self, car):
        self.active = False
        self.vx = random.uniform(-3, 3) + car.vx * 0.5
        self.vy = car.speed * 1.2 + 2
        self.spin = random.uniform(-14, 14)
        self.angle = 0.0
        self.life = 40

    def update(self):
        if not self.active and self.life > 0:
            self.x += self.vx
            self.wy += self.vy
            self.vy *= 0.96
            self.angle += self.spin
            self.life -= 1

    def draw(self, surface, cam):
        sy = PLAYER_Y + cam - self.wy
        if sy < -80 or sy > SCREEN_HEIGHT + 80:
            return
        img = OBSTACLE_SPRITES[self.kind]
        if self.active:
            surface.blit(img, img.get_rect(center=(int(self.x), int(sy))))
        elif self.life > 0:
            scale = 1 + (40 - self.life) / 40 * 0.4  # flies toward the camera
            img = pygame.transform.rotozoom(img, self.angle, scale)
            surface.blit(img, img.get_rect(center=(int(self.x), int(sy))))


class Pickup:
    def __init__(self, x, wy, kind):
        self.x, self.wy, self.kind = x, wy, kind
        self.active = True
        self.rect = pygame.Rect(0, 0, 26, 26)
        self.rect.center = (int(x), int(-wy))

    def draw(self, surface, cam):
        sy = PLAYER_Y + cam - self.wy
        if not self.active or sy < -40 or sy > SCREEN_HEIGHT + 40:
            return
        t = pygame.time.get_ticks() / 1000.0
        x, y = int(self.x), int(sy)
        if self.kind == "coin":
            w = int(abs(math.cos(t * 4 + self.wy * 0.01)) * 9) + 3
            pygame.draw.ellipse(surface, (160, 120, 10), (x - w - 1, y - 12, 2 * w + 2, 24))
            pygame.draw.ellipse(surface, YELLOW, (x - w, y - 11, 2 * w, 22))
            pygame.draw.ellipse(surface, (255, 240, 150), (x - w // 2, y - 8, max(2, w), 8))
        else:  # nitro canister
            pulse = 3 * math.sin(t * 6)
            pygame.draw.circle(surface, (30, 80, 140), (x, y), int(19 + pulse), 2)
            pygame.draw.circle(surface, (20, 50, 100), (x, y), 15)
            pygame.draw.circle(surface, NITRO_BLUE, (x, y), 13)
            pygame.draw.polygon(surface, WHITE, [(x + 2, y - 10), (x - 6, y + 2), (x, y + 2),
                                                 (x - 2, y + 10), (x + 6, y - 3), (x, y - 3)])


def build_track():
    """Randomly lay out obstacles and pickups for the whole race."""
    obstacles, pickups = [], []
    lane_w = ROAD_WIDTH / 3
    mid = (ROAD_LEFT + ROAD_RIGHT) / 2

    def rand_kind():
        return random.choices(["cone", "tires", "barrier"], weights=[5, 3, 2])[0]

    wy = 1800
    while wy < TOTAL_DIST - 600:
        lap_pos = wy % LAP_LENGTH
        if lap_pos < 300 or lap_pos > LAP_LENGTH - 300:
            wy += 300
            continue
        pattern = random.choices(["single", "pair", "wall", "slalom", "none"], weights=[4, 2, 1, 2, 2])[0]
        if pattern == "single":
            obstacles.append(Obstacle(random.randint(ROAD_LEFT + 50, ROAD_RIGHT - 50), wy, rand_kind()))
        elif pattern == "pair":
            obstacles.append(Obstacle(random.randint(ROAD_LEFT + 50, int(mid - 110)), wy, rand_kind()))
            obstacles.append(Obstacle(random.randint(int(mid + 110), ROAD_RIGHT - 50), wy, rand_kind()))
        elif pattern == "wall":
            gap = random.randint(0, 2)
            for lane in range(3):
                if lane != gap:
                    obstacles.append(Obstacle(ROAD_LEFT + lane_w * (lane + 0.5), wy, "barrier"))
        elif pattern == "slalom":
            side = random.choice([-1, 1])
            for i in range(3):
                x = mid + side * (-1) ** i * 120
                obstacles.append(Obstacle(x, wy + i * 230, "cone"))
            wy += 460
        wy += random.randint(500, 800)

    def free(x, y):
        return all(abs(o.wy - y) > 70 or abs(o.x - x) > o.w / 2 + 40 for o in obstacles)

    wy = 1200
    while wy < TOTAL_DIST - 400:
        x = random.randint(ROAD_LEFT + 60, ROAD_RIGHT - 60)
        for i in range(5):
            if free(x, wy + i * 70):
                pickups.append(Pickup(x, wy + i * 70, "coin"))
        wy += random.randint(900, 1400)
    wy = 2200
    while wy < TOTAL_DIST - 400:
        x = random.randint(ROAD_LEFT + 60, ROAD_RIGHT - 60)
        if free(x, wy):
            pickups.append(Pickup(x, wy, "nitro"))
        wy += random.randint(2200, 3200)
    return obstacles, pickups


# ----------------------------------------------------------------------------
# Cars
# ----------------------------------------------------------------------------
class Car:
    def __init__(self, x, dist, style):
        self.x, self.dist = float(x), float(dist)  # x = centre of car, dist = distance along the track
        self.style = style
        self.name, self.color, self.sprite = style["name"], style["color"], style["sprite"]
        self.speed = 0.0
        self.vx = 0.0
        self.tilt = 0.0
        self.max_speed = BASE_MAX_SPEED
        self.accel = 0.14
        self.nitro = 50.0
        self.boosting = False
        self.off_road = False
        self.hit_timer = 0
        self.bump_cd = 0
        self.finished = False
        self.finish_time = None
        self.place = None
        self.laps_done = 0

    def hitbox(self):
        r = pygame.Rect(0, 0, 28, 56)
        r.center = (int(self.x), int(-self.dist))
        return r

    def physics(self, throttle, brake, steer, boost):
        self.off_road = self.x < ROAD_LEFT - 8 or self.x > ROAD_RIGHT + 8
        top = self.max_speed * (0.55 if self.off_road else 1.0)

        self.boosting = bool(boost and throttle and self.nitro > 0 and self.speed > 1.0)
        if self.boosting:
            self.nitro = max(0.0, self.nitro - NITRO_DRAIN)
            top = self.max_speed * (1.0 if self.off_road else 1.38)

        if throttle:
            self.speed += self.accel * (1 - 0.6 * min(1.0, self.speed / top)) + (0.35 if self.boosting else 0.0)
        elif brake:
            self.speed = max(0.0, self.speed - 0.4)
        else:
            self.speed = max(0.0, self.speed - 0.05)
        if self.speed > top:
            self.speed = max(top, self.speed - 0.3)

        # steering: little grip when almost stopped, smooth lateral movement
        grip = min(1.0, 0.2 + self.speed / 6.0)
        self.vx += (steer * 6.2 * grip - self.vx) * 0.22
        self.x = clamp(self.x + self.vx, ROAD_LEFT - 50, ROAD_RIGHT + 50)
        self.dist += self.speed

        self.tilt += (clamp(-self.vx * 2.2, -14, 14) - self.tilt) * 0.3
        self.hit_timer = max(0, self.hit_timer - 1)
        self.bump_cd = max(0, self.bump_cd - 1)

    def draw(self, surface, cam):
        sy = PLAYER_Y + cam - self.dist
        if sy < -90 or sy > SCREEN_HEIGHT + 90:
            return
        if self.hit_timer and (self.hit_timer // 3) % 2:
            return  # blink after a crash
        img = pygame.transform.rotate(self.sprite, self.tilt)
        sh = pygame.transform.rotate(CAR_SHADOW, self.tilt)
        surface.blit(sh, sh.get_rect(center=(self.x + 4, sy + 5)))
        surface.blit(img, img.get_rect(center=(int(self.x), int(sy))))


class AICar(Car):
    """
    AI driver. Every few frames (its 'reaction time') it scores nine candidate
    lane positions looking ahead: obstacles, other cars and the edge of the
    road cost points, nitro pickups give a bonus. It steers toward the cheapest
    one. A little rubber-banding keeps the race close without cheating too much.
    """

    def __init__(self, x, dist, style, params, factor, pref_x):
        super().__init__(x, dist, style)
        self.p = params
        self.factor = factor
        self.pref_x = pref_x
        self.target_x = x
        self.timer = random.randint(0, params["reaction"])
        self.phase = random.uniform(0, 6.28)
        self.want_boost = False
        self.nitro = 60.0

    def plan(self, game):
        look = (160 + self.speed * 30) * self.p["look"]
        obs = game.obstacles_ahead(self.dist, look)
        nitros = [pk for pk in game.pickups
                  if pk.active and pk.kind == "nitro" and 0 < pk.wy - self.dist < look]
        others = [c for c in game.cars if c is not self and 0 < c.dist - self.dist < look * 0.6]
        pref = self.pref_x + 50 * math.sin(game.race_time * 0.5 + self.phase)

        n = 9
        best_cost, best_x = 1e9, self.x
        for i in range(n):
            cx = ROAD_LEFT + 45 + i * (ROAD_WIDTH - 90) / (n - 1)
            cost = abs(cx - pref) * 0.12 + abs(cx - self.x) * 0.30
            for ob in obs:
                d = ob.wy - self.dist
                if abs(ob.x - cx) < ob.w / 2 + 32:
                    cost += 300 + 300 * (1 - d / look)
                elif (d < look * 0.45 and abs(self.x - cx) > 20 and
                      min(self.x, cx) - ob.w / 2 - 20 < ob.x < max(self.x, cx) + ob.w / 2 + 20):
                    cost += 120  # don't sweep through an obstacle while changing lane
            for c in others:
                if abs(c.x - cx) < 48:
                    cost += 90
            for pk in nitros:
                if abs(pk.x - cx) < 30:
                    cost -= 80 if self.nitro < 70 else 15
            if cost < best_cost:
                best_cost, best_x = cost, cx
        self.target_x = best_x

    def drive(self, game):
        self.timer -= 1
        if self.timer <= 0:
            self.plan(game)
            self.timer = self.p["reaction"] + random.randint(0, 3)

        # speed for this frame: personality + small "form" wobble + rubber banding
        base = self.p["speed"] * self.factor * (1 + 0.012 * math.sin(game.race_time * 0.7 + self.phase))
        gap = self.dist - game.player.dist
        if gap > 700:
            base *= 1 - min(0.07, (gap - 700) / 12000) * self.p["rubber"]
        elif gap < -700:
            base *= 1 + min(0.06, (-gap - 700) / 12000) * self.p["rubber"]
        self.max_speed = 9.0 if self.finished else base

        steer = clamp((self.target_x - self.x) / 35, -1, 1)
        brake = any(abs(ob.x - self.x) < ob.w / 2 + 30 for ob in game.obstacles_ahead(self.dist, 90))

        if not self.want_boost and self.nitro > 45 and self.speed > self.max_speed * 0.9 \
                and random.random() < self.p["boost"]:
            self.want_boost = True
        if self.want_boost and (self.nitro <= 1 or self.finished):
            self.want_boost = False
        self.physics(not brake, brake, steer, self.want_boost)


# ----------------------------------------------------------------------------
# Records
# ----------------------------------------------------------------------------
def load_records():
    try:
        with open(RECORDS_FILE) as f:
            data = json.load(f)
        data.setdefault("time", {})
        data.setdefault("score", {})
        return data
    except (OSError, ValueError):
        return {"time": {}, "score": {}}


def save_records(records):
    try:
        with open(RECORDS_FILE, "w") as f:
            json.dump(records, f)
    except OSError:
        pass


# ----------------------------------------------------------------------------
# The game
# ----------------------------------------------------------------------------
class RaceGame:
    def __init__(self):
        self.running = True
        self.audio = Audio()
        self.world = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        self.records = load_records()
        self.difficulty = 1
        self.state = "menu"  # menu, countdown, racing, finished, results, paused
        self.prev_state = "menu"
        self.menu_cam = 0.0
        self.setup_race()

    # -- setup ---------------------------------------------------------------
    def setup_race(self):
        self.obstacles, self.pickups = build_track()
        self.particles = []
        self.flying = []
        params = DIFFICULTIES[self.difficulty]

        lx, rx = ROAD_LEFT + ROAD_WIDTH * 0.30, ROAD_LEFT + ROAD_WIDTH * 0.70
        grid = [(lx, 0), (rx, -40), (lx, -150), (rx, -190)]
        self.player = Car(grid[2][0], grid[2][1], CAR_STYLES["player"])
        self.ai_cars = []
        slots = [grid[0], grid[1], grid[3]]
        factors = [1.0, 0.975, 0.95]
        prefs = [ROAD_LEFT + ROAD_WIDTH * f for f in (0.5, 0.25, 0.75)]
        for style, slot, factor, pref in zip(CAR_STYLES["ai"], slots, factors, prefs):
            self.ai_cars.append(AICar(slot[0], slot[1], style, params, factor, pref))
        self.cars = [self.player] + self.ai_cars

        self.race_time = 0.0
        self.count_t = 0.0
        self.last_phase = -1
        self.finish_timer = 0.0
        self.shake = 0.0
        self.banner = None  # (text, seconds_left, color)
        self.lap_start = 0.0
        self.lap_times = []
        self.coins = 0
        self.score = 0
        self.new_record = False
        self.player.max_speed = BASE_MAX_SPEED

    # -- helpers -------------------------------------------------------------
    def obstacles_ahead(self, dist, dmax):
        return [o for o in self.obstacles if o.active and -30 < o.wy - dist < dmax]

    def standings(self):
        return sorted(self.cars, key=lambda c: (0, c.finish_time) if c.finished else (1, -c.dist))

    def emit(self, p):
        self.particles.append(p)

    def set_banner(self, text, color=WHITE, secs=2.0):
        self.banner = (text, secs, color)

    # -- events --------------------------------------------------------------
    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN:
                self.on_key(event.key)

    def on_key(self, key):
        if key == pygame.K_m:
            self.audio.toggle_mute()
        if self.state == "menu":
            if key in (pygame.K_LEFT, pygame.K_UP, pygame.K_a, pygame.K_w):
                self.difficulty = (self.difficulty - 1) % len(DIFFICULTIES)
                self.audio.play("tick")
            elif key in (pygame.K_RIGHT, pygame.K_DOWN, pygame.K_d, pygame.K_s):
                self.difficulty = (self.difficulty + 1) % len(DIFFICULTIES)
                self.audio.play("tick")
            elif key in (pygame.K_RETURN, pygame.K_SPACE):
                self.start_race()
            elif key == pygame.K_ESCAPE:
                self.running = False
        elif self.state in ("countdown", "racing"):
            if key in (pygame.K_p, pygame.K_ESCAPE):
                self.prev_state = self.state
                self.state = "paused"
        elif self.state == "paused":
            if key in (pygame.K_p, pygame.K_ESCAPE):
                self.state = self.prev_state
            elif key == pygame.K_q:
                self.state = "menu"
        elif self.state == "results":
            if key in (pygame.K_SPACE, pygame.K_RETURN):
                self.start_race()
            elif key == pygame.K_ESCAPE:
                self.state = "menu"

    def start_race(self):
        self.setup_race()
        self.state = "countdown"

    # -- update --------------------------------------------------------------
    def player_inputs(self, keys):
        throttle = keys[pygame.K_UP] or keys[pygame.K_w]
        brake = keys[pygame.K_DOWN] or keys[pygame.K_s]
        steer = int(bool(keys[pygame.K_RIGHT] or keys[pygame.K_d])) - int(bool(keys[pygame.K_LEFT] or keys[pygame.K_a]))
        boost = keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT] or keys[pygame.K_SPACE]
        return bool(throttle), bool(brake), steer, bool(boost)

    def update(self, dt):
        a = self.audio
        if self.state == "menu":
            self.menu_cam += 8
            a.silence()
            return
        if self.state == "paused":
            a.silence()
            return

        keys = pygame.key.get_pressed()
        throttle, brake, steer, boost = self.player_inputs(keys)

        if self.state == "countdown":
            self.count_t += dt
            phase = int(self.count_t)
            if phase != self.last_phase and phase < 3:
                self.last_phase = phase
                a.play("beep")
            a.update(self.player, throttle)
            if self.count_t >= 3:
                self.state = "racing"
                self.set_banner("GO!", GREEN, 1.2)
                a.play("go")
            return

        # ---- racing / finished / results: the world keeps running ----
        self.race_time += dt
        self.shake *= 0.85
        if self.banner:
            text, secs, color = self.banner
            self.banner = (text, secs - dt, color) if secs - dt > 0 else None

        if self.player.finished:
            # auto-pilot: ease off and drift back to the middle of the road
            self.player.physics(False, True, clamp(((ROAD_LEFT + ROAD_RIGHT) / 2 - self.player.x) / 80, -0.5, 0.5), False)
        else:
            self.player.physics(throttle, brake, steer, boost)
            if self.player.off_road and self.player.speed > 2:
                self.shake = max(self.shake, 2.0)
        for ai in self.ai_cars:
            ai.drive(self)

        for car in self.cars:
            self.check_progress(car)
        self.handle_collisions()
        self.update_effects()
        a.update(self.player, throttle and not self.player.finished)

        if self.state == "finished":
            self.finish_timer -= dt
            if self.finish_timer <= 0:
                self.state = "results"

    def check_progress(self, car):
        if car.finished:
            return
        lap_now = int(car.dist // LAP_LENGTH)
        if lap_now > car.laps_done and car.dist < TOTAL_DIST:
            car.laps_done = lap_now
            if car is self.player:
                lap_time = self.race_time - self.lap_start
                self.lap_start = self.race_time
                best = min(self.lap_times) if self.lap_times else None
                self.lap_times.append(lap_time)
                tag = "  BEST LAP!" if best is None or lap_time < best else ""
                self.set_banner(f"LAP {lap_now + 1}/{TOTAL_LAPS}   {fmt_time(lap_time)}{tag}", YELLOW, 2.5)
                self.audio.play("lap")
        if car.dist >= TOTAL_DIST:
            car.finished = True
            car.finish_time = self.race_time
            car.place = sum(1 for c in self.cars if c.finished)
            if car is self.player:
                self.lap_times.append(self.race_time - self.lap_start)
                self.finish_player()

    def finish_player(self):
        p = self.player
        key = str(self.difficulty)
        bonus = [1000, 600, 300, 100][p.place - 1]
        time_bonus = max(0, int((110 - p.finish_time) * 15))
        self.score = self.coins * 50 + bonus + time_bonus
        self.score_parts = (self.coins * 50, bonus, time_bonus)
        best_t = self.records["time"].get(key)
        best_s = self.records["score"].get(key)
        self.new_record = best_t is None or p.finish_time < best_t
        if self.new_record:
            self.records["time"][key] = p.finish_time
        if best_s is None or self.score > best_s:
            self.records["score"][key] = self.score
        save_records(self.records)

        self.state = "finished"
        self.finish_timer = 2.5
        self.set_banner("FINISH!", YELLOW, 3.0)
        self.audio.play("win" if p.place == 1 else "finish")
        for _ in range(90):
            self.emit(Particle(p.x + random.uniform(-40, 40), p.dist + 30, random.uniform(-4, 4),
                               random.uniform(-2, 9), random.randint(50, 90),
                               random.choice([RED, YELLOW, WHITE, NITRO_BLUE, GREEN]), 6, square=True))

    def handle_collisions(self):
        for car in self.cars:
            hb = car.hitbox()
            for ob in self.obstacles:
                if ob.active and abs(ob.wy - car.dist) < 90 and hb.colliderect(ob.rect):
                    ob.knock(car)
                    self.flying.append(ob)
                    car.speed *= ob.slow
                    car.hit_timer = 36 if car is self.player else 20
                    for _ in range(10):
                        self.emit(Particle(ob.x, ob.wy, random.uniform(-4, 4), random.uniform(0, 7),
                                           18, random.choice([YELLOW, ORANGE, WHITE]), 4))
                    if car is self.player:
                        self.shake = max(self.shake, 12)
                        self.audio.play("crash")
                    elif abs(car.dist - self.player.dist) < 500:
                        self.audio.play("bump")

            for pk in self.pickups:
                if pk.active and abs(pk.wy - car.dist) < 40 and hb.colliderect(pk.rect):
                    if pk.kind == "coin" and car is self.player:
                        pk.active = False
                        self.coins += 1
                        self.audio.play("coin")
                    elif pk.kind == "nitro":
                        pk.active = False
                        car.nitro = min(100.0, car.nitro + 35)
                        if car is self.player:
                            self.audio.play("nitro")
                            self.set_banner("+NITRO", NITRO_BLUE, 1.0)
                        for _ in range(12):
                            self.emit(Particle(pk.x, pk.wy, random.uniform(-4, 4), random.uniform(-2, 6),
                                               20, NITRO_BLUE, 5))

        # car vs car: shove apart sideways, and the one behind loses a bit of speed
        for i in range(len(self.cars)):
            for j in range(i + 1, len(self.cars)):
                a, b = self.cars[i], self.cars[j]
                if a.hitbox().colliderect(b.hitbox()):
                    push = 2.5 if a.x >= b.x else -2.5
                    a.x = clamp(a.x + push, ROAD_LEFT - 50, ROAD_RIGHT + 50)
                    b.x = clamp(b.x - push, ROAD_LEFT - 50, ROAD_RIGHT + 50)
                    rear = a if a.dist < b.dist else b
                    rear.speed *= 0.97
                    if self.player in (a, b) and self.player.bump_cd == 0:
                        self.player.bump_cd = 20
                        self.shake = max(self.shake, 6)
                        self.audio.play("bump")
                        for _ in range(6):
                            self.emit(Particle((a.x + b.x) / 2, (a.dist + b.dist) / 2, random.uniform(-3, 3),
                                               random.uniform(0, 5), 14, YELLOW, 3))

    def update_effects(self):
        for ob in self.flying:
            ob.update()
        self.flying = [o for o in self.flying if o.life > 0]

        for car in self.cars:
            if car.speed > 1.5 and random.random() < 0.35:
                for dx in (-8, 8):
                    self.emit(Particle(car.x + dx, car.dist - 38, random.uniform(-0.4, 0.4), car.speed * 0.6,
                                       22, (170, 170, 175), 3, fade_to=ROAD_GRAY, grow=5))
            if car.boosting:
                for dx in (-7, 7):
                    for col in ((255, 240, 160), ORANGE, (255, 80, 30)):
                        self.emit(Particle(car.x + dx + random.uniform(-2, 2), car.dist - 38,
                                           random.uniform(-0.5, 0.5), car.speed - random.uniform(2.5, 5),
                                           random.randint(8, 14), col, 5))
            if car.off_road and car.speed > 1:
                self.emit(Particle(car.x + random.uniform(-16, 16), car.dist - 20, random.uniform(-1, 1),
                                   car.speed * 0.5, 26, (130, 105, 70), 5, fade_to=GRASS_DARK, grow=4))

        for p in self.particles:
            p.update()
        self.particles = [p for p in self.particles if p.life > 0][-400:]

    # -- drawing -------------------------------------------------------------
    def draw_world(self, surf, cam, objects=True):
        blit_tiled(surf, GRASS_TILE, 0, PLAYER_Y + cam)
        blit_tiled(surf, ROAD_TILE, ROAD_LEFT - CURB_WIDTH, PLAYER_Y + cam)

        for wy, x, img in SCENERY:
            sy = (PLAYER_Y + cam - wy) % SCENERY_PERIOD
            if sy > SCENERY_PERIOD - 80:
                sy -= SCENERY_PERIOD
            if -60 < sy < SCREEN_HEIGHT + 60:
                surf.blit(img, img.get_rect(center=(x, int(sy))))

        if not objects:
            return

        for k in range(TOTAL_LAPS + 1):
            sy = PLAYER_Y + cam - k * LAP_LENGTH
            if -90 < sy < SCREEN_HEIGHT + 90:
                self.draw_finish_line(surf, sy, k)

        for pk in self.pickups:
            pk.draw(surf, cam)
        for ob in self.obstacles:
            ob.draw(surf, cam)
        for p in self.particles:
            p.draw(surf, cam)
        for car in sorted(self.cars, key=lambda c: c is self.player):
            car.draw(surf, cam)

        # speed lines when going really fast
        if self.player.speed > 12.5:
            for _ in range(int((self.player.speed - 12) * 5)):
                x = random.randint(0, SCREEN_WIDTH)
                y = random.randint(-40, SCREEN_HEIGHT)
                col = (210, 210, 215) if ROAD_LEFT < x < ROAD_RIGHT else (150, 200, 150)
                pygame.draw.line(surf, col, (x, y), (x, y + random.randint(20, 50)), 1)

    def draw_finish_line(self, surf, sy, k):
        sq = 20
        for row in range(2):
            for c in range(ROAD_WIDTH // sq):
                col = WHITE if (c + row) % 2 == 0 else (20, 20, 20)
                pygame.draw.rect(surf, col, (ROAD_LEFT + c * sq, sy - sq + row * sq, sq, sq))
        for px in (ROAD_LEFT - CURB_WIDTH - 30, ROAD_RIGHT + CURB_WIDTH + 10):
            pygame.draw.rect(surf, (0, 0, 0, 80), (px + 4, sy - 16, 20, 40))
            pygame.draw.rect(surf, (40, 40, 46), (px, sy - 20, 20, 40), border_radius=3)
            pygame.draw.rect(surf, RED, (px, sy - 20, 20, 8), border_radius=3)
        label = "START" if k == 0 else ("FINISH" if k == TOTAL_LAPS else f"LAP {k + 1}")
        img = finish_label(label)
        surf.blit(img, img.get_rect(center=(SCREEN_WIDTH // 2, int(sy + 70))))

    def draw(self):
        cam = self.menu_cam if self.state == "menu" else self.player.dist
        self.draw_world(self.world, cam, objects=self.state != "menu")

        ox = oy = 0
        if self.shake > 0.5:
            s = int(self.shake)
            ox, oy = random.randint(-s, s), random.randint(-s, s)
        screen.fill(GRASS_DARK)
        screen.blit(self.world, (ox, oy))
        screen.blit(VIGNETTE, (0, 0))

        if self.state == "menu":
            self.draw_menu()
        else:
            self.draw_hud()
            if self.state == "countdown":
                self.draw_countdown()
            elif self.state == "paused":
                self.draw_pause()
            elif self.state == "results":
                self.draw_results()
        pygame.display.flip()

    def draw_hud(self):
        p = self.player
        order = self.standings()
        place = order.index(p) + 1

        # position
        draw_panel(screen, (14, 10, 112, 50))
        draw_text(screen, ordinal(place), med_font, YELLOW if place == 1 else WHITE, (24, 20))
        draw_text(screen, f"/{len(self.cars)}", small_font, (200, 200, 200), (92, 34))

        # lap + time
        shown_time = p.finish_time if p.finished else self.race_time if self.state != "countdown" else 0.0
        lap = min(TOTAL_LAPS, max(0, int(p.dist // LAP_LENGTH)) + 1)
        draw_panel(screen, (SCREEN_WIDTH // 2 - 105, 10, 210, 54))
        draw_text(screen, f"LAP {lap}/{TOTAL_LAPS}", small_font, YELLOW, (SCREEN_WIDTH // 2, 16), "midtop")
        draw_text(screen, fmt_time(shown_time), font, WHITE, (SCREEN_WIDTH // 2, 33), "midtop")

        # speed
        draw_panel(screen, (SCREEN_WIDTH - 176, 10, 162, 50))
        draw_text(screen, f"{int(p.speed * KMH)}", med_font, ORANGE if p.boosting else WHITE,
                  (SCREEN_WIDTH - 70, 18), "topright")
        draw_text(screen, "KM/H", small_font, (200, 200, 200), (SCREEN_WIDTH - 64, 33))

        # nitro + coins
        col = ORANGE if p.boosting and (pygame.time.get_ticks() // 100) % 2 else NITRO_BLUE
        draw_bar(screen, 16, SCREEN_HEIGHT - 40, 230, 22, p.nitro / 100, col, "NITRO  (SHIFT)")
        draw_panel(screen, (16, SCREEN_HEIGHT - 108, 112, 32))
        pygame.draw.circle(screen, YELLOW, (34, SCREEN_HEIGHT - 92), 8)
        draw_text(screen, f"x {self.coins}", font, WHITE, (50, SCREEN_HEIGHT - 102))

        # race progress strip (right)
        top, height, x = 80, SCREEN_HEIGHT - 160, SCREEN_WIDTH - 36
        draw_panel(screen, (x - 12, top - 12, 28, height + 24), alpha=140)
        pygame.draw.line(screen, (120, 120, 126), (x + 2, top), (x + 2, top + height), 2)
        for k in range(TOTAL_LAPS + 1):
            y = top + height - int(height * k / TOTAL_LAPS)
            pygame.draw.line(screen, WHITE, (x - 6, y), (x + 10, y), 2)
        for car in sorted(self.cars, key=lambda c: c is p):
            y = top + height - int(height * clamp(car.dist / TOTAL_DIST, 0, 1))
            r = 7 if car is p else 5
            pygame.draw.circle(screen, car.color, (x + 2, y), r)
            pygame.draw.circle(screen, WHITE if car is p else BLACK, (x + 2, y), r, 2)

        # banner
        if self.banner:
            text, secs, color = self.banner
            draw_text(screen, text, med_font if len(text) > 8 else big_font, color,
                      (SCREEN_WIDTH // 2, 120), "center")

        if self.state == "countdown" or (self.state == "racing" and self.race_time < 6):
            draw_text(screen, "UP gas   DOWN brake   LEFT/RIGHT steer   SHIFT nitro   P pause   M mute",
                      small_font, WHITE, (SCREEN_WIDTH // 2, SCREEN_HEIGHT - 18), "center")

    def draw_countdown(self):
        phase = int(self.count_t)
        draw_panel(screen, (SCREEN_WIDTH // 2 - 90, 150, 180, 64), alpha=210)
        for i in range(3):
            lit = i <= phase
            pygame.draw.circle(screen, RED if lit else (60, 20, 20), (SCREEN_WIDTH // 2 - 54 + i * 54, 182), 19)
            if lit:
                pygame.draw.circle(screen, (255, 140, 140), (SCREEN_WIDTH // 2 - 60 + i * 54, 176), 5)
        frac = self.count_t - phase
        size = int(110 + 40 * (1 - frac))
        txt = pygame.font.Font(None, size).render(str(3 - phase), True, WHITE)
        screen.blit(txt, txt.get_rect(center=(SCREEN_WIDTH // 2, 290)))

    def dim(self, alpha=150):
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, alpha))
        screen.blit(overlay, (0, 0))

    def draw_pause(self):
        self.dim()
        draw_panel(screen, (SCREEN_WIDTH // 2 - 200, SCREEN_HEIGHT // 2 - 90, 400, 180), alpha=220)
        draw_text(screen, "PAUSED", big_font, YELLOW, (SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 - 40), "center")
        draw_text(screen, "P / ESC  resume      Q  quit to menu", font, WHITE,
                  (SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 + 30), "center")

    def draw_menu(self):
        self.dim(110)
        cx = SCREEN_WIDTH // 2
        draw_text(screen, "TURBO CIRCUIT", title_font, YELLOW, (cx, 72), "center")
        draw_text(screen, f"{TOTAL_LAPS} LAPS  -  3 RIVALS  -  COLLECT, DODGE, WIN", font, WHITE, (cx, 128), "center")

        draw_text(screen, "DIFFICULTY", small_font, (210, 210, 210), (cx, 184), "center")
        for i, d in enumerate(DIFFICULTIES):
            rect = pygame.Rect(cx - 240 + i * 165, 204, 150, 44)
            selected = i == self.difficulty
            draw_panel(screen, rect, alpha=230 if selected else 140, border=YELLOW if selected else (120, 120, 120))
            draw_text(screen, d["name"], font, YELLOW if selected else (200, 200, 200), rect.center, "center")

        key = str(self.difficulty)
        bt, bs = self.records["time"].get(key), self.records["score"].get(key)
        rec = f"BEST TIME {fmt_time(bt)}   BEST SCORE {bs}" if bt is not None else "NO RECORD YET - SET ONE!"
        draw_text(screen, rec, small_font, WHITE, (cx, 270), "center")

        draw_panel(screen, (cx - 280, 295, 560, 128), alpha=190)
        lines = ["UP/W accelerate    DOWN/S brake    LEFT/RIGHT steer    SHIFT nitro",
                 "P pause     M mute     ESC quit",
                 "Finish 3 laps in 1st place. Coins and score for a faster time.",
                 "Stay on the road - grass slows you down!"]
        for i, line in enumerate(lines):
            draw_text(screen, line, small_font, WHITE if i < 2 else (200, 220, 255), (cx, 315 + i * 26), "center")

        # showcase the cars
        for i, style in enumerate([CAR_STYLES["player"]] + CAR_STYLES["ai"]):
            img = pygame.transform.rotozoom(style["sprite"], 0, 1.2)
            bob = math.sin(pygame.time.get_ticks() / 400 + i) * 4
            screen.blit(img, img.get_rect(center=(cx - 165 + i * 110, 495 + bob)))

        if (pygame.time.get_ticks() // 500) % 2 == 0:
            draw_text(screen, "PRESS ENTER TO START", med_font, WHITE, (cx, 568), "center")

    def draw_results(self):
        self.dim(170)
        p = self.player
        cx = SCREEN_WIDTH // 2
        draw_panel(screen, (cx - 270, 60, 540, 480), alpha=225)

        medal = {1: (255, 205, 60), 2: (200, 205, 215), 3: (205, 130, 70)}.get(p.place, (110, 110, 120))
        pygame.draw.circle(screen, (0, 0, 0), (cx - 190, 128), 40)
        pygame.draw.circle(screen, medal, (cx - 190, 126), 38)
        pygame.draw.circle(screen, lerp_color(medal, WHITE, 0.5), (cx - 190, 126), 38, 3)
        draw_text(screen, str(p.place), big_font, BLACK, (cx - 190, 128), "center", shadow=False)
        headline = ["VICTORY!", "GREAT RACE!", "NOT BAD!", "KEEP PRACTICING"][p.place - 1]
        draw_text(screen, headline, big_font, YELLOW if p.place == 1 else WHITE, (cx + 25, 118), "center")
        draw_text(screen, f"{ordinal(p.place)} PLACE  -  {DIFFICULTIES[self.difficulty]['name']}",
                  font, (210, 210, 210), (cx + 25, 160), "center")

        # standings
        y = 200
        for i, c in enumerate(self.standings()):
            row = pygame.Rect(cx - 240, y + i * 34, 480, 30)
            if c is p:
                pygame.draw.rect(screen, (60, 60, 20), row, border_radius=6)
            pygame.draw.circle(screen, c.color, (row.x + 16, row.centery), 8)
            draw_text(screen, f"{i + 1}.  {c.name}", font, YELLOW if c is p else WHITE, (row.x + 34, row.y + 5))
            t = fmt_time(c.finish_time) if c.finished else "racing..."
            draw_text(screen, t, font, WHITE, (row.right - 10, row.y + 5), "topright")

        # stats
        best_lap = min(self.lap_times) if self.lap_times else 0
        a, b, c = self.score_parts
        stats = [("BEST LAP", fmt_time(best_lap)),
                 ("COINS", f"{self.coins}   (+{a})"),
                 ("POSITION BONUS", f"+{b}"),
                 ("TIME BONUS", f"+{c}")]
        for i, (k, v) in enumerate(stats):
            draw_text(screen, k, small_font, (200, 200, 200), (cx - 230, 354 + i * 26))
            draw_text(screen, v, font, WHITE, (cx + 230, 351 + i * 26), "topright")
        draw_text(screen, f"SCORE  {self.score}", med_font, YELLOW, (cx, 480), "center")
        if self.new_record:
            draw_text(screen, "NEW BEST TIME!", font, GREEN, (cx, 510), "center")
        else:
            draw_text(screen, "SPACE: race again      ESC: menu", small_font, WHITE, (cx, 512), "center")
        if self.new_record:
            draw_text(screen, "SPACE: race again      ESC: menu", small_font, WHITE, (cx, 528), "center")

    # -- main loop -----------------------------------------------------------
    def run(self):
        while self.running:
            dt = min(clock.tick(FPS) / 1000.0, 0.05)
            self.handle_events()
            self.update(dt)
            self.draw()
        pygame.quit()


if __name__ == "__main__":
    RaceGame().run()