############
### HEAD ###
############
### STANDARD
from typing import Annotated

### EXTERNAL
import pytest as pyt
import pydantic as pyd
import regex as re

### INTERNAL
from my.utils import SyntaxUtils

cls = SyntaxUtils


############
### BODY ###
############
class TestSyntaxUtils:
    @pyt.mark.parametrize(
        'tree, expected',
        [
            # Simple tree with None values
            ({'a': None, 'b': None}, {'a': {}, 'b': {}}),
            # Nested tree with None values
            ({'a': {'x': None, 'y': None}, 'b': None}, {'a': {'x': {}, 'y': {}}, 'b': {}}),
            # Tree with mixed None and dict values
            ({'a': None, 'b': {'c': None}}, {'a': {}, 'b': {'c': {}}}),
            # Tree with no None values (no change)
            ({'a': {}, 'b': {}}, {'a': {}, 'b': {}}),
            # Empty tree
            ({}, {}),
            # Tree with non-None leaf values (no change to leaves)
            ({'a': 1, 'b': 'test'}, {'a': 1, 'b': 'test'}),
        ],
    )
    def test_fill_tree(self, tree: dict, expected: dict):
        """Test filling None values with empty dicts in tree structure."""
        cls.fill_tree(tree)
        assert tree == expected

    @pyt.mark.parametrize(
        'tree, expected',
        [
            # Single leaf
            ('leaf', 1),
            (42, 1),
            # Empty dict (no leaves)
            ({}, 0),
            # Flat dict with leaves
            ({'a': 1, 'b': 2, 'c': 3}, 3),
            # Nested dict with leaves
            ({'a': {'x': 1, 'y': 2}, 'b': 3}, 3),
            # Deeply nested dict
            ({'a': {'b': {'c': 1}}}, 1),
            # Mixed depth tree
            ({'a': 1, 'b': {'c': 2, 'd': 3}, 'e': {'f': {'g': 4}}}, 4),
        ],
    )
    def test_tree_size(self, tree: object, expected: int):
        """Test counting leaf nodes in tree structure."""
        assert cls.tree_size(tree) == expected

    def test_pyd_schemify(self):
        """Test Pydantic schema creation for type validation."""
        # Test with regex Pattern
        pattern = re.compile(r'\d+')

        # Create a Pydantic model using the RegexField
        class TestModel(pyd.BaseModel):
            pattern: cls.RegexField

        # Should accept regex Pattern
        model = TestModel(pattern=pattern)
        assert model.pattern == pattern

        # Should reject non-Pattern types
        with pyt.raises(pyd.ValidationError):
            TestModel(pattern="not a pattern")

    def test_regex_field(self):
        """Test RegexField type annotation."""
        pattern = re.compile(r'test')

        class Model(pyd.BaseModel):
            regex: cls.RegexField

        m = Model(regex=pattern)
        assert m.regex == pattern

    def test_match_field(self):
        """Test MatchField type annotation."""
        pattern = re.compile(r'(\d+)')
        match = pattern.search('123')

        class Model(pyd.BaseModel):
            match: cls.MatchField

        m = Model(match=match)
        assert m.match == match
