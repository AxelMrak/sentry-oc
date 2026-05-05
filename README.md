# sentry-oc

OpenCode session monitor — real-time TUI dashboard for tracking active OpenCode agent sessions.

## Features

- Live session list filtered to last 5 minutes
- Animated status indicators (green/blue/yellow by recency)
- Session details, chat preview, and logs
- Open sessions directly from the monitor
- Responsive layout adapts to terminal size

## Requirements

- Python 3.12+
- [Textual](https://textual.textualize.io/)
- [OpenCode](https://opencode.ai/) CLI installed

## Install

```bash
uv venv .venv
source .venv/bin/activate
uv pip install textual
```

## Usage

```bash
python monitor.py
```

## Keybinds

| Key     | Action    |
| ------- | --------- |
| `d`     | Details   |
| `c`     | Chat      |
| `l`     | Logs      |
| `o`     | Open      |
| `r`     | Refresh   |
| `esc`   | Back      |
| `q`     | Quit      |

## License

MIT
