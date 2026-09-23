############
### HEAD ###
############
### STANDARD
import re as stdlib_re
import regex as re

### EXTERNAL
import pytest as pyt

### INTERNAL
from my.utils import TextUtils

cls = TextUtils


############
### BODY ###
############
class TestTextUtils:
    # ------------------------
    # `0` MANIPULATION & REGEX
    # ------------------------
    def test_replace(self):
        """Test sequential regex replacements."""
        text = 'hello world test'
        result = cls.replace(text, (r'hello', 'goodbye'), (r'world', 'universe'))
        assert result == 'goodbye universe test'

        # Multiple replacements
        result = cls.replace('a b c', (r'a', 'x'), (r'b', 'y'), (r'c', 'z'))
        assert result == 'x y z'

    @pyt.mark.parametrize(
        'text, pattern, n, rhs, expected',
        [
            ('a:b:c', ':', 2, True, ['a', 'b:c']),
            ('a:b:c', ':', 3, True, ['a', 'b', 'c']),
            ('a:b', ':', 3, True, ['a', 'b', '']),  # Pad on right
            ('a:b', ':', 3, False, ['', 'a', 'b']),  # Pad on left
            ('', ':', 2, True, ['', '']),  # Empty text
            ('a-b-c-d', '-', 2, True, ['a', 'b-c-d']),
        ],
    )
    def test_split_into(self, text: str, pattern: str, n: int, rhs: bool, expected: list[str]):
        """Test splitting string into exactly n parts."""
        assert cls.split_into(text, pattern, n, rhs) == expected

    def test_regex_dict(self):
        """Test compiling dict of regex patterns."""
        patterns = {'num': r'\d+', 'word': r'\w+'}
        result = cls.regex_dict(patterns)
        assert 'num' in result
        assert 'word' in result
        assert isinstance(result['num'], re.Pattern)
        assert isinstance(result['word'], re.Pattern)

        # Test with already compiled patterns
        compiled = cls.regex_dict({'test': re.compile(r'\d+')})
        assert isinstance(compiled['test'], re.Pattern)

    def test_regex_dict__precompiled_pattern_passthrough(self):
        """A precompiled Pattern value is returned by identity, never recompiled."""
        pattern = re.compile(r'\d+')
        result = cls.regex_dict(num=pattern)
        assert result['num'] is pattern

    def test_regex_dict__list_value_joined_with_sep(self):
        """A non-string value is treated as an iterable of strings joined by `sep`."""
        result = cls.regex_dict(sep='|', either=['aa', 'bb'])
        assert result['either'].fullmatch('aa')
        assert result['either'].fullmatch('bb')

    def test_regex_dict__reference_expansion(self):
        """A `{{.name}}` reference expands to an earlier entry's pattern text."""
        result = cls.regex_dict(digit=r'\d', pair=r'{{.digit}}{{.digit}}')
        assert result['pair'].fullmatch('42')
        assert not result['pair'].fullmatch('4')

    def test_regex_dict__escaped_reference_survives_expansion(self):
        r"""An escaped `\{{.name}}` stays literal while an identical unescaped twin expands.

        `str.replace()` used to rewrite the skipped escape as well, producing `a\xx`,
        which failed to compile.
        """
        result = cls.regex_dict(foo='x', pair=r'a\{{.foo}}{{.foo}}')
        assert result['pair'].pattern == r'a\{{.foo}}x'

    def test_regex_dict__reference_to_unknown_group_raises(self):
        """A `{{.name}}` reference to an undefined group raises, naming the group."""
        with pyt.raises(AssertionError, match='non-existent group'):
            cls.regex_dict(pair=r'{{.missing}}')

    def test_regex_dict__invalid_pattern_raises_value_error(self, capsys: pyt.CaptureFixture):
        """An unparsable pattern raises `ValueError` naming the offending key."""
        with pyt.raises(ValueError, match='Invalid Regular Expression "bad"'):
            cls.regex_dict(bad=r'(')
        # Regression guard: no stray debug output on the raising path.
        assert capsys.readouterr().out == ''

    def test_regex_dict__multiline_invalid_pattern_annotates_row(self):
        """A multiline pattern's error report still resolves without crashing."""
        with pyt.raises(ValueError, match=r'ERROR'):
            cls.regex_dict(bad='(?x)\nabc\n(')

    def test_regex_dict__stdlib_re_compile_function_also_reports(self):
        """`compile_function` isn't required to come from the `regex` module either."""
        with pyt.raises(ValueError, match='Invalid Regular Expression "bad"'):
            cls.regex_dict(bad=r'(', compile_function=stdlib_re.compile)  # pyrefly: ignore[bad-argument-type]

    def test_safe_compile__valid_pattern(self):
        """A valid pattern compiles and matches normally."""
        pattern = cls.safe_compile('ok', r'\w+', re.compile)
        assert pattern.fullmatch('abc')

    def test_safe_compile__invalid_pattern_returns_fallback(self, capsys: pyt.CaptureFixture):
        """An invalid pattern reports the error and returns the `'ERROR'` fallback pattern."""
        pattern = cls.safe_compile('broken', r'(', re.compile)
        assert pattern is not None
        assert pattern.pattern == r'ERROR'
        out = capsys.readouterr().out
        assert 'RGX COMPILATION ERROR' in out
        assert 'broken' in out

    def test_safe_compile__stdlib_re_compile_fn_also_falls_back(self):
        """`fn` isn't required to come from the `regex` module -- stdlib `re` must work too."""
        pattern = cls.safe_compile('broken', r'(', stdlib_re.compile)  # pyrefly: ignore[bad-argument-type]
        assert pattern is not None
        assert pattern.pattern == r'ERROR'

    def test_regex_array(self):
        """Test compiling array of (pattern, replacement) tuples."""
        array = [(r'\d+', 'NUM'), (r'\w+', 'WORD')]
        result = cls.regex_array(*array)
        assert len(result) == 2
        assert isinstance(result[0][0], re.Pattern)
        assert result[0][1] == 'NUM'

    @pyt.mark.parametrize(
        'expressions, expected_contains',
        [
            (['a', 'b', 'c'], 'a|b|c'),
            (['test', ['multi', 'part']], 'test|multi ?part'),
        ],
    )
    def test_multi_rgx(self, expressions: list, expected_contains: str):
        """Test combining multiple regex patterns."""
        result = cls.multi_rgx(*expressions)
        assert expected_contains in result
        assert result.startswith('(?:')

    # --------------
    # `1` FORMATTING
    # --------------
    def test_wrap(self):
        """Test wrapping text with decorative borders."""
        result = cls.wrap('TEST')
        assert 'TEST' in result
        assert '---' in result
        lines = result.split('\n')
        assert len(lines) >= 3  # At least top, content, bottom

    @pyt.mark.parametrize(
        'text, n, expected_starts',
        [
            ('hello', 4, '    hello'),
            ('hello', 0, 'hello'),
            ('line1\nline2', 2, '  line1\n  line2'),
        ],
    )
    def test_indent(self, text: str, n: int, expected_starts: str):
        """Test indenting text."""
        result = cls.indent(text, n)
        assert result.startswith(expected_starts.split('\n')[0])

    @pyt.mark.parametrize(
        'text, n, expected',
        [
            ('    hello', 1, 'hello'),
            ('        hello', 2, 'hello'),
            ('hello', 1, 'hello'),
        ],
    )
    def test_unindent(self, text: str, n: int, expected: str):
        assert cls.unindent(text, n) == expected

    @pyt.mark.parametrize(
        'data, expected',
        [
            (' "hello \'world\' " ', "hello 'world'"),
            ('hello world', 'hello world'),
            ('" _**hello_world**_ "', 'hello_world'),
            ('hello world**', 'hello world**'),
        ],
    )
    def test_strip_quotes(self, data: str, expected: str):
        assert cls.strip_quotes(data) == expected

    @pyt.mark.parametrize(
        'text, expected',
        [
            (' a\nb\n ', 'a-b'),
            ('ABC:DEF', 'abc_def'),
            ('a bc : de f', 'a-bc_de-f'),
            ('a,bc : de.f', 'a_bc_def'),
            ('a bc (de f)', 'a-bc_de-f'),
        ],
    )
    def test_clean_string(self, text: str, expected: str):
        assert cls.clean_string(text) == expected

    @pyt.mark.parametrize(
        'case, expected',
        [
            ('lower', 'text case'),
            ('upper', 'TEXT CASE'),
            ('title', 'Text Case'),
            ('capital', 'Text case'),
            ('kebab', 'text-case'),
            ('snake', 'text_case'),
            ('pascal', 'TextCase'),
            ('camel', 'textCase'),
        ],
    )
    def test_recase__all_cases_from_words(self, case: str, expected: str):
        assert cls.recase('Text Case', to=case, clean=False) == expected

    @pyt.mark.parametrize(
        'text, from_case, expected',
        [
            ('foo-bar-baz', 'kebab', 'fooBarBaz'),
            ('foo_bar_baz', 'snake', 'fooBarBaz'),
            ('FooBarBaz', 'pascal', 'fooBarBaz'),
            ('fooBarBaz', 'camel', 'fooBarBaz'),
        ],
    )
    def test_recase__camel_from_other_cases(self, text: str, from_case: str, expected: str):
        assert cls.recase(text, to='camel', _from=from_case, clean=False) == expected

    @pyt.mark.parametrize('empty', ['', '   ', '\n\t'])
    def test_recase__empty_input(self, empty: str):
        assert cls.recase(empty) == ''

    def test_recase__cleans_nonwords_by_default(self):
        assert cls.recase('Hello World!') == 'hello_world'

    def test_recase__accepts_textcase_enum_instances(self):
        assert cls.recase('one two', to=cls.TextCase.KEBAB) == 'one-two'

    def test_pascal_roundtrip(self):
        assert cls.to_pascal('foo_bar') == 'FooBar'
        assert cls.from_pascal('FooBar') == 'foo_bar'
        assert cls.from_pascal(cls.to_pascal('foo_bar')) == 'foo_bar'

    @pyt.mark.parametrize(
        'text, expected',
        [
            ('A', ['A']),
            ('A B', ['A', 'B']),
            ("A'B", ['A', 'B']),
            ('A-B', ['A', 'B']),
            ('A_B', ['A_B']),
            ('', []),
            (',!', []),
            ('abc, cde. efg!', ['abc', 'cde', 'efg']),
        ],
    )
    def test_to_words(self, text: str, expected: list[str]):
        assert cls.to_words(text) == expected

    @pyt.mark.parametrize(
        'article, pos, expected',
        [
            ('line1\nline2\nline3', 0, 1),
            ('line1\nline2\nline3', 6, 2),  # Position of 'l' in line2
            ('line1\nline2\nline3', 12, 3),  # Position of 'l' in line3
            ('line1\nline2\nline3', 'line2', 2),  # Find by substring
            ('line1\nline2\nline3', 'line3', 3),
        ],
    )
    def test_line_num(self, article: str, pos: int | str, expected: int):
        """Test calculating line number from position or substring."""
        assert cls.line_num(article, pos) == expected

    @pyt.mark.parametrize(
        'url, expected',
        [
            ('https://www.example.com/path', 'example.com'),
            ('https://example.com', 'example.com'),
            ('http://www.test.org', 'test.org'),
            ('', ''),
            ('invalid', ''),
        ],
    )
    def test_parse_domain(self, url: str, expected: str):
        """Test extracting domain from URL."""
        assert cls.parse_domain(url) == expected

    def test_wrap_paragraphs(self):
        """Test wrapping paragraphs to specified width."""
        long_text = 'a ' * 100  # Long text that needs wrapping
        result = cls.wrap_paragraphs(long_text, width=50)
        lines = result.split('\n')
        # All lines except possibly the last should be <= 50 chars
        for line in lines[:-1]:
            assert len(line) <= 50

    @pyt.mark.parametrize(
        'lines, expected',
        [
            (
                ['welcome', 'to the ', 'club now', ''],
                ['welcome to the club now'],
            ),
            (
                ['    welcome to', '        the club', '    now.'],
                ['welcome to the club now.'],
            ),
            (
                [
                    '    * welcome     ',
                    '    * >to the-',
                    '    * club-',
                    '    * !now-',
                    '    * - parent',
                    '    *     - child',
                    '    * > quote here',
                    '    * 1. numbered parent',
                    '    *     11. numbered child',
                ],
                [
                    'welcome >to the-club- !now-',
                    '- parent',
                    '    - child',
                    '> quote here',
                    '1. numbered parent',
                    '    11. numbered child',
                ],
            ),
        ],
    )
    def test_unwrap_paragraphs(self, lines: list[str], expected: list[str]):
        assert cls.unwrap_paragraphs('\n'.join(lines)) == '\n'.join(expected)
