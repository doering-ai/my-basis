############
### HEAD ###
############
### STANDARD
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, ClassVar, cast
import asyncio
import json
import pickle

### EXTERNAL
import pytest as pyt
import regex as re
import sublime as sb
from my import Utils as BasisUtils

### INTERNAL
from myBasis.infra import utils as utils_module
from myBasis.infra.utils import ut, Utils, PATHS

_Edit = cast('Any', sb.Edit)
_Window = cast('Any', sb.Window)


############
### DATA ###
############
def _run(coro: Any) -> Any:
    """Run a coroutine synchronously."""
    return asyncio.run(coro)


#: Generic helpers now inherited from my-basis instead of maintained as a parallel copy.
CANONICAL_METHODS = (
    '_clean_nonwords',
    '_multiprint_data',
    'clear_cached_properties',
    'debug_fence',
    'indexof',
    'multi_rgx',
    'multiprint',
    'posix',
    'replace',
    'roman_to_decimal',
)


############
### BODY ###
############
class TestCanonicalBasis:
    @pyt.mark.parametrize('name', CANONICAL_METHODS)
    def test_method_ownership(self, name: str):
        """Generic helpers have one implementation owner in my-basis."""
        assert name not in Utils.__dict__
        assert hasattr(BasisUtils, name)

    @pyt.mark.parametrize(
        'name, args, kwargs',
        [
            ('indexof', (['a', 'bb'], 'bb'), {}),
            ('multi_rgx', ('cat', 'dog'), {}),
            ('posix', (0,), {}),
            ('replace', ('a1b2', (r'\d', '#')), {}),
            ('roman_to_decimal', ('MCMXCIV',), {}),
        ],
    )
    def test_behavior(self, name: str, args: tuple[Any, ...], kwargs: dict[str, Any]):
        """The adapter exposes the canonical result for representative contracts."""
        assert getattr(Utils, name)(*args, **kwargs) == getattr(BasisUtils, name)(*args, **kwargs)


class TestCleanShellArgs:
    """Tests for ``Utils._clean_shell_args``."""

    def test_flattens_and_splits(self):
        result = list(ut._clean_shell_args(('git status', ['--short', '-b']), {}))
        assert result == ['git', 'status', '--short', '-b']

    def test_kwargs_become_flags(self):
        result = list(ut._clean_shell_args(('cmd',), {'v': True, 'depth': '2'}))
        assert result == ['cmd', '-v', '--depth', '2']

    def test_kwargs_iterable_values_repeat_flag(self):
        result = list(ut._clean_shell_args(('cmd',), {'opt': ['a', 'b']}))
        assert result == ['cmd', '--opt', 'a', '--opt', 'b']


class TestEx:
    """Tests for ``Utils.ex`` (sync subprocess wrapper)."""

    def test_basic_output(self):
        assert ut.ex('echo hello') == 'hello'

    def test_failure_returns_none(self):
        assert ut.ex('false') is None

    def test_cwd_is_applied(self, tmp_path: Path):
        """`cwd=` must change the subprocess working directory, not become a CLI flag."""
        assert ut.ex('pwd', cwd=tmp_path) == str(tmp_path.resolve())

    def test_cwd_not_leaked_into_argv(self, tmp_path: Path):
        """If cwd leaked through kwargs it would surface as a literal `--cwd` argument."""
        out = ut.ex('echo marker', cwd=tmp_path)
        assert out == 'marker'
        assert '--cwd' not in (out or '')


class TestExa:
    """Tests for ``Utils.exa`` (async subprocess wrapper)."""

    def test_basic_output(self):
        assert _run(ut.exa('echo hello')) == 'hello'

    def test_failure_returns_none(self):
        assert _run(ut.exa('false')) is None

    def test_cwd_is_applied(self, tmp_path: Path):
        """`cwd=` must change the subprocess working directory, not become a CLI flag."""
        assert _run(ut.exa('pwd', cwd=tmp_path)) == str(tmp_path.resolve())

    def test_cwd_not_leaked_into_argv(self, tmp_path: Path):
        out = _run(ut.exa('echo marker', cwd=tmp_path))
        assert out == 'marker'
        assert '--cwd' not in (out or '')

    def test_nonexistent_cwd_returns_none(self, tmp_path: Path):
        """An invalid cwd fails the subprocess launch and is swallowed to None."""
        assert _run(ut.exa('echo hello', cwd=tmp_path / 'missing')) is None


class TestExecuteAliases:
    """`execute`/`execute_async` forward to `ex`/`exa` including cwd."""

    def test_execute(self, tmp_path: Path):
        assert ut.execute('pwd', cwd=tmp_path) == str(tmp_path.resolve())

    def test_execute_async(self, tmp_path: Path):
        assert _run(ut.execute_async('pwd', cwd=tmp_path)) == str(tmp_path.resolve())


