############
### HEAD ###
############
### STANDARD
import itertools as it

### EXTERNAL
import pytest as pyt
import regex as re

### INTERNAL
from my import RegexStore, Regex, Tree


############
### DATA ###
############
WHITESPACE = [
    *range(0x09, 0x0E),
    *range(0x1C, 0x21),
    0x85,
    0xA0,
    0x1680,
    *range(0x2000, 0x200B),
    0x2028,
    0x2029,
    0x202F,
    0x205F,
    0x3000,
]

WITNESSES = [
    # Wildcards, zero-width assertions and existing atomic commitments are opaque.
    (['cat', 'ca.'], ['cab', 'cat', 'ca.', 'dog']),
    (['(?=a|b)c'], ['ac', 'bc', 'c']),
    (['(?<=a|b)c'], ['ac', 'bc', 'c']),
    (['(?>a|ab)b'], ['ab', 'abb']),
    # Variable/lazy repetition must retain both search priority and fullmatch backtracking.
    ([r'script\/?\w*?', 'plain'], ['script/Arabic', 'script', 'scriptA', 'plain']),
    # Capture branches must keep their positions, histories and replacement observations.
    (['(?P<z>ab)', '(?P<a>a)'], ['ab', 'a', 'aba']),
    (['(ab)', '(a)'], ['ab', 'a', 'aba']),
    (['(a)', '(a)'], ['a', 'aa']),
    (['(?:(?P<x>a)|(?P<x>b))+', 'ab'], ['ab', 'aba', 'a']),
    # Prefix and empty alternatives retain caller order.
    (['a', 'ab'], ['a', 'ab', 'abb']),
    (['ab', 'a'], ['a', 'ab', 'abb']),
    (['a', 'b', 'ab'], ['a', 'ab', 'abb', 'bb']),
    (['', 'ab'], ['', 'ab', 'abb']),
    (['a', '', 'ab'], ['', 'ab', 'abb']),
    (['a?a', 'a?b'], ['ab', 'a', 'b']),
    (['a?', 'b?'], ['', 'b', 'a']),
    (['a?a?a?a?a?a', 'a?a?a?a?a?b'], ['aaaaab', 'aaaaa', 'b']),
    # Set punctuation differs from regex punctuation and must be escaped on relocation.
    ([r'ca\.', 'cat'], ['cat', 'ca.', 'cab']),
    ([r'[+*?]', r'\-', r'\]'], ['+', '*', '?', '-', ']', 'a']),
    (['[a-z]', '[^a]'], ['a', 'm', 'z', '!', '^']),
    (['[]]', 'a'], [']', 'a', '[']),
    # Real Wikiparse shapes: optional words, assertions, captures, variable routers.
    (
        ['no-(?:footnotes|reliable-sources|significant-coverage)'],
        ['no-footnotes', 'no-reliable-sources', 'no-significant-coverage'],
    ),
    (['st', 'nd', 'n?th', 'rd', 'e', '°'], ['nth', 'th', 'nd', 'e']),
    (['article', 'number', 'no(?=:)', 'online'], ['no:', 'number', 'online']),
    (['publisher\\d*', 'journal', 'series'], ['publisher2', 'publisher', 'journal']),
    (
        ['Universi(ty|idad|t[aä]t|[eé])', '[EÉeé]cole', 'Schule'],
        ['University', 'Universität', 'École', 'Schule'],
    ),
]


def observation(match):
    if match is None:
        return None
    return match.span(), match.groups(), match.capturesdict(), match.allspans()


def assert_equivalent(raw, optimized, texts, flags=0):
    reference = re.compile(raw, flags)
    candidate = re.compile(optimized, flags)
    for text in texts:
        for method in ['search', 'match', 'fullmatch']:
            assert observation(getattr(candidate, method)(text)) == observation(
                getattr(reference, method)(text)
            ), (raw, optimized, flags, method, text)
        assert [observation(m) for m in candidate.finditer(text)] == [
            observation(m) for m in reference.finditer(text)
        ], (raw, optimized, text)
        for replacement in ['#', r'<\g<0>>']:
            assert candidate.sub(replacement, text) == reference.sub(replacement, text), (
                raw,
                optimized,
                replacement,
                text,
            )
        assert candidate.sub(lambda m: repr(m.capturesdict()), text) == reference.sub(
            lambda m: repr(m.capturesdict()), text
        ), (raw, optimized, text)


