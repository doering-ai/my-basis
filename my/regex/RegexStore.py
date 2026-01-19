############
### HEAD ###
############
### STANDARD
from typing import Literal, ClassVar, Any, Self, Annotated
from collections.abc import Iterable, Iterator, Callable, Mapping
from collections import deque
import functools as ft
import contextlib as ctx
from threading import Lock

### EXTERNAL
import more_itertools as mi
import pydantic as pyd
import regex as re
from regex import Match, Pattern, RegexFlag

### INTERNAL
from ..utils import ut
from ..types import Buffer
from ..typing import typist
from .meta import ParseData, Atom, GroupAtom, Regex, Tree, GroupKind, META_RGXS
from .MatchData import MatchData

############
### DATA ###
############
# --------------
# Public Aliases
# --------------
RegexParser = (
    str  # base case: Simply renames the output
    | Callable[[str], str]  # 1st case: returns some subset to the same name
    | Callable[[str], dict[str, str]]  # 2nd case: returns to any number of other names
    | Callable[[str], dict[str, str] | str]  # 3rd case: combo of above two
)

RegexTup = tuple[str, 'RegexList'] | tuple[str, str, 'RegexList', str]
RegexList = list['RegexVal']
RegexVal = str | RegexList | RegexTup | Pattern | dict
RegexDef = (
    # Raw/simple content
    (str | tuple[str, RegexParser])
    # Single piece of uncompiled content
    | (RegexTup | tuple[RegexTup, RegexParser])
    # Series of uncompiled content
    | (RegexList | tuple[RegexList, RegexParser])
    # Precompiled content
    | (Pattern | tuple[Pattern, RegexParser])
)

# A buffer built to hold Regex patterns
RegexBuffer = ft.partial(Buffer.new, fence_rgxs=['arrays'])

# Allowed regex search functions
RegexFunction = Literal['match', 'fullmatch', 'search', 'polymatch']


# ---------
# Constants
# ---------
DEBUG = False
NO_FLAG = RegexFlag(0)

LockField = Annotated[Lock, ut.pyd_schemify(Lock)]


