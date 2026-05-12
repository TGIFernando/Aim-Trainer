#!/usr/bin/env python3
"""Aim Trainer - Transparent overlay aim training tool. Requires PyQt5."""

import sys
import random
import math
import json
import os
import time as _time

from PyQt5.QtWidgets import QApplication, QWidget
from PyQt5.QtCore import Qt, QTimer, QPointF, QRectF
from PyQt5.QtGui import (
    QPainter, QColor, QBrush, QPen, QFont,
    QPainterPath, QRadialGradient,
)

# ── palette ────────────────────────────────────────────────────────────────────
PANEL_BG   = QColor(10, 10, 25, 210)
ACCENT     = QColor(90, 160, 255)
TEXT_FG    = QColor(230, 230, 240)
TEXT_DIM   = QColor(130, 130, 170)
BTN_NORMAL = QColor(28, 32, 68, 210)
BTN_HOVER  = QColor(52, 58, 120, 230)
BTN_ACTIVE = QColor(68, 92, 210, 240)
HEALTH_BG  = QColor(12, 12, 40, 210)
GOLD       = QColor(255, 210, 50)

# ── constants ──────────────────────────────────────────────────────────────────
TIME_OPTIONS = [30, 60, 120, 180, 300]
TIME_LABELS  = ["30s", "1 min", "2 min", "3 min", "5 min"]

GRID_N    = 3
ACTIVE_N  = 3
GRID_R    = 30
TRACK_R   = 38
DRAIN_PS  = 24.0     # HP per second while holding click on tracking target
MAX_HP    = 100.0
SPD_MIN   = 100.0
SPD_MAX   = 280.0

SCORES_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "highscores.json")

HP_OPTIONS  = [50, 100, 200, 300, 500]
HP_LABELS   = ["50", "100", "200", "300", "500"]

SPD_OPTIONS = [80, 150, 220, 300]
SPD_LABELS  = ["Slow", "Med", "Fast", "Max"]


# ── tiny data classes ──────────────────────────────────────────────────────────
class Button:
    __slots__ = ("rect", "label", "tag", "hovered", "active")

    def __init__(self, rect: QRectF, label: str, tag: str = None):
        self.rect    = rect
        self.label   = label
        self.tag     = tag
        self.hovered = False
        self.active  = False


class HitRing:
    __slots__ = ("x", "y", "life", "base_r")

    def __init__(self, x: float, y: float, base_r: float):
        self.x, self.y = x, y
        self.life   = 1.0
        self.base_r = base_r

    def tick(self, dt: float) -> bool:
        self.life -= dt * 2.6
        return self.life > 0


class BreakEffect:
    """Shards that fly outward when a grid target is hit."""
    __slots__ = ("cx", "cy", "r", "life", "shards")

    def __init__(self, cx: float, cy: float, r: float):
        self.cx, self.cy = cx, cy
        self.r    = r
        self.life = 1.0
        # 8 shards at evenly-spaced angles with slight random jitter
        self.shards = [
            {
                "x":  cx + math.cos(a) * r * 0.3,
                "y":  cy + math.sin(a) * r * 0.3,
                "vx": math.cos(a) * r * random.uniform(5.0, 8.5),
                "vy": math.sin(a) * r * random.uniform(5.0, 8.5),
                "sz": r * random.uniform(0.18, 0.34),
            }
            for a in (
                i * math.pi / 4 + random.uniform(-0.18, 0.18)
                for i in range(8)
            )
        ]

    def tick(self, dt: float) -> bool:
        self.life -= dt * 3.2     # ~0.31 s total
        for s in self.shards:
            s["x"] += s["vx"] * dt
            s["y"] += s["vy"] * dt
            s["vx"] *= 0.78       # friction — shards decelerate quickly
            s["vy"] *= 0.78
        return self.life > 0