class TestPosix:
    """Tests for ``Utils.posix`` / ``Utils.posix_since``."""

    def test_none_is_utc_now(self):
        before = datetime.now(timezone.utc)
        result = ut.posix()
        assert result.tzinfo == timezone.utc
        assert abs((result - before).total_seconds()) < 5

    def test_timestamp_converted(self):
        assert ut.posix(0) == datetime(1970, 1, 1, tzinfo=timezone.utc)

    def test_datetime_normalized_to_utc(self):
        est = timezone(timedelta(hours=-5))
        local = datetime(2026, 1, 1, 7, 0, tzinfo=est)
        result = ut.posix(local)
        assert result.tzinfo == timezone.utc
        assert result == local

    @pyt.mark.parametrize('falsy', [None, 0, 0.0])
    def test_since_falsy_is_zero(self, falsy: Any):
        assert ut.posix_since(falsy) == timedelta(0)

    def test_since_past_is_positive(self):
        assert ut.posix_since(1) > timedelta(days=365)


class TestMilliseconds:
    """Tests for ``Utils.milliseconds`` numeric coercion."""

    @pyt.mark.parametrize(
        'val, expected',
        [
            (0.25, 250),  # small values are treated as seconds
            (5, 5000),
            (9.999, 9999),
            (100, 100),  # values >= 10 are already milliseconds
            (timedelta(seconds=2), 2000),
            (timedelta(milliseconds=250), 250),
        ],
    )
    def test_conversions(self, val: Any, expected: int):
        assert ut.milliseconds(val) == expected

    def test_datetime_is_epoch_ms(self):
        dt = datetime(1970, 1, 2, tzinfo=timezone.utc)
        assert ut.milliseconds(dt) == 24 * 3600 * 1000

    def test_none_is_now(self):
        assert ut.milliseconds() >= 1_500_000_000_000


class TestRgxDict:
    """Tests for ``Utils.rgx_dict`` compilation and reference expansion."""

    def test_compiles_strings(self):
        result = ut.rgx_dict(word=r'\w+')
        assert result['word'].fullmatch('abc')

    def test_precompiled_pattern_passthrough(self):
        pattern = re.compile(r'\d+')
        result = ut.rgx_dict(num=pattern)
        assert result['num'] is pattern

    def test_iterable_joined_with_sep(self):
        result = ut.rgx_dict(sep='|', either=['aa', 'bb'])
        assert result['either'].fullmatch('aa')
        assert result['either'].fullmatch('bb')

    def test_reference_expansion(self):
        result = ut.rgx_dict(digit=r'\d', pair=r'{{.digit}}{{.digit}}')
        assert result['pair'].fullmatch('42')
        assert not result['pair'].fullmatch('4')

    def test_reference_to_unknown_group_raises(self):
        with pyt.raises(AssertionError, match='non-existent group'):
            ut.rgx_dict(pair=r'{{.missing}}')

    def test_invalid_pattern_raises_value_error(self, capsys: pyt.CaptureFixture):
        with pyt.raises(ValueError, match='Invalid Regular Expression "bad"'):
            ut.rgx_dict(bad=r'(')
        # Regression: no stray debug output (a leftover `print(len(out))` used to fire here).
        assert capsys.readouterr().out == ''

    def test_multiline_invalid_pattern_annotates_row(self):
        with pyt.raises(ValueError, match=r'ERROR'):
            ut.rgx_dict(bad='(?x)\nabc\n(')


class TestSafeCompile:
    """``safe_compile`` must honor its contract: report the error, return a fallback pattern."""

    def test_valid_pattern(self):
        pattern = ut.safe_compile('ok', r'\w+', re.compile)
        assert pattern.fullmatch('abc')

    def test_invalid_pattern_returns_fallback(self, capsys: pyt.CaptureFixture):
        pattern = ut.safe_compile('broken', r'(', re.compile)
        assert pattern is not None
        assert pattern.pattern == r'ERROR'
        out = capsys.readouterr().out
        assert 'RGX COMPILATION ERROR' in out
        assert 'broken' in out


class TestRgxBuilders:
    """Tests for ``rgx_definitions`` / ``define_rgx`` / ``rgx_array`` / ``multi_rgx``."""

    def test_definitions_empty(self):
        assert ut.rgx_definitions({}) == ''
        assert ut.define_rgx() == ''

    def test_definitions_compile_and_backreference(self):
        defs = ut.define_rgx(digit=r'\d')
        pattern = re.compile(defs + r'(?&digit)+')
        assert pattern.fullmatch('123')

    def test_rgx_definitions_matches_define_rgx(self):
        groups = {'a': r'x', 'b': r'y'}
        assert ut.rgx_definitions(groups) == ut.define_rgx(**groups)

    def test_rgx_array_compiles_keys(self):
        precompiled = re.compile(r'b')
        result = ut.rgx_array((r'a', 1), (precompiled, 2))
        assert result[0][0].pattern == 'a' and result[0][1] == 1
        assert result[1][0] is precompiled and result[1][1] == 2

    @pyt.mark.parametrize(
        'kwargs, matches, rejects',
        [
            (dict(), 'ab', 'ac'),
            (dict(pre='x'), 'xab', 'ab'),
            (dict(suf='z'), 'abz', 'ab'),
            (dict(branching=True), 'ab', 'ac'),
        ],
    )
    def test_multi_rgx(self, kwargs: dict, matches: str, rejects: str):
        expr = ut.multi_rgx('ab', 'cd', **kwargs)
        pattern = re.compile(expr)
        assert pattern.fullmatch(matches)
        assert not pattern.fullmatch(rejects)

    def test_multi_rgx_joins_lists(self):
        expr = ut.multi_rgx(['a', 'b'], sep='-')
        assert re.compile(expr).fullmatch('a-b')


