############
### HEAD ###
############
### STANDARD
import itertools as it
from typing import Self

### EXTERNAL
import regex as re

### INTERNAL
from ..utils import ut
from ..types import Buffer
from .GroupKind import GroupKind
from .MatchData import MatchData
from .RegexStore import RegexStore


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
    def _curate(
        self,
        atoms: tuple[str, ...],
        atom_ends: list[int],
        failed_idx: int,
        body: Buffer,
        definitions: dict[str, str],
        remaining_text: str,
    ) -> str:
        x0 = x1 = failed_idx
        while x0 > 0 and ut.has_any(self._quantify(atoms[x0 - 1]), '?', '*'):
            x0 -= 1

        snippet = body.slice(atom_ends[x0 - 1] if x0 else 0, atom_ends[x1])
        rgx_snippet = self.sanitize(snippet)
        invocations = self.parse_invocations(rgx_snippet)

        return '\n'.join(
            [
                r'(?(DEFINE)',
                *[definitions[group] for group in invocations],
                rf')(?m)^{rgx_snippet}',
            ]
        )

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

        # I. Split the regex up by the root-level groups present
        rgx = self.patterns[name]
        head, body_rgx = rgx.split(f'(?P<{name}>', 1)
        body_rgx = body_rgx[:-1]
        body = Buffer.new(body_rgx, fence_rgxs=['arrays'])
        atoms = self.atomize(str(body))
        while len(atoms) == 1 and self._is_group(atoms[0]):
            kind, start, flags, group_body, quant = self._parse_group(atoms[0])
            if kind in GroupKind._SIMPLE and quant == '' and not self._is_split(group_body):
                body.set(group_body)
                atoms = self.atomize(group_body)
            else:
                break
        atom_ends = list(it.accumulate(map(len, atoms)))

        # II. Iterate through the groups, matching until we fail
        n = 0
        data: MatchData = MatchData()
        for end in atom_ends:
            match = text.match(re.compile(head + body[:end]))
            if match is not None:
                data = self.parse(match)
                n += 1
            else:
                break

        # III. Exit early if we completely failed or completely succeeded
        out_rgx = self.sanitize(head + body_rgx)
        if n == 0:
            output.extend(
                [
                    f'Returned FAILED MATCH (n={n}) for entire RGX:',
                    out_rgx,
                    '',
                ]
            )
            remaining_text = str(text)
        elif n == len(atoms):
            output.extend(
                [
                    'Returned UNEXPECTED MATCH for RGX:',
                    '',
                    out_rgx,
                    '',
                    '...returning:',
                    '',
                    f'\t{data}',
                ]
            )
            if data.end < len(text):
                output.extend(['Unmatched text:', text.slice(data.end, len(text))])
            return output
        else:
            output.extend(
                [
                    f'Returned PARTIAL MATCH up to clause {n}, returning data:',
                    f'\t{data}',
                ]
            )
            remaining_text = str(text.slice(data.end, len(text)))

        # IV. Return just the clauses that we think failed
        head_buf = Buffer.new(head[len('(?(DEFINE)') : -1], fence_rgxs=['arrays'])
        definitions = {
            name: head_buf.slice(*span)
            for span, _, name, _, _ in self.group_iterator(
                head_buf, mask=GroupKind.PARAM, mode='roots'
            )
        }
        curated_rgx = self._curate(atoms, atom_ends, n, body, definitions, remaining_text)
        if not curated_rgx:
            output.extend(['Failed to curate RGX:', '', out_rgx])
        else:
            output.extend(
                [
                    '-' * 80,
                    'This test RGX:',
                    '',
                    curated_rgx,
                    '',
                    '...needs to match this remaining text:',
                    '',
                    remaining_text,
                    '-' * 80,
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
            func: Name of function used (e.g., 'match', 'search').

        Returns:
            Multi-line debug report showing pattern, text, and failure analysis.

        Raises:
            ValueError: If matched and expected are both False (no failure to debug).
        """
        assert names
        _name = names[0].upper() + (f'.{func}()' if func else '')
        output: list[str] = []

        status = str(int(matched)) + str(int(expected))
        rgxs_str = '\n\n'.join(map(self.sanitize, names))
        if status == '11':
            output.extend(
                [
                    f'RGX `{_name}` returned INCORRECT results for text:',
                    '',
                    text,
                    '',
                    '...VIA PATTERN:',
                    '',
                    rgxs_str,
                    '',
                ]
            )

        elif status == '10':
            output.extend(
                [
                    f'RGX `{_name}` returned UNEXPECTED success for text:',
                    '',
                    text,
                    '',
                    '...VIA PATTERN:',
                    '',
                    rgxs_str,
                    '',
                ]
            )

        elif status == '01':
            output.extend(
                [
                    f'RGX `{_name}` returned FAILURE to match text:',
                    '',
                    text,
                    '',
                    '...VIA PATTERN:',
                    '',
                    rgxs_str,
                    '',
                ]
            )
            buf = Buffer.new(text, fence_rgxs=['arrays'])
            for i, name in enumerate(names):
                if len(names) > 1:
                    header = f'## `{i}` output for {name.upper()} ##'
                    output.extend(
                        [
                            '',
                            '#' * len(header),
                            header,
                            '#' * len(header),
                        ]
                    )

                output.extend(self.debug_failed_match(name, buf))
        else:
            raise ValueError('No match, when we expected none -- why call debug_regex_test()?')

        return '\n'.join(output)
