############
### HEAD ###
############
### STANDARD
from __future__ import annotations

### EXTERNAL
import pytest as pyt
import regex as re

### INTERNAL
from myBasis.infra.constants import NO_ESC, RGXS, EVENTS, ASYNCABLE_EVENTS


############
### BODY ###
############
class TestEvents:
    """Tests for the ``EVENTS`` dict."""

    def test_keys(self):
        assert set(EVENTS.keys()) == {'views', 'none', 'view', 'window', 'buffer'}

    def test_all_values_are_lists_of_str(self):
        for key, events in EVENTS.items():
            assert isinstance(events, list), f'{key} should be a list'
            for event in events:
                assert isinstance(event, str), f'{key}: {event!r} should be str'

    @pyt.mark.parametrize(
        'key, expected',
        [
            ('views', ['init']),
            ('none', ['exit']),
        ],
    )
    def test_simple_groups(self, key: str, expected: list[str]):
        assert EVENTS[key] == expected

    def test_view_events_nonempty(self):
        assert len(EVENTS['view']) > 10

    def test_window_events_nonempty(self):
        assert len(EVENTS['window']) > 5

    def test_buffer_events(self):
        assert EVENTS['buffer'] == ['associate_buffer']

    def test_no_duplicates_within_group(self):
        for key, events in EVENTS.items():
            assert len(events) == len(set(events)), f'{key} has duplicate events'

    def test_no_duplicates_across_groups(self):
        all_events = [e for events in EVENTS.values() for e in events]
        assert len(all_events) == len(set(all_events)), 'Duplicate events across groups'


class TestAsyncableEvents:
    """Tests for the ``ASYNCABLE_EVENTS`` set."""

    def test_is_set(self):
        assert isinstance(ASYNCABLE_EVENTS, set)

    def test_all_members_are_str(self):
        for event in ASYNCABLE_EVENTS:
            assert isinstance(event, str)

    def test_subset_of_all_events(self):
        all_events = {e for events in EVENTS.values() for e in events}
        assert all_events >= ASYNCABLE_EVENTS, 'ASYNCABLE_EVENTS contains events not in EVENTS'

    def test_contains_modified(self):
        assert 'modified' in ASYNCABLE_EVENTS

    def test_contains_activated(self):
        assert 'activated' in ASYNCABLE_EVENTS

    def test_excludes_exit(self):
        assert 'exit' not in ASYNCABLE_EVENTS

    def test_excludes_save(self):
        assert 'save' not in ASYNCABLE_EVENTS

    def test_excludes_text_command(self):
        assert 'text_command' not in ASYNCABLE_EVENTS

    def test_nonempty(self):
        assert len(ASYNCABLE_EVENTS) > 10


class TestRegexConstants:
    """Tests for ``NO_ESC`` and ``RGXS``."""

    def test_no_esc_is_pattern(self):
        assert isinstance(NO_ESC, str)

    def test_no_esc_compiles(self):
        re.compile(NO_ESC)

    def test_rgxs_has_snake_separators(self):
        assert 'snake_separators' in RGXS

    def test_rgxs_snake_separators_is_pattern(self):
        assert isinstance(RGXS['snake_separators'], re.Pattern)

    def test_rgxs_snake_separators_matches_underscore(self):
        pat = RGXS['snake_separators']
        assert pat.search('hello_world')
        assert pat.search('a_b_c')

    def test_rgxs_snake_separators_no_match_no_alnum(self):
        pat = RGXS['snake_separators']
        # Underscore not between alphanumeric chars
        assert not pat.search('__')
        assert not pat.search('_')
