"""Smoke tests for the PEP 562 lazy facade in `my/__init__.py`.

Pydantic-backed facade branches and optional leaves are deferred to first attribute
access. These tests pin the two halves of that contract: bare `import my` must not pull
them (verified in a fresh interpreter, since the in-process `sys.modules` is already
polluted by the rest of the suite), and the deferred names must still resolve with the
same identity, `__all__` membership, and `AttributeError` behavior as the old eager
imports.

The facade also keeps `MetricUtils` and its optional Pandas/Logfire/OpenTelemetry stack cold
through class aliases, method reads, and inspection; the implementation loads when a method is
called or its submodule is explicitly imported. The cold facade does not mutate Pydantic's
process-global plugin setting, so application models retain their installed plugin behavior.
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

    def test_infra_paths__rejects_mutation(self):
        """The frozen model blocks the one path unvalidated data could enter through."""
        proc = _probe(
            """
from pathlib import Path
import pydantic as pyd
from my.infra import INFRA_PATHS
try:
    INFRA_PATHS.my = Path("/tmp")
except pyd.ValidationError:
    pass
else:
    raise AssertionError("INFRA_PATHS accepted mutation")
assert INFRA_PATHS.my != Path("/tmp")
"""
        )
        assert proc.returncode == 0, proc.stderr

    def test_star_import_resolves_lazy_names(self):
        """`from my import *` still binds the lazy names (each triggers `__getattr__`)."""
        proc = _probe('from my import *; assert env is ENV; assert Markdown is not None')
        assert proc.returncode == 0, proc.stderr

    def test_pydantic_branches__wake_installed_logfire_plugin_on_import(self):
        """The deferred branches define Pydantic models at import, waking installed plugins.

        This is why `caches`/`typing`/`types`/`regex` stay lazy alongside the metrics
        leaves: making them eager again would re-import Logfire at `import my` and break
        this card's cold-start acceptance criterion.
        """
        proc = _probe(
            "import sys; import my.caches; assert 'logfire.integrations.pydantic' in sys.modules"
        )
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

    def test_missing_attribute__stays_plain_error_when_metrics_warm(self):
        """A typo after a direct implementation import is still a plain AttributeError."""
        proc = _probe(
            'from my import ut; '
            'import my.utils.MetricUtils; '
            "assert not hasattr(ut, 'does_not_exist'); "
            "assert not hasattr(ut, '_does_not_exist')"
        )
        assert proc.returncode == 0, proc.stderr

    def test_metric_dir__is_identical_cold_and_warm(self):
        """`dir(ut)` advertises the same public surface before and after metrics activation."""
        proc = _probe(
            'from my import ut; '
            'cold = [name for name in dir(ut) if not name.startswith("_")]; '
            'assert "setup_logging" in cold; '
            'assert all(hasattr(ut, name) for name in cold); '
            'ut.get_package_name(); '
            'assert [name for name in dir(ut) if not name.startswith("_")] == cold'
        )
        assert proc.returncode == 0, proc.stderr

    def test_metric_classmethod__binds_the_requesting_class(self):
        """Cold wrappers forward the exact class they were invoked on, as inheritance did."""
        proc = _probe(
            """
import importlib
import sys

from my import ut

package = importlib.import_module("my.utils")
seen = []
def spy(name, owner, *args, **kwargs):
    seen.append((name, owner))
    return "ok"
package._call_metric_method = spy

class CustomUtils(ut):
    pass

assert ut.setup_metrics.__self__ is ut
assert CustomUtils.get_package_name() == "ok"
assert seen[-1] == ("get_package_name", CustomUtils)
assert ut.get_package_name() == "ok"
assert seen[-1] == ("get_package_name", ut)
assert "my.utils.MetricUtils" not in sys.modules
"""
        )
        assert proc.returncode == 0, proc.stderr

    def test_metric_private_helpers__resolve_only_after_activation(self):
        """Cold private probes fail plainly without warming; warm ones resolve via the facade."""
        proc = _probe(
            """
