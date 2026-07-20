############
### HEAD ###
############
### STANDARD
from __future__ import annotations
from typing import Any, ClassVar, Literal, TypeGuard, TypeVar, overload
from collections.abc import (
    Callable,
    Iterable,
    Mapping,
    Sequence,
    Hashable,
)
from collections import deque
from copy import deepcopy
from datetime import datetime
from enum import Enum
from pathlib import Path
import contextlib as ctx
import functools as ft
import inspect
import itertools as it
import more_itertools as mi
import logging

### EXTERNAL
import pydantic as pyd
from regex import Pattern

### INTERNAL
from ..infra.types import (
    Scalar,
    Scalars,
    Atoms,
    Atom,
    VecT,
    Vec,
    Iter,
    Map,
    Model,
    Struct,
)
from ..utils import ut
from .MyType import MyType, TypeArg
from .match import TypeMatch
from .cast import TypeCast, Transform, CastFlags, CastPreset
from .check import TypeCheck

############
### DATA ###
############
# Misc aliases
File = pyd.FilePath
Directory = pyd.DirectoryPath

ClassType = TypeVar('ClassType')

FileParam = str | bytes | File | None
RawJsonData = str | int | float | bool | list | dict | None
F = TypeVar('F')


type CaseKey = type | Callable[[object], bool]  #:
type CaseVal = Callable[[object], Any]

logger = logging.getLogger()

ty: Typist


