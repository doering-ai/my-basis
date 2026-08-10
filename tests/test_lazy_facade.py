"""Smoke tests for the PEP 562 lazy facade in `my/__init__.py`.

Pydantic-backed facade branches and optional leaves are deferred to first attribute
access. These tests pin the two halves of that contract: bare `import my` must not pull
them (verified in a fresh interpreter, since the in-process `sys.modules` is already
polluted by the rest of the suite), and the deferred names must still resolve with the
same identity, `__all__` membership, and `AttributeError` behavior as the old eager
imports.

The facade also keeps `MetricUtils` and its optional Pandas/Logfire/OpenTelemetry stack cold
until a metrics method or class alias is requested. The cold facade does not mutate
Pydantic's process-global plugin setting, so application models retain their installed
plugin behavior.
"""

############
### HEAD ###
############
### STANDARD
import importlib
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
LAZY_NAMES = tuple(my._LAZY_ATTRS)

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

    def test_infra_paths__model_construct_populates_defaults(self):
        """Unvalidated construction retains every static path default used by consumers."""
        proc = _probe(
            'from my.infra import INFRA_PATHS; '
            'assert set(INFRA_PATHS.__dict__) == {"my", "data", "templates"}; '
            'assert INFRA_PATHS.templates == INFRA_PATHS.data / "templates"; '
            'assert (INFRA_PATHS.data / "importas.yaml").is_file()'
        )
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

    def test_metric_surface__resolves_to_guarded_api_without_extras(self):
        """Advertised metric names resolve while calls fail with the documented guard."""
        proc = _probe(
            """
import importlib.abc
import sys

class BlockMetrics(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.partition(".")[0] in {"pandas", "logfire", "opentelemetry"}:
            raise ModuleNotFoundError(fullname)
        return None

sys.meta_path.insert(0, BlockMetrics())
from my import MetricUtils, ut
assert "setup_logging" in dir(ut)
assert ut.setup_logging is MetricUtils.setup_logging
assert MetricUtils.METRICS_INSTALLED is False
try:
    ut.setup_logging()
except ImportError as exc:
    assert "optional [metrics] extra" in str(exc)
else:
    raise AssertionError("metrics guard accepted missing extras")
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
assert ut.setup_metrics.__self__ is ut
assert ut.setup_metrics.__func__ is MetricUtils.setup_metrics.__func__
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

    def test_warm_metric_module_import__preserves_package_class_alias(self):
        """A direct module import after facade activation cannot split package identity."""
        proc = _probe(
            """
import importlib
from my import ut
_ = ut.setup_logging
import my.utils.MetricUtils
package = importlib.import_module("my.utils")
module = importlib.import_module("my.utils.MetricUtils")
assert package.MetricUtils is module.MetricUtils
assert ut.setup_logging is module.MetricUtils.setup_logging
"""
        )
        assert proc.returncode == 0, proc.stderr

    def test_metric_first_access__is_thread_safe(self):
        """Concurrent first reads converge on one imported method and class identity."""
        proc = _probe(
            """
from concurrent.futures import ThreadPoolExecutor
import sys
from my import ut
assert "my.utils.MetricUtils" not in sys.modules
with ThreadPoolExecutor(max_workers=16) as pool:
    methods = list(pool.map(lambda _: ut.setup_logging, range(64)))
assert len({id(method) for method in methods}) == 1
from my import MetricUtils, metric_utils
assert methods[0] is MetricUtils.setup_logging
assert metric_utils is MetricUtils
"""
        )
        assert proc.returncode == 0, proc.stderr

    def test_metric_manifest__matches_concrete_public_surface(self):
        """A new public MetricUtils member requires an explicit lazy-facade decision."""
        proc = _probe(
            """
import importlib
package = importlib.import_module("my.utils")
metric_cls = package.MetricUtils
owned_public = {name for name in metric_cls.__dict__ if not name.startswith("_")}
assert package._METRIC_FACADE_ATTRS == owned_public
"""
        )
        assert proc.returncode == 0, proc.stderr

    def test_metrics_aliases__remain_visible_in_package_dir(self):
        """Package introspection advertises lazy aliases before their first access."""
        proc = _probe(
            'import importlib, sys; package = importlib.import_module("my.utils"); '
            'assert "my.utils.MetricUtils" not in sys.modules; '
            'assert {"MetricUtils", "metric_utils"} <= set(dir(package)); '
            'assert "my.utils.MetricUtils" not in sys.modules'
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

    def test_metric_method_rebind__remains_live_through_facade(self):
        """A later MetricUtils method replacement remains visible through `ut`."""
        proc = _probe(
            'from my import MetricUtils, ut; '
            '_ = ut.setup_logging; '
            'replacement = lambda: "replacement"; '
            'MetricUtils.setup_logging = staticmethod(replacement); '
            'assert ut.setup_logging is replacement; '
            'assert ut.setup_logging() == "replacement"'
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

    def test_pydantic_plugin_setting__never_leaks_to_child_process(self):
        """A child spawned mid-import never inherits a plugin-suppression sentinel."""
        proc = _probe(
            """
import importlib.abc
import os
import subprocess
import sys

os.environ.pop('PYDANTIC_DISABLE_PLUGINS', None)

class ObserveSetting(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == 'my.utils':
            sys.meta_path.remove(self)
            child = subprocess.run(
                [sys.executable, '-c',
                 "import os; assert 'PYDANTIC_DISABLE_PLUGINS' not in os.environ"],
                capture_output=True,
                text=True,
            )
            assert child.returncode == 0, child.stderr
        return None

sys.meta_path.insert(0, ObserveSetting())
import my
assert 'PYDANTIC_DISABLE_PLUGINS' not in os.environ
"""
        )
        assert proc.returncode == 0, proc.stderr


class TestLazyFacadeContract:
    """Deferred names must resolve with the same identity and errors as eager imports."""

    @pyt.mark.parametrize('name', LAZY_NAMES)
    def test_lazy_name_resolves(self, name: str):
        """Every deferred name is reachable via attribute access."""
        assert getattr(my, name) is not None

    @pyt.mark.parametrize('name,module_name', my._LAZY_ATTRS.items())
    def test_lazy_name_preserves_source_identity(self, name: str, module_name: str):
        """Every deferred facade value is the exact object exported by its source module."""
        source_module = importlib.import_module(module_name)
        assert getattr(my, name) is getattr(source_module, name)

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
