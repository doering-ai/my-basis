############
### HEAD ###
############
### STANDARD
from pathlib import Path

### EXTERNAL
import pytest as pyt

### INTERNAL
from my import typist
from my.regex import COMMON_RGXS, RegexDebugger

EXAMPLES = typist.from_yaml(Path(__file__).parent / 'common_rgx_tests.yaml')

cls = RegexDebugger


############
### BODY ###
############
class TestCommonRegexes:
    # -------------------
    # `.` Initial Methods
    # -------------------
    @pyt.mark.parametrize(
        'name, index',
        [
            (name, index)
            for name, cases in EXAMPLES.items()
            for index in range(len(cases) if cases else 0)
            if cases
        ],
    )
    def test_common_rgxs(self, name: str, index: int, pytestconfig):
        # I. Parse the example into its full form
        text, func, expected = cls.parse_pytest(name, EXAMPLES[name][index])
        cls.pytest(
            store=COMMON_RGXS,
            name=name,
            index=index,
            text=text,
            func=func,
            expected=expected,
            verbose=pytestconfig.getoption('verbose') > 1,
        )
