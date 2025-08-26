############
### HEAD ###
############
### STANDARD
import functools as ft
from pathlib import Path

### EXTERNAL

### INTERNAL
from ..base.MyEnum import MyEnum

############
### DATA ###
############
ALIASES = dict(
    ts=['ts', 'tsx', 'js', 'jsx'],
    md=['md', 'my'],
    sql=['sql', 'sqlite', 'db'],
    cpp=['cpp', 'c++', 'cxx', 'cc', 'h'],
    yaml=['yaml', 'yml'],
    toml=['toml', 'tml'],
    css=['css', 'scss'],
)


############
### BODY ###
############
class Lang(MyEnum):
    # Modules
    PY = 'py'
    TS = 'tsx'
    CPP = 'cpp'
    RUST = 'rs'

    # Documents
    MD = 'md'
    YAML = 'yaml'
    TOML = 'toml'
    JSON = 'json'

    # Databases
    SQL = 'sql'
    PRISMA = 'prisma'

    # Websites
    HTML = 'html'
    CSS = 'css'

    # Scripts
    SH = 'sh'
    ZSH = 'zsh'

    @property
    def prefix(self) -> str:
        return self.name.lower()

    @property
    def suffix(self) -> str:
        return self.value

    @ft.cached_property
    def aliases(self) -> list[str]:
        return ALIASES.get(self.name.lower(), [self.value])

    @ft.cached_property
    def fastglob(self) -> str:
        # Follows "fast-glob" syntax
        # See: github.com/mrmlnc/fast-glob#pattern-syntax
        if self == Lang.PY:
            return '.py'
        if self == Lang.TS:
            return '.[jt]s?(x)'
        elif self == Lang.MD:
            return '.m[dy]'
        elif self == Lang.YAML:
            return '.y?(a)ml'
        elif self == Lang.TOML:
            return '.t?(o)ml'
        elif self == Lang.CSS:
            return '.?(s)css'
        else:
            return f'.({"|".join(self.aliases)})'

    @classmethod
    def read_path(cls, path: Path) -> 'Lang':
        return cls.read(path.suffix)

    @classmethod
    def read(cls, value: str | int | list) -> 'Lang':
        if isinstance(value, str):
            value = value.lower().strip(' .')
            for lang, aliases in ALIASES.items():
                if value in aliases:
                    return cls.__members__[lang.upper()]
        return super().read(value)
