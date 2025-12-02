############
### HEAD ###
############
### STANDARD
from typing import Iterable, Iterator, Literal, ClassVar, Any, Callable, Generator, Mapping, Self
from collections import deque
import functools as ft
import itertools as it

### EXTERNAL
import more_itertools as mi
import pydantic as pyd
import regex as re
from regex import Match, Pattern, RegexFlag

### INTERNAL
from ..utils import ut
from ..types import Span, Buffer
from .GroupKind import GroupKind, GROUP_KIND_MAP
from .MatchData import MatchData
from .ParseData import ParseData

############
### DATA ###
############
DEBUG = False
re.DEFAULT_VERSION = re.VERSION1

NO_KIND = GroupKind(0)
NO_FLAG = RegexFlag(0)

# General type aliases
Params = dict[str, str]
Captures = dict[str, list[str]]

# Regex-specific type aliases
Atom = str
Atoms = tuple[str, ...]
Branches = list[Atoms]
Block = tuple[Atoms, Atoms, Atoms]
RgxParser = (
    str  # base case: Simply renames the output
    | Callable[[str], str]  # 1st case: returns some subset to the same name
    | Callable[[str], dict[str, str]]  # 2nd case: returns to any number of other names
    | Callable[[str], dict[str, str] | str]  # 3rd case: combo of above two
)

RgxTup = tuple[str, 'RgxList'] | tuple[str, str, 'RgxList', str]
RgxList = Iterable['RgxVal']
RgxVal = str | RgxList | RgxTup | Pattern | dict
RgxDef = (
    str
    | tuple[str, RgxParser]  # Raw/simple content
    | RgxTup
    | tuple[RgxTup, RgxParser]  # Single piece of uncompiled content
    | RgxList
    | tuple[RgxList, RgxParser]  # Series of uncompiled content
    | Pattern
    | tuple[Pattern, RgxParser]  # Compiled content
)

# A buffer built to hold Regex patterns
RgxBuf = ft.partial(Buffer.new, fence_rgxs=['arrays'])

FLAGS = r'(?P<flags>-?[afiLmsuxwif]+|[afiLmsuxwif]+-[afiLmsuxwif]+)'
NO_ESC = r'(?<!^\\|[^\\]\\)'
NON_ESC = r'(?:^|[^\\]|\\\\)'
NO_SET = rf'(?<!{NON_ESC}\[[^\]]{{0,8}})'
NO_SET_SUF = rf'(?!\]|[^\[]{{0,8}}{NON_ESC}\])'
QUANT = r'(?>[*+]|\{\d+(?:,\d*)?\})?[?+]?'


