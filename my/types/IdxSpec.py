############
### HEAD ###
############
# --------
# Standard
# --------
from __future__ import annotations
from typing import ClassVar, Literal
from typing import Self
from collections import deque
from collections.abc import Iterator, Sequence
import functools as ft

# --------
# External
# --------
import regex as re
import pydantic as pyd
import more_itertools as mi

# --------
# Internal
# --------
from myBasis import ut
from .enums import IdxStyle

# Test
roman_rgx = ut.RGXS['roman'].pattern


############
### BODY ###
############
class IdxSpec(pyd.BaseModel):
    r"""Specification for the shape and notation of an index string.

    An `IdxSpec` describes *what* a valid index looks like for a particular
    header level, without holding any concrete value.  It is used to:

    - Generate a regex pattern that matches (and captures) valid index strings
      in header text via `rgx` / `rgx_parts`.
    - Provide default `IdxStyle` values for each depth via `style_iter`.
    - Constrain parsing in `Idx` (e.g. enforcing `max_depth`, `dotted`, `marked`).

    The `_build_rgx` class method synthesises a group pattern from the `styles` list.
    For example:

    ```rgx
    # styles=[NUMBER, ALPHAU, ROMANL], dotted=True, marked='.' =>
    (?P>number)(?:\.(?P>alphau)(?:\.(?P>romanl)?)?)?\.
    ```
    """

    SYMBOLS: ClassVar[str] = '.-+*^'
    EXPRS: ClassVar[dict[str, str]] = dict(
        untagged_pre=r'(?m)(?<=\s|^)',
        untagged_suf=r'(?=\s|$)',
        tagged_pre=r'(?m)(?<=`|^)',
        tagged_suf=r'(?=(?:\s[^\n`]*)?`|$)',
        flex_pre=r'(?m)(?<=[\s`]|^)',
        flex_suf=r'(?=[\s`]|$)',
    )
    RGXS: ClassVar[dict[str, ut.RegexField]] = ut.rgx_dict(
        mark=r'[.:)]',
        symbol=rf'[{re.escape(SYMBOLS)}]',
        number=r'\d(?:\d+(?=[.:)]))?',
        alphal=r'\b(?:\p{Ll}\b|\p{Ll}+(?=[.:)]))',
        alphau=r'\b(?:\p{Lu}\b|\p{Lu}+(?=[.:)]))',
        alpha=r'\b(?:\p{Ll}\b|\p{Lu}\b|(?:\p{Ll}+|\p{Lu}+)(?=[.:)]))',
        roman=roman_rgx,
        romanl=r'(?=\p{Ll}+(?:[.:)]|$))' + roman_rgx,
        romanu=r'(?=\p{Lu}+(?:[.:)]|$))' + roman_rgx,
        flex=r'(?>{{.symbol}}|{{.number}}|{{.alpha}}|{{.roman}})',
        flex_full=''.join(
            [
                r'(?(DEFINE)(?P<flex>{{.flex}}))',
                EXPRS['flex_pre'],
                r'(?P>flex)(?|(?:\.(?P>flex))+|(?P>flex)+)?',
                EXPRS['flex_suf'],
            ]
        ),
    )

    #: The style of index tags, if any.
    styles: tuple[IdxStyle, ...] = tuple()
    #: The maximum depth of index chains to match.
    max_depth: pyd.NonNegativeInt = 0

    #: Whether nested index levels are separated by periods.
    dotted: bool | None = None
    #: The character printed at the end of every full idx chain.
    marked: Literal['', '.', ')', ':'] | None = None
    #: Whether the idx appears with any tags in a bactic-fenced prefix. If False, must be marked.
    tagged: bool | None = None
    #: Whether this idx is a required part of the HeaderSpec that contains it, or is forbidden.
    forced: bool | None = None

    # -------------------
    # `.` Initial Methods
    # -------------------
    @pyd.model_validator(mode='before')
    @classmethod
    def _prepare_spec(cls, data: dict) -> dict:
        # I. Coerce style strings/ints into Enum values
        if 'styles' in data:
            styles = data['styles']
            if not isinstance(styles, Sequence):
                styles = (styles,)

            if any(isinstance(style, str) for style in styles):
                data['styles'] = tuple(map(IdxStyle.coerce, styles))

        # II. Accept False & None for marked
        if 'marked' in data and not data['marked']:
            data['marked'] = ''
        return data

    @pyd.model_validator(mode='after')
    def _validate_spec(self) -> Self:
        if any(style in IdxStyle.ROMAN for style in self.styles):
            self.dotted = True
        if not (self.tagged or self.marked):
            self.marked = '.'
        return self

    # -------------------
    # `-` Private Methods
    # -------------------

    # -------------------
    # `+` Primary Methods
    # -------------------
    @staticmethod
    @ft.lru_cache(maxsize=64)
    def _build_rgx(spec: IdxSpec) -> tuple[dict[str, str], str]:
        r"""Build a regex pattern for validating index strings of any depth that match this spec.

        Examples:
            In the examples below, the actual rgxs for each idx type are replaced by all-caps names.


            From [NUMBER, ALPHAU, ALPHAL, ROMANL], dotted, marked with ".", and tagged:
            ```regex
            (?<=`|^)(?:NUMBER)(?:\.ALPHAU(?:\.ALPHAL(?:\.ROMANL)?)?)?\.(?=(?:\s[^\n`]*)?`|$)
            ```

        Args:
            spec: The Idx specification to build the regex for.
        """
        self = spec
        groups = {}

        if IdxStyle.NONE in self.styles:
            # 0. Skip any specs that explicitly set style to NONE
            return {}, r'^$'
        elif self.styles:
            # I. If styles are specified, accumulate an order-sensititve expression
            # I.i. Determine the lookbehind/lookahead pair to use
            if self.tagged:
                pre, suf = self.EXPRS['tagged_pre'], self.EXPRS['tagged_suf']
            else:
                pre, suf = self.EXPRS['untagged_pre'], self.EXPRS['untagged_suf']

            # I.ii. Fetch the expressions for each of the styles in order
            names = [(style.name or '').lower() for style in self.styles]
            assert all(n in self.RGXS for n in names), f'Invalid styles in spec: {self.styles}'
            groups.update({name: self.RGXS[name].pattern for name in set(names)})
            atoms = [rf'(?P>{name})' for name in names]

            # I.iii. Construct the final expression one nested step at a time
            stack = deque([''])
            for is_first, is_last, atom in mi.mark_ends(reversed(atoms)):
                if is_last or self.dotted is False:
                    dot = r''
                elif self.dotted:
                    dot = r'\.'
                else:
                    assert self.dotted is None
                    dot = r'\.?'

                if is_last:
                    quant = r''
                elif is_first:
                    if self.max_depth <= 0:
                        quant = r'*'
                    elif (diff := self.max_depth - len(self.styles)) > 0:
                        quant = rf'{{0,{diff}}}'
                    else:
                        quant = r'?'
                else:
                    quant = r'?'

                if quant:
                    if dot or stack[0]:
                        stack.appendleft(rf'(?:{dot}{atom}{stack[0]}){quant}')
                    else:
                        stack.appendleft(rf'{atom}{quant}')
                else:
                    stack.appendleft(rf'{dot}{atom}{stack[0]}')
            body = stack[0]
        else:
            # II. If no styles are specified, check for any valid idxs in any order
            #     Note that specs can still set `dotted,` `marked`, and `tagged` without styles
            # II.i. Determine the lookbehind/lookahead pair to use
            pre, suf = self.EXPRS['flex_pre'], self.EXPRS['flex_suf']
            groups['flex'] = self.RGXS['flex'].pattern

            # II.ii. Determine the final atom's quantifier based on `max_depth`
            if self.max_depth <= 0:
                quant = r'*'
            elif self.max_depth == 1:
                quant = r''
            else:
                quant = rf'{{0,{self.max_depth - 1}}}'

            # II.iii. Construct the simple final expression based on `dotted` and `tagged` options
            if self.dotted:
                base = rf'(?:\.(?P>flex)){quant}'
            elif self.dotted is not None:
                base = rf'(?P>flex){quant}'
            else:
                base = rf'(?|(?P>flex){quant}|(?:\.(?P>flex)){quant})'
            body = rf'(?P>flex){base}'

        # III. Consolidate groups before returning
        if 'romanl' in groups and 'romanu' in groups:
            _rgx = groups['roman'] = self.RGXS['roman'].pattern
            groups['romanl'] = groups.pop('romanl').replace(_rgx, r'(?P>roman)')
            groups['romanu'] = groups.pop('romanu').replace(_rgx, r'(?P>roman)')

        return groups, rf'{pre}{body}{self.mark_rgx}{suf}'

    def style_iter(self, start: int = 0, end: int = -1) -> Iterator[IdxStyle]:
        """Yield default `IdxStyle` values for index depths in the range `[start, end)`.

        If `start` is beyond the length of `self.styles`, `NUMBER` is yielded for
        the remaining positions.  This is used by `Idx.build` and `Idx.build_relative`
        to fill in styles for newly-created index parts.

        Args:
            start: Inclusive start depth (default 0).
            end: Exclusive end depth; uses `len(self.styles)` if ≤ 0.
        """
        n = len(self.styles)
        end = end if end > 0 else n
        assert 0 <= start <= end, f'Invalid depth range: {start + 1} to {end + 1}'
        if start == end:
            return

        if start >= n:
            yield from (IdxStyle.NUMBER for _ in range(n, end))
        else:
            yield from mi.take(end - start, mi.repeat_last(self.styles[start:end]))

    # ------------------
    # `*` Public Methods
    # ------------------
    @property
    def mark_rgx(self) -> str:
        """The regex pattern for matching the mark at the end of an index string."""
        return r'[.):]?' if self.marked is None else re.escape(self.marked)

    @property
    def mark(self) -> str:
        """The character printed at the end of every full idx chain (if specified)."""
        return self.marked or ''

    def __hash__(self):
        return hash((self.styles, self.dotted, self.marked, self.tagged))

    @property
    def rgx_parts(self) -> dict[str, str]:
        """Named regex sub-expressions for embedding this spec inside a larger pattern.

        Returns a dict mapping group names to their uncompiled pattern strings,
        with the key `'idx'` holding the top-level index expression.  Intended
        for use by `HeaderSpec._build_prefix_rgx` when assembling the full
        header regex.
        """
        groups, rgx = self._build_rgx(self)
        groups['idx'] = rgx
        return groups

    @property
    def rgx(self) -> re.Pattern[str]:
        """Compiled regex that matches a complete, standalone index string for this spec.

        Suitable for standalone validation of an index string outside of a
        header context.  For embedding within the header regex, use `rgx_parts`
        instead.
        """
        head, body = self._build_rgx(self)
        return re.compile(ut.rgx_definitions(head) + body)

    @property
    def is_disabled(self) -> bool:
        """Whether this idx spec is disabled (i.e. explicitly set to NONE)."""
        return IdxStyle.NONE in self.styles