class TestCleanRgxMatch:
    """Tests for ``Utils.clean_rgx_match``."""

    def test_none_yields_empty_defaults(self):
        groups, captures = ut.clean_rgx_match(None)
        assert groups['anything'] == ''
        assert captures['anything'] == []

    def test_repeated_captures_collected(self):
        match = re.compile(r'(?:(?P<word>\w+) ?)+').fullmatch('foo bar baz')
        groups, captures = ut.clean_rgx_match(match)
        assert captures['word'] == ['foo', 'bar', 'baz']
        assert groups['word'] == 'baz'  # groups keep the *last* capture

    def test_empty_captures_filtered(self):
        match = re.compile(r'(?P<a>\w+)(?P<b>\s*)').fullmatch('foo')
        groups, captures = ut.clean_rgx_match(match)
        assert captures['b'] == []
        assert groups['b'] == ''


class TestRgxFullsplit:
    """Tests for ``Utils.rgx_fullsplit`` and empty-section collapsing."""

    def test_no_match_returns_single_section(self):
        delims, sections = ut.rgx_fullsplit(re.compile(r'\n+'), 'abc')
        assert (delims, sections) == ([''], ['abc'])

    def test_splits_with_leading_empty_delim(self):
        delims, sections = ut.rgx_fullsplit(re.compile(r'\n+'), 'a\nb\n\nc')
        assert delims == ['', '\n', '\n\n']
        assert sections == ['a', 'b', 'c']

    def test_zip_invariant(self):
        delims, sections = ut.rgx_fullsplit(re.compile(r','), ',a,,b,')
        assert len(delims) == len(sections)
        assert ''.join(d + s for d, s in zip(delims, sections)) == ',a,,b,'

    def test_collapse_merges_empty_sections(self):
        delims, sections = ut.rgx_fullsplit(re.compile(r'\n+'), '\na\n', collapse=True)
        assert '' not in sections
        assert ''.join(d + s for d, s in zip(delims, sections)) == '\na\n'


class TestRomanNumerals:
    """Tests for decimal <-> Roman conversions."""

    CASES: ClassVar[list] = [
        (1, 'I'),
        (4, 'IV'),
        (9, 'IX'),
        (14, 'XIV'),
        (40, 'XL'),
        (90, 'XC'),
        (400, 'CD'),
        (900, 'CM'),
        (1994, 'MCMXCIV'),
        (2026, 'MMXXVI'),
        (3999, 'MMMCMXCIX'),
    ]

    @pyt.mark.parametrize('decimal, roman', CASES)
    def test_decimal_to_roman(self, decimal: int, roman: str):
        assert ut.decimal_to_roman(decimal) == roman

    @pyt.mark.parametrize('decimal, roman', CASES)
    def test_roman_to_decimal(self, decimal: int, roman: str):
        assert ut.roman_to_decimal(roman) == decimal

    @pyt.mark.parametrize('decimal', range(1, 200, 7))
    def test_roundtrip(self, decimal: int):
        assert ut.roman_to_decimal(ut.decimal_to_roman(decimal)) == decimal

    def test_lowercase_accepted(self):
        assert ut.roman_to_decimal('xiv') == 14

    @pyt.mark.parametrize('invalid', ['ABC', 'MMMM12', 'I I'])
    def test_invalid_returns_zero(self, invalid: str):
        assert ut.roman_to_decimal(invalid) == 0

    def test_too_large_asserts(self):
        with pyt.raises(AssertionError, match='too large'):
            ut.decimal_to_roman(4000)


