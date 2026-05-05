# sentry

> Terminal UI for monitoring OpenCode agent sessions. Built in Rust.

<p align="center">
  <img src="https://img.shields.io/badge/built_with-Rust-dea584?style=flat&logo=rust" alt="Built with Rust">
  <img src="https://img.shields.io/badge/license-MIT-blue?style=flat" alt="License">
  <img src="https://img.shields.io/badge/platform-macOS-lightgrey?style=flat&logo=apple" alt="Platform">
</p>

**sentry** is a lightweight, real-time terminal dashboard that monitors your [OpenCode](https://opencode.ai/) agent sessions. See what agents are doing, browse chat history, and jump into sessions — all from a single terminal window.

---

## Features

- **Live session list** — sessions from the last 24 hours, auto-refreshed every 5 seconds
- **Activity detection** — see which files agents are reading/writing in real time
- **Animated spinners** — braille spinner on active sessions, colored status dots
- **Chat history** — browse full conversation with role-colored messages
- **Session details** — ID, project, duration, age at a glance
- **One-key open** — launch any session in OpenCode directly from the monitor
- **Zero dependencies at runtime** — single 1.2MB binary, no Python, no Node

## Install

### Homebrew (recommended)

```bash
brew tap AxelMrak/tap
brew install sentry
```

### Cargo

```bash
cargo install --git https://github.com/AxelMrak/sentry-oc.git
```

### From source

```bash
git clone https://github.com/AxelMrak/sentry-oc.git
cd sentry-oc
cargo build --release
./target/release/sentry
```

## Requirements

- **macOS** (Linux support coming soon)
- [OpenCode](https://opencode.ai/) CLI installed and in your `$PATH`
- `find` command available (ships with macOS)

## Usage

```bash
sentry
```

That's it. The TUI launches immediately and starts monitoring.

## Keybinds

| Key       | Action                              |
| --------- | ----------------------------------- |
| `↑` `↓`   | Navigate sessions                   |
| `Enter`   | Open details for selected session   |
| `d`       | Details view                        |
| `c`       | Chat history                        |
| `l`       | Logs                                |
| `o`       | Open session in OpenCode            |
| `r`       | Manual refresh                      |
| `esc`     | Back to list                        |
| `q`       | Back (in detail) / Quit (in list)   |

## Layout

```
┌─────────────────────────────────────────────────┐
│ ● Active: 3  OpenCode Monitor     01:45:32      │  ← Status bar
├─────────────────────────────────────────────────┤
│ ▸ Active Sessions (24h)                         │
│ ┌─────────────────────────────────────────────┐ │
│ │ Status  Session ID   Title    Activity  ... │ │
│ │ ⠋ ●     ses_20a20... ESLint.. Editing..     │ │  ← Animated spinner
│ │ ●       ses_19b10... Deploy  Idle            │ │  ← Static dot
│ │ ●       ses_18c30... Review  Editing..       │ │
│ └─────────────────────────────────────────────┘ │
├─────────────────────────────────────────────────┤
│ Created by Axel Mrak — github.com/axelmrak      │  ← Credit
└─────────────────────────────────────────────────┘
```

### Detail View (split panel)

```
┌──────────────────┬──────────────────────────────┐
│ SESSION INFO     │ OVERVIEW                     │
│                  │                              │
│ ● ACTIVE         │ Session — Fixing ESLint...   │
│                  │                              │
│ ID: ses_20a20... │ Working directory: ~/project │
│ Project: cpa     │ Session age: 2.3h ago        │
│ Created: 01:23   │                              │
│ Duration: 15m    │                              │
└──────────────────┴──────────────────────────────┘
```

## Status Colors

| Color  | Meaning                  |
| ------ | ------------------------ |
| 🟢 Green  | Active (updated < 1 min)  |
| 🔵 Blue   | Recent (updated < 3 min)  |
| 🟡 Yellow | Idle (updated > 3 min)    |

## Activity Detection

sentry scans the session's working directory for files modified in the last 60 seconds. When detected, it shows the filename in the Activity column. Cached per-refresh cycle to minimize `find` calls.

## Build from source

```bash
# Clone
git clone https://github.com/AxelMrak/sentry-oc.git
cd sentry-oc

# Build release (optimized, ~1.2MB)
cargo build --release

# Run
./target/release/sentry
```

### Dependencies

| Crate       | Purpose              |
| ----------- | -------------------- |
| `ratatui`   | Terminal UI framework|
| `crossterm` | Terminal manipulation|
| `serde`     | JSON deserialization |
| `chrono`    | Time formatting      |
| `anyhow`    | Error handling       |

## Performance

| Metric        | Python (Textual) | Rust (ratatui) |
| ------------- | ---------------- | -------------- |
| Binary size   | ~50MB (venv)     | **1.2MB**      |
| Startup       | ~2s              | **<100ms**     |
| Memory        | ~80MB            | **~8MB**       |
| CPU idle      | ~2%              | **<0.5%**      |

## License

MIT — see [LICENSE](LICENSE)

## Author

[Axel Mrak](https://github.com/AxelMrak)
