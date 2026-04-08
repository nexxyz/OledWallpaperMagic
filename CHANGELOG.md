# Changelog

All notable changes to OLED Wallpaper Magic will be documented in this file.

## [Unreleased]

### Added
- Dual-handle range sliders for paired min/max parameters in the main UI.
- Range Limits modal (gear button) to edit parameter bounds; saved limits apply after restart.
- Restore-default-presets icon button in preset controls.

### Changed
- Main parameter layout grouped into Circle Configuration, Glow Configuration, and Colors & Seed.
- Randomize button renamed to "Randomize All".
- Freeze Preview now collapses parameter ranges to exact preview values before locking.
- Preset handling now seeds defaults on first startup and supports restoring missing defaults.

## [1.0.0] - 2025-04-07

### Added
- Initial release
- GUI with real-time preview
- Multiple presets (minimal, dense, ultrawide, vivid, subtle, awesome_bubbles, cool_violet)
- Randomization locks for fine-grained control
- CLI for batch generation
- Session management for reviewing generated wallpapers
- UI state persistence (resolution, colors, preset selection)
- App icons for Windows

### Fixed
- Resolution persistence bug (was reverting to default after restart)
- Preview background now always black (letterbox fix)
- Scroll wheel no longer changes spinbox values

### Changed
- Default batch count changed from 50 to 10
- Removed lock buttons from width/height fields
- Improved button labels for clarity
