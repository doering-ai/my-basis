############
### HEAD ###
############
### STANDARD
from __future__ import annotations
from math import hypot, isclose, pi

### EXTERNAL
import pydantic as pyd
import pytest as pyt

### INTERNAL
from my.scripts.tuitorii.torus import TorusApp, TorusConfig

cls = TorusApp


############
### DATA ###
############
# Compact config that keeps the geometry tests fast while exercising every code path.
SMALL = TorusConfig(samples_u=12, samples_v=10, width=60, height=30, mesh_stride=4)


############
### BODY ###
############
class TestTorusConfig:
    """Test suite for the `TorusConfig` pydantic model."""

    # -------------------
    # `+` Primary Methods
    # -------------------
    @pyt.mark.parametrize(
        'field, value',
        [
            ('samples_u', 7),
            ('samples_u', 161),
            ('samples_v', 7),
            ('samples_v', 121),
            ('width', 19),
            ('width', 241),
            ('height', 11),
            ('height', 121),
            ('fps', 0.9),
            ('fps', 120.1),
            ('speed', 0.04),
            ('speed', 8.1),
            ('mesh_stride', 1),
            ('mesh_stride', 33),
        ],
    )
    def test_bounds__reject_out_of_range(self, field: str, value: float):
        """Test that out-of-range bound values raise `ValidationError`."""
        with pyt.raises(pyd.ValidationError):
            TorusConfig(**{field: value})

    @pyt.mark.parametrize(
        'field, value',
        [
            ('samples_u', 8),
            ('samples_u', 160),
            ('samples_v', 8),
            ('samples_v', 120),
            ('width', 20),
            ('width', 240),
            ('height', 12),
            ('height', 120),
            ('fps', 1.0),
            ('fps', 120.0),
            ('speed', 0.05),
            ('speed', 8.0),
            ('mesh_stride', 2),
            ('mesh_stride', 32),
        ],
    )
    def test_bounds__accept_in_range(self, field: str, value: float):
        """Test that boundary values are accepted."""
        config = TorusConfig(**{field: value})
        assert getattr(config, field) == value


