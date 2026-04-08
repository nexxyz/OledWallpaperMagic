from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from oled_wallpaper_magic.config import DEFAULT_SAVE_DIR, DEFAULT_TEMP_DIR

app = typer.Typer(
    rich_markup_mode="rich",
    help="[bold]oled_wallpaper_magic[/bold] — OLED fuzzy circle wallpaper generator",
)
presets_app = typer.Typer(help="Manage presets")

app.add_typer(presets_app, name="presets")

console = Console()

_GEN_OPTIONS = [
    typer.Option(50, "--count", "-n", help="Number of wallpapers to generate"),
    typer.Option("2560x1440", "--resolution", "-r", help="Resolution WxH"),
    typer.Option(4, "--min-circles", help="Minimum circle count"),
    typer.Option(20, "--max-circles", help="Maximum circle count"),
    typer.Option(60, "--min-radius", help="Minimum circle radius (px)"),
    typer.Option(400, "--max-radius", help="Maximum circle radius (px)"),
    typer.Option("gaussian", "--curve", help="Falloff curve: linear, ease, exp, gaussian, flat"),
    typer.Option(2.0, "--curve-param", help="Curve sharpness (>0)"),
    typer.Option(0.3, "--glow-strength", help="Glow intensity (>=0)"),
    typer.Option(0.88, "--glow-mu", help="Glow ring position (0-1)"),
    typer.Option(0.07, "--glow-sigma", help="Glow ring width"),
    typer.Option("#000000", "--background", help="Background color or hex"),
    typer.Option("random", "--primary", help="Primary color or 'random'"),
    typer.Option("random", "--secondary", help="Secondary color or 'random'"),
    typer.Option("#FFF3C8", "--glow-color", help="Glow edge color"),
    typer.Option(None, "--seed", help="Random seed for reproducibility"),
    typer.Option(1, "--workers", "-w", help="Parallel workers (0=auto)"),
    typer.Option(None, "--preset", help="Load preset as base config"),
    typer.Option(DEFAULT_SAVE_DIR, "--save-dir", help="Final output folder"),
    typer.Option(DEFAULT_TEMP_DIR, "--temp-dir", help="Session staging folder"),
]


def _build_config(
    count: int,
    resolution: str,
    min_circles: int,
    max_circles: int,
    min_radius: int,
    max_radius: int,
    curve: str,
    curve_param: float,
    glow_strength: float,
    glow_mu: float,
    glow_sigma: float,
    background: str,
    primary: str,
    secondary: str,
    glow_color: str,
    seed: int | None,
    workers: int,
    preset: str | None,
    save_dir: Path,
    temp_dir: Path,
):
    from oled_wallpaper_magic.config import (
        AppConfig,
        Resolution,
        parse_color,
    )

    app_config = AppConfig.from_preset(preset) if preset else AppConfig()

    width, height = map(int, resolution.split("x"))
    app_config.resolution = Resolution(width=width, height=height)
    app_config.generation.min_circles = min_circles
    app_config.generation.max_circles = max_circles
    app_config.generation.min_radius = min_radius
    app_config.generation.max_radius = max_radius
    app_config.generation.curve = curve  # type: ignore[arg-type]
    app_config.generation.curve_param_min = curve_param
    app_config.generation.curve_param_max = curve_param
    app_config.generation.glow_strength_min = glow_strength
    app_config.generation.glow_strength_max = glow_strength
    app_config.generation.glow_mu_min = glow_mu
    app_config.generation.glow_mu_max = glow_mu
    app_config.generation.glow_sigma_min = glow_sigma
    app_config.generation.glow_sigma_max = glow_sigma
    app_config.generation.workers = workers
    app_config.colors.background = parse_color(background) if isinstance(background, str) else background  # type: ignore[assignment]
    app_config.colors.primary = parse_color(primary) if isinstance(primary, str) else primary  # type: ignore[assignment]
    app_config.colors.secondary = parse_color(secondary) if isinstance(secondary, str) else secondary  # type: ignore[assignment]
    app_config.colors.glow = parse_color(glow_color) if isinstance(glow_color, str) else glow_color  # type: ignore[assignment]
    app_config.session.count = count
    app_config.session.save_dir = save_dir
    app_config.session.temp_dir = temp_dir
    app_config.seed = seed
    return app_config


