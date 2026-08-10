"""Smoke tests for the PEP 562 lazy facade in `my/__init__.py`.

`apis` and `files` are the only *leaf* subpackages, so `my/__init__.py` defers them to
first attribute access. These tests pin the two halves of that contract: bare `import my`
must not pull the leaves (verified in a fresh interpreter, since the in-process
`sys.modules` is already polluted by the rest of the suite), and the deferred names must
still resolve with the same identity, `__all__` membership, and `AttributeError` behavior
as the old eager imports.

The facade also keeps `MetricUtils` and its optional Pandas/Logfire/OpenTelemetry stack cold
until a metrics method or class alias is requested. Basis constructs its own eager Pydantic
models with plugin discovery temporarily suppressed, then restores the ambient setting so
application models retain their installed plugin behavior.
"""

############
### HEAD ###
############
### STANDARD
import subprocess
import sys

### EXTERNAL
import pytest as pyt

### INTERNAL
import my


############
### BODY ###
############
#: The facade names `my/__init__.py` defers via its `__getattr__` (see `_LAZY_ATTRS`).
LAZY_NAMES = (
    'GoogleSheet',
    'Environment',
    'ENV',
    'env',
    'Filesystem',
    'PATHS',
    'FS',
    'fs',
    'Markdown',
)

#: Metrics modules that the ordinary utility facade must leave cold even when installed.
METRICS_MODULES = ('my.utils.MetricUtils', 'pandas', 'logfire', 'opentelemetry')


def _probe(body: str) -> subprocess.CompletedProcess:
    """Run `body` in a fresh interpreter so `sys.modules` reflects only what `import my` pulls."""
    return subprocess.run(
        [sys.executable, '-c', body],
        capture_output=True,
        text=True,
        timeout=60,
    )


class TestLazyFacadeDefersLeaves:
    """`import my` must not eagerly import the `apis`/`files` leaves."""

    @pyt.mark.parametrize(
        'module_names',
        [
            pyt.param(('my.apis', 'my.files'), id='leaf-packages'),
            pyt.param(('googleapiclient',), id='google-client'),
            pyt.param(('jinja2',), id='jinja'),
        ],
    )
    def test_bare_import__defers_modules(self, module_names: tuple[str, ...]):
        """A fresh `import my` leaves deferred modules unimported."""
        checks = '; '.join(
            f'assert {module_name!r} not in sys.modules, {module_name + " eagerly imported"!r}'
            for module_name in module_names
        )
        proc = _probe(f'import my, sys; {checks}')
        assert proc.returncode == 0, proc.stderr

    @pyt.mark.parametrize(
        'body',
        [
            pyt.param(
                'import my.infra as infra, sys; '
                "assert 'jinja2' not in sys.modules; "
                'assert type(infra.JINJA).__name__ == "Environment"; '
                "assert 'jinja2' in sys.modules, 'accessing JINJA did not load jinja2'",
                id='infra-jinja',
            ),
            pyt.param(
                'import my, sys; '
                "assert 'my.apis' not in sys.modules; "
                '_ = my.env; '
                "assert 'my.apis' in sys.modules, 'accessing env did not load apis'",
                id='facade-env',
            ),
        ],
    )
    def test_access__loads_on_demand(self, body: str):
        """Deferred modules load on the first access that needs them."""
        proc = _probe(body)
        assert proc.returncode == 0, proc.stderr

    def test_star_import_resolves_lazy_names(self):
        """`from my import *` still binds the lazy names (each triggers `__getattr__`)."""
        proc = _probe('from my import *; assert env is ENV; assert Markdown is not None')
        assert proc.returncode == 0, proc.stderr


