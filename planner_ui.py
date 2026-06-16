#!/usr/bin/env python3
"""Rate-Limit Planner — tracks API quota across 7-day billing cycles."""
import tkinter as tk
from datetime import datetime, timedelta
import json
from pathlib import Path

# ─── Data ────────────────────────────────────────────────────────────────────

TOOLS = ['codex', 'claude']

PLANS = [
    ("WAGD",          {1:  0, 2:  0, 3:  0, 4:  0, 5:  0, 6:  0, 7:100}),
    ("Conservative 3",{1:  5, 2:  5, 3:  5, 4:  5, 5:  5, 6: 15, 7: 60}),
    ("Conservative 2",{1:  5, 2:  5, 3:  5, 4:  5, 5: 15, 6: 25, 7: 40}),
    ("Conservative 1",{1: 10, 2: 10, 3: 10, 4: 15, 5: 15, 6: 20, 7: 20}),
    ("Linear",        {1: 15, 2: 14, 3: 14, 4: 14, 5: 14, 6: 14, 7: 15}),
    ("Balanced",      {1: 20, 2: 20, 3: 15, 4: 15, 5: 10, 6: 10, 7: 10}),
    ("Progressive 1", {1: 30, 2: 25, 3: 20, 4: 10, 5:  5, 6:  5, 7:  5}),
    ("Progressive 2", {1: 40, 2: 25, 3: 15, 4:  5, 5:  5, 6:  5, 7:  5}),
    ("Progressive 3", {1: 50, 2: 20, 3: 10, 4:  5, 5:  5, 6:  5, 7:  5}),
    ("Aggressive 1",  {1: 60, 2: 15, 3:  5, 4:  5, 5:  5, 6:  5, 7:  5}),
    ("Aggressive 2",  {1: 70, 2:  5, 3:  5, 4:  5, 5:  5, 6:  5, 7:  5}),
    ("YOLO",          {1:100, 2:  0, 3:  0, 4:  0, 5:  0, 6:  0, 7:  0}),
]
PLAN_NAMES   = [p[0] for p in PLANS]
PLAN_TARGETS = {p[0]: p[1] for p in PLANS}
WEEKDAYS_EN   = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
SETTINGS_FILE = Path(__file__).parent / '.settings.json'

# ─── Colors ──────────────────────────────────────────────────────────────────

BG      = '#1e1e1e'
FG      = '#e0e0e0'
DIM     = '#888'
BTN_BG  = '#2d2d2d'
SEL_BG  = '#2a5580'
SEL_FG  = '#ffffff'
SEP_CLR = '#444'
WARN    = '#ff7070'
OK_CLR  = '#70d490'
VAL_FG  = '#7ec8e3'
RES_BG  = '#141414'

# ─── Settings ────────────────────────────────────────────────────────────────

def _default_settings():
    now = datetime.now()
    return {
        "last_tool": "codex",
        "tools": {t: {"plan": "Linear", "reset_weekday": (now.weekday() + 1) % 7,
                       "hour": now.hour, "minute": now.minute, "value": 50}
                  for t in TOOLS}
    }

def load_settings():
    s = _default_settings()
    if not SETTINGS_FILE.exists():
        return s
    try:
        saved = json.loads(SETTINGS_FILE.read_text())
        if saved.get("last_tool") in TOOLS:
            s["last_tool"] = saved["last_tool"]
        for t in TOOLS:
            if t in saved.get("tools", {}):
                for k in s["tools"][t]:
                    if k in saved["tools"][t]:
                        s["tools"][t][k] = saved["tools"][t][k]
                if "reset_weekday" not in saved["tools"][t] and "date_offset" in saved["tools"][t]:
                    try:
                        offset = int(saved["tools"][t]["date_offset"])
                    except Exception:
                        offset = 1
                    s["tools"][t]["reset_weekday"] = (datetime.now().weekday() + offset) % 7
    except Exception:
        pass
    return s

def save_settings(s):
    try:
        SETTINGS_FILE.write_text(json.dumps(s, indent=2))
    except Exception:
        pass

# ─── Tooltip ─────────────────────────────────────────────────────────────────

