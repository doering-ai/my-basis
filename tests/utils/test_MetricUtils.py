############
### HEAD ###
############
### STANDARD
from collections.abc import Callable
import functools as ft
import importlib
import logging as lg
from pathlib import Path
import time

### EXTERNAL
import pytest as pyt

### INTERNAL
import my.utils as ut
from my.utils import MetricUtils

cls = MetricUtils
metric_module = importlib.import_module('my.utils.MetricUtils')


############
### BODY ###
############
class TestMetricUtils:
    # -----------
    # `3` LOGGING
    # -----------
    def test_get_package_name(self):
        name = cls.get_package_name()
        assert isinstance(name, str)
        assert len(name) > 0

    def test_setup_fire_logging_is_private_and_environment_driven(
        self, monkeypatch: pyt.MonkeyPatch
    ):
        """OTLP-only setup keeps content capture off and expensive metrics opt-in."""
        configured: dict[str, object] = {}
        system_metrics: list[bool] = []
        logger = lg.getLogger('test-private-telemetry')
        logger.handlers.clear()
        monkeypatch.setenv('OTEL_EXPORTER_OTLP_ENDPOINT', 'http://127.0.0.1:4318')
        monkeypatch.setenv('OTEL_SERVICE_NAME', 'fleet-test')
        monkeypatch.setenv('OTEL_DEPLOYMENT_ENVIRONMENT', 'canary')
        monkeypatch.delenv('LOGFIRE_TOKEN', raising=False)
        monkeypatch.setattr(
            metric_module.fire, 'configure', lambda **kwargs: configured.update(kwargs)
        )
        monkeypatch.setattr(
            metric_module.fire,
            'instrument_system_metrics',
            lambda: system_metrics.append(True),
        )

        cls.setup_fire_logging('', 'test-package', logger, is_dev=False)

        assert configured['service_name'] == 'fleet-test'
        assert configured['environment'] == 'canary'
        assert configured['send_to_logfire'] == 'if-token-present'
        assert configured['inspect_arguments'] is False
        assert configured['distributed_tracing'] is False
        assert configured['console'] is False
        assert 'scrubbing' not in configured
        assert 'token' not in configured
        assert system_metrics == []
        assert logger.handlers == []

    @pyt.mark.parametrize('scrubbing', [False, 0, None, True])
    def test_setup_fire_logging_rejects_unsafe_scrubbing(
        self, monkeypatch: pyt.MonkeyPatch, scrubbing: object
    ):
        """Falsy lookalikes cannot bypass the content-scrubbing boundary."""
        monkeypatch.setattr(metric_module.fire, 'configure', lambda **_: None)

        with pyt.raises(ValueError, match='privacy'):
            cls.setup_fire_logging(
                'synthetic-token',
                'test-package',
                lg.getLogger('test-unsafe-scrubbing'),
                scrubbing=scrubbing,
            )

    def test_setup_fire_logging_rejects_other_unsafe_overrides(self, monkeypatch: pyt.MonkeyPatch):
        """Argument capture and an unconditional hosted send cannot be smuggled in."""
        monkeypatch.setattr(metric_module.fire, 'configure', lambda **_: None)
        logger = lg.getLogger('test-unsafe-telemetry')

        with pyt.raises(ValueError, match='privacy'):
            cls.setup_fire_logging(
                'synthetic-token', 'test-package', logger, inspect_arguments=True
            )
        with pyt.raises(ValueError, match='destination policy'):
            cls.setup_fire_logging('synthetic-token', 'test-package', logger, send_to_logfire=True)

    def test_setup_fire_logging_rejects_callback_scrubbing(self, monkeypatch: pyt.MonkeyPatch):
        """A custom callback cannot restore or redirect scrubbed content."""
        monkeypatch.setattr(metric_module.fire, 'configure', lambda **_: None)
        scrubbing = metric_module.fire.ScrubbingOptions(callback=lambda match: match)

        with pyt.raises(ValueError, match='privacy'):
            cls.setup_fire_logging(
                'synthetic-token',
                'test-package',
                lg.getLogger('test-custom-scrubbing'),
                scrubbing=scrubbing,
            )

    def test_setup_fire_logging_rejects_unknown_scrubbing_fields(
        self, monkeypatch: pyt.MonkeyPatch
    ):
        """A Logfire upgrade cannot add an unreviewed scrubbing escape hatch."""
        monkeypatch.setattr(metric_module.fire, 'configure', lambda **_: None)
        scrubbing = metric_module.fire.ScrubbingOptions()
        vars(scrubbing)['future_disable_scrubbing'] = True

        with pyt.raises(ValueError, match='privacy'):
            cls.setup_fire_logging(
                'synthetic-token',
                'test-package',
                lg.getLogger('test-future-scrubbing'),
                scrubbing=scrubbing,
            )

    def test_setup_fire_logging_rejects_unknown_options(self, monkeypatch: pyt.MonkeyPatch):
        """The privacy boundary is a closed allowlist across Logfire upgrades."""
        monkeypatch.setattr(metric_module.fire, 'configure', lambda **_: None)

        with pyt.raises(ValueError, match='Unsupported telemetry configuration'):
            cls.setup_fire_logging(
                'synthetic-token',
                'test-package',
                lg.getLogger('test-unknown-option'),
                future_content_capture=True,
            )

    @pyt.mark.parametrize(
        'name,value',
        [
            ('OTEL_SERVICE_NAME', 'service name with spaces'),
            ('OTEL_DEPLOYMENT_ENVIRONMENT', 'production\nforged=true'),
            ('OTEL_SERVICE_NAME', 'x' * 129),
        ],
    )
    def test_setup_fire_logging_rejects_unbounded_identity(
        self,
        monkeypatch: pyt.MonkeyPatch,
        name: str,
        value: str,
    ):
        """Environment identity cannot inject or explode telemetry cardinality."""
        monkeypatch.setenv(name, value)
        monkeypatch.setattr(metric_module.fire, 'configure', lambda **_: None)

        with pyt.raises(ValueError, match='bounded telemetry identity'):
            cls.setup_fire_logging(
                'synthetic-token',
                'test-package',
                lg.getLogger('test-unsafe-identity'),
            )

    @pyt.mark.parametrize(
        'endpoint',
        [
            'http://attacker.example:4318',
            'http://70447876.gitlab-o11y.com/v1/traces',
            'https://user:secret@70447876.gitlab-o11y.com/v1/traces',
            'https://70447876.gitlab-o11y.com/v1/traces?tenant=forged',
        ],
    )
    def test_setup_fire_logging_rejects_unapproved_otlp_destination(
        self, monkeypatch: pyt.MonkeyPatch, endpoint: str
    ):
        """Application exporters can target only local collectors or the GitLab group."""
        monkeypatch.setenv('OTEL_EXPORTER_OTLP_ENDPOINT', endpoint)
        monkeypatch.setattr(metric_module.fire, 'configure', lambda **_: None)

        with pyt.raises(ValueError, match='approved telemetry destination'):
            cls.setup_fire_logging(
                '',
                'test-package',
                lg.getLogger('test-unsafe-endpoint'),
            )

    def test_setup_fire_logging_accepts_gitlab_group_destination(
        self, monkeypatch: pyt.MonkeyPatch
    ):
        """The human-gated GitLab.com group endpoint remains an approved fan-out target."""
        configured: dict[str, object] = {}
        monkeypatch.setenv(
            'OTEL_EXPORTER_OTLP_ENDPOINT',
            'https://70447876.gitlab-o11y.com/v1/traces',
        )
        monkeypatch.setattr(
            metric_module.fire,
            'configure',
            lambda **kwargs: configured.update(kwargs),
        )

        cls.setup_fire_logging(
            '',
            'test-package',
            lg.getLogger('test-gitlab-endpoint'),
            is_dev=False,
        )

        assert configured['service_name'] == 'test-package'

    def test_setup_logging_surfaces_privacy_validation(self, monkeypatch: pyt.MonkeyPatch):
        """Invalid privacy controls fail before local logger state is changed."""
        setup_calls: list[bool] = []
        monkeypatch.setattr(
            cls,
            'setup_py_logging',
            staticmethod(lambda **_: setup_calls.append(True)),
        )

        with pyt.raises(ValueError, match='privacy'):
            cls.setup_logging(
                logdir=Path(),
                is_dev=False,
                fire_token='synthetic-token',
                package='test-package',
                scrubbing=False,
            )

        assert setup_calls == []

    def test_setup_fire_logging_sensitive_features_are_opt_in(self, monkeypatch: pyt.MonkeyPatch):
        """Hosted logs and per-process host metrics require an explicit caller choice."""
        system_metrics: list[bool] = []
        logger = lg.getLogger('test-opt-in-telemetry')
        logger.handlers.clear()
        monkeypatch.setattr(metric_module.fire, 'configure', lambda **_: None)
        monkeypatch.setattr(
            metric_module.fire,
            'instrument_system_metrics',
            lambda: system_metrics.append(True),
        )
        monkeypatch.setattr(metric_module.fire, 'LogfireLoggingHandler', lg.NullHandler)

        cls.setup_fire_logging(
            'synthetic-token',
            'test-package',
            logger,
            is_dev=False,
            export_logs=True,
            system_metrics=True,
        )

        assert system_metrics == [True]
        assert len(logger.handlers) == 1

    def test_setup_fire_logging_isolates_optional_instrumentation_failure(
        self, monkeypatch: pyt.MonkeyPatch, caplog: pyt.LogCaptureFixture
    ):
        """Optional metrics cannot tear down the configured trace provider."""
        configured: list[bool] = []
        logger = lg.getLogger('test-partial-telemetry')
        logger.handlers.clear()
        monkeypatch.setattr(
            metric_module.fire,
            'configure',
            lambda **_: configured.append(True),
        )
        monkeypatch.setattr(
            metric_module.fire,
            'instrument_system_metrics',
            lambda: (_ for _ in ()).throw(RuntimeError('provider failure')),
        )

        with caplog.at_level(lg.WARNING):
            cls.setup_fire_logging(
                'synthetic-token',
                'test-package',
                logger,
                is_dev=False,
                system_metrics=True,
            )

        assert configured == [True]
        assert 'System telemetry instrumentation failed.' in caplog.text
        assert 'provider failure' not in caplog.text

    def test_setup_logging_warns_when_cached_options_are_ignored(
        self, caplog: pyt.LogCaptureFixture
    ):
        """Idempotent setup makes its first-configuration-wins rule visible."""
        logger = lg.getLogger('test-cached-telemetry')
        original_loggers = cls.LOGGERS
        original_ready = cls.TELEMETRY_READY
        cls.LOGGERS = {'test-package': logger}
        cls.TELEMETRY_READY = {'test-package'}
        try:
            with caplog.at_level(lg.WARNING):
                result = cls.setup_logging(
                    logdir=Path(),
                    is_dev=False,
                    fire_token='',
                    package='test-package',
                    system_metrics=True,
                )
        finally:
            cls.LOGGERS = original_loggers
            cls.TELEMETRY_READY = original_ready

        assert result is logger
        assert 'later setup options were not applied' in caplog.text

    def test_setup_logging_degrades_without_provider_details(
        self, monkeypatch: pyt.MonkeyPatch, caplog: pyt.LogCaptureFixture
    ):
        """An unavailable telemetry backend cannot crash an otherwise healthy app."""
        logger = lg.getLogger('test-telemetry-degrade')
        logger.handlers.clear()
        original_loggers = cls.LOGGERS
        original_ready = cls.TELEMETRY_READY
        cls.LOGGERS = {}
        cls.TELEMETRY_READY = set()
        monkeypatch.setattr(cls, 'setup_py_logging', staticmethod(lambda **_: logger))

        def fail(**_: object) -> None:
            raise RuntimeError('Bearer synthetic-secret at private.example')

        monkeypatch.setattr(cls, 'setup_fire_logging', staticmethod(fail))
        try:
            with caplog.at_level(lg.WARNING):
                result = cls.setup_logging(
                    logdir=Path(),
                    is_dev=False,
                    fire_token='synthetic-token',
                    package='test-package',
                )
        finally:
            cls.LOGGERS = original_loggers
            cls.TELEMETRY_READY = original_ready

        assert result is logger
        assert 'Remote telemetry setup failed; continuing without export.' in caplog.text
        assert 'synthetic-secret' not in caplog.text
        assert 'private.example' not in caplog.text

    def test_setup_logging_retries_remote_setup(self, monkeypatch: pyt.MonkeyPatch):
        """A transient exporter failure does not make local logger caching permanent."""
        logger = lg.getLogger('test-telemetry-retry')
        logger.handlers.clear()
        setup_py_calls: list[bool] = []
        setup_fire_calls: list[bool] = []
        original_loggers = cls.LOGGERS
        original_ready = cls.TELEMETRY_READY
        cls.LOGGERS = {}
        cls.TELEMETRY_READY = set()
        monkeypatch.setattr(
            cls,
            'setup_py_logging',
            staticmethod(lambda **_: setup_py_calls.append(True) or logger),
        )

        def flaky_fire(**_: object) -> None:
            setup_fire_calls.append(True)
            if len(setup_fire_calls) == 1:
                raise RuntimeError('collector unavailable')

        monkeypatch.setattr(cls, 'setup_fire_logging', staticmethod(flaky_fire))
        try:
            first = cls.setup_logging(
                logdir=Path(),
                is_dev=False,
                fire_token='synthetic-token',
                package='test-package',
            )
            second = cls.setup_logging(
                logdir=Path(),
                is_dev=False,
                fire_token='synthetic-token',
                package='test-package',
            )
            assert 'test-package' in cls.TELEMETRY_READY
        finally:
            cls.LOGGERS = original_loggers
            cls.TELEMETRY_READY = original_ready

        assert first is second is logger
        assert setup_py_calls == [True]
        assert setup_fire_calls == [True, True]

    def test_setup_warnings(self):
        original = cls.WARNINGS_SETUP
        try:
            cls.WARNINGS_SETUP = False
            cls.setup_warnings()
            assert cls.WARNINGS_SETUP is True
            # Running again should be idempotent
            cls.setup_warnings()
            assert cls.WARNINGS_SETUP is True
        finally:
            cls.WARNINGS_SETUP = original

    def test_setup_warnings_callable_on_instance(self):
        """`setup_warnings` must be callable on an instance, not just the class.

        Regression test for MEMY-165: `setup_warnings` was a bare `@_guard`-decorated function
        with no `self`/`cls` parameter and no `@staticmethod`, so `MetricUtils().setup_warnings()`
        raised `TypeError: setup_warnings() takes 0 positional arguments but 1 was given` --
        Python implicitly passes the instance as the first positional argument to an
        undecorated function accessed off an instance. Dormant because every call site in this
        codebase goes through the class directly (`MetricUtils.setup_warnings()`, never
        instantiated), but it detonates on first instance access.
        """
        original = cls.WARNINGS_SETUP
        try:
            cls.WARNINGS_SETUP = False
            cls().setup_warnings()
            assert cls.WARNINGS_SETUP is True
        finally:
            cls.WARNINGS_SETUP = original

    # -----------
    # `4` METRICS
    # -----------
    def test_instrument_sync(self):
        counter = {'test_func': 0}

        def test_func():
            return sum(range(100))

        instrumented = cls._instrument(test_func, counter)
        result = instrumented()

        assert result == sum(range(100))
        assert counter['test_func'] >= 0

    @pyt.mark.asyncio
    async def test_instrument_async(self):
        counter = {'async_test': 0}

        async def async_test():
            return 42

        instrumented = cls._instrument(async_test, counter)
        result = await instrumented()

        assert result == 42
        assert counter['async_test'] >= 0

    @pyt.mark.parametrize(
        'make_measure',
        [
            pyt.param(
                lambda counter: ft.partial(cls.measure_context, counter=counter),
                id='owning_class',
            ),
            pyt.param(
                # MEMY-165: pyrefly WARNs `missing-attribute` here -- `my/__init__.py`'s
                # `Utils` re-export shadows the `my.utils` submodule name, so pyrefly's static
                # view of `ut` resolves to `Utils` (no `measure_context`) even though `ut` is
                # genuinely the submodule at runtime. Known, intentional facade shadow, not an
                # upstream stub gap; see the `missing-attribute` note in
                # `[tool.pyrefly.errors]` (pyproject.toml) for the full rationale.
                lambda counter: ft.partial(ut.measure_context, counter=counter),
                id='partial_via_module_facade',
            ),
        ],
    )
    def test_measure_context_records_elapsed_time(self, make_measure: Callable):
        """`measure_context` must work as a real context manager via both access patterns.

        Regression test for MEMY-158: `measure_context` stacks `@classmethod`,
        `@ctx.contextmanager`, and `@_guard`. The wrong decorator order (`@ctx.contextmanager`
        outermost, wrapping the bare `classmethod` descriptor instead of the bound function)
        raises `TypeError: 'classmethod' object is not callable` the moment the context manager
        is entered -- both directly off the owning class (`MetricUtils.measure_context`) and
        through the `my.utils` module facade via `ft.partial` (the exact pattern `wikiparse`
        uses). This asserts the timing side effect (`cls._measure` writing into `counter`)
        actually fires, not just that no exception was raised -- a `pass`-bodied block measures
        0ns and would pass even with `dur_ms == 0` skipping the write entirely.
        """
        counter: dict[str, int] = {'blk': 0}
        measure = make_measure(counter)

        with measure('blk'):
            time.sleep(0.01)

        assert counter['blk'] > 0

    @pyt.mark.parametrize(
        'counter',
        [
            pyt.param({}, id='unseeded'),
            pyt.param({'blk': 0}, id='seeded'),
        ],
    )
    def test_measure_context_unseeded_counter_no_keyerror(self, counter: dict[str, int]):
        """`_measure` must not raise `KeyError` when `name` isn't pre-seeded in `counter`.

        Regression test for MEMY-165: `counter[name] += dur_ms` assumes `name` is already a key
        in `counter`, which raises `KeyError` the first time a nonzero-duration measurement
        fires for a metric nobody pre-seeded. Every caller in this codebase happens to
        pre-seed (e.g. `dict.fromkeys(TIME_INDEX, 0)`), which masked the bug; this asserts an
        unseeded counter works identically to a seeded one.
        """
        with cls.measure_context('blk', counter):
            time.sleep(0.01)

        assert counter['blk'] > 0

    def test_measure_context_records_elapsed_time_on_exception(self):
        """`measure_context` must record timing even when the block raises.

        Regression test for MEMY-165: the original implementation was a bare `yield` with no
        `try`/`finally`, so `cls._measure` never ran when the body raised -- the timing was
        silently dropped on exactly the paths (slow-then-crashing code) where a caller
        debugging via metrics would want it most.
        """
        counter: dict[str, int] = {'blk': 0}

        def _sleep_then_raise() -> None:
            time.sleep(0.01)
            raise ValueError('boom')

        with pyt.raises(ValueError, match='boom'), cls.measure_context('blk', counter):
            _sleep_then_raise()

        assert counter['blk'] > 0
