#!/usr/bin/env python3
"""
Aim Trainer Mobile - Touch-based aim trainer for Android.
Requires: pip install kivy
Run on desktop: python aim_trainer_android.py
Package for Android: buildozer android debug  (see buildozer.spec)
"""

import random
import math
import json
import os

from kivy.app import App
from kivy.uix.widget import Widget
from kivy.clock import Clock
from kivy.graphics import (
    Color, Ellipse, Rectangle, Line, RoundedRectangle,
)
from kivy.core.window import Window
from kivy.core.text import Label as CoreLabel


# ── save file path (works on both desktop and Android) ────────────────────────
def _scores_path():
    app = App.get_running_app()
    if app and hasattr(app, 'user_data_dir') and app.user_data_dir:
        return os.path.join(app.user_data_dir, 'highscores.json')
    return os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        'highscores_mobile.json')


# ── game constants ─────────────────────────────────────────────────────────────
TIME_OPTIONS = [30, 60, 120, 180, 300]
TIME_LABELS  = ['30s', '1 min', '2 min', '3 min', '5 min']

GRID_N   = 3
ACTIVE_N = 3
MAX_HP   = 100.0
DRAIN_PS = 28.0     # HP/sec while holding finger on tracking target
SPD_MIN  = 80.0
SPD_MAX  = 220.0


# ── small data classes ─────────────────────────────────────────────────────────
class HitRing:
    __slots__ = ('x', 'y', 'life', 'base_r')

    def __init__(self, x, y, base_r):
        self.x, self.y = x, y
        self.life   = 1.0
        self.base_r = base_r

    def tick(self, dt):
        self.life -= dt * 2.6
        return self.life > 0


class UIButton:
    __slots__ = ('x', 'y', 'w', 'h', 'label', 'tag', 'active')

    def __init__(self, x, y, w, h, label, tag, active=False):
        self.x, self.y = x, y
        self.w, self.h = w, h
        self.label  = label
        self.tag    = tag
        self.active = active

    def hit(self, tx, ty):
        return self.x <= tx <= self.x + self.w and self.y <= ty <= self.y + self.h


