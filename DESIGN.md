# OLED Fuzzy Circle Wallpaper Generator

## Design Document

---

## 1. Overview

**Name:** `oledwall`
**Type:** Local CLI tool with optional lightweight GUI
**Summary:** Generate OLED-friendly wallpapers featuring random fuzzy circles with configurable colors, sizes, counts, gradient curves, and glow effects. Review generated images in a windowed desktop UI, mark keep/discard, and export the chosen ones.

**Stack:**
- Python 3.11+
- Pillow + NumPy — image generation
- Typer — CLI framework
- Rich — terminal output (progress bars, tables, styled text)
- PySide6 (Qt) — desktop config + preview + review UI
- Pydantic — config validation

---

## 2. Goals

- Generate `N` wallpapers in a single run with configurable parameters.
- Produce random fuzzy circles with adjustable count range, size range, gradient falloff curve, and glow edge color.
- Support configurable colors: background, primary, secondary, glow.
- Provide sensible defaults: black background, random vivid primary, random vivid secondary, warm white/yellow glow.
- Review generated results in a keyboard-driven windowed UI.
- Mark individual images as keep or discard.
- Export only kept images to a configurable output folder.
- Full reproducibility via random seed.
- Named preset system for saving and reusing parameter sets.

---

## 3. User Stories

| # | Story |
|---|-------|
| 1 | As a user, I can generate 200 wallpapers at `3440x1440` with one command. |
| 2 | As a user, I can set min/max circle size, circle count, gradient curve, and glow strength. |
| 3 | As a user, I can specify exact colors or leave primary/secondary as random. |
| 4 | As a user, I can reproduce the exact same batch using a fixed random seed. |
| 5 | As a user, I can save common parameter sets as named presets. |
| 6 | As a user, I can review generated images in a windowed review UI and mark each as keep or discard. |
| 7 | As a user, I can finalize the review, exporting only the kept images to a folder. |
| 8 | As a user, I can resume a paused review session later. |

---

## 4. Architecture

```
oledwall/
├── pyproject.toml
├── src/
│   └── oledwall/
│       ├── __init__.py
│       ├── __main__.py
│       ├── version.py
│       ├── cli.py                    # Typer app + subcommands (gen, run, review, presets, gui)
│       ├── config.py                 # Pydantic models + validation
│       ├── presets.py               # Preset store + built-in presets
│       ├── generator/
│       │   ├── __init__.py
│       │   ├── palette.py            # Color utilities, HSV↔RGB, vivid random
│       │   ├── fuzzy_circle.py       # Alpha curve functions
│       │   ├── circle.py             # FuzzyCircle dataclass + render
│       │   └── engine.py             # GenerationEngine (single + batch, parallel)
│       ├── session/
│       │   ├── __init__.py
│       │   ├── metadata.py            # Session, ImageRecord dataclasses
│       │   └── manager.py            # SessionManager
│       ├── uiqt/                     # PySide6 desktop UI
│       │   ├── __init__.py
│       │   ├── app.py                # MainWindow — config + preview + generation flow
│       │   ├── preview.py            # 2x2 preview rendering helpers
│       │   └── review.py             # ReviewWindow — windowed keep/discard workflow
│       └── uiqt/                     # active PySide6 desktop UI
├── tests/
│   └── test_generator.py           # Unit tests (9 passing)
├── presets/                          # Built-in presets (shipped TOML)
│   ├── minimal.toml
│   ├── dense.toml
│   ├── ultrawide.toml
│   ├── vivid.toml
│   └── subtle.toml
└── README.md
```

---

## 5. Configuration Model

### 5.1 Config Precedence

1. CLI flags (highest)
2. Preset file
3. `oledwall.toml` user config
4. Built-in defaults (lowest)

### 5.2 User Config File

Location: `~/.config/oledwall/oledwall.toml` (or `./oledwall.toml` if present)

```toml
[output]
count = 50
save_dir = "./wallpapers/kept"
temp_dir = "./wallpapers/_batch"
format = "png"
purge_discarded = false

[colors]
background = "#000000"
primary = "random"
secondary = "random"
glow = "#FFF3C8"

[generation]
min_circles = 6
max_circles = 18
min_radius = 70
max_radius = 450
curve = "gaussian"
curve_param = 2.0
glow_strength = 0.3
glow_mu = 0.88
glow_sigma = 0.07
primary_opacity_min = 0.4
primary_opacity_max = 1.0
primary_secondary_mix = 0.5
enforce_both_colors = true

[random]
seed = null
workers = 1
```

