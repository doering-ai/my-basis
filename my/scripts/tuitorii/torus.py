"""Torus showcase through PyRatatui.

A rotating 4D Clifford torus rendered from Python through `pyratatui`, the Python
binding for Ratatui. Animation state lives in `TorusApp`; each frame rotates the
sampled surface in several 4D coordinate planes, then projects 4D -> 3D -> 2D for
the terminal canvas. PyRatatui is an optional dependency (the `terminal` extra)
and is imported lazily so the pure-geometry core stays importable without it.
"""

############
### HEAD ###
############
### STANDARD
from __future__ import annotations
from typing import TYPE_CHECKING, NamedTuple

from collections.abc import Iterable
from math import cos, pi, sin
from time import monotonic
import argparse as ap
import itertools as it

### EXTERNAL
from pydantic import BaseModel, Field

### INTERNAL
# Local imports

if TYPE_CHECKING:
    from pyratatui import Frame

############
### DATA ###
############
type R2 = tuple[float, float]
type R3 = tuple[float, float, float]
type R4 = tuple[float, float, float, float]


class TorusConfig(BaseModel):
    """Configuration for the rotating 4D torus showcase."""

    #: Number of samples around the first circle.
    samples_u: int = Field(default=56, ge=8, le=160)

    #: Number of samples around the second circle.
    samples_v: int = Field(default=28, ge=8, le=120)

    #: Logical canvas width used by PyRatatui's Canvas widget.
    width: int = Field(default=120, ge=20, le=240)

    #: Logical canvas height used by PyRatatui's Canvas widget.
    height: int = Field(default=48, ge=12, le=120)

    #: Target frames per second for the event/render loop.
    fps: float = Field(default=30.0, ge=1.0, le=120.0)

    #: Initial angular speed multiplier.
    speed: float = Field(default=1.0, ge=0.05, le=8.0)

    #: Step size for drawing low-density guide rings.
    mesh_stride: int = Field(default=7, ge=2, le=32)

    #: Whether to print one non-interactive ASCII frame and exit.
    snapshot: bool = False


class TorusFrame(NamedTuple):
    """Projected geometry for a single animation instant."""

    #: Depth-sorted projected points in canvas coordinates.
    points: list[R3]

    #: Projected guide rings in canvas coordinates.
    rings: list[list[R2]]


