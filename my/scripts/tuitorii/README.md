# PyRatatui 4D Torus Showcase

This directory contains a small terminal-art showcase for `myBasis`: a rotating
4D Clifford torus rendered from Python through [`pyratatui`][pyratatui], the
Python binding for Ratatui.

The demo follows the Ratatui animation pattern recommended by the upstream
project:

- keep animation state in an application object;
- draw complete frames through Ratatui/PyRatatui and let the buffer diffing
  layer update the terminal;
- drive motion from elapsed time instead of treating each frame as one fixed
  simulation step;
- use `Terminal()` as a context manager so alternate-screen/raw-mode setup is
  restored on exit;
- keep input handling centralized and non-blocking.

## Run

Install the optional terminal dependency, then run the module:

```zsh
uv run --extra terminal python my/scripts/pyratatui_torus/torus.py
```

The module form below should also work once the top-level `my` package imports
cleanly in the current checkout:

```zsh
uv run --extra terminal python -m my.scripts.pyratatui_torus
```

Controls:

| Key | Effect |
| --- | --- |
| `q` / `Esc` | quit |
| `Space` | pause/resume |
| `+` / `=` | increase rotation speed |
| `-` / `_` | decrease rotation speed |
| `r` | reset speed and pause state |

For a non-interactive geometry smoke test, render one ASCII snapshot:

```zsh
uv run --extra terminal python my/scripts/pyratatui_torus/torus.py --snapshot
```

## Why a Clifford torus?

The point cloud is sampled from the 4D product of two circles:

```text
(x, y, z, w) = (cos u, sin u, cos v, sin v)
```

Each frame rotates the sampled surface in several 4D coordinate planes, then
projects 4D → 3D → 2D. Nearer projected points are drawn after farther ones so
the terminal image has a simple depth cue.

[pyratatui]: https://github.com/pyratatui/pyratatui
