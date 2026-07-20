"""Smoke tests for the PEP 562 lazy facade in `my/__init__.py`.

`apis` and `files` are the only *leaf* subpackages, so `my/__init__.py` defers them to
first attribute access. These tests pin the two halves of that contract: bare `import my`
must not pull the leaves (verified in a fresh interpreter, since the in-process
`sys.modules` is already polluted by the rest of the suite), and the deferred names must
still resolve with the same identity, `__all__` membership, and `AttributeError` behavior
as the old eager imports.

Note -- the facade defers the `apis`/`files` import cost and `apis`'s import-time side
effects only. It does *not* remove the `logfire`/`pandas` tax from `MetricUtils` (that
lives in the eager `utils` subpackage; deferring it is a separate follow-up), so these
tests deliberately do not assert `logfire`/`pandas` absence.
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

    def test_bare_import_defers_apis_and_files(self):
        """A fresh `import my` leaves `my.apis` and `my.files` unimported."""
        proc = _probe(
            'import my, sys; '
            "assert 'my.apis' not in sys.modules, 'apis eagerly imported'; "
            "assert 'my.files' not in sys.modules, 'files eagerly imported'"
        )
        assert proc.returncode == 0, proc.stderr

    def test_bare_import_defers_googleapiclient(self):
        """A bare `import my` leaves `googleapiclient` (inside lazy `apis`) unimported."""
        proc = _probe(
            "import my, sys; assert 'googleapiclient' not in sys.modules, 'eagerly imported'"
        )
        assert proc.returncode == 0, proc.stderr

    def test_bare_import_defers_jinja2(self):
        """A bare `import my` does not build the infra Jinja env (so `jinja2` stays unimported)."""
        proc = _probe(
            "import my, sys; assert 'jinja2' not in sys.modules, 'jinja2 eagerly imported'"
        )
        assert proc.returncode == 0, proc.stderr

    def test_infra_jinja_loads_on_demand(self):
        """`my.infra.JINJA` still resolves, building `jinja2` only on that first access."""
        proc = _probe(
            'import my.infra as infra, sys; '
            "assert 'jinja2' not in sys.modules; "
            'assert type(infra.JINJA).__name__ == "Environment"; '
            "assert 'jinja2' in sys.modules, 'accessing JINJA did not load jinja2'"
        )
        assert proc.returncode == 0, proc.stderr

    def test_env_access_loads_apis_on_demand(self):
        """Touching `my.env` pulls `apis` in -- deferral, not removal."""
        proc = _probe(
            'import my, sys; '
            "assert 'my.apis' not in sys.modules; "
            '_ = my.env; '
            "assert 'my.apis' in sys.modules, 'accessing env did not load apis'"
        )
        assert proc.returncode == 0, proc.stderr

    def test_star_import_resolves_lazy_names(self):
        """`from my import *` still binds the lazy names (each triggers `__getattr__`)."""
        proc = _probe('from my import *; assert env is ENV; assert Markdown is not None')
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
