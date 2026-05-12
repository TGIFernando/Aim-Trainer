# Aim Trainer

A lightweight aim trainer available in two versions:

- **Desktop** (`aim_trainer.py`) — transparent overlay that runs on top of any app. Built with Python + PyQt5.
- **Android** (`aim_trainer_android.py`) — full-screen touch app for Android. Built with Python + Kivy.

Both versions share the same two game modes, high score tracking, and configurable session lengths.

---

## What It's For

Most aim trainers require you to alt-tab away and lose context on what you were doing. The desktop version lives **on top of your screen** with a fully transparent background, so you can see whatever is behind it — a game lobby, a stream, a browser — while you train. The Android version lets you keep training on your phone between matches.

Two modes cover the two most fundamental aim skills:

- **Grid Aim** — trains target acquisition and click speed
- **Tracking** — trains smooth cursor control on a moving target

---

## Features

- Two game modes: Grid Aim and Tracking
- Configurable session length: 30s, 1 min, 2 min, 3 min, or 5 min
- Timer doesn't start until your first shot — no wasted countdown
- Live HUD showing score, personal best, accuracy, and time remaining
- High scores saved to disk and persist between sessions (tracked per mode)
- Pause menu that freezes the timer
- End-of-session stats screen with new high score callout
- No account, no telemetry — just Python scripts

**Desktop only:**
- Transparent, frameless window that stays on top of all other apps

**Android only:**
- Scales to any screen size and orientation
- Touch controls — tap or hold finger depending on mode

---

## Desktop Version

### Requirements

- Python 3.8 or higher
- PyQt5

### Installation

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

### Running

```bash
python aim_trainer.py
```

The window opens full-screen over your primary monitor. The background is transparent — everything behind it stays visible.

### Controls

| Input | Action |
|---|---|
| Left click | Shoot target (Grid Aim) |
| Hold left click | Drain health (Tracking) |
| `ESC` | Pause / Resume / Quit from menu |
| Pause button | Top-right corner during a session |

### Troubleshooting

**Window doesn't appear on top of my game**
Some games run in exclusive fullscreen mode, which prevents overlays. Switch the game to **Borderless Windowed** and the trainer will sit above it correctly.

**Text or buttons look blurry**
Windows display scaling above 100% can cause this. Right-click `aim_trainer.py` → Properties → Compatibility → Change high DPI settings → check "Override high DPI scaling behavior" → set to "Application".

**`ModuleNotFoundError: No module named 'PyQt5'`**
Run `pip install PyQt5` and make sure you're using the same Python installation you're running the script with.

---

## Android Version

### Requirements

- Python 3.8 or higher
- Kivy (for running on desktop to test)
- Buildozer (for building the APK — Linux or WSL only)

### Testing on Desktop First

Before building for Android you can run the app on your PC to verify it works:

```bash
pip install kivy
python aim_trainer_android.py
```

It opens as a regular window using the same game logic as the Android build.

### Building the Android APK

Buildozer (the standard tool for packaging Kivy apps as APKs) only runs on **Linux**. If you're on Windows, use **WSL (Windows Subsystem for Linux)**.

**1. Open a Linux/WSL terminal and navigate to the project folder**

**2. Install Buildozer and its dependencies**
```bash
pip install buildozer
sudo apt install -y git zip unzip openjdk-17-jdk python3-pip
```

**3. Build the debug APK**
```bash
buildozer android debug
```

The first build downloads the Android SDK/NDK automatically — this takes a while (10–20 min). Subsequent builds are much faster.

**4. Find your APK**

The APK is output to:
```
bin/aimtrainer-1.0-arm64-v8a_armeabi-v7a-debug.apk
```

**5. Install on your device**

Transfer the APK to your phone and open it. You may need to enable **"Install from unknown sources"** in your Android settings (Settings → Security → Unknown Sources, or Settings → Apps → Special app access → Install unknown apps).

Alternatively, deploy directly over USB with ADB:
```bash
buildozer android deploy run
```

> **Tip:** For a release build ready to share, use `buildozer android release` instead and sign the APK with `jarsigner`.

### Android Controls

| Input | Action |
|---|---|
| Tap a target | Shoot (Grid Aim) |
| Hold finger on target | Drain health (Tracking) |
| Slide finger onto target | Also starts tracking — no need to lift and re-tap |
| Pause button | Bottom-right corner during a session |

### Android Troubleshooting

**Build fails with SDK/NDK errors**
Make sure you have Java 17 installed (`java -version` should show 17). Buildozer can also sometimes fix itself on a second run: `buildozer android debug` again after a failure.

**App installs but crashes on launch**
Run `buildozer android logcat` with your device connected to see the Python traceback.

**Kivy not found during build**
Make sure `requirements = python3,kivy==2.3.0,pillow` is in `buildozer.spec` and hasn't been modified.

---

## Game Modes (both versions)

### Grid Aim
Nine positions arranged in a 3×3 grid. Three targets are active at any time. Shoot a target and it disappears; a new one immediately spawns in a random empty cell. Trains fast target acquisition and accuracy.

- **Score** — number of targets hit
- **Accuracy** — hits divided by total shots (penalizes misses)

### Tracking
A single target moves continuously around the screen, bouncing off edges. Hold your fire button (mouse or finger) on the target to drain its health bar. When the bar empties the target is destroyed, score goes up by one, and a new target spawns elsewhere.

- **Score** — number of targets destroyed
- **Accuracy** — percentage of session time spent actively shooting the target

#### Tracking Settings

Three settings are available from the main menu when Tracking mode is selected. They persist between rounds until you change them.

| Setting | Options | Description |
|---|---|---|
| **Target HP** | 50 / 100 / 200 / 300 / 500 | Health the target starts with. Lower HP means faster kills and a faster-paced session. |
| **Speed** | Slow (80) / Med (150) / Fast (220) / Max (300) | Target movement speed in pixels per second. The target bounces off edges and nudges slightly on each wall hit. |
| **Random Speed** | OFF / ON | When ON, the target randomly snaps to a new speed (between 35%–100% of the Speed ceiling) every 0.6–2.2 seconds, forcing you to adjust your tracking continuously. |

---

## Session Flow

```
Menu → choose mode + duration → Start
  └─ Waiting for first input (timer paused)
  └─ Playing → Pause → Resume
                  └─ Main Menu
  └─ Time's Up → stats screen → Play Again / Main Menu / Quit
```

---

## Files

| File | Description |
|---|---|
| `aim_trainer.py` | Desktop version (PyQt5, transparent overlay) |
| `aim_trainer_android.py` | Android version (Kivy, touch controls) |
| `requirements.txt` | Desktop dependency (`PyQt5`) |
| `buildozer.spec` | Android packaging config |
| `highscores.json` | Desktop high scores (auto-created on first run) |
| `highscores_mobile.json` | Android high scores when testing on desktop |

---

## License

MIT — do whatever you want with it.
