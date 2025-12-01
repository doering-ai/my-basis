############
### HEAD ###
############
### STANDARD
from regex import Match

### EXTERNAL
from pytest import mark

### INTERNAL
from my.text import MatchData

Captures = dict[str, list[str]]
Params = dict[str, str]

############
### DATA ###
############
cls = MatchData


############
### BODY ###
############
class TestMatchData:
    @mark.parametrize(
        'data, match, expected', [
            (dict(one='1', two=2), None, dict(one=['1'], two=['2'])),
            (dict(alpha=['1', '2'], beta=['3', '4']), None, None),
            (dict(alpha=['1', '2', '1']), None, None),
        ]
    )
    def test_new(self, data: dict, match: Match | None, expected: Captures | None):
        if expected is None:
            expected = data.copy()

        ret = cls(data=data, match=match)

        if match is None:
            assert ret.match is None
            if data is None:
                assert not ret.data
        else:
            assert ret.match is not None
            assert ret.data == expected

    @mark.parametrize(
        'data, field, default, expected', [
            (dict(alpha=['1', '2']), 'alpha', '', '2'),
            (dict(alpha=['1', '2']), '1', '', ''),
            (dict(alpha=['1', '2']), '1', 'DEF', 'DEF'),
            (dict(), '1', 'DEF', 'DEF'),
            (dict(), '', 'DEF', 'DEF'),
            (dict(alpha=['123', '1']), 'alpha', '', '1'),
            (dict(alpha=['1231', '1']), 'alpha', '', '1231'),
        ]
    )
    def test_at(self, data: Captures, field: str, default: str, expected: str):
        inst = cls(data=data)
        assert inst.at(field, default) == expected