### 5.3 Pydantic Models

#### `GenerationConfig`
| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `min_circles` | `int` | `4` | Minimum circle count per image |
| `max_circles` | `int` | `20` | Maximum circle count per image |
| `min_radius` | `int` | `60` | Minimum circle radius in pixels |
| `max_radius` | `int` | `400` | Maximum circle radius in pixels |
| `curve` | `Literal["linear", "ease", "exp", "gaussian"]` | `"gaussian"` | Gradient falloff curve |
| `curve_param` | `float` | `2.0` | Curve sharpness/intensity (> 0) |
| `glow_strength` | `float` | `0.3` | Glow edge intensity (0 = off) |
| `glow_mu` | `float` | `0.88` | Glow ring center (fraction of radius) |
| `glow_sigma` | `float` | `0.07` | Glow ring width |
| `primary_opacity_min` | `float` | `0.4` | Per-circle base opacity range |
| `primary_opacity_max` | `float` | `1.0` | Per-circle base opacity range |
| `primary_secondary_mix` | `float` | `0.5` | Probability of primary vs secondary color |
| `enforce_both_colors` | `bool` | `true` | Ensure at least 1 primary + 1 secondary circle |
| `workers` | `int` | `1` | Parallel generation workers (0 = auto) |

#### `ColorConfig`
| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `background` | `tuple[int,int,int] \| None` | `None` | Background RGB. `None` = black `(0,0,0)` |
| `primary` | `tuple[int,int,int] \| Literal["random"]` | `"random"` | Primary circle color |
| `secondary` | `tuple[int,int,int] \| Literal["random"]` | `"random"` | Secondary circle color |
| `glow` | `tuple[int,int,int]` | `(255,243,200)` | Glow edge color (warm white) |

#### `SessionConfig`
| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `count` | `int` | `50` | Number of wallpapers to generate |
| `save_dir` | `Path` | `"./wallpapers/kept"` | Final output folder |
| `temp_dir` | `Path` | `"./wallpapers/_batch"` | Session staging folder |
| `format` | `Literal["png"]` | `"png"` | Output image format |
| `purge_discarded` | `bool` | `false` | Delete discarded images after finalization |

#### `AppConfig`
Composes all three config models plus session metadata (resolution, seed, CLI flag tracking).

### 5.4 Validation Rules

| Rule | Constraint |
|------|------------|
| Circle count | `min_circles >= 1`, `max_circles >= min_circles` |
| Radius | `min_radius >= 1`, `max_radius >= min_radius` |
| Resolution | Parse `WxH`, max dimension `7680` |
| `curve_param` | `> 0` |
| `glow_strength` | `>= 0` |
| Colors | Parse `#RGB`, `#RRGGBB`, `#RRGGBBAA`, `rgb(r,g,b)`, or named CSS colors |
| `primary_secondary_mix` | `0.0 .. 1.0` |

---

## 6. Preset System

### 6.1 Built-in Presets

#### `minimal` — sparse, calm
```toml
[generation]
min_circles = 3
max_circles = 6
min_radius = 150
max_radius = 600
curve = "gaussian"
curve_param = 1.5
glow_strength = 0.2
```

#### `dense` — many overlapping circles
```toml
[generation]
min_circles = 15
max_circles = 30
min_radius = 40
max_radius = 200
curve = "ease"
curve_param = 3.0
glow_strength = 0.4
```

#### `ultrawide` — optimized for 3440x1440
```toml
[generation]
min_circles = 8
max_circles = 22
min_radius = 80
max_radius = 520
curve = "gaussian"
curve_param = 2.0
glow_strength = 0.35
```

### 6.2 Preset Storage

- **User presets:** `~/.config/oledwall/presets/`
- **Built-in presets:** shipped in `presets/` directory, loaded as fallback
- **Commands:**
  - `oledwall presets list` — list all presets
  - `oledwall presets show <name>` — dump preset TOML
  - `oledwall presets save <name>` — save current config as preset
  - `oledwall presets delete <name>` — remove user preset