class TestDebounced:
    """Deterministic tests for ``Utils.debounced`` using an injected clock and timer."""

    @pyt.fixture
    def timers(self, monkeypatch: pyt.MonkeyPatch) -> 'list[tuple[Any, int]]':
        """Capture `sublime.set_timeout` callbacks instead of running them synchronously."""
        pending: 'list[tuple[Any, int]]' = []
        monkeypatch.setattr(
            utils_module.sb, 'set_timeout', lambda cb, delay=0: pending.append((cb, delay))
        )
        return pending

    @pyt.fixture
    def clock(self, monkeypatch: pyt.MonkeyPatch) -> 'dict[str, int]':
        """Replace the `now` half of ``Utils.milliseconds`` with a controllable value."""
        state = {'now': 100_000}
        original = Utils.milliseconds.__func__

        def fake_milliseconds(cls: Any, val: Any = None) -> int:
            if val is None:
                return state['now']
            return original(cls, val)

        monkeypatch.setattr(Utils, 'milliseconds', classmethod(fake_milliseconds))
        return state

    def test_calls_are_coalesced(self, timers: list, clock: dict):
        calls: 'list[tuple]' = []
        wrapped = ut.debounced(lambda *a, **kw: calls.append((a, kw)))

        wrapped(1, key='a')
        assert len(timers) == 1 and timers[0][1] == ut.DEFAULT_DEBOUNCE
        assert not calls, 'the function must not run before the delay elapses'

        clock['now'] += 100
        wrapped(2, key='b')
        assert len(timers) == 1, 'a repeat call must only reset the timer, not add one'

        # First check fires at the originally scheduled time: the deadline has moved on.
        clock['now'] = 100_000 + ut.DEFAULT_DEBOUNCE
        cb, _ = timers.pop(0)
        cb()
        assert not calls
        assert len(timers) == 1, 'the check must reschedule itself for the remaining time'
        assert timers[0][1] == 100

        # Second check fires after the pushed-back deadline: the *first* call args win.
        clock['now'] += 100
        cb, _ = timers.pop(0)
        cb()
        assert calls == [((1,), {'key': 'a'})]

    def test_decorator_with_delta(self, timers: list, clock: dict):
        calls: 'list[int]' = []

        @ut.debounced(delta=50)
        def target(val: int) -> int:
            calls.append(val)
            return val

        target(7)
        assert timers[0][1] == 50
        clock['now'] += 50
        assert target(8) is None, 'the debounced wrapper must discard return values'
        clock['now'] += 50
        timers.pop(0)[0]()
        assert calls == [7]

    def test_fires_again_after_settling(self, timers: list, clock: dict):
        calls: 'list[int]' = []
        wrapped = ut.debounced(calls.append)

        for expected in (1, 2):
            wrapped(expected)
            clock['now'] += ut.DEFAULT_DEBOUNCE
            timers.pop(0)[0]()
            assert calls[-1] == expected
        assert calls == [1, 2]


class TestSequenceHelpers:
    """Tests for ``sorted_insert`` / ``indexof`` / ``locate`` / ``pop_index``."""

    @pyt.mark.parametrize(
        'array, item, expected_index',
        [([1, 3, 5], 4, 2), ([1, 3, 5], 0, 0), ([1, 3, 5], 9, 3), ([], 1, 0)],
    )
    def test_sorted_insert(self, array: list, item: int, expected_index: int):
        index = ut.sorted_insert(array, item)
        assert index == expected_index
        assert array == sorted(array)
        assert item in array

    def test_sorted_insert_with_key(self):
        array = [(1, 'a'), (3, 'c')]
        ut.sorted_insert(array, (2, 'b'), key=lambda t: t[0])
        assert array == [(1, 'a'), (2, 'b'), (3, 'c')]

    @pyt.mark.parametrize(
        'preds, expected',
        [
            (('b',), 1),  # plain values match by equality
            ((lambda x: x == 'c',), 2),  # functions are predicates
            (('missing',), -1),
            (('missing', 'a'), 0),  # any of several predicates may hit
        ],
    )
    def test_indexof(self, preds: tuple, expected: int):
        assert ut.indexof(['a', 'b', 'c'], *preds) == expected

    def test_locate_returns_index_and_item(self):
        assert ut.locate([10, 20, 30], lambda x: x > 15) == (1, 20)

    def test_locate_missing_asserts(self):
        with pyt.raises(AssertionError, match='No item found'):
            ut.locate([1], lambda x: x > 5)

    def test_pop_index_returns_new_list(self):
        original = [1, 2, 3]
        assert ut.pop_index(original, 1) == [1, 3]
        assert original == [1, 2, 3], 'the input sequence must not be mutated'

    def test_pop_index_out_of_bounds(self):
        with pyt.raises(AssertionError, match='out of bounds'):
            ut.pop_index([1], 4)


class TestGroupby:
    """Tests for ``Utils.groupby`` key styles and the ``drop`` flag."""

    DATA: ClassVar[list] = [(1, 'a'), (0, 'b'), (2, 'c'), (0, 'd'), (1, 'e')]

    def test_by_index(self):
        result = cast('dict[int, list[tuple[int, str]]]', dict(ut.groupby(self.DATA, 0)))
        assert result[1] == [(1, 'a'), (1, 'e')]
        assert result[0] == [(0, 'b'), (0, 'd')]

    def test_by_attribute_name(self):
        class Item:
            def __init__(self, tag: str) -> None:
                self.tag = tag

        items = [Item('x'), Item('y'), Item('x')]
        result = dict(ut.groupby(items, 'tag'))
        assert len(result['x']) == 2 and len(result['y']) == 1

    def test_by_callable(self):
        result = dict(ut.groupby([1, 2, 3, 4], lambda x: x % 2))
        assert result[0] == [2, 4] and result[1] == [1, 3]

    def test_drop_removes_falsy_keys(self):
        """Regression: ``drop=True`` used to be silently ignored."""
        result = dict(ut.groupby(self.DATA, 0, drop=True))
        assert 0 not in result
        assert set(result) == {1, 2}