class Tooltip:
    def __init__(self, widget, text, delay=600):
        self.widget, self.text, self.delay = widget, text, delay
        self._job = self._tip = None
        widget.bind('<Enter>',       self._schedule, add='+')
        widget.bind('<Leave>',       self._cancel,   add='+')
        widget.bind('<ButtonPress>', self._cancel,   add='+')

    def _schedule(self, _=None):
        self._cancel()
        self._job = self.widget.after(self.delay, self._show)

    def _cancel(self, _=None):
        if self._job:
            self.widget.after_cancel(self._job)
            self._job = None
        if self._tip:
            self._tip.destroy()
            self._tip = None

    def _show(self):
        x = self.widget.winfo_rootx() + 4
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 6
        self._tip = tk.Toplevel(self.widget)
        self._tip.wm_overrideredirect(True)
        self._tip.wm_geometry(f"+{x}+{y}")
        self._tip.attributes('-topmost', True)
        tk.Label(self._tip, text=self.text, bg='#252525', fg='#ccc',
                 font=('Courier', 9), relief='flat', padx=8, pady=5,
                 justify='left').pack()

# ─── App ─────────────────────────────────────────────────────────────────────

class App:
    def __init__(self, root):
        self.root = root
        self.root.title("Rate-Limit Planner")
        self.root.configure(bg=BG)
        self.root.minsize(940, 680)

        self.settings = load_settings()
        self.tool = self.settings["last_tool"]

        self.selected_plan = "Linear"
        self.reset_weekday = (datetime.now().weekday() + 1) % 7
        self.hour          = 23
        self.minute        = 59
        self.value         = 50

        self.hour_str   = tk.StringVar()
        self.min_str    = tk.StringVar()
        self.slider_var = tk.IntVar()

        self._build_ui()
        self._restore_tool(self.tool)
        self.calculate()
        self._schedule_update()

    # ── Build UI ─────────────────────────────────────────────────────────────

    def _build_ui(self):
        PAD = dict(padx=8, pady=5)

        # Row 1 – Tool
        f = tk.Frame(self.root, bg=BG)
        f.pack(fill='x', **PAD)
        tk.Label(f, text="Tool:", bg=BG, fg=DIM, width=6, anchor='w',
                 font=('Sans', 9)).pack(side='left')
        self.tool_btns = {}
        for t in TOOLS:
            b = tk.Button(f, text=t.upper(), width=12, relief='flat',
                          bg=BTN_BG, fg=FG, cursor='hand2',
                          font=('Sans', 10, 'bold'),
                          activebackground=SEL_BG, activeforeground=SEL_FG,
                          command=lambda x=t: self._sel_tool(x))
            b.pack(side='left', padx=5)
            self.tool_btns[t] = b

        tk.Frame(self.root, bg=SEP_CLR, height=1).pack(fill='x', padx=8)

        # Rows 2-3 – Plans
        pf = tk.Frame(self.root, bg=BG)
        pf.pack(fill='x', **PAD)
        tk.Label(pf, text="Plan:", bg=BG, fg=DIM, width=6, anchor='nw',
                 font=('Sans', 9)).pack(side='left')
        pc = tk.Frame(pf, bg=BG)
        pc.pack(side='left', fill='x', expand=True)
        r1 = tk.Frame(pc, bg=BG); r1.pack(fill='x')
        r2 = tk.Frame(pc, bg=BG); r2.pack(fill='x')
        self.plan_btns = {}
        self.plan_frames = {}
        for i, name in enumerate(PLAN_NAMES):
            row = r1 if i < 6 else r2
            wrap = tk.Frame(row, bg=SEP_CLR, padx=1, pady=1)
            wrap.pack(side='left', padx=2, pady=2)
            b = tk.Button(wrap, text=name, width=14, relief='flat',
                          bg=BTN_BG, fg=FG, cursor='hand2', font=('Sans', 8),
                          activebackground=SEL_BG, activeforeground=SEL_FG,
                          command=lambda n=name: self._sel_plan(n))
            b.pack(fill='both', expand=True)
            self.plan_btns[name] = b
            self.plan_frames[name] = wrap
            t = PLAN_TARGETS[name]
            tip = f"{name}\n" + "\n".join(f"Day {d}: {t[d]:>3}%" for d in range(1, 8))
            Tooltip(b, tip, delay=600)

        # Plan preview
        self.plan_preview = tk.Frame(self.root, bg=BG)
        self.plan_preview.pack(fill='x', padx=20, pady=(0, 2))
        self.plan_canvas = tk.Canvas(self.plan_preview, height=54, bg=BG,
                                     highlightthickness=0)
        self.plan_canvas.pack(fill='x')
        self.plan_canvas.bind('<Configure>', lambda _: self._draw_preview())
        self.plan_labels = tk.Frame(self.plan_preview, bg=BG)
        self.plan_labels.pack(fill='x', pady=(1, 0))
        self.plan_value_labels = []
        for i in range(7):
            lbl = tk.Label(self.plan_labels, text='0%', bg=BG, fg='#9a9a9a',
                           font=('Sans', 8), anchor='center')
            lbl.grid(row=0, column=i, sticky='ew')
            self.plan_labels.grid_columnconfigure(i, weight=1)
            self.plan_value_labels.append(lbl)

        tk.Frame(self.root, bg=SEP_CLR, height=1).pack(fill='x', padx=8)

        # Row 4 – Date
        df = tk.Frame(self.root, bg=BG)
        df.pack(fill='x', **PAD)
        tk.Label(df, text="Reset:", bg=BG, fg=DIM, width=6, anchor='w',
                 font=('Sans', 9)).pack(side='left')
        self.date_btns = {}
        visible_dates = self._visible_dates()
        for i, d in enumerate(visible_dates):
            lbl = f"{WEEKDAYS_EN[d.weekday()]}\n{d.strftime('%d.%m')}"
            b = tk.Button(df, text=lbl, width=7, relief='flat',
                          bg=BTN_BG, fg=FG, cursor='hand2', font=('Sans', 8),
                          justify='center',
                          activebackground=SEL_BG, activeforeground=SEL_FG,
                          command=lambda idx=i: self._sel_date(idx))
            b.pack(side='left', padx=2)
            self.date_btns[i] = b

        tk.Frame(self.root, bg=SEP_CLR, height=1).pack(fill='x', padx=8)

        # Row 5 – Time
        tf = tk.Frame(self.root, bg=BG)
        tf.pack(fill='x', **PAD)
        tk.Label(tf, text="Time:", bg=BG, fg=DIM, width=6, anchor='w',
                 font=('Sans', 9)).pack(side='left')

        def spin(parent, txt, cmd):
            return tk.Button(parent, text=txt, width=1, relief='flat',
                             bg=BTN_BG, fg=FG, cursor='hand2',
                             font=('Mono', 10, 'bold'),
                             activebackground=SEL_BG, command=cmd)

        spin(tf, '−', self._dec_h).pack(side='left', padx=(2, 1))
        self.hour_entry = tk.Entry(
            tf, textvariable=self.hour_str, width=4, justify='center',
            bg=BTN_BG, fg='white', insertbackground='white', relief='flat',
            font=('Mono', 15, 'bold')
        )
        self.hour_entry.config(validate='key',
                               validatecommand=(self.root.register(self._validate_time_input), '%P'))
        self.hour_entry.bind('<KeyRelease>', lambda _e: self._sync_time_from_entry('hour'))
        self.hour_entry.bind('<FocusOut>', lambda _e: self._finalize_time_entry('hour'))
        self.hour_entry.bind('<Return>', lambda _e: self._finalize_time_entry('hour'))
        self.hour_entry.bind('<KP_Enter>', lambda _e: self._finalize_time_entry('hour'))
        self.hour_entry.pack(side='left')
        spin(tf, '+', self._inc_h).pack(side='left', padx=(1, 4))
        tk.Label(tf, text=':', bg=BG, fg=FG, font=('Mono', 15)).pack(side='left', padx=(2, 4))
        spin(tf, '−', self._dec_m).pack(side='left', padx=(1, 1))
        self.min_entry = tk.Entry(
            tf, textvariable=self.min_str, width=4, justify='center',
            bg=BTN_BG, fg='white', insertbackground='white', relief='flat',
            font=('Mono', 15, 'bold')
        )
        self.min_entry.config(validate='key',
                              validatecommand=(self.root.register(self._validate_time_input), '%P'))
        self.min_entry.bind('<KeyRelease>', lambda _e: self._sync_time_from_entry('minute'))
        self.min_entry.bind('<FocusOut>', lambda _e: self._finalize_time_entry('minute'))
        self.min_entry.bind('<Return>', lambda _e: self._finalize_time_entry('minute'))
        self.min_entry.bind('<KP_Enter>', lambda _e: self._finalize_time_entry('minute'))
        self.min_entry.pack(side='left')
        spin(tf, '+', self._inc_m).pack(side='left', padx=(1, 4))
        tk.Button(tf, text='[00]', width=4, relief='flat', bg=BTN_BG, fg=FG,
                  cursor='hand2', font=('Sans', 9), activebackground=SEL_BG,
                  command=self._reset_minutes).pack(side='left', padx=(6, 0))

        tk.Frame(self.root, bg=SEP_CLR, height=1).pack(fill='x', padx=8)

        # Row 6 – Slider
        sf = tk.Frame(self.root, bg=BG)
        sf.pack(fill='x', **PAD)
        tk.Label(sf, text='Current:', bg=BG, fg='#aaa',
                 width=8, anchor='w', font=('Sans', 10, 'bold')).pack(side='left')
        spin(sf, '−', self._dec_val).pack(side='left', padx=2)
        spin(sf, '+', self._inc_val).pack(side='left', padx=2)
        self.slider = tk.Scale(sf, from_=0, to=100, resolution=1,
                               variable=self.slider_var, orient='horizontal',
                               bg=BG, fg=FG, troughcolor='#333',
                               highlightthickness=0, bd=0,
                               showvalue=False, sliderlength=22,
                               command=self._on_slide)
        self.slider.pack(side='left', fill='x', expand=True, padx=8)
        self.val_lbl = tk.Label(sf, text='50', bg=BG, fg='white',
                                width=4, font=('Mono', 15, 'bold'), anchor='e')
        self.val_lbl.pack(side='left')

        tk.Frame(self.root, bg=SEP_CLR, height=1).pack(fill='x', padx=8)

        # Result
        rf = tk.Frame(self.root, bg=BG)
        rf.pack(fill='both', expand=True, padx=8, pady=4)
        self.result_panel = tk.Frame(rf, bg=RES_BG, highlightbackground=SEP_CLR,
                                     highlightthickness=1)
        self.result_panel.pack(fill='both', expand=True)
        result_body = tk.Frame(self.result_panel, bg=RES_BG)
        result_body.pack(fill='both', expand=True, padx=12, pady=10)
        self.result_fields = {}
        result_body.grid_columnconfigure(0, weight=1)
        result_body.grid_columnconfigure(1, weight=1)

        def add_field(row, col, key, title, value_fg=FG, value_font=('Courier', 11, 'bold')):
            cell = tk.Frame(result_body, bg=RES_BG)
            cell.grid(row=row, column=col, sticky='w', padx=(0, 20), pady=(0, 10))
            tk.Label(cell, text=title, bg=RES_BG, fg='#8c8c8c',
                     font=('Sans', 8), anchor='w').pack(anchor='w')
            lbl = tk.Label(cell, text='', bg=RES_BG, fg=value_fg,
                           font=value_font, anchor='w')
            lbl.pack(anchor='w', pady=(1, 0))
            self.result_fields[key] = lbl

        add_field(0, 0, 'tool', 'Tool')
        add_field(0, 1, 'plan', 'Plan')
        add_field(1, 0, 'mode', 'Mode')
        add_field(1, 1, 'reset', 'Reset')
        add_field(2, 0, 'cycle_day', 'Cycle day')
        add_field(2, 1, 'time_left', 'Time left')
        add_field(3, 0, 'day_start', 'Start of day')
        add_field(3, 1, 'current', 'Current', VAL_FG)
        add_field(4, 0, 'daily_target', 'Daily target')
        add_field(4, 1, 'goal', 'Goal')
        status = tk.Frame(result_body, bg=RES_BG)
        status.grid(row=5, column=0, columnspan=2, sticky='w', pady=(2, 0))
        tk.Label(status, text='Status', bg=RES_BG, fg='#8c8c8c',
                 font=('Sans', 8), anchor='w').pack(anchor='w')
        self.result_fields['status'] = tk.Label(
            status, text='', bg=RES_BG, fg=OK_CLR,
            font=('Courier', 11, 'bold'), anchor='w'
        )
        self.result_fields['status'].pack(anchor='w', pady=(1, 0))

        tk.Frame(self.root, bg=SEP_CLR, height=1).pack(fill='x', padx=8)

        # Bottom row
        bf = tk.Frame(self.root, bg=BG)
        bf.pack(fill='x', padx=8, pady=6)
        tk.Button(bf, text='Quit', command=self.root.destroy,
                  bg='#401a1a', fg='#d49090', relief='flat', cursor='hand2',
                  font=('Sans', 10), width=14, pady=5,
                  activebackground='#602020').pack(side='right', padx=4)

    # ── Plan preview ─────────────────────────────────────────────────────────

    def _current_day_num(self):
        return self._cycle_context()[2]

    def _draw_preview(self):
        c = self.plan_canvas
        c.delete('all')
        w, h = c.winfo_width(), c.winfo_height()
        if w < 10 or h < 10:
            return
        targets = PLAN_TARGETS.get(self.selected_plan, PLAN_TARGETS["Linear"])
        today   = self._current_day_num()
        max_val = max(targets[i] for i in range(1, 8)) or 1
        bar_zone = h - 6
        col_w    = w / 7
        for i in range(1, 8):
            x0, x1 = (i - 1) * col_w, i * col_w
            val = targets[i]
            bh  = (val / max_val) * bar_zone
            color = '#5ab0f0' if i == today else ('#1e3d54' if i < today else '#2a5580')
            if bh > 1:
                c.create_rectangle(x0 + 3, bar_zone - bh, x1 - 3, bar_zone - 2,
                                   fill=color, outline='')
            if i - 1 < len(self.plan_value_labels):
                lbl = self.plan_value_labels[i - 1]
                lbl.config(text=f"{val}%", fg='#ffffff' if i == today else '#9a9a9a',
                           font=('Sans', 8, 'bold' if i == today else 'normal'))

    # ── Actions ──────────────────────────────────────────────────────────────

    def _sel_tool(self, t):
        self._save_current()
        self.tool = t
        self.settings["last_tool"] = t
        self._restore_tool(t)
        save_settings(self.settings)
        self.calculate()

    def _sel_plan(self, name):
        self.selected_plan = name
        self._hi(self.plan_btns, name)
        self._commit()

    def _sel_date(self, idx):
        visible = self._visible_dates()
        if idx < len(visible):
            self.reset_weekday = visible[idx].weekday()
        self._refresh_calendar()
        self._commit()

    def _inc_h(self):
        self.hour = (self.hour + 1) % 24
        self.hour_str.set(f"{self.hour:02d}"); self._commit()

    def _dec_h(self):
        self.hour = (self.hour - 1) % 24
        self.hour_str.set(f"{self.hour:02d}"); self._commit()

    def _inc_m(self):
        self.minute = (self.minute + 1) % 60
        self.min_str.set(f"{self.minute:02d}"); self._commit()

    def _dec_m(self):
        self.minute = (self.minute - 1) % 60
        self.min_str.set(f"{self.minute:02d}"); self._commit()

    def _reset_minutes(self):
        self.minute = 0
        self.min_str.set('00')
        self._commit()

    def _on_slide(self, val):
        self.value = int(float(val))
        self.val_lbl.config(text=str(self.value)); self._commit()

    def _inc_val(self):
        self.value = min(100, self.value + 1)
        self.slider_var.set(self.value)
        self.val_lbl.config(text=str(self.value)); self._commit()

    def _dec_val(self):
        self.value = max(0, self.value - 1)
        self.slider_var.set(self.value)
        self.val_lbl.config(text=str(self.value)); self._commit()

    def _validate_time_input(self, proposed):
        return proposed == '' or (proposed.isdigit() and len(proposed) <= 2)

    def _sync_time_from_entry(self, kind):
        var = self.hour_str if kind == 'hour' else self.min_str
        raw = var.get().strip()
        limit = 23 if kind == 'hour' else 59
        if not raw.isdigit():
            return
        value = int(raw)
        if value > limit:
            var.set('00')
            if kind == 'hour':
                self.hour = 0
            else:
                self.minute = 0
            self._commit()
            return
        if kind == 'hour':
            self.hour = value
        else:
            self.minute = value
        self._commit()

    def _finalize_time_entry(self, kind):
        var = self.hour_str if kind == 'hour' else self.min_str
        raw = var.get().strip()
        limit = 23 if kind == 'hour' else 59
        if not raw.isdigit() or int(raw) > limit:
            value = 0
        else:
            value = int(raw)
        var.set(f"{value:02d}")
        if kind == 'hour':
            self.hour = value
        else:
            self.minute = value
        self._commit()

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _hi(self, btn_dict, active):
        for k, b in btn_dict.items():
            b.config(bg=SEL_BG if k == active else BTN_BG,
                     fg=SEL_FG if k == active else FG)

    def _visible_dates(self):
        today = datetime.now().date()
        return [today + timedelta(days=i) for i in range(8)]

    def _next_reset_datetime(self):
        now = datetime.now()
        candidate = datetime(now.year, now.month, now.day, self.hour, self.minute)
        days_ahead = (self.reset_weekday - now.weekday()) % 7
        candidate += timedelta(days=days_ahead)
        if candidate < now:
            candidate += timedelta(days=7)
        return candidate

    def _refresh_calendar(self):
        visible = self._visible_dates()
        active_reset = self._next_reset_datetime().date()
        for idx, b in self.date_btns.items():
            d = visible[idx]
            b.config(text=f"{WEEKDAYS_EN[d.weekday()]}\n{d.strftime('%d.%m')}")
            if d == active_reset:
                b.config(bg=SEL_BG, fg=SEL_FG)
            else:
                b.config(bg=BTN_BG, fg=FG)
        self._update_plan_borders()

    def _cycle_context(self):
        reset_dt = self._next_reset_datetime()
        now = datetime.now()
        delta = (now - (reset_dt - timedelta(days=7))).total_seconds()
        day_num = (1 if (delta < 0 or delta >= 7 * 86400)
                   else min(7, int(delta // 86400) + 1))
        return reset_dt, now, day_num

    def _plan_matches(self, tool, plan_name, day_num, value):
        targets = PLAN_TARGETS.get(plan_name, PLAN_TARGETS["Linear"])
        rest_start  = 100 - sum(targets[i] for i in range(1, day_num))
        target_use  = targets[day_num]
        target_rest = rest_start - target_use
        if tool == 'claude':
            day_start = 100 - rest_start
            target_val = 100 - target_rest
            return day_start <= value <= target_val
        day_start = rest_start
        target_val = target_rest
        return day_start >= value >= target_val

    def _update_plan_borders(self, valid_plan_names=None):
        valid_plan_names = set(valid_plan_names or [])
        for name, wrap in self.plan_frames.items():
            wrap.config(bg='#2f7d45' if name in valid_plan_names else SEP_CLR)

    def _save_current(self):
        self.settings["tools"][self.tool] = {
            "plan": self.selected_plan, "reset_weekday": self.reset_weekday,
            "hour": self.hour, "minute": self.minute, "value": self.value,
        }

    def _restore_tool(self, t):
        s = self.settings["tools"].get(t, {})
        plan = s.get("plan", "Linear")
        if plan not in PLAN_TARGETS:
            plan = "Linear"
        self.selected_plan = plan
        self.reset_weekday = int(s.get("reset_weekday", (datetime.now().weekday() + 1) % 7)) % 7
        self.hour     = int(s.get("hour",   23))
        self.minute   = int(s.get("minute", 59))
        self.value    = int(s.get("value",  50))
        self.slider.config(resolution=1)
        self.hour_str.set(f"{self.hour:02d}")
        self.min_str.set(f"{self.minute:02d}")
        self.slider_var.set(self.value)
        self.val_lbl.config(text=str(self.value))
        self._hi(self.tool_btns, t)
        self._hi(self.plan_btns, plan)
        self._refresh_calendar()
        self._draw_preview()

    def _commit(self):
        self._save_current()
        save_settings(self.settings)
        self.calculate()

    def _schedule_update(self):
        self._upd_job = self.root.after(60_000, self._auto_update)

    def _auto_update(self):
        self.calculate()
        self._schedule_update()

    # ── Calculation ──────────────────────────────────────────────────────────

    def _calc(self, tool, plan_name, value):
        targets = PLAN_TARGETS.get(plan_name, PLAN_TARGETS["Linear"])
        reset_dt, now, day_num = self._cycle_context()
        d = reset_dt.date()

        rest_start  = 100 - sum(targets[i] for i in range(1, day_num))
        target_use  = targets[day_num]
        target_rest = rest_start - target_use
        hours_left  = (reset_dt - now).total_seconds() / 3600

        if tool == 'claude':
            mode        = 'Used'
            day_start   = 100 - rest_start
            target_val  = 100 - target_rest
            is_over     = value > target_val
            to_goal     = target_val - value
        else:
            mode        = 'Remaining'
            day_start   = rest_start
            target_val  = target_rest
            is_over     = value < target_val
            to_goal     = value - target_val
        if is_over:
            status = f"Over budget by {abs(to_goal)} percentage points"
            status_fg = WARN
        elif to_goal == 0:
            status = "Exactly on target"
            status_fg = OK_CLR
        else:
            status = f"{abs(to_goal)} percentage points short of target"
            status_fg = OK_CLR

        return {
            "tool": tool.upper(),
            "plan": plan_name,
            "mode": mode,
            "reset": f'{d.strftime("%d.%m.%Y")}  {self.hour:02d}:{self.minute:02d}  ({WEEKDAYS_EN[d.weekday()]})',
            "cycle_day": f"{day_num} / 7",
            "time_left": self._fmt(hours_left),
            "day_start": f"{day_start:>3} %",
            "current": f"{value:>3} %",
            "daily_target": f"{target_use:>3} %",
            "goal": f"{target_val:>3} %",
            "status": status,
            "status_fg": status_fg,
            "day_num": day_num,
        }

    def calculate(self):
        self._refresh_calendar()
        data = self._calc(self.tool, self.selected_plan, self.value)
        valid = [name for name in PLAN_NAMES
                 if self._plan_matches(self.tool, name, data["day_num"], self.value)]
        self._update_plan_borders(valid)
        for key in ("tool", "plan", "mode", "reset", "cycle_day",
                    "time_left", "day_start", "current", "daily_target",
                    "goal", "status"):
            self.result_fields[key].config(text=data[key])
        self.result_fields["status"].config(fg=data["status_fg"])
        self._draw_preview()

    def _fmt(self, hours):
        if hours <= 0:
            return 'expired'
        def plural(value, singular, plural_form):
            return singular if value == 1 else plural_form
        total_m = int(hours * 60)
        if total_m >= 24 * 60:
            days = total_m // (24 * 60)
            rem  = total_m % (24 * 60)
            hours_left = rem // 60
            s = f"{days} {plural(days, 'day', 'days')}"
            return f"{s} {hours_left} {plural(hours_left, 'hour', 'hours')}" if hours_left else s
        if total_m >= 60:
            h, m = divmod(total_m, 60)
            if m:
                return f"{h} {plural(h, 'hour', 'hours')} {m} {plural(m, 'minute', 'minutes')}"
            return f"{h} {plural(h, 'hour', 'hours')}"
        return f"{total_m} {plural(total_m, 'minute', 'minutes')}"


def main():
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == '__main__':
    main()