# ── main widget ────────────────────────────────────────────────────────────────
class AimTrainer(QWidget):

    # ── setup ──────────────────────────────────────────────────────────────────
    def __init__(self):
        super().__init__()
        self._setup_window()
        self._highscores = self._load_scores()
        self._new_hs     = False
        self._init_vars()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(16)
        self._last_t = _time.monotonic()
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)

    def _setup_window(self):
        self.setWindowFlags(
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint |
            Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        scr = QApplication.primaryScreen().geometry()
        self.setGeometry(scr)

    def _init_vars(self):
        self.state    = "menu"
        self.mode     = "grid"
        self.time_idx = 1

        self.score       = 0
        self.shots       = 0
        self.hits        = 0
        self.time_on_tgt = 0.0
        self.elapsed     = 0.0
        self.time_left   = float(TIME_OPTIONS[self.time_idx])

        # timer waits for first input before counting down
        self._waiting    = True

        # grid
        self.active_cells: set  = set()
        self.cell_rects: list   = []

        # tracking
        w = self.width()  or 1920
        h = self.height() or 1080
        self._tx  = float(w) / 2
        self._ty  = float(h) / 2
        self._tvx = random.choice([-1, 1]) * 160.0
        self._tvy = random.choice([-1, 1]) * 130.0
        self._hp  = MAX_HP
        self._on  = False
        self._mouse_held = False   # must hold LMB to deal damage in tracking

        # tracking settings (persist between rounds — only set once in _init_vars)
        if not hasattr(self, 'track_hp_idx'):
            self.track_hp_idx     = 1      # default 100 HP
            self.track_spd_idx    = 1      # default Med (150 px/s)
            self.track_random_spd = False

        # per-round tracking state
        self._track_max_hp = float(HP_OPTIONS[self.track_hp_idx])
        self._spd_timer    = 0.0

        # visual
        self._rings:  list = []
        self._breaks: list = []
        self._mx = 0
        self._my = 0

        # buttons
        self._menu_btns : list   = []
        self._pause_btns: list   = []
        self._go_btns   : list   = []
        self._pause_btn : Button = Button(QRectF(0, 0, 84, 34), "Pause", "pause")

    # ── high score persistence ─────────────────────────────────────────────────
    def _load_scores(self) -> dict:
        try:
            with open(SCORES_FILE) as f:
                data = json.load(f)
            return {"grid": int(data.get("grid", 0)),
                    "tracking": int(data.get("tracking", 0))}
        except Exception:
            return {"grid": 0, "tracking": 0}

    def _save_scores(self):
        try:
            with open(SCORES_FILE, "w") as f:
                json.dump(self._highscores, f)
        except Exception:
            pass

    # ── game loop ──────────────────────────────────────────────────────────────
    def _tick(self):
        now = _time.monotonic()
        dt  = min(now - self._last_t, 0.1)
        self._last_t = now

        if self.state == "playing":
            if not self._waiting:
                self.time_left -= dt
                if self.time_left <= 0:
                    self.time_left = 0.0
                    self._end_game()
                    return
            # target always moves so player can see it before starting
            if self.mode == "tracking":
                self._tick_tracking(dt)

        self._rings  = [r for r in self._rings  if r.tick(dt)]
        self._breaks = [b for b in self._breaks if b.tick(dt)]
        self.update()

    def _tick_tracking(self, dt: float):
        w, h = self.width(), self.height()
        mg   = TRACK_R + 12

        self._tx = max(mg, min(w - mg, self._tx + self._tvx * dt))
        self._ty = max(mg, min(h - mg, self._ty + self._tvy * dt))

        if self._tx <= mg or self._tx >= w - mg:
            self._tvx = -self._tvx
            self._tvy += random.uniform(-20, 20)
        if self._ty <= mg or self._ty >= h - mg:
            self._tvy = -self._tvy
            self._tvx += random.uniform(-20, 20)

        if self.track_random_spd:
            # periodically snap to a new random speed between 35-100% of selected max
            self._spd_timer -= dt
            if self._spd_timer <= 0:
                self._spd_timer = random.uniform(0.6, 2.2)
                top = float(SPD_OPTIONS[self.track_spd_idx])
                new_spd = random.uniform(top * 0.35, top)
                spd = math.hypot(self._tvx, self._tvy)
                if spd > 1:
                    f = new_spd / spd
                    self._tvx *= f
                    self._tvy *= f
        else:
            # hold exactly at the selected constant speed
            target = float(SPD_OPTIONS[self.track_spd_idx])
            spd = math.hypot(self._tvx, self._tvy)
            if spd > 1:
                f = target / spd
                self._tvx *= f
                self._tvy *= f

        dist     = math.hypot(self._mx - self._tx, self._my - self._ty)
        self._on = dist < TRACK_R

        # damage + accuracy only after player starts (holds click)
        if not self._waiting:
            self.elapsed += dt
            if self._on and self._mouse_held:
                self.time_on_tgt += dt
                self._hp -= DRAIN_PS * dt
                if self._hp <= 0:
                    self._hp = self._track_max_hp
                    self.score += 1
                    self._rings.append(HitRing(self._tx, self._ty, TRACK_R))
                    mg2 = TRACK_R * 3
                    self._tx = random.uniform(mg2, w - mg2)
                    self._ty = random.uniform(mg2, h - mg2)
                    self._tvx = random.choice([-1, 1]) * random.uniform(130, 230)
                    self._tvy = random.choice([-1, 1]) * random.uniform(100, 190)

    # ── game flow ──────────────────────────────────────────────────────────────
    def _start_game(self):
        w, h = self.width(), self.height()
        self.score       = 0
        self.shots       = 0
        self.hits        = 0
        self.time_on_tgt = 0.0
        self.elapsed     = 0.0
        self.time_left   = float(TIME_OPTIONS[self.time_idx])
        self._waiting    = True
        self._mouse_held = False
        self._new_hs     = False
        self._rings.clear()
        self._breaks.clear()

        if self.mode == "grid":
            self._build_grid()
        else:
            mg = TRACK_R * 3
            self._tx = random.uniform(mg, w - mg)
            self._ty = random.uniform(mg, h - mg)
            # initialise speed from settings
            self._track_max_hp = float(HP_OPTIONS[self.track_hp_idx])
            self._spd_timer    = 0.0
            spd   = float(SPD_OPTIONS[self.track_spd_idx])
            angle = random.uniform(0, math.pi * 2)
            self._tvx = math.cos(angle) * spd
            self._tvy = math.sin(angle) * spd
            self._hp  = self._track_max_hp
            self._on  = False

        self.state = "playing"

    def _end_game(self):
        if self.score > 0 and self.score >= self._highscores[self.mode]:
            self._new_hs = True
            self._highscores[self.mode] = self.score
            self._save_scores()
        self._layout_go()
        self.state = "gameover"

    # ── grid helpers ──────────────────────────────────────────────────────────
    def _build_grid(self):
        w, h = self.width(), self.height()
        gw = min(w * 0.52, 540.0)
        gh = min(h * 0.52, 440.0)
        ox = (w - gw) / 2
        oy = (h - gh) / 2
        cw, ch = gw / GRID_N, gh / GRID_N
        self.cell_rects = [
            QRectF(ox + c * cw, oy + r * ch, cw, ch)
            for r in range(GRID_N) for c in range(GRID_N)
        ]
        self.active_cells = set(random.sample(range(GRID_N * GRID_N), ACTIVE_N))

    def _grid_click(self, px: int, py: int):
        # first click starts the timer regardless of whether it's a hit
        if self._waiting:
            self._waiting = False
        self.shots += 1
        for idx in list(self.active_cells):
            rect = self.cell_rects[idx]
            cx   = rect.x() + rect.width()  / 2
            cy   = rect.y() + rect.height() / 2
            if math.hypot(px - cx, py - cy) < GRID_R:
                self.hits  += 1
                self.score += 1
                self._rings.append(HitRing(cx, cy, GRID_R))
                self._breaks.append(BreakEffect(cx, cy, GRID_R))
                self.active_cells.remove(idx)
                self._spawn_cell()
                return

    def _spawn_cell(self):
        pool = set(range(GRID_N * GRID_N)) - self.active_cells
        if pool:
            self.active_cells.add(random.choice(list(pool)))

    # ── button layouts ─────────────────────────────────────────────────────────
    def _btn(self, cx, cy, w, h, label, tag=None) -> Button:
        return Button(QRectF(cx - w / 2, cy - h / 2, w, h), label, tag)

    def _layout_menu(self):
        cx, cy = self.width() / 2, self.height() / 2
        track = (self.mode == "tracking")

        # button y-centres — two layouts depending on mode
        if track:
            my  = cy - 130   # mode buttons
            dy  = cy - 58    # duration buttons
            hy  = cy + 36    # HP buttons
            sy  = cy + 101   # speed buttons
            ry  = cy + 145   # random-speed toggle
            sty = cy + 192   # start
            qy  = cy + 244   # quit
        else:
            my  = cy - 44
            dy  = cy + 30
            sty = cy + 86
            qy  = cy + 140

        self._menu_btns = [
            self._btn(cx - 95, my, 162, 42, "Grid Aim", "mode_grid"),
            self._btn(cx + 95, my, 162, 42, "Tracking", "mode_track"),
        ]

        tx0 = cx - (len(TIME_OPTIONS) * 86) / 2 + 43
        for i, lbl in enumerate(TIME_LABELS):
            b = self._btn(tx0 + i * 86, dy, 72, 34, lbl, f"time_{i}")
            b.active = (i == self.time_idx)
            self._menu_btns.append(b)

        if track:
            # HP buttons
            hx0 = cx - (len(HP_OPTIONS) * 82) / 2 + 41
            for i, lbl in enumerate(HP_LABELS):
                b = self._btn(hx0 + i * 82, hy, 70, 30, lbl, f"hp_{i}")
                b.active = (i == self.track_hp_idx)
                self._menu_btns.append(b)

            # speed buttons
            sx0 = cx - (len(SPD_OPTIONS) * 96) / 2 + 48
            for i, lbl in enumerate(SPD_LABELS):
                b = self._btn(sx0 + i * 96, sy, 82, 30, lbl, f"spd_{i}")
                b.active = (i == self.track_spd_idx)
                self._menu_btns.append(b)

            # random speed toggle
            rlbl = "Random Speed: ON" if self.track_random_spd else "Random Speed: OFF"
            rb = self._btn(cx, ry, 210, 34, rlbl, "toggle_rspd")
            rb.active = self.track_random_spd
            self._menu_btns.append(rb)

        self._menu_btns += [
            self._btn(cx, sty, 162, 44, "Start", "start"),
            self._btn(cx, qy,  110, 34, "Quit",  "quit"),
        ]
        self._menu_btns[0].active = (self.mode == "grid")
        self._menu_btns[1].active = (self.mode == "tracking")

    def _layout_pause(self):
        cx, cy = self.width() / 2, self.height() / 2
        self._pause_btns = [
            self._btn(cx, cy +  4, 162, 44, "Resume",    "resume"),
            self._btn(cx, cy + 60, 162, 44, "Main Menu", "menu"),
            self._btn(cx, cy + 114, 110, 34, "Quit",     "quit"),
        ]

    def _layout_go(self):
        cx, cy = self.width() / 2, self.height() / 2
        self._go_btns = [
            self._btn(cx, cy + 100, 162, 44, "Play Again", "again"),
            self._btn(cx, cy + 154, 162, 44, "Main Menu",  "menu"),
            self._btn(cx, cy + 208, 110, 34, "Quit",       "quit"),
        ]

    def _active_buttons(self) -> list:
        if self.state == "menu":     return self._menu_btns
        if self.state == "paused":   return self._pause_btns
        if self.state == "gameover": return self._go_btns
        if self.state == "playing":  return [self._pause_btn]
        return []

    def _handle_button(self, tag: str):
        if   tag == "quit":       QApplication.quit()
        elif tag == "start":      self._start_game()
        elif tag == "again":      self._start_game()
        elif tag == "resume":     self.state = "playing"
        elif tag == "pause":
            self._layout_pause()
            self.state = "paused"
        elif tag == "menu":
            self._layout_menu()
            self.state = "menu"
        elif tag == "mode_grid":
            self.mode = "grid";     self._layout_menu()
        elif tag == "mode_track":
            self.mode = "tracking"; self._layout_menu()
        elif tag and tag.startswith("time_"):
            self.time_idx = int(tag[5:]); self._layout_menu()
        elif tag and tag.startswith("hp_"):
            self.track_hp_idx = int(tag[3:]); self._layout_menu()
        elif tag and tag.startswith("spd_"):
            self.track_spd_idx = int(tag[4:]); self._layout_menu()
        elif tag == "toggle_rspd":
            self.track_random_spd = not self.track_random_spd; self._layout_menu()

    # ── input ──────────────────────────────────────────────────────────────────
    def mouseMoveEvent(self, ev):
        self._mx, self._my = ev.x(), ev.y()
        for b in self._active_buttons():
            b.hovered = b.rect.contains(ev.x(), ev.y())

    def mousePressEvent(self, ev):
        if ev.button() != Qt.LeftButton:
            return
        px, py = ev.x(), ev.y()

        for b in self._active_buttons():
            if b.rect.contains(px, py):
                self._handle_button(b.tag)
                return

        if self.state == "playing":
            if self.mode == "grid":
                self._grid_click(px, py)
            elif self.mode == "tracking":
                self._mouse_held = True
                if self._waiting:
                    self._waiting = False   # first hold starts the timer

    def mouseReleaseEvent(self, ev):
        if ev.button() == Qt.LeftButton:
            self._mouse_held = False

    def keyPressEvent(self, ev):
        k = ev.key()
        if k == Qt.Key_Escape:
            if self.state == "playing":
                self._layout_pause()
                self.state = "paused"
            elif self.state == "paused":
                self.state = "playing"
            else:
                QApplication.quit()

    # ── stats ───────────────────────────────────────────────────────────────────
    @property
    def accuracy(self) -> float:
        if self.mode == "grid":
            return (self.hits / self.shots * 100) if self.shots else 0.0
        else:
            return (self.time_on_tgt / self.elapsed * 100) if self.elapsed else 0.0

    @property
    def time_str(self) -> str:
        s = max(0, int(self.time_left))
        return f"{s // 60}:{s % 60:02d}"

    # ── paint ──────────────────────────────────────────────────────────────────
    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()

        if self.state == "menu":
            self._draw_menu(p, w, h)
        elif self.state == "playing":
            self._draw_game(p, w, h)
        elif self.state == "paused":
            self._draw_game(p, w, h)
            self._draw_pause_overlay(p, w, h)
        elif self.state == "gameover":
            self._draw_gameover(p, w, h)
        p.end()

    # ── drawing primitives ────────────────────────────────────────────────────
    def _panel(self, p: QPainter, x, y, w, h, r=12):
        path = QPainterPath()
        path.addRoundedRect(QRectF(x, y, w, h), r, r)
        p.fillPath(path, PANEL_BG)
        p.setPen(QPen(ACCENT.darker(200), 1))
        p.drawPath(path)

    def _draw_btn(self, p: QPainter, b: Button):
        color = BTN_ACTIVE if b.active else (BTN_HOVER if b.hovered else BTN_NORMAL)
        path  = QPainterPath()
        path.addRoundedRect(b.rect, 7, 7)
        p.fillPath(path, color)
        border = ACCENT if (b.active or b.hovered) else QColor(80, 80, 130)
        p.setPen(QPen(border, 1))
        p.drawPath(path)
        p.setPen(TEXT_FG)
        wt = QFont.Bold if b.active else QFont.Normal
        p.setFont(QFont("Segoe UI", 11, wt))
        p.drawText(b.rect, Qt.AlignCenter, b.label)

    def _draw_target(self, p: QPainter, cx, cy, r):
        grad = QRadialGradient(cx - r * 0.22, cy - r * 0.22, r * 1.2)
        grad.setColorAt(0.0, QColor(120, 190, 255))
        grad.setColorAt(0.42, QColor(30, 100, 220))
        grad.setColorAt(1.0,  QColor(5, 30, 120))
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(grad))
        p.drawEllipse(QPointF(cx, cy), r, r)
        for frac, alpha in [(0.62, 65), (0.33, 100)]:
            p.setBrush(QBrush(QColor(255, 255, 255, alpha)))
            p.drawEllipse(QPointF(cx, cy), r * frac, r * frac)
        p.setBrush(QBrush(QColor(255, 255, 255, 225)))
        p.drawEllipse(QPointF(cx, cy), r * 0.14, r * 0.14)

    def _draw_rings(self, p: QPainter):
        p.setBrush(Qt.NoBrush)
        for ring in self._rings:
            alpha = int(ring.life * 210)
            scale = 1 + (1 - ring.life) * 1.8
            p.setPen(QPen(QColor(100, 200, 255, alpha), 2))
            p.drawEllipse(QPointF(ring.x, ring.y),
                          ring.base_r * scale, ring.base_r * scale)

    def _draw_breaks(self, p: QPainter):
        p.setPen(Qt.NoPen)
        for fx in self._breaks:
            # center impact flash — bright white-blue, quadratic fade so it
            # feels like a sharp hit rather than a slow fade
            flash_a = int(fx.life * fx.life * 220)
            p.setBrush(QBrush(QColor(190, 220, 255, flash_a)))
            p.drawEllipse(QPointF(fx.cx, fx.cy), fx.r * 0.9, fx.r * 0.9)
            # shards — shrink and fade as they fly outward
            for s in fx.shards:
                sz    = max(1.0, s["sz"] * fx.life)
                alpha = int(fx.life * 240)
                p.setBrush(QBrush(QColor(70, 150, 255, alpha)))
                p.drawEllipse(QPointF(s["x"], s["y"]), sz, sz)

    # ── game screen ───────────────────────────────────────────────────────────
    def _draw_game(self, p: QPainter, w, h):
        if self.mode == "grid":
            self._draw_grid_mode(p)
        else:
            self._draw_tracking_mode(p)
        self._draw_rings(p)
        self._draw_breaks(p)
        self._draw_hud(p, w, h)
        if self._waiting:
            self._draw_start_prompt(p, w, h)

    def _draw_grid_mode(self, p: QPainter):
        p.setPen(QPen(QColor(255, 255, 255, 14), 1))
        p.setBrush(Qt.NoBrush)
        for rect in self.cell_rects:
            p.drawRect(rect)
        for idx in self.active_cells:
            rect = self.cell_rects[idx]
            cx   = rect.x() + rect.width()  / 2
            cy   = rect.y() + rect.height() / 2
            self._draw_target(p, cx, cy, GRID_R)

    def _draw_tracking_mode(self, p: QPainter):
        tx, ty = self._tx, self._ty
        bw, bh = 120, 11
        bx, by = tx - bw / 2, ty + TRACK_R + 12

        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(HEALTH_BG))
        p.drawRoundedRect(QRectF(bx, by, bw, bh), 4, 4)
        pct = max(0.0, self._hp / self._track_max_hp)
        if pct > 0:
            rc = int(220 * (1 - pct) + 40  * pct)
            gc = int(40  * (1 - pct) + 220 * pct)
            p.setBrush(QBrush(QColor(rc, gc, 40)))
            p.drawRoundedRect(QRectF(bx, by, bw * pct, bh), 4, 4)

        # glow only when actively holding and on target
        if self._on and self._mouse_held:
            p.setBrush(Qt.NoBrush)
            p.setPen(QPen(QColor(120, 200, 255, 120), 5))
            p.drawEllipse(QPointF(tx, ty), TRACK_R + 6, TRACK_R + 6)

        self._draw_target(p, tx, ty, TRACK_R)

    def _draw_hud(self, p: QPainter, w, h):
        hs = self._highscores[self.mode]
        self._panel(p, 10, 10, 430, 46, 8)
        p.setPen(TEXT_FG)
        p.setFont(QFont("Segoe UI", 11))
        mode_lbl = "Grid Aim" if self.mode == "grid" else "Tracking"
        hud = (f"Score: {self.score}    "
               f"Best: {hs}    "
               f"Acc: {self.accuracy:.0f}%    "
               f"{self.time_str}    "
               f"[{mode_lbl}]")
        p.drawText(QRectF(18, 22, 408, 24), Qt.AlignLeft | Qt.AlignVCenter, hud)

        br = QRectF(w - 98, 10, 84, 34)
        self._pause_btn.rect    = br
        self._pause_btn.hovered = br.contains(self._mx, self._my)
        self._draw_btn(p, self._pause_btn)

    def _draw_start_prompt(self, p: QPainter, w, h):
        cx, cy = w / 2, h / 2
        if self.mode == "grid":
            msg = "Click any target to start"
        else:
            msg = "Hold left click on the target to start"
        pw, ph = 380, 48
        self._panel(p, cx - pw / 2, cy - ph / 2 + 140, pw, ph, 10)
        p.setPen(ACCENT)
        p.setFont(QFont("Segoe UI", 13, QFont.Bold))
        p.drawText(QRectF(cx - pw / 2, cy - ph / 2 + 140, pw, ph),
                   Qt.AlignCenter, msg)

    # ── overlays ──────────────────────────────────────────────────────────────
    def _draw_pause_overlay(self, p: QPainter, w, h):
        p.fillRect(0, 0, w, h, QColor(0, 0, 0, 115))
        cx, cy = w / 2, h / 2
        self._panel(p, cx - 124, cy - 78, 248, 224, 14)
        p.setPen(ACCENT)
        p.setFont(QFont("Segoe UI", 20, QFont.Bold))
        p.drawText(QRectF(cx - 110, cy - 68, 220, 40), Qt.AlignCenter, "Paused")
        for b in self._pause_btns:
            self._draw_btn(p, b)
        p.setPen(TEXT_DIM)
        p.setFont(QFont("Segoe UI", 8))
        p.drawText(QRectF(cx - 120, cy + 122, 240, 20), Qt.AlignCenter, "ESC to resume")

    def _draw_gameover(self, p: QPainter, w, h):
        cx, cy = w / 2, h / 2
        self._panel(p, cx - 185, cy - 148, 370, 420, 14)

        p.setPen(ACCENT)
        p.setFont(QFont("Segoe UI", 22, QFont.Bold))
        p.drawText(QRectF(cx - 165, cy - 138, 330, 44), Qt.AlignCenter, "Time's Up!")

        # new high score banner
        if self._new_hs:
            p.setPen(GOLD)
            p.setFont(QFont("Segoe UI", 12, QFont.Bold))
            p.drawText(QRectF(cx - 165, cy - 88, 330, 28), Qt.AlignCenter,
                       "New High Score!")

        secs  = TIME_OPTIONS[self.time_idx]
        hs    = self._highscores[self.mode]
        stats = [
            ("Score",      str(self.score)),
            ("Best",       str(hs)),
            ("Accuracy",   f"{self.accuracy:.1f}%"),
            ("Duration",   f"{secs // 60}:{secs % 60:02d}"),
            ("Mode",       "Grid Aim" if self.mode == "grid" else "Tracking"),
        ]
        p.setFont(QFont("Segoe UI", 13))
        y_start = cy - 56 if self._new_hs else cy - 68
        for i, (lbl, val) in enumerate(stats):
            y = y_start + i * 34
            # highlight the score row gold if new high score
            p.setPen(GOLD if (lbl == "Best" and self._new_hs) else TEXT_DIM)
            p.drawText(QRectF(cx - 165, y, 140, 28), Qt.AlignRight | Qt.AlignVCenter, lbl)
            p.setPen(GOLD if (lbl in ("Score", "Best") and self._new_hs) else TEXT_FG)
            p.drawText(QRectF(cx + 28,  y, 140, 28), Qt.AlignLeft  | Qt.AlignVCenter, val)

        for b in self._go_btns:
            self._draw_btn(p, b)

    # ── menu ──────────────────────────────────────────────────────────────────
    def _draw_menu(self, p: QPainter, w, h):
        self._layout_menu()
        cx, cy = w / 2, h / 2
        track = (self.mode == "tracking")
        pw = 520
        ph = 540 if track else 310

        self._panel(p, cx - pw / 2, cy - ph / 2 - 22, pw, ph + 44)

        # title
        p.setPen(ACCENT)
        p.setFont(QFont("Segoe UI", 26, QFont.Bold))
        p.drawText(QRectF(cx - 220, cy - ph / 2 + 2, 440, 52), Qt.AlignCenter, "Aim Trainer")

        # subtitle
        p.setPen(TEXT_DIM)
        p.setFont(QFont("Segoe UI", 9))
        p.drawText(QRectF(cx - 220, cy - ph / 2 + 50, 440, 22),
                   Qt.AlignCenter, "ESC to quit  •  choose mode and duration")

        # high scores
        grid_hs  = self._highscores["grid"]
        track_hs = self._highscores["tracking"]
        p.setPen(GOLD)
        p.setFont(QFont("Segoe UI", 9))
        p.drawText(QRectF(cx - 220, cy - ph / 2 + 70, 440, 20),
                   Qt.AlignCenter,
                   f"Best — Grid: {grid_hs}   Tracking: {track_hs}")

        # section labels (positions match _layout_menu y-values minus 26px)
        p.setPen(TEXT_DIM)
        p.setFont(QFont("Segoe UI", 10))
        if track:
            p.drawText(QRectF(cx - 220, cy - 156, 440, 22), Qt.AlignCenter, "MODE")
            p.drawText(QRectF(cx - 220, cy - 84,  440, 22), Qt.AlignCenter, "DURATION")
            # tracking settings divider
            p.setPen(QPen(ACCENT.darker(200), 1))
            p.drawLine(int(cx - 220), int(cy - 8), int(cx + 220), int(cy - 8))
            p.setPen(TEXT_DIM)
            p.setFont(QFont("Segoe UI", 9))
            p.drawText(QRectF(cx - 220, cy - 6, 440, 18),
                       Qt.AlignCenter, "TRACKING SETTINGS")
            p.setFont(QFont("Segoe UI", 10))
            p.drawText(QRectF(cx - 220, cy + 16, 440, 18), Qt.AlignCenter, "TARGET HP")
            p.drawText(QRectF(cx - 220, cy + 81, 440, 18), Qt.AlignCenter, "SPEED")
        else:
            p.drawText(QRectF(cx - 220, cy - 66, 440, 22), Qt.AlignCenter, "MODE")
            p.drawText(QRectF(cx - 220, cy + 8,  440, 22), Qt.AlignCenter, "DURATION")

        for b in self._menu_btns:
            self._draw_btn(p, b)


# ── entry point ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = AimTrainer()
    window.show()
    sys.exit(app.exec_())
