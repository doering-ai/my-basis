############
### HEAD ###
############
### STANDARD
from __future__ import annotations
from typing import Any, Set, Literal, TypeVar, Protocol, Generic, ClassVar, overload
from typing_extensions import TypeAlias
from collections import defaultdict
from collections.abc import Callable, Hashable, MutableSequence, MutableMapping
import functools as ft
from datetime import datetime

### EXTERNAL
import pydantic as pyd
import sublime as sb
import regex as re

### INTERNAL


class BaseProtocol(Protocol):
    """A base protocol that all classes using `ViewProperties` must follow."""

    _cache: 'ViewProperties'
    view: sb.View


C = TypeVar('C', bound=BaseProtocol)
R = TypeVar('R', bound=object)
Method: TypeAlias = 'Callable[[C], R]'
Decorator: TypeAlias = 'Callable[[Callable[[C], R]], property]'


############
### BODY ###
############
class ViewProperties(pyd.BaseModel, Generic[C]):
    """Stores metadata for invalidating cached properties."""

    DEBUG: ClassVar[bool] = False

    view_id: int = 0

    #: The change count at which the property was last calculated (if it has been).
    counts: dict[str, int] = defaultdict(lambda: -1)
    #: The hash of the source content used to calculate the property (if applicable).
    hashes: dict[str, int] = defaultdict(lambda: -1)
    #: The cached value of the property (if it exists).
    values: dict[str, Any] = defaultdict(lambda: None)

    #: The functions used to calculate the properties.
    methods: dict[str, Callable[[C], Any]] = {}
    #: A function that produces a hashable value representing properties' source content.
    hash_fns: dict[str, Callable[[C], Hashable]] = {}
    #: A list of other properties that the key property is derived from.
    dependencies: dict[str, list[str]] = defaultdict(list)
    #: Properties that depend on sub-edit changes (namely, to cursor/selection state).
    eager_methods: Set[str] = set()

    def __contains__(self, name: str) -> bool:
        return name in self.counts or name in self.values

    @staticmethod
    def _hash_scope_executor(view: sb.View, *scopes: str) -> int:
        return hash(
            tuple(
                (*region.to_tuple(), hash(view.substr(region)))
                for scope in scopes
                if (regions := view.find_by_selector(scope))
                for region in regions
            )
        )

    def register(
        self,
        view_id: int,
        name: str,
        method: Callable[[C], Any],
        hash_fn: Callable[[C], Hashable] | None = None,
        dependencies: list[str] | None = None,
        eager: bool = False,
    ) -> None:
        """Register a hash function to be used for a given property."""
        if self.view_id != view_id:
            if self.view_id > 0:
                self.counts.clear()
                self.hashes.clear()
                self.values.clear()
            self.view_id = view_id

        if name not in self.methods:
            self.methods[name] = method
            if hash_fn:
                self.hash_fns[name] = hash_fn
            if dependencies:
                self.dependencies[name] = dependencies

            if eager:
                self.eager_methods.add(name)

    def _changed_since(self, name: str, now: int, last: int) -> bool:
        return name in self.eager_methods or now > last or last == -1

    def _log(
        self,
        name: str,
        *args: Any,
        sep: str = ' ',
        time: bool = True,
        indent: int = 0,
        rjust: bool = False,
        **kwargs,
    ) -> None:
        if self.DEBUG:
            parts = [f'[_cache.{name}]'.ljust(32), *map(str, args)]
            if time:
                parts.insert(0, datetime.now().strftime('%H:%M:%S.%f')[:-3])
            ret = sep.join(parts)
            if rjust:
                lines = ret.splitlines()
                ret = '\n'.join(line.rjust(128 - indent) for line in lines)
            elif indent > 0:
                ret = re.sub(r'(?m)^(?!$)', ' ' * indent, ret)
            print(ret, **kwargs)

    def should_rerun(self, inst: C, name: str, now: int, d: int = 0) -> bool:
        """Determines whether the identified property should be recalculated."""
        _log = ft.partial(self._log, name, time=True, indent=d * 4)
        # By default, rerun on every change to the file
        if self._changed_since(name, now, last := self.counts[name]):
            # Properties with dependencies only change when they have
            if name in self.dependencies:
                if not any(
                    (
                        self._changed_since(dep, self.counts[dep], last)
                        or self.should_rerun(inst, dep, now, d + 1)
                    )
                    for dep in self.dependencies[name]
                ):
                    _log('🟦 (no dependencies changed)', f'[{last}/{now}]')
                    return False

            # Hashed properties only rerun when the source content changes
            if name in self.hash_fns:
                if (_hash := hash(self.hash_fns[name](inst))) and _hash == self.hashes[name]:
                    _log('🟦 (hash match)', f'[{self.hashes[name]}]')
                    return False
                else:
                    if _hash and d == 0:
                        # _log(f'Updating hash to {_hash}.')
                        self.hashes[name] = _hash

            # Do the actual work and update the count for next time
            _log('🟨', f'[{last}/{now}]')
            return True
        else:
            _log('🟦', f'[{last}/{now}]')
            return False

    def invalidate(self, *names: str) -> None:
        """Invalidate the identified properties, causing them to be recalculated on next access."""
        for name in names:
            self._log(name, 'Invalidating.')
            if name in self.counts:
                self.counts[name] = -1
            if name in self.hashes:
                self.hashes[name] = -1

    def revalidate(
        self,
        name: str,
        count: int | None = None,
        _hash: int | None = None,
        value: Any | None = None,
    ) -> None:
        """Manually update a cached property, bypassing the normal caching mechanism."""
        self._log(
            name,
            f'Revalidating -- count={bool(count)}, hash={bool(_hash)}, value={value is not None}.',
        )
        if count is not None:
            self.counts[name] = count
        if _hash is not None:
            self.hashes[name] = _hash
        if value is not None:
            self.set_value(name, value)

    def set_value(self, name: str, value: R, mutate: bool = True) -> R:
        """Manually set the cached value of a property without changing its count or hash."""
        if (
            mutate
            and isinstance(value, (MutableSequence, MutableMapping))
            and type(value) is type(self.values[name])
        ):
            if isinstance(self.values[name], MutableSequence):
                self.values[name].clear()
                self.values[name].extend(value)
            elif isinstance(self.values[name], MutableMapping):
                self.values[name].clear()
                self.values[name].update(value)
        else:
            self.values[name] = value
        return value