import sys
from my import MetricUtils
assert not hasattr(MetricUtils, "_guard")
assert "my.utils.MetricUtils" not in sys.modules
MetricUtils.get_package_name()
assert MetricUtils._guard is not None
"""
        )
        assert proc.returncode == 0, proc.stderr

    def test_star_import__leaves_metrics_stack_cold(self):
        """`from my import *` binds the cold metric facade without its optional dependencies."""
        proc = _probe(
            'from my import *; import sys; '
            'assert MetricUtils is metric_utils; '
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
from pathlib import Path
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
    ut.setup_logging(Path("."), False, "")
except ImportError as exc:
    assert "optional [metrics] extra" in str(exc)
else:
    raise AssertionError("metrics guard accepted missing extras")
"""
        )
        assert proc.returncode == 0, proc.stderr

    def test_metric_method_read__stays_cold_and_preserves_facade_aliases(self):
        """Reading a metrics method returns its canonical wrapper without warming dependencies."""
        proc = _probe(
            """
import sys
from my import MetricUtils, metric_utils, ut
from my.utils import MetricUtils as PackageMetricUtils
assert 'my.utils.MetricUtils' not in sys.modules
setup_logging = ut.setup_logging
assert 'my.utils.MetricUtils' not in sys.modules
assert all(name not in sys.modules for name in ('pandas', 'logfire', 'opentelemetry'))
assert MetricUtils is metric_utils is PackageMetricUtils
assert setup_logging is MetricUtils.setup_logging
assert ut.setup_metrics.__self__ is ut
assert ut.setup_metrics.__func__ is MetricUtils.setup_metrics.__func__
assert 'setup_logging' in dir(ut)
assert ut.get_package_name() == 'my-basis'
assert 'my.utils.MetricUtils' in sys.modules
assert all(name in sys.modules for name in ('pandas', 'logfire', 'opentelemetry'))
"""
        )
        assert proc.returncode == 0, proc.stderr

    def test_metric_static_inspection__preserves_descriptor_without_warming(self):
        """Static inspection sees the inherited descriptor while metrics remain cold."""
        proc = _probe(
            'import inspect, sys; from my import Utils; '
            'descriptor = inspect.getattr_static(Utils, "setup_logging"); '
            'assert isinstance(descriptor, staticmethod); '
            'assert descriptor.__func__.__name__ == "setup_logging"; '
            'assert tuple(inspect.signature(descriptor).parameters)[:3] '
            '== ("logdir", "is_dev", "fire_token"); '
            'assert "my.utils.MetricUtils" not in sys.modules'
        )
        assert proc.returncode == 0, proc.stderr

    def test_metric_first_classification__is_complete_truthful_and_cold(self):
        """One cold class inventory reports the live base and every descriptor kind."""
        proc = _probe(
            """
import inspect
import sys
from my import MetricUtils, Utils

assert "my.utils.MetricUtils" not in sys.modules
assert MetricUtils in Utils.__mro__
attrs = {item.name: item for item in inspect.classify_class_attrs(Utils)}
assert "my.utils.MetricUtils" not in sys.modules
assert all(name not in sys.modules for name in ("pandas", "logfire", "opentelemetry"))

#: The cold class explicitly defines its full public surface -- no manifest to consult.
metric_public = {name for name in vars(MetricUtils) if not name.startswith("_")}
assert "setup_logging" in metric_public
for name in metric_public:
    item = attrs[name]
    assert item.defining_class is MetricUtils
    descriptor = inspect.getattr_static(MetricUtils, name)
    if isinstance(descriptor, staticmethod):
        assert item.kind == "static method"
        assert isinstance(item.object, staticmethod)
        assert item.object.__func__.__name__ == name
    elif isinstance(descriptor, classmethod):
        assert item.kind == "class method"
        assert isinstance(item.object, classmethod)
        assert item.object.__func__.__name__ == name
    else:
        assert item.kind == "data"

static_signature = inspect.signature(attrs["setup_logging"].object)
assert tuple(static_signature.parameters)[:3] == ("logdir", "is_dev", "fire_token")
assert static_signature.parameters["fire_kwargs"].kind is inspect.Parameter.VAR_KEYWORD

class_signature = inspect.signature(attrs["setup_metrics"].object.__func__)
assert tuple(class_signature.parameters) == ("cls", "metrics", "logger")
"""
        )
        assert proc.returncode == 0, proc.stderr

    def test_metric_super__uses_canonical_cold_runtime_base(self):
        """Subclass delegation through super returns the real cold wrapper and keeps inheritance."""
        proc = _probe(
            """
import inspect
import sys
from my import MetricUtils, Utils

class CustomUtils(Utils):
    @classmethod
    def metric_via_super(cls):
        return super().setup_logging

assert "my.utils.MetricUtils" not in sys.modules
setup_logging = CustomUtils.metric_via_super()
assert "my.utils.MetricUtils" not in sys.modules
assert issubclass(Utils, MetricUtils)
descriptor = inspect.getattr_static(Utils, "setup_logging")
assert descriptor is inspect.getattr_static(MetricUtils, "setup_logging")
assert isinstance(descriptor, staticmethod)
classified = next(
    item for item in inspect.classify_class_attrs(Utils) if item.name == "setup_logging"
)
assert classified.kind == "static method"
assert classified.defining_class is MetricUtils
assert setup_logging is MetricUtils.setup_logging
"""
        )
        assert proc.returncode == 0, proc.stderr

    def test_direct_metric_module_import__preserves_package_class_alias(self):
        """Direct submodule-first imports restore inheritance without splitting aliases."""
        proc = _probe(
            'import inspect; '
            'from my import Utils; '
            'from my.utils.MetricUtils import MetricUtils; '
            'from my.utils import MetricUtils as PackageMetricUtils; '
            'assert PackageMetricUtils is MetricUtils; '
            'assert issubclass(Utils, MetricUtils); '
            'assert isinstance(inspect.getattr_static(Utils, "setup_logging"), staticmethod)'
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
        """Concurrent cold reads and classifications converge without warming or stale metadata."""
        proc = _probe(
            """
from concurrent.futures import ThreadPoolExecutor
import inspect
import sys
from my import MetricUtils, Utils, metric_utils, ut

def inspect_once(index):
    if index % 2:
        return ut.setup_logging
    attrs = {item.name: item for item in inspect.classify_class_attrs(Utils)}
    item = attrs["setup_logging"]
    assert item.defining_class is MetricUtils
    assert item.object.__func__.__name__ == "setup_logging"
    return item.object.__func__

assert "my.utils.MetricUtils" not in sys.modules
with ThreadPoolExecutor(max_workers=16) as pool:
    methods = list(pool.map(inspect_once, range(128)))
assert len({id(method) for method in methods}) == 1
assert methods[0] is MetricUtils.setup_logging
assert metric_utils is MetricUtils
assert "my.utils.MetricUtils" not in sys.modules
assert all(name not in sys.modules for name in ("pandas", "logfire", "opentelemetry"))
"""
        )
        assert proc.returncode == 0, proc.stderr

    def test_metric_first_call__is_thread_safe(self):
        """Concurrent first calls share one implementation import and stable public aliases."""
        proc = _probe(
            """
from concurrent.futures import ThreadPoolExecutor
import importlib
import sys
from my import MetricUtils, metric_utils, ut

assert "my.utils.MetricUtils" not in sys.modules
with ThreadPoolExecutor(max_workers=16) as pool:
    results = list(pool.map(lambda _: ut.setup_warnings(), range(64)))
assert results == [None] * 64
module = importlib.import_module("my.utils.MetricUtils")
assert module.MetricUtils is MetricUtils is metric_utils
assert MetricUtils.WARNINGS_SETUP is True
assert ut.setup_warnings is MetricUtils.setup_warnings
"""
        )
        assert proc.returncode == 0, proc.stderr

    def test_metric_alias__never_exposes_module_under_concurrent_loads(self):
        """No interleaving of direct and facade-triggered loads can expose the submodule."""
        proc = _probe(
            """
from concurrent.futures import ThreadPoolExecutor
import importlib
import threading
import time

package = importlib.import_module("my.utils")
metric_cls = package.MetricUtils
stop = threading.Event()
violations = []

def watch():
    while not stop.is_set():
        if package.__dict__["MetricUtils"] is not metric_cls:
            violations.append(package.__dict__["MetricUtils"])
        time.sleep(0.001)

def hammer(index):
    if index % 2:
        importlib.import_module("my.utils.MetricUtils")
    else:
        metric_cls.get_package_name()

watcher = threading.Thread(target=watch)
watcher.start()
try:
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(hammer, range(32)))
finally:
    stop.set()
    watcher.join(5)

assert not violations, violations
assert package.__dict__["MetricUtils"] is metric_cls
assert package.__dict__["metric_utils"] is metric_cls
from my.utils import MetricUtils as via_package
assert via_package is metric_cls
"""
        )
        assert proc.returncode == 0, proc.stderr

    def test_metric_first_call__recovers_after_interrupted_load(self):
        """A failed first implementation import leaves no residue; the retry fully succeeds."""
        proc = _probe(
            """
import importlib.abc
import importlib.util
import sys

from my import MetricUtils

class KillFirstLoad(importlib.abc.MetaPathFinder):
    done = False

    def find_spec(self, fullname, path=None, target=None):
        if fullname != "my.utils.MetricUtils" or self.done:
            return None
        self.done = True
        sys.meta_path.remove(self)
        try:
            spec = importlib.util.find_spec(fullname)
        finally:
            sys.meta_path.insert(0, self)
        def interrupt(module):
            raise KeyboardInterrupt("simulated mid-load interruption")
        spec.loader.exec_module = interrupt
        return spec

sys.meta_path.insert(0, KillFirstLoad())
try:
    MetricUtils.get_package_name()
except KeyboardInterrupt:
    pass
else:
    raise AssertionError("first load was not interrupted")

assert "my.utils.MetricUtils" not in sys.modules
assert MetricUtils.get_package_name() == "my-basis"
counter = {}
with MetricUtils.measure_context("step", counter):
    pass
assert counter["step"] > 0
"""
        )
        assert proc.returncode == 0, proc.stderr

    def test_metric_cold_surface__mirrors_implementation(self):
        """The cold class exposes the implementation's exact public names, kinds, and signatures."""
        proc = _probe(
            """
import importlib
import inspect

package = importlib.import_module("my.utils")
metric_cls = package.MetricUtils
module = importlib.import_module("my.utils.MetricUtils")
implementation = module._MetricUtilsImplementation

cold_public = {name for name in vars(metric_cls) if not name.startswith("_")}
impl_public = {name for name in vars(implementation) if not name.startswith("_")}
assert cold_public == impl_public

for name in cold_public:
    public = inspect.getattr_static(metric_cls, name)
    concrete = inspect.getattr_static(implementation, name)
    assert type(public) is type(concrete), name
    if isinstance(public, (staticmethod, classmethod)):
        assert public.__func__.__name__ == concrete.__func__.__name__ == name
        assert inspect.signature(public.__func__) == inspect.signature(concrete.__func__), name

impl_private = {
    name
    for name in vars(implementation)
    if name.startswith("_") and not (name.startswith("__") and name.endswith("__"))
}
assert impl_private
for name in impl_private:
    assert getattr(metric_cls, name) is not None, name
"""
        )
        assert proc.returncode == 0, proc.stderr

    def test_metric_reflection__keeps_cold_source_and_full_public_docs(self):
        """Reflection stays truthful and documented on both sides of metrics activation."""
        proc = _probe(
            """
import importlib
import inspect
import sys

package = importlib.import_module("my.utils")
metric_cls = package.MetricUtils
assert "my.utils.MetricUtils" not in sys.modules
assert inspect.getmodule(metric_cls) is package
assert f"{metric_cls.__module__}.{metric_cls.__qualname__}" == (
    "my.utils.MetricUtils.MetricUtils"
)
cold_source = inspect.getsource(metric_cls)
assert "class MetricUtils(" in cold_source
assert "def setup_logging(" in cold_source
setup_doc = inspect.getdoc(metric_cls.setup_logging)
assert setup_doc is not None and len(setup_doc) > 1_000
assert "fire_token: Logfire API token" in setup_doc
assert "Returns:" in setup_doc
assert "Examples:" in setup_doc
assert "my.utils.MetricUtils" not in sys.modules

importlib.import_module("my.utils.MetricUtils")
assert inspect.getmodule(metric_cls) is package
assert inspect.getsource(metric_cls) == cold_source
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

    def test_metric_class_state__preserves_rebinding_across_first_load(self):
        """A caller's cold availability override remains authoritative after activation."""
        proc = _probe(
            """
from my import MetricUtils

MetricUtils.METRICS_INSTALLED = False
try:
    MetricUtils.setup_warnings()
except ImportError as exc:
    assert "optional [metrics] extra" in str(exc)
else:
    raise AssertionError("first implementation load discarded the public override")
assert MetricUtils.METRICS_INSTALLED is False
assert MetricUtils.WARNINGS_SETUP is False
"""
        )
        assert proc.returncode == 0, proc.stderr

    def test_metric_public_data__preserves_stdlib_pattern_type(self):
        """The cold telemetry identity pattern retains its historical concrete type."""
        proc = _probe(
            """
import re
from my import MetricUtils

assert isinstance(MetricUtils.TELEMETRY_IDENTITY, re.Pattern)
MetricUtils.get_package_name()
assert isinstance(MetricUtils.TELEMETRY_IDENTITY, re.Pattern)
"""
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


#: Channel-gap dependencies: declared in `pyproject.toml`, but imported lazily (via
#: `_UtilsBase._optional_import()`) so bare `import my` never requires them. Not optional
#: extras -- see LIBS-62 and `SUBL-32` harness/libs.md #2c for why a plugin host that
#: provisions Python packages outside `uv`/PyPI needs `import my` to succeed without them.
CHANNEL_GAP_MODULES = ('srsly', 'tomli_w', 'unidecode')


class TestLazyFacadeDefersChannelGapDependencies:
    """`import my` must not require `srsly`, `tomli_w`, or `unidecode`.

    These three are ordinary, unconditional `my-basis` dependencies -- not optional extras --
    but Sublime Text's ST 4213 plugin host (Python 3.14) provisions packages into its own
    `Lib/python314` directory outside `uv`/PyPI, and the Package Control channel does not yet
    carry them for 3.14. Deferring their imports past `import my` lets the host load `my` at
    all; only the methods that actually need them (YAML/JSON/TOML serialization, `srsly`'s
    dumps; `clean_string`'s transliteration, `unidecode`) still require them installed, and do
    so with a clear, greppable `ImportError` instead of a bare `ModuleNotFoundError`.
    """

    def test_bare_import__succeeds_with_channel_gap_modules_blocked(self):
        """A fresh `import my` succeeds even when `srsly`/`tomli_w`/`unidecode` are absent."""
        proc = _probe(
            f"""
import importlib.abc
import sys

class BlockChannelGap(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.partition('.')[0] in {CHANNEL_GAP_MODULES!r}:
            raise ModuleNotFoundError(fullname)
        return None

sys.meta_path.insert(0, BlockChannelGap())
import my
for name in {CHANNEL_GAP_MODULES!r}:
    assert name not in sys.modules, f'{{name}} eagerly imported'
assert my.ut.multi_rgx('cat', 'dog') == '(?:cat|dog)'
"""
        )
        assert proc.returncode == 0, proc.stderr

    def test_call_without_dependency__raises_clear_import_error(self):
        """Calling a guarded method without its dependency names the missing library plainly.

        One probe, sequenced deliberately, rather than three independently-blocked ones:
        `to_yaml`/`to_json`/`from_json`/`from_yaml`/`to_toml` all route through the shared
        `Typist` (`cls.ty`), which is only populated by importing `my.typing` -- and
        `my.typing` transitively imports `my.caches.FileCache`, which itself eagerly imports
        `srsly` (already lazy relative to bare `import my`, per LIBS-62 step 1, but not
        relative to `my.typing`). So `ut.ty` is primed first, with `srsly` genuinely
        importable, then `sys.modules['srsly'] = None` re-blocks it -- overriding the now-
        cached real module -- immediately before exercising the srsly-guarded calls. A
        `None` entry makes any subsequent `import <name>` (including a submodule import,
        since Python must first successfully import the parent) raise `ImportError`.
        """
        proc = _probe(
            """
import sys

for name in ('srsly', 'tomli_w', 'unidecode'):
    sys.modules[name] = None

import my
assert my.ut.multi_rgx('cat', 'dog') == '(?:cat|dog)'

# `clean_string` needs `unidecode` and touches no `Typist` state.
try:
    my.ut.clean_string('Cafe')
except ImportError as exc:
    assert 'unidecode' in str(exc)
else:
    raise AssertionError('clean_string did not raise without unidecode')

# Populate `ut.ty` via a real import; `tomli_w`/`unidecode` stay blocked throughout.
del sys.modules['srsly']
import my.typing
assert my.ut.ty is not None

# `to_toml` needs `tomli_w`.
try:
    my.ut.to_toml({'a': 1})
except ImportError as exc:
    assert 'tomli_w' in str(exc)
else:
    raise AssertionError('to_toml did not raise without tomli_w')

# Re-block `srsly` to exercise its own guarded call sites.
sys.modules['srsly'] = None
calls = (
    lambda: my.ut.to_yaml({'a': 1}),
    lambda: my.ut.to_json({'a': 1}),
    lambda: my.ut.from_json('{"a": 1}'),
    lambda: my.ut.from_yaml('a: 1'),
)
for call in calls:
    try:
        call()
    except ImportError as exc:
        assert 'srsly' in str(exc)
    else:
        raise AssertionError('a srsly-backed call did not raise without srsly')
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
