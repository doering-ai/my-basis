############
### HEAD ###
############
### STANDARD
from __future__ import annotations
from typing import ClassVar, Any, overload
from typing_extensions import Self, Annotated
from pathlib import Path
import functools as ft

### EXTERNAL
import jinja2 as jn
import pydantic as pyd
import regex as re

### INTERNAL
from ..infra.utils import ut


############
### BODY ###
############
class Template(pyd.RootModel):
    """A wrapper around Jinja2 templates for use in Sublime Text plugins."""

    DEFAULTS: ClassVar[dict[str, Any]] = dict(
        trim_blocks=True,
        lstrip_blocks=True,
    )
    ENVS: ClassVar[dict[str, jn.Environment]] = {
        '': jn.Environment(**DEFAULTS),
    }
    RGXS: ClassVar[dict[str, re.Pattern]] = ut.rgx_dict(
        dirname=r'templates?|tmpls?|data|static|assets?|resources?',
    )

    root: Annotated[jn.Template, ut.schemify(jn.Template)]

    # -------------------
    # `.` Initial Methods
    # -------------------
    @staticmethod
    @ft.lru_cache(2**6)
    def _new_from_raw(raw: str) -> Template:
        return Template(Template.ENVS[''].from_string(raw))

    @staticmethod
    @ft.lru_cache(2**6)
    def _new_from_path(
        path: str | Path, root: jn.Template | None = None, **kwargs: Any
    ) -> Template:
        path = Path(path)
        parent = str(Template._infer_root(path))

        if root:
            pass
        elif env := Template.ENVS.get(parent, None):
            root = env.get_template(path.name)
        else:
            env = Template.ENVS[parent] = Template._new_environment(parent, **kwargs)
            root = env.get_template(path.name)
        return Template(root)

    # -------------------
    # `-` Private Methods
    # -------------------
    @staticmethod
    def _infer_root(path: Path | str) -> Path:
        path = Path(path).expanduser()
        ret = next(
            filter(lambda p: bool(Template.RGXS['dirname'].fullmatch(p.name)), path.parents),
            path.parent,
        )
        if ret is None:
            raise ValueError(f'Could not infer template root from path: {path}')
        return ret

    @classmethod
    def _new_environment(cls, path: str | None = None, **kwargs: Any) -> jn.Environment:
        if path:
            kwargs.setdefault('loader', jn.FileSystemLoader(path))
        for k, v in cls.DEFAULTS.items():
            kwargs.setdefault(k, v)
        return jn.Environment(**kwargs)

    # -------------------
    # `+` Primary Methods
    # -------------------

    # ------------------
    # `*` Public Methods
    # ------------------
    @overload
    @classmethod
    def get(cls, *, raw: str, **kwargs: Any) -> Self: ...

    @overload
    @classmethod
    def get(cls, path: str | Path, *, root: jn.Template | None = None, **kwargs: Any) -> Self: ...

    @classmethod
    def get(
        cls,
        path: str | Path | None = None,
        root: jn.Template | None = None,
        raw: str | None = None,
        **kwargs: Any,
    ) -> Self:
        """Create a new Template instance from a file path or raw string."""
        if raw:
            ret = cls._new_from_raw(raw)
        elif path:
            ret = cls._new_from_path(path, root, **kwargs)
        else:
            raise ValueError('Either path or raw must be provided to create a Template.')

        assert isinstance(ret, cls), f'Expected Template instance, got {type(ret)}'
        return ret