############
### BODY ###
############
class TorusApp:
    """Application state and geometry renderer for the PyRatatui torus demo."""

    def __init__(self, config: TorusConfig) -> None:
        """Initialize the app and pre-sample the 4D torus.

        Args:
            config: Rendering and animation configuration.
        """
        self.config = config
        self.started_at = monotonic()
        self.paused_at: float | None = None
        self.pause_accumulated = 0.0
        self.speed = config.speed
        self.samples = list(self._sample_clifford_torus())

    # -------------------
    # `-` Private Methods
    # -------------------
    def _sample_clifford_torus(self) -> Iterable[R4]:
        """Yield points from a Clifford torus embedded in four dimensions.

        Returns:
            An iterable of `(x, y, z, w)` sample points.
        """
        for i in range(self.config.samples_u):
            u = 2.0 * pi * i / self.config.samples_u
            for j in range(self.config.samples_v):
                v = 2.0 * pi * j / self.config.samples_v
                yield (cos(u), sin(u), cos(v), sin(v))

    @staticmethod
    def _rotate_plane(point: R4, a: int, b: int, angle: float) -> R4:
        """Rotate a 4D point in one coordinate plane.

        Args:
            point: Original 4D point.
            a: First coordinate index.
            b: Second coordinate index.
            angle: Rotation angle in radians.
        Returns:
            Rotated 4D point.
        """
        coords = list(point)
        ca = cos(angle)
        sa = sin(angle)
        xa = coords[a]
        xb = coords[b]
        coords[a] = xa * ca - xb * sa
        coords[b] = xa * sa + xb * ca
        return (coords[0], coords[1], coords[2], coords[3])

    def _rotate(self, point: R4, dur: float) -> R4:
        """Apply several coupled 4D rotations to a point.

        Args:
            point: Original 4D point.
            dur: Animation time in seconds.
        Returns:
            Rotated 4D point.
        """
        t = dur * self.speed
        point = self._rotate_plane(point, 0, 3, 0.43 * t)
        point = self._rotate_plane(point, 1, 2, 0.37 * t)
        point = self._rotate_plane(point, 0, 2, 0.19 * t)
        return self._rotate_plane(point, 1, 3, 0.13 * t)

    def _project(self, point: R4) -> R3:
        """Project a rotated 4D point to 2D canvas coordinates with depth.

        Args:
            point: Rotated 4D point.
        Returns:
            `(x, y, depth)` in logical canvas coordinates.
        """
        x, y, z, w = point

        # Perspective from 4D into 3D, then from 3D into 2D. The constants keep
        # the denominator safely positive for points on the unit Clifford torus.
        k4 = 2.8 / (3.6 - w)
        x3 = x * k4
        y3 = y * k4
        z3 = z * k4
        k3 = 2.2 / (3.2 - z3)

        scale = min(self.config.width * 0.38, self.config.height * 0.78)
        px = (self.config.width / 2.0) + x3 * k3 * scale
        py = (self.config.height / 2.0) + y3 * k3 * scale * 0.55
        depth = z3 + (0.45 * w)
        return (px, py, depth)

    def _project_ring(self, fixed: str, index: int, elapsed: float) -> list[R2]:
        """Project one torus guide ring.

        Args:
            fixed: Which angular dimension to hold fixed (`u` or `v`).
            index: Fixed sample index.
            elapsed: Animation time in seconds.
        Returns:
            Ordered 2D ring points.
        """
        ring: list[R2] = []
        n = self.config.samples_v if fixed == 'u' else self.config.samples_u
        fixed_n = self.config.samples_u if fixed == 'u' else self.config.samples_v
        for k in range(n + 1):
            u_index, v_index = (index, k % n) if fixed == 'u' else (k % n, index)
            u = 2.0 * pi * u_index / fixed_n if fixed == 'u' else 2.0 * pi * u_index / n
            v = 2.0 * pi * v_index / n if fixed == 'u' else 2.0 * pi * v_index / fixed_n
            x, y, _depth = self._project(self._rotate((cos(u), sin(u), cos(v), sin(v)), elapsed))
            ring.append((x, y))
        return ring

    # -------------------
    # `+` Primary Methods
    # -------------------
    def elapsed(self) -> float:
        """Return animation time, excluding paused wall-clock time.

        Returns:
            Effective elapsed animation time in seconds.
        """
        now = self.paused_at or monotonic()
        return now - self.started_at - self.pause_accumulated

    def frame(self) -> TorusFrame:
        """Build projected geometry for the current animation time.

        Returns:
            A depth-sorted torus frame.
        """
        elapsed = self.elapsed()
        points = [self._project(self._rotate(point, elapsed)) for point in self.samples]
        points.sort(key=lambda point: point[2])

        rings = [
            self._project_ring('u', u, elapsed)
            for u in range(0, self.config.samples_u, self.config.mesh_stride)
        ]
        rings.extend(
            self._project_ring('v', v, elapsed)
            for v in range(0, self.config.samples_v, self.config.mesh_stride)
        )

        return TorusFrame(points=points, rings=rings)

    def toggle_pause(self) -> None:
        """Pause or resume the animation clock."""
        now = monotonic()
        if self.paused_at is None:
            self.paused_at = now
        else:
            self.pause_accumulated += now - self.paused_at
            self.paused_at = None

    def reset(self) -> None:
        """Reset the animation clock and speed."""
        self.started_at = monotonic()
        self.paused_at = None
        self.pause_accumulated = 0.0
        self.speed = self.config.speed

    def change_speed(self, factor: float) -> None:
        """Adjust the animation speed by a multiplier.

        Args:
            factor: Multiplicative speed adjustment.
        """
        self.speed = max(0.05, min(8.0, self.speed * factor))

    def snapshot(self) -> str:
        """Render a non-interactive ASCII snapshot of the current frame.

        Returns:
            Plain text representation suitable for smoke tests and logs.
        """
        w = min(96, self.config.width)
        h = min(36, self.config.height)
        rows = [[' ' for _ in range(w)] for _ in range(h)]
        chars = '·:+=*#%@'
        for x, y, depth in self.frame().points:
            sx = round(x * (w - 1) / max(1, self.config.width - 1))
            sy = round(y * (h - 1) / max(1, self.config.height - 1))
            if 0 <= sx < w and 0 <= sy < h:
                idx = max(0, min(len(chars) - 1, round((depth + 1.65) * 2.2)))
                rows[sy][sx] = chars[idx]

        label = 'myBasis x PyRatatui: 4D Clifford Torus'
        title = '\n'.join(['', '=' * (len(label) + 8), f'=== {label} ===', '=' * (len(label) + 8)])
        return title + '\n' + '\n'.join(''.join(row).rstrip() for row in rows)


