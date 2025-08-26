############
### HEAD ###
############
### STANDARD
from typing import Any, Mapping, ClassVar
import more_itertools as mi
from collections import deque, defaultdict

### EXTERNAL
import pytest as pyt

### INTERNAL
from my.type.Predicate import Predicate
from my.text.Buffer import Buffer

cls = Predicate


############
### BODY ###
############
class TestPredicate:
    # --------------------
    # Helper Data
    # --------------------
    SAMPLES: ClassVar[dict[str, Predicate]] = dict(
        basic=cls.new(dict(k1=['A', 'B'], k2=['C'])),
        dupes=cls.new(dict(k1=['A', 'B', 'B'], k2=['C', 'D', 'C']), duplicates=True),
        nests=cls.new(dict(root=dict(c1=['A'], c2=['B', 'C']), k1=['D'])),
    )

    # --------------------
    # Utility Functions
    # --------------------

    # --------------------
    # Initialization & Validation
    # --------------------
    @pyt.mark.parametrize(
        'field, val, expected', [
            ('k1', 'A', dict(k1=['A'])),
            ('k1', ['A', 'B'], dict(k1=['A', 'B'])),
            ('k1', ['A', 'B', 'B'], dict(k1=['A', 'B', 'B'])),
            ('k1.child', 'val', dict([('k1.child', ['val'])])),
            ('parent.child.grandchild', ['A'], dict([('parent.child.grandchild', ['A'])])),
        ]
    )
    def test_cast(self, field: str, val: Any, expected: dict[str, list[str]]):
        result = dict(cls.cast(field, val, duplicates=True))
        assert result == expected

    @pyt.mark.parametrize(
        'data, expected', [
            (dict(k1='A'), dict(k1=['A'])),
            (dict(k1=['A', 'B']), dict(k1=['A', 'B'])),
            ([('k1', ['A', 'B'])], dict(k1=['A', 'B'])),
            ([('k1', 'A')], dict(k1=['A'])),
            (
                dict(parent=dict(k1='A', child=dict(grandchild='B'))),
                dict([('parent.k1', ['A']), ('parent.child.grandchild', ['B'])]),
            ),
            ({}, {}),
            (cls.new(dict(k1=['A'])), dict(k1=['A'])),
            ('{"k1": "A", "k2": "B"}', dict(k1=['A'], k2=['B'])),
            (['{"k1": "A", "k2": "B"}'], dict(k1=['A'], k2=['B'])),
            (['"k1": "A"', '"k2": "B"'], dict(k1=['A'], k2=['B'])),
            ([('parent.child.grandchild', ['A']), ('numbers', ['5', '10', '15'])], {
                'parent.child.grandchild': ['A'],
                'numbers': ['5', '10', '15']
            }),
        ]
    )
    def test_new(self, data: Any, expected: dict[str, list[str]]):
        result = cls.new(data)
        assert result.data == expected

    @pyt.mark.parametrize(
        'data', [
            dict(k1=['A', 'B']),
            [('k1', ['A', 'B'])],
            dict(parent=dict(child='val')),
        ]
    )
    def test_init_success(self, data):
        pred = cls.new(data)
        assert isinstance(pred, cls)

    # --------------------
    # Dictionary-like Interface
    # --------------------
    def test_getitem(self):
        pred = cls.new(self.SAMPLES['basic'])
        assert pred['k1'] == ['A', 'B']
        assert pred['k2'] == ['C']
        assert pred['k3'] == []

    @pyt.mark.parametrize(
        'key, val, expected', [
            ('k1', 'val', dict(k1=['val'])),
            ('k1', ['A', 'B'], dict(k1=['A', 'B'])),
            ('k1', dict(child='val'), dict([('k1.child', ['val'])])),
            ('existing', 'new_val', dict(existing=['new_val'])),
        ]
    )
    def test_setitem(self, key: str, val: Any, expected: dict):
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
        ]
    )
    def test_contains(self, lhs: dict | Predicate, rhs: object, expected: bool):
        pred = cls.new(lhs, duplicates=False)
        assert (rhs in pred) == expected

    @pyt.mark.parametrize(
        'lhs, rhs, expected', [
            (dict(k1=['A']), dict(k1=['A', 'A']), False),
            (SAMPLES['basic'], dict(k1=['B', 'B', 'A']), False),
            (SAMPLES['dupes'], dict(k1=['B', 'B', 'A']), True),
        ]
    )
    def test_contains__duplicates(self, lhs: dict, rhs: object, expected: bool):
        pred = cls.new(lhs, duplicates=True)
        assert (rhs in pred) == expected

    @pyt.mark.parametrize(
        'lhs, rhs, expected', [
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
        ]
    )
    def test_eq(self, lhs: Any, rhs: Any, expected: bool):
        pred = cls.new(lhs, duplicates=True)
        assert (pred == rhs) == expected

    @pyt.mark.parametrize(
        'data, expected', [
            (SAMPLES['basic'], (2, 3)),
            (SAMPLES['dupes'], (2, 6)),
            (SAMPLES['nests'], (3, 4)),
            ({}, (0, 0)),
        ]
    )
    def test_len_and_size(self, data: Any, expected: tuple[int, int]):
        pred = cls.new(data, duplicates=True)
        assert (len(pred), pred.size) == expected

    @pyt.mark.parametrize(
        'data, expected', [
            (SAMPLES['basic'], [('k1', ['A', 'B']), ('k2', ['C'])]),
        ]
    )
    def test_getters(self, data: Any, expected: list[tuple[str, list[str]]]):
        pred = cls.new(data)
        assert pred.items() == expected
        keys, values = map(list, mi.unzip(expected))
        assert pred.keys() == keys
        # assert pred.values() == values

    @pyt.mark.parametrize(
        'key, default, expected', [
            ('k1', [], ['A', 'B']),
            ('nonexistent', ['default'], ['default']),
            ('k2', [], ['C']),
        ]
    )
    def test_get(self, key: str, default: list, expected: list):
        pred = cls.new(self.SAMPLES['basic'])
        assert pred.get(key, default) == expected

    # ----------
    # Operations
    # ----------
    @pyt.mark.parametrize(
        'lhs, rhs, expected', [
            (dict(k1=['A']), dict(k2=['B']), dict(k1=['A'], k2=['B'])),
            (dict(k1=['A']), dict(k1=['B']), dict(k1=['A', 'B'])),
            (
                dict(k1=['A', 'B']),
                dict(k1=['B', 'C']),
                dict(k1=['A', 'B', 'C']),
            ),
            (dict(), dict(k1=['A']), dict(k1=['A'])),
            (dict(k1=['A']), dict(), dict(k1=['A'])),
        ]
    )
    def test_add(self, lhs: Any, rhs: Any, expected: dict):
        pred0, pred1 = cls.new(lhs), cls.new(rhs)
        result = pred0 + pred1
        assert result.data == expected

        # Ensure original is unchanged
        assert pred0.data == lhs
        assert pred1.data == rhs

    @pyt.mark.parametrize(
        'lhs, rhs, expected', [
            (dict(k1=['A']), dict(k2=['B']), dict(k1=['A'], k2=['B'])),
            (dict(k1=['A']), dict(k1=['B']), dict(k1=['B'])),
            (dict(k1=['A', 'B']), dict(k1=['B', 'C']), dict(k1=['B', 'C'])),
            (dict(), dict(k1=['A']), dict(k1=['A'])),
            (dict(k1=['A']), dict(), dict(k1=['A'])),
        ]
    )
    def test_or(self, lhs: Any, rhs: Any, expected: dict):
        pred0, pred1 = cls.new(lhs), cls.new(rhs)
        assert pred0 | pred1 == expected

    @pyt.mark.parametrize(
        'lhs, rhs, expected', [
            (dict(k1=['A']), dict(k2=['B']), dict(k1=['A'])),
            (dict(k1=['A']), dict(k1=['A']), dict()),
            (dict(k1=['A', 'B']), dict(k1=['B', 'C']), dict(k1=['A'])),
            ({}, dict(k1=['A']), dict()),
            (dict(k1=['A']), {}, dict(k1=['A'])),
        ]
    )
    def test_sub(self, lhs: Any, rhs: Any, expected: dict):
        pred0, pred1 = cls.new(lhs), cls.new(rhs)
        assert pred0 - pred1 == expected

    @pyt.mark.parametrize(
        'lhs, rhs, expected',
        [
            (dict(k1=['A', 'B']), dict(k1=['A', 'C']), dict(k1=['A'])),
            (dict(k1=['A'], k2=['B']), dict(k1=['A']), dict(k1=['A'])),
            (dict(k1=['A']), dict(k2=['B']), {}),  # no overlap
            (dict(k1=['A', 'B']), dict(k1=['A', 'B', 'C']), dict(k1=['A', 'B'])),
        ]
    )
    def test_and(self, lhs: dict, rhs: dict, expected: dict):
        pred1 = cls.new(lhs)
        pred2 = cls.new(rhs)
        result = pred1 & pred2
        assert result == expected

    # ----------------------
    # Export & Serialization
    # ----------------------
    @pyt.mark.parametrize(
        'data, dupes, expected', [
            (dict(), True, []),
            (SAMPLES['dupes'], False, [('k1', ['A', 'B']), ('k2', ['C', 'D'])]),
            (SAMPLES['dupes'], True, [('k1', ['A', 'B', 'B']), ('k2', ['C', 'D', 'C'])]),
            (SAMPLES['nests'], False, [('root.c1', ['A']), ('root.c2', ['B', 'C']), ('k1', ['D'])]),
        ]
    )
    def test_import_map(
        self, data: dict | Predicate, dupes: bool, expected: list[tuple[str, list[str]]]
    ):
        result = list(cls.import_map(data, duplicates=dupes))
        assert result == expected

    @pyt.mark.parametrize(
        'data, typevar, expected',
        [
            ({}, None, {}),
            (SAMPLES['basic'], None, dict(k1=['A', 'B'], k2=['C'])),
            (SAMPLES['basic'], dict[str, str], dict(k1='A', k2='C')),
            (SAMPLES['basic'], dict[str, None], dict(k1=['A', 'B'], k2=['C'])),
            (SAMPLES['basic'], dict[str, Buffer], dict(k1=Buffer.new('A'), k2=Buffer.new('C'))),
            (SAMPLES['basic'], list[str], ['"k1": ["A", "B"]', '"k2": ["C"]']),
            (SAMPLES['basic'], str, '{"k1": ["A", "B"], "k2": ["C"]}'),
            (SAMPLES['basic'], list[int], [('k1', ['A', 'B']), ('k2', ['C'])]),

            # Known Classes
            (dict(k1=['1', '2']), dict[str, deque[int]], dict(k1=deque([1, 2]))),
            (
                dict(k1=['1', '2', '3'], k2=['4', '5', '6']),
                defaultdict[str, list[int]],
                defaultdict(list, dict(k1=[1, 2, 3], k2=[4, 5, 6])),
            ),

            # Complex nests
            (
                dict([('a.b.c', ['55']), ('aa', ['66'])]),
                None,
                dict(a=dict(b=dict(c=['55'])), aa=['66']),
            ),
            (
                dict([('a.b.c', ['55']), ('aa', ['66'])]),
                Mapping[str, list[int] | Mapping],
                dict(a=dict(b=dict(c=[55])), aa=[66]),
            ),
            (
                dict([('a.b.c', ['55']), ('aa', ['66'])]),
                Mapping[str, list[int] | Mapping[str, list[int] | Mapping]],
                dict(a=dict(b=dict(c=[55])), aa=[66]),
            ),
            (
                dict([('a.b.c', ['55']), ('aa', ['66'])]),
                Mapping[str, int],
                {
                    'a.b.c': 55,
                    'aa': 66
                },
            ),
            (
                dict([('a.b.c', ['55']), ('aa', ['66'])]),
                Mapping[tuple[str, ...], list[int]],
                dict([(('a', 'b', 'c'), [55]), (('aa', ), [66])]),
            ),
        ]
    )
    def test_serialize(self, data: dict[str, list[str]], typevar: type | None, expected: Any):
        pred = cls.new(data)
        result = pred.serialize(tvar=typevar)
        assert result == expected

    @pyt.mark.parametrize(
        'text, expected', [
            ('simple text', 'simple text'),
            ('text\nwith\nnewlines', 'text\\nwith\\nnewlines'),
            ('no newlines', 'no newlines'),
            ('multiple\n\nnewlines\n', 'multiple\\n\\nnewlines\\n'),
            ('', ''),
        ]
    )
    def test_escape(self, text: str, expected: str):
        assert cls._escape(text) == expected

    @pyt.mark.parametrize(
        'data, expected', [
            (
                dict(k1=['A'], k2=['B', 'C']),
                ['k1: A', 'k2: [B, C]'],
            ),
            (
                [('parent.child.grandchild', ['A']), ('numbers', ['5', '10', '15'])],
                ['numbers: [5, 10, 15]', 'parent:', '    child:', '        grandchild: A'],
            ),
            (
                dict(
                    ratios=['0.5', '0.666', '1.0000'],
                    answers=['yes', 'True', 'N', 'false'],
                    n=['1000']
                ),
                ['answers: [true, true, false, false]', 'n: 1000', 'ratios: [0.5, 0.666, 1.0]'],
            ),
        ]
    )
    def test_to_and_from_yaml(self, data: Any, expected: list[str]):
        # I. Test to_yaml
        pred = Predicate.new(data, duplicates=True)
        serialized = pred.to_yaml()
        lines = list(filter(bool, serialized.splitlines()))
        assert lines == expected

        # II. Test from_yaml
        deserialized = Predicate.from_yaml(serialized, duplicates=True)
        assert deserialized.to_yaml() == serialized