class TestLazyFacadeDefersMetrics:
    """The ordinary utility facade must not initialize the optional metrics stack."""

    def test_all_extras_import__leaves_metrics_cold(self):
        """Installed metrics packages stay absent after the real consumer import."""
        checks = '; '.join(
            f'assert {module_name!r} not in sys.modules, {module_name + " eagerly imported"!r}'
            for module_name in METRICS_MODULES
        )
        proc = _probe(f'from my import ut; import sys; assert ut is not None; {checks}')
        assert proc.returncode == 0, proc.stderr

    def test_text_functions__preserve_identity_without_metrics(self):
        """Myform's canonical TextUtils functions retain their exact facade objects."""
        proc = _probe(
            'import sys; from my import ut; from my.utils.TextUtils import TextUtils; '
            'assert ut.multi_rgx is TextUtils.multi_rgx; '
            'assert ut.regex_dict is TextUtils.regex_dict; '
            "assert 'my.utils.MetricUtils' not in sys.modules"
        )
        assert proc.returncode == 0, proc.stderr

    def test_missing_attribute__does_not_warm_metrics(self):
        """A facade typo fails normally without turning into a metrics import request."""
        proc = _probe(
            'import sys; from my import ut; '
            "assert not hasattr(ut, 'does_not_exist'); "
            "assert 'my.utils.MetricUtils' not in sys.modules"
        )
        assert proc.returncode == 0, proc.stderr

    def test_base_environment__does_not_request_metrics_packages(self):
        """The utility facade works when every optional metrics import is unavailable."""
        proc = _probe(
            """
import importlib.abc
import sys

class BlockMetrics(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.partition('.')[0] in {'pandas', 'logfire', 'opentelemetry'}:
            raise ModuleNotFoundError(fullname)
        return None

sys.meta_path.insert(0, BlockMetrics())
from my import ut
assert ut.multi_rgx('cat', 'dog') == '(?:cat|dog)'
assert 'my.utils.MetricUtils' not in sys.modules
"""
        )
        assert proc.returncode == 0, proc.stderr

    def test_metric_access__loads_and_preserves_facade_aliases(self):
        """The first real metrics attribute resolves the historical class aliases on demand."""
        proc = _probe(
            """
import sys
from my import ut
assert 'my.utils.MetricUtils' not in sys.modules
setup_logging = ut.setup_logging
assert 'my.utils.MetricUtils' in sys.modules
assert all(name in sys.modules for name in ('pandas', 'logfire', 'opentelemetry'))
from my import MetricUtils, metric_utils
from my.utils import MetricUtils as PackageMetricUtils
assert MetricUtils is metric_utils is PackageMetricUtils
assert setup_logging is MetricUtils.setup_logging
assert 'setup_logging' in dir(ut)
"""
        )
        assert proc.returncode == 0, proc.stderr

    def test_direct_metric_module_import__preserves_package_class_alias(self):
        """Direct submodule-first imports cannot replace the package facade with a module."""
        proc = _probe(
            'from my.utils.MetricUtils import MetricUtils; '
            'from my.utils import MetricUtils as PackageMetricUtils; '
            'assert PackageMetricUtils is MetricUtils'
        )
        assert proc.returncode == 0, proc.stderr

    def test_metric_class_state__remains_live_through_facade(self):
        """Lazy constants retain the live inherited-state behavior of the old facade."""
        proc = _probe(
            'from my import MetricUtils, ut; '
            '_ = ut.METRICS_INSTALLED; '
            'MetricUtils.METRICS_INSTALLED = not MetricUtils.METRICS_INSTALLED; '
            'assert ut.METRICS_INSTALLED is MetricUtils.METRICS_INSTALLED'
        )
        assert proc.returncode == 0, proc.stderr

    def test_pydantic_plugin__remains_available_to_application_models(self):
        """Cold Basis models do not globally disable the installed Pydantic plugin surface."""
        proc = _probe(
            """
import os
import sys
os.environ.pop('PYDANTIC_DISABLE_PLUGINS', None)
import my
assert 'logfire' not in sys.modules
assert 'PYDANTIC_DISABLE_PLUGINS' not in os.environ
import pydantic as pyd
class ApplicationModel(pyd.BaseModel):
    value: int
assert 'logfire.integrations.pydantic' in sys.modules
"""
        )
        assert proc.returncode == 0, proc.stderr

    def test_pydantic_plugin_setting__restores_caller_value(self):
        """A caller's existing plugin selection survives the cold Basis import byte-for-byte."""
        proc = _probe(
            "import os; os.environ['PYDANTIC_DISABLE_PLUGINS'] = 'caller-plugin'; "
            'import my; '
            "assert os.environ['PYDANTIC_DISABLE_PLUGINS'] == 'caller-plugin'"
        )
        assert proc.returncode == 0, proc.stderr


class TestLazyFacadeContract:
    """Deferred names must resolve with the same identity and errors as eager imports."""

    @pyt.mark.parametrize('name', LAZY_NAMES)
    def test_lazy_name_resolves(self, name: str):
        """Every deferred name is reachable via attribute access."""
        assert getattr(my, name) is not None

    @pyt.mark.parametrize('name', LAZY_NAMES)
    def test_lazy_name_still_in_all(self, name: str):
        """Every deferred name is still advertised in `__all__`."""
        assert name in my.__all__

    def test_singleton_identity_preserved(self):
        """The `env = ENV` / `fs = FS = PATHS` aliasing survives one lazy `apis` import."""
        from my import ENV, FS, PATHS, env, fs

        assert env is ENV
        assert fs is FS is PATHS

    def test_missing_attribute_raises(self):
        """A genuinely-absent name raises `AttributeError` (module dunder probes rely on this)."""
        with pyt.raises(AttributeError):
            getattr(my, 'does_not_exist')

    def test_dir_lists_full_facade(self):
        """`dir(my)` surfaces the whole public facade, lazy names included."""
        assert set(LAZY_NAMES) <= set(dir(my))
