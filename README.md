# Rate-Limit Planner

A desktop GUI tool for tracking API quota consumption across 7-day billing cycles.

## Features

- Supports **Codex** and **Claude** tools
- 12 built-in consumption plans (from WAGD to YOLO)
- Live calculation of daily targets and progress
- Plan preview bar chart showing 7-day distribution
- Tooltips on plan buttons showing the full day-by-day breakdown
- Per-tool persistent settings (restored on next launch)
- Auto-refresh every 60 seconds
- Export to text file — select which tool snapshots to include

## Requirements

- Python 3.8+
- `tkinter` (included with most Python distributions)

## Usage

```bash
python planner_ui.py
```

## How it works

Select your tool, consumption plan, and reset date/time. Move the slider to your
current quota value (REMAINING % for Codex, USED % for Claude). The tool calculates
which day of the 7-day cycle you're in and shows how far you are from today's target.

### Plans

Plans are hardcoded in `planner_ui.py`. Each plan distributes 100% of quota
across 7 days with different strategies:

| Plan | Strategy |
|---|---|
| WAGD | All quota on day 7 |
| Conservative 3–1 | Heavy end-of-week use |
| Linear | Equal daily (~14%) |
| Balanced | Front-loaded, gradual decline |
| Progressive 1–3 | Heavy day-1, steep decline |
| Aggressive 1–2 | Very heavy day-1 |
| YOLO | 100% on day 1 |

## Settings

Per-tool settings are saved automatically to `.settings.json` in the same directory
(excluded from version control).
