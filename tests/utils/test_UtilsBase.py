############
### HEAD ###
############
### STANDARD
import json
import subprocess
import sys
import types

### EXTERNAL
import pytest as pyt

### INTERNAL
from my.utils._UtilsBase import _UtilsBase

############
### DATA ###
############
cls = _UtilsBase

#: Optional-extra stacks that no serializer should drag in. Logfire and OpenTelemetry are not
#: listed: Pydantic's plugin discovery wakes them for any `my.typing` import, `ty`-first included.
HEAVY_MODULES = ('pandas', 'aiohttp', 'googleapiclient', 'my.utils.MetricUtils', 'my.apis')

#: Child-process harness: import ONLY `ut`, run one call, then report what the call did.
#: `call` is a public `ut` expression whose JSON-friendly result the parent compares.
ONLY_UT = """
import json, sys
from my import ut
cold = 'my.typing' not in sys.modules
result = {call}
print(json.dumps({{
    'cold': cold,
    'warm': 'my.typing' in sys.modules,
    'heavy': [m for m in {heavy!r} if m in sys.modules],
    'result': result,
}}))
"""


def _child(source: str) -> dict:
    """Run `source` in a fresh interpreter and parse its single JSON line."""
    proc = subprocess.run(
        [sys.executable, '-c', source],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout.strip().splitlines()[-1])


############
### BODY ###
############
class TestUtilsBase:
    # -------------------
    # `+` Primary Methods
    # -------------------
    @pyt.mark.parametrize(
        'call, expected',
        [
            pyt.param('ut.serialize({"a": {3, 1}})', {'a': [1, 3]}, id='serialize'),
            pyt.param('ut.to_json({"a": 1}, wrap=False)', '{\n    "a":1\n}', id='to_json'),
            pyt.param('ut.to_yaml({"a": 1})', 'a: 1\n', id='to_yaml'),
            pyt.param('ut.to_toml({"a": 1})', 'a = 1\n', id='to_toml'),
            pyt.param('ut.normalize({"a": (1, 2)})', {'a': [1, 2]}, id='normalize'),
        ],
    )
    def test_ut_only_import__first_call_initializes_typist(self, call: str, expected: object):
        """Importing only `ut` is enough: the first call that needs `ty` loads it itself."""
        out = _child(ONLY_UT.format(call=call, heavy=HEAVY_MODULES))
        assert out['result'] == expected
        assert out['cold'], '`import my` must not import `my.typing` eagerly'
        assert out['warm'], 'the call should have loaded `my.typing` itself'
        assert out['heavy'] == [], 'a serializer must not import optional extras'

    def test_ut_only_import__stays_cold_until_a_typed_call(self):
        """A call that needs no `ty` leaves `my.typing` unimported, so cold start is unchanged."""
        out = _child(ONLY_UT.format(call='ut.clean_string("  a  b ")', heavy=HEAVY_MODULES))
        assert out['cold']
        assert not out['warm']

    @pyt.mark.parametrize('first', ['ut', 'ty'])
    def test_import_order__does_not_change_the_result(self, first: str):
        """`ut`-first and `ty`-first interpreters agree, and share one Typist instance."""
        imports = {'ut': 'from my import ut, ty', 'ty': 'from my import ty, ut'}[first]
        out = _child(
            f"""
import json
{imports}
print(json.dumps({{
    'json': ut.to_json({{'a': [1, 2], 'b': {{'c': 3}}}}),
    'same': ut.typist() is ty,
}}))
"""
        )
        assert out['same'] is True
        assert json.loads(out['json']) == {'a': [1, 2], 'b': {'c': 3}}

    def test_typist__is_stable_after_first_use(self):
        """Repeated reads return the one installed instance."""
        assert cls.typist() is cls.typist()
        assert cls.typist() is cls.ty

    def test_typist__does_not_recurse_while_typing_is_initializing(
        self, monkeypatch: pyt.MonkeyPatch
    ):
        """If `my.typing` has not installed itself yet, fail plainly instead of looping."""
        module = sys.modules[cls.__module__]
        imported: list[str] = []

        def import_module(name: str, package: str | None = None) -> None:
            imported.append(name)

        monkeypatch.delattr(cls, 'ty', raising=False)
        monkeypatch.setattr(module, 'importlib', types.SimpleNamespace(import_module=import_module))

        with pyt.raises(AttributeError, match='initializ'):
            cls.typist()
        assert imported == ['..typing']
