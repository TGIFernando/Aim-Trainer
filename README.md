# Aim Trainer

A lightweight, transparent overlay aim trainer that runs on top of any application. Built with Python and PyQt5 — no game engine, no Electron, just a frameless window you can leave running over your desktop or game client during downtime.

---

## What It's For

Most aim trainers require you to alt-tab away and lose context on what you were doing. This one lives **on top of your screen** with a fully transparent background, so you can see whatever is behind it — a game lobby, a stream, a browser — while you train.

Two modes cover the two most fundamental aim skills:

- **Grid Aim** — trains target acquisition and click speed
- **Tracking** — trains smooth cursor control on a moving target

---

## Features

- Transparent, frameless window that stays on top of all other apps
- Two game modes: Grid Aim and Tracking
- Configurable session length: 30s, 1 min, 2 min, 3 min, or 5 min
- Live HUD showing score, accuracy, and time remaining
- Pause menu that freezes the timer
- End-of-session stats screen (score, accuracy, duration, mode)
- No install wizard, no account, no telemetry — just a Python script

---

## Requirements

- Python 3.8 or higher
- PyQt5

---

## Installation

**1. Clone the repo**
```bash
git clone https://github.com/TGIFernando/Aim-Trainer.git
cd Aim-Trainer
```

**2. Install the dependency**
```bash
pip install PyQt5
```

Or use the requirements file:
```bash
pip install -r requirements.txt
```

> **Tip:** If you have multiple Python versions, use `pip3` and `python3` instead.

---

## Running

```bash
python aim_trainer.py
```

The window opens full-screen over your primary monitor. The background is transparent — everything behind it stays visible.

---

## Game Modes

### Grid Aim
Nine target positions arranged in a 3×3 grid. Three targets are active at any time. Click a target and it disappears; a new one immediately spawns in a random empty cell. Trains fast target acquisition and click accuracy.

- **Score** — number of targets hit
- **Accuracy** — hits divided by total clicks (penalizes misclicks)

### Tracking
A single target moves continuously around the screen, bouncing off edges and changing direction slightly on each bounce. Hold your cursor over the target to drain its health bar. When the bar empties the target is destroyed, your score goes up by one, and a new target spawns at a random position.

- **Score** — number of targets destroyed
- **Accuracy** — percentage of elapsed time your cursor was on the target

---

## Controls

| Input | Action |
|---|---|
| Left click | Shoot target (Grid Aim) / used for all buttons |
| Mouse hover | Drain health (Tracking) |
| `ESC` | Pause during play / Resume while paused / Quit from menu |
| Pause button | Top-right corner during a session |

---

## Session Flow

```
Menu → choose mode + duration → Start
  └─ Playing → Pause (ESC or button) → Resume
                   └─ Main Menu
  └─ Time's Up → Play Again / Main Menu / Quit
```

---

## Troubleshooting

**Window doesn't appear on top of my game**
Some games run in exclusive fullscreen mode, which takes over the entire display and prevents overlays. Switch the game to **Borderless Windowed** mode and the trainer will sit above it correctly.

**Text or buttons look blurry**
Windows display scaling above 100% can cause this. Right-click `aim_trainer.py`, go to Properties → Compatibility → Change high DPI settings → check "Override high DPI scaling behavior" and set it to "Application".

**`ModuleNotFoundError: No module named 'PyQt5'`**
Run `pip install PyQt5` and make sure you're using the same Python installation you're running the script with.

---

## License

MIT — do whatever you want with it.
