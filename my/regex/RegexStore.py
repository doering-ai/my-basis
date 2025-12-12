############
### HEAD ###
############
### STANDARD
from typing import Iterable, Iterator, Literal, ClassVar, Any, Callable, Mapping, Self
import functools as ft

### EXTERNAL
import more_itertools as mi
import pydantic as pyd
import regex as re
from regex import Match, Pattern, RegexFlag

### INTERNAL
from ..utils import ut
from ..types import Buffer
from ..typing import typist
from .meta import Atom, Atoms, Block, GroupKind, META_RGXS
from .MatchData import MatchData
from .ParseData import ParseData

############
### DATA ###
############
# --------------
# Public Aliases
# --------------
RgxParser = (
    str  # base case: Simply renames the output
    | Callable[[str], str]  # 1st case: returns some subset to the same name
    | Callable[[str], dict[str, str]]  # 2nd case: returns to any number of other names
    | Callable[[str], dict[str, str] | str]  # 3rd case: combo of above two
)

RgxTup = tuple[str, 'RgxList'] | tuple[str, str, 'RgxList', str]
RgxList = list['RgxVal']
RgxVal = str | RgxList | RgxTup | Pattern | dict
RgxDef = (
    # Raw/simple content
    (str | tuple[str, RgxParser])
    # Single piece of uncompiled content
    | (RgxTup | tuple[RgxTup, RgxParser])
    # Series of uncompiled content
    | (RgxList | tuple[RgxList, RgxParser])
    # Precompiled content
    | (Pattern | tuple[Pattern, RgxParser])
)

# A buffer built to hold Regex patterns
RegexBuffer = ft.partial(Buffer.new, fence_rgxs=['arrays'])


# ---------
# Constants
# ---------
DEBUG = False
NO_FLAG = RegexFlag(0)


