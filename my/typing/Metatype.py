############
### HEAD ###
############
### STANDARD
from __future__ import annotations
from typing import get_origin
from enum import Enum
import functools as ft

### EXTERNAL

### INTERNAL


############
### BODY ###
############
class Metatype(Enum):
    """A name-based classifier for the type annotations that aren't ordinary `type` instances.

    Each member holds a `frozenset` of the *names* (i.e. `__name__`) of the special forms it
    covers, so that `Metatype(value)` can categorize any annotation by looking up its name. Ordinary
    types (e.g. `int`, `list`, `dict`) belong to no special form and resolve to the falsy `NULL`.
    """

    #: Unrecognized / ordinary types -- the falsy fallback.
    NULL = frozenset()

    #: Forms that always match (e.g. `Any`).
    ALWAYS = frozenset({'Any', 'Unknown'})

    #: Forms that are treated as unmatchable or are not yet handled.
    #: NOTE: `TypeVar`/`TypeVarTuple`/`ParamSpec` (and its `.args`/`.kwargs` accessors) are
    #: deliberately absent here -- each per-declaration instance reports its own parameter name
    #: (e.g. `'T'`) as `__name__`, not the special form's name, so they can never be matched by
    #: name. `MyType._process_root` detects them via `isinstance` instead.
    NEVER = frozenset(
        {
            '',
            'None',
            'NoneType',
            'CapsuleType',
            'Concatenate',
            'LiteralString',
            'Never',
            'NewType',
            'NoReturn',
            'NotImplementedType',
            'Protocol',
            'ReadOnly',
            'Self',
            'Type',
            # Conditionals (resolve to bool, but unhandled at parse time)
            'TypeGuard',
            'TypeIs',
            # Callables (unhandled as annotations)
            'Callable',
            'Coroutine',
            # Iterator-likes (unhandled as annotations)
            'AsyncGenerator',
            'AsyncIterable',
            'AsyncIterator',
            'Generator',
            'Iterator',
            'TypedDict',
            'NamedTuple',
        }
    )

    #: Simple wrapper forms that unwrap to a single inner type (e.g. `Annotated[int, ...]`).
    MONO = frozenset(
        {
            'Annotated',
            'ClassVar',
            'Final',
            'NotRequired',
            'Required',
            'Unpack',
        }
    )

    #: Forms that wrap more than one type at once (i.e. unions).
    POLY = frozenset({'Union', 'Optional', 'UnionType'})

    #: Fundamental stdlib forms from the `types` module.
    TYPE = frozenset({'Ellipsis', 'ellipsis', 'EllipsisType', 'TypeAlias', 'TypeAliasType'})

    #: The `Literal[...]` form, handled specially during parsing.
    LITERAL = frozenset({'Literal'})

    # -------------------
    # `.` Initial Methods
    # -------------------
    @classmethod
    def _missing_(cls, value: object) -> Metatype:
        """Categorize an arbitrary annotation by its (form) name."""
        name = cls._name(value)
        return next((member for member in cls if name and name in member.value), cls.NULL)

    # -------------------
    # `-` Private Methods
    # -------------------
    @staticmethod
    @ft.lru_cache(maxsize=2**12)
    def _name(value: object) -> str:
        """Best-effort extraction of the canonical name of a type or special form."""
        if value is None:
            return 'None'
        if isinstance(value, str):
            return value
        name = getattr(value, '__name__', None) or getattr(value, '_name', None)
        if not name:
            origin = get_origin(value)
            if origin is not None and origin is not value:
                return Metatype._name(origin)
            # Fallback: the last dotted component of the repr, sans any subscripts.
            name = str(value).split('[', 1)[0].rsplit('.', 1)[-1]
        return str(name)

    # ------------------
    # `*` Public Methods
    # ------------------
    @property
    def val(self) -> frozenset[str]:
        """The set of names associated with this metatype."""
        return self.value

    def __bool__(self) -> bool:
        """Whether this metatype is a recognized special form (i.e. not `NULL`)."""
        return self is not Metatype.NULL

    def __contains__(self, value: object) -> bool:
        """Whether the given annotation is categorized as this metatype."""
        return Metatype._name(value) in self.value


_M = Metatype
