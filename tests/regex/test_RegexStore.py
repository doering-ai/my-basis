############
### HEAD ###
############
### STANDARD
import inspect
from typing import Any
import random

### EXTERNAL
import regex as re
import pytest as pyt
import more_itertools as mi

### INTERNAL
from my import Buffer, ut, typist
from my.infra import INFRA_PATHS
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

    @staticmethod
    @pyt.fixture(scope='class')
    def importas_data() -> set[str]:
        file = INFRA_PATHS.data / 'importas.yaml'
        data = set(typist.from_yaml(file.read_text())['IMPORT_AS_PREFIXES'])
        assert len(data) > 100
        return data

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
        assert store._is_loaded
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

    def test_new__with_imports_lazy_load_no_deadlock(self):
        # basis-12 item 1 regression: `initial_load()` recurses into an imported store's own
        # `.load` while still inside its own `.load`. Both stores default to `lazy_load=True`
        # here (unlike `test_new__with_imports`, which sidesteps the lock by loading eagerly),
        # so `store2.match(...)` is what actually drives both `.load` calls through the lock.
        # A regression to a single shared (non-reentrant) lock hangs forever; the suite's global
        # 15s pytest-timeout turns that hang into a test failure rather than a stuck run.
        store1 = RegexStore.new(alpha=r'[[:alpha:]]+', numeric=r'\d+')
        store2 = RegexStore.new(
            imports=[(store1, ['alpha'])],
            test=[r'(?P>alpha)', r' test'],
        )

        data = store2.match('test', 'hello test')
        assert data.get('alpha') == ['hello']

    def test_new__init_formatter(self):
        def formatter(val: Any):
            return val.upper() if isinstance(val, str) else val

        store = RegexStore.new(
            dict(lazy_load=False, init_formatter=formatter),
            test='test',
        )

        # The formatter should have been applied
        assert 'TEST' in store.definitions['test']

    def test_new__empty(self):
        store = RegexStore.new(dict(lazy_load=False))

        assert len(store) == 0
        assert store.keys() == []
        assert store.values() == []

    @pyt.mark.parametrize(
        'options, match, expected',
        [
            (dict(autostrip_spaces=True), ' test ', 'test'),
            (dict(autostrip_brackets=True), '(test)', 'test'),
            (dict(autostrip_commas=True), ',test,', 'test'),
            (
                dict(autostrip_spaces=True, autostrip_brackets=True),
                ' ( test ) ',
                'test',
            ),
            (
                dict(
                    autostrip_commas=True,
                    autostrip_spaces=True,
                    autostrip_brackets=True,
                ),
                ' [ Hello, World, ] ',
                'Hello, World',
            ),
        ],
    )
    def test_process_options__autostrip(self, options: dict, match: str, expected: str):
        store = RegexStore.new(dict(lazy_load=False, **options))
        assert store._strip[0](match) == expected

    def test_process_options__force_reinvocations(self):
        store = RegexStore.new(
            dict(lazy_load=False, force_reinvocations=True),
            test=r'(?P<alpha>a+) (?P=alpha)',
        )
        assert '(?P>' in store.definitions['test']
        assert '(?P=' not in store.definitions['test']

    def test_process_options__force_named_groups(self):
        store = RegexStore.new(
            dict(lazy_load=False, force_named_groups=True),
            test=r'(test)',
        )

        assert '(?:' in store.definitions['test']
        assert store.definitions['test'].count('(') == store.definitions['test'].count('(?:')

    # -------------------
    # `-` Private Methods
    # -------------------
    @pyt.mark.parametrize(
        'mark, expected',
        [
            ('[]:', (GroupKind.PLAIN, '(?:', '', '')),
            ('[]>*+', (GroupKind.ATOMS, '(?>', '', '*+')),
            ('|:?', (GroupKind.PLAIN, '(?:', '|', '?')),
            ('|?', (GroupKind.RESET, '(?|', '|', '?')),
            ('[ ]!', (GroupKind.NOT_AHEAD, '(?!', ' ', '')),
            ('[a]<={2,}', (GroupKind.BEHIND, '(?<=', 'a', '{2,}')),
            (':m-is', (GroupKind.PLAIN, r'(?m-is:', r' ?', '')),
            ('m-is', (GroupKind.POSIT, r'((?m-is)', r' ?', '')),
            ('[ *]:{2,}?', (GroupKind.PLAIN, r'(?:', r' *', '{2,}?')),
        ],
    )
    def test_parse_mark(self, mark: str, expected: tuple[str, str, str], store: RegexStore):
        assert store._parse_mark(mark) == expected

    def test_parse_mark__invalid(self, store: RegexStore):
        with pyt.raises(AssertionError):
            store._parse_mark('invalid_mark_syntax_!@#$%')

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
                (
                    '|+?',
                    ['one', 'two', ('[ *]:{2,}?', ['alpha', 'beta']), 'three', 'four'],
                ),
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
            (['Alpha', 'Zeta', 'Beta'], r'(?>Alph|[BZ]et)a'),
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
                [r'(?P>_ws)(?:p?p|P[Pp])\.(?!\S)'],
                r'(?P>_ws)(?>P[Pp]|pp?)\.(?!\S)',
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
        assert store.compose('test') == 'test'
        assert store.compose('') == ''

    def test_compose__pattern(self, store: RegexStore):
        pattern = re.compile(r'test')
        assert store.compose(pattern) == 'test'

    def test_compose__list(self, store: RegexStore):
        assert store.compose(['a', 'b', 'c']) == r'a ?b ?c'
        assert store.compose([]) == ''

    def test_compose__list_custom_sep(self, store: RegexStore):
        result = store.compose(['a', 'b', 'c'], sep='|')
        assert result == r'a|b|c'

    def test_compose__dict(self, store: RegexStore):
        result = store.compose({'mark': '|:', 'body': ['a', 'b']})
        assert 'a' in result and 'b' in result

    def test_compose_group(self):
        store = RegexStore.new(dict(lazy_load=False))

        complex_def = ('|:', ['a', ('[]:', ['b', ('|:', ['c', 'd'])]), 'e'])
        result = store.compose(complex_def)

        assert isinstance(result, str)
        assert 'a' in result and 'e' in result

    def test_compose_group__subroutine_mark(self, store: RegexStore):
        _ = store.load
        result = store.compose_group('|&', ['_word', '_digit'])

        assert '(?&_word)' in result
        assert '(?&_digit)' in result

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
        store |= dict(new1=r'test1', new2=r'test2')

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
        self,
        store: RegexStore,
        pattern_name: str,
        text: str,
        expected_sections: list[str],
    ):
        _ = store.load
        delims, sections = store.fullsplit(pattern_name, text)
        assert sections == expected_sections
        assert len(delims) == len(sections)

    def test_fullsplit__collapse(self, store: RegexStore):
        _ = store.load
        delims, sections = store.fullsplit('_word', 'one  two', collapse=True)
        assert '' not in sections[1:]
        assert len(delims) == len(sections)

    def test_fullsplit__fail(self, store: RegexStore):
        _ = store.load
        delims, sections = store.fullsplit('_digit', 'no digits here')
        assert delims == ['']
        assert sections == ['no digits here']

    def test_polymatch(self, store: RegexStore):
        _ = store.load
        result = store.polymatch('_word', 'one two three')
        assert bool(result)
        assert result['_word'] == ['one', 'two', 'three']

    def test_polymatch__fail(self, store: RegexStore):
        _ = store.load
        result = store.polymatch('_digit', 'no digits here')
        assert not result

    def test_automatch__race_conditions(self, store: RegexStore):
        _ = store.load
        result = store.match(['simple', '_word'], 'hello')

        assert bool(result)
        assert result.text == 'hello'

    def test_automatch__buffer_input(self, store: RegexStore):
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
    def test_automatch__parsers(
        self, store: RegexStore, text: str, pattern: str, should_match: bool
    ):
        _ = store.load
        result = store.match(pattern, text)
        assert bool(result) == should_match
        if should_match:
            assert ut.has_none(result.at(pattern), '(', ')')

    def test_automatch__hidden_field_removal(self):
        store = RegexStore.new(
            dict(lazy_load=False),
            _hidden=r'(?P<_internal>\w+)',
            test=r'(?P>_hidden)',
        )

        result = store.match('test', 'hello')
        assert ut.has_none(result.data, '_internal', '_hidden')

    @pyt.mark.parametrize(
        'func, alias, text',
        [
            ('fullmatch', 'full', '(paren) suffix'),
            ('polymatch', 'poly', '(paren0) suffix (paren1)'),
            ('fullsplit', 'split', 'prefix (paren0) suffix'),
        ],
    )
    def test_automatch__aliases(self, store: RegexStore, func: str, alias: str, text: str):
        _ = store.load
        fn0 = getattr(store, func)
        fn1 = getattr(store, alias)
        assert fn0 and fn1
        sig0 = inspect.signature(fn0)
        sig1 = inspect.signature(fn1)
        assert sig0.parameters == sig1.parameters

        m0 = fn0('_parenthetical', text)
        m1 = fn1('_parenthetical', text)
        assert m0 == m1

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
            'wrapped',
            dict(alpha=r'[[:alpha:]]+', nums=r'\d+'),
            prefix=r'\b',
            suffix=r'\b',
        )

        assert 'wrapped' in store.routers
        assert store.match('wrapped', 'abc')

    @pyt.mark.parametrize(
        'lazy_load, expect_queued',
        [
            (True, True),
            (False, False),
        ],
        ids=['lazy_store', 'already_loaded_store'],
    )
    def test_routers_property__triggers_load(self, lazy_load: bool, expect_queued: bool):
        """`.routers` is a load-triggering property, not a plain field access.

        A lazy store's `define_router_tree` call is itself queued behind the lazy-load queue
        (see `define_router_tree`'s own `if not self._is_loaded: ...; return` guard), so the
        backing `_routers` dict stays empty until something forces a load -- bare access to a
        plain field would silently see the empty dict. An already-loaded (or eagerly-loaded)
        store has nothing queued, so `.routers` must return the same data whether or not it's
        accessed via the property.
        """
        store = RegexStore.new(dict(lazy_load=lazy_load))
        store.define_router_tree('handler', dict(alpha=r'[[:alpha:]]+', nums=r'\d+'))

        # The raw private dict reflects whether the definition is still queued.
        assert (store._routers == {}) is expect_queued

        # The public property must trigger any pending load either way.
        assert 'handler' in store.routers
        assert store.routers['handler'] == ['alpha', 'nums']
        assert store._is_loaded

    def test_routers_property__already_loaded_store_unaffected(self):
        """An eagerly-loaded store's `.routers` behaves identically before/after the property
        access -- the load-triggering property must not mutate or re-derive already-populated
        router data.
        """
        store = RegexStore.new(dict(lazy_load=False))
        store.define_router_tree('router', dict(alpha=r'[[:alpha:]]+'))

        before = dict(store._routers)
        first_access = store.routers
        second_access = store.routers

        assert before == first_access == second_access == {'router': ['alpha']}

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

    # ----------------------------
    # `*4` Expression Construction
    # ----------------------------
    @pyt.mark.parametrize(
        'target, expected',
        [
            (
                'web.archive.org/web/20081205101019/http://www.balticseawind.org',
                'balticseawind.org',
            ),
            (
                'https://www.web.archive.org/web/20081205101019/http://www.balticseawind.org',
                'balticseawind.org',
            ),
            ('https://www.gbif.org/species/113225725', 'gbif.org/species/113225725'),
            ('web.archive.org/web/20081205101019/http://site.com/', 'site.com'),
            ('archive.org/web/12345678901234/https://example.org/', 'example.org'),
            (
                'http://web.archive.org/web/20200101000000/http://example.com/a/b',
                'example.com/a/b',
            ),
            ('http://example.com/path', 'example.com/path'),
            ('https://example.com', 'example.com'),
            ('www.example.com', 'example.com'),
            ('  site.com.  ', 'site.com'),
            ("site.com,'", 'site.com'),
            ('site.com."', 'site.com'),
            ('site.com/#weird_path/#section1"', 'site.com/#weird_path'),
        ],
    )
    def test_format_url(self, target: str, expected: str):
        assert cls.format_url(target) == expected

    @pyt.mark.parametrize(
        'target, expected',
        [
            ('', r'(?P>_ws)(?P>_we)'),
            (['one', 'two'], [r'(?P>_ws)', r'one', r'two', r'(?P>_we)']),
            (
                ('[]:', ['part1', 'part2']),
                ('[]:', r'(?P>_ws)', ['part1', 'part2'], r'(?P>_we)'),
            ),
            (
                ('[]:', r'pre', ['part1', 'part2'], r'suf'),
                ('[]:', r'(?P>_ws)pre', ['part1', 'part2'], r'suf(?P>_we)'),
            ),
        ],
    )
    def test_atom(self, target, expected):
        assert cls.atom(target) == expected

    # --------------------------
    # `*5` Development Utilities
    # --------------------------
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

    def test_pretty_print(self, store: RegexStore, snapshot: str):
        _ = store.load
        result = store.pretty_print('compound')
        assert isinstance(result, str)
        assert len(result) > 0
        assert result == snapshot

    def test_pretty_print__no_head(self, store: RegexStore):
        _ = store.load
        result = store.pretty_print('simple', print_head=False)
        assert isinstance(result, str)
        assert len(result) > 0
        # Just ensure it works -- no need for another snapshot

    # -----------------------------
    # `^0` ImportAs Example Dataset
    # -----------------------------
    @pyt.fixture(scope='class')
    def importas_store(self, importas_data: set[str]) -> RegexStore:
        data = importas_data
        return RegexStore.new(
            options=dict(lazy_load=False),
            importas=('<|>', r'\b', list(sorted(data)), r'\b'),
        )

    def test_tree__importas_example(
        self,
        importas_data: set[str],
        importas_store: RegexStore,
        pytestconfig,
        snapshot,
    ):
        data, store = importas_data, importas_store
        # I. Create "additive" negative examples by concatenating three random letters to each entry
        _a, _z = ord('a'), ord('z')
        _rand = lambda: chr(random.randint(_a, _z))
        negative_examples: set[str] = set(
            mi.flatten(
                [prefix + c, c + prefix] for prefix in data for _ in range(10) if (c := _rand())
            )
        )
        negative_examples -= data
        print(f'Loaded {len(negative_examples)} negative examples total.')

        # IV. Test the router tree against both positive and negative examples
        _fn = store.partial('importas', 'full')
        false_negatives, true_positives = map(list, mi.partition(_fn, data))
        true_negatives, false_positives = map(list, mi.partition(_fn, negative_examples))

        verbosity: int = pytestconfig.getoption('verbose')
        if verbosity > 0 and (false_negatives or false_positives):
            true_positives.sort()
            true_negatives.sort()
            false_positives.sort()
            false_negatives.sort()
            out = []
            out.extend(
                [
                    f'TRUE POSITIVE RATE: {len(true_positives) / len(data):.2%}',
                    f'TRUE NEGATIVE RATE: {len(true_negatives) / len(negative_examples):.2%}'
                    f'\t' + ', '.join(sorted(false_positives)),
                ]
            )
            if false_negatives:
                out.extend(
                    [
                        '\nFALSE NEGATIVES: ',
                        '\t[' + ', '.join(sorted(false_negatives)) + ']',
                    ]
                )
            if false_positives:
                out.extend(
                    [
                        '\nFALSE POSITIVES: ',
                        '\t[' + ', '.join(sorted(false_positives)) + ']',
                    ]
                )

            if verbosity > 2:
                out.extend(['', '', 'REGEX:', '', store.pretty_print('importas')])
            print('\n'.join(out))

        assert len(false_negatives) == 0 and len(false_positives) == 0
        assert store.pretty_print('importas') == snapshot
