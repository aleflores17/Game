# Game

A collection of games created with Pygame to learn game development fundamentals.

## Games

### Pong
A classic two-player Pong game where players control paddles to hit a ball back and forth.

**How to Play:**
- **Player 1** (Left Paddle): Use `W` to move up, `S` to move down
- **Player 2** (Right Paddle): Use `UP ARROW` to move up, `DOWN ARROW` to move down
- First player to miss loses a point to the opponent
- Press `ESC` or close the window to exit

### Race Game
A top-down racing game where you compete against an AI opponent to reach 3000 distance first.

**How to Play:**
- **UP ARROW**: Accelerate forward
- **DOWN ARROW**: Brake/Reverse
- **LEFT ARROW**: Steer left
- **RIGHT ARROW**: Steer right
- Avoid gray obstacles on the road
- First to reach 3000 distance wins!
- Press `SPACE` to restart after game ends
- Press `ESC` to exit

**Features:**
- AI opponent with obstacle avoidance
- Progress bars showing race progress
- Speed and distance tracking
- Collision detection with obstacles
- Smooth acceleration and friction physics

## Installation

1. Clone the repository:
```bash
git clone https://github.com/aleflores17/Game.git
cd Game
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

## Running the Games

To play Pong:
```bash
python pong.py
```

To play Race Game:
```bash
python race_game.py
```

## Learning Concepts

These projects demonstrate:
- Game loops and frame rate management
- Sprite collision detection
- Keyboard input handling
- Game scoring and progress systems
- Physics (movement, acceleration, friction)
- AI opponent behavior
- Obstacle generation and management

## Future Games

Planned additions:
- Snake
- Breakout/Brick Breaker
- Space Invaders
- Flappy Bird
- Tetris

## Requirements

- Python 3.7+
- Pygame 2.5.2+

## License

MIT
