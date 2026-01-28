############
### HEAD ###
############
### STANDARD
from typing import Any

### EXTERNAL
import pytest as pyt
import regex as re

### INTERNAL
from my.regex.meta import ParseData
from my.regex import MatchData
from ...conftest import boolmap

############
### DATA ###
############
cls = ParseData


############
### BODY ###
############
class TestParseData:
    # -------------------
    # `.` Initial Methods
    # -------------------
    def test_init__empty(self):
        pd = cls()
        assert pd.captures == {}
        assert pd.starts == {}
        assert pd.field == ''
        assert pd.value == []
        assert pd.start == []

    def test_init__with_data(self):
        pd = cls(
            captures={'field1': ['value1', 'value2']},
            starts={'field1': [0, 10]},
        )
        assert 'field1' in pd.captures
        assert pd.starts['field1'] == [0, 10]

    # -------------------
    # `-` Private Methods
    # -------------------
    def test_interleave__add_to_new_field(self):
        pd = cls()
        effects = [(0, 'value1'), (5, 'value2')]

        pd.interleave('', 'dest', effects)

        assert pd.captures['dest'] == ['value1', 'value2']
        assert pd.starts['dest'] == [0, 5]

    def test_interleave__merge_with_existing(self):
        pd = cls(
            captures={'dest': ['existing']},
            starts={'dest': [10]},
        )

        effects = [(0, 'new1'), (20, 'new2')]
        pd.interleave('', 'dest', effects)

        # Should be sorted by start position
        assert pd.captures['dest'] == ['new1', 'existing', 'new2']
        assert pd.starts['dest'] == [0, 10, 20]

    def test_interleave__consume_from_source(self):
        pd = cls(
            captures={'src': ['val1', 'val2', 'val3']},
            starts={'src': [0, 5, 10]},
        )

        # Move some values from src to dest
        effects = [(0, 'transformed1'), (10, 'transformed3')]
        pd.interleave('src', 'dest', effects)

        # src should only have unconsumed value
        assert pd.captures['src'] == ['val2']
        assert pd.starts['src'] == [5]

        # dest should have consumed values
        assert pd.captures['dest'] == ['transformed1', 'transformed3']
        assert pd.starts['dest'] == [0, 10]

    def test_interleave__consume_all_removes_source(self):
        pd = cls(
            captures={'src': ['val1', 'val2']},
            starts={'src': [0, 5]},
        )

        # Consume all values
        effects = [(0, 'new1'), (5, 'new2')]
        pd.interleave('src', 'dest', effects)

        # src should be removed entirely
        assert 'src' not in pd.captures
        assert 'src' not in pd.starts

        # dest should have all values
        assert pd.captures['dest'] == ['new1', 'new2']

    def test_interleave__hidden_field_not_consumed(self):
        pd = cls(
            captures={'_hidden': ['val1']},
            starts={'_hidden': [0]},
        )

        # Hidden fields (starting with _) should not be consumed
        effects = [(0, 'new')]
        pd.interleave('_hidden', 'dest', effects)

        # _hidden should still exist
        assert '_hidden' in pd.captures
        assert pd.captures['dest'] == ['new']

    def test_interleave__empty_effects(self):
        pd = cls(
            captures={'dest': ['existing']},
            starts={'dest': [5]},
        )

        pd.interleave('', 'dest', [])

        # Should remain unchanged
        assert pd.captures['dest'] == ['existing']
        assert pd.starts['dest'] == [5]

    def test_interleave__maintains_sort_order(self):
        pd = cls(
            captures={'dest': ['mid']},
            starts={'dest': [10]},
        )

        # Add out-of-order effects
        effects = [(20, 'last'), (0, 'first'), (15, 'middle')]
        pd.interleave('', 'dest', effects)

        # Should be sorted by start position
        assert pd.starts['dest'] == [0, 10, 15, 20]
        assert pd.captures['dest'] == ['first', 'mid', 'middle', 'last']

    # -------------------
    # `+` Primary Methods
    # -------------------
    def test_apply_dict_parser(self):
        # Create a pattern with named groups
        pattern = re.compile(r'(?P<name>\w+):(?P<value>\d+)')

        pd = cls(
            captures={'field': ['test:123', 'foo:456']},
            starts={'field': [0, 10]},
        )
        pd.set_field('field')

        # Parser remaps 'name' to 'names' field
        parser = {'names': 'name'}

        pd.apply_dict_parser(parser, pattern)

        # Should have created 'names' field with remapped values
        assert 'names' in pd.captures
        assert pd.captures['names'] == ['test', 'foo']

    def test_apply_dict_parser__multiple_remaps(self):
        pattern = re.compile(r'(?P<key>\w+)=(?P<val>\d+)')

        pd = cls(
            captures={'data': ['a=1', 'b=2']},
            starts={'data': [0, 5]},
        )
        pd.set_field('data')

        parser = {'keys': 'key', 'values': 'val'}

        pd.apply_dict_parser(parser, pattern)

        assert pd.captures['keys'] == ['a', 'b']
        assert pd.captures['values'] == ['1', '2']

    def test_apply_dict_parser__preserves_positions(self):
        pattern = re.compile(r'(?P<word>\w+)')

        pd = cls(
            captures={'text': ['hello', 'world']},
            starts={'text': [0, 10]},
        )
        pd.set_field('text')

        parser = {'words': 'word'}

        pd.apply_dict_parser(parser, pattern)

        # Positions should be preserved
        assert pd.starts['words'] == [0, 10]

    def test_apply_dict_parser__no_matching_fields(self):
        pattern = re.compile(r'(?P<name>\w+)')

        pd = cls(
            captures={'field': ['test']},
            starts={'field': [0]},
        )
        pd.set_field('field')

        # Parser maps field that doesn't exist in pattern
        parser = {'output': 'nonexistent'}

        pd.apply_dict_parser(parser, pattern)

        # Should not create output field
        assert 'output' not in pd.captures

    def test_apply_func_parser__string_return(self):
        pd = cls(
            captures={'field': ['hello', 'world']},
            starts={'field': [0, 10]},
        )
        pd.set_field('field')

        # Parser returns string - simple transformation
        def parser(s: str) -> str:
            return s.upper()

        pd.apply_func_parser(parser)

        # Should transform in place
        assert pd.captures['field'] == ['HELLO', 'WORLD']
        assert pd.starts['field'] == [0, 10]

    def test_apply_func_parser__dict_return(self):
        pd = cls(
            captures={'field': ['key:value', 'foo:bar']},
            starts={'field': [0, 15]},
        )
        pd.set_field('field')

        # Parser returns dict - creates new fields
        def parser(s: str) -> dict[str, str]:
            parts = s.split(':')
            return {'key': parts[0], 'value': parts[1]}

        pd.apply_func_parser(parser)

        # Should create new fields
        assert pd.captures['key'] == ['key', 'foo']
        assert pd.captures['value'] == ['value', 'bar']
        # Original field should be consumed
        assert 'field' not in pd.captures

    def test_apply_func_parser__dict_return_preserves_positions(self):
        pd = cls(
            captures={'data': ['a=1', 'b=2']},
            starts={'data': [5, 20]},
        )
        pd.set_field('data')

        def parser(s: str) -> dict[str, str]:
            k, v = s.split('=')
            return {'k': k, 'v': v}

        pd.apply_func_parser(parser)

        # Positions should match original
        assert pd.starts['k'] == [5, 20]
        assert pd.starts['v'] == [5, 20]

    def test_apply_func_parser__dict_return_partial_fields(self):
        pd = cls(
            captures={'field': ['has:value', 'no_colon']},
            starts={'field': [0, 15]},
        )
        pd.set_field('field')

        def parser(s: str) -> dict[str, str]:
            if ':' in s:
                k, v = s.split(':')
                return {'k': k, 'v': v}
            return {'k': s}

        pd.apply_func_parser(parser)

        # Should handle partial results
        assert len(pd.captures['k']) == 2
        assert len(pd.captures['v']) == 1  # Only first item had value

    def test_apply_func_parser__dict_consumes_source_when_unique(self):
        pd = cls(
            captures={'source': ['data1', 'data2']},
            starts={'source': [0, 10]},
        )
        pd.set_field('source')

        def parser(s: str) -> dict[str, str]:
            return {'other': s.upper()}

        pd.apply_func_parser(parser)

        # source should be consumed since 'other' is a different field
        assert 'source' not in pd.captures
        assert pd.captures['other'] == ['DATA1', 'DATA2']

    def test_apply_func_parser__dict_keeps_source_when_same_name(self):
        pd = cls(
            captures={'field': ['data']},
            starts={'field': [0]},
        )
        pd.set_field('field')

        def parser(s: str) -> dict[str, str]:
            # Returns same field name - should not consume
            return {'field': s.upper(), 'other': s.lower()}

        pd.apply_func_parser(parser)

        # field should still exist (transformed)
        assert 'field' in pd.captures

    # ------------------
    # `*` Public Methods
    # ------------------
    @pyt.mark.parametrize(
        'captures, field, expected',
        [
            ({'field1': ['val']}, 'field1', True),
            ({'field1': ['val']}, 'field2', False),
            ({}, 'field', False),
        ],
    )
    def test_contains(self, captures: dict, field: str, expected: bool):
        pd = cls(
            captures=captures,
            starts={k: [0] for k in captures.keys()},
        )
        assert (field in pd) == expected

    def test_contains__requires_both_captures_and_starts(self):
        pd = cls(
            captures={'field': ['val']},
            starts={},  # Missing starts
        )
        assert 'field' not in pd

    @pyt.mark.parametrize(
        'captures, expected_len',
        [
            ({}, 0),
            ({'field1': ['val']}, 1),
            ({'field1': ['val'], 'field2': ['val']}, 2),
            ({'f1': [], 'f2': [], 'f3': []}, 3),
        ],
    )
    def test_len(self, captures: dict, expected_len: int):
        pd = cls(captures=captures)
        assert len(pd) == expected_len

    def test_items(self):
        pd = cls(
            captures={'field1': ['val1', 'val2'], 'field2': ['val3']},
            starts={'field1': [0, 5], 'field2': [10]},
        )

        items = pd.items()

        assert len(items) == 2
        assert ('field1', ([0, 5], ['val1', 'val2'])) in items
        assert ('field2', ([10], ['val3'])) in items

    def test_items__empty(self):
        pd = cls()
        assert pd.items() == []

    def test_keys(self):
        pd = cls(
            captures={'field1': ['val1'], 'field2': ['val2'], 'field3': ['val3']},
        )

        keys = pd.keys()

        assert len(keys) == 3
        assert 'field1' in keys
        assert 'field2' in keys
        assert 'field3' in keys

    def test_keys__empty(self):
        pd = cls()
        assert pd.keys() == []

    def test_values(self):
        pd = cls(
            captures={'field1': ['val1'], 'field2': ['val2']},
            starts={'field1': [0], 'field2': [5]},
        )

        values = pd.values()

        assert len(values) == 2
        assert ([0], ['val1']) in values
        assert ([5], ['val2']) in values

    def test_values__empty(self):
        pd = cls()
        assert pd.values() == []

    def test_set_field(self):
        pd = cls(
            captures={'field': ['val1', 'val2']},
            starts={'field': [0, 5]},
        )

        pd.set_field('field')

        assert pd.field == 'field'
        assert pd.value == ['val1', 'val2']
        assert pd.start == [0, 5]

        # Should be removed from captures/starts
        assert 'field' not in pd.captures
        assert 'field' not in pd.starts

    def test_set_field__invalid_field(self):
        pd = cls(
            captures={'field1': ['val']},
            starts={'field1': [0]},
        )

        with pyt.raises(AssertionError, match='Invalid field'):
            pd.set_field('nonexistent')

    def test_set_field__requires_both(self):
        pd = cls(
            captures={'field': ['val']},
            starts={},  # Missing starts
        )

        with pyt.raises(AssertionError, match='Invalid field'):
            pd.set_field('field')

    # ----------------
    # Integration Tests
    # ----------------
    def test_workflow__multiple_parsers(self):
        """Test applying multiple parsers in sequence."""
        pd = cls(
            captures={'raw': ['user:alice:25', 'user:bob:30']},
            starts={'raw': [0, 20]},
        )

        # First parser: split by colons
        pd.set_field('raw')

        def split_parser(s: str) -> dict[str, str]:
            parts = s.split(':')
            return {'type': parts[0], 'name': parts[1], 'age': parts[2]}

        pd.apply_func_parser(split_parser)

        # Second parser: transform names to uppercase
        pd.set_field('name')

        def upper_parser(s: str) -> str:
            return s.upper()

        pd.apply_func_parser(upper_parser)

        assert pd.captures['name'] == ['ALICE', 'BOB']
        assert pd.captures['type'] == ['user', 'user']
        assert pd.captures['age'] == ['25', '30']

    def test_workflow__dict_parser_with_regex(self):
        """Test dict parser with actual regex pattern."""
        pattern = re.compile(r'(?P<year>\d{4})-(?P<month>\d{2})-(?P<day>\d{2})')

        pd = cls(
            captures={'dates': ['2024-01-15', '2024-12-25']},
            starts={'dates': [0, 15]},
        )
        pd.set_field('dates')

        # Remap to new field names
        parser = {'years': 'year', 'months': 'month', 'days': 'day'}

        pd.apply_dict_parser(parser, pattern)

        assert pd.captures['years'] == ['2024', '2024']
        assert pd.captures['months'] == ['01', '12']
        assert pd.captures['days'] == ['15', '25']

    def test_workflow__interleave_from_multiple_sources(self):
        """Test interleaving captures from multiple sources."""
        pd = cls(
            captures={
                'src1': ['val1', 'val2'],
                'src2': ['val3', 'val4'],
            },
            starts={
                'src1': [0, 10],
                'src2': [5, 15],
            },
        )

        # Interleave from src1
        pd.interleave('src1', 'combined', [(0, 'new1'), (10, 'new2')])

        # Interleave from src2
        pd.interleave('src2', 'combined', [(5, 'new3'), (15, 'new4')])

        # Should be sorted by position
        assert pd.starts['combined'] == [0, 5, 10, 15]
        assert pd.captures['combined'] == ['new1', 'new3', 'new2', 'new4']

        # Sources should be consumed
        assert 'src1' not in pd.captures
        assert 'src2' not in pd.captures

    # ----------------
    # Edge Cases Tests
    # ----------------
    def test_empty_captures_list(self):
        """Test handling of empty captures list."""
        pd = cls(
            captures={'field': []},
            starts={'field': []},
        )

        assert 'field' in pd
        assert len(pd) == 1
        assert pd.captures['field'] == []

    def test_single_value(self):
        """Test with single captured value."""
        pd = cls(
            captures={'single': ['value']},
            starts={'single': [0]},
        )
        pd.set_field('single')

        def parser(s: str) -> str:
            return s.upper()

        pd.apply_func_parser(parser)

        assert pd.captures['single'] == ['VALUE']

    def test_many_captures(self):
        """Test with many captured values."""
        n = 100
        pd = cls(
            captures={'many': [f'val{i}' for i in range(n)]},
            starts={'many': list(range(0, n * 10, 10))},
        )
        pd.set_field('many')

        def parser(s: str) -> str:
            return s.upper()

        pd.apply_func_parser(parser)

        assert len(pd.captures['many']) == n

    def test_complex_interleaving(self):
        """Test complex interleaving with many values."""
        pd = cls(
            captures={'existing': ['e1', 'e2', 'e3']},
            starts={'existing': [10, 30, 50]},
        )

        # Add many new values at various positions
        effects = [(0, 'n1'), (20, 'n2'), (40, 'n3'), (60, 'n4'), (5, 'n5')]
        pd.interleave('', 'existing', effects)

        # Should be properly sorted
        assert pd.starts['existing'] == [0, 5, 10, 20, 30, 40, 50, 60]
        assert pd.captures['existing'] == ['n1', 'n5', 'e1', 'n2', 'e2', 'n3', 'e3', 'n4']

    def test_parser_with_special_characters(self):
        """Test parsers with special characters in values."""
        pd = cls(
            captures={'field': ['test@example.com', 'foo#bar']},
            starts={'field': [0, 20]},
        )
        pd.set_field('field')

        def parser(s: str) -> str:
            return s.replace('@', '_at_').replace('#', '_hash_')

        pd.apply_func_parser(parser)

        assert pd.captures['field'] == ['test_at_example.com', 'foo_hash_bar']

    def test_dict_parser_with_overlapping_positions(self):
        """Test dict parser when multiple captures have same start position."""
        pattern = re.compile(r'(?P<word>\w+)')

        pd = cls(
            captures={'text': ['hello', 'world']},
            starts={'text': [0, 0]},  # Same position
        )
        pd.set_field('text')

        parser = {'words': 'word'}

        pd.apply_dict_parser(parser, pattern)

        # Should handle duplicate positions
        assert len(pd.captures['words']) == 2
        assert pd.starts['words'] == [0, 0]

    def test_func_parser_empty_dict_result(self):
        """Test func parser that returns empty dict."""
        pd = cls(
            captures={'field': ['val1', 'val2']},
            starts={'field': [0, 5]},
        )
        pd.set_field('field')

        def parser(s: str) -> dict[str, str]:
            return {}  # Empty dict

        pd.apply_func_parser(parser)

        # Should handle empty results
        # field should be removed since no affected fields
        assert 'field' not in pd.captures

    def test_interleave_with_duplicate_positions(self):
        """Test interleaving with duplicate start positions."""
        pd = cls()

        effects = [(0, 'val1'), (0, 'val2'), (5, 'val3')]
        pd.interleave('', 'field', effects)

        # Should keep all values even with duplicate positions
        assert len(pd.captures['field']) == 3
        assert pd.starts['field'] == [0, 0, 5]

    def test_multiple_set_field_calls(self):
        """Test calling set_field multiple times."""
        pd = cls(
            captures={'field1': ['val1'], 'field2': ['val2']},
            starts={'field1': [0], 'field2': [5]},
        )

        pd.set_field('field1')
        assert pd.field == 'field1'
        assert pd.value == ['val1']

        # Set different field
        pd.set_field('field2')
        assert pd.field == 'field2'
        assert pd.value == ['val2']

    def test_preserves_data_types(self):
        """Test that string values are preserved correctly."""
        pd = cls(
            captures={'nums': ['123', '456']},
            starts={'nums': [0, 5]},
        )

        # Values should remain strings
        assert all(isinstance(v, str) for v in pd.captures['nums'])

    def test_interleave_preserves_order_stability(self):
        """Test that interleave preserves stable sort order."""
        pd = cls()

        # Add effects in specific order, all with same position
        effects = [(0, 'third'), (0, 'first'), (0, 'second')]
        pd.interleave('', 'field', effects)

        # Should maintain stable sort (original order when positions equal)
        assert pd.captures['field'] == ['third', 'first', 'second']