class TestClearCachedProperties:
    """Tests for ``Utils.clear_cached_properties``."""

    class _Cached:
        CACHED_PROPERTIES = ('alpha', 'beta')

    def _make(self) -> '_Cached':
        inst = self._Cached()
        inst.__dict__.update(alpha=1, beta=2, gamma=3)
        return inst

    def test_explicit_properties(self):
        inst = self._make()
        ut.clear_cached_properties(inst, 'alpha')
        assert 'alpha' not in inst.__dict__ and 'beta' in inst.__dict__

    def test_defaults_to_cached_properties_attr(self):
        inst = self._make()
        ut.clear_cached_properties(inst)
        assert 'alpha' not in inst.__dict__ and 'beta' not in inst.__dict__
        assert inst.__dict__['gamma'] == 3

    def test_missing_property_ignored(self):
        inst = self._make()
        ut.clear_cached_properties(inst, 'nonexistent')  # must not raise


class TestPlural:
    """Tests for ``Utils.plural``."""

    @pyt.mark.parametrize(
        'count, singular, plural, expected',
        [
            (1, 'file', None, 'file'),
            (0, 'file', None, 'files'),
            (2, 'file', None, 'files'),
            (2, 'index', 'indices', 'indices'),
            (1.5, 'hour', None, 'hours'),
        ],
    )
    def test_plural(self, count: Any, singular: str, plural: 'str | None', expected: str):
        assert ut.plural(count, singular, plural) == expected


class TestWriteTuple:
    """Tests for the ``Utils.Write`` batching container."""

    @pyt.mark.parametrize(
        'pos, expected',
        [
            (3, (3, 3)),  # int -> empty region
            ((2, 7), (2, 7)),  # tuple passes through sorted
            ((7, 2), (2, 7)),  # reversed tuple is sorted
        ],
    )
    def test_region_coercion(self, pos: Any, expected: tuple):
        assert ut.Write(pos, 'x').points == expected

    def test_reversed_region_normalized(self):
        write = ut.Write(sb.Region(9, 4), 'x')
        assert (write.start, write.end) == (4, 9)

    def test_bad_tuple_asserts(self):
        with pyt.raises(AssertionError, match='two integers'):
            _ = ut.Write((1, 2, 3), 'x').region

    def test_text_and_delta(self):
        write = ut.Write((0, 4), 'ab')
        assert write.text == 'ab'
        assert write.delta == 2  # region shrinks by two characters

    def test_ordering(self):
        assert ut.Write(1, 'a') < ut.Write((5, 9), 'b')
        assert not (ut.Write(1, 'a') < 'not-a-write')


class TestBatchWrite:
    """Tests for the ``Utils.batch_write`` context manager against the mock view."""

    def _fill(self, view: sb.View, text: str) -> sb.Edit:
        edit = _Edit(view)
        view.insert(edit, 0, text)
        return edit

    def test_writes_applied_in_reverse_order(self, make_view: sb.View):
        edit = self._fill(make_view, 'aaa bbb ccc')
        with ut.batch_write(make_view, edit) as write:
            write((0, 3), 'XX')  # earlier region queued first,
            write((8, 11), 'YY')  # but must be applied *after* the later one
        assert make_view.substr(sb.Region(0, make_view.size())) == 'XX bbb YY'

    def test_insert_at_point(self, make_view: sb.View):
        edit = self._fill(make_view, 'ab')
        with ut.batch_write(make_view, edit) as write:
            write(1, 'X')
        assert make_view.substr(sb.Region(0, make_view.size())) == 'aXb'

    def test_noop_write_skipped(self, make_view: sb.View, capsys: pyt.CaptureFixture):
        edit = self._fill(make_view, 'same')
        count = make_view.change_count()
        with ut.batch_write(make_view, edit) as write:
            write((0, 4), 'same')
        assert make_view.change_count() == count, 'a no-op write must not touch the view'
        assert 'Skipping no-op write' in capsys.readouterr().out

    def test_overlapping_writes_assert(self, make_view: sb.View):
        edit = self._fill(make_view, 'abcdefgh')
        batch = ut.batch_write(make_view, edit)
        write = batch.__enter__()
        write((0, 5), 'X')
        write((3, 8), 'Y')
        with pyt.raises(AssertionError, match='overlapping'):
            batch.__exit__(None, None, None)

    def test_debug_prints_summary(self, make_view: sb.View, capsys: pyt.CaptureFixture):
        edit = self._fill(make_view, 'abc')
        with ut.batch_write(make_view, edit, debug=True) as write:
            write((0, 3), 'z')
        assert 'Replacing' in capsys.readouterr().out


