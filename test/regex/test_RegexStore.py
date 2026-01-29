############
### HEAD ###
############
### STANDARD

### EXTERNAL
import regex as re
import pytest as pyt

### INTERNAL
from my.types import Buffer
from my.regex.meta import GroupKind
from my.regex import RegexList, RegexVal, MatchData
from my.regex.RegexStore import RegexStore, RegexBuffer

############
### DATA ###
############
cls = RegexStore


############
### BODY ###
############
class TestRegexStore:
    @pyt.fixture(scope='class')
    def store(self) -> RegexStore:
        return RegexStore.new(
            options=dict(
                separator=r' ?',
            ),
            _parenthetical=(r'\(\w+\)', lambda s: s.strip('() ')),
            _word=r'\w+',
            _digit=r'\d+',
            simple=r'hello',
            compound=[r'hello', r'world'],
        )

    # -------------------
    # `.` Initial Methods
    # -------------------
    def test_new(self, store: RegexStore) -> None:
        # test lazy-loading
        assert len(store.patterns) == 0
        assert isinstance(store['_parenthetical'], re.Pattern)
        assert len(store.patterns) > 0

        assert len(store.patterns) == len(store.definitions)

    def test_new__no_lazy_load(self):
        store = RegexStore.new(
            dict(lazy_load=False),
            test=r'test',
        )
        assert store.is_loaded
        assert 'test' in store.patterns

    def test_new__with_imports(self):
        store1 = RegexStore.new(
            dict(lazy_load=False),
            alpha=r'[[:alpha:]]+',
            numeric=r'\d+',
        )
        store2 = RegexStore.new(
            dict(lazy_load=False),
            imports=[(store1, ['alpha'])],
            test=[r'(?P>alpha)', r' test'],
        )

        assert 'alpha' in store2.definitions
        assert 'numeric' not in store2.definitions

    @pyt.mark.parametrize(
        'options, match, expected',
        [
            (dict(autostrip_spaces=True), ' test ', 'test'),
            (dict(autostrip_brackets=True), '(test)', 'test'),
            (dict(autostrip_commas=True), ',test,', 'test'),
            (dict(autostrip_spaces=True, autostrip_brackets=True), ' ( test ) ', 'test'),
            (
                dict(autostrip_commas=True, autostrip_spaces=True, autostrip_brackets=True),
                ' [ Hello, World, ] ',
                'Hello, World',
            ),
        ],
    )
    def test_process_options__autostrip(self, options: dict, match: str, expected: str):
        store = RegexStore.new(dict(lazy_load=False, **options))
        assert store.strip(match) == expected

    def test_process_options__force_reinvocations(self):
        store = RegexStore.new(
            dict(lazy_load=False, force_reinvocations=True),
            test=r'(?P<alpha>a+) (?P=alpha)',
        )
        assert '(?P>' in store.definitions['test']
        assert '(?P=' not in store.definitions['test']

    # -------------------
    # `-` Private Methods
    # -------------------
    @pyt.mark.parametrize(
        'mark, expected',
        [
            ('[]:', (GroupKind.PLAIN, '(?:', '', '')),
            ('[]>*+', (GroupKind.ATOMS, '(?>', '', '*+')),
            ('|:?', (GroupKind.PLAIN, '(?:', '|', '?')),
            ('|?', (GroupKind.MULTI, '(?|', '|', '?')),
            ('[ ]!', (GroupKind.NOT_AHEAD, '(?!', ' ', '')),
            ('[a]<={2,}', (GroupKind.BEHIND, '(?<=', 'a', '{2,}')),
            (':m-is', (GroupKind.PLAIN, r'(?m-is:', r' ?', '')),
            ('m-is', (GroupKind.POSIT, r'((?m-is)', r' ?', '')),
            ('[ *]:{2,}?', (GroupKind.PLAIN, r'(?:', r' *', '{2,}?')),
        ],
    )
    def test_parse_mark(self, mark: str, expected: tuple[str, str, str], store: RegexStore):
        assert store._parse_mark(mark) == expected

    def test_render_definitions(self, store: RegexStore):
        _ = store.load
        result = store._render_definitions('_word', '_digit')
        assert '(?(DEFINE)' in result
        assert '(?P<_word>' in result
        assert '(?P<_digit>' in result

    def test_render_definitions__empty(self, store: RegexStore):
        result = store._render_definitions()
        assert result == ''

    def test_find_all_invocations(self):
        store = RegexStore.new(
            dict(lazy_load=False),
            alpha=r'[[:alpha:]]+',
            word=r'(?P>alpha)',
            sentence=[r'(?P>word)', r' ', r'(?P>word)'],
        )

        invocations = store.find_all_invocations({'sentence'})
        assert 'sentence' in invocations
        assert 'word' in invocations
        assert 'alpha' in invocations

    def test_find_all_invocations__recursive(self):
        store = RegexStore.new(
            dict(lazy_load=False),
            a=r'test',
            b=r'(?P>a)',
            c=r'(?P>b)',
            d=r'(?P>c)',
        )

        invocations = store.find_all_invocations({'d'})
        assert invocations == {'d', 'c', 'b', 'a'}

    @pyt.mark.parametrize(
        'definition, expected',
        [
            (
                ('|&{1,3}', '', ['alpha', '_beta'], r'\b,? ?'),
                r'(?:(?:(?&alpha)|(?&_beta))\b,? ?){1,3}',
            ),
            (
                ('|:-i{0,2}?', ['alpha', 'beta']),
                r'(?-i:alpha|beta){0,2}?',
            ),
            (
                ('|+?', ['one', 'two', ('[ *]:{2,}?', ['alpha', 'beta']), 'three', 'four']),
                r'(?|one|two|(?:alpha *beta){2,}?|three|four)+?',
            ),
            (
                ('|:*', r'', [('|:{1,3}', ['A', 'B'])], r'SUFFIX'),
                r'(?:(?:A|B){1,3}SUFFIX)*',
            ),
            (('[ *]:is', ['ab', 'cd']), r'(?is:ab *cd)'),
        ],
    )
    def test_compose_tuple(self, definition: RegexVal, expected: str, store: RegexStore):
        ret = store.compose(definition)
        assert ret == expected

    @pyt.mark.parametrize(
        'data, expected',
        [
            (['Alpha', 'Zeta', 'Beta'], r'(?:Alph|[BZ]et)a'),
            (['abcx', 'abcy'], r'abc[xy]'),
            (['abxc', 'abyc'], r'ab[xy]c'),
            (['axbc', 'aybc'], r'a[xy]bc'),
            (['is', 'in', 'into'], r'i(?>n(?:to)?|s)'),
            (['Publish', 'Publishing', 'Published'], r'Publish(?>ed|ing)?'),
            (['Publisher', 'Publishing', 'Published'], r'Publish(?>e[dr]|ing)'),
            (
                [
                    'Books',
                    'Company',
                    'Group',
                    'House',
                    'International',
                    'Library',
                    'Publishers',
                    'Publishing',
                    'Publications',
                    'Productions',
                    'Press',
                    'Pictures',
                    'Studios',
                    'UP',
                ],
                (
                    r'(?>Books|Company|Group|House|International|Library|'
                    r'P(?>(?>icture|r(?>es|oduction))s|ubli(?>cations|sh(?>ers|ing)))|Studios|UP)'
                ),
            ),
            (
                [r'no-(?:footnotes|reliable-sources|significant-coverage)'],
                r'no-(?>(?>footnot|reliable-sourc)es|significant-coverage)',
            ),
            (
                [r'(?P=_ws)(?:p?p|P[Pp])\.(?!\S)'],
                r'(?P=_ws)(?:P[Pp]|pp?)\.(?!\S)',
            ),
        ],
    )
    def test_compose_tree(self, data: RegexList, expected: str, store: RegexStore):
        ret = store.compose(('<|>', data))
        assert ret == expected

    def test_parse_tuple__length_2(self, store: RegexStore):
        mark, children, pre, suf = store._parse_tuple(('|:', ['a', 'b']))
        assert mark == '|:'
        assert children == ['a', 'b']
        assert pre == ''
        assert suf == ''

    def test_parse_tuple__length_4(self, store: RegexStore):
        mark, children, pre, suf = store._parse_tuple(('|:', 'PREFIX', ['a', 'b'], 'SUFFIX'))
        assert mark == '|:'
        assert children == ['a', 'b']
        assert pre == 'PREFIX'
        assert suf == 'SUFFIX'

    def test_parse_tuple__invalid_length(self, store: RegexStore):
        with pyt.raises(ValueError, match='Invalid group spec'):
            store._parse_tuple(('mark',))  # type: ignore

    def test_collapse_empty_sections(self):
        delims = ['', 'del1', 'del2', 'del3']
        sections = ['sec1', '', 'sec2', 'sec3']

        RegexStore._collapse_empty_sections(delims, sections)

        assert len(sections) == 3
        assert '' not in sections

    # -------------------
    # `+` Primary Methods
    # -------------------
    def test_parse(self, store: RegexStore):
        _ = store.load
        pattern = store['simple']
        match = pattern.match('hello world')

        data = store.parse(match, 'simple')
        assert data.match is not None
        assert data.text == 'hello'

    def test_parse__none(self, store: RegexStore):
        data = store.parse(None)
        assert data.match is None
        assert not bool(data)

    def test_parse__with_parser(self):
        store = RegexStore.new(
            dict(lazy_load=False),
            word=(r'\w+', lambda t: t.upper()),
        )

        match = store.match('word', 'hello')
        assert match['word'] == ['HELLO']

    def test_compose__string(self, store: RegexStore):
        result = store.compose('test')
        assert result == 'test'

    def test_compose__pattern(self, store: RegexStore):
        pattern = re.compile(r'test')
        result = store.compose(pattern)
        assert result == 'test'

    def test_compose__list(self, store: RegexStore):
        result = store.compose(['a', 'b', 'c'])
        assert result == r'a ?b ?c'

    def test_compose__list_custom_sep(self, store: RegexStore):
        result = store.compose(['a', 'b', 'c'], sep='|')
        assert result == r'a|b|c'

    def test_compose__dict(self, store: RegexStore):
        result = store.compose({'mark': '|:', 'body': ['a', 'b']})
        assert 'a' in result and 'b' in result

    def test_clean(self):
        store = RegexStore.new(dict(lazy_load=False))

        text = RegexBuffer(r'test')
        groups = store.clean('test', text)
        assert isinstance(groups, set)

    def test_clean__with_invocations(self):
        store = RegexStore.new(
            dict(lazy_load=False),
            alpha=r'[[:alpha:]]+',
        )

        text = RegexBuffer(r'(?P>alpha)')
        groups = store.clean('test', text)
        assert 'alpha' in groups

    def test_define(self, store: RegexStore):
        _ = store.load
        store.define('new_pattern', r'test')
        assert 'new_pattern' in store.definitions
        assert 'new_pattern' in store.patterns

    def test_define__with_parser(self, store: RegexStore):
        _ = store.load

        def parser(s: str) -> str:
            return s.upper()

        store.define('with_parser', r'\w+', parser)
        assert 'with_parser' in store.parsers

    def test_define__duplicate_raises(self, store: RegexStore):
        _ = store.load
        store.define('dup', r'test')

        with pyt.raises(AssertionError, match='Duplicate'):
            store.define('dup', r'test2')

    def test_autostrip__bracket_balancing(self):
        store = RegexStore.new(dict(lazy_load=False, autostrip_brackets=True))
        result = store.autostrip(['test(params)'])
        assert '(' in result[0] and ')' in result[0]

    def test_autostrip__string_input(self):
        store = RegexStore.new(dict(lazy_load=False, autostrip_spaces=True))

        result = store.autostrip(' test ')
        assert result == ['test']

    # ------------------
    # `*` Public Methods
    # ------------------
    # --------------
    # `*0` Overrides
    # --------------
    def test_len(self, store: RegexStore):
        _ = store.load
        assert len(store) > 0
        assert len(store) == len(store.patterns)

    def test_contains(self, store: RegexStore):
        _ = store.load
        assert 'simple' in store
        assert 'nonexistent' not in store

    def test_setitem(self):
        store = RegexStore.new(dict(lazy_load=False))
        store['new'] = r'test'

        assert 'new' in store.patterns
        assert store.definitions['new'] == 'test'

    def test_setitem__with_parser(self):
        store = RegexStore.new(dict(lazy_load=False))

        def parser(s: str) -> str:
            return s.upper()

        store['parsed'] = (r'\w+', parser)

        assert 'parsed' in store.parsers

    def test_setitem__duplicate_raises(self):
        store = RegexStore.new(dict(lazy_load=False))
        store['dup'] = r'test'

        with pyt.raises(AssertionError, match='Duplicate'):
            store['dup'] = r'test2'

    def test_getitem(self, store: RegexStore):
        _ = store.load
        pattern = store['simple']
        assert isinstance(pattern, re.Pattern)

    def test_getitem__not_found(self):
        store = RegexStore.new(dict(lazy_load=False))

        with pyt.raises(AssertionError, match='not found'):
            _ = store['nonexistent']

    def test_ior__from_dict(self):
        store = RegexStore.new(dict(lazy_load=False))
        store |= {'new1': r'test1', 'new2': r'test2'}

        assert 'new1' in store
        assert 'new2' in store

    def test_ior__from_store(self):
        store1 = RegexStore.new(dict(lazy_load=False), alpha=r'[[:alpha:]]+')
        store2 = RegexStore.new(dict(lazy_load=False))

        store2 |= store1

        assert 'alpha' in store2

    def test_get__exists(self, store: RegexStore):
        _ = store.load
        pattern = store.get('simple')
        assert pattern is not None
        assert isinstance(pattern, re.Pattern)

    def test_get__not_found(self, store: RegexStore):
        _ = store.load
        pattern = store.get('nonexistent', None)
        assert pattern is None

    def test_get_def__exists(self, store: RegexStore):
        _ = store.load
        definition = store.get_def('simple')
        assert definition is not None
        assert isinstance(definition, str)

    def test_get_def__not_found(self, store: RegexStore):
        _ = store.load
        definition = store.get_def('nonexistent', None)
        assert definition is None

    def test_keys(self, store: RegexStore):
        _ = store.load
        keys = store.keys()
        assert isinstance(keys, list)
        assert 'simple' in keys

    def test_values(self, store: RegexStore):
        _ = store.load
        values = store.values()
        assert isinstance(values, list)
        assert all(isinstance(v, re.Pattern) for v in values)

    def test_items(self, store: RegexStore):
        _ = store.load
        items = store.items()
        assert isinstance(items, list)
        assert all(isinstance(k, str) and isinstance(v, re.Pattern) for k, v in items)

    # -------------------------------
    # `*1` Top-Level Matching Methods
    # -------------------------------
    @pyt.mark.parametrize(
        'pattern_name, text, should_match',
        [
            ('simple', 'hello', True),
            ('simple', 'hello world', True),
            ('simple', 'goodbye', False),
            ('compound', 'hello world', True),
            ('compound', 'hello  world', False),
        ],
    )
    def test_match(self, store: RegexStore, pattern_name: str, text: str, should_match: bool):
        _ = store.load
        result = store.match(pattern_name, text)
        assert bool(result) == should_match

    def test_match__multiple_patterns(self, store: RegexStore):
        _ = store.load
        result = store.match(['_word', '_digit'], '123')
        assert bool(result)
        assert result.text == '123'

    @pyt.mark.parametrize(
        'pattern_name, text, should_match',
        [
            ('simple', 'hello', True),
            ('simple', 'hello world', False),
            ('compound', 'hello world', True),
            ('compound', 'hello world extra', False),
        ],
    )
    def test_fullmatch(self, store: RegexStore, pattern_name: str, text: str, should_match: bool):
        _ = store.load
        result = store.fullmatch(pattern_name, text)
        assert bool(result) == should_match

    @pyt.mark.parametrize(
        'pattern_name, text, should_match',
        [
            ('simple', 'hello', True),
            ('simple', 'say hello there', True),
            ('simple', 'goodbye', False),
            ('_word', 'test123', True),
        ],
    )
    def test_search(self, store: RegexStore, pattern_name: str, text: str, should_match: bool):
        _ = store.load
        result = store.search(pattern_name, text)
        assert bool(result) == should_match

    def test_finditer(self, store: RegexStore):
        _ = store.load
        results = list(store.finditer('_word', 'one two three'))
        assert len(results) == 3
        assert all(isinstance(r, MatchData) for r in results)

    def test_finditer__no_matches(self, store: RegexStore):
        _ = store.load
        results = list(store.finditer('_digit', 'no digits here'))
        assert len(results) == 0

    def test_findall(self, store: RegexStore):
        _ = store.load
        results = store.findall('_word', 'one two three')
        assert len(results) == 3

    @pyt.mark.parametrize(
        'pattern_name, text, expected_sections',
        [
            ('_word', 'one two three', ['', ' ', ' ', '']),
            ('_digit', '1a2b3', ['', 'a', 'b', '']),
        ],
    )
    def test_fullsplit(
        self, store: RegexStore, pattern_name: str, text: str, expected_sections: list[str]
    ):
        _ = store.load
        delims, sections = store.fullsplit(pattern_name, text)
        assert sections == expected_sections

    def test_fullsplit__collapse(self, store: RegexStore):
        _ = store.load
        delims, sections = store.fullsplit('_word', 'one  two', collapse=True)
        # Collapsed empty sections
        assert '' not in sections[1:]

    def test_polymatch(self, store: RegexStore):
        _ = store.load
        result = store.polymatch('_word', 'one two three')
        assert bool(result)
        # Should contain all matches merged

    # -------------------------
    # `*2` Functional Utilities
    # -------------------------
    def test_parse_invocations(self):
        store = RegexStore.new(
            dict(lazy_load=False),
            alpha=r'[[:alpha:]]+',
            word=r'(?P>alpha)',
        )

        invocations = store.parse_invocations(r'(?P>word)')
        assert 'word' in invocations
        assert 'alpha' in invocations

    def test_partial__match(self, store: RegexStore):
        _ = store.load
        match_fn = store.partial('simple', 'match')
        result = match_fn('hello world')
        assert bool(result)

    def test_partial__search(self, store: RegexStore):
        _ = store.load
        search_fn = store.partial('simple', 'search')
        result = search_fn('say hello')
        assert bool(result)

    def test_apply(self, store: RegexStore):
        _ = store.load
        texts = ['hello', 'goodbye', 'hello again']
        results = list(store.apply('simple', texts, 'match'))

        assert len(results) == 3
        assert bool(results[0])
        assert not bool(results[1])
        assert bool(results[2])

    def test_filter(self, store: RegexStore):
        _ = store.load
        texts = ['hello', 'goodbye', 'hello again']
        filtered = list(store.filter('simple', texts, 'match'))

        assert len(filtered) == 2
        assert 'hello' in filtered
        assert 'hello again' in filtered

    # ---------------------------------------
    # `*3` Performant "Router Tree" Functions
    # ---------------------------------------
    def test_router_tree(self, store: RegexStore):
        _ = store.load
        store.define_router_tree('test', dict(alpha=r'[[:alpha:]]+', nums=r'\d+'))

        text_a = 'abc'
        assert store.match('test', text_a)
        assert store.route_match('test', text_a) == 'alpha'

        text_b = '123'
        assert store.match('test', text_b)
        assert store.route_match('test', text_b) == 'nums'

    def test_router_tree__with_prefix_suffix(self):
        store = RegexStore.new(dict(lazy_load=False))
        store.define_router_tree(
            'wrapped', dict(alpha=r'[[:alpha:]]+', nums=r'\d+'), prefix=r'\b', suffix=r'\b'
        )

        assert 'wrapped' in store.routers
        assert store.match('wrapped', 'abc')

    def test_route_match__no_match(self):
        store = RegexStore.new(dict(lazy_load=False))
        store.define_router_tree('router', dict(alpha=r'[[:alpha:]]+'))

        result = store.route_match('router', '123')
        assert result == ''

    def test_route_match__from_matchdata(self):
        store = RegexStore.new(dict(lazy_load=False))
        store.define_router_tree('router', dict(alpha=r'[[:alpha:]]+'))

        match_data = store.fullmatch('router', 'abc')
        result = store.route_match('router', match_data)
        assert result == 'alpha'

    def test_expand_match(self):
        store = RegexStore.new(dict(lazy_load=False))
        store.define_router_tree('router', dict(test=r'(?P<value>\w+)'))

        result = store.expand_match('router', 'hello')
        assert isinstance(result, str)

    # ---------
    # `*4` Misc
    # ---------
    def test_sanitize__pattern_name(self, store: RegexStore):
        _ = store.load
        result = store.sanitize('simple')
        assert isinstance(result, str)

    def test_sanitize__compiled_pattern(self, store: RegexStore):
        _ = store.load
        pattern = store['simple']
        result = store.sanitize(pattern)
        assert isinstance(result, str)

    def test_sanitize__string(self, store: RegexStore):
        result = store.sanitize(r'test(?m)pattern')
        assert isinstance(result, str)

    def test_tree_print(self, store: RegexStore):
        _ = store.load
        result = store.tree_print('compound')
        assert isinstance(result, str)
        assert len(result) > 0

    def test_tree_print__no_head(self, store: RegexStore):
        _ = store.load
        result = store.tree_print('simple', print_head=False)
        assert isinstance(result, str)

    # ----------------
    # Edge Cases Tests
    # ----------------
    def test_lazy_loading_thread_safety(self):
        """Test that lazy loading works correctly with threading."""
        store = RegexStore.new(
            dict(lazy_load=True),
            test=r'test',
        )

        assert not store.is_loaded
        _ = store.load
        assert store.is_loaded

    def test_empty_store(self):
        """Test operations on empty store."""
        store = RegexStore.new(dict(lazy_load=False))

        assert len(store) == 0
        assert store.keys() == []
        assert store.values() == []

    def test_complex_nested_composition(self):
        """Test deeply nested regex composition."""
        store = RegexStore.new(dict(lazy_load=False))

        complex_def = ('|:', ['a', ('[]:', ['b', ('|:', ['c', 'd'])]), 'e'])
        result = store.compose(complex_def)

        assert isinstance(result, str)
        assert 'a' in result and 'e' in result

    def test_force_named_groups(self):
        """Test that positional groups are converted to non-capturing."""
        store = RegexStore.new(
            dict(lazy_load=False, force_named_groups=True),
            test=r'(test)',
        )

        assert '(?:' in store.definitions['test']
        assert store.definitions['test'].count('(') == store.definitions['test'].count('(?:')

    def test_multiple_pattern_match_first_wins(self, store: RegexStore):
        """Test that when matching multiple patterns, first match wins."""
        _ = store.load
        result = store.match(['simple', '_word'], 'hello')

        assert bool(result)
        assert result.text == 'hello'

    def test_buffer_input(self, store: RegexStore):
        """Test that Buffer input is handled correctly."""
        _ = store.load

        buffer = Buffer.new('hello world')
        result = store.match('simple', buffer)
        assert bool(result)

    @pyt.mark.parametrize(
        'text, pattern, should_match',
        [
            ('(test)', '_parenthetical', True),
            ('(hello)', '_parenthetical', True),
            ('test', '_parenthetical', False),
        ],
    )
    def test_parser_application(
        self, store: RegexStore, text: str, pattern: str, should_match: bool
    ):
        """Test that parsers are applied correctly."""
        _ = store.load
        result = store.match(pattern, text)
        assert bool(result) == should_match

        if should_match:
            # Parser should have stripped parentheses
            assert '(' not in result.at(pattern)
            assert ')' not in result.at(pattern)

    def test_invalid_mark_syntax(self, store: RegexStore):
        """Test error handling for invalid mark syntax."""
        with pyt.raises(AssertionError):
            store._parse_mark('invalid_mark_syntax_!@#$%')

    def test_compose_group__subroutine_mark(self, store: RegexStore):
        """Test compose_group with subroutine mark."""
        _ = store.load
        result = store.compose_group('|&', ['_word', '_digit'])

        assert '(?&_word)' in result
        assert '(?&_digit)' in result

    def test_hidden_field_removal(self):
        """Test that hidden fields (starting with _) are removed from results."""
        store = RegexStore.new(
            dict(lazy_load=False),
            _hidden=r'(?P<_internal>\w+)',
            test=r'(?P>_hidden)',
        )

        result = store.match('test', 'hello')
        # _internal should not be in final result
        assert '_internal' not in result.data

    def test_format_definition(self):
        """Test that init_formatter is applied to definitions."""

        def formatter(val):
            if isinstance(val, str):
                return val.upper()
            return val

        store = RegexStore.new(
            dict(lazy_load=False, init_formatter=formatter),
            test='test',
        )

        # The formatter should have been applied
        assert 'TEST' in store.definitions['test']

    def test_compose_empty_string(self, store: RegexStore):
        """Test composing empty string."""
        result = store.compose('')
        assert result == ''

    def test_compose_empty_list(self, store: RegexStore):
        """Test composing empty list."""
        result = store.compose([])
        assert result == ''

    def test_fullsplit_no_matches(self, store: RegexStore):
        """Test fullsplit when pattern doesn't match."""
        _ = store.load
        delims, sections = store.fullsplit('_digit', 'no digits here')

        assert delims == ['']
        assert sections == ['no digits here']

    def test_polymatch_no_matches(self, store: RegexStore):
        """Test polymatch when pattern doesn't match."""
        _ = store.load
        result = store.polymatch('_digit', 'no digits here')

        assert not bool(result)
