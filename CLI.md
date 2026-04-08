# CLI Reference

The CLI is available via the `owm` command after installation.

## Commands

### `owm gui` — Desktop GUI

Launches the PySide6 desktop application.

```bash
owm gui
```

See the [README](README.md) for the full GUI workflow.

---

### `owm gen` — Generate a session

Generates a batch of wallpapers into a session folder for later review.

```bash
owm gen [OPTIONS]
```

**Generation options:**

| Flag | Default | Description |
|------|---------|-------------|
| `--count`, `-n` | `50` | Number of wallpapers to generate |
| `--resolution`, `-r` | `2560x1440` | Resolution as `WIDTHxHEIGHT` |
| `--min-circles` | `4` | Minimum circle count per image |
| `--max-circles` | `20` | Maximum circle count per image |
| `--min-radius` | `60` | Minimum circle radius in pixels |
| `--max-radius` | `400` | Maximum circle radius in pixels |
| `--curve` | `gaussian` | Falloff curve: `linear`, `ease`, `exp`, `gaussian`, `flat` |
| `--curve-param` | `2.0` | Curve sharpness/intensity (> 0) |
| `--glow-strength` | `0.3` | Glow edge intensity (0 = off) |
| `--glow-mu` | `0.88` | Glow ring center (fraction of radius) |
| `--glow-sigma` | `0.07` | Glow ring width |
| `--background` | `#000000` | Background color (hex or `rgb(r,g,b)`) |
| `--primary` | `random` | Primary circle color or `random` |
| `--secondary` | `random` | Secondary circle color or `random` |
| `--glow-color` | `#FFF3C8` | Glow edge color |
| `--seed` | _(none)_ | Random seed for reproducibility |
| `--workers`, `-w` | `1` | Parallel workers (0 = auto/all cores) |
| `--preset` | _(none)_ | Load a named preset as base config |
| `--save-dir` | `./wallpapers/kept` | Final output folder |
| `--temp-dir` | `./wallpapers/_batch` | Session staging folder |

**Examples:**

```bash
# Default settings, 80 wallpapers at 1440p
owm gen --count 80

# Reproducible batch
owm gen --count 100 --seed 42

# Dense, sharp circles
owm gen --count 50 --min-circles 15 --max-circles 30 --curve ease --curve-param 3.0

# Large, soft, sparse circles on black
owm gen --count 30 --min-circles 3 --max-circles 6 --min-radius 150 --max-radius 600 --curve gaussian --curve-param 1.5

# Using a preset
owm gen --preset ultrawide --count 120 --resolution 3440x1440

# Custom colors
owm gen --count 30 --primary "#FF3366" --secondary "#33CCFF" --glow-color "#FFFFFF"
```

---

### `owm run` — Generate + review immediately

Combines `gen` and `review` in one command. After generation finishes, immediately opens the review UI.

```bash
owm run [OPTIONS]
```

Accepts the same options as `owm gen`.

---

### `owm review` — Review a session

Opens the review UI for a previously generated session.

```bash
owm review SESSION_PATH [OPTIONS]
```

| Flag | Description |
|------|-------------|
| `SESSION_PATH` | Path to the session directory |
| `--start`, `-s` | Start index (default: 0) |

**Review controls:**

| Key | Action |
|-----|--------|
| `→` or `Space` | Next image |
| `←` or `Backspace` | Previous image |
| `K` or `A` | **Keep** — mark for export |
| `D` or `X` | **Discard** |
| `U` | Unmark (reset to undecided) |
| `G` | Jump to first undecided image |
| `Home` / `End` | First / last image |
| `Enter` | **Finalize** — export kept images |
| `Esc` or `Q` | Quit |

Click on a thumbnail at the bottom to jump directly to that image.

---

### `owm presets` — Manage presets

```bash
# List all available presets
owm presets list

# Show a preset's full configuration
owm presets show ultrawide

# Delete a preset
owm presets delete my-preset
```

---

## Alpha Curves

The `--curve` flag controls how the circle fades from center to edge:

| Curve | Formula | Feel |
|-------|---------|------|
| `linear` | `a = 1 - t` | Soft linear falloff |
| `ease` | `a = (1 - t)^k` | Power curve — higher `k` = sharper |
| `exp` | `a = exp(-k·t)` | Exponential decay |
| `gaussian` | `a = exp(-t²·k)` | Smooth bell-shaped falloff (default) |
| `flat` | `a = 1` | No fade, solid circle |

---

## Reproducibility

Pass `--seed` to get the same batch on repeated runs:

```bash
owm gen --count 50 --seed 12345
# ... generate again with same seed ...
owm gen --count 50 --seed 12345  # identical output
```

The seed is stored in the session metadata alongside per-image seeds.

---

## Session Structure

```
wallpapers/
├── _batch/
│   └── session_20260405_153012/
│       ├── generated/
│       │   ├── img_0001.png
│       │   └── img_0002.png
│       ├── metadata.json        # full config snapshot
│       └── review_state.json   # keep/discard state
└── kept/                       # final exports
    ├── oled_20260405_0001.png
    └── oled_20260405_0007.png
```
