############
### HEAD ###
############
### STANDARD
from __future__ import annotations
from typing import ClassVar, Generator
from typing_extensions import Self
import contextlib as ctx
import functools as ft

### EXTERNAL
import pydantic as pyd
import sublime as sb

### INTERNAL
from ..infra.PathRegistry import PATHS
from ..infra.utils import ut


############
### DATA ###
############
_REGISTRY = dict()
#: PKG names already claimed by a subclass definition (instances register in `_REGISTRY`).
_DEFINED: set[str] = set()


############
### BODY ###
############
class PackageSettings(pyd.BaseModel):
    """Settings object for defining your package's settings in a clear, obvious format."""

    PKG: ClassVar[str] = ''
    REGISTRY: ClassVar[dict[str, PackageSettings]] = _REGISTRY

    _root: sb.Settings | None = None

    debug: bool = pyd.Field(False, description='Whether to enable debug mode for this package.')

    @classmethod
    def __init_subclass__(cls, *args, **kwargs) -> None:
        if not (pkg := getattr(cls, 'PKG', '')):
            raise TypeError(f'Settings model "{cls.__name__}" must define a `PKG` class variable.')
        if pkg in _DEFINED:
            raise TypeError(f'Settings model for package "{pkg}" already registered.')
        _DEFINED.add(pkg)

    @classmethod
    def new(cls, settings: sb.Settings | None = None) -> Self:
        """Create a new instance of the top-level settings class, reading any applicable files."""
        if cls.PKG not in cls.REGISTRY:
            if settings is None:
                settings = sb.load_settings(f'{cls.PKG}.sublime-settings')
            _get = ft.partial(cls._get, settings)
            data = {key: val for key in cls.normkeys() if (val := _get(key))}
            cls.REGISTRY[cls.PKG] = cls(**data)
        return cls.REGISTRY[cls.PKG]

    @classmethod
    def _get(cls, settings: sb.Settings, key: str) -> object | None:
        return next((v for alias in cls._alias(key) if (v := settings.get(alias, None))), None)

    @staticmethod
    @ft.lru_cache(2**10)
    def normkey(key: str) -> str:
        """Normalize the given settings field name, transforming it to snake-case words."""
        return '.'.join(map(ut.recase, key.strip(' "\'').split('.')))

    @classmethod
    def _pre(cls) -> str:
        return cls.normkey(f'{cls.PKG}.')

    @classmethod
    def _alias(cls, key: str) -> Generator[str]:
        pre = cls._pre()
        # prefixed, not, orig,
        key, raw = cls.normkey(key), key
        yield raw
        if raw.startswith(pre):
            yield raw[len(pre) :]
            if key != raw:
                yield key
        else:
            yield f'{pre}{key}'
            if key != raw:
                yield f'{cls.PKG}.{raw}'

    @classmethod
    def keys(cls) -> set[str]:
        """Get the keys for this settings class, which are the field names defined in the class."""
        return set(cls.model_fields.keys())

    @classmethod
    def normkeys(cls) -> set[str]:
        """Get the normalized (i.e. snake-case) keys for this settings class."""
        return set(map(cls.normkey, cls.keys()))

    @classmethod
    def filename(cls) -> str:
        """Get the filename for this settings class."""
        return f'{cls.PKG}.sublime-settings'

    @ctx.contextmanager
    @classmethod
    def open(cls) -> Generator[Self]:
        """Open the settings for potential editing, writing any changes back at the end."""
        inst = cls.new()
        _old = inst.model_dump(exclude_unset=True)

        yield inst

        _new = inst.model_dump(exclude_unset=True)
        if _new and _new != _old:
            settings = inst._root
            assert settings, 'Settings instance not found on object.'
            for key, value in _new.items():
                settings.set(key, value)
            sb.save_settings(cls.filename())

    def refresh(self, settings: sb.Settings) -> Self:
        """Refresh the state of this object based on new readings from a file."""
        for key in self.model_fields.keys():
            if val := settings.get(key, settings.get(f'PKG.{key}', None)):
                setattr(self, key, val)
        return self

    @classmethod
    def write_schema(cls) -> dict:
        """Create a JSON schema for this settings class and save it to the local package."""
        text = cls.model_json_schema()
        # text = ut.pretty_json(schema)
        file = PATHS.pkgs / cls.PKG / 'settings-schema.json'
        assert file.parent.exists(), f'Package not found at {PATHS.pkgs}.'
        file.write_text(text)