@app.command()
def run(
    count: int = _GEN_OPTIONS[0],
    resolution: str = _GEN_OPTIONS[1],
    min_circles: int = _GEN_OPTIONS[2],
    max_circles: int = _GEN_OPTIONS[3],
    min_radius: int = _GEN_OPTIONS[4],
    max_radius: int = _GEN_OPTIONS[5],
    curve: str = _GEN_OPTIONS[6],
    curve_param: float = _GEN_OPTIONS[7],
    glow_strength: float = _GEN_OPTIONS[8],
    glow_mu: float = _GEN_OPTIONS[9],
    glow_sigma: float = _GEN_OPTIONS[10],
    background: str = _GEN_OPTIONS[11],
    primary: str = _GEN_OPTIONS[12],
    secondary: str = _GEN_OPTIONS[13],
    glow_color: str = _GEN_OPTIONS[14],
    seed: int | None = _GEN_OPTIONS[15],
    workers: int = _GEN_OPTIONS[16],
    preset: str | None = _GEN_OPTIONS[17],
    save_dir: Path = _GEN_OPTIONS[18],
    temp_dir: Path = _GEN_OPTIONS[19],
) -> None:
    """Generate wallpapers then launch review immediately."""
    from oled_wallpaper_magic.session.manager import SessionManager
    from oled_wallpaper_magic.uiqt.review import launch_review_window

    app_config = _build_config(
        count, resolution, min_circles, max_circles, min_radius, max_radius,
        curve, curve_param, glow_strength, glow_mu, glow_sigma,
        background, primary, secondary, glow_color, seed, workers,
        preset, save_dir, temp_dir,
    )

    manager = SessionManager(temp_dir)
    session = manager.create_session(app_config, count)
    _generate_session(session, app_config, console)

    console.print(f"\n[green]Generated {count} wallpapers in {session.root}[/green]")
    console.print(f"[dim]Reviewing session: {session.id}[/dim]\n")
    launch_review_window(session)


@app.command("gen")
def gen(
    count: int = _GEN_OPTIONS[0],
    resolution: str = _GEN_OPTIONS[1],
    min_circles: int = _GEN_OPTIONS[2],
    max_circles: int = _GEN_OPTIONS[3],
    min_radius: int = _GEN_OPTIONS[4],
    max_radius: int = _GEN_OPTIONS[5],
    curve: str = _GEN_OPTIONS[6],
    curve_param: float = _GEN_OPTIONS[7],
    glow_strength: float = _GEN_OPTIONS[8],
    glow_mu: float = _GEN_OPTIONS[9],
    glow_sigma: float = _GEN_OPTIONS[10],
    background: str = _GEN_OPTIONS[11],
    primary: str = _GEN_OPTIONS[12],
    secondary: str = _GEN_OPTIONS[13],
    glow_color: str = _GEN_OPTIONS[14],
    seed: int | None = _GEN_OPTIONS[15],
    workers: int = _GEN_OPTIONS[16],
    preset: str | None = _GEN_OPTIONS[17],
    save_dir: Path = _GEN_OPTIONS[18],
    temp_dir: Path = _GEN_OPTIONS[19],
) -> None:
    """Generate wallpapers and save them as a session."""
    from oled_wallpaper_magic.session.manager import SessionManager

    app_config = _build_config(
        count, resolution, min_circles, max_circles, min_radius, max_radius,
        curve, curve_param, glow_strength, glow_mu, glow_sigma,
        background, primary, secondary, glow_color, seed, workers,
        preset, save_dir, temp_dir,
    )

    manager = SessionManager(temp_dir)
    session = manager.create_session(app_config, count)
    _generate_session(session, app_config, console)

    console.print(f"\n[green]Generated {count} wallpapers in {session.root}[/green]")
    console.print(f"[dim]Review with: [bold]oled_wallpaper_magic review {session.root}[/bold][/dim]")


