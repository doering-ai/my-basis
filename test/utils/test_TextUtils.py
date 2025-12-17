############
### HEAD ###
############
### STANDARD

### EXTERNAL
import pytest as pyt

### INTERNAL
from my.utils import TextUtils

cls = TextUtils


############
### BODY ###
############
class TestUtils:
    # ------------------------
    # `0` MANIPULATION & REGEX
    # ------------------------
    # @pyt.mark.parametrize('data, expected', [])
    # def test_regex_dict(self, data: str, expected: str):
    #     assert cls.regex_dict(data) == expected

    # @pyt.mark.parametrize('data, expected', [])
    # def test_regex_array(self, data: str, expected: str):
    #     assert cls.regex_array(data) == expected

    # @pyt.mark.parametrize('data, expected', [])
    # def test_spaced_rgx(self, data: str, expected: str):
    #     assert cls.spaced_rgx(data) == expected

    # @pyt.mark.parametrize('data, expected', [])
    # def test_multi_rgx(self, data: str, expected: str):
    #     assert cls.multi_rgx(data) == expected

    # --------------
    # `1` FORMATTING
    # --------------
    @pyt.mark.parametrize('data, expected', [])
    def test_wrap(self, data: str, expected: str):
        pass

    @pyt.mark.parametrize('data, expected', [])
    def test_indent(self, data: str, expected: str):
        pass

    @pyt.mark.parametrize('data, expected', [])
    def test_unindent(self, data: str, expected: str):
        pass

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

    # @pyt.mark.parametrize('data, expected', [])
    # def test_line_num(self, data: str, expected: str):
    #     assert cls.line_num(data) == expected

    # @pyt.mark.parametrize('data, expected', [])
    # def test_parse_domain(self, data: str, expected: str):
    #     assert cls.parse_domain(data) == expected

    @pyt.mark.parametrize('data, expected', [])
    def test_wrap_paragraphs(self, data: str, expected: str):
        pass

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
