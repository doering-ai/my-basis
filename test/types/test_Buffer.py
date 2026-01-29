############
### HEAD ###
############
### STANDARD
from typing import Any
import itertools as it
import functools as ft

### EXTERNAL
import pytest as pyt
import numpy as np
import regex as re

### INTERNAL
from my.types import Span
from my.types.Buffer import Buffer, PairMode
from ..conftest import boolmap

############
### DATA ###
############
cls = Buffer
DefBuf = ft.partial(Buffer.new, fence_rgxs=['bactic'])


############
### BODY ###
############
class TestBuffer:
    @pyt.mark.parametrize('text', ['test string', ['test string']])
    def test_factory(self, text: Any):
        assert cls.new(text).serialize() == 'test string'

    @pyt.mark.parametrize(
        'text, expected',
        [
            ('`0`1`34`6`7`', ['`0`', '`34`', '`7`']),
            ('01```\n23456\n```789', ['```\n23456\n```']),
            ('01`\n23456\n`789', []),
            ('01`3`5`7`9', ['`3`', '`7`']),
            ('`0`1```\n23456\n```78`9`', ['`0`', '```\n23456\n```', '`9`']),
            ('`12``56`', ['`12`', '`56`']),
        ],
    )
    def test_build_fences(self, text: str, expected: list[str]):
        buf = DefBuf(text)
        assert list(it.starmap(buf.slice, buf.fences.tolist())) == expected

    @pyt.mark.parametrize(
        'text, rgxs, expected',
        [
            ('`0`1`34`6`7`', ['bactic'], ['`0`', '`34`', '`7`']),
            ('`0`1`34`6`7`', [], []),
            ('[0]1[34]6[7]', ['arrays'], ['[0]', '[34]', '[7]']),
            ('0[1[34]6]7', ['arrays'], ['[1[34]6]']),
        ],
    )
    def test_build_custom_fences(self, text: str, rgxs: list[str], expected: list[str]):
        buf = cls.new(text, fence_rgxs=rgxs)
        assert list(it.starmap(buf.slice, buf.fences.tolist())) == expected

    @pyt.mark.parametrize(
        'text, replacement, expected',
        [
            ('01`34`67`89`', ('`34`', ''), '0167`89`'),
            ('01`34`67`89`', ((2, 6), ''), '0167`89`'),
            ('01`34`6677`89`', ('6677', '66667777'), '01`34`66667777`89`'),
            ('0`23`5', ('23', '`23`'), '0``23``5'),
            ('0`2345`7', ('ABC', 'XYZ'), '0`2345`7'),
        ],
    )
    def test_replace(
        self, text: str, replacement: tuple[str | tuple[int, int], str], expected: str
    ):
        buf = DefBuf(text)
        buf.replace(*replacement, 5)
        assert str(buf) == expected

    @pyt.mark.parametrize(
        'span, expected',
        boolmap(
            true=[
                Span(0, 3),
                Span(2, 3),
                Span(2, 6),
                Span(6, 11),
                Span(8, 99),
            ],
            false=[
                Span(0, 2),
                Span(1, 7),
                Span(6, 8),
                Span(11, 99),
            ],
            base_type=Span,
        ),
    )
    def test_is_fenced(self, span: Span, expected: bool):
        buf = DefBuf('01`34`67`9`')
        assert buf._is_fenced(span) == expected

    @pyt.mark.parametrize(
        'text, mode, expected',
        [
            ('one {{ two }} three', 'all', [' two ']),
            ('one {{ {{ nested }} base }} three', 'all', [' nested ', '  base ']),
            ('one {{ {{ nested }} base }} three', 'roots', [' {{ nested }} base ']),
            ('one {{ {{ nested }} base }} three', 'leaves', [' nested ']),
            (
                'abc {{Small|Ruth Kinna (2019){{Sfn|Kinna|2019|p=97}}}} xyz',
                'all',
                ['Sfn|Kinna|2019|p=97', 'Small|Ruth Kinna (2019)'],
            ),
            (
                '{{small|{{large|{{huge|text!}}}}}}',
                'all',
                ['huge|text!', 'large|', 'small|'],
            ),
        ],
    )
    def test_pair_iterator(self, text: str, mode: PairMode, expected: list[str]):
        buf = DefBuf(text)
        rgx = re.compile(r'(?P<start>{{)|(?P<end>}})')
        for (span, _, body, _), exp in zip(buf.pair_iterator(rgx, mode), expected, strict=True):
            assert body == exp
            buf.drop(span)

    @pyt.mark.parametrize(
        'text, rgx, expected',
        [
            ('xx0x9xx', r'0.*?9', ['0x9']),
            ('xx0x90xx9x', r'0.*?9', ['0x9', '0xx9']),
            ('xx0x09xx9x', r'0.*?9', ['0x09']),
        ],
    )
    def test_rgx_iterator(self, text: str, rgx: str, expected: list[str]):
        buf = DefBuf(text)
        for match, exp in zip(buf.rgx_iterator(rgx), expected, strict=True):
            assert match[0] == exp
            buf.drop(match.span())

    def test_rgx_iterator__recursive(self):
        buf = DefBuf('start [WORD1] middle [WORD3] end')
        for match in buf.rgx_iterator('arrays', True):
            span = match.span()
            text = match[0][1:-1]
            if text == 'WORD1':
                buf.replace(span, '[here is WORD2 right here]')
            elif text == 'here is WORD2 right here' or text == 'WORD3':
                buf.drop(span)
            else:
                raise ValueError(f'Unexpected match: {text}')
        assert buf.text[0] == 'start  middle  end'

    @pyt.mark.parametrize(
        'source, span, delta, expected_pre, expected_post',
        [
            # Basic case
            (
                [Span(0, 2), Span(3, 5), Span(6, 8)],
                Span(4, 5),
                -1,
                [Span(0, 2)],
                [Span(5, 7)],
            ),
            # Insertion
            (
                [Span(0, 3), Span(3, 5), Span(6, 8)],
                Span(3, 3),
                4,
                [Span(0, 3)],
                [Span(7, 9), Span(10, 12)],
            ),
        ],
    )
    def test_split_spans(
        self,
        source: list[Span],
        span: Span,
        delta: int,
        expected_pre: list[Span],
        expected_post: list[Span],
    ):
        pre, post = cls._split_spans(list(map(Span, source)), Span(span), delta)
        assert np.all(pre == np.array(expected_pre, dtype=int))
        assert np.all(post == np.array(expected_post, dtype=int))

    @pyt.mark.parametrize(
        'text, new, old, expected',
        [
            # Update outside any fence
            ('This is some text with `code` block', 'sample', 'some', ['code']),
            # Overlaps w/ fence
            ('This is some `code` block', 'special c', 'some `c', []),
            ('This is some `code` block', 'ode block', 'ode` block', []),
            # Within fence
            ('This is some `code` block', 'java', 'code', ['java']),
            # Removes fence(s)
            ('This is some `code` block', ' ', '`code`', []),
            ('This is some `code1` and `code2` block', ' ', '`code1` and `code2`', []),
            # Adds fence(s)
            ('This is some ', ' `code`', (9, 10), ['code']),
            ('This is some ', ' some `code1` and `code2`', (9, 10), ['code1', 'code2']),
            # Update multiple fences
            ('This is `code1` and `code2` here', 'updated content', '`code1` and `code2`', []),
            ('This `code1` and `code2` here', '---', 'de1` and `co', ['co---de2']),
            (
                '`code1` and `code2`',
                '...de1` `code3` `co...',
                'de1` and `co',
                ['co...de1', 'code3', 'co...de2'],
            ),
            # Update text before fences
            ('Prefix `code1` and `code2` suffix', 'Long ', (0, 0), ['code1', 'code2']),
            # Update edges
            ('This is `code`', ' more', (14, 14), ['code']),
            ('This has `code`', ' and more `stuff`', (15, 15), ['code', 'stuff']),
            ('`code` here', 'new', '`code`', []),
            # Update between adjacent fences
            ('This `code1``code2` here', ' and ', (12, 12), ['code1', 'code2']),
            # Update nested fence
            ('This ```outer `inner` code``` here', 'nested', 'inner', ['``outer `nested` code``']),
            ## EDGE CASES ##
            # Empty update (no change)
            ('This has `code` blocks', '', (0, 0), ['code']),
            # Empty buffer with update
            ('', '`code`', (0, 0), ['code']),
            # Update that deletes all text
            ('This has `code` blocks', '', 'This has `code` blocks', []),
        ],
    )
    def test_update_fences(self, text: str, new: str, old: tuple | str, expected: list[str]):
        buf = DefBuf(text)
        buf.replace(old, new)
        assert list(it.starmap(buf.slice, buf.fences)) == [f'`{s}`' for s in expected]

    @pyt.mark.parametrize(
        'text, chars, expected, fences',
        [
            ('` welcome` ', '` ', 'welcome', []),
            ('` welcome` ', '`', ' welcome` ', []),
            (' `one` `two` ', ' ', '`one` `two`', ['one', 'two']),
            (' `one` `two` ', '', '`one` `two`', ['one', 'two']),
            ('`one` `two`', '`', 'one` `two', [' ']),
        ],
    )
    def test_strip(self, text: str, chars: str, expected: str, fences: list[str]):
        buf = DefBuf(text)
        buf.strip(chars)
        assert str(buf) == expected
        assert list(it.starmap(buf.slice, buf.fences)) == [f'`{f}`' for f in fences]

    @pyt.mark.parametrize(
        'text, pos, expected',
        [
            # Trailing cases
            ('line1', 0, (0, 5)),
            ('line1', 2, (0, 5)),
            ('line1', 4, (0, 5)),
            ('line1\nline2', 5, (6, 11)),
            ('line1\nline2', 10, (6, 11)),
            # Terminated cases
            ('a\nb\nc\n', 0, (0, 1)),
            ('a\nb\nc\n', 1, (2, 3)),
            ('a\nb\nc\n', 2, (2, 3)),
            ('a\nb\nc\n', 3, (4, 5)),
            ('a\nb\nc\n', 4, (4, 5)),
            ('a\nb\nc\n', 5, (6, 6)),
            # Empty lines
            ('\n', 0, (1, 1)),
            ('a\n\nb', 0, (0, 1)),
            ('a\n\nb', 1, (2, 2)),
            ('a\n\nb', 2, (3, 4)),
            ('a\n\nb', 3, (3, 4)),
            # Edge cases
            ('\nline1', 0, (1, 6)),
            ('\nline1', 1, (1, 6)),
            ('\n\nline1', 0, (1, 1)),
            ('\n\nline1', 1, (2, 7)),
        ],
    )
    def test_linespan(self, text: str, pos: int, expected: tuple[int, int]):
        y0, y1 = expected

        buffer = cls.new(text)
        x0, x1 = buffer.linespan(pos)
        assert (x0, x1) == (y0, y1)
        assert x0 - 1 <= pos < x1

        # Verify that the span actually contains the line
        line = text[x0:x1]
        assert line == '\n' or '\n' not in line

    def test_linespan__oob(self):
        buffer = cls.new('line1')
        with pyt.raises(AssertionError, match='Position -1 is out of bounds'):
            buffer.linespan(-1)
        with pyt.raises(AssertionError, match='Position 5 is out of bounds'):
            buffer.linespan(5)

        empty_buffer = cls()
        with pyt.raises(AssertionError, match='Position 1 is out of bounds'):
            empty_buffer.linespan(1)