@app.command("review")
def review_cmd(
    session_path: Path = typer.Argument(..., help="Session directory path"),
    start_index: int = typer.Option(0, "--start", "-s", help="Start index"),
) -> None:
    """Review a session's wallpapers in a windowed desktop UI."""
    from oled_wallpaper_magic.session.manager import SessionManager
    from oled_wallpaper_magic.uiqt.review import launch_review_window

    manager = SessionManager(session_path.parent)
    session = manager.load_session(session_path.name)
    launch_review_window(session, start_index=start_index)


@presets_app.command("list")
def presets_list() -> None:
    """List all available presets."""
    from rich.table import Table

    from oled_wallpaper_magic.presets import preset_store

    presets = preset_store.list_presets()
    table = Table(title="Available Presets")
    table.add_column("Name", style="cyan")
    table.add_column("Description", style="dim")
    table.add_column("Source", style="green")

    for p in presets:
        table.add_row(p["name"], p.get("description", ""), p.get("source", ""))

    console.print(table)


@presets_app.command("show")
def presets_show(name: str = typer.Argument(..., help="Preset name")) -> None:
    """Show a preset's full configuration."""
    from oled_wallpaper_magic.presets import preset_store

    preset = preset_store.get(name)
    if preset is None:
        console.print(f"[red]Preset '{name}' not found[/red]")
        raise typer.Exit(1)

    console.print(f"[bold]{name}[/bold]")
    console.print(preset.to_toml())


@presets_app.command("delete")
def presets_delete(name: str = typer.Argument(..., help="Preset name")) -> None:
    """Delete a user preset."""
    from oled_wallpaper_magic.presets import preset_store

    ok = preset_store.delete(name)
    if ok:
        console.print(f"[green]Deleted preset '{name}'[/green]")
    else:
        console.print(f"[red]Preset '{name}' not found or is built-in[/red]")
        raise typer.Exit(1)


def _generate_session(session, app_config, console: Console) -> None:
    from rich.progress import (
        BarColumn,
        Progress,
        TaskProgressColumn,
        TextColumn,
        TimeRemainingColumn,
    )

    from oled_wallpaper_magic.generator.engine import GenerationEngine
    from oled_wallpaper_magic.session.manager import SessionManager

    engine = GenerationEngine(app_config)
    generated = session.root / "generated"
    generated.mkdir(parents=True, exist_ok=True)

    manager = SessionManager(app_config.session.temp_dir)

    with Progress(
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TimeRemainingColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("[cyan]Generating wallpapers...", total=len(session.images))

        try:
            batch_seed = app_config.seed if app_config.seed is not None else 0
            for i, image_data in enumerate(
                engine.generate_batch(len(session.images), batch_seed)
            ):
                img_path = generated / f"img_{i+1:04d}.png"
                image_data.save(img_path)
                session.images[i].filename = img_path.name
                session.images[i].seed = image_data.seed
                session.images[i].circle_count = image_data.circle_count
                session.images[i].generation_time_ms = image_data.generation_time_ms
                progress.advance(task)
        except KeyboardInterrupt:
            progress.stop()
            session.review_state = {img.filename: "unddecided" for img in session.images if img.filename}
            session.current_index = 0
            manager.save_session(session)
            generated_count = sum(1 for img in session.images if img.filename)
            total = len(session.images)
            console.print(
                f"\n[yellow]Interrupted. {generated_count}/{total} images saved.[/yellow]"
            )
            console.print(f"[dim]Resume with: [bold]oled_wallpaper_magic review {session.root}[/bold][/dim]")
            raise

    session.review_state = {img.filename: "unddecided" for img in session.images if img.filename}
    session.current_index = 0
    manager.save_session(session)


@app.command("gui")
def gui() -> None:
    """Launch the interactive GUI (config panel + preview + review)."""
    from oled_wallpaper_magic.uiqt.app import launch_qt_gui

    launch_qt_gui()


@app.command("cli")
def cli_mode() -> None:
    """Run in CLI mode (for scripting/batch processing)."""
    pass


def main() -> None:
    import sys

    if len(sys.argv) == 1 or len(sys.argv) == 2 and sys.argv[1] == "gui":
        gui()
    else:
        app()


if __name__ == "__main__":
    main()