def _draw_canvas(app: TorusApp, frame: Frame) -> None:
    """Draw the torus frame through PyRatatui.

    Args:
        app: Current app state.
        frame: PyRatatui frame object supplied by `Terminal.draw`.
    """
    from pyratatui import Block, Canvas, Color, Paragraph, Style

    torus = app.frame()
    canvas = Canvas(width=app.config.width, height=app.config.height)

    # Guide rings are drawn first; depth-sorted points then thicken the visible
    # surface. PyRatatui 0.2.9 exposes Canvas geometry primitives but not
    # per-stroke styles, so depth is represented by draw order and density.
    for ring in torus.rings:
        for (x1, y1), (x2, y2) in it.pairwise(ring):
            canvas.draw_line(x1, y1, x2, y2)
    for x, y, _depth in torus.points:
        canvas.draw_point(x, y)

    area = frame.area
    block = (
        Block()
        .bordered()
        .title(' myBasis x PyRatatui — rotating 4D Clifford torus ')
        .title_bottom(f' q/Esc quit │ Space pause │ +/- speed {app.speed:0.2f}x │ r reset ')
        .border_style(Style().fg(Color.cyan()))
    )
    # `Block.inner(area)` shrinks a bordered block's area by one cell per side;
    # `Rect.inner(1, 1)` is the equivalent, stub-complete form (pyratatui's
    # stubs do not yet expose `Block.inner`).
    inner = area.inner(1, 1)
    frame.render_widget(block, area)
    frame.render_widget(canvas, inner)

    if app.paused_at is not None:
        paused = (
            Paragraph.from_string(' paused ')
            .block(Block().bordered().title(' state '))
            .style(Style().fg(Color.yellow()))
            .centered()
        )
        frame.render_widget(paused, inner.inner(2, 2))


def _parse_args() -> TorusConfig:
    """Parse CLI arguments into a torus configuration.

    Returns:
        Validated torus configuration.
    """
    parser = ap.ArgumentParser(
        prog='tuitorii',
        description='Render a rotating 4D Clifford torus through PyRatatui.',
    )
    parser.add_argument('--snapshot', action='store_true', help='print one ASCII frame and exit')
    parser.add_argument('--fps', type=float, default=30.0, help='target frames per second')
    parser.add_argument(
        '--speed', type=float, default=1.0, help='initial rotation speed multiplier'
    )
    parser.add_argument('--samples-u', type=int, default=56, help='samples around first circle')
    parser.add_argument('--samples-v', type=int, default=28, help='samples around second circle')
    parser.add_argument('--width', type=int, default=120, help='logical canvas width')
    parser.add_argument('--height', type=int, default=48, help='logical canvas height')
    parser.add_argument('--mesh-stride', type=int, default=7, help='guide-ring sampling stride')

    args = parser.parse_args()
    config = TorusConfig(
        samples_u=args.samples_u,
        samples_v=args.samples_v,
        width=args.width,
        height=args.height,
        fps=args.fps,
        speed=args.speed,
        mesh_stride=args.mesh_stride,
        snapshot=args.snapshot,
    )
    return config


def run(app: TorusApp) -> None:
    """Run the interactive PyRatatui application.

    Args:
        app: Application state to render and mutate from key events.
    """
    from pyratatui import Terminal

    tick_ms = max(1, round(1000 / app.config.fps))
    with Terminal() as term:
        term.hide_cursor()
        while True:
            term.draw(lambda frame: _draw_canvas(app, frame))
            event = term.poll_event(timeout_ms=tick_ms)
            if event is None:
                continue
            if event.code in {'q', 'Esc'}:
                break
            if event.code == ' ':
                app.toggle_pause()
            elif event.code in {'+', '='}:
                app.change_speed(1.15)
            elif event.code in {'-', '_'}:
                app.change_speed(1 / 1.15)
            elif event.code == 'r':
                app.reset()


def main() -> None:
    """Entry point for the PyRatatui torus showcase."""
    config = _parse_args()
    app = TorusApp(config)
    if config.snapshot:
        print(app.snapshot())
        return
    run(app)


if __name__ == '__main__':
    main()