class TestTorusApp:
    """Test suite for the `TorusApp` geometry and clock core."""

    # -------------------
    # `.` Initial Methods
    # -------------------
    @pyt.fixture
    def app(self) -> TorusApp:
        """Create a fresh app with the small config."""
        return cls(SMALL)

    @pyt.fixture
    def clock(self, patch: pyt.MonkeyPatch):
        """Replace `monotonic` with a manually advanceable clock.

        Returns:
            A mutable list whose first element is the current fake time.
        """
        time = [0.0]

        def fake_monotonic() -> float:
            return time[0]

        patch.setattr('my.scripts.tuitorii.torus.monotonic', fake_monotonic)
        return time

    @pyt.fixture
    def clock_app(self, clock):
        """Create an app bound to the fake clock (started at t=0)."""
        return cls(SMALL)

    # -------------------
    # `-` Private Methods
    # -------------------
    @pyt.mark.parametrize(
        'a, b',
        [(0, 1), (0, 2), (0, 3), (1, 2), (1, 3), (2, 3)],
    )
    def test_rotate_plane__preserves_untouched_coords(self, a: int, b: int):
        """Test that coordinates outside the rotation plane are unchanged."""
        point = (3.0, 4.0, 5.0, 6.0)
        rotated = cls._rotate_plane(point, a, b, pi / 4)
        untouched = {0, 1, 2, 3} - {a, b}
        for i in untouched:
            assert rotated[i] == point[i]

    @pyt.mark.parametrize('angle', [0.0, pi / 6, pi / 4, pi / 2, pi])
    def test_rotate_plane__preserves_pair_norm(self, angle: float):
        """Test that the rotated coordinate pair preserves its norm."""
        point = (3.0, 4.0, 0.0, 0.0)
        rotated = cls._rotate_plane(point, 0, 1, angle)
        assert isclose(hypot(rotated[0], rotated[1]), hypot(point[0], point[1]), rel_tol=1e-12)

    @pyt.mark.parametrize('dur', [0.0, 0.5, 1.234, 10.0])
    def test_rotate__preserves_4d_norm(self, app: TorusApp, dur: float):
        """Test that coupled 4D rotations preserve the full 4D norm."""
        point = (0.6, 0.8, 0.0, 1.0)
        rotated = app._rotate(point, dur)
        assert isclose(hypot(*rotated), hypot(*point), rel_tol=1e-12)

    @pyt.mark.parametrize('elapsed', [0.0, 0.3, 1.0, 5.5])
    def test_project__stays_in_canvas_bounds(self, app: TorusApp, elapsed: float):
        """Test that every sampled point projects inside the canvas rectangle."""
        for sample in app.samples:
            px, py, _depth = app._project(app._rotate(sample, elapsed))
            assert -1e-6 <= px <= app.config.width + 1e-6
            assert -1e-6 <= py <= app.config.height + 1e-6

    # -------------------
    # `+` Primary Methods
    # -------------------
    def test_frame__point_and_ring_counts(self, app: TorusApp):
        """Test that `frame` produces the expected point/ring counts and ring lengths."""
        frame = app.frame()
        assert len(frame.points) == SMALL.samples_u * SMALL.samples_v
        # rings: one per u-stride plus one per v-stride
        u_rings = list(range(0, SMALL.samples_u, SMALL.mesh_stride))
        v_rings = list(range(0, SMALL.samples_v, SMALL.mesh_stride))
        assert len(frame.rings) == len(u_rings) + len(v_rings)
        for ring in frame.rings[: len(u_rings)]:
            assert len(ring) == SMALL.samples_v + 1
        for ring in frame.rings[len(u_rings) :]:
            assert len(ring) == SMALL.samples_u + 1

    def test_frame__points_depth_sorted(self, app: TorusApp):
        """Test that projected points are sorted by ascending depth."""
        frame = app.frame()
        depths = [p[2] for p in frame.points]
        assert depths == sorted(depths)

    def test_frame__is_deterministic_for_fixed_clock(self, clock_app: TorusApp, clock):
        """Test that two frames at the same instant are identical."""
        clock[0] = 1.5
        first = clock_app.frame()
        second = clock_app.frame()
        assert first == second

    def test_elapsed__advances_with_wall_time(self, clock_app: TorusApp, clock):
        """Test that elapsed time tracks wall-clock time when not paused."""
        clock[0] = 1.0
        assert isclose(clock_app.elapsed(), 1.0, rel_tol=1e-12)
        clock[0] = 2.5
        assert isclose(clock_app.elapsed(), 2.5, rel_tol=1e-12)

    def test_toggle_pause__freezes_elapsed(self, clock_app: TorusApp, clock):
        """Test that pausing freezes the reported elapsed time."""
        clock[0] = 1.0
        clock_app.toggle_pause()
        clock[0] = 5.0
        assert isclose(clock_app.elapsed(), 1.0, rel_tol=1e-12)

    def test_toggle_pause__resume_continues_without_jump(self, clock_app: TorusApp, clock):
        """Test that resuming continues elapsed time from the pause point."""
        clock[0] = 1.0
        clock_app.toggle_pause()
        clock[0] = 5.0
        clock_app.toggle_pause()
        clock[0] = 6.0
        # elapsed = 6.0 - 0.0 (start) - 4.0 (paused duration) = 2.0
        assert isclose(clock_app.elapsed(), 2.0, rel_tol=1e-12)

    def test_reset__zeroes_clock_and_speed(self, clock_app: TorusApp, clock):
        """Test that reset zeroes the clock and restores the configured speed."""
        clock[0] = 1.0
        clock_app.change_speed(2.0)
        clock_app.toggle_pause()
        clock[0] = 5.0
        clock_app.reset()
        assert clock_app.paused_at is None
        assert clock_app.pause_accumulated == 0.0
        assert clock_app.speed == SMALL.speed
        clock[0] = 6.0
        assert isclose(clock_app.elapsed(), 1.0, rel_tol=1e-12)

    @pyt.mark.parametrize(
        'start, factor, expected',
        [
            (1.0, 1.15, 1.15),
            (8.0, 10.0, 8.0),  # clamped to upper bound
            (0.1, 0.001, 0.05),  # clamped to lower bound
        ],
    )
    def test_change_speed__clamps_to_bounds(
        self, app: TorusApp, start: float, factor: float, expected: float
    ):
        """Test that speed adjustments are clamped to the `[0.05, 8.0]` range."""
        app.speed = start
        app.change_speed(factor)
        assert isclose(app.speed, expected, rel_tol=1e-12)

    # ------------
    # `*2` Methods
    # ------------
    def test_snapshot__banner_and_shape(self, clock_app: TorusApp, clock):
        """Test that the snapshot contains the banner and the expected line count."""
        clock[0] = 0.0
        text = clock_app.snapshot()
        assert 'myBasis x PyRatatui: 4D Clifford Torus' in text
        h = min(36, SMALL.height)
        # banner is 4 lines (blank, separator, label, separator) plus h body rows
        assert text.count('\n') == 4 + h - 1

    def test_snapshot__is_deterministic(self, clock_app: TorusApp, clock):
        """Test that two snapshots at the same instant are identical."""
        clock[0] = 0.7
        first = clock_app.snapshot()
        second = clock_app.snapshot()
        assert first == second

    # ----------------
    # Draw-Path Tests
    # ----------------
    def test_draw_canvas__renders_widgets(self, app: TorusApp, patch: pyt.MonkeyPatch):
        """Test that `_draw_canvas` drives the PyRatatui frame render path."""
        pyt.importorskip('pyratatui')
        from pyratatui import Rect

        class _FakeFrame:
            def __init__(self, area: Rect) -> None:
                self.area = area
                self.rendered: list[tuple] = []

            def render_widget(self, widget: object, area: Rect) -> None:
                self.rendered.append((widget, area))

        frame = _FakeFrame(Rect(0, 0, SMALL.width, SMALL.height))
        from my.scripts.tuitorii.torus import _draw_canvas

        _draw_canvas(app, frame)  # type: ignore[bad-argument-type]
        # block + canvas are always rendered
        assert len(frame.rendered) >= 2

    def test_draw_canvas__renders_pause_overlay_when_paused(
        self, app: TorusApp, patch: pyt.MonkeyPatch
    ):
        """Test that a paused app renders an additional overlay widget."""
        pyt.importorskip('pyratatui')
        from pyratatui import Rect

        class _FakeFrame:
            def __init__(self, area: Rect) -> None:
                self.area = area
                self.rendered: list[tuple] = []

            def render_widget(self, widget: object, area: Rect) -> None:
                self.rendered.append((widget, area))

        app.toggle_pause()
        frame = _FakeFrame(Rect(0, 0, SMALL.width, SMALL.height))
        from my.scripts.tuitorii.torus import _draw_canvas

        _draw_canvas(app, frame)  # type: ignore[bad-argument-type]
        # block + canvas + paused overlay
        assert len(frame.rendered) == 3


