############
### HEAD ###
############
### STANDARD

### EXTERNAL
import pytest as pyt

### INTERNAL
from my.regex.meta import GroupKind
from my.regex import RegexStore, RegexList, RegexVal

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
            dict(
                separator=r' ?',
                autostrip_brackets=True,
            ),
            _parenthetical=(r'\(\w+\)', lambda s: s.strip('() ')),
        )

    # -------------------
    # `0` Initial Methods
    # -------------------
    # TODO: more tests
    def test_new(self, store: RegexStore) -> None:
        assert len(store.patterns) == len(store.definitions)

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

    def test_render_definitions(self):
        pass

    def test_find_all_invocations(self):
        pass

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

    # -------------------
    # `+` Primary Methods
    # -------------------
    def test_parse(self):
        pass

    def test_compose(self):
        pass

    def test_clean(self):
        pass

    def test_define(self):
        pass

    def test_autostrip(self):
        pass

    # ------------------
    # `x` Public Methods
    # ------------------
    # --------------
    # `x0` Overrides
    # --------------
    def test_setitem(self):
        pass

    def test_getitem(self):
        pass

    def test_ior(self):
        pass

    def test_pop(self):
        pass

    def test_get(self):
        pass

    def test_get_def(self):
        pass

    def test_keys(self):
        pass

    def test_values(self):
        pass

    def test_items(self):
        pass

    # -------------------------------
    # `x1` Top-Level Matching Methods
    # -------------------------------
    def test_match(self):
        pass

    def test_fullmatch(self):
        pass

    def test_finditer(self):
        pass

    def test_fullsplit(self):
        pass

    def test_polymatch(self):
        pass

    # -------------------------
    # `x2` Functional Utilities
    # -------------------------
    def test_parse_invocations(self):
        pass

    def test_partial(self):
        pass

    def test_apply(self):
        pass

    def test_filter(self):
        pass

    # ---------------------------------------
    # `x3` Performant "Router Tree" Functions
    # ---------------------------------------
    def test_router_tree(self, store: RegexStore):
        store.define_router_tree('test', dict(alpha=r'[[:alpha:]]+', nums=r'\d+'))

        text_a = 'abc'
        assert store.match('test', text_a)
        assert store.route_match('test', text_a) == 'alpha'

        text_b = '123'
        assert store.match('test', text_b)
        assert store.route_match('test', text_b) == 'nums'