############
### BODY ###
############
class TestOptimizerSemantics:
    @pyt.fixture
    def store(self):
        return RegexStore.new(dict(lazy_load=False, separator='', force_named_groups=False))

    @pyt.mark.parametrize('branches, texts', WITNESSES)
    def test_compose_tree(self, store, branches, texts):
        raw = '(?:' + '|'.join(branches) + ')'
        optimized = store.compose_tree(branches)
        assert_equivalent(raw, optimized, texts)
        assert_equivalent(raw, store.compose(('<|>', branches)), texts)
        for suffix in ['', 'b', 'a?', '(?=b)', '(?!b)']:
            assert_equivalent(raw + suffix, optimized + suffix, texts)
            assert_equivalent(raw + suffix, store.compose(('<|>', '', branches, suffix)), texts)
        tree = Tree.new(*branches) if '[]]' not in branches else None
        if tree is not None:
            assert_equivalent(raw, str(tree.expand().condense().render()), texts)

    def test_compose_tree__priority_permutations(self, store):
        # Exhaustive bounded comparison includes empty branches, overlapping sets and optional
        # atoms. Context outside the optimized subtree must still be able to backtrack.
        words = ['', 'a', 'b', 'ab', 'ba', 'a?', 'a[ab]', '(?:a|ab)b']
        texts = [''.join(chars) for n in range(5) for chars in it.product('ab', repeat=n)]
        for branches in it.permutations(words, 3):
            raw = '(?:' + '|'.join(branches) + ')'
            optimized = store.compose_tree(list(branches))
            for suffix in ['', 'a', 'b']:
                assert_equivalent(raw + suffix, optimized + suffix, texts)

    @pyt.mark.parametrize(
        'flags',
        [
            re.V0,
            re.V0 | re.I,
            re.V1,
            re.V1 | re.I,
            re.F | re.I,
            re.R,
            re.X,
            re.BESTMATCH,
            re.ENHANCEMATCH,
        ],
    )
    @pyt.mark.parametrize(
        'branches, texts',
        [
            (['ss', 'st'], ['ß', 'ss', 'st', 'SS', 'ST', 'ﬆ']),
            (['ab', 'cab'], ['ab', 'cab', 'cabab']),
            (['Straße', 'strasse'], ['Straße', 'STRASSE', 'strasse']),
            (['a b', 'ab'], ['a b', 'ab']),
        ],
    )
    def test_compose_tree__known_flags(self, store, flags, branches, texts):
        raw = '(?:' + '|'.join(branches) + ')'
        assert_equivalent(raw, store.compose_tree(branches, flags=flags), texts, flags)
        store.define('flagged', ('<|>', branches), flags=flags)
        assert_equivalent('(?P<flagged>' + raw + ')', store['flagged'].pattern, texts, flags)
        # Exercise flag forwarding into a deeper optimized tuple and its external continuation.
        nested = ['c', ('<|>', branches)]
        store.define('nested', nested, flags=flags)
        assert_equivalent('(?P<nested>c' + raw + ')', store['nested'].pattern, texts, flags)

    @pyt.mark.parametrize(
        'definition',
        [
            ('<|>fi', ['ss', 'st']),
            ['(?V1)(?i)', ('<|>', ['ss', 'st'])],
            ('[]:', '(?V1)(?i)', [('<|>', ['ss', 'st'])], ''),
            ['(?V1)', ('<|>i', ['ss', 'st'])],
            {'mark': '[]:', 'pre': '(?fi)', 'body': [('<|>', ['ss', 'st'])]},
        ],
    )
    def test_compose_tree__inline_flag_context(self, store, definition):
        result = store.compose(definition)
        assert re.fullmatch(result, 'ß') is not None, result

    def test_compose_tree__default_version(self, store, monkeypatch):
        monkeypatch.setattr(re, 'DEFAULT_VERSION', re.V0)
        simple = store.compose(('<|>i', ['ss', 'st']))
        assert_equivalent('(?i:ss|st)', simple, ['ß', 'ss', 'st', 'SS'])
        monkeypatch.setattr(re, 'DEFAULT_VERSION', re.V1)
        full_fold = store.compose(('<|>i', ['ss', 'st']))
        assert_equivalent('(?i:ss|st)', full_fold, ['ß', 'ss', 'st', 'SS'])

    @pyt.mark.parametrize('prefix', ['(?fi)', '(?V1)(?i)'])
    def test_compose_tree__direct_nested_flag_context(self, store, prefix):
        data = [prefix, ('<|>', ['ss', 'st'])]
        assert_equivalent(
            '(?:' + prefix + '|(?:ss|st))', store.compose_tree(data), ['ß', 'ss', 'st', 'SS']
        )

    @pyt.mark.parametrize(
        'branches',
        [
            ['a', 'b', 'ab', 'ba', 'abc'],
            ['ab', 'b', 'a', 'ba', 'abc'],
            ['a', '[ab]c', 'ab', 'b'],
            ['a', '', 'b', 'ab'],
            ['i', 'b', 'Ix', 'İx', 'ix'],
            ['a?', 'b', 'ab', 'a'],
        ],
    )
    @pyt.mark.parametrize('flags', [re.V0, re.V0 | re.I, re.V1])
    def test_compose_tree__independent_regrouping(self, store, branches, flags):
        raw = '(?:' + '|'.join(branches) + ')'
        optimized = store.compose_tree(branches, flags=flags)
        texts = ['ab', 'ba', 'abc', 'ac', 'a', 'b', 'İx', 'ix', 'Ix', '']
        for suffix in ['', 'b', 'c', 'a?']:
            assert_equivalent(raw + suffix, optimized + suffix, texts, flags)

    def test_compose_tree__shuffled_fixed_width(self, store):
        # This lexical form is also measured by the campaign scaling harness.
        words = [f'commonprefix{index:04x}' for index in range(256)]
        words = words[::2] + list(reversed(words[1::2]))
        optimized = store.compose_tree(words)
        assert len(optimized) < 100
        assert_equivalent(
            '(?:' + '|'.join(words) + ')',
            optimized,
            [*words, 'commonprefixffff', 'commonprefix000x'],
        )

    def test_compose_tree__formatter_flag_context(self):
        store = RegexStore.new(
            dict(
                lazy_load=False,
                separator='',
                formatter=lambda value: value.replace('FLAG', '(?fi)'),
            )
        )
        result = store.compose(['FLAG', ('<|>', ['ss', 'st'])])
        assert_equivalent('(?fi)(?:ss|st)', result, ['ß', 'ss', 'st', 'SS'])

    def test_compose_tree__fuzzy_context(self, store):
        definition = [('<|>', ['cat', 'car', 'dog']), '{e<=1}']
        raw = '(?:cat|car|dog){e<=1}'
        assert_equivalent(raw, store.compose(definition), ['cat', 'cab', 'dog', 'cag', 'cot'])

    def test_expand_atom__scoped_flags(self):
        tree = Tree.new('(?i-s:ab)?')
        assert_equivalent(
            '(?i-s:ab)?', str(tree.expand_atom(tree.branches[0].one)), ['ab', 'AB', 'aB', '']
        )

    def test_condense__optional_prefix(self):
        for branches in [['a?a', 'a?b'], ['a?', 'b?']]:
            raw = '(?:' + '|'.join(branches) + ')'
            assert_equivalent(raw, str(Tree.new(*branches).condense()), ['ab', 'b', 'aa', 'a'])

    @pyt.mark.parametrize('codepoint', WHITESPACE, ids=lambda cp: f'U+{cp:04X}')
    @pyt.mark.parametrize('flags', [re.V0, re.V0 | re.I, re.V1 | re.I, re.X])
    def test_compose_tree__escaped_whitespace(self, store, codepoint, flags):
        text = 'abc' + chr(codepoint) + 'def'
        leaf = re.escape(text)
        # The AST must retain every source character before eligibility or factoring.
        assert str(Regex(leaf)) == leaf
        assert Tree.new(leaf).is_transformable
        assert store.compose_tree([leaf], flags=re.V0) == leaf
        texts = [text, 'abcdef', 'abcxdef', text + ' ' + text]
        for branches in [[leaf], [leaf, 'abcdef', 'abcxdef']]:
            raw = '(?:' + '|'.join(branches) + ')'
            for optimized in [
                store.compose_tree(branches, flags=flags),
                store.compose(('<|>', branches), flags=flags),
                store.compose(dict(mark='<|>', body=branches), flags=flags),
                store.compose(('|:', branches), flags=flags),
            ]:
                assert_equivalent(raw, optimized, texts, flags)
        pre, suf = r'(?<!\w)', r'(?!\w)'
        store.define('whitespace', [pre, ('<|>', [leaf]), suf], flags=flags)
        assert_equivalent(
            '(?P<whitespace>' + pre + leaf + suf + ')', store['whitespace'].pattern, texts, flags
        )
        assert store['whitespace'].fullmatch(text) is not None

    @pyt.mark.parametrize(
        'text',
        [
            'abc\ndef',
            'abc\n\ndef',
            'abc\r\ndef',
            'a complete *good*\n\nobject and to identify himself',
            'dynamic categories-container-con-\n\ntained, empty-full',
            'Crane, Stephen, *Red Badge of Courage,*\n*the*, 101',
        ],
    )
    def test_compose_tree__multiline_learned_batch(self, store, text):
        # Mend's learned path: longest-first escaped literals inside external word boundaries.
        words = sorted([text, text.replace('\n', ''), 'unrelated'], key=lambda s: (-len(s), s))
        branches = [re.escape(word) for word in words]
        pre, suf = r'(?<!\w)', r'(?!\w)'
        raw = pre + '(?:' + '|'.join(branches) + ')' + suf
        definition = [pre, ('<|>', branches), suf]
        texts = [*words, text + ' ' + text, 'x' + text, text + 'x']
        assert_equivalent(raw, store.compose(definition), texts)
        assert_equivalent(raw, store.compose(('<|>', pre, branches, suf)), texts)
        assert_equivalent(raw, store.compose(('|:', pre, branches, suf)), texts)
        store.define('learned', definition)
        assert_equivalent('(?P<learned>' + raw + ')', store['learned'].pattern, texts)
        assert store['learned'].fullmatch(text) is not None

    @pyt.mark.parametrize('leaf', [r'abc\ndef', r'abc\x0adef', r'abc\u000adef'])
    def test_compose_tree__symbolic_whitespace(self, store, leaf):
        assert_equivalent(leaf, store.compose_tree([leaf]), ['abc\ndef', 'abcdef'])

    @pyt.mark.parametrize('flags', [re.V0 | re.X, re.V1 | re.X])
    def test_compose_tree__verbose_formatting(self, store, flags):
        branches = ['a b', 'a# comment\nb', 'a# comment\\\nb', 'acb']
        optimized = store.compose_tree(branches, flags=flags)
        assert_equivalent('(?:' + '|'.join(branches) + ')', optimized, ['ab', 'a b', 'acb'], flags)
        assert re.fullmatch(optimized, 'ab', flags) is not None
        assert re.fullmatch(optimized, 'a b', flags) is None

    @pyt.mark.parametrize(
        'leaf, texts',
        [
            (r'\N{LINE FEED}', ['\n', '']),
            (r'(?i:abc)', ['abc', 'ABC', 'ab']),
            ('(?x:a # comment\n b)', ['ab', 'a b']),
            (r'(?P<word>abc)', ['abc', 'ab']),
            (r'(?:a(?:b|c)[x])', ['abx', 'acx', 'abcx']),
        ],
    )
    def test_compose_tree__opaque_syntax(self, store, leaf, texts):
        assert str(Regex(leaf)) == leaf
        assert_equivalent(leaf, store.compose_tree([leaf]), texts)

    def test_compose_tree__incomplete_escape(self, store):
        # Unknown trailing bytes remain opaque rather than becoming a different valid literal.
        leaf = 'abc\\'
        assert str(Regex(leaf)) == leaf
        assert not Tree.new(leaf).is_transformable
        optimized = store.compose_tree([leaf])
        assert optimized == '(?:' + leaf + ')'
        with pyt.raises(re.error, match=r'missing \)'):
            re.compile(optimized)

    def test_compose_tree__capture_replacement(self, store):
        branches = ['(?P<z>ab)', '(?P<a>a)']
        optimized = re.compile(store.compose(('<|>', branches)))
        raw = re.compile('(?:' + '|'.join(branches) + ')')
        assert optimized.sub(r'\g<z>:xyz:\g<a>', 'ab a') == raw.sub(r'\g<z>:xyz:\g<a>', 'ab a')
