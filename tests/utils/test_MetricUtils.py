############
### HEAD ###
############
### STANDARD
from collections.abc import Callable
import functools as ft
import time

### EXTERNAL
import pytest as pyt

### INTERNAL
import my.utils as ut
from my.utils import MetricUtils

cls = MetricUtils


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
