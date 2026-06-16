#!/usr/bin/env python3
"""Rate-Limit Planner — tracks API quota across 7-day billing cycles."""
import tkinter as tk
from tkinter import filedialog
from datetime import datetime, timedelta
import json
from pathlib import Path

# ─── Data ────────────────────────────────────────────────────────────────────

TOOLS = ['codex', 'claude', 'agy']

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
PLAN_SHORT   = {
    "WAGD": "WAGD",          "Conservative 3": "Kons-3",
    "Conservative 2": "Kons-2", "Conservative 1": "Kons-1",
    "Linear": "Linear",      "Balanced": "Balanced",
    "Progressive 1": "Prog-1", "Progressive 2": "Prog-2",
    "Progressive 3": "Prog-3", "Aggressive 1": "Aggr-1",
    "Aggressive 2": "Aggr-2",  "YOLO": "YOLO",
}
WEEKDAYS_DE   = ['Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa', 'So']
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
        "tools": {t: {"plan": "Linear", "date_offset": 1,
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
        self.root.minsize(940, 640)

        self.settings = load_settings()
        self.tool = self.settings["last_tool"]

        today = datetime.now().date()
        self.dates = [today + timedelta(days=i) for i in range(8)]

        self.selected_plan = "Linear"
        self.date_idx      = 1
        self.hour          = 23
        self.minute        = 59
        self.value         = 50

        self.hour_str   = tk.StringVar()
        self.min_str    = tk.StringVar()
        self.slider_var = tk.IntVar()
        self.lbl_metric = tk.StringVar(value='REST')

        self.exp_codex  = tk.BooleanVar(value=True)
        self.exp_claude = tk.BooleanVar(value=True)
        self.exp_agy    = tk.BooleanVar(value=True)

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
        for i, name in enumerate(PLAN_NAMES):
            row = r1 if i < 6 else r2
            b = tk.Button(row, text=PLAN_SHORT[name], width=9, relief='flat',
                          bg=BTN_BG, fg=FG, cursor='hand2', font=('Sans', 9),
                          activebackground=SEL_BG, activeforeground=SEL_FG,
                          command=lambda n=name: self._sel_plan(n))
            b.pack(side='left', padx=2, pady=2)
            self.plan_btns[name] = b
            t = PLAN_TARGETS[name]
            tip = (f"{name}\n  " +
                   "  ".join(f"T{d}:{t[d]:>4}%" for d in range(1, 8)))
            Tooltip(b, tip, delay=600)

        # Plan preview canvas
        self.plan_canvas = tk.Canvas(self.root, height=62, bg=BG,
                                     highlightthickness=0)
        self.plan_canvas.pack(fill='x', padx=20, pady=(0, 2))
        self.plan_canvas.bind('<Configure>', lambda _: self._draw_preview())

        tk.Frame(self.root, bg=SEP_CLR, height=1).pack(fill='x', padx=8)

        # Row 4 – Date
        df = tk.Frame(self.root, bg=BG)
        df.pack(fill='x', **PAD)
        tk.Label(df, text="Reset:", bg=BG, fg=DIM, width=6, anchor='w',
                 font=('Sans', 9)).pack(side='left')
        self.date_btns = {}
        for i, d in enumerate(self.dates):
            lbl = f"{WEEKDAYS_DE[d.weekday()]}\n{d.strftime('%d.%m')}"
            b = tk.Button(df, text=lbl, width=7, relief='flat',
                          bg=BTN_BG, fg=FG, cursor='hand2', font=('Sans', 8),
                          justify='center',
                          activebackground=SEL_BG, activeforeground=SEL_FG,
                          command=lambda idx=i: self._sel_date(idx))
            b.pack(side='left', padx=2)
            self.date_btns[i] = b

        tk.Frame(self.root, bg=SEP_CLR, height=1).pack(fill='x', padx=8)

        # Row 5 – Time ±
        tf = tk.Frame(self.root, bg=BG)
        tf.pack(fill='x', **PAD)
        tk.Label(tf, text="Zeit:", bg=BG, fg=DIM, width=6, anchor='w',
                 font=('Sans', 9)).pack(side='left')

        def spin(parent, txt, cmd):
            return tk.Button(parent, text=txt, width=2, relief='flat',
                             bg=BTN_BG, fg=FG, cursor='hand2',
                             font=('Mono', 12, 'bold'),
                             activebackground=SEL_BG, command=cmd)

        spin(tf, '−', self._dec_h).pack(side='left', padx=2)
        tk.Label(tf, textvariable=self.hour_str, bg=BTN_BG, fg='white',
                 width=3, font=('Mono', 15, 'bold'), anchor='center').pack(side='left')
        spin(tf, '+', self._inc_h).pack(side='left', padx=2)
        tk.Label(tf, text=' : ', bg=BG, fg=FG, font=('Mono', 15)).pack(side='left')
        spin(tf, '−', self._dec_m).pack(side='left', padx=2)
        tk.Label(tf, textvariable=self.min_str, bg=BTN_BG, fg='white',
                 width=3, font=('Mono', 15, 'bold'), anchor='center').pack(side='left')
        spin(tf, '+', self._inc_m).pack(side='left', padx=2)

        tk.Frame(self.root, bg=SEP_CLR, height=1).pack(fill='x', padx=8)

        # Row 6 – Slider
        sf = tk.Frame(self.root, bg=BG)
        sf.pack(fill='x', **PAD)
        tk.Label(sf, textvariable=self.lbl_metric, bg=BG, fg='#aaa',
                 width=6, anchor='w', font=('Sans', 10, 'bold')).pack(side='left')
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
        self.result = tk.Text(rf, bg=RES_BG, fg=FG, font=('Courier', 11),
                              state='disabled', relief='flat', height=11,
                              selectbackground=SEL_BG, cursor='arrow')
        self.result.pack(fill='both', expand=True)
        self.result.tag_configure('dim',  foreground='#555')
        self.result.tag_configure('bold', foreground='white', font=('Courier', 11, 'bold'))
        self.result.tag_configure('val',  foreground=VAL_FG,  font=('Courier', 11, 'bold'))
        self.result.tag_configure('warn', foreground=WARN)
        self.result.tag_configure('ok',   foreground=OK_CLR)

        tk.Frame(self.root, bg=SEP_CLR, height=1).pack(fill='x', padx=8)

        # Bottom row
        bf = tk.Frame(self.root, bg=BG)
        bf.pack(fill='x', padx=8, pady=6)
        left = tk.Frame(bf, bg=BG)
        left.pack(side='left')
        tk.Button(left, text='Exportieren', command=self._export,
                  bg='#1a4020', fg='#90d490', relief='flat', cursor='hand2',
                  font=('Sans', 10), width=14, pady=5,
                  activebackground='#2a6030').pack(side='left', padx=(0, 8))
        for var, lbl in [(self.exp_codex, 'codex'),
                         (self.exp_claude, 'claude'),
                         (self.exp_agy, 'agy')]:
            tk.Checkbutton(left, text=lbl, variable=var, bg=BG, fg=FG,
                           selectcolor=BTN_BG, activebackground=BG,
                           activeforeground=FG, font=('Sans', 9),
                           cursor='hand2').pack(side='left', padx=4)
        tk.Button(bf, text='Beenden', command=self.root.destroy,
                  bg='#401a1a', fg='#d49090', relief='flat', cursor='hand2',
                  font=('Sans', 10), width=14, pady=5,
                  activebackground='#602020').pack(side='right', padx=4)

    # ── Plan preview ─────────────────────────────────────────────────────────

    def _current_day_num(self):
        d = self.dates[self.date_idx]
        reset_dt = datetime(d.year, d.month, d.day, self.hour, self.minute)
        delta = (datetime.now() - (reset_dt - timedelta(days=7))).total_seconds()
        if delta < 0 or delta >= 7 * 86400:
            return 1
        return min(7, int(delta // 86400) + 1)

    def _draw_preview(self):
        c = self.plan_canvas
        c.delete('all')
        w, h = c.winfo_width(), c.winfo_height()
        if w < 10 or h < 10:
            return
        targets = PLAN_TARGETS.get(self.selected_plan, PLAN_TARGETS["Linear"])
        today   = self._current_day_num()
        max_val = max(targets[i] for i in range(1, 8)) or 1
        LABEL_H = 14
        bar_zone = h - LABEL_H
        col_w    = w / 7
        for i in range(1, 8):
            x0, x1 = (i - 1) * col_w, i * col_w
            cx  = (x0 + x1) / 2
            val = targets[i]
            bh  = (val / max_val) * bar_zone
            color = '#5ab0f0' if i == today else ('#1e3d54' if i < today else '#2a5580')
            if bh > 1:
                c.create_rectangle(x0 + 3, bar_zone - bh, x1 - 3, bar_zone,
                                   fill=color, outline='')
            c.create_text(cx, h - 3, text=f"{val}%" if val else "0",
                          fill='#777', font=('Sans', 7), anchor='s')
        c.create_text(w - 4, 4, text=self.selected_plan,
                      fill='#555', font=('Sans', 8, 'italic'), anchor='ne')

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
        self.date_idx = idx
        self._hi(self.date_btns, idx)
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

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _hi(self, btn_dict, active):
        for k, b in btn_dict.items():
            b.config(bg=SEL_BG if k == active else BTN_BG,
                     fg=SEL_FG if k == active else FG)

    def _save_current(self):
        self.settings["tools"][self.tool] = {
            "plan": self.selected_plan, "date_offset": self.date_idx,
            "hour": self.hour, "minute": self.minute, "value": self.value,
        }

    def _restore_tool(self, t):
        s = self.settings["tools"].get(t, {})
        plan = s.get("plan", "Linear")
        if plan not in PLAN_TARGETS:
            plan = "Linear"
        self.selected_plan = plan
        self.date_idx = min(int(s.get("date_offset", 1)), 7)
        self.hour     = int(s.get("hour",   23))
        self.minute   = int(s.get("minute", 59))
        self.value    = int(s.get("value",  50))
        self.slider.config(resolution=20 if t == 'agy' else 1)
        self.hour_str.set(f"{self.hour:02d}")
        self.min_str.set(f"{self.minute:02d}")
        self.slider_var.set(self.value)
        self.val_lbl.config(text=str(self.value))
        self.lbl_metric.set('USED' if t == 'claude' else 'REST')
        self._hi(self.tool_btns, t)
        self._hi(self.plan_btns, plan)
        self._hi(self.date_btns, self.date_idx)
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

    def _calc(self, tool, plan_name, date_idx, hour, minute, value):
        targets = PLAN_TARGETS.get(plan_name, PLAN_TARGETS["Linear"])
        d = self.dates[date_idx]
        reset_dt = datetime(d.year, d.month, d.day, hour, minute)
        now = datetime.now()
        delta = (now - (reset_dt - timedelta(days=7))).total_seconds()
        day_num = (1 if (delta < 0 or delta >= 7 * 86400)
                   else min(7, int(delta // 86400) + 1))

        rest_start  = 100 - sum(targets[i] for i in range(1, day_num))
        target_use  = targets[day_num]
        target_rest = rest_start - target_use
        hours_left  = (reset_dt - now).total_seconds() / 3600

        if tool == 'claude':
            metric      = 'USED'
            tagesbeginn = 100 - rest_start
            target_val  = 100 - target_rest
            is_over     = value > target_val
            to_goal     = target_val - value
        else:
            metric      = 'REST'
            tagesbeginn = rest_start
            target_val  = target_rest
            is_over     = value < target_val
            to_goal     = value - target_val

        S = '═' * 52
        T = '─' * 52
        tagged = [
            ('dim',  S + '\n'),
            ('bold', f'  Tool:           {tool.upper()}\n'),
            ('',     f'  Plan:           {plan_name}\n'),
            ('',     f'  Reset:          {d.strftime("%d.%m.%Y")}  {hour:02d}:{minute:02d}'
                     f'  ({WEEKDAYS_DE[d.weekday()]})\n'),
            ('',     f'  Zyklustag:      {day_num} / 7   (noch {self._fmt(hours_left)})\n'),
            ('dim',  '  ' + T + '\n'),
            ('',     f'  Tagesbeginn {metric}:   {tagesbeginn:>3} %\n'),
            ('val',  f'  Aktuell {metric}:       {value:>3} %p\n'),
            ('',     f'  Verbrauchsziel:    {target_use:>3} %p'
                     f'   →   Ziel-{metric}: {target_val:>3} %\n'),
            ('dim',  '  ' + T + '\n'),
        ]

        if is_over:
            tagged.append(('warn', f'  ⚠  Zu viel verbraucht!   (Δ {abs(to_goal)} %p)\n'))
        elif to_goal == 0:
            tagged.append(('ok', '  ✓  Exakt auf Tagesziel!\n'))
        else:
            tagged.append(('ok', f'  →  {abs(to_goal)} %p bis Tagesziel\n'))

        tagged.append(('dim', S + '\n'))
        return tagged, ''.join(t for _, t in tagged)

    def calculate(self):
        tagged, _ = self._calc(self.tool, self.selected_plan, self.date_idx,
                                self.hour, self.minute, self.value)
        self.result.config(state='normal')
        self.result.delete('1.0', 'end')
        for tag, text in tagged:
            self.result.insert('end', text, tag)
        self.result.config(state='disabled')
        self._draw_preview()

    def _fmt(self, hours):
        if hours <= 0:
            return 'abgelaufen'
        total_m = int(hours * 60)
        if total_m >= 24 * 60:
            days = total_m // (24 * 60)
            h    = (total_m % (24 * 60)) // 60
            s    = f"{days} {'Tag' if days == 1 else 'Tage'}"
            return f"{s} {h} Stunden" if h else s
        if total_m >= 60:
            h, m = divmod(total_m, 60)
            return f"{h} Stunden {m} Minuten" if m else f"{h} Stunden"
        return f"{total_m} Minuten"

    # ── Export ───────────────────────────────────────────────────────────────

    def _export(self):
        to_export = [t for t, v in zip(TOOLS,
                     [self.exp_codex, self.exp_claude, self.exp_agy]) if v.get()]
        if not to_export:
            return
        now = datetime.now()
        blocks = [f"Rate-Limit Planner Export\nGenerated: {now.strftime('%Y-%m-%d %H:%M:%S')}\n"]
        for t in to_export:
            s    = self.settings["tools"].get(t, {})
            plan = s.get("plan", "Linear")
            if plan not in PLAN_TARGETS:
                plan = "Linear"
            di   = min(int(s.get("date_offset", 1)), 7)
            h    = int(s.get("hour",   23))
            m    = int(s.get("minute", 59))
            v    = int(s.get("value",  50))
            _, plain = self._calc(t, plan, di, h, m, v)
            blocks.append(plain)
        path = filedialog.asksaveasfilename(
            defaultextension='.txt',
            initialfile=f"rate-limit-planner_{now:%Y%m%d_%H%M}.txt",
            filetypes=[('Textdateien', '*.txt'), ('Alle Dateien', '*.*')])
        if path:
            Path(path).write_text('\n'.join(blocks))


def main():
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == '__main__':
    main()
