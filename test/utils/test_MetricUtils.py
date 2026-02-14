############
### HEAD ###
############
### STANDARD

### EXTERNAL
import pytest as pyt

### INTERNAL
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
