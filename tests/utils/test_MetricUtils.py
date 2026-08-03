############
### HEAD ###
############
### STANDARD
from collections.abc import Callable
import functools as ft
import importlib
import logging as lg
import logging.handlers as lgh
from pathlib import Path
from typing import Any, cast
import time

### EXTERNAL
import pytest as pyt

### INTERNAL
from my import utils as ut
from my.utils import MetricUtils

cls = MetricUtils
metric_module = importlib.import_module('my.utils.MetricUtils')


############
### DATA ###
############
def _unknown_scrubbing() -> object:
    """Build scrubbing options with a field unknown to the privacy allowlist."""
    scrubbing = metric_module.fire.ScrubbingOptions()
    vars(scrubbing)['future_disable_scrubbing'] = True
    return scrubbing


class _RecordingHandler(lg.NullHandler):
    """A `LogfireLoggingHandler` double that captures the level passed to `setLevel`."""

    def __init__(self) -> None:
        super().__init__()
        self.recorded_level: int | str | None = None

    def setLevel(self, level: int | str) -> None:  # noqa: N802  # stdlib camelCase override
        self.recorded_level = level
        super().setLevel(level)


############
### BODY ###
############
class TestMetricUtils:
    # -----------
    # `3` LOGGING
    # -----------
    @pyt.mark.parametrize(
        'environment, expected',
        [
            pyt.param('editable', 'my-basis', id='editable'),
            pyt.param('source', 'my-basis', id='source_tree'),
            pyt.param('script', 'my', id='script_fallback'),
        ],
    )
    def test_get_package_name(
        self,
        monkeypatch: pyt.MonkeyPatch,
        tmp_path: Path,
        environment: str,
        expected: str,
    ):
        """Resolve installed and source projects while retaining the import-name fallback."""
        if environment in {'source', 'script'}:
            monkeypatch.setattr(metric_module.impm, 'packages_distributions', dict)
            monkeypatch.setattr(metric_module.impm, 'distributions', tuple)
        if environment == 'script':
            script_file = tmp_path / 'my' / 'utils' / 'MetricUtils.py'
            script_file.parent.mkdir(parents=True)
            script_file.touch()
            monkeypatch.setattr(metric_module, '__file__', str(script_file))

        name = cls.get_package_name()
        assert name == expected

    def test_setup_py_logging__pid_suffix_prevents_same_second_collision(
        self,
        monkeypatch: pyt.MonkeyPatch,
        tmp_path: Path,
    ):
        """Parallel sessions in the same second with the same logger name get distinct log files."""
        fixed_time = metric_module.SystemUtils.posix(0)
        monkeypatch.setattr(
            metric_module.SystemUtils,
            'posix',
            classmethod(lambda cls, val=None: fixed_time),
        )

        logger = lg.getLogger('test-same-second')
        logger.handlers.clear()

        # First process
        monkeypatch.setattr(metric_module.os, 'getpid', lambda: 1001)
        first = cls.setup_py_logging(tmp_path, True, 'test-same-second', logger=logger)
        first_file = cast('lg.FileHandler', first.handlers[-1]).baseFilename

        # Second process with the same logger name, same second, different PID
        monkeypatch.setattr(metric_module.os, 'getpid', lambda: 1002)
        second = cls.setup_py_logging(tmp_path, True, 'test-same-second', logger=logger)
        second_file = cast('lg.FileHandler', second.handlers[-1]).baseFilename

        assert Path(first_file).name == 'test-same-second_700101-000000_1001.log'
        assert Path(second_file).name == 'test-same-second_700101-000000_1002.log'
        assert first_file != second_file
        assert Path(first_file).exists()
        assert Path(second_file).exists()

    def test_setup_fire_logging__private(self, monkeypatch: pyt.MonkeyPatch):
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

    @pyt.mark.parametrize(
        'options_factory,error',
        [
            pyt.param(lambda: {'scrubbing': False}, 'privacy', id='scrubbing_false'),
            pyt.param(lambda: {'scrubbing': 0}, 'privacy', id='scrubbing_zero'),
            pyt.param(lambda: {'scrubbing': None}, 'privacy', id='scrubbing_none'),
            pyt.param(lambda: {'scrubbing': True}, 'privacy', id='scrubbing_true'),
            pyt.param(
                lambda: {
                    'scrubbing': metric_module.fire.ScrubbingOptions(callback=lambda match: match)
                },
                'privacy',
                id='scrubbing_callback',
            ),
            pyt.param(
                lambda: {'scrubbing': _unknown_scrubbing()},
                'privacy',
                id='scrubbing_unknown_field',
            ),
            pyt.param(
                lambda: {'inspect_arguments': True},
                'privacy',
                id='argument_capture',
            ),
            pyt.param(
                lambda: {'send_to_logfire': True},
                'destination policy',
                id='hosted_send',
            ),
            pyt.param(
                lambda: {'future_content_capture': True},
                'Unsupported telemetry configuration',
                id='unknown_option',
            ),
        ],
    )
    def test_setup_fire_logging__rejects_options(
        self,
        monkeypatch: pyt.MonkeyPatch,
        options_factory: Callable[[], dict[str, Any]],
        error: str,
    ):
        """Unsafe and unknown Logfire options fail against the closed allowlist."""
        monkeypatch.setattr(metric_module.fire, 'configure', lambda **_: None)

        with pyt.raises(ValueError, match=error):
            cls.setup_fire_logging(
                'synthetic-token',
                'test-package',
                lg.getLogger('test-unsafe-option'),
                **options_factory(),
            )

    @pyt.mark.parametrize(
        'name,value',
        [
            ('OTEL_SERVICE_NAME', 'service name with spaces'),
            ('OTEL_DEPLOYMENT_ENVIRONMENT', 'production\nforged=true'),
            ('OTEL_SERVICE_NAME', 'x' * 129),
        ],
    )
    def test_setup_fire_logging__rejects_identity(
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
    def test_setup_fire_logging__rejects_destination(
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

    def test_setup_fire_logging__accepts_gitlab(self, monkeypatch: pyt.MonkeyPatch):
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

    def test_setup_logging__privacy_validation(self, monkeypatch: pyt.MonkeyPatch):
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

    def test_setup_fire_logging__sensitive_features_opt_in(self, monkeypatch: pyt.MonkeyPatch):
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

    @pyt.mark.parametrize(
        'is_dev, expected',
        [
            pyt.param(True, lg.DEBUG, id='dev_debug'),
            pyt.param(False, lg.INFO, id='prod_info'),
        ],
    )
    def test_setup_fire_logging__log_level_default(
        self, monkeypatch: pyt.MonkeyPatch, is_dev: bool, expected: int
    ):
        """Without `log_level`, the export handler floor keeps the environment default."""
        logger = lg.getLogger('test-log-level-default')
        logger.handlers.clear()
        handler = _RecordingHandler()
        monkeypatch.setattr(metric_module.fire, 'configure', lambda **_: None)
        monkeypatch.setattr(metric_module.fire, 'LogfireLoggingHandler', lambda: handler)

        cls.setup_fire_logging(
            'synthetic-token', 'test-package', logger, is_dev=is_dev, export_logs=True
        )

        assert handler.recorded_level == expected
        assert logger.handlers == [handler]

    @pyt.mark.parametrize(
        'log_level, expected',
        [
            pyt.param('WARNING', lg.WARNING, id='standard_name'),
            pyt.param('warning', lg.WARNING, id='case_insensitive'),
            pyt.param('ERROR', lg.ERROR, id='higher_floor'),
        ],
    )
    def test_setup_fire_logging__log_level_explicit(
        self, monkeypatch: pyt.MonkeyPatch, log_level: str, expected: int
    ):
        """An explicit `log_level` overrides the environment default, case-insensitively."""
        logger = lg.getLogger('test-log-level-explicit')
        logger.handlers.clear()
        handler = _RecordingHandler()
        monkeypatch.setattr(metric_module.fire, 'configure', lambda **_: None)
        monkeypatch.setattr(metric_module.fire, 'LogfireLoggingHandler', lambda: handler)

        cls.setup_fire_logging(
            'synthetic-token',
            'test-package',
            logger,
            is_dev=False,
            export_logs=True,
            log_level=log_level,
        )

        assert handler.recorded_level == expected

    @pyt.mark.parametrize(
        'log_level',
        [
            pyt.param('BOGUS', id='unknown_name'),
            pyt.param('warn level', id='malformed_name'),
        ],
    )
    def test_setup_fire_logging__log_level_rejects_invalid(
        self, monkeypatch: pyt.MonkeyPatch, log_level: str
    ):
        """Junk level names fail before the telemetry provider is configured."""
        configured: list[bool] = []
        monkeypatch.setattr(metric_module.fire, 'configure', lambda **_: configured.append(True))

        with pyt.raises(ValueError, match='Unsupported telemetry log level'):
            cls.setup_fire_logging(
                'synthetic-token',
                'test-package',
                lg.getLogger('test-log-level-invalid'),
                export_logs=True,
                log_level=log_level,
            )

        assert configured == []

    def test_setup_logging__log_level_threads_through(self, monkeypatch: pyt.MonkeyPatch):
        """`log_level` reaches the export handler through the full `setup_logging` chain."""
        logger = lg.getLogger('test-log-level-thread')
        logger.handlers.clear()
        handler = _RecordingHandler()
        original_loggers = cls.LOGGERS
        original_ready = cls.TELEMETRY_READY
        cls.LOGGERS = {}
        cls.TELEMETRY_READY = set()
        monkeypatch.setattr(cls, 'setup_py_logging', staticmethod(lambda **_: logger))
        monkeypatch.setattr(metric_module.fire, 'configure', lambda **_: None)
        monkeypatch.setattr(metric_module.fire, 'LogfireLoggingHandler', lambda: handler)
        try:
            cls.setup_logging(
                logdir=Path(),
                is_dev=False,
                fire_token='synthetic-token',
                package='test-package',
                export_logs=True,
                log_level='ERROR',
            )
            assert 'test-package' in cls.TELEMETRY_READY
        finally:
            cls.LOGGERS = original_loggers
            cls.TELEMETRY_READY = original_ready

        assert handler.recorded_level == lg.ERROR
        assert logger.handlers == [handler]

    def test_setup_fire_logging__isolates_instrument_failure(
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

    def test_setup_logging__warns_cached_options(self, caplog: pyt.LogCaptureFixture):
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

    def test_setup_logging__degrades_without_provider_details(
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

    def test_setup_logging__retries_remote(self, monkeypatch: pyt.MonkeyPatch):
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

    @pyt.mark.parametrize(
        'setup',
        [
            pyt.param(cls.setup_warnings, id='class'),
            pyt.param(cls().setup_warnings, id='instance'),
        ],
    )
    def test_setup_warnings(self, setup: Callable[[], None]):
        """Warning setup is idempotent through class and instance access."""
        original = cls.WARNINGS_SETUP
        try:
            cls.WARNINGS_SETUP = False
            setup()
            assert cls.WARNINGS_SETUP
            setup()
            assert cls.WARNINGS_SETUP
        finally:
            cls.WARNINGS_SETUP = original

    # -----------
    # `4` METRICS
    # -----------
    def test_setup_metrics__clears_directory(self, tmp_path: Path, monkeypatch: pyt.MonkeyPatch):
        """A non-empty metrics directory is cleared recursively."""
        pyt.importorskip('pandas')
        metrics_dir = (tmp_path / 'metrics').resolve()
        metrics_dir.mkdir()
        (metrics_dir / 'stale.db').write_text('old')
        nested = metrics_dir / 'nested'
        nested.mkdir()
        (nested / 'inner.db').write_text('old')

        monkeypatch.setenv('PROMETHEUS_MULTIPROC_DIR', str(metrics_dir))
        original_setup = cls.METRICS_SETUP
        cls.METRICS_SETUP = False
        try:
            cls.setup_metrics(metrics_dir, lg.getLogger('test-setup-metrics-clear'))
        finally:
            cls.METRICS_SETUP = original_setup

        assert list(metrics_dir.iterdir()) == []

    @pyt.mark.parametrize(
        'elapsed_ns,repetitions',
        [
            pyt.param(700_000, 1, id='single'),
            pyt.param(300_000, 5, id='accumulated'),
        ],
    )
    def test_measure__sub_millisecond(
        self,
        monkeypatch: pyt.MonkeyPatch,
        elapsed_ns: int,
        repetitions: int,
    ):
        """Sub-millisecond durations are recorded once and when accumulated."""
        pyt.importorskip('pandas')
        now = 10_000_000
        counter: dict[str, float] = {}
        monkeypatch.setattr(metric_module, 'perf_counter_ns', lambda: now)

        for _ in range(repetitions):
            cls._measure('fast_op', counter, now - elapsed_ns)

        assert counter['fast_op'] == repetitions * elapsed_ns / 1_000_000

    def test_instrument__sync(self):
        counter: dict[str, float] = {'sample_func': 0}

        def sample_func():
            return sum(range(100))

        instrumented = cls._instrument(sample_func, counter)
        result = instrumented()

        assert result == sum(range(100))
        assert counter['sample_func'] >= 0

    @pyt.mark.asyncio
    async def test_instrument__async(self):
        counter: dict[str, float] = {'async_test': 0}

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
                lambda counter: ft.partial(ut.measure_context, counter=counter),
                id='partial_via_module_facade',
            ),
        ],
    )
    def test_measure_context__access(self, make_measure: Callable):
        """The context manager records elapsed time through both public access paths."""
        counter: dict[str, float] = {'blk': 0}
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
    def test_measure_context__counter(self, counter: dict[str, float]):
        """Seeded and unseeded counters both record elapsed time."""
        with cls.measure_context('blk', counter):
            time.sleep(0.01)

        assert counter['blk'] > 0

    def test_measure_context__exception(self):
        """Elapsed time is recorded when the measured block raises."""
        counter: dict[str, float] = {'blk': 0}

        def _sleep_then_raise() -> None:
            time.sleep(0.01)
            raise ValueError('boom')

        with pyt.raises(ValueError, match='boom'), cls.measure_context('blk', counter):
            _sleep_then_raise()

        assert counter['blk'] > 0

    # -------------------------------
    # `setup_logging`/`setup_fire_logging` decomposition helpers
    # -------------------------------
    @pyt.mark.parametrize(
        'fire_token, env_token, otlp_env, expected_token, should_raise',
        [
            ('explicit', None, None, 'explicit', False),
            ('', 'env-token', None, 'env-token', False),
            ('', None, 'http://127.0.0.1:4318', '', False),
            ('', None, None, '', True),
        ],
    )
    def test_resolve_fire_token(
        self,
        monkeypatch: pyt.MonkeyPatch,
        fire_token: str,
        env_token: str | None,
        otlp_env: str | None,
        expected_token: str,
        should_raise: bool,
    ):
        """`_resolve_fire_token` falls back to the env var and accepts OTLP as a destination."""
        monkeypatch.delenv('LOGFIRE_TOKEN', raising=False)
        monkeypatch.delenv('OTEL_EXPORTER_OTLP_ENDPOINT', raising=False)
        monkeypatch.delenv('OTEL_EXPORTER_OTLP_TRACES_ENDPOINT', raising=False)
        if env_token is not None:
            monkeypatch.setenv('LOGFIRE_TOKEN', env_token)
        if otlp_env is not None:
            monkeypatch.setenv('OTEL_EXPORTER_OTLP_ENDPOINT', otlp_env)

        if should_raise:
            with pyt.raises(ValueError, match='No telemetry destination configured'):
                cls._resolve_fire_token(fire_token)
        else:
            assert cls._resolve_fire_token(fire_token) == expected_token

    def test_resolve_setup_package__auto_detect(self, monkeypatch: pyt.MonkeyPatch):
        """`_resolve_setup_package` auto-detects when the caller passes an empty string."""
        detected: list[bool] = []
        monkeypatch.setattr(
            cls, 'get_package_name', classmethod(lambda c: detected.append(True) or 'auto-pkg')
        )
        assert cls._resolve_setup_package('') == 'auto-pkg'
        assert detected == [True]

    def test_resolve_setup_package__passthrough(self):
        """`_resolve_setup_package` returns the given name unchanged when non-empty."""
        assert cls._resolve_setup_package('my-explicit-pkg') == 'my-explicit-pkg'

    def test_try_fire_logging__success_marks_ready(self, monkeypatch: pyt.MonkeyPatch):
        """`_try_fire_logging` marks the package telemetry-ready on success."""
        logger = lg.getLogger('test-try-fire-success')
        original_ready = cls.TELEMETRY_READY
        cls.TELEMETRY_READY = set()
        monkeypatch.setattr(cls, 'setup_fire_logging', classmethod(lambda *a, **kw: None))
        try:
            result = cls._try_fire_logging(
                fire_token='tok',
                package='test-pkg',
                is_dev=False,
                logger=logger,
                app=None,
                export_logs=False,
                system_metrics=False,
                fire_kwargs={},
            )
            assert result is True
            assert 'test-pkg' in cls.TELEMETRY_READY
        finally:
            cls.TELEMETRY_READY = original_ready

    def test_try_fire_logging__failure_warns_and_returns_false(
        self, monkeypatch: pyt.MonkeyPatch, caplog: pyt.LogCaptureFixture
    ):
        """`_try_fire_logging` swallows failure, warns, and returns False without marking ready."""
        logger = lg.getLogger('test-try-fire-fail')
        original_ready = cls.TELEMETRY_READY
        cls.TELEMETRY_READY = set()

        def boom(**_: object) -> None:
            raise RuntimeError('exporter down')

        monkeypatch.setattr(cls, 'setup_fire_logging', classmethod(boom))
        try:
            with caplog.at_level(lg.WARNING):
                result = cls._try_fire_logging(
                    fire_token='tok',
                    package='test-pkg',
                    is_dev=False,
                    logger=logger,
                    app=None,
                    export_logs=False,
                    system_metrics=False,
                    fire_kwargs={},
                )
        finally:
            cls.TELEMETRY_READY = original_ready
        assert result is False
        assert 'test-pkg' not in cls.TELEMETRY_READY
        assert 'Remote telemetry setup failed' in caplog.text

    def test_configure_cached_logger__first_config_wins(self, caplog: pyt.LogCaptureFixture):
        """`_configure_cached_logger` warns and returns early when telemetry is already ready."""
        logger = lg.getLogger('test-cached-first-wins')
        original_loggers = cls.LOGGERS
        original_ready = cls.TELEMETRY_READY
        cls.LOGGERS = {'test-pkg': logger}
        cls.TELEMETRY_READY = {'test-pkg'}
        try:
            with caplog.at_level(lg.WARNING):
                result = cls._configure_cached_logger(
                    package='test-pkg',
                    fire_token='tok',
                    is_dev=False,
                    app=None,
                    export_logs=False,
                    system_metrics=False,
                    fire_kwargs={},
                )
        finally:
            cls.LOGGERS = original_loggers
            cls.TELEMETRY_READY = original_ready
        assert result is logger
        assert 'later setup options were not applied' in caplog.text

    def test_configure_cached_logger__retries_on_cached(self, monkeypatch: pyt.MonkeyPatch):
        """`_configure_cached_logger` retries fire setup when the package was not yet ready."""
        logger = lg.getLogger('test-cached-retry')
        original_loggers = cls.LOGGERS
        original_ready = cls.TELEMETRY_READY
        cls.LOGGERS = {'test-pkg': logger}
        cls.TELEMETRY_READY = set()
        fire_calls: list[bool] = []
        monkeypatch.setattr(
            cls, 'setup_fire_logging', classmethod(lambda *a, **kw: fire_calls.append(True))
        )
        try:
            result = cls._configure_cached_logger(
                package='test-pkg',
                fire_token='tok',
                is_dev=False,
                app=None,
                export_logs=False,
                system_metrics=False,
                fire_kwargs={},
            )
        finally:
            cls.LOGGERS = original_loggers
            cls.TELEMETRY_READY = original_ready
        assert result is logger
        assert fire_calls == [True]


############
### FASTAPI REGRESSION (LIBS-12)
############
class TestFastApiAppShape:
    """`setup_py_logging` and `_instrument_app` duck-type Flask vs. FastAPI app shapes.

    LIBS-12: `MetricUtils.setup_py_logging(app=...)` assumed a Flask-shaped ASGI app
    (`app.logger`, `app.config`), and `_instrument_app` assumed `app.asgi_app`. A real
    `FastAPI()` instance has neither `.logger` nor `.asgi_app` -- passing one raised
    `AttributeError: 'FastAPI' object has no attribute 'logger'`. These tests exercise a
    real `FastAPI()` instance (not a mock) so the regression is caught at the integration
    boundary, not just at the duck-type shim.
    """

    def test_setup_py_logging__fastapi_app_does_not_raise(self, tmp_path: Path):
        """`setup_py_logging(app=<a real FastAPI() instance>)` no longer raises AttributeError."""
        fastapi = pyt.importorskip('fastapi')
        app = fastapi.FastAPI()

        logger = lg.getLogger('test-fastapi-py-logging')
        logger.handlers.clear()
        result = cls.setup_py_logging(
            logdir=tmp_path,
            is_dev=True,
            package='test-fastapi-py-logging',
            logger=logger,
            app=app,
        )

        assert result is logger
        # The file handler was attached despite the app lacking `.logger`/`.config`.
        assert any(isinstance(h, lgh.RotatingFileHandler) for h in logger.handlers)

    def test_setup_py_logging__flask_shaped_app_still_attaches_handlers(self, tmp_path: Path):
        """Flask/Quart-shaped apps (with `.logger` and `.config`) keep their handlers."""
        flask_app = _FlaskShapedApp()

        logger = lg.getLogger('test-flask-py-logging')
        logger.handlers.clear()
        cls.setup_py_logging(
            logdir=tmp_path,
            is_dev=False,
            package='test-flask-py-logging',
            logger=logger,
            app=flask_app,
        )

        # The framework logger received our file handler.
        assert any(isinstance(h, lgh.RotatingFileHandler) for h in flask_app.logger.handlers)
        assert flask_app.config['DEBUG'] is False

    def test_instrument_app__fastapi_app_does_not_raise(self):
        """`_instrument_app` skips wrapping a FastAPI app (no `.asgi_app`) without error."""
        fastapi = pyt.importorskip('fastapi')
        app = fastapi.FastAPI()
        logger = lg.getLogger('test-fastapi-instrument')
        logger.handlers.clear()

        # instrument_asgi is monkeypatched to avoid requiring a live OTLP collector.
        instrumented: list[bool] = []
        monkey = pyt.MonkeyPatch()
        monkey.setattr(
            metric_module.fire, 'instrument_asgi', lambda asgi: instrumented.append(True) or asgi
        )
        try:
            cls._instrument_app(app, logger)
        finally:
            monkey.undo()

        # FastAPI is the ASGI callable itself (no `.asgi_app`), so it cannot be rewrapped.
        assert instrumented == []

    def test_instrument_app__flask_shaped_app_wraps_asgi(self):
        """Flask/Quart-shaped apps (with `.asgi_app`) are wrapped by `instrument_asgi`."""
        app = _FlaskShapedApp()
        logger = lg.getLogger('test-flask-instrument')
        logger.handlers.clear()

        instrumented: list[object] = []
        monkey = pyt.MonkeyPatch()
        monkey.setattr(
            metric_module.fire, 'instrument_asgi', lambda asgi: instrumented.append(asgi) or asgi
        )
        try:
            cls._instrument_app(app, logger)
        finally:
            monkey.undo()

        # The original asgi_app was wrapped (returned from instrument_asgi).
        assert instrumented == [app.asgi_app]


############
### FASTAPI REGRESSION HELPERS
############
class _FlaskShapedApp:
    """A minimal stand-in for Flask/Quart with `.logger`, `.config`, and `.asgi_app`."""

    def __init__(self) -> None:
        self.logger = lg.getLogger('test-flask-shaped-app')
        self.logger.handlers.clear()
        self.config: dict[str, object] = {}
        self.asgi_app = object()