class TestReplaceAndRecase:
    """Tests for ``replace`` / ``_clean_nonwords`` / ``TextCase`` / ``recase``."""

    def test_replace_sequential(self):
        result = ut.replace('a-b-c', (r'-', '_'), (r'a', 'X'))
        assert result == 'X_b_c'

    def test_replace_with_callable(self):
        result = ut.replace('a1b2', (re.compile(r'\d'), lambda m: str(int(m[0]) * 2)))
        assert result == 'a2b4'

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
    def test_all_cases_from_words(self, case: str, expected: str):
        assert ut.recase('Text Case', to=case, clean=False) == expected

    @pyt.mark.parametrize(
        'text, from_case, expected',
        [
            ('foo-bar-baz', 'kebab', 'fooBarBaz'),
            ('foo_bar_baz', 'snake', 'fooBarBaz'),
            ('FooBarBaz', 'pascal', 'fooBarBaz'),
            ('fooBarBaz', 'camel', 'fooBarBaz'),
        ],
    )
    def test_camel_from_other_cases(self, text: str, from_case: str, expected: str):
        assert ut.recase(text, to='camel', _from=from_case, clean=False) == expected

    @pyt.mark.parametrize('empty', ['', '   ', '\n\t'])
    def test_empty_input(self, empty: str):
        assert ut.recase(empty) == ''

    def test_recase_cleans_nonwords(self):
        assert ut.recase('Hello World!') == 'hello_world'

    def test_pascal_roundtrip(self):
        assert ut.to_pascal('foo_bar') == 'FooBar'
        assert ut.from_pascal('FooBar') == 'foo_bar'
        assert ut.from_pascal(ut.to_pascal('foo_bar')) == 'foo_bar'

    def test_textcase_enum_accepts_instances(self):
        assert ut.recase('one two', to=ut.TextCase.KEBAB) == 'one-two'


class TestNormalizePath:
    """Tests for ``Utils.normalize_path`` -- the foundation of `Venv` path handling."""

    def test_absolute_passthrough(self, tmp_path: Path):
        assert ut.normalize_path(tmp_path) == tmp_path

    def test_tilde_expanded(self):
        assert ut.normalize_path('~') == Path.home()

    @pyt.mark.parametrize('empty', ['.', ''])
    def test_empty_paths_survive(self, empty: str):
        """Regression: leading-$ detection used to IndexError on empty paths."""
        assert ut.normalize_path(empty) == Path(empty)

    def test_env_var_expanded(self, tmp_path: Path, monkeypatch: pyt.MonkeyPatch):
        monkeypatch.setenv('MYBASIS_TEST_ROOT', str(tmp_path))
        assert ut.normalize_path('$MYBASIS_TEST_ROOT/sub') == tmp_path / 'sub'

    def test_nested_env_vars_resolved(self, tmp_path: Path, monkeypatch: pyt.MonkeyPatch):
        monkeypatch.setenv('MYBASIS_OUTER', '$MYBASIS_INNER')
        monkeypatch.setenv('MYBASIS_INNER', str(tmp_path))
        assert ut.normalize_path('$MYBASIS_OUTER/x') == tmp_path / 'x'

    def test_missing_env_var_asserts(self, monkeypatch: pyt.MonkeyPatch):
        monkeypatch.delenv('MYBASIS_MISSING', raising=False)
        with pyt.raises(AssertionError, match='not found'):
            ut.normalize_path('$MYBASIS_MISSING/x')

    def test_env_var_loop_detected(self, monkeypatch: pyt.MonkeyPatch):
        monkeypatch.setenv('MYBASIS_LOOP', '$MYBASIS_LOOP')
        with pyt.raises(ValueError, match='infinite loop'):
            ut.normalize_path('$MYBASIS_LOOP/x')

    @pyt.mark.parametrize(
        'prefix, registry_attr',
        [
            ('Packages', 'pkgs'),
            ('Installed Packages', 'inst'),
            ('Package Storage', 'data'),
            ('Cache', 'cache'),
        ],
    )
    def test_mainline_resources(self, prefix: str, registry_attr: str):
        result = ut.normalize_path(f'{prefix}/Foo/bar.py')
        assert result == getattr(PATHS, registry_attr) / 'Foo' / 'bar.py'

    def test_marker_found_mid_path(self):
        result = ut.normalize_path('junk/Packages/Foo/bar.py')
        assert result == PATHS.pkgs / 'Foo' / 'bar.py'

    def test_bare_package_name(self, monkeypatch: pyt.MonkeyPatch):
        monkeypatch.setattr(Utils, 'package_list', lambda: {'FakePkg'})
        result = ut.normalize_path('FakePkg/sub.py')
        assert result == PATHS.pkgs / 'FakePkg' / 'sub.py'

    def test_window_folder_relative(self, monkeypatch: pyt.MonkeyPatch, tmp_path: Path):
        monkeypatch.setattr(Utils, 'package_list', lambda: set())
        window = _Window()
        window.set_project_data({'folders': [{'path': str(tmp_path / 'proj')}]})
        result = ut.normalize_path('proj/file.txt', window)
        assert result == tmp_path / 'proj' / 'file.txt'

    def test_unresolvable_relative_passthrough(self, monkeypatch: pyt.MonkeyPatch):
        monkeypatch.setattr(Utils, 'package_list', lambda: set())
        assert ut.normalize_path('no/such/prefix', _Window()) == Path('no/such/prefix')


