############
### HEAD ###
############
### STANDARD
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

    def test_regex_array(self):
        """Test compiling array of (pattern, replacement) tuples."""
        array = [(r'\d+', 'NUM'), (r'\w+', 'WORD')]
        result = cls.regex_array(array)
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
