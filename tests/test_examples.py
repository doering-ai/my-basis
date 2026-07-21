############
### HEAD ###
############
### STANDARD
import doctest
import importlib
import pkgutil

### EXTERNAL
import pytest as pyt

### INTERNAL
import my


############
### DATA ###
############
#: Modules whose import or doctest run is unsafe outside a full dev environment.
EXCLUDED_SUFFIXES = ('__main__',)


############
### BODY ###
############
def iter_module_names() -> list[str]:
    """Collect every importable module under the `my` package, for doctest sweeping."""
    return [
        info.name
        for info in pkgutil.walk_packages(my.__path__, prefix='my.')
        if not info.name.endswith(EXCLUDED_SUFFIXES)
    ]


@pyt.mark.parametrize('name', iter_module_names())
def test_module_doctests(name: str):
    """Every `Examples:` block in the package must execute exactly as written.

    This is the enforcement half of the docs-campaign contract: examples are real code with
    real outputs, so a behavior change that invalidates one fails the suite rather than
    silently rotting the docs. Connection-gated examples are opted out inline via
    `# doctest: +SKIP`.
    """
    module = importlib.import_module(name)
    result = doctest.testmod(module)
    assert result.failed == 0, f'{result.failed} doctest failure(s) in {name}'