# ── main game widget ───────────────────────────────────────────────────────────
class GameWidget(Widget):

    def __init__(self, **kw):
        super().__init__(**kw)
        self._highscores: dict  = {'grid': 0, 'tracking': 0}
        self._new_hs:      bool = False
        self._buttons:     list = []
        self._init_state()
        Clock.schedule_interval(self._tick, 1 / 60)

    # ── app lifecycle ──────────────────────────────────────────────────────────
    def on_parent(self, *_):
        self._highscores = self._load_scores()

    # ── high scores ────────────────────────────────────────────────────────────
    def _load_scores(self):
        try:
            with open(_scores_path()) as f:
                d = json.load(f)
            return {'grid':     int(d.get('grid', 0)),
                    'tracking': int(d.get('tracking', 0))}
        except Exception:
            return {'grid': 0, 'tracking': 0}

    def _save_scores(self):
        try:
            with open(_scores_path(), 'w') as f:
                json.dump(self._highscores, f)
        except Exception:
            pass

    # ── state init ────────────────────────────────────────────────────────────
    def _init_state(self):
        self.state    = 'menu'
        self.mode     = 'grid'
        self.time_idx = 1
        self._reset_round()

    def _reset_round(self):
        self.score       = 0
        self.shots       = 0
        self.hits        = 0
        self.time_on_tgt = 0.0
        self.elapsed_t   = 0.0
        self.time_left   = float(TIME_OPTIONS[self.time_idx])
        self._waiting    = True
        self._rings:     list = []
        # grid
        self.active_cells: set  = set()
        self.cell_rects:   list = []
        # tracking
        w, h = Window.width, Window.height
        self._tx = w / 2.0
        self._ty = h / 2.0
        self._tvx = random.choice([-1, 1]) * 150.0
        self._tvy = random.choice([-1, 1]) * 120.0
        self._hp  = MAX_HP
        self._on  = False
        self._held_uid:  object = None   # uid of touch currently held on target
        self._touch_pos: dict   = {}     # uid → (x, y) for all live touches

    # ── game loop ─────────────────────────────────────────────────────────────
    def _tick(self, dt):
        dt = min(dt, 0.1)

        if self.state == 'playing':
            if not self._waiting:
                self.time_left -= dt
                if self.time_left <= 0:
                    self.time_left = 0.0
                    self._end_game()
                    return
            if self.mode == 'tracking':
                self._tick_tracking(dt)

        self._rings = [r for r in self._rings if r.tick(dt)]
        self._render()

    def _tick_tracking(self, dt):
        w, h = Window.width, Window.height
        tr   = self._tr()
        mg   = tr + 12

        self._tx = max(mg, min(w - mg, self._tx + self._tvx * dt))
        self._ty = max(mg, min(h - mg, self._ty + self._tvy * dt))

        if self._tx <= mg or self._tx >= w - mg:
            self._tvx = -self._tvx
            self._tvy += random.uniform(-18, 18)
        if self._ty <= mg or self._ty >= h - mg:
            self._tvy = -self._tvy
            self._tvx += random.uniform(-18, 18)

        spd = math.hypot(self._tvx, self._tvy)
        if spd > SPD_MAX:
            f = SPD_MAX / spd;  self._tvx *= f;  self._tvy *= f
        elif spd < SPD_MIN:
            f = SPD_MIN / spd;  self._tvx *= f;  self._tvy *= f

        # check if held touch is still on target
        self._on = False
        if self._held_uid is not None:
            pos = self._touch_pos.get(self._held_uid)
            if pos:
                self._on = math.hypot(pos[0] - self._tx, pos[1] - self._ty) < tr

        if not self._waiting:
            self.elapsed_t += dt
            if self._on:
                self.time_on_tgt += dt
                self._hp -= DRAIN_PS * dt
                if self._hp <= 0:
                    self._hp = MAX_HP
                    self.score += 1
                    self._rings.append(HitRing(self._tx, self._ty, tr))
                    mg2 = tr * 3
                    self._tx = random.uniform(mg2, w - mg2)
                    self._ty = random.uniform(mg2, h - mg2)
                    self._tvx = random.choice([-1, 1]) * random.uniform(110, 200)
                    self._tvy = random.choice([-1, 1]) * random.uniform(90, 160)

    # ── sizing (proportional to screen) ───────────────────────────────────────
    def _tr(self):
        """Tracking target radius."""
        return min(Window.width, Window.height) * 0.075

    def _gr(self):
        """Grid target radius."""
        return min(Window.width, Window.height) * 0.058

    # ── game control ──────────────────────────────────────────────────────────
    def _start_game(self):
        self._new_hs = False
        self._reset_round()
        if self.mode == 'grid':
            self._build_grid()
        else:
            tr  = self._tr()
            mg2 = tr * 3
            w, h = Window.width, Window.height
            self._tx = random.uniform(mg2, w - mg2)
            self._ty = random.uniform(mg2, h - mg2)
        self.state = 'playing'

    def _end_game(self):
        if self.score > 0 and self.score >= self._highscores[self.mode]:
            self._new_hs = True
            self._highscores[self.mode] = self.score
            self._save_scores()
        self.state = 'gameover'

    def _build_grid(self):
        w, h  = Window.width, Window.height
        hud_h = h * 0.10
        gw    = w * 0.90
        gh    = (h - hud_h) * 0.82
        ox    = (w - gw) / 2
        oy    = (h - hud_h - gh) / 2
        cw, ch = gw / GRID_N, gh / GRID_N
        self.cell_rects = [
            (ox + c * cw, oy + r * ch, cw, ch)
            for r in range(GRID_N) for c in range(GRID_N)
        ]
        self.active_cells = set(random.sample(range(GRID_N * GRID_N), ACTIVE_N))

    # ── touch input ───────────────────────────────────────────────────────────
    def on_touch_down(self, touch):
        self._touch_pos[touch.uid] = (touch.x, touch.y)

        for btn in self._buttons:
            if btn.hit(touch.x, touch.y):
                self._handle_tag(btn.tag)
                return True

        if self.state == 'playing':
            if self.mode == 'grid':
                self._grid_tap(touch.x, touch.y)
            elif self.mode == 'tracking':
                tr = self._tr()
                if math.hypot(touch.x - self._tx, touch.y - self._ty) < tr:
                    self._held_uid = touch.uid
                    self._on = True
                    if self._waiting:
                        self._waiting = False
        return True

    def on_touch_move(self, touch):
        self._touch_pos[touch.uid] = (touch.x, touch.y)
        # allow sliding finger onto target to begin holding
        if (self.state == 'playing' and self.mode == 'tracking'
                and self._held_uid is None):
            tr = self._tr()
            if math.hypot(touch.x - self._tx, touch.y - self._ty) < tr:
                self._held_uid = touch.uid
                if self._waiting:
                    self._waiting = False
        return True

    def on_touch_up(self, touch):
        self._touch_pos.pop(touch.uid, None)
        if touch.uid == self._held_uid:
            self._held_uid = None
            self._on = False
        return True

    def _grid_tap(self, tx, ty):
        if self._waiting:
            self._waiting = False
        self.shots += 1
        gr = self._gr()
        for idx in list(self.active_cells):
            rx, ry, rw, rh = self.cell_rects[idx]
            cx, cy = rx + rw / 2, ry + rh / 2
            if math.hypot(tx - cx, ty - cy) < gr:
                self.hits  += 1
                self.score += 1
                self._rings.append(HitRing(cx, cy, gr))
                self.active_cells.remove(idx)
                pool = set(range(GRID_N * GRID_N)) - self.active_cells
                if pool:
                    self.active_cells.add(random.choice(list(pool)))
                return

    def _handle_tag(self, tag):
        if   tag == 'quit':       App.get_running_app().stop()
        elif tag == 'start':      self._start_game()
        elif tag == 'again':      self._start_game()
        elif tag == 'resume':     self.state = 'playing'
        elif tag == 'pause':      self.state = 'paused'
        elif tag == 'menu':       self.state = 'menu'
        elif tag == 'mode_grid':  self.mode = 'grid'
        elif tag == 'mode_track': self.mode = 'tracking'
        elif tag and tag.startswith('time_'):
            self.time_idx = int(tag[5:])

    # ── stats ─────────────────────────────────────────────────────────────────
    @property
    def accuracy(self):
        if self.mode == 'grid':
            return (self.hits / self.shots * 100) if self.shots else 0.0
        return (self.time_on_tgt / self.elapsed_t * 100) if self.elapsed_t else 0.0

    @property
    def time_str(self):
        s = max(0, int(self.time_left))
        return f'{s // 60}:{s % 60:02d}'

    # ── render ────────────────────────────────────────────────────────────────
    def _render(self):
        self.canvas.clear()
        self._buttons.clear()
        w, h = Window.width, Window.height

        with self.canvas:
            Color(0.04, 0.04, 0.10, 1)
            Rectangle(pos=(0, 0), size=(w, h))

            if self.state == 'menu':
                self._draw_menu(w, h)
            elif self.state == 'playing':
                self._draw_game(w, h)
            elif self.state == 'paused':
                self._draw_game(w, h)
                self._draw_pause_overlay(w, h)
            elif self.state == 'gameover':
                self._draw_gameover(w, h)

    # ── canvas primitives ─────────────────────────────────────────────────────
    @staticmethod
    def _col(r, g, b, a=1.0):
        Color(r / 255, g / 255, b / 255, a)

    def _panel(self, x, y, w, h, radius=14):
        self._col(10, 10, 25, 0.90)
        RoundedRectangle(pos=(x, y), size=(w, h), radius=[radius])
        self._col(90, 160, 255, 0.35)
        Line(rounded_rectangle=(x, y, w, h, radius), width=1.2)

    def _text(self, text, cx, cy, size=16, color=(230, 230, 240), bold=False):
        lbl = CoreLabel(text=str(text), font_size=size, bold=bold,
                        color=[c / 255 for c in (*color, 255)])
        lbl.refresh()
        tex = lbl.texture
        if tex:
            Color(1, 1, 1, 1)
            Rectangle(texture=tex,
                      pos=(cx - tex.width / 2, cy - tex.height / 2),
                      size=tex.size)

    def _button(self, x, y, w, h, label, tag, active=False):
        """Draw a button and register it for touch testing."""
        self._col(68, 92, 210, 0.94) if active else self._col(28, 32, 68, 0.88)
        RoundedRectangle(pos=(x, y), size=(w, h), radius=[8])
        self._col(90, 160, 255, 0.80 if active else 0.45)
        Line(rounded_rectangle=(x, y, w, h, 8), width=1.2)
        fs = max(12, int(min(w * 0.30, h * 0.45)))
        self._text(label, x + w / 2, y + h / 2,
                   size=fs, color=(230, 230, 240), bold=active)
        self._buttons.append(UIButton(x, y, w, h, label, tag, active))

    def _target(self, cx, cy, r):
        self._col(30, 100, 220)
        Ellipse(pos=(cx - r, cy - r), size=(r * 2, r * 2))
        self._col(120, 190, 255, 0.28)
        mr = r * 0.62
        Ellipse(pos=(cx - mr, cy - mr), size=(mr * 2, mr * 2))
        Color(1, 1, 1, 0.42)
        ir = r * 0.33
        Ellipse(pos=(cx - ir, cy - ir), size=(ir * 2, ir * 2))
        Color(1, 1, 1, 0.90)
        dr = r * 0.14
        Ellipse(pos=(cx - dr, cy - dr), size=(dr * 2, dr * 2))

    def _draw_rings(self):
        for ring in self._rings:
            Color(100 / 255, 200 / 255, 1.0, ring.life * 0.85)
            scale = 1 + (1 - ring.life) * 1.8
            Line(circle=(ring.x, ring.y, ring.base_r * scale), width=2)

    # ── menu screen ───────────────────────────────────────────────────────────
    def _draw_menu(self, w, h):
        cx, cy = w / 2, h / 2
        pw, ph = w * 0.90, h * 0.90
        self._panel(cx - pw / 2, cy - ph / 2, pw, ph)

        fs_title = int(h * 0.052)
        fs_sub   = int(h * 0.024)
        fs_lbl   = int(h * 0.026)

        self._text('Aim Trainer', cx, cy + ph / 2 - h * 0.075,
                   size=fs_title, color=(90, 160, 255), bold=True)
        self._text('Choose mode and duration, then tap Start',
                   cx, cy + ph / 2 - h * 0.135, size=fs_sub, color=(130, 130, 170))

        gs = self._highscores['grid']
        ts = self._highscores['tracking']
        self._text(f'Best  —  Grid: {gs}   Tracking: {ts}',
                   cx, cy + ph / 2 - h * 0.185, size=fs_sub, color=(255, 210, 50))

        # mode row
        self._text('MODE', cx, cy + h * 0.155, size=fs_lbl, color=(130, 130, 170))
        mbw = pw * 0.42
        mbh = h * 0.075
        mby = cy + h * 0.090
        self._button(cx - mbw - 6, mby, mbw, mbh, 'Grid Aim', 'mode_grid',
                     active=(self.mode == 'grid'))
        self._button(cx + 6, mby, mbw, mbh, 'Tracking', 'mode_track',
                     active=(self.mode == 'tracking'))

        # duration row
        self._text('DURATION', cx, cy + h * 0.030, size=fs_lbl, color=(130, 130, 170))
        tbw = (pw - 10) / len(TIME_OPTIONS) - 7
        tbh = h * 0.062
        tx0 = cx - pw / 2 + 5
        for i, lbl in enumerate(TIME_LABELS):
            bx = tx0 + i * (tbw + 7)
            by = cy - h * 0.015
            self._button(bx, by, tbw, tbh, lbl, f'time_{i}',
                         active=(i == self.time_idx))

        abw = pw * 0.50
        abh = h * 0.075
        self._button(cx - abw / 2, cy - h * 0.130, abw, abh, 'Start', 'start')
        qw = pw * 0.30
        self._button(cx - qw / 2,  cy - h * 0.225, qw,  h * 0.060, 'Quit', 'quit')

    # ── playing screen ────────────────────────────────────────────────────────
    def _draw_game(self, w, h):
        if self.mode == 'grid':
            self._draw_grid_mode(w, h)
        else:
            self._draw_tracking_mode(w, h)
        self._draw_rings()
        self._draw_hud(w, h)
        if self._waiting:
            self._draw_start_prompt(w, h)

    def _draw_grid_mode(self, w, h):
        Color(1, 1, 1, 0.06)
        for rx, ry, rw, rh in self.cell_rects:
            Line(rectangle=(rx, ry, rw, rh), width=1)
        gr = self._gr()
        for idx in self.active_cells:
            rx, ry, rw, rh = self.cell_rects[idx]
            self._target(rx + rw / 2, ry + rh / 2, gr)

    def _draw_tracking_mode(self, w, h):
        tx, ty = self._tx, self._ty
        tr     = self._tr()
        bw     = tr * 3.2
        bh     = h * 0.020
        bx     = tx - bw / 2
        by     = ty - tr - bh - 10

        # health bar
        self._col(12, 12, 40, 0.90)
        RoundedRectangle(pos=(bx, by), size=(bw, bh), radius=[4])
        pct = max(0.0, self._hp / MAX_HP)
        if pct > 0:
            rc = int(220 * (1 - pct) + 40  * pct)
            gc = int(40  * (1 - pct) + 220 * pct)
            Color(rc / 255, gc / 255, 40 / 255)
            RoundedRectangle(pos=(bx, by), size=(bw * pct, bh), radius=[4])

        # glow when actively shooting
        if self._on:
            Color(120 / 255, 200 / 255, 1.0, 0.45)
            Line(circle=(tx, ty, tr + 8), width=4)

        self._target(tx, ty, tr)

    def _draw_hud(self, w, h):
        hs    = self._highscores[self.mode]
        hud_h = h * 0.085
        self._panel(6, h - hud_h - 6, w * 0.73, hud_h, 8)
        mode_s = 'Grid' if self.mode == 'grid' else 'Track'
        hud = (f'Score: {self.score}  Best: {hs}  '
               f'Acc: {self.accuracy:.0f}%  {self.time_str}  [{mode_s}]')
        self._text(hud, 6 + w * 0.365, h - hud_h / 2 - 6,
                   size=int(h * 0.028), color=(230, 230, 240))
        pbw = w * 0.22
        pbh = hud_h
        self._button(w - pbw - 6, h - pbh - 6, pbw, pbh, 'Pause', 'pause')

    def _draw_start_prompt(self, w, h):
        cx = w / 2
        msg = ('Tap a target to start'
               if self.mode == 'grid' else
               'Hold finger on target to start')
        pw = w * 0.80
        ph = h * 0.075
        self._panel(cx - pw / 2, h * 0.10, pw, ph, 10)
        self._text(msg, cx, h * 0.10 + ph / 2,
                   size=int(h * 0.030), color=(90, 160, 255), bold=True)

    # ── pause overlay ─────────────────────────────────────────────────────────
    def _draw_pause_overlay(self, w, h):
        Color(0, 0, 0, 0.55)
        Rectangle(pos=(0, 0), size=(w, h))
        cx, cy = w / 2, h / 2
        pw, ph = w * 0.72, h * 0.52
        self._panel(cx - pw / 2, cy - ph / 2, pw, ph)
        self._text('Paused', cx, cy + ph / 2 - h * 0.085,
                   size=int(h * 0.048), color=(90, 160, 255), bold=True)
        bw = pw * 0.65
        bh = h * 0.075
        self._button(cx - bw / 2, cy + h * 0.030, bw, bh, 'Resume',    'resume')
        self._button(cx - bw / 2, cy - h * 0.062, bw, bh, 'Main Menu', 'menu')
        qw = bw * 0.60
        self._button(cx - qw / 2, cy - h * 0.160, qw, h * 0.060, 'Quit', 'quit')

    # ── game over screen ──────────────────────────────────────────────────────
    def _draw_gameover(self, w, h):
        cx, cy = w / 2, h / 2
        pw, ph = w * 0.88, h * 0.88
        self._panel(cx - pw / 2, cy - ph / 2, pw, ph)

        self._text("Time's Up!", cx, cy + ph / 2 - h * 0.080,
                   size=int(h * 0.052), color=(90, 160, 255), bold=True)

        hs_offset = 0.0
        if self._new_hs:
            self._text('★  New High Score!  ★',
                       cx, cy + ph / 2 - h * 0.150,
                       size=int(h * 0.032), color=(255, 210, 50), bold=True)
            hs_offset = h * 0.060

        secs  = TIME_OPTIONS[self.time_idx]
        hs    = self._highscores[self.mode]
        stats = [
            ('Score',    str(self.score)),
            ('Best',     str(hs)),
            ('Accuracy', f'{self.accuracy:.1f}%'),
            ('Duration', f'{secs // 60}:{secs % 60:02d}'),
            ('Mode',     'Grid Aim' if self.mode == 'grid' else 'Tracking'),
        ]
        row_h  = h * 0.078
        base_y = cy + ph / 2 - h * 0.255 - hs_offset
        fs     = int(h * 0.028)
        for i, (lbl, val) in enumerate(stats):
            y    = base_y - i * row_h
            gold = lbl in ('Score', 'Best') and self._new_hs
            self._text(lbl + ':', cx - pw * 0.06, y, size=fs,
                       color=(255, 210, 50) if gold else (130, 130, 170))
            self._text(val, cx + pw * 0.16, y, size=fs,
                       color=(255, 210, 50) if gold else (230, 230, 240),
                       bold=gold)

        bw  = pw * 0.55
        bh  = h * 0.075
        by0 = cy - ph / 2 + h * 0.230
        self._button(cx - bw / 2, by0 + bh * 1.25, bw, bh, 'Play Again', 'again')
        self._button(cx - bw / 2, by0,              bw, bh, 'Main Menu',  'menu')
        qw = bw * 0.60
        self._button(cx - qw / 2, by0 - bh * 1.10, qw, h * 0.060, 'Quit', 'quit')


# ── app entry ─────────────────────────────────────────────────────────────────
class AimTrainerApp(App):
    title = 'Aim Trainer'

    def build(self):
        Window.clearcolor = (0.04, 0.04, 0.10, 1)
        return GameWidget()


if __name__ == '__main__':
    AimTrainerApp().run()