class TestPathPredicates:
    """Tests for ``is_valid_path`` / ``is_relative_to`` / ``relativize``."""

    @pyt.mark.parametrize('invalid', [None, ''])
    def test_falsy_paths_invalid(self, invalid: Any):
        assert not ut.is_valid_path(invalid)

    def test_nonexistent_invalid(self, tmp_path: Path):
        assert not ut.is_valid_path(tmp_path / 'missing')

    def test_existing_dir_valid(self, tmp_path: Path):
        assert ut.is_valid_path(tmp_path)

    def test_existing_file_valid(self, tmp_path: Path):
        target = tmp_path / 'file.txt'
        target.touch()
        assert ut.is_valid_path(target)

    def test_dot_invalid_despite_existing(self):
        """`.` exists but is only dots/whitespace, so it is rejected."""
        assert not ut.is_valid_path('.')

    def test_is_relative_to(self, tmp_path: Path):
        assert ut.is_relative_to(tmp_path / 'a' / 'b', tmp_path)
        assert not ut.is_relative_to(tmp_path, tmp_path / 'a')

    def test_is_relative_to_respects_segment_boundaries(self, tmp_path: Path):
        """Regression: sibling dirs sharing a string prefix are NOT relative to each other."""
        assert not ut.is_relative_to(str(tmp_path) + 'suffix/x', tmp_path)
        assert not ut.is_relative_to('/home/user/foo-bar', '/home/user/foo')

    def test_is_relative_to_self(self, tmp_path: Path):
        """A path is relative to itself (matching `Path.is_relative_to` semantics)."""
        assert ut.is_relative_to(tmp_path, tmp_path)

    @pyt.mark.parametrize(
        'child, parent, expected',
        [
            ('/a/b/c', '/a/b', True),
            ('/a/b/c', '/a/b/', True),  # trailing slash normalized away
            ('/a/bc', '/a/b', False),
            ('/a/b', '/a/b/c', False),
            ('a/b/c', 'a/b', True),  # relative paths compare by parts too
            ('/x/y', '/a', False),
        ],
    )
    def test_is_relative_to_matrix(self, child: str, parent: str, expected: bool):
        assert ut.is_relative_to(child, parent) is expected

    def test_relativize_first_match_wins(self, tmp_path: Path):
        path = tmp_path / 'a' / 'b.txt'
        assert ut.relativize(path, tmp_path / 'a', tmp_path) == Path('b.txt')
        assert ut.relativize(path, tmp_path, tmp_path / 'a') == Path('a/b.txt')

    def test_relativize_no_match(self, tmp_path: Path):
        assert ut.relativize(tmp_path, '/nonexistent-root-xyz') is None

    @pyt.mark.parametrize(
        'registry_attr, prefix',
        [('pkgs', 'Packages'), ('inst', 'Packages'), ('cache', 'Cache')],
    )
    def test_path_to_resource(self, registry_attr: str, prefix: str):
        path = getattr(PATHS, registry_attr) / 'Foo' / 'f.py'
        assert ut.path_to_resource(path) == f'{prefix}/Foo/f.py'

    def test_path_to_resource_unrelated(self, tmp_path: Path):
        assert ut.path_to_resource(tmp_path / 'f.py') is None


class TestReadFile:
    """Tests for ``Utils.read_file``."""

    def test_raw_multiline_text_passthrough(self):
        raw = 'line one\nline two'
        assert ut.read_file(raw) == ('', raw)

    def test_raw_long_text_passthrough(self):
        raw = 'x' * 300
        assert ut.read_file(raw) == ('', raw)

    def test_absolute_existing_file(self, tmp_path: Path):
        target = tmp_path / 'data.txt'
        target.write_text('payload')
        assert ut.read_file(target) == ('', 'payload')

    def test_absolute_missing_file_asserts(self, tmp_path: Path):
        with pyt.raises(AssertionError, match='does not exist'):
            ut.read_file(tmp_path / 'missing.txt')

    def test_unresolvable_relative_raises(self):
        with pyt.raises(ValueError, match='Could not resolve'):
            ut.read_file('definitely/not/a/resource.xyz')


