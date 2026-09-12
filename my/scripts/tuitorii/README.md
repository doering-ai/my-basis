# Tuitorii

> Left-rule blocks mark artificial prose; quotations retain their own attribution.

<blockquote class="artificial-prose">

Tuitorii is a terminal demonstration of a rotating 4D torus, rendered through [PyRatatui]. It projects the surface through three dimensions into a shaded character grid, making the geometry inspectable without a graphical renderer. Install the parent Python package through the [root myBasis guide](../../../README.md#installation); the interactive display additionally needs the `terminal` extra.

</blockquote>

## Run

<blockquote class="artificial-prose">

Run the file directly while developing it, or use the package entry point once the package is installed. Both forms call the same `torus.main()` command.

</blockquote>

```console
uv run --extra terminal python my/scripts/tuitorii/torus.py
uv run --extra terminal python -m my.scripts.tuitorii
```

<blockquote class="artificial-prose">

The animation begins immediately. Its rendering loop samples the torus on two angular axes, applies a 4D rotation, projects it to the terminal plane, and uses depth and surface orientation to choose a character.

</blockquote>

| Key         | Action                   |
| ----------- | ------------------------ |
| `q` / `Esc` | Quit                     |
| Space       | Pause or resume          |
| `+` / `=`   | Increase rotation speed  |
| `-` / `_`   | Decrease rotation speed  |
| `r`         | Reset rotation and speed |

## Snapshot

<blockquote class="artificial-prose">

Snapshot mode renders one deterministic frame and exits. It is the useful form for a terminal capture or a quick check in a non-interactive shell.

</blockquote>

```console
uv run --extra terminal python my/scripts/tuitorii/torus.py --snapshot
```

## Geometry

<blockquote class="artificial-prose">

The point cloud samples the 4D product of two circles with angles `u` and `v`. Each frame rotates that surface through several coordinate planes, then projects 4D to 3D and 3D to the terminal plane. Nearer projected points are drawn after farther points, providing a simple depth cue. The command-line options expose sample counts, terminal size, mesh stride, frame rate, and rotation speed for inspection or performance experiments.

</blockquote>

```text
(x, y, z, w) = (cos u, sin u, cos v, sin v)
```

## Tests

<blockquote class="artificial-prose">

The focused tests cover configuration bounds, geometry generation, pause and reset behavior, deterministic snapshots, and the drawing path when PyRatatui is available. PyRatatui is imported lazily, so only draw-path tests need the optional dependency.

</blockquote>

```console
uv run pytest tests/scripts/test_torus.py -v
```

## See also

<blockquote class="artificial-prose">

The `building-ratatui` corpus skill records the Ratatui and PyRatatui conventions used by terminal applications, including application state, elapsed-time motion, and a context-managed `Terminal()`.

</blockquote>

[pyratatui]: https://github.com/pyratatui/pyratatui
