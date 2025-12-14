############
### HEAD ###
############
### STANDARD
from typing import Self, Any
import more_itertools as mi
import functools as ft

### EXTERNAL
import regex as re

### INTERNAL
from ..utils import ut
from ..types import Buffer
from .meta import GroupKind, Atom, Atoms, Block, Quantifier
from .MatchData import MatchData
from .RegexStore import RegexStore, RegexBuffer


############
### BODY ###
############
class RegexDebugger(RegexStore):
    """
    Debugging tools for analyzing regex pattern failures.

    Extends RegexStore with methods to diagnose why patterns fail to match text.
    Provides detailed failure analysis by isolating the failing clause and showing
    which parts of the pattern matched successfully before failure.
    """

    # -------------------
    # `0` Initial Methods
    # -------------------
    @classmethod
    def new_debugger(cls, store: RegexStore) -> Self:
        """
        Create a debugger from an existing RegexStore.

        Args:
            store: RegexStore instance to create debugger from.
        Returns:
            New RegexDebugger with all patterns from the store.
        """
        return cls.model_construct(**store.model_dump())

    # -------------------
    # `-` Private Methods
    # -------------------
    def pinpoint_failure(self, text: Buffer, atoms: Atoms, prefix: str) -> tuple[int, MatchData]:
        last_match: MatchData = MatchData()

        # I. Iterate through the atoms, progressively testing longer snippets until one breaks
        for i in range(len(atoms)):
            snippet = re.compile(rf'{prefix}{atoms[:i]}')
            if (match := text.match(snippet)) is not None:
                last_match = self.parse(match)
            else:
                return i, last_match

        # II. If no failure was found, return an impossible index to indicate as much
        return len(atoms), last_match

    def curate(self, atoms: Atoms, failed_idx: int, flags: Atom) -> str:
        """
        Curate the given regex snippet to include only the failing clause and its dependencies.

        Args:
            atoms: Tuple of regex atoms from the pattern body.
            atom_ends: List of end indices for each atom in the body.
            failed_idx: Index of the atom where matching failed.
            body: Buffer containing the full pattern body.
            defs: Dictionary of group definitions from the pattern head.
        Returns:
            A truncated version of the given expression.
        """
        # I. Starting from the failed atom, walk backwards to include any optional atoms that may
        #    not have matched, thus causing the error
        start_idx = failed_idx
        while start_idx > 0 and atoms[start_idx - 1].is_optional:
            start_idx -= 1

        # II. Slice out the snippet and 'sanitize' it so that it's exportable to any regex platform
        snippet = str(atoms[start_idx:failed_idx])

        # III. Identify the groups referenced in the snippet and collect just those definitions
        groups_invoked = self.parse_invocations(snippet)
        definitions = self._render_definitions(*groups_invoked)

        # IV. Return a valid RGX expression.
        return rf'{definitions}{flags}^{self.sanitize(snippet)}'

    def format_expr(self, expr: str | Atoms) -> str:
        return ut.wrap('EXPRESSION', char='-', width=3) + f'\n{expr}'

    def format_data(self, match: str | MatchData) -> str:
        return ut.wrap('LAST MATCH', char='-', width=1) + f'\n{match}'

    def format_curated(self, curated_expr: str | Atoms) -> str:
        return ut.wrap('CURATED EXPRESSION', char='-', width=2) + f'\n{curated_expr}'

    def format_text(self, text: str | Buffer) -> str:
        return ut.wrap('UNMATCHED TEXT', char='-', width=1) + f'\n{text}'

    def format_fulltext(self, text: str | Buffer) -> str:
        return ut.wrap('FULL TEXT', char='-', width=3) + f'\n{text}'

    def format_fullexpr(self, expr: str | Atoms) -> str:
        return ut.wrap('FULL EXPRESSION', char='-', width=3) + f'\n{expr}'

    def format_early_return(self, name: str, explanation: str, text: str, expr: str) -> list[str]:
        return [
            f'Regular expression "{name}" {explanation}',
            self.format_fulltext(text),
            self.format_fullexpr(expr),
        ]

    # -------------------
    # `+` Primary Methods
    # -------------------
    def debug_failed_match(self, name: str, text: Buffer) -> list[str]:
        """
        Analyze a pattern that failed to match and identify the failing clause.
        Iteratively tests progressively longer subpatterns to find exactly where
        matching stops, then extracts that clause with its dependencies for testing.

        Args:
            name: Name of pattern that failed.
            text: Buffer containing text that failed to match.
        Returns:
            List of strings describing the failure with a curated test regex.
        """
        output = []

        flags = {'m'}
        atoms = Atoms.atomize(self.definitions[name])
        while len(atoms) == 1 and atoms.one.is_group:
            _kind, _, _flags, _body, _quant = atoms.one.as_group()
            group_atoms = Atoms.atomize(_body)
            if _kind in GroupKind._SIMPLE and not (_quant or Atoms.is_split(group_atoms)):
                atoms = group_atoms
                flags |= set(_flags)
            else:
                break

        # I.ii. Generate a convenient (if oversized) prefix for future repeated use
        flag_group = Atom(f'(?{"".join(sorted(flags))})')
        definitions = mi.first(Atoms.atomize(self.patterns[name].pattern))
        prefix = str(Atoms(definitions, flag_group))

        # II. Iterate through the groups, matching until we fail
        failed_idx, last_match = self.pinpoint_failure(text, atoms, prefix)

        # III. Identify special cases
        if failed_idx == len(atoms):
            # III.i. All atoms succeeded
            output.extend(
                [
                    'Failed to identify failure during debugging (all atoms matched successfully).',
                    self.format_expr(self.sanitize(name)),
                    self.format_data(last_match),
                ]
            )
            if last_match.end < len(text):
                output.append(self.format_text(text[last_match.end :]))
            return output
        elif failed_idx == 0:
            # III.ii. All atoms failed
            output.extend(
                [
                    'All atoms of the regex failed, implicating the first atom OR a context issue.',
                    self.format_expr(self.sanitize(name)),
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
                    self.format_expr(self.sanitize(name)),
                ]
            )
        else:
            output.extend(
                [
                    self.format_data(last_match),
                    self.format_curated(curated_rgx),
                    self.format_text(remaining_text),
                ]
            )

        return output

    # ------------------
    # `x` Public Methods
    # ------------------
    def debug(
        self,
        names: list[str],
        text: str,
        matched: bool,
        expected: bool = True,
        func: str = '',
    ) -> str:
        """
        Generate debug output for a regex test that produced unexpected results.

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
        name = names[0].upper() + (f'.{func}()' if func else '')

        term_width = ut.get_terminal_width()
        output: list[str] = [f'{" REGEX DEBUGGER ":#^{term_width}}']
        preamble = ft.partial(
            self.format_early_return,
            name=name,
            text=text,
            expressions='\n\n'.join(map(self.sanitize, names)),
        )

        # II. Analyze the failure case
        if matched and expected:
            # II.i. Incorrect case
            output.extend(preamble('INCORRECTLY MATCHED, returning the wrong data.'))

        elif matched and not expected:
            # II.ii. Unexpected case
            output.extend(preamble('UNEXPECTEDLY MATCHED when it should have failed.'))

        elif expected and not matched:
            # II.iii. Main case
            output.extend(preamble('FAILED TO MATCH the full text.'))
            for i, _name in enumerate(names):
                if len(names) > 1:
                    output.append(ut.wrap(f'`{i}` DEBUGGING {_name.upper()}...', char='=', width=4))

                output.extend(self.debug_failed_match(_name, RegexBuffer(text)))
        else:
            raise ValueError('No match, when we expected none -- why call debug_regex_test()?')

        output.extend(['', '#' * term_width])
        return '\n'.join(output)
