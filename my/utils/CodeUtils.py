############
### HEAD ###
############
### STANDARD
from typing import (
    Any,
    Collection,
    Mapping,
    Sequence,
)
from collections import deque
from types import ModuleType
import functools as ft
import importlib as imp

### EXTERNAL
import pydantic as pyd

### INTERNAL
from ..infra import Series
from .IterUtils import iut


############
### BODY ###
############
class CodeUtils:
    @staticmethod
    def instance_fields(cls: type[pyd.BaseModel]) -> dict[str, type]:
        return {
            field: info.annotation
            for field, info in cls.model_fields.items()
            if field.islower() and info.annotation is not None
        }

    @ft.lru_cache(maxsize=1024)
    @staticmethod
    def instance_aliases(cls: type[pyd.BaseModel]) -> dict[str, type]:
        ret = {}
        for field, info in cls.model_fields.items():
            if field.islower() and info.annotation is not None:
                if alias := info.alias:
                    field = alias
                elif v_alias := info.validation_alias:
                    if isinstance(v_alias, pyd.AliasChoices):
                        v_alias = v_alias.choices[0]

                    if isinstance(v_alias, pyd.AliasPath):
                        field = str(v_alias.convert_to_aliases()[0])
                    else:
                        field = v_alias
                ret[field] = info.annotation
        return ret

    @classmethod
    def nested_replace(
        cls,
        obj: Collection | pyd.BaseModel,
        old: Any,
        new: Any,
        depth: int = 0,
    ) -> bool:
        next_iter: Collection[Collection | pyd.BaseModel] | None = None
        if isinstance(obj, Series):
            if old in obj:
                if isinstance(obj, Sequence):
                    index = obj.index(old)
                    if isinstance(obj, list | deque):
                        obj[index] = new
                    elif isinstance(obj, tuple):
                        obj = tuple(obj[:index] + (new,) + obj[index + 1 :])
                else:
                    obj.remove(old)
                    obj.add(new)
                return True
            else:
                next_iter = obj

        elif isinstance(obj, Mapping):
            if key := iut.find_key(obj, old):
                obj[key] = new  # type:ignore
                return True
            else:
                next_iter = list(obj.values())  # ty: ignore[invalid-assignment]

        elif isinstance(obj, pyd.BaseModel):
            attrs = iut.attr_map(obj, cls.instance_fields(type(obj)).keys())
            if field := iut.find_key(attrs, old):
                setattr(obj, field, new)
                return True
            else:
                next_iter = list(attrs.values())

        if next_iter and depth < 10:
            return any(
                map(
                    ft.partial(cls.nested_replace, old=old, new=new, depth=depth + 1),
                    filter(
                        lambda val: val and isinstance(val, Collection | pyd.BaseModel),
                        next_iter,
                    ),
                )
            )
        return False

    @staticmethod
    def import_module(file: pyd.FilePath, root: pyd.DirectoryPath) -> ModuleType:
        pathstr = file.with_suffix('').relative_to(root).as_posix().replace('/', '.')
        return imp.import_module(pathstr)

    @staticmethod
    def clear_cached_properties(inst: object, *properties: str) -> None:
        if not properties and hasattr(inst, 'CACHED_PROPERTIES'):
            properties = tuple(getattr(inst, 'CACHED_PROPERTIES'))

        for prop in properties:
            if prop in inst.__dict__:
                del inst.__dict__[prop]

        # TODO: outdated?
        # for attr in filter(lambda attr: hasattr(inst, attr), properties):
        #     delattr(inst, attr)


cut = CodeUtils
