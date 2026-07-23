############
### HEAD ###
############
### STANDARD
import warnings

### EXTERNAL
import pytest as pyt
from regex import Match

### INTERNAL
from my.regex import MatchData

cls = MatchData


############
### BODY ###
############
class TestMatchData:
    @pyt.mark.parametrize(
        'data, match, expected',
        [
            (dict(one='1', two=2), None, dict(one=['1'], two=['2'])),
            (dict(alpha=['1', '2'], beta=['3', '4']), None, None),
            (dict(alpha=['1', '2', '1']), None, None),
        ],
    )
    def test_new(self, data: dict, match: Match | None, expected: dict[str, list[str]] | None):
        if expected is None:
            expected = data.copy()

        ret = cls.new(data=data, match=match)

        if match is None:
            assert ret.match is None
            if data is None:
                assert not ret.data
        else:
            assert ret.match is not None
            assert ret.data == expected

    @pyt.mark.parametrize(
        'data, field, default, expected',
        [
            (dict(alpha=['1', '2']), 'alpha', '', '2'),
            (dict(alpha=['1', '2']), '1', '', ''),
            (dict(alpha=['1', '2']), '1', 'DEF', 'DEF'),
            (dict(), '1', 'DEF', 'DEF'),
            (dict(), '', 'DEF', 'DEF'),
            (dict(alpha=['123', '1']), 'alpha', '', '1'),
            (dict(alpha=['1231', '1']), 'alpha', '', '1231'),
        ],
    )
    def test_at(self, data: dict[str, list[str]], field: str, default: str, expected: str):
        inst = cls(data=data)
        assert inst.at(field, default) == expected

    @pyt.mark.parametrize(
        'data',
        [
            # basis-12 item 6: `flex_deserialize` "decasts" numeric-looking captures into real
            # int/float values during serialization, so a round-trip leaves non-str leaves in a
            # dict[str, list[str]]-shaped field. `_serialize_predicate`'s return-type annotation
            # used to claim every leaf was `str`, which made pydantic emit
            # `UserWarning: Pydantic serializer warnings` for any decast leaf.
            dict(count=['123']),
            dict(ratio=['1.5']),
            dict(mixed=['1', '2']),
            dict(flag=['true']),
        ],
    )
    def test_serialize__no_serializer_warnings(self, data: dict[str, list[str]]):
        inst = cls(data=data)
        with warnings.catch_warnings():
            warnings.simplefilter('error')
            inst.model_dump()