---

## 7. Generation Algorithm

### 7.1 Overview

For each image:
1. Resolve background to RGB `(0, 0, 0)`.
2. Resolve primary/secondary colors (random if configured).
3. Ensure hue separation of at least 35° between primary and secondary.
4. Sample circle count `n` from `randint(min_circles, max_circles)`.
5. If `enforce_both_colors` and `n >= 2`, reserve at least 1 primary and 1 secondary.
6. For each circle, sample center `(cx, cy)`, radius `r`, and per-circle opacity.
7. Render each fuzzy circle onto a NumPy canvas using alpha compositing.
8. Clip values to `[0, 255]` and save as PNG.

### 7.2 Fuzzy Circle Alpha Functions

All functions take normalized distance `t = clamp(d / r, 0, 1)` where `d` is pixel distance from center.

| Name | Formula | Notes |
|------|---------|-------|
| `linear` | `a = 1 - t` | Soft linear falloff |
| `ease` | `a = (1 - t)^k` | Power curve, `k > 1` = sharper |
| `exp` | `a = exp(-k * t)` | Exponential decay |
| `gaussian` | `a = exp(-(t²) * k)` | Smooth bell-shaped falloff |

Outside `t > 1`: `a = 0`

### 7.3 Glow Ring Profile

Gaussian ring centered near the circle edge:
```
a_glow = exp(-((t - mu)²) / (2 * sigma²))
```
- `mu = 0.88` — ring positioned at 88% of radius
- `sigma = 0.07` — ring width
- Glow is blended additively over the base circle

### 7.4 Alpha Compositing

```
canvas_new = fill_color * fill_alpha + canvas_old * (1 - fill_alpha)
canvas_final = canvas_new + glow_color * glow_alpha  (additive blend)
```

### 7.5 Random Color Generation

When `primary` or `secondary` is `"random"`:
- Hue: uniform random `U(0, 360)`
- Saturation: `U(0.65, 1.0)` — vivid colors
- Value: `U(0.65, 1.0)` — bright colors
- Convert HSV → RGB

### 7.6 Reproducibility

- Global RNG seeded at session start via `--seed`.
- Per-image seed: `session_seed + image_index`.
- All random choices (positions, sizes, colors, opacities) derive from per-image seed.
- Session metadata stores full config snapshot and per-image seeds for exact reproduction.

---

## 8. Session & Metadata

### 8.1 Directory Structure

```
wallpapers/
  _batch/
    session_20260405_153012/
      generated/
        img_0001.png
        img_0002.png
        ...
      metadata.json
      review_state.json
  kept/
    oled_20260405_0001.png
    oled_20260405_0007.png
    ...
```

### 8.2 `metadata.json`

```json
{
  "session_id": "session_20260405_153012",
  "created_at": "2026-04-05T15:30:12",
  "config": {
    "resolution": [3440, 1440],
    "count": 50,
    "generation": { ... },
    "colors": { ... }
  },
  "images": [
    {
      "filename": "img_0001.png",
      "index": 1,
      "seed": 12345,
      "palette": {
        "primary": [45, 120, 255],
        "secondary": [255, 80, 90],
        "glow": [255, 243, 200]
      },
      "circle_count": 14,
      "generation_time_ms": 320
    }
  ]
}
```

### 8.3 `review_state.json`

```json
{
  "session_id": "session_20260405_153012",
  "current_index": 7,
  "states": {
    "img_0001.png": "keep",
    "img_0002.png": "discard",
    "img_0003.png": "unddecided"
  },
  "updated_at": "2026-04-05T15:35:00"
}
```

### 8.4 SessionManager API

```python
class SessionManager:
    def create_session(config: AppConfig, count: int) -> Session
    def save_session(session: Session)
    def load_session(session_id: str) -> Session
    def list_sessions() -> list[SessionSummary]
    def finalize(session: Session, save_dir: Path, purge: bool)
```

---

## 9. CLI Interface

### 9.1 Commands

```bash
# Generate wallpapers
oledwall gen [OPTIONS]

# Generate + launch review immediately
oledwall run [OPTIONS]

# Review a session
oledwall review SESSION_PATH [OPTIONS]

# Manage presets
oledwall presets list
oledwall presets show <name>
oledwall presets save <name>
oledwall presets delete <name>
```