class TestTorusCli:
    """Test suite for the CLI entry points (`_parse_args`, `main`)."""

    # -------------------
    # `.` Initial Methods
    # -------------------
    @pyt.fixture
    def argv(self, patch: pyt.MonkeyPatch):
        """Patch `sys.argv`; returns a mutable list the test can populate."""
        args: list[str] = []
        patch.setattr('sys.argv', args)
        return args

    # ------------
    # `*2` Methods
    # ------------
    def test_parse_args__defaults(self, argv: list[str]):
        """Test that `_parse_args` produces default config with no flags."""
        from my.scripts.tuitorii.torus import _parse_args

        argv.extend(['tuitorii'])
        config = _parse_args()
        assert config.samples_u == 56
        assert config.samples_v == 28
        assert config.width == 120
        assert config.height == 48
        assert config.fps == 30.0
        assert config.speed == 1.0
        assert config.mesh_stride == 7
        assert config.snapshot is False

    def test_parse_args__custom_flags(self, argv: list[str]):
        """Test that `_parse_args` honors custom CLI flags."""
        from my.scripts.tuitorii.torus import _parse_args

        argv.extend(
            [
                'tuitorii',
                '--snapshot',
                '--samples-u',
                '24',
                '--samples-v',
                '16',
                '--width',
                '80',
                '--height',
                '40',
                '--fps',
                '60',
                '--speed',
                '2.5',
                '--mesh-stride',
                '5',
            ]
        )
        config = _parse_args()
        assert config.samples_u == 24
        assert config.samples_v == 16
        assert config.width == 80
        assert config.height == 40
        assert config.fps == 60.0
        assert config.speed == 2.5
        assert config.mesh_stride == 5
        assert config.snapshot is True

    def test_main__snapshot_prints_banner(self, argv: list[str], capsys: pyt.CaptureFixture[str]):
        """Test that `main --snapshot` prints the ASCII banner and exits."""
        from my.scripts.tuitorii.torus import main

        argv.extend(['tuitorii', '--snapshot'])
        main()
        out = capsys.readouterr().out
        assert 'myBasis x PyRatatui: 4D Clifford Torus' in out
