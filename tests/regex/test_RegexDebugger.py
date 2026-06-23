############
### HEAD ###
############
### STANDARD
# from typing import Any

### EXTERNAL
import regex as re
import pytest as pyt

### INTERNAL
from my.regex.meta import Atom, Regex, GroupAtom
from my.regex.RegexStore import RegexStore, RegexBuffer
from my.regex import RegexDebugger
from ..conftest import boolmap

############
### DATA ###
############
cls = RegexDebugger


############
### BODY ###
############
class TestRegexDebugger:
    @pyt.fixture(scope='class')
    def store(self) -> RegexStore:
        """Create a basic RegexStore for testing."""
        return RegexStore.new(
            dict(separator='', lazy_load=False),
            # Basic patterns for testing
            _word=r'\w+',
            _digit=r'\d+',
            simple=r'hello',
            compound=[r'hello', r' ', r'world'],
            with_group=('[]:', [r'test', r' ', r'pattern']),
            optional=[r'start', ('|:?', [r'opt1', r'opt2']), r'end'],
            nested=('[]:', [r'outer', ('[]:', [r'inner', r'nested'])]),
            with_flag=('m', [r'^line', r'$']),
            complex_optional=[r'required', ('|:?', [r'maybe1', r'maybe2']), ('|:?', [r'maybe3'])],
            year=r'(?<![[:alnum:]])(?:1?\d\d\d|20[01]\d|202[0-6])(?=$|[\W_a-p])',
            month=r'(?i)\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\b',
        )

    @pyt.fixture(scope='class')
    def debugger(self, store: RegexStore) -> RegexDebugger:
        """Create a RegexDebugger from the store fixture."""
        return RegexDebugger.new_debugger(store)

    # -------------------
    # `.` Initial Methods
    # -------------------
    def test_new_debugger(self, store: RegexStore):
        """Test creating a debugger from an existing RegexStore."""
        debugger = cls.new_debugger(store)
        assert isinstance(debugger, cls)
        # Should have all the patterns from the original store
        assert debugger.definitions == store.definitions
        assert debugger.options == store.options
        # Should inherit all store functionality
        assert debugger.match('simple', 'hello')
        assert not debugger.match('simple', 'goodbye')

    def test_new_debugger__preserves_patterns(self, store: RegexStore):
        """Test that debugger preserves all patterns and can compile them."""
        debugger = cls.new_debugger(store)
        # All patterns should be accessible
        for name in store.definitions.keys():
            pattern = debugger[name]
            assert isinstance(pattern, re.Pattern)

    # -------------------
    # `-` Private Methods
    # -------------------
    @pyt.mark.parametrize(
        'pattern_name, text, expected',
        [
            # All atoms succeed
            ('simple', 'hello', 5),
            ('compound', 'hello world', 11),
            # First atom fails
            ('simple', 'goodbye', 1),
            # Middle atom fails
            ('compound', 'hello there', 7),
            ('compound', 'hello ', 7),
            # Last atom fails
            ('simple', 'helly', 5),
        ],
    )
    def test_pinpoint_failure(
        self, debugger: RegexDebugger, pattern_name: str, text: str, expected: int
    ):
        """Test pinpointing which atom in a pattern causes failure."""
        atoms = Regex(debugger.definitions[pattern_name])
        # Drill through wrapper groups
        while len(atoms) == 1 and isinstance(grp := atoms.one, GroupAtom):
            if debugger._do_drill(grp):
                atoms = Regex(grp.body)
            else:
                break

        buffer = RegexBuffer(text)
        prefix = ''
        failed_idx, _ = debugger.pinpoint_failure(buffer, atoms, prefix)
        assert failed_idx == expected

    @pyt.mark.parametrize(
        'pattern_name, text',
        [
            ('simple', 'hello'),
            ('compound', 'hello world'),
            ('with_group', 'test pattern'),
        ],
    )
    def test_pinpoint_failure__successful_match(
        self, debugger: RegexDebugger, pattern_name: str, text: str
    ):
        """Test pinpoint_failure when all atoms match successfully."""
        atoms = Regex(debugger.definitions[pattern_name])
        # Drill through wrapper groups
        while len(atoms) == 1 and isinstance(grp := atoms.one, GroupAtom):
            if debugger._do_drill(grp):
                atoms = Regex(grp.body)
            else:
                break

        buffer = RegexBuffer(text)
        prefix = ''
        failed_idx, last_match = debugger.pinpoint_failure(buffer, atoms, prefix)
        # Should return length when all succeed
        assert failed_idx == len(atoms)
        assert last_match.match is not None

    @pyt.mark.parametrize(
        'text, expected',
        boolmap(
            false=[
                r'(?:a)+',
                r'(?:a)?',
                r'(?:a)*',
                r'(?:a|b)',
                r'(?=P<a>b)',
            ],
            true=[
                r'(?:abc)',
                r'(?is:abc)',
                r'(?>xyz)',
            ],
        ),
    )
    def test_do_drill(self, debugger: RegexDebugger, text: str, expected: bool):
        # Create a mock GroupAtom
        expr = Regex(text)
        group = expr.one
        assert isinstance(group, GroupAtom)
        assert debugger._do_drill(group) == expected

    def test_curate(self, debugger: RegexDebugger):
        # Create simple atoms
        atoms = Regex('hello world')
        failed_idx = 6  # 'world' failed
        flags = Atom('')
        result = debugger.curate(atoms, failed_idx, flags)
        # Should include atoms up to failure point
        assert result == r'^w'

    def test_curate__with_optional(self, debugger: RegexDebugger):
        atoms = debugger.definitions['complex_optional']
        atoms = Regex(atoms)
        # Drill through wrapper
        while len(atoms) == 1 and isinstance(grp := atoms.one, GroupAtom):
            if debugger._do_drill(grp):
                atoms = Regex(grp.body)
            else:
                break

        failed_idx = 2
        flags = Atom('')
        result = debugger.curate(atoms, failed_idx, flags)
        # Should walk back to include optional atoms
        assert result  # Should produce a valid result

    @pyt.mark.parametrize(
        'format_method, input_text',
        [
            ('_format_expr', 'test expression'),
            ('_format_data', 'match data'),
            ('_format_curated', 'curated regex'),
            ('_format_text', 'unmatched text'),
            ('_format_fulltext', 'full text content'),
            ('_format_fullexpr', 'full expression'),
        ],
    )
    def test_format_methods(self, debugger: RegexDebugger, format_method: str, input_text: str):
        method = getattr(debugger, format_method)
        result = method(input_text)
        assert isinstance(result, str)
        assert input_text in result
        assert '-' in result  # Header separator

    def test_format_early_return(self, debugger: RegexDebugger):
        result = debugger._format_early_return(
            name='test_pattern',
            explanation='failed to match',
            text='sample text',
            expr='test.*pattern',
        )
        assert isinstance(result, list)
        assert len(result) == 3
        assert 'test_pattern' in result[0]
        assert 'failed to match' in result[0]
        assert 'sample text' in result[1]
        assert 'test.*pattern' in result[2]

    # -------------------
    # `+` Primary Methods
    # -------------------
    def test_debug_failed_match__simple_failure(self, debugger: RegexDebugger):
        text = RegexBuffer('goodbye')
        result = debugger.debug_failed_match('simple', text)
        assert isinstance(result, list)
        assert len(result) > 0
        # Should contain some diagnostic information
        assert any('atom' in str(s).lower() for s in result)

    def test_debug_failed_match__partial_match(self, debugger: RegexDebugger):
        text = RegexBuffer('hello there')
        result = debugger.debug_failed_match('compound', text)
        assert isinstance(result, list)
        assert len(result) > 0
        # Should identify the successful part and the failure
        assert any('match' in str(s).lower() for s in result)

    def test_debug_failed_match__all_atoms_failed(self, debugger: RegexDebugger):
        text = RegexBuffer('xyz123')
        result = debugger.debug_failed_match('simple', text)
        assert isinstance(result, list)
        assert any('All atoms' in str(s) or 'first atom' in str(s) for s in result)

    def test_debug_failed_match__all_atoms_succeeded(self, debugger: RegexDebugger):
        text = RegexBuffer('hello world extra text')
        result = debugger.debug_failed_match('compound', text)
        assert isinstance(result, list)
        # Should indicate all atoms matched
        assert any('success' in str(s).lower() or 'matched' in str(s).lower() for s in result)

    # ------------------
    # `*` Public Methods
    # ------------------
    @pyt.mark.parametrize(
        'names, text, matched, expected, func',
        [
            # Expected match but got incorrect data
            ('simple', 'hello', True, True, 'match'),
            # Unexpected match when should have failed
            ('simple', 'hello', True, False, 'match'),
            # Failed to match when expected to
            ('simple', 'goodbye', False, True, 'match'),
            # Multiple patterns
            (['simple', 'compound'], 'test', False, True, 'search'),
        ],
    )
    def test_debug__various_scenarios(
        self,
        debugger: RegexDebugger,
        names: str | list[str],
        text: str,
        matched: bool,
        expected: bool,
        func: str,
    ):
        result = debugger.debug(names, text, matched, expected, func)
        assert isinstance(result, str)
        assert len(result) > 0
        # Should contain header
        assert 'REGEX DEBUGGER' in result
        # Should contain the pattern name
        if isinstance(names, str):
            assert names.upper() in result
        else:
            assert names[0].upper() in result
        # Should contain text
        assert text in result or text[:20] in result

    def test_debug__failed_match(self, debugger: RegexDebugger):
        result = debugger.debug('simple', 'goodbye', matched=False, expected=True, func='match')
        assert 'REGEX DEBUGGER' in result
        assert 'FAILED TO MATCH' in result
        assert 'goodbye' in result

    def test_debug__unexpected_match(self, debugger: RegexDebugger):
        result = debugger.debug('simple', 'hello', matched=True, expected=False, func='match')
        assert 'REGEX DEBUGGER' in result
        assert 'UNEXPECTEDLY MATCHED' in result

    def test_debug__incorrect_match(self, debugger: RegexDebugger):
        result = debugger.debug('simple', 'hello', matched=True, expected=True, func='match')
        assert 'REGEX DEBUGGER' in result
        assert 'INCORRECTLY MATCHED' in result

    def test_debug__with_function_name(self, debugger: RegexDebugger):
        result = debugger.debug('simple', 'test', matched=False, expected=True, func='search')
        assert 'search()' in result or 'SEARCH' in result

    def test_debug__multiple_patterns(self, debugger: RegexDebugger):
        names = ['simple', 'compound']
        result = debugger.debug(names, 'test text', matched=False, expected=True)
        assert 'REGEX DEBUGGER' in result
        # Should debug each pattern
        for name in names:
            assert name.upper() in result or name in result

    def test_debug__raises_on_invalid_input(self, debugger: RegexDebugger):
        with pyt.raises(ValueError, match='why call debug'):
            debugger.debug('simple', 'text', matched=False, expected=False)

    # -----------------
    # Integration Tests
    # -----------------
    def test_integration__year_pattern_failure(self, debugger: RegexDebugger):
        # Test with invalid year
        text = '2030'  # Outside valid range for year pattern
        result = debugger.debug('year', text, matched=False, expected=True)
        assert isinstance(result, str)
        assert 'REGEX DEBUGGER' in result
        assert '2030' in result

    def test_integration__month_pattern_success(self, debugger: RegexDebugger):
        # Should match various month formats
        for month in ['january', 'Jan', 'FEBRUARY', 'mar']:
            match = debugger.match('month', month)
            assert match is not None

    def test_integration__complex_pattern_debugging(self, debugger: RegexDebugger):
        text = RegexBuffer('outer text')
        result = debugger.debug_failed_match('nested', text)
        assert isinstance(result, list)
        assert len(result) > 0
        # Should provide diagnostic information
        diagnostic_text = ' '.join(str(s) for s in result)
        assert len(diagnostic_text) > 0

    def test_integration__optional_atoms_debugging(self, debugger: RegexDebugger):
        text = 'requiredend'  # Missing optional parts
        result = debugger.debug('optional', text, matched=False, expected=True)
        assert 'REGEX DEBUGGER' in result
        # Should walk back to include optional atoms in curated output

    # ----------
    # Edge Cases
    # ----------
    def test_edge_case__empty_pattern(self, debugger: RegexDebugger):
        # Even simple patterns should be debuggable
        text = 'test'
        result = debugger.debug('simple', text, matched=False, expected=True)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_edge_case__long_text(self, debugger: RegexDebugger):
        long_text = 'x' * 1000
        result = debugger.debug('simple', long_text, matched=False, expected=True)
        assert isinstance(result, str)

    def test_edge_case__special_characters(self, debugger: RegexDebugger):
        special_text = r'hello.*world\d+[a-z]'
        result = debugger.debug('simple', special_text, matched=False, expected=True)
        assert isinstance(result, str)

    def test_sanitize_output(self, debugger: RegexDebugger):
        result = debugger.debug('compound', 'test', matched=False, expected=True)
        assert isinstance(result, str)

    def test_debugger_inherits_store_methods(self, debugger: RegexDebugger):
        # Should be able to use all RegexStore methods
        assert hasattr(debugger, 'match')
        assert hasattr(debugger, 'fullmatch')
        assert hasattr(debugger, 'finditer')
        assert hasattr(debugger, 'parse')
        assert hasattr(debugger, 'compose')

        # Test some basic functionality
        assert debugger.match('simple', 'hello')
        assert not debugger.match('simple', 'goodbye')

    def test_patterns_accessible(self, debugger: RegexDebugger, store: RegexStore):
        for name in store.definitions.keys():
            assert name in debugger.definitions
            # Should be able to get compiled pattern
            pattern = debugger[name]
            assert isinstance(pattern, re.Pattern)