### 9.2 `gen` / `run` Options

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--count`, `-n` | `int` | `50` | Number of wallpapers |
| `--resolution`, `-r` | `str` | `2560x1440` | Resolution `WxH` |
| `--min-circles` | `int` | `4` | Min circle count |
| `--max-circles` | `int` | `20` | Max circle count |
| `--min-radius` | `int` | `60` | Min circle radius (px) |
| `--max-radius` | `int` | `400` | Max circle radius (px) |
| `--curve` | `str` | `gaussian` | Falloff curve |
| `--curve-param` | `float` | `2.0` | Curve sharpness |
| `--glow-strength` | `float` | `0.3` | Glow intensity |
| `--glow-mu` | `float` | `0.88` | Glow ring position |
| `--glow-sigma` | `float` | `0.07` | Glow ring width |
| `--background` | `str` | `#000000` | Background color |
| `--primary` | `str` | `random` | Primary color or `random` |
| `--secondary` | `str` | `random` | Secondary color or `random` |
| `--glow-color` | `str` | `#FFF3C8` | Glow edge color |
| `--seed` | `int` | `null` | Random seed (reproducibility) |
| `--workers`, `-w` | `int` | `1` | Parallel workers |
| `--preset` | `str` | `null` | Load preset as base config |
| `--save-dir` | `Path` | `./wallpapers/kept` | Final output folder |
| `--temp-dir` | `Path` | `./wallpapers/_batch` | Session staging folder |

### 9.3 `run` Command

Shorthand for `gen` followed by `review`. Prints session path after generation.

```bash
oledwall run --count 120 --resolution 3440x1440 \
  --min-circles 8 --max-circles 22 \
  --min-radius 80 --max-radius 520 \
  --curve gaussian --curve-param 2.0 \
  --glow-strength 0.35
```

---

## 10. Review UI (Qt)

### 10.1 Window Layout

```
+--------------------------------------------------+
| [index overlay - top left, semi-transparent]    |
| 12 / 120  |  STATUS: KEEP                        |
|                                                  |
|                                                  |
|            [full image, aspect-fit]              |
|                                                  |
|                                                  |
|                                                  |
| [thumbnail strip - bottom, 40px tall]           |
+--------------------------------------------------+
| ← → navigate  |  K keep  |  D discard  |  U unmark  |  Enter finalize  |  Esc quit  |
+--------------------------------------------------+
```

### 10.2 Overlays

**Top-left status box:**
- Dark semi-transparent background `rgba(0,0,0,0.6)`
- `12 / 120` in white
- `STATUS: KEEP` in green / `DISCARD` in red / `---` in grey

**Bottom thumbnail strip:**
- 40px tall strip of all images
- Green/red/grey border per status
- Current image highlighted
- Click to jump; arrow keys scroll

**Key hint bar:**
- Single-line hint at very bottom
- `← → navigate | K keep | D discard | U unmark | Enter finalize | Esc quit`

### 10.3 Keyboard Controls

| Key | Action |
|-----|--------|
| `Right` / `Space` | Next image |
| `Left` / `Backspace` | Previous image |
| `K` | Mark as keep |
| `D` | Mark as discard |
| `U` | Unmark (reset to undecided) |
| `G` | Jump to first undecided |
| `Home` | Jump to first image |
| `End` | Jump to last image |
| `R` | Random jump |
| `Enter` | Finalize and export |
| `Esc` / `Q` | Quit (confirm if changes unsaved) |

### 10.4 Finalization Flow

1. Show confirmation dialog: `Finalize? 47 kept, 73 discarded. [Y/n]`
2. Copy kept images to `save_dir` with timestamped names: `oled_YYYYMMDD_NNNN.png`
3. If `--purge-discarded`, delete temp session directory
4. Print summary: `Exported 47 wallpapers to ./wallpapers/kept`

---

## 11. Implementation Phases

### Phase 1 — Project Scaffold
- [x] `pyproject.toml` with all dependencies
- [x] `src/oledwall/__init__.py`, `__main__.py`
- [x] CLI app skeleton with Typer subapps

