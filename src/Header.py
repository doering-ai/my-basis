############
### HEAD ###
############
# Standard
from typing import ClassVar, Dict, Optional, Tuple, Union, List, Iterator, Iterable
from dataclasses import dataclass
import re
from enum import Flag, auto
import itertools as it
import functools as ft

# External

# Internal
from .common import decimal_to_roman, roman_to_decimal, ROMAN_RGX
from .Comment import Comment


############
### DATA ###
############
class IdxStyle(Flag):
    NONE = 0
    SYMBOL = auto()  # 0, -, +, x [0, 3]
    NUMBER = auto()  # 0, 1, 2, ... [0, 9] (or [0, ...) with separators)
    ROMANL = auto()  # i, ii, iii, iv, v, ... [0, 47]
    ROMANU = auto()  # I, II, III, IV, V, ... [0, 47]
    ALPHAL = auto()  # a, b, c, ... [0, 25]
    ALPHAU = auto()  # A, B, C, ... [0, 25]

    ROMAN = ROMANL | ROMANU
    ALPHA = ALPHAL | ALPHAU


############
### BODY ###
############
@ft.total_ordering
@dataclass
class Header(Comment):
    QUAD: ClassVar[str] = '.-+*'
    RGXS: ClassVar[Dict[str, re.Pattern]] = dict(
        idx=re.compile(rf'(?:(?:[.\-+*]|\d)\.?|{ROMAN_RGX.pattern}\.){{1,5}}'),
        roman=ROMAN_RGX,
    )

    # Independent
    level: int = 1
    title: str = ''
    tag: str = ''

    # -------------------
    # `.` Initial Methods
    # -------------------
    @classmethod
    def new(cls, comment: Comment, level: int = 1) -> 'Header':
        assert comment.n_lines == 3, 'Header comment must be exactly three lines.'
        header = cls(
            level=level,
            title=comment.texts[1].strip(),
            lines=comment.lines,
            texts=comment.texts,
            row=comment.row,
            col=comment.col,
            mark=comment.mark,
        )

        # I. Separate out the tag if present
        if match := re.fullmatch(r'^`([^`]+)` ?(.*?)', header.title):
            header.tag, header.title = match.groups()

        # II. Format title and mark for level 0 headers
        if level == 0:
            header.mark = header.mark[0] * 3
            if header.mark and header.title.endswith(f' {header.mark}'):
                header.title = header.title[: -len(header.mark)].strip()

            header.title = header.title.upper()

        return header

    # -------------------
    # `-` Private Methods
    # -------------------
    @staticmethod
    def _are_delims(t0: str, t1: str, level: int = 1) -> bool:
        """
        Determine if a line of text is a header delimiter based on the specified level.

        Args:
            text: The line of text to check.
            level: 0 for HEAD/DATA/BODY/MAIN, 1 for body sections, -1 for any.
        """
        t0 = t0.strip()
        t1 = t1.strip()

        return t0 == t1 and (
            (level in {0, -1} and bool(re.match(r'#{12,}|\/{12,}|={12,}', t0)))
            or (level in {1, -1} and t0.startswith('-' * 8))
            or (level == -1 and len(chars := set(t0)) == 1 and chars.pop() in '-#/=')
        )

    @classmethod
    def _read_idx_part(cls, part: str) -> Tuple[IdxStyle, int]:
        part = part.strip(' .:`')
        assert '.' not in part
        if not part:
            return (IdxStyle.NUMBER, 0)

        elif part.isdigit():
            return (IdxStyle.NUMBER, int(part))

        elif part in cls.QUAD:
            assert len(part) == 1, 'Quad idx must be a single character.'
            return (IdxStyle.SYMBOL, cls.QUAD.index(part))

        elif cls.RGXS['roman'].fullmatch(part):
            style = IdxStyle.ROMANU if part.isupper() else IdxStyle.ROMANL
            return style, roman_to_decimal(part)

        elif part.isalpha():
            assert len(part) == 1, 'Alphabetic idx must be a single character.'
            style = IdxStyle.ALPHAU if part.isupper() else IdxStyle.ALPHAL
            return style, ord(part.upper()) - ord('A') + 1

        raise ValueError(f'Cannot classify idx: {part}')

    @classmethod
    def _write_idx_part(cls, style: IdxStyle, pos: int) -> str:
        assert pos >= 0
        if style == IdxStyle.NUMBER:
            return str(pos)

        elif style == IdxStyle.SYMBOL:
            assert pos < 4
            return cls.QUAD[pos]

        elif style & IdxStyle.ROMAN:
            assert pos < 48
            fn = str.lower if style == IdxStyle.ROMANL else str.upper
            return fn(decimal_to_roman(pos))

        elif style & IdxStyle.ALPHA:
            assert pos < 26
            fn = str.lower if style == IdxStyle.ALPHAL else str.upper
            return chr(ord(fn('a')) + pos - 1)

        else:
            raise ValueError(f'Cannot write idx for unrecognized style: {style}')

    def _collect_siblings(
        self,
        iterator: Optional[Iterable['Header']],
        reverse: bool = False,
    ) -> Iterator['Header']:
        if iterator is None:
            return
        for rhs in iterator:
            if self.level > rhs.level or self.col > rhs.col:
                return
            elif self.level == rhs.level and self.col == rhs.col:
                yield rhs

    def is_parent_of(self, child: 'Header') -> bool:
        return child.level == self.level + 1 or (
            child.level == self.level
            and child.col == self.col
            and 0 < len(child.idx) < len(self.idx)
            and child.idx.startswith(self.idx)
        )

    # -------------------
    # `+` Primary Methods
    # -------------------
    @classmethod
    def generate(cls, text: str, col: int, mark: str, level: int) -> List[str]:
        """
        Returns:
            The delta number of characters.
        """
        assert text and mark and level >= 0, 'Invalid arguments for header generation.'

        if level == 0:
            mchar = mark[0]
            text = f'{mchar * 3} {text.upper()} {mchar * 3}'
            delim = mchar * len(text)
            lines = [delim, text, delim]
        elif level == 1:
            delim = f'{mark} {"-" * len(text)}'
            text = f'{mark} {text}'
            lines = [delim, text, delim]
        else:
            lines = [text]

        return [f'{indent}{line}' for line in lines] if (indent := ' ' * (col - 1)) else lines

    def find_family(
        self,
        before: List['Header'],
        after: List['Header'],
    ) -> Tuple[Optional['Header'], List['Header'], List['Header']]:
        parent = self.find_parent(before)
        older, younger = self.find_siblings(before, after)
        children = self.find_children(after)
        return parent, [*older, self, *younger], children

    def find_parent(self, others: List['Header']) -> Optional['Header']:
        return next((p for p in reversed(others) if p < self and p.is_parent_of(self)), None)

    def find_children(self, others: List['Header']) -> List['Header']:
        after = list(filter(lambda other: other > self, others))
        if after and self.is_parent_of(after[0]):
            heir, *after = after
            return [heir, *heir._collect_siblings(after)]
        return []

    def find_siblings(
        self,
        before: Optional[List['Header']] = None,
        after: Optional[List['Header']] = None,
    ) -> Tuple[List['Header'], List['Header']]:
        older = list(self._collect_siblings(before, reverse=True))
        younger = list(self._collect_siblings(after))
        return older, younger

    @classmethod
    def idx_to_parts(cls, idx: str) -> Tuple[bool, List[Tuple[IdxStyle, int]]]:
        is_dotted = '.' in idx
        idx = idx.strip(' .:`')
        parts = list(filter(bool, idx.split('.')) if is_dotted else idx)

        return is_dotted, list(map(cls._read_idx_part, parts))

    @classmethod
    def parts_to_idx(cls, *parts: Tuple[IdxStyle, int], is_dotted: bool = False) -> str:
        ret = list(it.starmap(cls._write_idx_part, parts))
        if (
            is_dotted
            or max(map(len, ret)) > 1
            or any((style & IdxStyle.ROMAN) for style, _ in parts)
        ):
            return '.'.join(ret) + '.'
        else:
            return ''.join(ret)

    # ------------------
    # `*` Public Methods
    # ------------------
    def __str__(self) -> str:
        text = f'`{self.tag}` {self.title}' if self.tag else self.title
        lines = self.generate(text, self.col, self.mark, self.level)
        return '\n'.join(lines)

    @property
    def idx(self) -> str:
        if (word := self.tag.split(' ', maxsplit=1)[0]) and self.RGXS['idx'].fullmatch(word):
            return word
        return ''

    @idx.setter
    def idx(self, value: str) -> None:
        assert self.idx or not self.tag, (
            f'Cannot set idx {value} over non-idx node "`{self.tag}` {self.title}"'
        )
        self.tag = value

    @classmethod
    def relative_idx(
        cls,
        idx: str,
        *,
        place: Tuple[int, Union[int, List[int]]] = (0, 0),
        shift: Tuple[int, Union[int, List[int]]] = (0, 0),
    ) -> str:
        place_v, place_h = place
        shift_v, shift_h = shift
        assert any([place_v, place_h, shift_v, shift_h]), 'Must specify at least one argument.'

        is_dotted, parts = cls.idx_to_parts(idx)
        depth0 = depth = len(parts)

        assert not (place_v and shift_v), 'Cannot place AND shift vertically.'
        if place_v:
            if place_v < depth:
                parts = parts[:place_v]
            elif place_v > depth:
                parts.extend((IdxStyle.NUMBER, 0) for _ in range(place_v - depth))
            depth = place_v
        elif shift_v:
            if depth == 0:
                parts.extend((IdxStyle.NUMBER, 0) for _ in range(shift_v))
            elif shift_v < 0:
                parts = parts[:shift_v]
            else:
                parts.extend((IdxStyle.NUMBER, 0) for _ in range(shift_v))
            depth += shift_v

        if depth == 0:
            raise IndexError(f'Vertical change out of bounds ({place_v=}, {shift_v=}, {depth0=})')

        assert not (place_h and shift_h), 'Cannot place AND shift horizontally.'
        orig_h = [pos for _, pos in parts]
        if place_h:
            if isinstance(place_h, int):
                parts[-1] = parts[-1][0], place_h
            else:
                parts = [(style, pos) for (style, _), pos in zip(parts, place_h, strict=True)]
        elif shift_h:
            if isinstance(shift_h, int):
                style, last = parts[-1]
                parts[-1] = style, last + shift_h
            else:
                parts = [
                    (style, cur + shift) for (style, cur), shift in zip(parts, shift_h, strict=True)
                ]

        if any(pos < 0 for _, pos in parts):
            raise IndexError(f'Horizontal change out of bounds ({place_h=}, {shift_h=}, {orig_h=})')

        return cls.parts_to_idx(*parts, is_dotted=is_dotted)
