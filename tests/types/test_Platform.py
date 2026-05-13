############
### HEAD ###
############
### STANDARD
import platform

### EXTERNAL
import pytest as pyt

### INTERNAL
from my.types import Platform
from ..conftest import Patch, boolmap

cls = Platform
PLAT = cls.local()


############
### BODY ###
############
class TestPlatform:
    """Test suite for the Platform IntFlag enum."""

    # -------------------
    # `.` Initial Methods
    # -------------------
    @pyt.mark.parametrize(
        'member, expected',
        [
            (Platform.NONE, 0),
            (Platform.MOBILE, 2),
            (Platform.GNU, 4),
            (Platform.MAC, 8),
            (Platform.DOS, 16),
            (Platform.IOS, 42),  # auto() | MOBILE | MAC = 32 | 2 | 8
            (Platform.ANDROID, 70),  # auto() | MOBILE | GNU = 64 | 2 | 4
            (Platform.OLD, 128),
            (Platform.ERR, 128),  # OLD | NONE = 128 | 0
        ],
    )
    def test_auto(self, member: Platform, expected: int):
        assert member.value == expected

    @pyt.mark.parametrize(
        'member, op, flag, expected',
        boolmap(
            true=[
                (Platform.IOS, 'and', Platform.MOBILE),
                (Platform.IOS, 'and', Platform.MAC),
                (Platform.MAC, 'and', Platform.IOS),
                (Platform.MAC, 'in', Platform.IOS),
                (Platform.GNU, 'in', Platform.ANDROID),
                (Platform.MOBILE, 'in', Platform.ANDROID),
                (Platform.MOBILE, 'in', Platform.IOS),
                (Platform.OLD, 'in', Platform.ERR),
                (Platform.IOS, 'and', Platform.ANDROID),  # both include MOBILE
            ],
            false=[
                (Platform.IOS, 'in', Platform.MAC),
            ],
        ),
    )
    def test_bitwise_comparison(self, member: Platform, op: str, flag: Platform, expected: bool):
        if _not := op.startswith('not '):
            op = op[4:]

        if op == 'and':
            ret = bool(member & flag)
        elif op == 'in':
            ret = member in flag
        elif op == 'or':
            ret = bool(member | flag)
        else:
            raise ValueError(f'Invalid operator: {op}')

        if _not:
            ret = not ret
        assert ret == expected

    # -------------------
    # `+` Primary Methods
    # -------------------
    def test_local(self):
        assert isinstance(cls.local(), cls)

    @pyt.mark.parametrize(
        'plat, strings',
        [
            (cls.GNU, ['linux', 'gnu', 'unix', 'bsd', 'cygwin']),
            (cls.MAC, ['osx', 'darwin']),
            (cls.DOS, ['windows', 'dos', 'win32']),
            (cls.IOS, ['iphone', 'apple']),
            (cls.ANDROID, ['android', 'google']),
            (cls.OLD, ['sunos', 'solaris']),
            (cls.NONE, ['unknownsystem12345', '', '0', '!!', '; drop table USERS']),
        ],
    )
    def test_match(self, plat: Platform, strings: list[str], patch: Patch, subtests: pyt.Subtests):
        for i, string in enumerate(strings):
            with subtests.test(msg=f'platform.system() = "{string}"', i=i):
                patch.setattr(platform, 'system', lambda _s=string: _s)
                cls._set_local(None)
                assert cls.local() == plat
