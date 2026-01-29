############
### HEAD ###
############
### STANDARD
from typing import ClassVar
from pathlib import Path

### EXTERNAL
import pytest as pyt

### INTERNAL
from my import ut, typist, Series, Atomic, MatchData
from my.regex import format_url, atom, COMMON_RGXS, RegexDebugger

EXAMPLES = typist.from_yaml(Path(__file__).parent / 'test_common.yaml')


############
### BODY ###
############
class TestCommonRegexes:
    @classmethod
    def parse_regex_example(
        cls,
        name: str,
        case: list | dict | str,
    ) -> tuple[str, str, dict | None]:
        text: str
        func = 'full'
        expected: dict[str, list[str]] | None = None

        if isinstance(case, Series):
            text = str(case[0])
            if len(case) == 2:
                # II.ii. Verify that it matches and the named group returns the given value
                if isinstance(case[1], list):
                    expected = {name: [str(v) for v in case[1]]}
                else:
                    expected = {name: [str(case[1])]}
            elif len(case) > 2:
                raise ValueError(f'Unexpected case length: {len(case)}')

        elif isinstance(case, dict):
            assert 'text' in case
            text = str(case.pop('text'))
            if 'func' in case:
                func = case.pop('func')

            if case.get('expect_none', False):
                pass
            elif case:
                # II.iv. Main/default mode: verify that the given string returns the given captures
                expected = {
                    key: list(map(str, val if isinstance(val, list) else [val]))
                    for key, val in case.items()
                }
            else:
                expected = {}
        else:
            # II.i. Cast to string and verify that any sort of match occurs
            func = 'match'
            text = str(case)
            expected = {}

        assert isinstance(text, str)
        assert isinstance(func, str) and func in {
            'match',
            'full',
            'search',
            'fullsplit',
            'poly',
        }
        return text, func, expected

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
        text, func, expected = self.parse_regex_example(name, EXAMPLES[name][index])
        store = COMMON_RGXS

        # II. Run the appropriate function
        data: MatchData
        if func == 'fullsplit':
            delims, segments = store.fullsplit(name, text)
            if to_drop := [i for i, s in enumerate(segments) if not s.strip()]:
                for i in reversed(to_drop):
                    del delims[i]
                    del segments[i]

            data = MatchData.new(data=dict(delims=delims, segments=segments))
        else:
            if func in ['full', 'poly']:
                func += 'match'
            assert hasattr(store, func), f'Unknown function: {func}'
            function = getattr(store, func)
            data = function(name, text)

        # III. Analyze the result
        if not data:
            # III.i. Expected null result
            if expected is None:
                return
        elif isinstance(expected, str):
            if data.match is not None:
                return
        elif isinstance(expected, dict):
            assert data.match is not None
            if not expected:
                return

            # III.ii. Add "hidden" keys that we're testing, as they're automatically trimmed
            if hidden_keys := set(
                filter(lambda k: k.startswith('_') and k not in data, expected.keys())
            ):
                captures = data.match.capturesdict()
                data |= {key: captures.get(key, []) for key in hidden_keys}

            # III.iii. In normal scenarios, only look for the keys we've been asked to look for
            if all(k in data for k in expected.keys()):
                captures = {key: vals for key, vals in data.items() if key in expected}
            else:
                captures = dict(data.items())

            # III.iv. Do the actual test
            if captures == expected:
                return

        if pytestconfig.get_verbosity() > 1:
            out = RegexDebugger.new_debugger(store).debug(
                name, text, bool(data), expected is not None, func
            )
            print(out)
        pyt.fail(
            f'{func}({name}, "{text[:32]}") '
            + (
                f'returned {data}, expected {expected}'
                if data.match is not None
                else 'failed to match.'
            )
        )