### Phase 2 — Config & Validation
- [x] `config.py` — Pydantic models
- [x] Color parser (hex, rgb, named colors)
- [x] Config validation
- [x] `presets.py` — PresetStore with built-in presets

### Phase 3 — Generation Engine
- [x] `palette.py` — color utilities, HSV→RGB, vivid random
- [x] `fuzzy_circle.py` — alpha curve functions (linear, ease, exp, gaussian)
- [x] `circle.py` — FuzzyCircle dataclass + render method
- [x] `engine.py` — GenerationEngine (single + batch with multiprocessing)

### Phase 4 — Session Management
- [x] `session/metadata.py` — ImageRecord, SessionManifest
- [x] `session/manager.py` — SessionManager (create, save, load, list, finalize)

### Phase 5 — CLI Commands
- [x] `gen` command
- [x] `run` command
- [x] `review` command
- [x] `presets` subcommand (list, show, save, delete)

### Phase 6 — Review UI
- [x] `slideshow.py` — core window, image display, scaling
- [x] Status overlay, key hint bar
- [x] Thumbnail strip with click handling
- [x] Finalization + export

### Phase 7 — Polish
- [x] Ctrl+C interrupt handling, partial session save
- [x] Resume review session (`current_index` persisted on every action)
- [x] Determinism unit test (seed → identical output)
- [x] Rich terminal styling throughout
- [x] README and documentation

### Phase 8 — Qt Desktop UI
- [x] `uiqt/app.py` — `MainWindow` state flow (CONFIG → GENERATING → REVIEW)
- [x] `uiqt/preview.py` — 2x2 live preview renderer
- [x] `uiqt/review.py` — windowed review mode
- [x] Qt-native controls (spinboxes, combo boxes, scroll area, text inputs)
- [x] `oledwall gui` CLI command

---

## 12. Qt GUI (`oledwall gui`)

Launched via `oledwall gui`. Single Qt desktop application with three modes driven by a state machine.

### 12.1 Modes

```
CONFIG ──[GENERATE BATCH]──> GENERATING ──[done]──> REVIEW
   │                            │
   └──[OPEN SESSION]────> REVIEW <──[Esc, keep session]──> CONFIG
```

### 12.2 CONFIG Mode Layout

```
┌────────────────┬──────────────────────────────────────────┐
│  [CONTROLS]    │  ┌─────────┐  ┌─────────┐              │
│                │  │ Preview │  │ Preview │              │
│  Resolution     │  │  #1     │  │  #2     │              │
│  Width/Height  │  └─────────┘  └─────────┘              │
│  ─────────     │  ┌─────────┐  ┌─────────┐              │
│  Circles       │  │ Preview │  │ Preview │              │
│  Count         │  │  #3     │  │  #4     │              │
│  Min/Max Circ │  └─────────┘  └─────────┘              │
│  Min/Max Rad  │                                        │
│  ─────────     │  [GENERATE BATCH]  [OPEN SESSION]     │
│  Appearance    │                                        │
│  Curve [▼]    │                                        │
│  Curve Param   │                                        │
│  ─────────     │                                        │
│  Glow          │                                        │
│  Strength       │                                        │
│  Mu / Sigma    │                                        │
│  Opacity Min   │                                        │
│  Opacity Max   │                                        │
│  ─────────     │                                        │
│  Colors        │                                        │
│  Bg / Pri /    │                                        │
│  Sec / Glow    │                                        │
│  ─────────     │                                        │
│  Presets       │                                        │
│  [min][dense]  │                                        │
│  [ultra][vivid]│                                        │
│  ─────────     │                                        │
│  Seed: [____] │                                        │
└────────────────┴──────────────────────────────────────────┘
```

### 12.3 Control Widgets

**Sliders** — click anywhere on track to set value, drag thumb to adjust:
- Width, Height (resolution)
- Count (batch size)
- Min/Max Circles, Min/Max Radius
- Curve Param, Glow Strength, Glow Mu, Glow Sigma
- Primary Opacity Min/Max

**Dropdown** — click to open, click item to select:
- Curve type: `linear`, `ease`, `exp`, `gaussian`

**Color Swatches** — animated cycling color when `is_random`, solid color otherwise:
- Left-click: toggle random on/off
- Hover: show hex code tooltip