############
### BODY ###
############
class Typist(TypeCheck, TypeMatch, TypeCast):
    """Semi-singleton interface for building systems that are resilient to slight inconsistencies.

    Specifically, this class provides runtime type introspection, parsing, and coercion capabilities
    that extend Python's static type hints into the runtime domain.

    This class was originally built as an extension of a Minksian Frame data structure, which needed
    to flexibly translate between untyped LLM outputs and strongly-typed in-memory data structures.
    It contains a large variety of functionality-for and examples-of working with types at runtime,
    but I suspect that this sort of **"Vibe Typing"** usecase will remain its shining capability.

    .. tip::
       Typist is written as an instanced class only for situations where configuration differs
       across a single project. If that's not you, just use the global instance ``typist``!

    .. rubric:: I. Parsing

    The features of Typist that most diverge from what's capable with the standard library rely
    on the ``parse()`` method, which decomposes a given type so that other methods can intelligently
    handly each part in turn. By far the most likely usecase is for containers such as
    ``dict[str, int]`` (which becomes the tuple ``(dict, str, int)``) and ``list[int]`` (which
    becomes ``(list, int, None)``), but it's useful for other generics, unions (e.g.
    ``string | int``), and special non-type forms (e.g. ``Annotated`` and ``Literal``).

    That said, not all possible type annotations are covered -- see the ``Typist.SPECIAL_TYPES``
    attribute for a best-effort list of unhandled annotations.

    .. rubric:: II. Comparison

    **Type Comparison ("matching")**

    Type matching (mostly via ``match()``) determines whether a value or type is a valid subset of
    another type. As opposed to the stdlib's ``issubclass()``, Typist handles subtypes of generics
    recursively; for example, ``dict[str, int]`` matches ``Mapping[str, int]`` and
    ``Collection[Sequence, int]``, but not ``Mapping[str, str]`` or ``Collection[int]``.

    Matching results are cached using a ``NestedCache`` for performance.

    A small number of non-atomic yet common types are handled with custom logic:
    ``tuple[int, str, float]`` only matches another tuple with the same length and member types,
    whereas ``tuple[int, ...]`` matches any-length tuples of ints.

    **Object Comparison ("checking")**

    Runtime data can be compared to other data using ``match_instances()``, but obviously the
    primary usecase is to bring type-checking functionality into runtime in an ergonomic, idiomatic
    way. For this, Typist publishes ``check()`` for individual object/type pairs, and ``all_are()``
    for asserting the types of the contents of containers.

    All of these methods use the TypeGuard protocol to enable type-narrowing in conditional
    statements, complementing static type-checkers like mypy or ty.

    .. rubric:: III. Coercion

    The core functionality is **intelligent type coercion via** ``cast()`` **and** ``flexcast()``,
    which both try their absolute hardest to find a reasonable mapping between any two types.
    Obviously this is definitionally impossible to do perfectly for all possible types, but it has
    been tested extensively on the types that make up the vast majority of usecases (AI or
    otherwise):

    - Atomic types: ``str``, ``int``, ``float``, and ``bool``
    - Series: ``list``, ``tuple``, ``set``, ``deque``, etc.
    - Maps: ``dict``, ``Counter``, ``Predicate``, etc.
    - Pydantic models: any subclass of ``pyd.BaseModel``
    - Times: ``datetime``, ``date``, ``time``, and ``timedelta``
    - Enums: standard Python ``Enum`` types
    - And, most importantly: nested combinations of the above!

    Some of the decisions made within this class are arbitrary, but if the system is used
    consistently for both reading and writing, the implied instability/inconsistency can be
    minimized.

    .. rubric:: IV. Transformation

    Typist provides more than just type coercion, which is ideally a minimally-semantic process.
    Namely, the ``serialize()``, ``assemble()`` and ``distill()`` methods are built to flatten,
    combine together, and split apart complex nested data structures composed of sequences,
    mappings, and even Pydantic objects.

    .. rubric:: V. Persistence

    For reading and writing typed data to and from disk, Typist provides ``to_file()`` and
    ``from_file()``. In just one short statement, users can interface with three file
    formats--**YAML, JSON, and Pickle**--using the very highly performant `srsly
    <https://github.com/explosion/srsly>`_ library.

    .. rubric:: VI. Invocation

    Finally, ``invoke()`` provides safe function calling with automatic type casting of arguments
    and return values. It inspects function signatures to determine expected types, casts provided
    arguments accordingly, and casts the return value to the annotated return type. This enables
    seamless integration of typed functions into dynamic workflows.
    """

    # Static Global Members

    ### Regular Expressions (can't use RegexStore because it depends on this class). Merge the
    ### inherited scalar patterns (int/float/bool/...) with these so methods like `flex_deserialize`
    ### see both; defining `RGXS` here would otherwise shadow `TypeCast.RGXS` entirely.
    RGXS: ClassVar[dict[str, Pattern]] = TypeCast.RGXS | ut.regex_dict(
        dict(
            ### Misc
            splitter=r' *(?:[,]|\/\/) *',
            no_space_splitter=r'(?<=\w)[.:](?=\w)',
            yaml=r'(?sm)^```yaml *\n(?P<content>.+?)\n``` *$',
            timedelta=r'(?i)'
            + ut.multi_rgx(
                r'(?P<weeks>\d+) ?(?:w|weeks?)(?![a-z])',
                r'(?P<days>\d+) ?(?:d|days?)(?![a-z])',
                r'(?P<hours>\d+) ?(?:h|hours?)(?![a-z])',
                r'(?P<minutes>\d+) ?(?:m|mins?|minutes?)(?![a-z])',
                r'(?P<seconds>\d+) ?(?:s|secs?|seconds?)(?![a-z])',
                r'(?P<milliseconds>\d+) ?(?:ms|milliseconds?)(?![a-z])',
                r'(?P<microseconds>\d+) ?(?:us|microseconds?)(?![a-z])',
                r'(?P<hours>\d+):(?P<minutes>\d+):(?P<seconds>\d+(?:\.\d+)?)\b',
                branching=True,
            ),
            short_iso_date=r'\d\d[-./]\d\d[-./]\d\d',
            encoding=r'&#?\w+;',
        )
    )

    ### Metatypes
    SCALAR_TYPES: ClassVar[dict[str, type]] = dict(
        str=str,
        int=int,
        float=float,
        bool=bool,
        datetime=datetime,
        enum=Enum,
    )

    # YAML Config
    RAISE: ClassVar[bool] = True

    # Dynamic Global Members
    LOGGER: ClassVar[logging.Logger] = logger
    _INST: ClassVar[Typist]

    #: Validate flag assignment so runtime toggles (e.g. ``typist.splits = False``) stay
    #: type-checked.
    model_config = pyd.ConfigDict(validate_assignment=True)

    # ---- Cast configuration flags ----
    # These gate the "loose" coercions in the cast chamber. They remain the process-wide default
    # source: `TypeCast.cast()` (and the `upper_cast`/`multicast`/`flexcast` facades) snapshot
    # them into a frozen `CastFlags` exactly once per call -- an explicit `flags=` argument wins,
    # otherwise these fields are read at that single entry point -- so toggling them at runtime
    # (directly, or via a `preset()` bundle) still changes every subsequent cast's default, while
    # a cast already in flight is no longer disturbed by a mid-cast mutation. See
    # `docs/DESIGN-cast-flags.md` and `cast.CastFlags`.

    #: ``Vec -> Atom`` Collapse a multi-element series to its first element (``[1, 2] -> 1``).
    firsts: bool = True

    #: ``Vec -> Atom`` Unwrap a single-element series (``[1] -> 1``).
    atomics: bool = True

    #: ``String -> Struct`` Split a string before casting it to a collection
    #: (``'a.b' -> ['a', 'b']``).
    splits: bool = True

    #: ``Atom <-> Struct`` Wrap an atom into a collection, and vice-versa (``'a' -> ['a']``).
    wraps: bool = True

    @classmethod
    def preset(cls, level: CastPreset = 'basic') -> dict[str, bool]:
        """Get a preset bundle of cast-flag values for a strictness tier.

        Delegates to ``CastFlags.preset``, the canonical per-call value-object equivalent of this
        bundle (see ``docs/DESIGN-cast-flags.md``).

        Args:
            level: The strictness tier -- 'strict' disables every loose coercion, 'basic' enables
                the everyday conveniences, and 'flex' additionally wraps atoms into collections.
        Returns:
            A mapping of cast-flag names to booleans, suitable for ``Typist(**preset(...))`` or for
            assigning onto an existing instance.
        """
        return CastFlags.preset(level).model_dump()

    # -------------------
    # `.` Initial Methods
    # -------------------
    @classmethod
    def inst(cls) -> Typist:
        """Get the global instance of Typist.

        The global singleton defaults to the ``flex`` tier -- every loose coercion enabled -- in
        keeping with the package's permissive "vibe typing" stance. Tighten it per-process by
        assigning a stricter ``preset()`` bundle onto the returned instance.
        """
        if not hasattr(cls, '_INST'):
            cls._INST = cls(**cls.preset('flex'))
        return cls._INST

    # -------------------
    # `-` Private Methods
    # -------------------
    def sort_options(self, data: object, *options: MyType) -> list[MyType]:
        """Sort type options by how well they fit the given data for coercion.

        Args:
            data: The source data to be cast.
            *options: Type options to sort by fitness.
        Returns:
            List of MyType options sorted by fitness score (best first).
        """
        # NOTE: `data` must bind positionally -- a `ft.partial(..., data=data)` keyword bind
        # collides with the option that `sorted` passes positionally (it lands in the `data`
        # slot) and raises `TypeError: got multiple values for argument 'data'`.
        fn = ft.partial(self._score_option, data)
        # `sorted` is stable and `reverse=True` preserves source order among equal scores, so
        # score ties fall back to declaration order -- meaningful for unions (e.g. a constrained
        # TypeVar's first constraint is the canonical choice).
        return list(sorted(options, key=fn, reverse=True))

    @classmethod
    def _score_option(cls, data: object, option: MyType) -> int:
        """Score how well a type option fits the given data for coercion.

        Args:
            data: The source data to be cast.
            option: The type option to score.
        Returns:
            Integer score where higher values indicate better fit.
        """
        # I. Validate and parse args, catching edge cases
        if not (tvar := option.main):
            return -10
        elif option.check(data):
            return 10
        elif option.is_split:
            return max(*(cls._score_option(data, subopt) for subopt in option.args))

        c0 = cls.is_struct(data)
        c1 = cls.is_struct_type(tvar)
        a0 = cls.is_atom(data)
        a1 = cls.is_atom_type(tvar)

        # II. "Main" score: compare the base types, especially atomics vs. collections
        score = 0
        if isinstance(data, tvar):
            # Base type match (tho if we got here, we know that it isn't perfect)
            score += 3
        elif a0 and a1:
            # Both atomic types
            score += 2
        elif a0 or a1 or c0 or c1:
            # Otherwise, if we understood *anything* then we know there's a mismatch
            score -= 2

        # III. Type-specific cases
        if a0 and a1:
            # III.i. Particularly apt atomic casts
            if isinstance(data, int) and issubclass(tvar, bool):  # type: ignore
                score += 1 if data in {0, 1} else -1
            elif isinstance(data, str) and tvar in Scalars:
                # The scalar type the text *literally parses as* (per the `flex_deserialize`
                # priority) fits better than a sibling that would truncate ('-1.5' -> int) or
                # truthify ('123' -> bool) it -- matters for union targets, where members are
                # tried best-fit-first.
                flexed = Transform.flex_deserialize(data)
                if flexed is not None and type(flexed) is tvar:
                    score += 1
        elif c0 and c1:
            # III.ii. Compare the nested values of collection generics
            score += 2
            if cls.is_map(data) and issubclass(tvar, Mapping):
                score += 2
                if option.keys is None:
                    score += 1
                if option.vals is None:
                    score += 1
                if items := ut.map_items(data):
                    keys, vals = mi.unzip(items)
                    if cls.match(tuple(set(map(type, keys))), option.keys):
                        score += 2
                    if cls.match(tuple(set(map(type, vals))), option.vals):
                        score += 2
            elif cls.is_vec(data) and cls.is_vec_type(tvar):
                score += 2

                if option.vals is None:
                    score += 1
                elif data and cls.match(tuple(set(map(type, data))), option.vals):
                    score += 2

        return score

    @staticmethod
    def _read_file(file: str | bytes | File | None) -> str:
        """Read a file and return its contents as a string."""
        if isinstance(file, bytes):
            return file.decode('utf-8')
        elif isinstance(file, Path):
            ut.validate_file(file)
            return file.read_text()
        elif not file:
            return ''
        else:
            return file

    @classmethod
    def _param_is_positional(cls, param: inspect.Parameter) -> bool:
        """Check if a parameter can accept positional arguments.

        Args:
            param: The parameter to check.
        Returns:
            True if the parameter accepts positional arguments.
        """
        return param.kind in {
            param.POSITIONAL_ONLY,
            param.POSITIONAL_OR_KEYWORD,
            param.VAR_POSITIONAL,
        }

    @classmethod
    def _param_is_keyword(cls, param: inspect.Parameter) -> bool:
        """Check if a parameter can accept keyword arguments.

        Args:
            param: The parameter to check.
        Returns:
            True if the parameter accepts keyword arguments.
        """
        return param.kind in {
            param.KEYWORD_ONLY,
            param.POSITIONAL_OR_KEYWORD,
            param.VAR_KEYWORD,
        }

    # -------------------
    # `+` Primary Methods
    # -------------------
    def __repr__(self) -> str:
        return 'Typist'

    @staticmethod
    def specify(tvar: type[F]) -> type[F]:
        """Convert a type variable to its generic form if it's a generic alias."""
        return getattr(tvar, '__origin__', tvar)

    # ------------------
    # `*` Public Methods
    # ------------------
    # ------------
    # `*1` PARSING
    # ------------
    @staticmethod
    def parse(tvar: Any) -> MyType:
        """Parse a type annotation into a MyType instance. See `MyType.parse()` for details."""
        return MyType.parse(tvar)

    # ---------------
    # `*2` COMPARISON
    # ---------------
    @classmethod
    def all_are[T](cls, iterable: Iterable, tvar: type[T]) -> TypeGuard[Iterable[T]]:
        """Check if all values in an iterable match a type variable."""
        return all(cls.check(value, tvar) for value in list(iterable))

    @classmethod
    def any_are[E, T](cls, iterable: Iterable[E], tvar: type[T]) -> TypeGuard[Iterable[E | T]]:
        """Check if any value in an iterable matches a type variable."""
        return any(cls.check(value, tvar) for value in list(iterable))

    def match_instances(self, t0: object, t1: object, intersect: bool = False) -> bool:
        """Check if two instances have matching types.

        Args:
            t0: First instance.
            t1: Second instance.
            intersect: If True, check for intersection; if False, check for subset.
        Returns:
            True if the instances' types match.
        """
        return self.match(MyType.typeof(t0), MyType.typeof(t1), intersect)

    @classmethod
    def type_partition[T0, T1 = object](
        cls,
        data: Iterable[T0 | T1],
        tvar: type[T0],
    ) -> tuple[list[T0], list[T1]]:
        """Separate out all the items matching the given type in the given container.

        Args:
            data: The iterable to partition.
            tvar: The type to partition by.
        Returns:
            1. A list with the rest.
            2. A list of only items that are (subclasses of) the first type.
        """
        myty = MyType.parse(tvar)
        if not myty:
            raise ValueError(f'Type is currently unhandled, and cannot be used: {tvar}')
        return tuple(map(list, mi.partition(myty.check, data)))  # type: ignore

    def seek_usage(self, target: TypeArg, container: type | MyType) -> bool:
        """Check if a type is used anywhere within another type's structure.

        Args:
            target: The type to search for.
            container: The type to search within.
        Returns:
            True if target is used within container's type structure.
        """
        t0 = MyType.parse(target)
        t1 = MyType.parse(container)
        if self.match(t0, t1, True):
            return True

        if inspect.isclass(container):
            # III.ii.a. Recurse into class members
            return any(self.seek_usage(t0, ann) for ann in ut.instance_fields(container).values())
        else:
            # III.ii.b. Recurse into container values
            if t1.keys and self.seek_usage(t0, t1.keys):
                return True

            if t1.vals:
                return self.seek_usage(t0, t1.vals)
            elif t1.literal_members and t1.origin is tuple:
                return any(self.seek_usage(t0, arg) for arg in t1.literal_members)

        return False

    # -------------
    # `*3` COERCION
    # -------------
    def flex_deserialize(self, values: Sequence[str] | str) -> list[Atom]:
        """Convert a list of strings to their most appropriate Atomic types."""
        values = [values] if isinstance(values, str) else list(map(str, values))
        new_types = [
            next(
                (
                    _type
                    for name, _type in self.SCALAR_TYPES.items()
                    if (rgx := self.RGXS.get(name, None)) and rgx.fullmatch(val)
                ),
                str,
            )
            for val in values
        ]
        return [  #  type:ignore
            (val if tvar is str else self.cast(val, tvar))
            for val, tvar in zip(values, new_types, strict=True)
        ]

    def setattr(self, obj: object, key: str, value: Any, tvar: TypeArg = None) -> bool:
        """Set an attribute on an object, casting the value to the appropriate type.

        Args:
            obj: The object to set the attribute on.
            key: The attribute name.
            value: The value to set (will be cast if needed).
            tvar: Optional explicit type to cast to (inferred from obj if None).
        Returns:
            True if successful, False if casting failed.
        """
        # I. Infer the type to cast to, when possible
        if tvar is None:
            tvar = ut.instance_fields(type(obj)).get(key, None)

        # II. When we have a parseable type, cast the value before setting
        if value is not None and (target := MyType.parse(tvar)):
            if (cast_value := self.cast(value, target)) is not None:
                value = cast_value
            else:
                self.LOGGER.error(
                    f'Cannot setattr {type(obj).__name__}.{key} by casting to {tvar}.'
                )
                return False

        # III. Directly set the value attribute on the object
        setattr(obj, key, value)
        return True

    def cast_file_data(self, data: RawJsonData, tvar: type[F]) -> F:
        """Cast raw file data (JSON/YAML) to a specific type with smart conversions.

        Args:
            data: Raw data from file (str, int, float, bool, list, dict, or None).
            tvar: The target type to cast to.
        Returns:
            Cast data of the target type.
        Raises:
            TypeError: If casting fails.
        """
        val = None
        # I. Edge Cases
        if isinstance(data, tvar):
            return data
        elif issubclass(type(data), tvar):
            val = data

        # II. Casting from atomics
        elif isinstance(data, Scalars):
            if self.is_vec_type(tvar):
                val = [data]
            elif self.is_map_type(tvar):
                val = {'content': data}

        # III. Catching mismatched collections
        elif self.is_map(data) and self.is_vec_type(tvar):
            _d = dict(data)
            if len(_d) == 1 and self.is_vec(first := mi.first(_d.values())):
                val = first
            else:
                val = [data]
        elif isinstance(data, list) and issubclass(tvar, Mapping):
            if len(data) == 1 and isinstance((first := mi.first(data)), Mapping):
                val = first
            else:
                val = {'content': data}

        if val is not None:
            return tvar(val)  # type: ignore

        # IV. Main case: coerce it dynamically
        if (ret := self.cast(data, MyType.parse(tvar))) is not None:
            return ret
        raise TypeError(f'Cannot cast file data of type `{type(data)}` to `{tvar}`.')

    # -------------------
    # `*4` TRANSFORMATION
    # -------------------
    @overload
    def serialize(
        self, data: Scalar, full: bool = False, cases: dict[CaseKey, CaseVal] | None = None
    ) -> Scalar: ...
    @overload
    def serialize(
        self, data: Atom, full: bool = False, cases: dict[CaseKey, CaseVal] | None = None
    ) -> str: ...
    @overload
    def serialize(
        self, data: Map | Model, full: bool = False, cases: dict[CaseKey, CaseVal] | None = None
    ) -> dict: ...
    @overload
    def serialize(
        self, data: Vec | Iter, full: bool = False, cases: dict[CaseKey, CaseVal] | None = None
    ) -> list: ...
    @overload
    def serialize(
        self, data: object, full: bool = False, cases: dict[CaseKey, CaseVal] | None = None
    ) -> object: ...
    def serialize(
        self, data: object, full: bool = False, cases: dict[CaseKey, CaseVal] | None = None
    ) -> Any:
        """Recursively simplify the given object into serialization-ready, standardized types.

        This method is undeniably an opinionated way of preparing data for export, but it should
        be easy enough to change or add some of these decisions using ``cases``.

        The following rules are applied:

        - All **enums** and **times** are converted to strings.
        - All other **atomics** are left as-is
        - All **series** are cast to lists.
        - All **maps** are cast to dicts.
        - All **models** are converted to dicts using their ``model_dump()`` method.

        Args:
            data: The source data to serialize. Passing more than one obviously creates a list.
            full: If True, include unset/default fields for pydantic models.
            cases: Optional special-case handlers, keyed by type or predicate, that trigger at
                all depths.
        """
        # 0. If the caller specified a special handler, call that instead
        for key, handler in (cases or {}).items():
            if (isinstance(key, type) and isinstance(data, key)) or (
                not isinstance(key, type) and key(data)
            ):
                return handler(data)

        # I. Cast special atomics to strings, and return others as-is
        if self.is_atom(data):
            if isinstance(data, Enum) or self.is_time(data):
                return self.cast(data, str)
            else:
                return data

        # II. Look for familiar functions on models, else treat them as dictionaries
        elif self.is_model(data):
            if (res := self.try_method(data, 'serialize')) and isinstance(res, (list, dict, Atoms)):
                # II.i. Shortcut to a model-specific `serialize()` function
                return res

            # II.ii. Rely on the model's serializers and treat the result as a dict
            if isinstance(data, pyd.BaseModel):
                data = data.model_dump(exclude_unset=full, exclude_defaults=full)  # type: ignore

        # III. Recurse into collections
        if self.is_struct(data):
            _recur = ft.partial(self.serialize, cases=cases, full=full)
            if self.is_map(data):
                return ut.val_map(_recur, data)
            else:
                # Plain `list(data)`, not `self.cast(data, list)` -- casting would normalize
                # each element (e.g. flattening a nested Model into pairs) before `_recur` gets
                # a chance to serialize it via its own `serialize()`/`model_dump()` logic.
                return list(map(_recur, data))

        return data

    def assemble[T: dict](
        self,
        base: T,
        *args: T,
        copy: bool = True,
        sort: bool = True,
        dups: bool = False,
    ) -> T:
        """Combine dictionaries, recursively merging nested structures wherever possible.

        Args:
            base: The base dictionary to merge into.
            *args: Additional dictionaries to merge in order.
            copy: If True, make a deep copy of the base before merging.
            sort: If True, sort lists after merging.
            dups: If False, remove duplicates from lists after merging.
        Return:
            Merged dictionary.
        """
        if base is None:
            base = {}  # type: ignore
        elif copy:
            base = deepcopy(base)

        # 0. Ensure that we have at least two dictionaries to merge
        _args = list(filter(bool, args))
        if not _args:
            return base
        other, *rest = _args

        # I. Partition fields on the second dict based on presence in the base
        _unique, _shared = ut.partition(other.items(), lambda item: item[0] in base)

        # II. Unique fields overwrite completely
        base |= dict(_unique)

        # III. Shared fields are recursively merged if possible, otherwise overwritten
        for key, new in _shared:
            old = base[key]
            tvar = MyType.typeof(old)
            if self.is_struct(old) and self.is_struct(new):
                res = self.cast(new, tvar)
                if res is None:
                    base[key] = new
                elif isinstance(old, dict):
                    self.assemble(old, res, copy=False)
                elif isinstance(old, set):
                    old.update(res)
                elif isinstance(old, list):
                    old.extend(res)
                    if not dups:
                        ut.drop_duplicates(old)
                    if sort:
                        old.sort()
                else:
                    base[key] = new
            else:
                base[key] = new

        # IV. Recursively merge other models into the result if present
        if rest:
            return self.assemble(base, *rest, copy=False)
        return base

    def distill(self, models: list[dict], exclude: set[str] | None = None) -> dict:
        """Recursively extract common fields from multiple models; the inverse of `assemble()`.

        Args:
            models: List of dictionaries to distill.
            exclude: Set of field names to exclude from distillation (used during recursion).
        Returns:
            Distilled dictionary of shared fields.
        """
        assert len(models) > 1, f'At least two models are required to distill, got {len(models)}.'

        base, *rest = models
        distillate: dict = {}
        for key in set(base.keys()):
            if (exclude and key in exclude) or not ut.all_has_all(rest, key):
                continue

            _type = type(base[key])
            restvals = [model[key] for model in rest]

            if set(map(type, filter(bool, restvals))) != {_type}:
                # I. Skip inconsistently-typed fields
                continue

            elif issubclass(_type, list | deque | set):
                # II. Handle series, removing the shared values
                if shared := set(filter(lambda item: ut.all_has_all(restvals, item), base[key])):
                    for model in models:
                        if model[key]:
                            model[key] = _type(it.filterfalse(shared.__contains__, model[key]))
                        if not model[key]:
                            del model[key]
                    distillate[key] = _type(sorted(set(distillate.get(key, [])) | shared))

            elif issubclass(_type, dict):
                # III. Recurse into maps
                if _ret := self.distill([base[key], *restvals], exclude=exclude):
                    distillate[key] = _ret
                    for model in models:
                        if not model[key]:
                            del model[key]

            elif issubclass(_type, Hashable) and set(restvals) == {base[key]}:
                # IV. Finally, handle atomic types by looking for a single shared value
                distillate[key] = base[key]
                for model in models:
                    del model[key]

        # V. If there's existing data, add it to the result before returning
        return distillate

    # ----------------
    # `*5` PERSISTENCE
    # ----------------
    # NOTE: The actual file I/O lives in `SystemUtils` (import-order constraints); these are thin
    # convenience wrappers so callers can reach it through the `typist` interface.
    @overload
    def from_file(self, file: FileParam) -> dict: ...
    @overload
    def from_file(self, file: FileParam, tvar: type[F], cast: bool = True) -> F: ...
    def from_file(self, file: FileParam, tvar: type = dict, cast: bool = True) -> Any:
        """Load & cast data from a local JSON/YAML/TOML/Pickle file. See ``ut.from_file()``."""
        return ut.from_file(file, tvar, cast)

    @overload
    def from_json(self, file: FileParam) -> dict: ...
    @overload
    def from_json(self, file: FileParam, tvar: type[F], cast: bool = True) -> F: ...
    def from_json(self, file: FileParam, tvar: type = dict, cast: bool = True) -> Any:
        """Load & cast data from a JSON file or string. See ``ut.from_json()``."""
        return ut.from_json(file, tvar, cast)

    @overload
    def from_yaml(self, file: FileParam) -> dict: ...
    @overload
    def from_yaml(self, file: FileParam, tvar: type[F], cast: bool = True) -> F: ...
    def from_yaml(self, file: FileParam, tvar: type = dict, cast: bool = True) -> Any:
        """Load & cast data from a YAML file or string. See ``ut.from_yaml()``."""
        return ut.from_yaml(file, tvar, cast)

    @overload
    def from_toml(self, file: FileParam) -> dict: ...
    @overload
    def from_toml(self, file: FileParam, tvar: type[F], cast: bool = True) -> F: ...
    def from_toml(self, file: FileParam, tvar: type = dict, cast: bool = True) -> Any:
        """Load & cast data from a TOML file or string. See ``ut.from_toml()``."""
        return ut.from_toml(file, tvar, cast)

    @overload
    def from_pickle(self, file: FileParam) -> dict: ...
    @overload
    def from_pickle(self, file: FileParam, tvar: type[F], cast: bool = True) -> F: ...
    def from_pickle(self, file: FileParam, tvar: type = dict, cast: bool = True) -> Any:
        """Load & cast data from a Pickle file or bytes. See ``ut.from_pickle()``."""
        return ut.from_pickle(file, tvar, cast)

    def to_file(self, data: Atom | Struct, file: str | File) -> None:
        """Save data to a local JSON/YAML/TOML/Pickle file. See ``ut.to_file()``."""
        return ut.to_file(data, file)

    def to_yaml(self, data: Atom | Struct, wrap: bool = False, **kwargs) -> str:
        """Serialize data to a YAML string. See ``ut.to_yaml()``."""
        return ut.to_yaml(data, wrap, **kwargs)

    def to_json(self, data: Atom | Struct, wrap: bool = False, **kwargs) -> str:
        """Serialize data to a JSON string. See ``ut.to_json()``."""
        return ut.to_json(data, wrap, **kwargs)

    def to_toml(self, data: Atom | Struct, wrap: bool = False, **kwargs) -> str:
        """Serialize data to a TOML string. See ``ut.to_toml()``."""
        return ut.to_toml(data, wrap, **kwargs)

    def to_pickle(self, data: Atom | Struct, **kwargs) -> bytes:
        """Serialize data to Pickle bytes. See ``ut.to_pickle()``."""
        return ut.to_pickle(data, **kwargs)

    # ---------------
    # `*6` INVOCATION
    # ---------------
    def get_str_method(self, obj: object, *extra_methods: str) -> Callable[..., str] | None:
        """Get a string conversion method from an object.

        Args:
            obj: The object to search for string methods.
            *extra_methods: Additional method names to check before standard ones.
        Returns:
            First found string conversion method, or None if none found.
        """
        return self.get_method(obj, *extra_methods, 'write', 'to_string', 'toString', '__str__')

    def get_method(self, obj: object, *methods: str) -> Callable | None:
        """Get the first available method from an object by name.

        Args:
            obj: The object to search for methods.
            *methods: Method names to search for in order.
        Returns:
            First found callable method, or None if none found.
        """
        for method in methods:
            if (fn := getattr(obj, method, None)) is not None and callable(fn):
                return fn
        return None

    @classmethod
    def invocable(
        cls, sig: Callable | inspect.Signature, *args: object, **kwargs: object
    ) -> inspect.BoundArguments | None:
        """Check if a function can be called with the given arguments.

        This method validates that the provided arguments can be bound to the function's
        signature and optionally performs type checking on the arguments.

        Args:
            sig: The function or signature to inspect.
            *args: Positional arguments to validate.
            **kwargs: Keyword arguments to validate.

        Returns:
            A tuple of (args, kwargs) that can be used to call the function if binding succeeds,
            or None if the function cannot be called with the given arguments.
        """
        # I. Coerce to signature if needed
        if not isinstance(sig, inspect.Signature):
            assert callable(sig), f'Invalid function provided: {sig}'
            try:
                sig = inspect.signature(sig)
            except (ValueError, TypeError):
                # Some builtins (`dict`, `int`, ...) have no introspectable signature -- Python
                # raises `ValueError: no signature found for builtin type`. "Can't read its
                # signature" means "can't validate a call to it": report not-invocable (None)
                # rather than letting the ValueError escape. `_object_to_model` relies on this to
                # decline builtin targets instead of crashing (the crash was formerly swallowed by
                # the cast loop's blanket suppress).
                return None

        # II. Attempt to bind the arguments to the signature
        binding = cls._attempt_binding(sig, args, kwargs)

        # III. Typecheck the proposed binding
        if binding and len(binding.arguments) > 0:
            for name, value in binding.arguments.items():
                param = sig.parameters[name]
                if (ann := param.annotation) is inspect.Parameter.empty:
                    continue
                if param.kind == param.VAR_POSITIONAL:
                    if not isinstance(value, tuple):
                        value = (value,)

                    for item in value:
                        if not cls.check(item, ann):
                            return None
                elif param.kind == param.VAR_KEYWORD:
                    assert isinstance(value, dict)
                    for item in value.values():
                        if not cls.check(item, ann):
                            return None
                else:
                    if not cls.check(value, ann):
                        return None

        return binding

    @classmethod
    def _attempt_binding(
        cls, sig: inspect.Signature, args: tuple, kwargs: dict
    ) -> inspect.BoundArguments | None:
        params = list(sig.parameters.values())

        # II.i. Naive attempt
        with ctx.suppress(TypeError):
            bound = sig.bind(*args, **kwargs)
            return bound

        # II.ii. Unpacked attempt
        if len(args) == 1:
            if any(map(cls._param_is_keyword, params)) and (items := ut.map_items(args[0])):
                kwargs = dict(items) | kwargs
            elif cls.is_vec(args[0]):
                args = tuple(args[0])  # type: ignore
            else:
                return None
            with ctx.suppress(TypeError):
                bound = sig.bind(*args, **kwargs)
                return bound

        # II.iii. Packed attempt
        if len(kwargs) > 0 and any(
            cls.is_map_type(param.annotation) for param in filter(cls._param_is_positional, params)
        ):
            with ctx.suppress(TypeError):
                bound = sig.bind(*args, kwargs)
                return bound
        return None

    @overload
    def upper_cast[V](
        self, data: object, tvar: type[V], flags: CastFlags | CastPreset | None = None
    ) -> V | None: ...

    @overload
    def upper_cast(
        self, data: object, tvar: Any, flags: CastFlags | CastPreset | None = None
    ) -> Any | None: ...

    def upper_cast[V](
        self, data: object, tvar: type[V] | Any, flags: CastFlags | CastPreset | None = None
    ) -> V | Any | None:
        """Attempt to cast/coerce the  data to the given type, returning None if unsuccessful.

        Args:
            data: The source data to cast.
            tvar: The target type to cast to.
            flags: An explicit ``CastFlags`` snapshot (or preset-level name); resolved once here so
                every option attempted below shares the same flag set. See ``TypeCast.cast``.
        """
        # I. Return null if the target is invalid
        if data is None or tvar in {None, Any}:
            return None
        target = MyType.parse(tvar)

        # II. Return the data as-is if it already matches the target type
        if self.check(data, target):
            return data

        # III. When given abstract classes, arbitrarily choose a concrete type
        if target.main is not None:
            target = Transform.concretize(target, data)

        # IV.i. Try to guess the most likely answers out of long unions
        options = self.sort_options(data, *target.args) if target.is_split else [target]

        # IV.ii. Perform the actual casting
        t0 = MyType.typeof(data)
        resolved = CastFlags.resolve(flags)
        return next(
            filter(bool, (self.cast(data, target=t1, source=t0, flags=resolved) for t1 in options)),
            None,
        )

    @overload
    @classmethod
    def invoke[V](cls, func: Callable[..., V], *args, _strict: Literal[True], **kwargs) -> V: ...

    @overload
    @classmethod
    def invoke[V](cls, func: Callable[..., V], *args, **kwargs) -> V | None: ...

    @classmethod
    def invoke[V](
        cls,
        func: Callable[..., V],
        *args,
        _strict: bool = False,
        **kwargs,
    ) -> V | None:
        """Attempt to call a function with the given arguments.

        This method first validates the arguments using invocable(), then calls the function
        if validation succeeds.

        Args:
            func: The function to call.
            *args: Positional arguments to pass to the function.
            _strict: If set, this method will raise a ValueError rather than returning None.
            **kwargs: Keyword arguments to pass to the function.

        Returns:
            A tuple of (success, result) where success is True if the call succeeded,
            and result is the return value of the function (or None if it failed).

        Raises:
            ValueError: If ``_strict`` is set and the function doesn't exist or couldn't be called.
        """
        # I. Check if the function can be called with the given arguments
        if not func:
            return None
        elif (bound := cls.invocable(func, *args, **kwargs)) is not None:
            try:
                # II. Unpack the validated arguments and call the function
                return func(*bound.args, **bound.kwargs)
            except Exception as e:
                # A failed invocation is a *declined* attempt, not an application error --
                # invoke() exists precisely to try a call and gracefully report `None` on
                # failure (see `_strict` for the one case where a caller wants an exception
                # instead). Cast candidates probe this speculatively (e.g. `_object_to_model`
                # trying `float(data)` on a non-numeric string while dispatching a date/time
                # cast) and are expected to fail routinely during normal, successful casts --
                # logging that at ERROR made every such probe look like a crash. See the
                # `decline-valve:` mechanism in `cast.py` for the analogous, cast-specific
                # signal used when a transform genuinely crashes rather than declines.
                name = getattr(func, '__name__', '[ANONYMOUS_FUNCTION]')
                cls.LOGGER.debug(
                    f'Failed to invoke {name} with args={bound.args}, kwargs={bound.kwargs}: {e}'
                )
        if _strict:
            raise ValueError(f'Cannot invoke function `{func}` with given arguments.')
        return None

    @overload
    def try_method[T](
        self,
        obj: object,
        methods: str | VecT[str],
        *args,
        _tvar: type[T],
        _strict: Literal[True],
        **kwargs,
    ) -> T: ...

    @overload
    def try_method(
        self,
        obj: object,
        methods: str | VecT[str],
        *args,
        _tvar: None = None,
        _strict: Literal[True],
        **kwargs,
    ) -> object: ...

    @overload
    def try_method[T](
        self,
        obj: object,
        methods: str | VecT[str],
        *args,
        _tvar: type[T],
        **kwargs,
    ) -> T | None: ...

    @overload
    def try_method(
        self, obj: object, methods: str | VecT[str], *args, **kwargs
    ) -> object | None: ...

    def try_method[T](
        self,
        obj: object,
        methods: str | VecT[str],
        *args,
        _tvar: type[T] | None = None,
        _strict: bool = False,
        **kwargs,
    ) -> T | object | None:
        """A thin wrapper that calls `get_method()`, then `invoke()` if successful."""
        if isinstance(methods, str):
            methods = (methods,)

        if fn := self.get_method(obj, *methods):
            ret = self.invoke(fn, *args, _strict=_strict, **kwargs)
            if ret is None:
                if _strict:
                    raise ValueError(f'typist.invoke({fn}) returned None unexpectedly.')
            elif _tvar is None:
                return ret
            else:
                if isinstance(_tvar, type) and isinstance(ret, _tvar):
                    # Already the right type -- casting it again would re-normalize a structured
                    # instance (e.g. a Model) into an intermediate list-of-pairs/dict form, which
                    # is a lossy round-trip at best and, for a Model target, an infinite bounce
                    # back through `_object_to_model` -> here at worst.
                    return ret
                elif _cast := self.cast(ret, _tvar):
                    return _cast
                elif _strict:
                    raise ValueError(f'{fn} returned `{type(ret)}`, cannot cast to `{_tvar}`.')
        elif _strict:
            raise ValueError(f'No method found on {type(obj)} w/ name in list {methods}.')
        return None


ty = typist = Typist.inst()
ut.set_typist(ty)
