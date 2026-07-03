############
### HEAD ###
############
### STANDARD
from __future__ import annotations

### EXTERNAL
import regex as re

### INTERNAL
from myBasis.infra.constants import NO_ESC, RGXS, EVENTS, ASYNCABLE_EVENTS


############
### BODY ###
############
class TestEventInvariants:
    """Cross-cutting invariants of the event tables (not mere restatements)."""

    def test_no_duplicates_within_group(self):
        for key, events in EVENTS.items():
            assert len(events) == len(set(events)), f'{key} has duplicate events'

    def test_no_duplicates_across_groups(self):
        all_events = [e for events in EVENTS.values() for e in events]
        assert len(all_events) == len(set(all_events)), 'Duplicate events across groups'

    def test_asyncable_events_subset_of_all_events(self):
        all_events = {e for events in EVENTS.values() for e in events}
        assert all_events >= ASYNCABLE_EVENTS, 'ASYNCABLE_EVENTS contains events not in EVENTS'


class TestRegexConstants:
    """Behavioral tests for the shared regex constants."""

    def test_no_esc_compiles(self):
        re.compile(NO_ESC)

    def test_no_esc_rejects_escaped(self):
        pattern = re.compile(NO_ESC + r'x')
        assert pattern.search('ax')
        assert not pattern.search('a\\x'), 'a backslash-escaped char must not match'
        assert pattern.search('a\\\\x'), 'an escaped backslash does not escape the char'

    def test_snake_separators_matches_underscore_between_words(self):
        pat = RGXS['snake_separators']
        assert pat.search('hello_world')
        assert pat.search('a_b_c')

    def test_snake_separators_ignores_bare_underscores(self):
        pat = RGXS['snake_separators']
        assert not pat.search('__')
        assert not pat.search('_')