**Preset Buttons** — loads preset into all controls and triggers preview refresh:
- `minimal`, `dense`, `ultrawide`, `vivid`, `subtle`

**Text Input** — seed field (leave blank = random)

**Action Buttons**:
- `GENERATE BATCH` — starts generation with progress bar
- `OPEN SESSION` — tkinter file dialog to open existing session

### 12.4 Preview Grid

2×2 grid of preview cells, each ~380×200px at 1080p. Each cell:
- Renders a wallpaper with current params but different seed (base_seed + i)
- Re-renders on: any slider change (150ms debounce), preset click, color change
- Generation runs on background thread (UI stays responsive)
- Shows "generating..." overlay with pulsing animation while rendering
- Seed label `S:42` in bottom-right corner

### 12.5 GENERATING Mode

Bottom progress bar showing:
- Animated fill bar (percentage complete)
- Current filename: `img_0001.png`
- Progress: `12/50`
- ESC to cancel → returns to CONFIG mode

### 12.6 REVIEW Mode

Fullscreen slideshow (shares `ReviewMode` from `review/slideshow.py`). Same controls as CLI review:
- `K`/`D`/`U` mark keep/discard/undecided
- `←→` navigate, `G` jump to first undecided
- `Enter` finalize → copies kept images to save_dir
- `Esc` → returns to CONFIG mode

### 12.7 Window

- Resizable (min 1024×640)
- Dark theme (`#0C0C12` background)
- Left panel: fixed-width sidebar (~320px) with controls
- Right area: 2×2 preview grid + action buttons
- `VIDEORESIZE` event handled — relayouts on window resize

### 12.8 GUI → CLI Integration

- `GuiApp` uses `GenerationEngine.generate_single()` for previews
- Batch generation uses same engine + `SessionManager`
- Sessions saved via `SessionManager` — fully compatible with CLI sessions
- `oledwall review <path>` works on sessions created from GUI

---

## 12. Acceptance Criteria

- [x] `oledwall gen --count 100` generates 100 PNG wallpapers without error
- [x] Fixed `--seed` produces identical batch on repeated runs
- [x] All 4 alpha curve types produce visually distinct falloffs
- [x] Glow ring is visible near circle edges when `glow_strength > 0`
- [x] Review UI displays images scaled to window size with correct aspect ratio
- [x] Keyboard controls navigate and mark images correctly
- [x] Finalize exports only kept images to configured folder
- [x] Presets are listed, shown, saved, and deleted correctly
- [x] Config precedence: CLI flags override preset, preset overrides defaults
- [x] Unit tests pass: color parsing, curve alpha range `[0,1]`, determinism (9/9 passing)
- [x] `oledwall gui` launches config panel with live preview
- [x] Preview grid updates within ~200ms of any parameter change
- [x] 4 preview cells show visually different wallpapers (different seeds)
- [x] GENERATE BATCH shows progress, then switches to review mode
- [x] ESC from review returns to config mode
- [x] Parallel generation works with `--workers N`

---

## 13. Performance Targets

| Scenario | Target |
|----------|--------|
| Single image at 1080p | < 1 second |
| Batch 100 images at 1440p, 1 worker | < 3 minutes |
| Batch 100 images at 1440p, 4 workers | < 60 seconds |
| Review UI image load | < 100ms |
| Memory per image at 4K | < 50 MB |

---

## 14. Error Handling

| Situation | Behavior |
|-----------|----------|
| Invalid resolution format | Clear error: `Resolution must be WxH, e.g. 2560x1440` |
| Invalid color value | Clear error: `Cannot parse color "...": expected hex or rgb()` |
| `min > max` on any range | Clear error: `min_radius (400) must be <= max_radius (200)` |
| Disk full | Stop generation, save session so far, print `Disk full: session saved to ...` |
| Interrupt (Ctrl+C) during generation | Save partial session, print `Interrupted. Resume with: oledwall review <session>` |
| Missing session on review | Clear error with session list suggestion |
| Qt not installed | Fallback message: `Install PySide6 to use desktop UI: pip install pyside6` |

---

## 15. Security & Privacy

- Entirely local — no network access, no telemetry
- No secrets or credentials handled
- Safe file naming: timestamp + index, no user input in filenames
- Explicit `--overwrite` flag required to overwrite existing output files