############
### BODY ###
############
class RegexStore(pyd.BaseModel):
    """
    A powerful regex pattern management system with composition and parsing capabilities.

    RegexStore provides a comprehensive framework for defining, composing, and applying
    complex regex patterns.
    To do this, it also contains code for analyzing existing patterns, breaking them down into their
    component parts.

    Features:
        - Hierarchical pattern composition from simple building blocks.
        - Recursive pattern references via named groups.
        - Ergonomic group management and subroutine invocation.
        - Automatic parsing of match results into a more ergonomic form (see MatchData).
        - Pattern optimization applied by default.
        - Construction of "Router trees" for efficient matching of long patterns to long texts.

    The DSL used to specify patterns can combine a variety of input types into one, including:
        - String literals and pre-compiled patterns.
        - Tuples for group creation with custom separators.
        - Lists for sequential composition of groups.
    """

    # ----------------
    # Meta Expressions
    # ----------------
    META_RGXS: ClassVar[dict[str, re.Pattern]] = META_RGXS

    # --------------
    # Public Members
    # --------------
    # Uncompiled expressions, ready for reuse
    definitions: dict[str, str] = {}

    # Compiled expressions, ready for invocation
    patterns: dict[str, Pattern] = {}

    # Expression-specific parsers of match data
    parsers: dict[str, RgxParser] = {}
    routers: dict[str, list[str]] = {}

    # Private Members
    strip: Callable[[str], str] = pyd.Field(default=lambda x: x, exclude=True)

    # -------------
    # Store Options
    # -------------
    class Options(pyd.BaseModel):
        # Convenience options
        init_formatter: Callable[..., str] | None = None
        formatter: Callable[..., str] | None = None
        separator: str = r' *'
        force_named_groups: bool = False

        # Autostrip behavior
        autostrip_spaces: bool = True
        autostrip_brackets: bool = False
        autostrip_commas: bool = False

    options: Options = pyd.Field(default_factory=Options)

    # -------------------
    # `0` Initial Methods
    # -------------------
    @classmethod
    def new(
        cls,
        options: dict[str, Any] | Options | None = None,
        imports: list[tuple[Self, Iterable[str]]] | None = None,
        **definitions: RgxDef | Any,
    ) -> Self:
        """
        This is the primary interface for creating new stores, allowing callers to specify their
        patterns upfront as direct arguments to this function.

        Args:
            options: A dictionary of store-level options to apply as member variables.
            imports: References to patterns contianed in existing stores to be included in this one
            **definitions: The named pattern specifications (see RgxDef) that make up the new store.
        Returns:
            A new RegexStore instance with the given patterns compiled into execution-ready objects.
        """
        # I. Initialize the store with the requested options before any compilation is done
        if not options:
            options = cls.Options()
        elif isinstance(options, dict):
            options = cls.Options(**options)
        store = cls(options=options)

        # II. Import the requested patterns from other stores
        for source, names in imports or []:
            for name in source.find_all_invocations(set(names)):
                store.definitions[name] = source.definitions[name]
                store.patterns[name] = source.patterns[name]
                if name in source.parsers:
                    store.parsers[name] = source.parsers[name]

        if store.init_formatter is not None:
            # III.i. Preformat the given definitions with the user-defined formatter function
            definitions = {
                name: (store.init_formatter(dfn) if not isinstance(dfn, Pattern) else dfn)
                for name, dfn in definitions.items()
            }
            for name, val in definitions.items():
                store.define(name, val, None)
        else:
            # III.ii. Just set the values of the store
            for name, _def in definitions.items():
                store[name] = _def

        return store

    @pyd.field_validator('definitions')
    @classmethod
    def _init_definitions(cls, definitions: dict[str, str]) -> dict[str, str]:
        """Clean the passed definitions by normalizing group reference syntax."""
        return {key: val.replace('(?P=', '(?&') for key, val in definitions.items()}

    @pyd.model_validator(mode='after')
    def _process_options(self) -> Self:
        """Finalize the store by setting up the autostrip function based on member variables."""
        strip_string = ''
        if self.options.autostrip_spaces:
            strip_string += ' '
        if self.options.autostrip_brackets:
            strip_string += '()[]'

        if self.options.autostrip_commas:
            strip_string += ','

        if strip_string:
            self.strip = lambda text: text.strip(strip_string) or text
        else:
            self.strip = lambda text: text

        return self

    # -------------------
    # `-` Private Methods
    # -------------------
    def _read_match(self, match: Match) -> tuple[dict[str, str], dict[str, list[str]]]:
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

    @classmethod
    def _tree_print(cls, text: str, depth: int = 0) -> str:
        """
        Recursive helper for tree_print, handling indentation and group structure.

        Args:
            text: The regex pattern body to print.
            depth: Current indentation depth.
        Returns:
            Multi-line string representation with indentation showing nesting.
        """
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
        Pretty-print a regex pattern as an indented multiline tree structure, primarily for use
        in debugging.

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
        buffer = RegexBuffer()
        new_groups: set[str] = set()
        for existing_group in groups_used:
            buffer.set(self.definitions[existing_group])
            group_names = {
                name for _, _, name, _, _ in Atom.group_iterator(buffer, mask=GroupKind.INVOC)
            }
            new_groups |= group_names - groups_used

        if new_groups:
            return groups_used | self.find_all_invocations(new_groups)
        else:
            return groups_used

    def _parse_mark(self, mark: str) -> tuple[GroupKind, str, str, str]:
        """
        Parses a given string of "mark syntax" DSL (see class documentation) into valid regex
        snippets.

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
        match = META_RGXS['struct_mark'].fullmatch(mark)
        assert match, f'Invalid mark: {mark}, {META_RGXS["struct_mark"].pattern}'
        data, _ = self._read_match(match)

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
            sep = self.options.separator

        # Override this group, which is used by the caller to wrap children
        if group == '&':
            group = ':'
        start = f'(?{group}' if group else '('
        kind = GroupKind.read(start)
        if flags := data.pop('flags', ''):
            start = f'(?{flags}:' if kind == GroupKind.PLAIN else f'{start}(?{flags})'

        return kind, start, sep, quant

    def _validate_automatch_params(
        self,
        patterns: str | Iterable[str],
        text: str | Buffer,
    ) -> tuple[Iterable[str], str]:
        """
        Validate, clean, and/or coerce the usual public paramaters of the constructor.

        Args:
            patterns: Pattern name(s) to validate.
            text: Text to coerce to string if necessary.
        Returns:
            (validated_patterns, cleaned_text_string)
        """
        if isinstance(patterns, str):
            patterns = [patterns]
        assert ut.has_all(self.patterns, *patterns), f'Unknown pattern(s): {patterns}'
        return patterns, str(text) if isinstance(text, Buffer) else text

    def _parse_tuple(self, data: RgxTup) -> tuple[str, RgxList, str, str]:
        if (n := len(data)) == 2:
            assert typist.tuple_is(data, tuple[str, list]), f'Invalid group spec: {data}'
            mark, children = data  # type: ignore
            return mark, children, '', ''
        elif n == 4:
            assert typist.tuple_is(data, tuple[str, str, list, str]), (
                f'Invalid group spec (w/ prefix & suffix): {data}'
            )
            mark, prefix, children, suffix = data  # type: ignore
            # The prefix and suffix weren't formatted upfront
            if self.options.formatter is not None:
                prefix, suffix = map(self.options.formatter, (prefix, suffix))
            return mark, children, prefix, suffix
        else:
            raise ValueError(f'Invalid group spec (bad length of {n=}, should be 2 or 4): {data}')

    @staticmethod
    def _collapse_empty_sections(delims: list[str], sections: list[str]) -> None:
        """
        Remove any empty sections in the given delimited fullsplit(). Modifies arguments.

        Args:
            delims: List of delimiters.
            sections: List of sections.
        """
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

        # I. Parse the custom "mark" language into final regex syntax
        kind, start, sep, quant = self._parse_mark(mark)
        end = ')'

        # II. Recursively compose the list component into a single string
        body = self.compose(children, sep)

        # III. Add wrappers to handle surrounding context
        has_context = pre or suf or start[-1] == ')'
        if Atoms.is_split(body):
            if has_context:
                # III.i. Split groups with context must be wrapped in a non-capturing group
                c = '>' if start == '(?>' else ':'
                body = f'(?{c}{body})'
        elif kind in GroupKind._SIMPLE and len(start) == 3 and not quant and not has_context:
            # III.ii. Non-split, simple, unquantified groups can drop the wrapping entirely
            start = end = ''

        # e.g.          (?:    \(?  ...   \)?  )    ?
        return ''.join([start, pre, body, suf, end, quant])

    def _render_definitions(self, *definitions: str) -> str:
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

    def _autoparse(self, func: str, names: Iterable[str], text: str) -> MatchData:
        for name in names:
            if _match := getattr(self.patterns[name], func)(text):
                return self.parse(_match, name)
        return MatchData()

    # -------------------
    # `+` Primary Methods
    # -------------------
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

        _, captures = self._read_match(match)
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
            if self.options.force_named_groups and '(' in data:
                # I.i. Force all anonynmous groups (i.e. kind=POSIT) to be non-capturing
                buf = RegexBuffer(data)
                for (x0, _), *_ in Atom.group_iterator(buf, mask=GroupKind.POSIT):
                    buf.replace((x0, x0 + 1), '(?:')
                data = str(buf)
            if self.options.formatter:
                # I.ii. Format the final string if requested
                data = self.options.formatter(data)
            return data

        elif isinstance(data, Pattern):
            # I.ii. Extract the (raw) expressions behind (compiled) patterns
            return data.pattern

        elif isinstance(data, list):
            if sep is None:
                sep = self.options.separator
            elif sep == '<|>':
                root_branches = [self.compose(item, sep='|') for item in data]
                return str(Block.construct_tree(root_branches))

            return sep.join(map(self.compose, data))

        # II. Handle the main/complex case: a tuple describing a group
        elif isinstance(data, tuple):
            return self.compose_tuple(*self._parse_tuple(data))

        # III. Special case: an explicitly-specified tuple (likely by a .yaml file)
        elif isinstance(data, dict):
            tup = (data['mark'], data.get('pre', ''), data['body'], data.get('suf', ''))  # type: ignore
            return self.compose_tuple(*self._parse_tuple(tup))

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

        for _, kind, cname, _, _ in Atom.group_iterator(text, mask=GroupKind._NAMED):
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
            raw_text = self.compose(val, self.options.separator)

            # II. Clean up the pattern and store it as-is, while noticing which groups are used
            text = RegexBuffer(raw_text)
            groups_used = self.clean(name, text)
            self.definitions[name] = str(text)

            # III. Compile a finalized version with subroutines attached as 'definitions'
            definitions = self._render_definitions(*groups_used)
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
        if values and self.options.autostrip_brackets:
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

    # ------------------
    # `x` Public Methods
    # ------------------
    # --------------
    # `x0` Overrides
    # --------------
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
            val = param  # type: ignore
            parser = None

        self.define(name, val, parser)  # type: ignore

    def __getitem__(self, name: str) -> Pattern:
        assert name in self.patterns, f'Pattern not found: {name}'
        return self.patterns[name]

    def __ior__(self, other: 'dict[str, RgxDef] | RegexStore') -> 'RegexStore':
        if isinstance(other, RegexStore):
            for name in other.keys():
                self[name] = (other.definitions[name], other.parsers.get(name, None))
        else:
            for name, param in other.items():
                self[name] = param
        return self

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

    def keys(self) -> list[str]:
        return list(self.patterns.keys())

    def values(self) -> list[Pattern]:
        return list(self.patterns.values())

    def items(self) -> list[tuple[str, Pattern]]:
        return list(self.patterns.items())

    # -------------------------------
    # `x1` Top-Level Matching Methods
    # -------------------------------
    def match(self, names: str | Iterable[str], text: str | Buffer) -> MatchData:
        """
        Match one of the named patterns against text from the beginning.

        Args:
            names: Pattern name or list of pattern names to try.
            text: Text to match against.
        Returns:
            MatchData from first successful match, or empty MatchData if none match.
        """
        names, text = self._validate_automatch_params(names, text)
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
        names, text = self._validate_automatch_params(names, text)
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
        names, text = self._validate_automatch_params(names, text)
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
        _, text = self._validate_automatch_params(name, text)
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
                self._collapse_empty_sections(delims, sections)

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
            text = RegexBuffer(text)

        for match in text.rgx_iterator(self.patterns[name]):
            for field, values in self.parse(match, name).items():
                starts = match.starts(field)
                if field not in pd:
                    pd.captures[field] = values
                    pd.starts[field] = starts
                else:
                    pd.interleave('', field, list(zip(starts, values, strict=True)))

        return MatchData(data=pd.captures)

    # -------------------------
    # `x2` Functional Utilities
    # -------------------------
    def parse_invocations(self, text: str) -> set[str]:
        """
        Find all group invocations in text and transitively expand dependencies.

        Args:
            text: Regex pattern text to analyze.
        Returns:
            Set of all group names invoked directly or indirectly.
        """
        invocations = {name for _, _, name, _, _ in Atom.group_iterator(text, mask=GroupKind.INVOC)}
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

    # ---------------------------------------
    # `x3` Performant "Router Tree" Functions
    # ---------------------------------------
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

    # ---------
    # `x4` Misc
    # ---------
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
            (META_RGXS['inline_flags'], r'(?:(?\1)'),
        )

    @classmethod
    def split(cls, pattern: str | Atoms | list[str], recursive: bool = False) -> list[str]:
        return list(map(''.join, cls._atomic_split(pattern, recursive)))
