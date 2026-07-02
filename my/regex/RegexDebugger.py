############
### HEAD ###
############
### STANDARD
from typing import Self, Any
import more_itertools as mi
import functools as ft

### EXTERNAL
import regex as re
import pytest as pyt

### INTERNAL
from ..infra.types import Vec
from ..utils import ut
from ..types import Buffer
from .meta import GroupKind, Atom, Regex, GroupAtom
from .MatchData import MatchData
from .RegexStore import RegexStore, RegexBuffer

re.DEFAULT_VERSION = re.VERSION1  # type: ignore


############
### BODY ###
############
class RegexDebugger(RegexStore):
    """Debugging tools for analyzing regex pattern failures.

    Extends RegexStore with methods to diagnose why patterns fail to match text.
    Provides detailed failure analysis by isolating the failing clause and showing
    which parts of the pattern matched successfully before failure.
    """

    # -------------------
    # `.` Initial Methods
    # -------------------
    @classmethod
    def new_debugger(cls, store: RegexStore) -> Self:
        """Create a debugger from an existing RegexStore.

        Args:
            store: RegexStore instance to create debugger from.
        Returns:
            New RegexDebugger with all patterns from the store.
        """
        new = cls.model_construct(**store.model_dump())
        new.options = store.options.model_copy()
        # `routers` moved to a private attr (RegexStore.routers is now a load-triggering
        # property) so `model_dump()`/`model_construct()` no longer round-trip it the way they
        # still do for the public `patterns`/`definitions` fields -- copy it explicitly to match
        # the prior behavior of carrying over whatever router state the source store had.
        new._routers = dict(store._routers)
        return new

    # -------------------
    # `-` Private Methods
    # -------------------
    def pinpoint_failure(self, text: Buffer, expr: Regex, prefix: str) -> tuple[int, MatchData]:
        """Identifies the first clause to cause an accumulated sub-expression to fail to match.

        Args:
            text: Buffer containing text to match against.
            expr: Tuple of regex atoms from the pattern body.
            prefix: Precompiled prefix string to prepend to each snippet.
        Returns:
            1. Index of failing atom.
            2. MatchData of last successful match.
        """
        n = len(expr)
        last_match: MatchData = MatchData()

        # I. Iterate through the atoms, progressively testing longer snippets until one breaks
        for i in range(n):
            snippet = re.compile(rf'{prefix}{expr[:i]}')
            if (match := text.match(snippet)) is not None:
                last_match = self.parse(match)
            else:
                return i, last_match

        # II. If no failure was found, return an impossible index to indicate as much
        return n, last_match

    def curate(self, atoms: Regex, failed_idx: int, flags: Atom) -> str:
        """Curate the given regex snippet to include only the failing clause and its dependencies.

        The purpose of this function is to help callers construct a "minimally-failing version" of
        a problem regex.

        Args:
            atoms: Tuple of regex atoms from the pattern body.
            failed_idx: Index of the atom where matching failed.
            flags: Atom containing any regex flags(/"modifiers") to apply to the curated expression.
        Returns:
            A truncated version of the given expression.
        """
        # I. Starting from the failed atom, walk backwards to include any optional atoms that may
        #    not have matched, thus causing the error
        start_idx = failed_idx
        while start_idx > 0 and atoms[start_idx - 1].is_optional:
            start_idx -= 1

        # II. Slice out the snippet and 'sanitize' it so that it's exportable to any regex platform
        snippet = str(atoms[start_idx : failed_idx + 1])

        # III. Identify the groups referenced in the snippet and collect just those definitions
        groups_invoked = self.parse_invocations(snippet)
        definitions = self._render_definitions(*groups_invoked)

        # IV. Return a valid RGX expression.
        return rf'{definitions}{flags}^{self.sanitize(snippet)}'

    def _do_drill(self, group: GroupAtom) -> bool:
        return (
            group.kind in GroupKind._SIMPLE
            and group.quantifier == ''
            and not Regex.is_split(group.body)
        )

    def _format_expr(self, expr: str | Regex) -> str:
        return ut.wrap('EXPRESSION', char='-', width=3) + f'\n{expr}'

    def _format_data(self, match: str | MatchData) -> str:
        return ut.wrap('LAST MATCH', char='-', width=1) + f'\n{match}'

    def _format_curated(self, curated_expr: str | Regex) -> str:
        return ut.wrap('CURATED EXPRESSION', char='-', width=2) + f'\n{curated_expr}'

    def _format_text(self, text: str | Buffer) -> str:
        return ut.wrap('UNMATCHED TEXT', char='-', width=1) + f'\n{text}'

    def _format_fulltext(self, text: str | Buffer) -> str:
        return ut.wrap('FULL TEXT', char='-', width=3) + f'\n{text}'

    def _format_fullexpr(self, expr: str | Regex) -> str:
        return ut.wrap('FULL EXPRESSION', char='-', width=3) + f'\n{expr}'

    def _format_early_return(self, name: str, explanation: str, text: str, expr: str) -> list[str]:
        return [
            f'Regular expression "{name}" {explanation}',
            self._format_fulltext(text),
            self._format_fullexpr(expr),
        ]

    @staticmethod
    def _run_pytest(store, name, func, text) -> MatchData:  # pragma: no cover
        if func == 'fullsplit':
            delims, segments = store.fullsplit(name, text)
            if to_drop := [i for i, s in enumerate(segments) if not s.strip()]:
                for i in reversed(to_drop):
                    del delims[i]
                    del segments[i]

            return MatchData.new(data=dict(delims=delims, segments=segments))
        else:
            assert hasattr(store, func), f'Unknown function: {func}'
            function = getattr(store, func)
            return function(name, text)

    @staticmethod
    def _analyze_pytest(data: MatchData, expected: Any) -> bool:  # pragma: no cover
        if not data:
            # I. Null case -- expect failure
            if expected is None:
                return True
        elif isinstance(expected, str):
            # II. Basic case -- verify any match at all
            if data.match is not None:
                return True
        elif isinstance(expected, dict):
            # III. Main case
            assert data.match is not None
            if not expected:  # basic case pt. 2
                return True

            # III.i. Add "hidden" keys that we're testing, as they're automatically trimmed
            if hidden_keys := set(
                filter(lambda k: k.startswith('_') and k not in data, expected.keys())
            ):
                captures = data.match.capturesdict()
                data |= {key: captures.get(key, []) for key in hidden_keys}

            # III.ii. In normal scenarios, only look for the keys we've been asked to look for
            if all(k in data for k in expected.keys()):
                captures = {key: vals for key, vals in data.items() if key in expected}
            else:
                captures = dict(data.items())

            # III.iii. Do the actual test
            if captures == expected:
                return True

        return False

    # -------------------
    # `+` Primary Methods
    # -------------------
    def debug_failed_match(self, name: str, text: Buffer) -> list[str]:
        """Identify which clause in the identified pattern caused matching to fail.

        Iteratively tests progressively longer subpatterns to find exactly where
        matching stops, then extracts that clause with its dependencies for testing.

        Args:
            name: Name of pattern that failed.
            text: Buffer containing text that failed to match.
        Returns:
            List of strings describing the failure with a curated test regex.
        """
        output = []

        atoms = Regex(self.definitions[name])

        # I.i. Drill down through unnecessary wrapper groups, collecting any flags set along the way
        flags = {'m'}
        while len(atoms) == 1 and isinstance(grp := atoms.one, GroupAtom) and self._do_drill(grp):
            atoms = Regex(grp.body)
            flags |= grp.flags

        # I.ii. Generate a convenient (if oversized) prefix for future repeated use
        definitions = mi.first(Regex.atomize(self.patterns[name].pattern))
        flag_group = Atom(f'(?{"".join(sorted(flags))})') if flags else Atom('')
        prefix = str(Regex(definitions, flag_group))

        # II. Iterate through the groups, matching until we fail
        failed_idx, last_match = self.pinpoint_failure(text, atoms, prefix)

        # III. Identify special cases
        if failed_idx == len(atoms):
            # III.i. All atoms succeeded
            output.extend(
                [
                    'Failed to identify failure during debugging (all atoms matched successfully).',
                    self._format_expr(self.sanitize(name)),
                    self._format_data(last_match),
                ]
            )
            if last_match.end < len(text):
                output.append(self._format_text(text[last_match.end :]))
            return output
        elif failed_idx == 0:
            # III.ii. All atoms failed
            output.extend(
                [
                    'All atoms of the regex failed, implicating the first atom OR a context issue.',
                    self._format_expr(self.sanitize(name)),
                ]
            )
            remaining_text = str(text)

        else:
            # III.iii. Main case (partial match up to failure)
            output.extend([f'Successfully identified the problematic atom ({failed_idx=}).'])
            remaining_text = text[last_match.end :]

        # IV. Return just the clauses that we think failed
        curated_rgx = self.curate(atoms, failed_idx, flag_group)
        if not curated_rgx:
            output.extend(
                [
                    'DEBUGGING ERROR -- failed to curate!',
                    self._format_expr(self.sanitize(name)),
                ]
            )
        else:
            output.extend(
                [
                    self._format_data(last_match),
                    self._format_curated(curated_rgx),
                    self._format_text(remaining_text),
                ]
            )

        return output

    # ------------------
    # `*` Public Methods
    # ------------------
    def debug(
        self,
        names: str | list[str],
        text: str,
        matched: bool,
        expected: bool = True,
        func: str = '',
    ) -> str:
        """Generate stdout-ready debug output for a regex test that produced unexpected results.

        Args:
            names: List of pattern names that were tested.
            text: Text that was matched against.
            matched: Whether the pattern actually matched.
            expected: Whether a match was expected (default: True).
            func: Name of function used (e.g., 'match', 'search', 'findall', etc).
        Returns:
            Multi-line debug report showing pattern, text, and failure analysis.
        Raises:
            ValueError: If matched and expected are both False (no failure to debug).
        """
        assert names
        if isinstance(names, str):
            names = [names]
        name = names[0].upper() + (f'.{func}()' if func else '')

        term_width = ut.get_terminal_width()
        output: list[str] = [f'{" REGEX DEBUGGER ":#^{term_width}}']
        preamble = ft.partial(
            self._format_early_return,
            name=name,
            text=text,
            expr='\n\n'.join(map(self.sanitize, names)),
        )

        # II. Analyze the failure case
        if matched and expected:
            # II.i. Incorrect case
            output.extend(preamble(explanation='INCORRECTLY MATCHED, returning the wrong data.'))

        elif matched and not expected:
            # II.ii. Unexpected case
            output.extend(preamble(explanation='UNEXPECTEDLY MATCHED when it should have failed.'))

        elif expected and not matched:
            # II.iii. Main case
            output.extend(preamble(explanation='FAILED TO MATCH the full text.'))
            for i, _name in enumerate(names):
                if len(names) > 1:
                    output.append(ut.wrap(f'`{i}` DEBUGGING {_name.upper()}...', char='=', width=4))

                output.extend(self.debug_failed_match(_name, RegexBuffer(text)))
        else:
            raise ValueError('No match, when we expected none -- why call debug_regex_test()?')

        output.extend(['', '#' * term_width])
        return '\n'.join(output)

    @staticmethod
    def parse_pytest(name: str, case: Vec | dict | str) -> tuple[str, str, dict | None]:
        """Parse a single regex test case (likely from a `.yaml` file)."""
        text: str
        func = 'full'
        expected: dict[str, list[str]] | None = None

        if isinstance(case, Vec):
            case = list(case)
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
            text = case
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

    @classmethod
    def pytest(  # pragma: no cover
        cls,
        store: RegexStore,
        name: str,
        index: int,
        text: str,
        func: str,
        expected: Any,
        verbose: bool = True,
    ) -> None:
        """Run a single test case against the given RegexStore, verifying expected results.

        Args:
            store: RegexStore containing the pattern to test.
            name: Name of the pattern to test.
            index: Index of the test case (for logging purposes).
            text: Text to match against.
            func: Name of the function to use (match|full|search|split|poly).
            expected: Expected result (None for no match, dict for expected captures).
            verbose: Whether to print debug output on failure.
        """
        if func in ['full', 'poly']:
            func += 'match'
        elif func == 'split':
            func = 'fullsplit'

        data = cls._run_pytest(store=store, name=name, func=func, text=text)
        success = cls._analyze_pytest(data=data, expected=expected)

        if not success:
            # If configured to do so, print debug output for the failed pattern
            if verbose > 1:
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
