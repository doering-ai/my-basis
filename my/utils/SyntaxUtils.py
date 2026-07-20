############
### HEAD ###
############
### STANDARD
from collections import deque
from collections.abc import Collection
from types import ModuleType
from typing import Annotated, Any
import functools as ft
import importlib as imp
import inspect

### EXTERNAL
from pydantic_core import core_schema as pyd_schema
import pydantic as pyd
import regex as re

### INTERNAL (NOTE: If adding new internal imports, update the comments in `__init__.py`)
from ..infra.types import Vecs, Maps
from ._UtilsBase import _UtilsBase
from .IterUtils import iter_utils


############
### BODY ###
############
class SyntaxUtils(_UtilsBase):
    """Methods for syntax-y tasks (i.e. related to data's form rather than its content)."""

    # -----------------
    # `0` NORMALIZATION
    # -----------------
    @classmethod
    def fill_tree[T, C](cls, tree: dict[T, C]) -> None:
        """Recursively replace None values with empty dicts in a nested tree structure.

        Modifies tree in-place.

        Args:
            tree: Nested dictionary tree to fill.
        """
        for key, val in tree.items():
            if isinstance(val, dict):
                cls.fill_tree(val)
            elif val is None:
                tree[key] = {}  # type:ignore

    @classmethod
    def tree_size(cls, tree: object) -> int:
        """Calculate total number of leaf nodes in a nested tree structure.

        Args:
            tree: Tree structure (dict of dicts, or leaf value).
        Returns:
            Total count of leaf nodes (non-dict values).
        """
        return sum(map(cls.tree_size, tree.values())) if isinstance(tree, dict) else 1

    # --------------
    # `1` ANNOTATION
    # --------------
    @staticmethod
    def pyd_schemify(tvar: type) -> pyd.GetPydanticSchema:
        """Create Pydantic schema validator for instance type checking.

        Args:
            tvar: Type to create validator for.
        Returns:
            GetPydanticSchema validator for use with Annotated types.
        """
        return pyd.GetPydanticSchema(lambda _, __: pyd_schema.is_instance_schema(cls=tvar))

    # Regex
    RegexField = Annotated[re.Pattern, pyd_schemify(re.Pattern)]
    MatchField = Annotated[re.Match, pyd_schemify(re.Match)]

    # --------------
    # `2` REFLECTION
    # --------------
    @staticmethod
    def instance_fields(cls: type) -> dict[str, Any]:  # type: ignore
        """Extract instance field names and annotations from a Pydantic model or typeddict.

        Args:
            cls: Pydantic BaseModel class to inspect.
        Returns:
            Dictionary mapping lowercase field names to their type annotations.
        """
        if issubclass(cls, pyd.BaseModel):
            annotations = {field: info.annotation for field, info in cls.model_fields.items()}
        elif inspect.isclass(cls):
            annotations = {
                field: ann
                for field, ann in inspect.get_annotations(cls, eval_str=True).items()
                if (member := getattr(cls, field, None)) is not None
                and not (inspect.isfunction(member) or inspect.isclass(member))
            }
        else:
            return {}

        return {
            field: ann for field, ann in annotations.items() if field.islower() and ann is not None
        }

    @ft.lru_cache(maxsize=1024)
    @staticmethod
    def instance_aliases(cls: type) -> dict[str, Any]:
        """Extract field aliases and types from a Pydantic model with caching.

        Resolves field aliases including validation aliases and alias choices,
        converting AliasPath objects to string representations.

        Args:
            cls: Pydantic BaseModel class to inspect.
        Returns:
            Dictionary mapping field aliases to their type annotations.
        """
        if not issubclass(cls, pyd.BaseModel):
            return SyntaxUtils.instance_fields(cls)

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
        max_depth: int = 10,
    ) -> bool:
        """Recursively search and replace a single value in nested data structures.

        Supports sequences (list, tuple, deque, set), mappings (dict), and Pydantic
        models. Recursively traverses nested structures up to depth limit.

        A tuple is immutable, so a value found directly among a tuple's own elements
        cannot be replaced in place; that case reports `False` rather than a false
        success. Mutable containers (list, dict, model, ...) nested *inside* a tuple
        are still replaced normally, since the tuple's reference to them is untouched.

        Args:
            obj: Collection or Pydantic model to search within.
            old: Value to find and replace.
            new: Replacement value.
            depth: Current recursion depth, up to a hard max of 100.
            max_depth: Maximum recursion depth.
        Returns:
            True if value was found and replaced, False otherwise.
        """
        children: Collection[Collection | pyd.BaseModel] | None = None
        if isinstance(obj, Vecs):
            if old in obj:
                if isinstance(obj, (list, deque)):
                    index = obj.index(old)
                    obj[index] = new
                    return True
                elif isinstance(obj, tuple):
                    # Tuples are immutable: rebinding the local `obj` can't propagate a
                    # replacement back to the caller's reference, so no mutation actually
                    # occurs here. Report `False` rather than falsely claiming success.
                    return False
                elif isinstance(obj, set):
                    obj.remove(old)
                    obj.add(new)
                    return True
            else:
                children = obj

        elif isinstance(obj, Maps):
            if key := iter_utils.find_key(obj, old):
                obj[key] = new  # type:ignore
                return True
            else:
                children = list(obj.values())  # ty: ignore[invalid-assignment]

        elif isinstance(obj, pyd.BaseModel):
            attrs = iter_utils.attr_map(obj, cls.instance_fields(type(obj)).keys())
            if field := iter_utils.find_key(attrs, old):
                setattr(obj, field, new)
                return True
            else:
                children = list(attrs.values())

        if children and depth < max_depth:
            return any(
                cls.nested_replace(child, old, new, depth + 1, max_depth)
                for child in filter(bool, children)
            )
        return False

    @staticmethod
    def import_module(file: pyd.FilePath, root: pyd.DirectoryPath) -> ModuleType:
        """Dynamically import a Python module from a file path.

        Converts file path to module dotted notation and imports it.

        Args:
            file: Path to Python file to import.
            root: Root directory for relative import path calculation.
        Returns:
            Imported ModuleType object.
        """
        pathstr = file.with_suffix('').relative_to(root).as_posix().replace('/', '.')
        return imp.import_module(pathstr)

    # -----------
    # `3` CACHING
    # -----------
    @staticmethod
    def clear_cached_properties(inst: object, *properties: str) -> None:
        """Clear cached properties from an object instance.

        If no properties specified, clears all properties listed in instance's
        CACHED_PROPERTIES attribute.

        Args:
            inst: Object instance to clear cached properties from.
            *properties: Property names to clear. If empty, uses inst.CACHED_PROPERTIES.
        """
        if not properties and hasattr(inst, 'CACHED_PROPERTIES'):
            properties = tuple(getattr(inst, 'CACHED_PROPERTIES'))

        for prop in properties:
            if prop in inst.__dict__:
                del inst.__dict__[prop]


syntax_utils = SyntaxUtils
"""An alias of `SyntaxUtils`, cased so as to imply static usage."""