############
### BODY ###
############
class RegexStore(pyd.BaseModel):
    """
    A powerful regex pattern management system with composition and parsing capabilities.

    RegexStore provides a comprehensive framework for defining, composing, and applying
    complex regex patterns. It supports:
    - Hierarchical pattern composition from simple building blocks
    - Named group management and subroutine invocation
    - Custom parsing functions for match results
    - Pattern optimization and tree construction
    - Router trees for pattern classification

    Patterns can be defined using a flexible DSL that supports:
    - String literals and pre-compiled patterns
    - Lists for sequential composition
    - Tuples for group creation with custom separators
    - Recursive pattern references via named groups
    """
    # Meta Regexes
    RGXS: ClassVar[dict[str, Pattern]] = ut.regex_dict(
        dict(
            struct_mark=''.join(
                [
                    r'(?P<divis><\|>|\||\[.*?\])?',
                    r'(?P<group>[:>&|]|<?[=!]|P<\w+>)?',
                    rf'{FLAGS}?(?P<quant>{QUANT})',
                ]
            ),
            set=NO_ESC + ut.multi_rgx(r'(?P<start>\[)', rf'(?P<end>\]{QUANT})'),
            group=NO_ESC
            + ut.multi_rgx(
                rf'(?P<start>\((?:\?(?>[:>&|]|<?[=!]|P[=<]|{FLAGS}:)?)?)',
                rf'(?P<end>\){QUANT})',
            ),
            inline_flags=rf'{NO_ESC}\(\?{FLAGS}:',
            atom=NO_ESC
            + ut.multi_rgx(
                r'\\'
                + ut.multi_rgx(
                    r'\d+|g<\d+>',
                    r'L<\w+>',
                    r'[Pp]\{[[:alpha:]]+\}',
                    r'.',
                ),
                r'(?<!\[)\[(?s:[^\\\[\]]+|\\.|\[.+?\])*\](?!\])',
                r'[^\\]',
            )
            + QUANT,
            quant=NO_ESC + r'(?:\?|(?:[*+]|\{\d+(?:,\d*)?\})[?+]?)$',
            set_operator=rf'^\[?(?:\^|[^\[].*?{NO_ESC}(?>--?|~~|&&|\|\|))',
            special_characters=NO_ESC + r'([+*?()|.^$])',
        )
    )

    # Uncompiled strings, ready for reuse
    definitions: dict[str, str] = {}

    # Compiled patterns, ready to be invoked
    patterns: dict[str, Pattern] = {}

    # Functions for handling groups we've stored, dropping unnecessary info
    parsers: dict[str, RgxParser] = {}

    routers: dict[str, list[str]] = {}

    # Convenience options
    init_formatter: Callable[..., str] | None = None
    formatter: Callable[..., str] | None = None
    separator: str = r' *'
    force_named_groups: bool = False

    # Autostrip behavior
    autostrip_spaces: bool = True
    autostrip_brackets: bool = False
    autostrip_commas: bool = False

    # Caches/excluded fields
    strip: Callable[[str], str] = pyd.Field(default=lambda x: x, exclude=True)

    # -------------------
    # `0` Initial Methods
    # -------------------
    @classmethod
    def new(
        cls,
        options: dict[str, Any] | None = None,
        imports: list[tuple['RegexStore', Iterable[str]]] | None = None,
        **params: RgxDef | Any,
    ) -> Self:
        """
        Create a new RegexStore, populating internal fields appropriately by transforming the
        given inputs. All extra/dynamic params are interpreted as patterns.
        """
        if options is None:
            options = {}
        if imports is None:
            imports = []
        store = cls(**options)

        for source, names in imports:
            for name in source.find_all_invocations(set(names)):
                store.definitions[name] = source.definitions[name]
                store.patterns[name] = source.patterns[name]
                if name in source.parsers:
                    store.parsers[name] = source.parsers[name]

        if store.init_formatter is not None:
            # I. Format the given args (of any type) if told to, without parsers
            for name, param in params.items():
                val = store.init_formatter(param) if not isinstance(param, Pattern) else param
                store.define(name, val, None)
        else:
            # II. Set the values of the store without formatting, but perhaps with Parsers
            for name, param in params.items():
                store[name] = param

        return store

    @pyd.field_validator('definitions')
    @classmethod
    def _validate_definitions(cls, definitions: dict[str, str]) -> dict[str, str]:
        return {key: val.replace('(?P=', '(?&') for key, val in definitions.items()}

    @pyd.model_validator(mode='after')
    def _validate_store(self) -> 'RegexStore':
        strip_string = ''
        if self.autostrip_spaces:
            strip_string += ' '
        if self.autostrip_brackets:
            strip_string += '()[]'

        if self.autostrip_commas:
            strip_string += ','

        if strip_string:
            self.strip = lambda text: text.strip(strip_string) or text
        else:
            self.strip = lambda text: text

        return self

    def __len__(self) -> int:
        return len(self.patterns)

    def __contains__(self, key: str) -> bool:
        return key in self.patterns

    def __setitem__(self, name: str, param: RgxDef) -> None:
        assert name not in self.patterns, f'Duplicate pattern name: {name}'

        # Pull out the parser, if present
        val: RgxVal
        if isinstance(param, tuple) and len(param) == 2 and not isinstance(param[1], (list, tuple)):
            val, parser = param  # type: ignore
        else:
            val = param
            parser = None

        self.define(name, val, parser)  # type: ignore

    def __getitem__(self, name: str) -> Pattern:
        assert name in self.patterns, f'Pattern not found: {name}'
        return self.patterns[name]

    def pop(self, name: str) -> Pattern:
        assert name in self.patterns, f'Pattern not found: {name}'
        del self.definitions[name]
        if name in self.parsers:
            del self.parsers[name]
        return self.patterns.pop(name)

    def get(self, name: str, default: Pattern | None = None) -> Pattern | None:
        return self.patterns.get(name, default)

    def get_def(self, name: str, default: str | None = None) -> str | None:
        return self.definitions.get(name, default)

    # -------------------
    # `-` Private Methods
    # -------------------
    @classmethod
    def _tree_print(cls, text: str, depth: int = 0) -> str:
        indent = '\t' * depth

        branches: list[str] = []
        for atoms in cls._atomic_split(text):
            line: list[str] = []
            for atom in atoms:
                if cls._is_group(atom) and ('|' in atom or len(atom) > 48):
                    kind, start, flags, body, quant = cls._parse_group(atom)
                    line.append(
                        '\n'.join(
                            [
                                f'{start}{"(?" + flags + ")" if flags else ""}',
                                cls._tree_print(body, depth + 1),
                                f'{indent}){quant}',
                            ]
                        )
                    )
                else:
                    line.append(atom)
            branches.append(''.join(line))
        return indent + f'|\n{indent}'.join(branches)

    def tree_print(self, pattern: str | Pattern | Buffer, print_head: bool = True) -> str:
        """
        Pretty-print a regex pattern as an indented tree structure.

        Args:
            pattern: Pattern to print (string, compiled Pattern, or Buffer).
            print_head: Whether to include the pattern header in output.
        Returns:
            Multi-line string representation with indentation showing nesting.
        """
        text = self.sanitize(pattern)
        *head_arr, body = text.split('\n)(', 1)
        body = body[body.index('>') + 1 : -1]
        ret = self._tree_print(body)
        return f'{head_arr[0]}\n){ret}' if print_head and head_arr else ret

    def find_all_invocations(self, groups_used: set[str]) -> set[str]:
        """
        Recursively find all groups invoked by the given set of groups.

        Args:
            groups_used: Initial set of group names to analyze.
        Returns:
            Complete set of all groups transitively invoked by the initial set.
        """
        buffer = RgxBuf()
        new_groups: set[str] = set()
        for existing_group in groups_used:
            buffer.set(self.definitions[existing_group])
            for _, _, name, _, _ in self.group_iterator(buffer, mask=GroupKind.INVOC):
                if name not in groups_used:
                    new_groups.add(name)

        if new_groups:
            return groups_used | self.find_all_invocations(new_groups)
        else:
            return groups_used

    def _parse_mark(self, mark: str) -> tuple[GroupKind, str, str, str]:
        """
        Parse a custom mark string into regex group components.

        Processes mark syntax like '|:', '[]:', '<|>', and flag specifiers to determine
        the type of regex group to create, the opening syntax, separator, and quantifier.

        Args:
            mark: Custom mark string using the store's DSL syntax.
        Returns:
            Tuple of (kind, start, separator, quantifier) where:
            - kind: GroupKind enum value
            - start: Opening group syntax (e.g., '(?:', '(?>')
            - separator: String to join children (defaults to self.separator)
            - quantifier: Quantifier string (e.g., '?', '+', '*')
        """
        mark = mark.strip()
        match = self.RGXS['struct_mark'].fullmatch(mark)
        assert match, f'Invalid mark: {mark}, {self.RGXS["struct_mark"].pattern}'
        data, _ = self.read_match(match)

        sep = match['divis'] or ''
        group = data.pop('group', '')
        quant = data.pop('quant', '')

        if sep == '|' and not group:
            group = '|'
        elif sep == '<|>' and not group:
            group = '>'
        elif len(sep) >= 2 and sep[0] == '[' and sep[-1] == ']':  # type: ignore
            sep = sep[1:-1]
        elif not sep:
            sep = self.separator

        # Override this group, which is used by the caller to wrap children
        if group == '&':
            group = ':'
        start = f'(?{group}' if group else '('
        kind = self.parse_group_kind(start)
        if flags := data.pop('flags', ''):
            start = f'(?{flags}:' if kind == GroupKind.PLAIN else f'{start}(?{flags})'

        return kind, start, sep, quant

    @classmethod
    def parse_group_kind(cls, group: str) -> GroupKind:
        """
        Determine the GroupKind of a regex group from its opening syntax.

        Args:
            group: The opening part of a regex group (e.g., '(?:', '(?=', '(?>').
        Returns:
            The corresponding GroupKind enum value, or GroupKind(0) if no match.
        """
        return next(
            (kind for prefix, kind in reversed(GROUP_KIND_MAP.items()) if group.startswith(prefix)),
            GroupKind(0),
        )

    @classmethod
    def set_iterator(cls, text: Buffer | str | list[str]) -> Iterator[tuple[Span, str, str]]:
        """
        Iterate over all character sets in the text.

        Args:
            text: Text to search for character sets.
        Yields:
            Tuples of (span, body, quantifier) for each character set found.
        """
        if isinstance(text, list):
            text = ''.join(text)
        if isinstance(text, str):
            text = Buffer.new(text, no_fence=True)  # NOTE: Not a RgxBuf, so no fence_rgxs

        for span, _, body, end in text.pair_iterator(cls.RGXS['set'], mode='roots'):
            yield span, body, end[1:]

    @classmethod
    def group_iterator(
        cls,
        text: Buffer | str | list[str],
        mask: GroupKind = NO_KIND,
        mode: Literal['all', 'roots', 'leaves'] = 'all',
    ) -> Iterator[tuple[Span, GroupKind, str, str, str]]:
        """
        Iterate over regex groups in the text.

        Args:
            text: Text to search for groups (automatically converted to Buffer).
            mask: Optional GroupKind filter to yield only matching group types.
            mode: Iteration mode - 'all' for all groups, 'roots' for top-level only,
                  'leaves' for innermost only.
        Yields:
            Tuples of (span, kind, name, body, quantifier) for each group found.
        """
        # Cast the input text to a charset-ignoring buffer
        if isinstance(text, list):
            text = RgxBuf(''.join(text))
        elif isinstance(text, str):
            text = RgxBuf(text)
        else:
            assert 'arrays' in text.fence_rgxs, f'Invalid buffer: {text.fence_rgxs}'

        for span, start, body, end in text.pair_iterator(cls.RGXS['group'], mode):
            kind = cls.parse_group_kind(start)
            if mask and kind not in mask:
                continue

            if kind in GroupKind._NAMED:
                name = body.split('>', 1)[0]
                body = body[len(name) + 1 :]
            else:
                name = ''
            yield span, kind, name, body, end[1:]

    def _validate_params(
        self, patterns: str | Iterable[str], text: str | Buffer
    ) -> tuple[Iterable[str], str]:
        """Validate the usual public paramaters, returning a guaranteed Buffer."""
        if isinstance(patterns, str):
            patterns = [patterns]
        assert ut.has_all(self.patterns, *patterns), f'Unknown pattern(s): {patterns}'
        return patterns, str(text) if isinstance(text, Buffer) else text

    @staticmethod
    def _validate_tuple(data: tuple, types: tuple[type, ...]) -> None:
        assert len(data) == len(types), f'Invalid tuple: {data}'
        assert all(isinstance(v, t) for v, t in zip(data, types, strict=True)), (
            f'Invalid tuple: {data}'
        )

    @staticmethod
    def _greatest_common_prefix(*args: Atoms) -> Atoms:
        if not args or not all(map(len, args)):
            return tuple()
        elif len(args) == 1:
            return args[0]

        return tuple(mi.longest_common_prefix(args))

    @staticmethod
    def _greatest_common_suffix(*args: Atoms) -> Atoms:
        if not args or not all(map(len, args)):
            return tuple()
        elif len(args) == 1:
            return args[0]

        return tuple(reversed(tuple(mi.longest_common_prefix(map(reversed, args)))))

    @classmethod
    def _apply_quantity(cls, text: str, quantity: str) -> str:
        # I. Null case
        if not quantity:
            return text
        elif cls._is_atomic(text):
            if cls._is_optional(text):
                # Edge case: double-applying optionality
                if quantity == '?':
                    return text
            elif not cls._is_quantified(text):
                return f'{text}{quantity}'

        # Default: Wrap in group
        return f'(?:{text}){quantity}'

    @classmethod
    def _clean_branches(cls, branches: Branches, quantity: str) -> tuple[Branches, bool]:
        to_drop: set[int] = set()
        inferred_optional = False
        for i, branch in enumerate(branches):
            if (n := len(branch)) == 0 or not any(branch):
                # I.i. Empty branch -- whole thing is now optional
                to_drop.add(i)
                inferred_optional = True
            elif n == 1:
                # I.ii. Single atom -- check for optionality
                atom = branch[0]
                _q = cls._quantify(atom)
                if _q == '?':
                    inferred_optional = True
                    branches[i] = (atom[:-1],)
                elif quantity in ('', '?'):
                    if _q.startswith('{0'):
                        inferred_optional = True
                        branches[i] = (atom[: -len(_q)] + '{1' + _q[2:],)
                    elif _q.startswith('*'):
                        inferred_optional = True
                        branches[i] = (atom[: -len(_q)] + f'+{_q[1:]}',)
            else:
                # I.iii. Look for a copy of this branch w/ a prefix
                candidates = [
                    j for j, j_br in enumerate(branches) if j not in to_drop and len(j_br) == n + 1
                ]
                if (j := next((j for j in candidates if branches[j][1:] == branch), -1)) != -1:
                    to_drop.add(i)
                    j_br = branches[j]
                    branches[j] = (cls._apply_quantity(j_br[0], '?'), *j_br[1:])

        # II. Combine the branches into one atomic group
        return ut.drop_at(branches, to_drop), inferred_optional

    @classmethod
    def _render_branches(
        cls, branches: Branches, has_suffix: bool = False, quantity: str = ''
    ) -> str:
        # I. Clean the branch list, identifying optional branches and pre-combining where possible
        branches, inferred_optional = cls._clean_branches(branches, quantity)
        assert branches, 'Empty branches passed'

        # II. Determine whether we can safely use an atomic grouping here
        if len(branches) == 1:
            body = ''.join(branches[0])
        else:
            mark = cls._choose_joining_mark(branches, has_suffix)
            body = f'(?{mark}{"|".join(map("".join, branches))})'

        # III. Apply quantity mark & optionality to the group, and return
        if inferred_optional:
            body = cls._apply_quantity(body, '?')
        if quantity:
            body = cls._apply_quantity(body, quantity)

        return body

    @classmethod
    def _choose_joining_mark(cls, branches: Branches, has_suffix: bool = False) -> str:
        assert branches, 'Empty param.'

        # Look for sets if we have a suffix
        if any(
            atom[0] == '[' or cls._is_quantified(atom) or cls._is_complex_group(atom)
            for branch in branches
            for atom in (branch if has_suffix else (branch[0],))
        ):
            return ':'
        return '>'

    @classmethod
    def _join_atoms(cls, atoms: list[Atom], has_suffix: bool = False) -> Atom:
        # I. Determine if the resulting atom should be optional
        quantity = ''
        for i, atom in enumerate(atoms):
            if cls._is_optional(atom):
                quantity = '?'
                atoms[i] = atom[:-1]

        # II. Split into simple atoms and sets
        branches, simple_atoms = map(list, mi.partition(cls._is_simple, atoms))

        if (n_simple := len(simple_atoms)) == 0:
            pass
        elif n_simple == 1:
            branches.insert(0, simple_atoms[0])
        else:
            chars, sets = map(list, mi.partition(cls._is_simple_set, simple_atoms))
            set_chars = [
                _atom for _set in sets for _atoms in cls.split_set(_set) for _atom in _atoms
            ]
            set_body = ''.join(sorted({*set_chars, *chars}))
            branches.insert(0, f'[{set_body}]')

        # III. Render the resulting set alternated w/ the complex branches
        return cls._render_branches([(b,) for b in branches], has_suffix, quantity)

    @classmethod
    def _group_by_prefix(cls, branches: Branches) -> Generator[Branches, None, None]:
        yield from map(
            list,
            mi.split_when(branches, lambda lhs, rhs: not cls._greatest_common_prefix(lhs, rhs)),
        )

    @staticmethod
    def _block_suffix(block: Block) -> Atoms:
        return block[2] if block[0] else block[1]

    @classmethod
    def _group_by_suffix(cls, blocks: list[Block]) -> Generator[list[Block], None, None]:
        yield from map(
            list,
            mi.split_when(
                blocks, lambda *args: not cls._greatest_common_suffix(*map(cls._block_suffix, args))
            ),
        )

    @classmethod
    def _construct_branches(cls, block: Branches) -> Block:
        # 0. Return immediately if this is a single branch, with no prefix
        if len(block) == 1:
            return (tuple(), block[0], tuple())

        # I. Determine the prefix for this block, which is guaranteed to exist
        prefix = cls._greatest_common_prefix(*block)
        assert (n_pre := len(prefix)), f'No prefix found for: {block}'
        block = [branch[n_pre:] for branch in block]

        # II. Check for a shared suffix
        if suffix := cls._greatest_common_suffix(*block):
            block = [branch[: -len(suffix)] for branch in block]

        # III. Recursively construct children branches
        content = cls.construct_tree(block, has_suffix=bool(suffix))
        return (prefix, (content,), suffix)

    @classmethod
    def _render_blocks(cls, section: list[Block]) -> Atoms:
        assert (n := len(section)), 'Iterated to empty section.'
        # I. Simple/base case is that each block is handled separately
        if n == 1:
            prefix, body, suffix = section[0]
            return prefix + body + suffix

        # II. When adjacent blocks share (part of) their suffixes, handle here
        shared_suffix = cls._greatest_common_suffix(*map(cls._block_suffix, section))
        assert shared_suffix, f'Somehow collected multiple no-suffix sections: {section}'
        branches = [
            (prefix + body + suffix)[: -len(shared_suffix)] for prefix, body, suffix in section
        ]

        # III. Render the final result with the suffix at the end
        return (cls._render_branches(branches, True), *shared_suffix)

    @classmethod
    def construct_tree(cls, branches: Branches, has_suffix: bool = False) -> str:
        """
        Construct an optimized regex from branches by factoring common prefixes and suffixes.

        This method builds an efficient regex pattern by identifying and extracting common
        prefixes and suffixes from multiple branches, minimizing redundancy in the result.

        Args:
            branches: Tuple of atom sequences representing alternative branches.
            has_suffix: Whether parent context implies a shared suffix exists.
        Returns:
            Optimized regex string with factored common elements.
        """
        # 0. Sort and de-dupe
        branches = list(sorted(set(branches)))

        # I. Shortcut for simple cases
        if len(branches) == 1:
            assert (branch := branches[0]), 'Just one empty branch passed in.'
            ret = ''.join(branch)
        elif max(*map(len, branches)) == 1:
            ret = cls._join_atoms([(branch[0] if branch else '') for branch in branches])
        else:
            # II. Separate the sorted branches into sections that share prefixes
            blocks = list(map(cls._construct_branches, cls._group_by_prefix(branches)))

            # III. Render each block, factoring out any shared suffixes
            clauses = list(map(cls._render_blocks, cls._group_by_suffix(blocks)))
            ret = cls._render_branches(clauses, has_suffix)

        return ret

    @classmethod
    @ft.lru_cache(maxsize=64)
    def _is_group(cls, atom: str) -> bool:
        return len(atom) > 0 and atom[0] == '('

    @classmethod
    @ft.lru_cache(maxsize=64)
    def _is_complex_group(cls, atom: str) -> bool:
        if not cls._is_group(atom):
            return False
        kind, _, _, _, quant = cls._parse_group(atom)
        return kind not in GroupKind._SIMPLE or quant not in ('', '?')

    @classmethod
    @ft.lru_cache(maxsize=64)
    def _is_simple(cls, atom: str) -> bool:
        # Don't include groups or quantified values
        return len(atom) > 0 and not (
            cls._is_group(atom)
            or cls._is_quantified(atom)
            or (atom[0] == '[' and not cls._is_simple_set(atom))
        )

    @classmethod
    @ft.lru_cache(maxsize=64)
    def _is_simple_set(cls, atom: str) -> bool:
        if len(atom) < 3:
            return False
        return bool(atom[0] == '[' and not cls.RGXS['set_operator'].search(atom))

    @classmethod
    def _quantify(cls, atom: str) -> str:
        if cls._is_atomic(atom) and len(atom) >= 2 and (match := cls.RGXS['quant'].search(atom)):
            return match[0]
        return ''

    @classmethod
    @ft.lru_cache(maxsize=64)
    def _is_quantified(cls, atom: str) -> bool:
        return cls._quantify(atom) not in ('', '?')

    @classmethod
    @ft.lru_cache(maxsize=64)
    def _is_optional(cls, atom: str) -> bool:
        return cls._quantify(atom) == '?'

    @classmethod
    def _is_split(cls, pattern: str | Atoms) -> bool:
        if isinstance(pattern, str):
            return any(atom == '|' for atom in cls.atomize_iter(pattern))
        else:
            return '|' in pattern

    @classmethod
    def _is_atomic(cls, pattern: Atom | Atoms) -> bool:
        if isinstance(pattern, str):
            return next((len(v) == len(pattern) for v in cls.atomize_iter(pattern)), False)
        else:
            return len(pattern) == 1

    @classmethod
    def split_group(cls, grp_atom: Atom, recursive: bool = False) -> tuple[Atoms, ...]:
        branches: tuple[Atoms, ...] = ((grp_atom,),)
        if cls._is_group(grp_atom):
            kind, start, flags, body, quant = cls._parse_group(grp_atom)

            if kind in GroupKind._SPLITTABLE and quant in ('', '?'):
                branches = cls._atomic_split(body, recursive)
                if quant == '?':
                    branches = (tuple(),) + branches
                if flags:
                    flag_group = (f'(?{flags})',)
                    branches = tuple(
                        (flag_group + branch) if branch else branch for branch in branches
                    )
            elif quant == '?':
                branches = (tuple(), (grp_atom[:-1],))

        return branches

    @classmethod
    @ft.lru_cache(maxsize=64)
    def split_set(cls, set_atom: Atom) -> tuple[Atoms, ...]:
        is_simple, body, quant = cls._parse_set(set_atom)
        if not is_simple or quant not in ('', '?'):
            return ((set_atom,),)

        branches = tuple((atom,) for atom in cls.atomize(body, escape=True))
        return (tuple(), *branches) if quant == '?' else branches

    @classmethod
    def _split_atom(cls, atom: Atom) -> tuple[Atoms, ...]:
        if cls._is_group(atom):
            return cls.split_group(atom, True)
        elif cls._is_simple_set(atom):
            return cls.split_set(atom)
        elif cls._is_optional(atom):
            return (tuple(), (atom[:-1],))
        else:
            return ((atom,),)

    @classmethod
    def _atomic_split(
        cls, pattern: str | Atoms | list[str], recursive: bool = False, max_split: int = 4
    ) -> tuple[Atoms, ...]:
        # 0. Handle edge cases and different call formats
        if not pattern:
            return tuple()
        elif isinstance(pattern, list):
            return tuple(block for p in pattern for block in cls._atomic_split(p, recursive))
        elif isinstance(pattern, tuple):
            items = pattern
        else:
            items = cls.atomize(pattern)

        # I. Split into initial groupings based on hard branches
        blocks: deque[Atoms] = deque()
        separators = [i for i, c in enumerate(items) if c == '|'] + [len(items)]
        for j, end in enumerate(separators):
            start = separators[j - 1] + 1 if j else 0
            block: Atoms = items[start:end]

            # I.i. Recursively split up to one set or group to create multiple branches
            if recursive:
                n_split = 0
                branch_list: deque[tuple[Atoms, ...]] = deque()
                for atom in block:
                    if n_split < max_split and len(branches := cls._split_atom(atom)) > 1:
                        branch_list.append(branches)
                        n_split += 1
                    else:
                        branch_list.append(((atom,),))

                if n_split:
                    blocks.extend(
                        [
                            tuple(mi.collapse(permutation))
                            for permutation in it.product(*branch_list)
                        ]
                    )
                    continue

            # I.ii. Otherwise, just return this block as one branch
            blocks.append(block)

        return tuple(sorted(set(blocks)) if recursive else blocks)

    @classmethod
    def split(cls, pattern: str | Atoms | list[str], recursive: bool = False) -> list[str]:
        return list(map(''.join, cls._atomic_split(pattern, recursive)))

    @classmethod
    def _parse_set(cls, atom: str) -> tuple[bool, str, str]:
        body, quant = atom[1:].rsplit(']', 1)
        return cls._is_simple_set(atom), body, quant

    @classmethod
    def _parse_group(cls, atom: str) -> tuple[GroupKind, str, str, str, str]:
        # I. Parse the group and determine its type
        ret = next(cls.group_iterator(atom, mode='roots'), None)
        assert ret, f'Invalid atom: {atom}'

        span, kind, cname, body, quant = ret
        assert span == (0, len(atom)), f'Invalid atom: {atom}'

        start = atom[: atom.index(body)]

        # II. Expand out inline flags
        flags = ''
        if kind == GroupKind.FLAGS and start.endswith(':'):
            flags = start[2:-1]
            start = '(?:'
            kind = GroupKind.PLAIN

        return kind, start, flags, body, quant

    @classmethod
    def _parse_tuple(
        cls,
        data: RgxTup,
        formatter: Callable[[str], str] | None = None,
    ) -> tuple[str, RgxList, str, str]:
        if (n := len(data)) == 2:
            cls._validate_tuple(data, (str, list))
            mark, children = data  # type: ignore
            return mark, children, '', ''
        elif n == 4:
            cls._validate_tuple(data, (str, str, list, str))
            mark, prefix, children, suffix = data  # type: ignore
            if formatter is not None:
                prefix, suffix = map(formatter, (prefix, suffix))
            return mark, children, prefix, suffix
        else:
            raise ValueError(f'Invalid tuple: {data}')

    @classmethod
    def atomize_iter(cls, pattern: str) -> Generator[str, None, None]:
        n = len(pattern)
        _x = 0

        for (x0, x1), *_ in cls.group_iterator(pattern, mode='roots'):
            if x0 > _x:
                # Yield any atoms between this and the last group
                yield from cls.RGXS['atom'].findall(pattern[_x:x0])
            if x1 > x0:
                # Yield this group
                yield pattern[x0:x1]
            _x = x1

        # Yield any atoms after the last group
        if _x < n:
            yield from cls.RGXS['atom'].findall(pattern[_x:])

    @classmethod
    @ft.lru_cache(maxsize=64)
    def atomize(cls, pattern: str, escape: bool = False) -> Atoms:
        """
        Break a regex pattern into its atomic components.

        Args:
            pattern: Regex pattern string to atomize.
            escape: Whether to escape special regex characters.
        Returns:
            Tuple of atomic regex components (characters, groups, character sets, etc.).
        """
        if escape:
            pattern = cls.RGXS['special_characters'].sub(r'\\\1', pattern)
        return tuple(cls.atomize_iter(pattern))

    @staticmethod
    def _collapse_empty_splits(delims: list[str], sections: list[str]) -> None:
        empty_idxs = list(mi.locate(sections, lambda x: len(x) == 0))
        for i in reversed(empty_idxs):
            if i == len(sections) - 1:
                target = delims if i - 1 in empty_idxs else sections
                target[i - 1] += delims[i]
            else:
                delims[i + 1] = delims[i] + delims[i + 1]
            delims.pop(i)
            sections.pop(i)

    def compose_tuple(self, mark: str, children: RgxList, pre: str = '', suf: str = '') -> str:
        """
        Compose a regex group from a mark, children, and optional prefix/suffix.

        Args:
            mark: Custom mark syntax defining group type and separator.
            children: List of child regex values to compose.
            pre: Optional prefix string to prepend inside the group.
            suf: Optional suffix string to append inside the group.
        Returns:
            Complete regex group string with composed children.
        """
        # 0. For subroutine marks, wrap all children
        if '&' in mark:
            assert all(isinstance(child, str) for child in children)
            children = [f'(?&{child})' for child in children]

        # II. Parse the custom "mark" language into final regex syntax
        kind, start, sep, quant = self._parse_mark(mark)
        end = ')'

        # III. Recursively compose the list component into a single string
        body = self.compose(children, sep)

        # III.ii. Add wrappers to handle surrounding context
        has_context = pre or suf or start[-1] == ')'
        if self._is_split(body):
            if has_context:
                c = '>' if start == '(?>' else ':'
                body = f'(?{c}{body})'
        elif kind in GroupKind._SIMPLE and len(start) == 3 and not quant and not has_context:
            start = end = ''

        # e.g.        '(?:'  '\(?'   '....'   '\)?' ')?'
        return ''.join([start, pre, body, suf, end, quant])

    # -------------------
    # `+` Primary Methods
    # -------------------
    def compose(self, data: RgxVal, sep: str | None = None) -> str:
        """
        Recursively process a flexible definition structure into a single valid regex string.
        Lists are combined using a given (or default) "separator" string, strings and patterns
        are returned as-is, and tuples are used to create new non-capturing groups.
        """
        # I. Catch simple cases: plain strings, pre-composed patterns, and lists of other values
        if not data:
            return ''
        elif isinstance(data, str):
            if self.force_named_groups and '(' in data:
                buf = RgxBuf(data)
                for (x0, _), *_ in self.group_iterator(buf, mask=GroupKind.POSIT):
                    buf.replace((x0, x0 + 1), '(?:')
                data = str(buf)
            if self.formatter:
                data = self.formatter(data)
            return data

        elif isinstance(data, Pattern):
            return data.pattern

        elif isinstance(data, list):
            if sep is None:
                sep = self.separator
            elif sep == '<|>':
                unique_segments = list({self.compose(item, sep='|') for item in data})
                branches = list(self._atomic_split(unique_segments, recursive=True))
                return self.construct_tree(branches)

            return sep.join(map(self.compose, data))

        # II. Handle the main/complex case: a tuple describing a group
        elif isinstance(data, tuple):
            return self.compose_tuple(*self._parse_tuple(data, self.formatter))  # type: ignore

        # III. Special case: an explicitly-specified tuple (likely by a .yaml file)
        elif isinstance(data, dict):
            tup = (data['mark'], data.get('pre', ''), data['body'], data.get('suf', ''))  # type: ignore
            return self.compose_tuple(*self._parse_tuple(tup, self.formatter))

        else:
            raise ValueError(f'Invalid data type: {type(data)}')

    def clean(self, name: str, text: Buffer) -> set[str]:
        """
        Clean and validate a regex pattern, identifying all group dependencies.

        Normalizes group invocation syntax and validates that local group names don't
        conflict with predefined subroutine names.

        Args:
            name: Name of the pattern being cleaned.
            text: Buffer containing the pattern text.
        Returns:
            Set of all group names invoked by this pattern.
        Raises:
            AssertionError: If local group names conflict with predefined groups.
        """
        # I. Replace the convenience syntax with the actual, ugly syntax
        text.replace('(?P=', '(?&')

        # II. Go through all the subroutine calls in the pattern, replacing as we go
        groups_used: set[str] = set()
        local_groups: set[str] = set()

        for _, kind, cname, _, _ in self.group_iterator(text, mask=GroupKind._NAMED):
            if kind == GroupKind.PARAM:
                local_groups.add(cname)
            elif kind == GroupKind.INVOC and cname != name:
                # Intentional reference to a defined subroutine
                assert cname in self.definitions, f'Unknown group invoked: {cname}'
                groups_used.add(cname)

        # III. Recursively fetch dependencies for the used groups
        groups_used = self.find_all_invocations(groups_used)

        # IV. Ensure that any local groups don't conflict with predefined ones
        ambiguous = set.intersection(groups_used, local_groups)
        assert len(ambiguous) == 0, f'Ambiguous groups found: {ambiguous}'
        return groups_used

    def render_definitions(self, *definitions: str) -> str:
        """
        Serialize definitions into a DEFINE block for regex compilation.

        Orders and serializes the specified definitions as a (?(DEFINE)...) block,
        ensuring references to other definitions are resolved in definition order.

        Args:
            *definitions: Names of definitions to include in the DEFINE block.
        Returns:
            String containing the DEFINE block, or empty string if no definitions.
        Raises:
            AssertionError: If any definition name is not found in the store.
        """
        if not definitions:
            return ''
        assert all(name in self.definitions for name in definitions), (
            f'Unknown definitions passed: {definitions}'
        )

        # Render in the order of definition above, not in the order passed in
        data = [(name, rgx) for name, rgx in self.definitions.items() if name in definitions]
        return '\n'.join([r'(?(DEFINE)', *[f'(?P<{name}>{rgx})' for name, rgx in data], ')'])

    def define(
        self,
        name: str,
        val: RgxVal,
        parser: RgxParser | None = None,
        flags: RegexFlag = NO_FLAG,
    ) -> None:
        """
        Define a new named regex pattern in the store.

        Composes the pattern from the given value, cleans and validates it, compiles it
        with any necessary definitions, and stores it along with an optional parser.

        Args:
            name: Unique name for this pattern.
            val: Regex value to compose (string, list, tuple, or Pattern).
            parser: Optional function to parse match results.
            flags: Optional regex flags to apply during compilation.
        Raises:
            AssertionError: If name is already defined.
            Exception: If pattern composition or compilation fails.
        """
        assert name not in self.definitions, f'Duplicate definition: {name}'

        try:
            # I. Compose complex data structures into a string, and apply universal formatting
            raw_text = self.compose(val, self.separator)

            # II. Clean up the pattern and store it as-is, while noticing which groups are used
            text = RgxBuf(raw_text)
            groups_used = self.clean(name, text)
            self.definitions[name] = str(text)

            # III. Compile a finalized version with subroutines attached as 'definitions'
            definitions = self.render_definitions(*groups_used)
            rgx = rf'{definitions}(?P<{name}>{text})'
            self.patterns[name] = re.compile(rgx, flags)

        except Exception as e:
            print(f'Error compiling rgx `{name.upper()}`: {e}')
            if DEBUG:
                if 'rgx' in locals():
                    print(f'\nRENDERED:\n{rgx}\nfrom {groups_used=}')
                elif 'groups_used' in locals():
                    print(f'\nCLEANED:\n{text}\n')
                elif 'raw_text' in locals():
                    print(f'\nCOMPOSED:\n{raw_text}\n')
            raise e

        # III. Store the parser function & regex flags for this group, if present
        if parser:
            self.parsers[name] = parser

        # IV. Cache behavioral triggers when appropriate
        _str = self.definitions[name]

    def autostrip(self, values: list[str] | str) -> list[str]:
        """
        Strip configured characters from values and fix broken brackets.

        Args:
            values: Single string or list of strings to strip.
        Returns:
            List of stripped strings with bracket balancing corrected.
        """
        if not isinstance(values, list):
            values = [values]
        values = list(filter(len, map(self.strip, values)))

        # Check if we removed an actually useful bracket above, and add it back in if so
        if values and self.autostrip_brackets:
            steps = [
                (i, val, brs[0], brs[1])
                for i, val in enumerate(values)
                for brs in [('(', ')'), ('[', ']')]
                if any(map(val.__contains__, brs))
            ]
            for i, value, lb, rb in steps:
                if (ln := value.count(lb)) != (rn := value.count(rb)):
                    values[i] = f'{value}{rb}' if ln > rn else f'{lb}{value}'
        return values

    def sanitize(self, pattern: str | Pattern | Buffer) -> str:
        """
        Sanitize a pattern by normalizing inline flag syntax.

        Args:
            pattern: Pattern to sanitize (string, Pattern, Buffer, or pattern name).
        Returns:
            Sanitized pattern string with normalized flag syntax.
        """
        if isinstance(pattern, Pattern):
            pattern = pattern.pattern
        elif isinstance(pattern, Buffer):
            pattern = str(pattern)
        elif pattern in self.patterns:
            pattern = self.patterns[pattern].pattern
        assert isinstance(pattern, str)

        return ut.replace(
            pattern,
            (self.RGXS['inline_flags'], r'(?:(?\1)'),
        )

    # ------------------
    # `x` Public Methods
    # ------------------
    def keys(self) -> list[str]:
        return list(self.patterns.keys())

    def values(self) -> list[Pattern]:
        return list(self.patterns.values())

    def items(self) -> list[tuple[str, Pattern]]:
        return list(self.patterns.items())

    def read_match(self, match: Match) -> tuple[Params, Captures]:
        """
        Extract and autostrip all captured groups from a match object.

        Args:
            match: Regex match object to read.
        Returns:
            Tuple of (params dict with last values, captures dict with all values).
        """
        data, captures = {}, {}
        if match is not None and (src := match.capturesdict().items()):
            items = [(key, stripped) for key, vals in src if (stripped := self.autostrip(vals))]
            for key, values in items:
                data[key] = values[-1]
                captures[key] = values

        return data, captures

    def parse(self, match: Match | None, pattern_name: str = '') -> MatchData:
        """
        Parse a match object, applying registered parsers and cleaning results.

        Reads the match, applies any parsers registered for captured groups, removes
        hidden fields (those starting with '_'), and returns a clean MatchData object.

        Args:
            match: Match object to parse, or None for empty MatchData.
            pattern_name: Optional name of the pattern that produced this match.
        Returns:
            MatchData object with parsed captures and optional match reference.
        """
        # I. Read the match object, dropping any empty values
        if match is None:
            return MatchData()

        _, captures = self.read_match(match)
        if parseable := list(filter(self.parsers.__contains__, captures.keys())):
            pd = ParseData(captures=captures, starts={f: match.starts(f) for f in captures.keys()})
            for field, parser in [(f, self.parsers[f]) for f in parseable]:
                pd.set_field(field)

                if isinstance(parser, str):
                    pd.interleave(pd.field, parser, list(zip(pd.start, pd.value, strict=True)))
                elif isinstance(parser, dict):
                    pd.apply_dict_parser(parser, self.patterns[field])  # type: ignore
                else:
                    pd.apply_func_parser(parser)
            captures = pd.captures

        # IV. Removed unnecessary "hidden" values
        hidden_fields = [key for key in captures.keys() if key[0] == '_' and key != pattern_name]
        if 0 < len(hidden_fields) < len(captures):
            for field in hidden_fields:
                del captures[field]

        for field in [k for k, v in captures.items() if not v or not any(v)]:
            del captures[field]

        if pattern_name in captures and len(captures) > 1 and pattern_name not in self.parsers:
            del captures[pattern_name]

        # V. Clean and return a datadict and a capturedict
        ret = MatchData(data=captures, match=match)
        return ret

    # Autoparse Overrides
    # -------------------
    def _autoparse(self, func: str, names: Iterable[str], text: str) -> MatchData:
        for name in names:
            if _match := getattr(self.patterns[name], func)(text):
                return self.parse(_match, name)
        return MatchData()

    def match(self, names: str | Iterable[str], text: str | Buffer) -> MatchData:
        """
        Match one of the named patterns against text from the beginning.

        Args:
            names: Pattern name or list of pattern names to try.
            text: Text to match against.
        Returns:
            MatchData from first successful match, or empty MatchData if none match.
        """
        names, text = self._validate_params(names, text)
        return self._autoparse('match', names, text)

    def fullmatch(self, names: str | Iterable[str], text: str | Buffer) -> MatchData:
        """
        Match one of the named patterns against the entire text.

        Args:
            names: Pattern name or list of pattern names to try.
            text: Text to match against.
        Returns:
            MatchData from first successful fullmatch, or empty MatchData if none match.
        """
        names, text = self._validate_params(names, text)
        return self._autoparse('fullmatch', names, text)

    def search(self, names: str | Iterable[str], text: str | Buffer) -> MatchData:
        """
        Search for one of the named patterns anywhere in text.

        Args:
            names: Pattern name or list of pattern names to try.
            text: Text to search.
        Returns:
            MatchData from first successful search, or empty MatchData if none found.
        """
        names, text = self._validate_params(names, text)
        return self._autoparse('search', names, text)

    def finditer(self, name: str, text: str | Buffer, **kwargs) -> Iterator[MatchData]:
        """
        Find all non-overlapping matches of the pattern in text.

        Args:
            name: Pattern name to search for.
            text: Text to search (string or Buffer).
            **kwargs: Optional arguments passed to Buffer.rgx_iterator().
        Yields:
            MatchData objects for each match found.
        """
        rgx = self.patterns[name]
        parse = ft.partial(self.parse, pattern_name=name)
        if isinstance(text, Buffer):
            yield from map(parse, text.rgx_iterator(rgx, **kwargs))
        else:
            assert not kwargs, f'Unexpected kwargs {kwargs} for plain-string "{text[:25]}..."'
            yield from map(parse, rgx.finditer(text))

    def findall(self, name: str, text: str | Buffer, **kwargs) -> list[MatchData]:
        """
        Find all non-overlapping matches of the pattern in text.

        Args:
            name: Pattern name to search for.
            text: Text to search (string or Buffer).
            **kwargs: Optional arguments passed to Buffer.rgx_iterator().
        Returns:
            List of MatchData objects for all matches found.
        """
        return list(self.finditer(name, text, **kwargs))

    def fullsplit(
        self,
        name: str,
        text: str | Buffer,
        collapse: bool = False,
    ) -> tuple[list[str], list[str]]:
        """
        Split text by matches, returning both delimiters and sections.

        Args:
            name: Pattern name to split on.
            text: Text to split.
            collapse: Whether to collapse empty sections into adjacent delimiters.
        Returns:
            Tuple of (delimiters, sections) where delimiters[0] is always empty and
            the lists interleave: section[0], delim[1], section[1], delim[2], etc.
        """
        _, text = self._validate_params(name, text)
        delims, sections = [], []
        if matches := list(self.finditer(name, text)):
            xp = 0
            for x0, x1 in (m.span for m in matches):
                sections.append(text[xp:x0])
                delims.append(text[x0:x1])
                xp = x1
            sections.append(text[xp:])
        else:
            sections = [text]

        if sections:
            delims.insert(0, '')

            # If requested, collapse any empty sections into longer delimiters
            if collapse:
                self._collapse_empty_splits(delims, sections)

        return delims, sections

    def polymatch(self, name: str, text: str | Buffer) -> MatchData:
        """
        Find all matches and merge their captures into a single MatchData.

        Unlike findall which returns separate MatchData objects, this merges all
        captures from all matches into one result, preserving order by start position.

        Args:
            name: Pattern name to search for.
            text: Text to search (automatically converted to Buffer).
        Returns:
            Single MatchData with all captures from all matches merged.
        """
        pd = ParseData()
        if isinstance(text, str):
            text = RgxBuf(text)

        for match in text.rgx_iterator(self.patterns[name]):
            for field, values in self.parse(match, name).items():
                starts = match.starts(field)
                if field not in pd:
                    pd.captures[field] = values
                    pd.starts[field] = starts
                else:
                    pd.interleave('', field, list(zip(starts, values, strict=True)))

        return MatchData(data=pd.captures)

    # Utility functions
    # -----------------
    def parse_invocations(self, text: str) -> set[str]:
        """
        Find all group invocations in text and transitively expand dependencies.

        Args:
            text: Regex pattern text to analyze.
        Returns:
            Set of all group names invoked directly or indirectly.
        """
        invocations = {name for _, _, name, _, _ in self.group_iterator(text, mask=GroupKind.INVOC)}
        return self.find_all_invocations(invocations)

    def partial(
        self,
        name: str,
        func: Literal['match', 'fullmatch', 'search', 'polymatch'] = 'match',
    ) -> Callable[[str | Buffer], MatchData]:
        """
        Create a partially applied matching function for a pattern.

        Args:
            name: Pattern name to use.
            func: Matching function name ('match', 'fullmatch', 'search', or 'polymatch').
        Returns:
            Function that takes text and returns MatchData using the specified pattern.
        """
        return ft.partial(getattr(self, func), name)

    def apply(
        self,
        name: str,
        texts: Iterable[str],
        func: Literal['match', 'fullmatch', 'search', 'polymatch'] = 'match',
    ) -> Iterable[MatchData]:
        """
        Apply a pattern to multiple texts.

        Args:
            name: Pattern name to use.
            texts: Iterable of text strings to match against.
            func: Matching function to use ('match', 'fullmatch', 'search', or 'polymatch').
        Yields:
            MatchData objects for each text in order.
        """
        yield from map(self.partial(name, func), texts)

    def filter(
        self,
        name: str,
        texts: Iterable[str],
        func: Literal['match', 'fullmatch', 'search', 'polymatch'] = 'match',
    ) -> Iterable[str]:
        """
        Filter texts by whether they match a pattern.

        Args:
            name: Pattern name to test against.
            texts: Iterable of text strings to filter.
            func: Matching function to use ('match', 'fullmatch', 'search', or 'polymatch').
        Yields:
            Only those texts that successfully match the pattern.
        """
        fn = self.partial(name, func)
        yield from filter(lambda text: bool(fn(text)), texts)

    # Builder Functions
    # -----------------
    def define_router_tree(self, router: str, items: Mapping[str, RgxVal], **kwargs: str) -> None:
        """
        Define a router pattern that classifies text into named categories.

        Creates two patterns: one optimized router (<router>) and one with route tracking
        (<router>_router) that captures which category matched.

        Args:
            router: Base name for the router patterns.
            items: Mapping of category names to their regex patterns.
            **kwargs: Optional 'prefix'/'suffix' or 'p0'/'p1'/'s0'/'s1' for wrapping patterns.
        Raises:
            AssertionError: If router name is already defined.
        """
        assert router not in self.routers, f'Duplicate router name: {router}'
        items = {k: v for k, v in items.items() if v}
        self.routers[router] = list(items.keys())

        if prefix := kwargs.pop('prefix', ''):
            p0 = p1 = prefix
        else:
            p0 = kwargs.get('p0', '')
            p1 = kwargs.get('p1', '')

        if suffix := kwargs.pop('suffix', ''):
            s0 = s1 = suffix
        else:
            s0 = kwargs.get('s0', '')
            s1 = kwargs.get('s1', '')

        self[router] = ('<|>', p0, list(items.values()), s0)

        routes = [
            (i, rgx if isinstance(rgx, list) else [rgx]) for i, rgx in enumerate(items.values())
        ]
        self[f'{router}_router'] = ('|:', p1, [(f'<|>P<rt_{i}>', rgx) for i, rgx in routes], s1)

    def route_match(self, router: str, text: str | MatchData) -> str:
        """
        Determine which category a text matches in a router tree.

        Args:
            router: Name of router pattern to use.
            text: Text to classify, or MatchData from previous match.
        Returns:
            Name of the matching category, or empty string if no match.
        Raises:
            AssertionError: If router name is not found.
        """
        assert router in self.routers, f'Unknown router: {router}'
        if isinstance(text, MatchData):
            text = text.text

        data = self.fullmatch(f'{router}_router', text)
        if raw_idx := next((name[3:] for name in data.keys() if name.startswith('rt_')), ''):
            assert raw_idx.isdigit(), f'Invalid router index: {raw_idx}'
            return self.routers[router][int(raw_idx)]
        return ''

    def expand_match(self, router: str, text: str | MatchData) -> str:
        """
        Match text against a router and expand using the matched category's format.

        Args:
            router: Name of router pattern to use.
            text: Text to match and expand, or MatchData from previous match.
        Returns:
            Expanded string using the matched category name as format string.
        Raises:
            AssertionError: If router name is not found or match object is invalid.
        """
        assert router in self.routers, f'Unknown router: {router}'
        if isinstance(text, MatchData):
            text = text.text

        data = self.fullmatch(f'{router}_router', text)
        if raw_idx := next((name[3:] for name in data.keys() if name.startswith('rt_')), ''):
            assert raw_idx.isdigit(), f'Invalid router index: {raw_idx}'
            fmt = self.routers[router][int(raw_idx)]

            assert data.match is not None, 'Invalid match object'
            return data.match.expandf(fmt)

        return ''
