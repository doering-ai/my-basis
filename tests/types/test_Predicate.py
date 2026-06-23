############
### HEAD ###
############
### STANDARD
from typing import ClassVar
from collections.abc import Mapping
import more_itertools as mi
from collections import deque, defaultdict

### EXTERNAL
import pytest as pyt

### INTERNAL
from my.types import Predicate, Buffer

cls = Predicate


############
### BODY ###
############
class TestPredicate:
    SAMPLES: ClassVar[dict[str, Predicate]] = dict(
        basic=cls.new(k1=['A', 'B'], k2=['C']),
        dupes=cls.new(k1=['A', 'B', 'B'], k2=['C', 'D', 'C'], duplicates=True),
        nests=cls.new(k1=dict(c1=dict(c11=['A']), c2=['B', 'C']), k2=['D']),
    )

    # -------------------
    # `.` Initial Methods
    # -------------------
    @pyt.mark.parametrize(
        'args, kwargs, expected',
        [
            (None, None, dict()),
            (
                [dict(k1='AB')],
                None,
                dict(k1=['AB']),
            ),
            (
                [dict(k1=['A', 'B'])],
                None,
                dict(k1=['A', 'B']),
            ),
            (
                [[('k1', ['A', 'B'])]],
                None,
                dict(k1=['A', 'B']),
            ),
            (
                [[('k1', 'A')]],
                None,
                dict(k1=['A']),
            ),
            (
                None,
                dict(k1='A'),
                dict(k1=['A']),
            ),
            (
                None,
                dict(k1=['A', 'B']),
                dict(k1=['A', 'B']),
            ),
            (
                None,
                dict(k1=[1, 2]),
                dict(k1=['1', '2']),
            ),
            (
                None,
                dict(parent=dict(k1='A', child=dict(grandchild='B'))),
                {'parent.k1': ['A'], 'parent.child.grandchild': ['B']},
            ),
            (
                [cls.new(k1=['A'])],
                None,
                dict(k1=['A']),
            ),
            (
                ['{"k1": "A", "k2": "B"}'],
                None,
                dict(k1=['A'], k2=['B']),
            ),
            (
                [[('parent.child.grandchild', ['A']), ('numbers', ['5', '10', '15'])]],
                None,
                {'parent.child.grandchild': ['A'], 'numbers': ['5', '10', '15']},
            ),
            (None, dict(duplicates=True), dict()),
            (
                None,
                dict(k1=['A', 'B', 'B'], duplicates=True),
                dict(k1=['A', 'B', 'B']),
            ),
            (
                None,
                dict(k1=['A', 'B', 'B'], duplicates=False),
                dict(k1=['A', 'B']),
            ),
            (
                [SAMPLES['basic']],
                None,
                dict(k1=['A', 'B'], k2=['C']),
            ),
            (
                [SAMPLES['nests']],
                None,
                {'k1.c1.c11': ['A'], 'k1.c2': ['B', 'C'], 'k2': ['D']},
            ),
            (
                [SAMPLES['dupes']],
                dict(duplicates=True),
                dict(k1=['A', 'B', 'B'], k2=['C', 'D', 'C']),
            ),
            (
                [SAMPLES['dupes']],
                dict(duplicates=False),
                dict(k1=['A', 'B'], k2=['C', 'D']),
            ),
        ],
    )
    def test_new(self, args: list | None, kwargs: dict | None, expected: dict[str, list[str]]):
        result = cls.new(*(args or []), **(kwargs or {}))
        assert result.data == expected

    @pyt.mark.parametrize(
        'data, typevar, expected',
        [
            ({}, None, {}),
            (SAMPLES['basic'], None, dict(k1=['A', 'B'], k2=['C'])),
            (SAMPLES['basic'], dict[str, str], dict(k1='A', k2='C')),
            (SAMPLES['basic'], dict[str, set[str]], dict(k1={'A', 'B'}, k2={'C'})),
            (SAMPLES['basic'], dict[str, list[set[str]]], dict(k1=[{'A'}, {'B'}], k2=[{'C'}])),
            (
                SAMPLES['basic'],
                dict[str, list[Buffer]],
                dict(k1=[Buffer.new('A'), Buffer.new('B')], k2=[Buffer.new('C')]),
            ),
            (SAMPLES['basic'], list[str], ['"k1": ["A", "B"]', '"k2": ["C"]']),
            (SAMPLES['basic'], str, '{"k1": ["A", "B"], "k2": ["C"]}'),
            (SAMPLES['basic'], list, [('k1', ['A', 'B']), ('k2', ['C'])]),
            # Known Classes
            (dict(k1=['1', '2']), dict[str, deque[int]], dict(k1=deque([1, 2]))),
            (
                dict(k1=['1', '2', '3'], k2=['4', '5', '6']),
                defaultdict[str, list[int]],
                defaultdict(list, dict(k1=[1, 2, 3], k2=[4, 5, 6])),
            ),
            # Complex nests
            (
                {'a.b.c': ['55'], 'aa': ['66']},
                None,
                dict(a=dict(b=dict(c=['55'])), aa=['66']),
            ),
            (
                {'a.b.c': ['55'], 'aa': ['66']},
                Mapping[str, list[int] | Mapping],
                dict(a=dict(b=dict(c=[55])), aa=[66]),
            ),
            (
                {'a.b.c': ['55'], 'aa': ['66']},
                Mapping[str, list[int] | Mapping[str, list[int] | Mapping]],
                dict(a=dict(b=dict(c=[55])), aa=[66]),
            ),
            (
                {'a.b.c': ['55'], 'aa': ['66']},
                Mapping[str, int],
                {'a.b.c': 55, 'aa': 66},
            ),
            (
                {'a.b.c': ['55'], 'aa': ['66']},
                Mapping[tuple[str, ...], list[int]],
                {('a', 'b', 'c'): [55], ('aa',): [66]},
            ),
        ],
    )
    def test_serialize(self, data: dict[str, list[str]], typevar: type | None, expected):
        pred = cls.new(data)
        result = pred.serialize(tvar=typevar)
        assert result == expected

    # -------------------
    # `-` Private Methods
    # -------------------
    @pyt.mark.parametrize(
        'text, expected',
        [
            ('simple text', 'simple text'),
            ('text\nwith\nnewlines', 'text\\nwith\\nnewlines'),
            ('no newlines', 'no newlines'),
            ('multiple\n\nnewlines\n', 'multiple\\n\\nnewlines\\n'),
            ('', ''),
        ],
    )
    def test_escape(self, text: str, expected: str):
        assert cls._escape(text) == expected

    # -------------------
    # `+` Primary Methods
    # -------------------

    @pyt.mark.parametrize(
        'data, expected',
        [
            (
                dict(k1=['A'], k2=['B', 'C']),
                ['k1: A', 'k2:', '    - B', '    - C'],
            ),
            (
                [('parent.child.grandchild', ['A']), ('numbers', ['5', '10', '15'])],
                [
                    'numbers:',
                    '    - 5',
                    '    - 10',
                    '    - 15',
                    'parent:',
                    '    child:',
                    '        grandchild: A',
                ],
            ),
            (
                dict(
                    ratios=['0.5', '0.666', '1.0000'],
                    answers=['yes', 'True', 'N', 'false'],
                    n=['1000'],
                ),
                [
                    'answers:',
                    '    - true',
                    '    - true',
                    '    - false',
                    '    - false',
                    'n: 1000',
                    'ratios:',
                    '    - 0.5',
                    '    - 0.666',
                    '    - 1.0',
                ],
            ),
        ],
    )
    def test_to_and_from_yaml(self, data, expected: list[str]):
        # I. Test to_yaml
        pred = Predicate.new(data, duplicates=True)
        serialized = pred.to_yaml()
        lines = list(filter(bool, serialized.splitlines()))
        assert lines == expected

        # II. Test from_yaml
        deserialized = Predicate.from_yaml(serialized, duplicates=True)
        assert deserialized.to_yaml() == serialized

    # ------------------
    # `*` Public Methods
    # ------------------
    # --------------
    # `*0` Overrides
    # --------------
    def test_getitem(self):
        pred = cls.new(self.SAMPLES['basic'])
        assert pred['k1'] == ['A', 'B']
        assert pred['k2'] == ['C']
        assert pred['k3'] == []

    @pyt.mark.parametrize(
        'key, val, expected',
        [
            ('k1', 'val', dict(k1=['val'])),
            ('k1', ['A', 'B'], dict(k1=['A', 'B'])),
            ('k1', dict(child='val'), {'k1.child': ['val']}),
            ('existing', 'new_val', dict(existing=['new_val'])),
        ],
    )
    def test_setitem(self, key: str, val, expected: dict):
        pred = cls.new(self.SAMPLES['basic'])
        pred[key] = val
        for exp_key, exp_val in expected.items():
            assert pred[exp_key] == exp_val

    def test_delitem(self):
        pred = cls.new(self.SAMPLES['basic'])
        del pred['k1']
        assert pred.keyset == {'k2'}

    @pyt.mark.parametrize(
        'lhs, rhs, expected',
        [
            # Key presence
            (SAMPLES['basic'], 'k1', True),
            (SAMPLES['basic'], 'nonexistent', False),
            (SAMPLES['basic'], ('k1', 'k2'), True),
            (SAMPLES['basic'], ('k1', 'k2', 'k3'), False),
            # Slot Presence
            (SAMPLES['basic'], dict(k1=['A']), True),
            (SAMPLES['basic'], dict(k1=['A', 'B']), True),
            (SAMPLES['basic'], dict(k1=['B', 'A']), True),  # ordering
            (SAMPLES['basic'], dict(k1=['A', 'B', 'B']), True),  # no dupes yet
            (SAMPLES['basic'], dict(k1=['A', 'B', 'C']), False),
            (SAMPLES['basic'], dict(K1=['A']), False),  # case sensitivity
        ],
    )
    def test_contains(self, lhs: Predicate, rhs: object, expected: bool):
        pred = cls.new(lhs, duplicates=False)
        assert (rhs in pred) == expected

    @pyt.mark.parametrize(
        'lhs, rhs, expected',
        [
            (cls.new(k1=['A']), dict(k1=['A', 'A']), False),
            (SAMPLES['basic'], dict(k1=['B', 'B', 'A']), False),
            (SAMPLES['dupes'], dict(k1=['B', 'B', 'A']), True),
        ],
    )
    def test_contains__duplicates(self, lhs: dict, rhs: object, expected: bool):
        pred = cls.new(lhs, duplicates=True)
        assert (rhs in pred) == expected

    @pyt.mark.parametrize(
        'lhs, rhs, expected',
        [
            (SAMPLES['basic'], SAMPLES['basic'], True),
            (SAMPLES['basic'], [('k1', ['A', 'B']), ('k2', 'C')], True),
            (SAMPLES['basic'], 5, False),
            (SAMPLES['dupes'], dict(k1=['B', 'A', 'B'], k2=['D', 'C', 'C']), True),
            (SAMPLES['dupes'], dict(k1=['B', 'A', 'B'], k2=['C', 'C', 'C']), False),
            (SAMPLES['nests'], SAMPLES['nests'], True),
            (
                dict(ratios=[0.5, 0.666, 1.0], answers=[True, True, False, False], n=[1000]),
                dict(answers=[True, True, False, False], n=[1000], ratios=[0.5, 0.666, 1.0]),
                True,
            ),
        ],
    )
    def test_eq(self, lhs, rhs, expected: bool):
        pred = cls.new(lhs, duplicates=True)
        assert (pred == rhs) == expected

    @pyt.mark.parametrize(
        'data, expected',
        [
            (SAMPLES['basic'], (2, 3)),
            (SAMPLES['dupes'], (2, 6)),
            (SAMPLES['nests'], (3, 4)),
            (cls(), (0, 0)),
        ],
    )
    def test_len_and_size(self, data, expected: tuple[int, int]):
        assert (len(data), data.size) == expected

    @pyt.mark.parametrize(
        'key, default, expected',
        [
            ('k1', [], ['A', 'B']),
            ('nonexistent', ['default'], ['default']),
            ('k2', [], ['C']),
        ],
    )
    def test_get(self, key: str, default: list, expected: list):
        assert self.SAMPLES['basic'].get(key, default) == expected

    @pyt.mark.parametrize(
        'lhs, rhs, expected',
        [
            (dict(k1=['A']), dict(k2=['B']), dict(k1=['A'], k2=['B'])),
            (dict(k1=['A']), dict(k1=['B']), dict(k1=['A', 'B'])),
            (
                dict(k1=['A', 'B']),
                dict(k1=['B', 'C']),
                dict(k1=['A', 'B', 'C']),
            ),
            (dict(), dict(k1=['A']), dict(k1=['A'])),
            (dict(k1=['A']), dict(), dict(k1=['A'])),
        ],
    )
    def test_add(self, lhs, rhs, expected: dict):
        pred0, pred1 = cls.new(lhs), cls.new(rhs)
        result = pred0 + pred1
        assert result.data == expected

        # Ensure original is unchanged
        assert pred0.data == lhs
        assert pred1.data == rhs

    @pyt.mark.parametrize(
        'lhs, rhs, expected',
        [
            (dict(k1=['A']), dict(k2=['B']), dict(k1=['A'], k2=['B'])),
            (dict(k1=['A']), dict(k1=['B']), dict(k1=['B'])),
            (dict(k1=['A', 'B']), dict(k1=['B', 'C']), dict(k1=['B', 'C'])),
            (dict(), dict(k1=['A']), dict(k1=['A'])),
            (dict(k1=['A']), dict(), dict(k1=['A'])),
        ],
    )
    def test_or(self, lhs, rhs, expected: dict):
        pred0, pred1 = cls.new(lhs, overwrite=True), cls.new(rhs)
        assert pred0 | pred1 == expected

    @pyt.mark.parametrize(
        'lhs, rhs, expected',
        [
            (dict(k1=['A']), dict(k2=['B']), dict(k1=['A'])),
            (dict(k1=['A']), dict(k1=['A']), dict()),
            (dict(k1=['A', 'B']), dict(k1=['B', 'C']), dict(k1=['A'])),
            ({}, dict(k1=['A']), dict()),
            (dict(k1=['A']), {}, dict(k1=['A'])),
        ],
    )
    def test_sub(self, lhs, rhs, expected: dict):
        pred0, pred1 = cls.new(lhs), cls.new(rhs)
        assert pred0 - pred1 == expected

    @pyt.mark.parametrize(
        'lhs, rhs, expected',
        [
            (dict(k1=['A', 'B']), dict(k1=['A', 'C']), dict(k1=['A'])),
            (dict(k1=['A'], k2=['B']), dict(k1=['A']), dict(k1=['A'])),
            (dict(k1=['A']), dict(k2=['B']), {}),  # no overlap
            (dict(k1=['A', 'B']), dict(k1=['A', 'B', 'C']), dict(k1=['A', 'B'])),
        ],
    )
    def test_and(self, lhs: dict, rhs: dict, expected: dict):
        result = cls.new(lhs) & cls.new(rhs)
        assert result == cls.new(expected)

    # --------------
    # `*2` Accessors
    # --------------
    @pyt.mark.parametrize(
        'data, expected',
        [
            (SAMPLES['basic'], [('k1', ['A', 'B']), ('k2', ['C'])]),
        ],
    )
    def test_accessors(self, data: Predicate, expected: list[tuple[str, list[str]]]):
        assert data.items() == expected
        keys, values = map(list, mi.unzip(expected))
        assert data.keys() == keys
        assert data.values() == values

    # -------------
    # `*3` Mutators
    # -------------