class TestFromFile:
    """Tests for ``Utils.from_file`` reader dispatch."""

    @pyt.mark.parametrize(
        'name, content, expected',
        [
            ('conf.yaml', 'a: 1\nb: [2, 3]', {'a': 1, 'b': [2, 3]}),
            ('conf.yml', 'x: true', {'x': True}),
            ('conf.json', '{"a": 1}', {'a': 1}),
            ('conf.toml', 'a = 1', {'a': 1}),
        ],
    )
    def test_loads_by_suffix(self, tmp_path: Path, name: str, content: str, expected: dict):
        target = tmp_path / name
        target.write_text(content)
        assert ut.from_file(target) == expected

    def test_pickle(self, tmp_path: Path):
        target = tmp_path / 'data.pkl'
        target.write_bytes(pickle.dumps({'k': 1}, protocol=0))
        assert ut.from_file(target) == {'k': 1}

    def test_explicit_filetype_overrides_suffix(self, tmp_path: Path):
        target = tmp_path / 'data.txt'
        target.write_text(json.dumps({'a': 2}))
        assert ut.from_file(target, filetype='json') == {'a': 2}

    def test_empty_yaml_becomes_empty_dict(self, tmp_path: Path):
        target = tmp_path / 'empty.yaml'
        target.write_text('')
        assert ut.from_file(target) == {}

    def test_scalar_wrapped_in_dict(self, tmp_path: Path):
        target = tmp_path / 'scalar.yaml'
        target.write_text('42')
        assert ut.from_file(target) == {'data': 42}

    def test_list_preserved(self, tmp_path: Path):
        target = tmp_path / 'list.json'
        target.write_text('[1, 2]')
        assert ut.from_file(target) == [1, 2]

    def test_unsupported_suffix_raises(self, tmp_path: Path):
        target = tmp_path / 'file.xyz'
        target.write_text('data')
        with pyt.raises(ValueError, match='Unsupported file type'):
            ut.from_file(target)

    def test_no_suffix_raises(self):
        with pyt.raises(ValueError, match='Could not infer filetype'):
            ut.from_file('noextension')


class TestWindowHelpers:
    """Tests for the window-facing helpers (`get_window`, `open_folders`, `open_projects`)."""

    def test_get_window_by_id(self):
        window = _Window()
        assert ut.get_window(window.id()) is window

    def test_get_window_unknown_id(self):
        assert ut.get_window(-12345) is None

    def test_window_folders(self, tmp_path: Path):
        window = _Window()
        window.set_project_data({'folders': [{'path': str(tmp_path)}]})
        assert ut.window_folders(window) == [tmp_path]

    def test_open_folders_includes_existing(self, tmp_path: Path):
        window = _Window()
        window.set_project_data({'folders': [{'path': str(tmp_path)}]})
        folders = ut.open_folders()
        assert folders[window.id()] == {tmp_path}

    def test_open_folders_skips_missing(self, tmp_path: Path, capsys: pyt.CaptureFixture):
        window = _Window()
        window.set_project_data({'folders': [{'path': str(tmp_path / 'gone')}]})
        assert window.id() not in ut.open_folders()
        assert 'does not exist' in capsys.readouterr().out

    def test_open_folders_expands_symlinks(self, tmp_path: Path):
        real = tmp_path / 'real'
        real.mkdir()
        link = tmp_path / 'link'
        link.symlink_to(real)
        window = _Window()
        window.set_project_data({'folders': [{'path': str(link)}]})
        assert ut.open_folders()[window.id()] == {link, real}

    def test_open_projects_resolves_relative_folders(self, tmp_path: Path):
        (tmp_path / 'src').mkdir()
        window = _Window()
        cast('Any', window)._project_file_name = str(tmp_path / 'myproj.sublime-project')
        window.set_project_data({'folders': [{'path': 'src'}]})
        projects = ut.open_projects()
        assert projects['myproj'] == {tmp_path / 'src'}

    def test_expand_symlinks(self, tmp_path: Path):
        real = tmp_path / 'real'
        real.mkdir()
        link = tmp_path / 'link'
        link.symlink_to(real)
        assert list(ut.expand_symlinks(link, tmp_path)) == [link, real, tmp_path]


class TestMultiprint:
    """Tests for ``Utils.multiprint`` formatting."""

    def test_quiet_returns_without_printing(self, capsys: pyt.CaptureFixture):
        result = ut.multiprint('hello', quiet=True)
        assert 'hello' in result
        assert capsys.readouterr().out == ''

    def test_title_indents_content(self):
        result = ut.multiprint('body', title='Header:', quiet=True)
        lines = result.strip('\n').splitlines()
        assert lines[0] == 'Header:'
        assert lines[1] == '    body'

    def test_data_dict_rendered_as_key_values(self):
        result = ut.multiprint(data={'key': 'val'}, quiet=True)
        assert "{'key': 'val'}" in result  # small mappings print inline

    def test_long_data_rendered_multiline(self):
        data = {'alpha': 'x' * 40, 'beta': 'y' * 40}
        result = ut.multiprint(data=data, quiet=True)
        assert 'alpha: ' in result and 'beta: ' in result

    def test_margins(self):
        result = ut.multiprint('x', margins=(2, 3), quiet=True)
        assert result.startswith('\n\n') and result.endswith('\n\n\n')

    def test_lines_and_items_merged(self):
        result = ut.multiprint('item', lines=['line'], quiet=True)
        assert result.index('line') < result.index('item')


class TestDebugFence:
    """Tests for the ``debug_fence`` context manager."""

    def test_prints_fence_around_block(self, capsys: pyt.CaptureFixture):
        with ut.debug_fence('SECTION', mark='=', width=20):
            print('inner')
        out = capsys.readouterr().out
        assert out.count('=' * 20) == 2
        assert 'SECTION' in out
        assert out.index('SECTION') < out.index('inner')

    def test_indent(self, capsys: pyt.CaptureFixture):
        with ut.debug_fence('T', mark='-', width=10, indent=4):
            pass
        assert '    ' + '-' * 6 in capsys.readouterr().out