@overload
def view_property(method: Method) -> property: ...


@overload
def view_property(
    *,
    scopes: tuple[str] | None = None,
    dependencies: list[str] | tuple[str] | set[str] | None = None,
) -> Decorator: ...


@overload
def view_property(
    *,
    hash_fn: Callable[[C], Hashable],
    dependencies: list[str] | tuple[str] | set[str] | None = None,
) -> Decorator: ...


@overload
def view_property(*, hash_by_syntax: Literal[True]) -> Decorator: ...


@overload
def view_property(*, hash_by_cursor: Literal[True]) -> Decorator: ...


def view_property(
    method: Method | None = None,
    *,
    scopes: tuple[str] | None = None,
    hash_fn: Callable[[C], Hashable] | None = None,
    hash_by_syntax: bool = False,
    hash_by_cursor: bool = False,
    dependencies: list[str] | tuple[str] | set[str] | None = None,
) -> property | Decorator:
    """Wrap a method with one or more simple caching mechanisms."""
    if method is not None:
        return _decorator_factory(method)

    assert sum(map(bool, (scopes, hash_fn, hash_by_syntax))) <= 1, (
        'Cannot specify more than one hash method at once.'
    )

    # I. Setup the cache property once during class creation, normalizing arguments
    eager = False
    if scopes:
        hash_fn = lambda self: ViewProperties._hash_scope_executor(self.view, *scopes)
    elif hash_by_syntax:
        hash_fn = lambda self: self.view.syntax()
    elif hash_by_cursor:
        hash_fn = lambda self: tuple(sel.to_tuple() for sel in self.view.selection)
        eager = True

    if dependencies is not None:
        dependencies = list(dependencies)

    # II. Return the decorator, which will have access to the actual cache instance
    return ft.partial(_decorator_factory, hash_fn=hash_fn, dependencies=dependencies, eager=eager)


def _decorator_factory(
    method: Method,
    hash_fn: Callable[[C], Hashable] | None = None,
    dependencies: list[str] | None = None,
    eager: bool = False,
) -> property:
    name = method.__name__
    assert name, 'Cannot cache unnamed function -- tried to pass a lambda, perhaps?'

    @ft.wraps(method)
    def _wrapper(self: C) -> R:  # pyright: ignore[reportInvalidTypeVarUse]
        """The new version of the passed method."""
        # III.i. Register the method and its hash function with the cache on first access
        if not hasattr(self, '_cache'):
            self._cache = ViewProperties()
        cache = self._cache
        cache.register(self.view.id(), name, method, hash_fn, dependencies, eager)

        # III.ii. Check if the method needs to be rerun; if so, do it and update the cache
        if cache.should_rerun(self, name, now := self.view.change_count()):
            cache.counts[name] = now
            cache.set_value(name, method(self))

        return cache.values[name]

    return property(_wrapper)  # pyrefly: ignore[bad-return]  # generic descriptor; property() is a property at runtime