############
### BODY ###
############
class RegexStore(pyd.BaseModel):
    """A powerful regex pattern management system with composition and parsing capabilities.

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

    # -------
    # Members
    # -------
    # Uncompiled expressions, ready for reuse
    definitions: dict[str, str] = {}

    # Compiled expressions, ready for invocation
    patterns: dict[str, ut.RegexField] = {}

    # Expression-specific parsers of match data
    parsers: dict[str, RegexParser] = {}
    routers: dict[str, list[str]] = {}

    # Function used to clean matched strings
    strip: Callable[[str], str] = pyd.Field(default=lambda x: x, exclude=True)
    lazy_queue: deque[Callable[[], None]] = pyd.Field(default_factory=deque, exclude=True)
    is_loaded: bool = pyd.Field(default=True, exclude=True)
    load_lock: LockField = pyd.Field(default_factory=Lock, exclude=True)

    # -------------
    # Store Options
    # -------------
    class Options(pyd.BaseModel):
        """Configuration options for RegexStore behavior -- must be set at initialization time."""

        # Convenience options
        init_formatter: Callable[..., str] | None = None
        formatter: Callable[..., str] | None = None
        separator: str = r' *'
        force_named_groups: bool = False
        force_reinvocations: bool = True
        lazy_load: bool = True

        # Autostrip behavior
        autostrip_spaces: bool = True
        autostrip_brackets: bool = False
        autostrip_commas: bool = False

    options: Options = pyd.Field(default_factory=Options)

    # -------------------
    # `.` Initial Methods
    # -------------------
    @classmethod
    def new(
        cls,
        options: dict[str, Any] | Options | None = None,
        imports: list[tuple[Self, Iterable[str]]] | None = None,
        **definitions: RegexDef | Any,
    ) -> Self:
        """Create a new store, likely specifying almost all your patterns upfront.

        Args:
            options: A dictionary of store-level options to apply as member variables.
            imports: References to patterns contianed in existing stores to be included in this one
            **definitions: A dictionary of named regular expressions -- see RegexDef.
        Returns:
            A new RegexStore instance with the given patterns compiled into execution-ready objects.
        """
        # I. Initialize the store with the requested options before any compilation is done
        if not options:
            options = cls.Options()
        elif isinstance(options, dict):
            options = cls.Options(**options)
        store = cls(options=options)

        _init_load = ft.partial(store.initial_load, imports=imports, definitions=definitions)
        if store.options.lazy_load:
            store.lazy_queue.append(_init_load)
            store.is_loaded = False
        else:
            _init_load()

        return store

    def initial_load(
        self,
        imports: list[tuple[Self, Iterable[str]]] | None,
        definitions: dict[str, RegexDef | Any],
    ) -> None:
        """Initial loading of patterns into the store, including imports and formatting."""
        # II. Import the requested patterns from other stores
        if imports:
            for source, names in imports:
                for name in source.find_all_invocations(set(names)):
                    self.definitions[name] = source.definitions[name]
                    self.patterns[name] = source.patterns[name]
                    if name in source.parsers:
                        self.parsers[name] = source.parsers[name]

        # III. Preformat the given definitions with the user-defined formatter function
        if (fn := self.options.init_formatter) is not None:
            definitions = ut.val_map(ft.partial(self.format_definition, fn=fn), definitions)

        # IV. Set the values of the store
        for name, val in definitions.items():
            self[name] = val

    def load(self) -> None:
        """Load all lazy definitions into the store now."""
        if not self.is_loaded:
            with self.load_lock:
                while self.lazy_queue:
                    fn = self.lazy_queue.popleft()
                    fn()
                self.is_loaded = True

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

        if self.options.force_reinvocations:
            self.definitions = {
                key: val.replace('(?P=', '(?P>') for key, val in self.definitions.items()
            }

        return self

    # -------------------
    # `-` Private Methods
    # -------------------
    @classmethod
    def format_definition(cls, fn: Callable[..., str], value: RegexDef) -> RegexDef:
        """Apply a formatting function to a regex definition value, if possible."""
        if isinstance(value, Pattern):
            pass
        elif isinstance(value, tuple) and len(value) == 2 and callable(value[1]):
            val, parser = value  # type: ignore
            if isinstance(val, str):
                with ctx.suppress(Exception):
                    return (fn(val), parser)
        else:
            with ctx.suppress(Exception):
                return fn(value)
        return value

    def _read_match(self, match: Match) -> tuple[dict[str, str], dict[str, list[str]]]:
        """Extract and autostrip all captured groups from a match object.

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
    def _tree_print(
        cls,
        expr: Regex | str | Atom,
        depth: int = 0,
        maxdepth: int = 0,
        threshold: int = 48,
    ) -> str:
        """Recursive helper for tree_print, handling indentation and group structure.

        Args:
            expr: The regex expression to print.
            depth: Current indentation depth.
            maxdepth: Maximum depth to recurse (0 for unlimited).
            threshold: Minimum length of group body to consider for splitting.
        Returns:
            Multi-line string representation with indentation showing nesting.
        """
        if maxdepth > 0 and depth >= maxdepth:
            return f'\t{expr}'

        sections: list[str] = []
        block = Tree.new(expr)
        for branch in block.branches:
            lines: list[str] = []
            for atom in branch:
                if isinstance(atom, GroupAtom) and (Regex.is_split(atom) or len(atom) > threshold):
                    lines.extend(
                        [
                            atom.start,
                            cls._tree_print(atom.body, depth + 1, maxdepth, threshold),
                            f'){atom.quantifier}',
                        ]
                    )
                else:
                    lines.append(str(atom))
            if lines:
                if depth > 0:
                    lines = [f'\t{line}' for line in lines]
                sections.append('\n'.join(lines))
        return r'|\n'.join(sections)

    def _parse_mark(self, mark: str) -> tuple[GroupKind, str, str, str]:
        """Parses a given string of "mark syntax" DSL into valid regex snippets.

        Args:
            mark: Custom mark string using the store's DSL syntax.
        Returns:
            1. GroupKind enum value
            2. Opening group syntax (e.g., `(?:`, `(?>`)
            3. String to join children (defaults to self.separator)
            4. Quantifier string (e.g., `?`, `+`, `*`)
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
        """Validate, clean, and/or coerce the usual public paramaters of the constructor.

        Args:
            patterns: Pattern name(s) to validate.
            text: Text to coerce to string if necessary.
        Returns:
            (validated_patterns, cleaned_text_string)
        """
        self.load() if not self.is_loaded else None
        if isinstance(patterns, str):
            patterns = [patterns]
        assert ut.has_all(self.patterns, *patterns), f'Unknown pattern(s): {patterns}'
        return patterns, str(text) if isinstance(text, Buffer) else text

    def _parse_tuple(self, data: RegexTup) -> tuple[str, RegexList, str, str]:
        if (n := len(data)) == 2:
            assert typist.check(data, tuple[str, list]), f'Invalid group spec: {data}'
            mark, children = data
            return mark, children, '', ''
        elif n == 4:
            assert typist.check(data, tuple[str, str, list, str]), (
                f'Invalid group spec (w/ prefix & suffix): {data}'
            )

            mark, prefix, children, suffix = data
            # The prefix and suffix weren't formatted upfront
            if self.options.formatter is not None:
                prefix, suffix = map(self.options.formatter, (prefix, suffix))
            return mark, children, prefix, suffix
        else:
            raise ValueError(f'Invalid group spec (bad length of {n=}, should be 2 or 4): {data}')

    @staticmethod
    def _collapse_empty_sections(delims: list[str], sections: list[str]) -> None:
        """Remove any empty sections in the given delimited fullsplit(). Modifies arguments.

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

    def _render_definitions(self, *definitions: str) -> str:
        """Serialize definitions into a DEFINE block for regex compilation.

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
        """Helper function for parsing the outputs from a typical regex call.

        Args:
            func: Name of the regex function to call (e.g., 'match', 'search').
            names: Names of patterns to try in order.
            text: Text to apply the patterns to.
        Returns:
            MatchData object with the first successful match's data, or empty if none matched.
        """
        for name in names:
            if _match := getattr(self.patterns[name], func)(text):
                return self.parse(_match, name)
        return MatchData()

    def find_all_invocations(self, groups_used: set[str]) -> set[str]:
        """Recursively find all groups invoked by the given set of groups.

        Args:
            groups_used: Initial set of group names to analyze.
        Returns:
            Complete set of all groups transitively invoked by the initial set.
        """
        buffer = RegexBuffer()
        new_groups: set[str] = set()
        for existing_group in groups_used:
            buffer.set(self.definitions[existing_group])
            groups_invoked = {g.name for g in Regex.group_iterator(buffer, mask=GroupKind.INVOC)}
            new_groups |= groups_invoked - groups_used

        if new_groups:
            return groups_used | self.find_all_invocations(new_groups)
        else:
            return groups_used

    def compose_group(self, mark: str, children: RegexList, pre: str = '', suf: str = '') -> str:
        """Compose a regex group from a mark, children, and optional prefix/suffix.

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
        if Regex.is_split(body):
            if has_context:
                # III.i. Split groups with context must be wrapped in a non-capturing group
                c = '>' if start == '(?>' else ':'
                body = f'(?{c}{body})'
        elif kind in GroupKind._SIMPLE and len(start) == 3 and not quant and not has_context:
            # III.ii. Non-split, simple, unquantified groups can drop the wrapping entirely
            start = end = ''

        # e.g.          (?:    \(?  ...   \)?  )    ?
        return ''.join([start, pre, body, suf, end, quant])

    def compose_tree(self, data: RegexList) -> str:
        """Compose an optimized/"condensed" version of the give regex branches.

        Args:
            data: List of branched regex expressions.
        Return:
            The corresponding optimized branching tree regex expression.
        """
        # 0. Finish composing definitions below this one into valid expressions
        rendered_branches = [self.compose(branch, sep='|') for branch in data]

        # I. Initialize a "block" object containing these branches
        block = Tree.new(*sorted(rendered_branches))

        # II. Recursively "expand" all the branches, replacing them with more verbose equivalents
        block.expand()

        # III. Recursively "condense" the expanded branches by factoring out shared elements
        block.condense()

        # IV. Return the rendered union of these branches (e.g. `(?:a|b|c)`)
        return str(block.render())

    # -------------------
    # `+` Primary Methods
    # -------------------
    def parse(self, match: Match | None, pattern_name: str = '') -> MatchData:
        """Parse a match object, applying registered parsers and cleaning results.

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

    @ft.singledispatchmethod
    def compose(self, data: RegexVal, sep: str | None = None) -> str:
        """Recursively transform a DSL-compliant definition into a valid regular expression.

        Args:
            data: The regex value to compose.
            sep: Optional separator string for lists (defaults to store's separator).
        Returns:
            The composed expression.
        """
        if not data:
            return ''
        raise NotImplementedError(f'Unsupported data type: {type(data)}')

    @compose.register
    def _compose_string(self, data: str, sep: str | None = None) -> str:
        # I.i. Change all positional capture groups to non-capturing
        if self.options.force_named_groups and '(' in data:
            buf = RegexBuffer(data)
            for group in Regex.group_iterator(buf, mask=GroupKind.POSIT):
                buf.insert(group.span[0] + 1, '?:')
            data = str(buf)

        # I.ii. Format the final string if requested
        if self.options.formatter:
            data = self.options.formatter(data)
        return data

    @compose.register
    def _compose_pattern(self, data: Pattern, sep: str | None = None) -> str:
        # I.ii. Extract the (raw) expressions behind (compiled) patterns
        return data.pattern

    @compose.register
    def _compose_list(self, data: list, sep: str | None = None) -> str:
        if sep is None:
            sep = self.options.separator
        elif sep == '<|>':
            return self.compose_tree(data)

        return sep.join(map(self.compose, data))

    @compose.register
    def _compose_tuple(self, data: tuple, sep: str | None = None) -> str:
        # II. Handle the main/complex case: a tuple describing a group
        return self.compose_group(*self._parse_tuple(data))

    @compose.register
    def _compose_dict(self, data: dict, sep: str | None = None) -> str:
        # III. Special case: an explicitly-specified tuple (likely by a .yaml file)
        tup = (
            data.get('mark', ''),
            data.get('pre', ''),
            data.get('body', []),
            data.get('suf', ''),
        )
        return self.compose_group(*self._parse_tuple(tup))

    def clean(self, name: str, text: Buffer) -> set[str]:
        """Clean and validate a regex pattern, identifying all group dependencies.

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
        if self.options.force_reinvocations:
            text.replace('(?P=', '(?P>')

        # II. Go through all the subroutine calls in the pattern, replacing as we go
        groups_used: set[str] = set()
        local_groups: set[str] = set()

        for group in Regex.group_iterator(text, mask=GroupKind._NAMED):
            if group.kind == GroupKind.PARAM:
                local_groups.add(group.name)
            elif group.kind == GroupKind.INVOC and group.name != name:
                # Intentional reference to a defined subroutine
                assert group.name in self.definitions, f'Unknown group invoked: {group.name}'
                groups_used.add(group.name)

        # III. Recursively fetch dependencies for the used groups
        groups_used = self.find_all_invocations(groups_used)

        # IV. Ensure that any local groups don't conflict with predefined ones
        ambiguous = set.intersection(groups_used, local_groups)
        assert len(ambiguous) == 0, f'Ambiguous groups found: {ambiguous}'
        return groups_used

    def define(
        self,
        name: str,
        val: RegexVal,
        parser: RegexParser | None = None,
        flags: RegexFlag = NO_FLAG,
    ) -> None:
        """Define a new named regex pattern in the store.

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
            try:
                self.patterns[name] = re.compile(rgx, flags)
            except Exception:
                print(f'Failed to compile rgx `{name.upper()}`:\n{rgx}\n')
                raise

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
        """Strip configured characters from values and fix broken brackets.

        Args:
            values: Single string or list of strings to strip.
        Returns:
            List of stripped strings with bracket balancing corrected.
        """
        if not isinstance(values, list):
            values = [values]
        values = list(filter(bool, map(self.strip, values)))

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

    def parse_invocations(self, text: str) -> set[str]:
        """Find all group invocations in text and transitively expand dependencies.

        Args:
            text: Regex pattern text to analyze.
        Returns:
            Set of all group names invoked directly or indirectly.
        """
        invocations = {group.name for group in Regex.group_iterator(text, mask=GroupKind.INVOC)}
        return self.find_all_invocations(invocations)

    # ------------------
    # `*` Public Methods
    # ------------------
    # --------------
    # `*0` Overrides
    # --------------
    def __len__(self) -> int:
        self.load() if not self.is_loaded else None
        return len(self.patterns)

    def __contains__(self, key: str) -> bool:
        self.load() if not self.is_loaded else None
        return key in self.patterns

    def __setitem__(self, name: str, param: RegexDef) -> None:
        if not self.is_loaded:
            self.lazy_queue.append(ft.partial(self.__setitem__, name, param))
            return
        assert name not in self.patterns, f'Duplicate pattern name: {name}'

        # Pull out the parser, if present
        val: RegexVal
        if isinstance(param, tuple) and len(param) == 2 and not isinstance(param[1], (list, tuple)):
            val, parser = param  # type: ignore
        else:
            val = param  # type: ignore
            parser = None

        self.define(name, val, parser)

    def __getitem__(self, name: str) -> Pattern:
        self.load() if not self.is_loaded else None
        assert name in self.patterns, f'Pattern not found: {name}'
        return self.patterns[name]

    def __ior__(self, other: dict[str, RegexDef] | Self) -> Self:
        self.load() if not self.is_loaded else None
        if isinstance(other, RegexStore):
            for name in other.keys():
                if name in other.parsers:
                    self[name] = (other.definitions[name], other.parsers[name])
                else:
                    self[name] = other.definitions[name]
        else:
            for name, param in other.items():
                self[name] = param
        return self

    def get(self, name: str, default: Pattern | None = None) -> Pattern | None:
        """Get a compiled pattern by name, or return a default if not found."""
        self.load() if not self.is_loaded else None
        return self.patterns.get(name, default)

    def get_def(self, name: str, default: str | None = None) -> str | None:
        """Get a raw definition by name, or return a default if not found."""
        self.load() if not self.is_loaded else None
        return self.definitions.get(name, default)

    def keys(self) -> list[str]:
        """Get a list of all defined pattern names in the store."""
        self.load() if not self.is_loaded else None
        return list(self.patterns.keys())

    def values(self) -> list[Pattern]:
        """Get a list of all compiled patterns in the store."""
        self.load() if not self.is_loaded else None
        return list(self.patterns.values())

    def items(self) -> list[tuple[str, Pattern]]:
        """Get a list of all (name, pattern) pairs in the store."""
        self.load() if not self.is_loaded else None
        return list(self.patterns.items())

    # -------------------------------
    # `*1` Top-Level Matching Methods
    # -------------------------------
    def match(self, names: str | Iterable[str], text: str | Buffer) -> MatchData:
        """Match one of the named patterns against text from the beginning.

        Args:
            names: Pattern name or list of pattern names to try.
            text: Text to match against.
        Returns:
            MatchData from first successful match, or empty MatchData if none match.
        """
        names, text = self._validate_automatch_params(names, text)
        return self._autoparse('match', names, text)

    def fullmatch(self, names: str | Iterable[str], text: str | Buffer) -> MatchData:
        """Match one of the named patterns against the entire text.

        Args:
            names: Pattern name or list of pattern names to try.
            text: Text to match against.
        Returns:
            MatchData from first successful fullmatch, or empty MatchData if none match.
        """
        names, text = self._validate_automatch_params(names, text)
        return self._autoparse('fullmatch', names, text)

    def search(self, names: str | Iterable[str], text: str | Buffer) -> MatchData:
        """Search for one of the named patterns anywhere in text.

        Args:
            names: Pattern name or list of pattern names to try.
            text: Text to search.
        Returns:
            MatchData from first successful search, or empty MatchData if none found.
        """
        names, text = self._validate_automatch_params(names, text)
        return self._autoparse('search', names, text)

    def finditer(self, name: str, text: str | Buffer, **kwargs) -> Iterator[MatchData]:
        """Find all non-overlapping matches of the pattern in text.

        Args:
            name: Pattern name to search for.
            text: Text to search (string or Buffer).
            **kwargs: Optional arguments passed to Buffer.rgx_iterator().
        Yields:
            MatchData objects for each match found.
        """
        self.load() if not self.is_loaded else None
        rgx = self.patterns[name]
        parse = ft.partial(self.parse, pattern_name=name)
        if isinstance(text, Buffer):
            yield from map(parse, text.rgx_iterator(rgx, **kwargs))
        else:
            assert not kwargs, f'Unexpected kwargs {kwargs} for plain-string "{text[:25]}..."'
            yield from map(parse, rgx.finditer(text))

    def findall(self, name: str, text: str | Buffer, **kwargs) -> list[MatchData]:
        """Find all non-overlapping matches of the pattern in text.

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
        """Split text by matches, returning both delimiters and sections.

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
        """Find all matches and merge their captures into a single MatchData.

        Unlike findall which returns separate MatchData objects, this merges all
        captures from all matches into one result, preserving order by start position.

        Args:
            name: Pattern name to search for.
            text: Text to search (automatically converted to Buffer).
        Returns:
            Single MatchData with all captures from all matches merged.
        """
        self.load() if not self.is_loaded else None
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
    # `*2` Functional Utilities
    # -------------------------
    def partial(
        self,
        name: str,
        func: Literal['match', 'fullmatch', 'search', 'polymatch'] = 'match',
    ) -> Callable[[str | Buffer], MatchData]:
        """Create a partially applied matching function for a pattern.

        Args:
            name: Pattern name to use.
            func: Matching function name ('match', 'fullmatch', 'search', or 'polymatch').
        Returns:
            Function that takes text and returns MatchData using the specified pattern.
        """
        self.load() if not self.is_loaded else None
        return ft.partial(getattr(self, func), name)

    def apply(
        self,
        name: str,
        texts: Iterable[str],
        func: Literal['match', 'fullmatch', 'search', 'polymatch'] = 'match',
    ) -> Iterable[MatchData]:
        """Apply a pattern to multiple texts.

        Args:
            name: Pattern name to use.
            texts: Iterable of text strings to match against.
            func: Matching function to use ('match', 'fullmatch', 'search', or 'polymatch').
        Yields:
            MatchData objects for each text in order.
        """
        self.load() if not self.is_loaded else None
        yield from map(self.partial(name, func), texts)

    def filter(
        self,
        name: str,
        texts: Iterable[str],
        func: Literal['match', 'fullmatch', 'search', 'polymatch'] = 'match',
    ) -> Iterable[str]:
        """Filter texts by whether they match a pattern.

        Args:
            name: Pattern name to test against.
            texts: Iterable of text strings to filter.
            func: Matching function to use ('match', 'fullmatch', 'search', or 'polymatch').
        Yields:
            Only those texts that successfully match the pattern.
        """
        self.load() if not self.is_loaded else None
        fn = self.partial(name, func)
        yield from filter(lambda text: bool(fn(text)), texts)

    # ---------------------------
    # `*3` Optimization Functions
    # ---------------------------
    def define_router_tree(self, router: str, items: Mapping[str, RegexVal], **kwargs: str) -> None:
        """Define a router pattern that classifies text into named categories.

        Creates two patterns: one optimized router (`<router>`) and one with route tracking
        (`<router>_router`) that captures which category matched.

        Args:
            router: Base name for the router patterns.
            items: Mapping of category names to their regex patterns.
            **kwargs: Optional 'prefix'/'suffix' or 'p0'/'p1'/'s0'/'s1' for wrapping patterns.
        Raises:
            AssertionError: If router name is already defined.
        """
        if not self.is_loaded:
            self.lazy_queue.append(ft.partial(self.define_router_tree, router, items, **kwargs))
            return

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
        self[f'{router}_router'] = (
            '|:',
            p1,
            [(f'<|>P<rt_{i}>', rgx) for i, rgx in routes],
            s1,
        )

    def route_match(self, router: str, text: str | MatchData) -> str:
        """Determine which category a text matches in a router tree.

        Args:
            router: Name of router pattern to use.
            text: Text to classify, or MatchData from previous match.
        Returns:
            Name of the matching category, or empty string if no match.
        Raises:
            AssertionError: If router name is not found.
        """
        self.load() if not self.is_loaded else None
        assert router in self.routers, f'Unknown router: {router}'
        if isinstance(text, MatchData):
            text = text.text

        data = self.fullmatch(f'{router}_router', text)
        if raw_idx := next((name[3:] for name in data.keys() if name.startswith('rt_')), ''):
            assert raw_idx.isdigit(), f'Invalid router index: {raw_idx}'
            return self.routers[router][int(raw_idx)]
        return ''

    def expand_match(self, router: str, text: str | MatchData) -> str:
        """Match text against a router and expand using the matched category's format.

        Args:
            router: Name of router pattern to use.
            text: Text to match and expand, or MatchData from previous match.
        Returns:
            Expanded string using the matched category name as format string.
        Raises:
            AssertionError: If router name is not found or match object is invalid.
        """
        self.load() if not self.is_loaded else None
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
    # `*4` Misc
    # ---------
    def sanitize(self, pattern: str | Pattern | Buffer | Regex | Atom) -> str:
        """Sanitize a pattern by normalizing inline flag syntax.

        Args:
            pattern: Either a known pattern's name, a compiled pattern, or a raw expression.
        Returns:
            Sanitized pattern string with normalized flag syntax.
        """
        self.load() if not self.is_loaded else None
        if isinstance(pattern, Pattern):
            pattern = pattern.pattern
        elif isinstance(pattern, str) and pattern in self.patterns:
            pattern = self.patterns[pattern].pattern
        else:
            pattern = str(pattern)

        return ut.replace(
            pattern,
            (META_RGXS['inline_flags'], r'(?:(?\1)'),
        )

    def tree_print(
        self,
        pattern: str | Pattern | Buffer | Regex | Atom,
        print_head: bool = True,
        **kwargs: Any,
    ) -> str:
        """Pretty-print a regex pattern as an indented multiline tree structure.

        Args:
            pattern: The name of an existing pattern, a compiled pattern, or a raw expression.
            print_head: Whether to include the pattern header (i.e. `(?:DEFINE)...)`) in output.
            **kwargs: Additional arguments passed to `_tree_print()`.
        Returns:
            Multi-line string representation with indentation showing nesting.
        """
        self.load() if not self.is_loaded else None
        # 0. Normalize & validate arguments
        body: Regex
        if isinstance(pattern, Regex):
            body = pattern
        elif isinstance(pattern, Atom):
            body = Regex(pattern)
        else:
            if isinstance(pattern, Pattern):
                expr = pattern.pattern
            elif isinstance(pattern, str) and pattern in self:
                expr = self.definitions[pattern]
            else:
                expr = str(pattern)
            body = Regex(expr)

        if not body:
            return ''

        # I. Identify and separate out the definition section, if present
        head = Atom()
        if (
            len(body) > 1
            and isinstance(first := body.first, GroupAtom)
            and first.kind == GroupKind.DEFINE
        ):
            head, *body = body
        elif print_head and isinstance(pattern, str) and pattern in self:
            head = mi.first(Regex.atomize(self.patterns[pattern].pattern))
            assert isinstance(head, GroupAtom) and head.kind == GroupKind.DEFINE

        # II. Pretty-print the body & head separately
        kwargs = dict(maxdepth=6, threshold=48) | kwargs
        ret = self._tree_print(body, **kwargs)
        if print_head and head:
            ret = f'{self._tree_print(head, **kwargs)}\n{ret}'
        return ret
