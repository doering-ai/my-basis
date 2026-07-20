r"""Technical Overview of the `my-basis` python package.

### Subpackage Dependency Tree

When adding new relative imports to any of the modules in this package, make sure to either respect
or update this structure (in order to prevent circular dependencies).

- `infra` imports nothing -- it's the package's foundational layer.
  - `utils` imports `infra`.
    - `caches` imports `utils`.
      - `typing` imports `infra`, `utils`, and `caches`.
        - `types` imports `infra`, `utils`, and `typing`.
          - `regex` imports `infra`, `utils`, `types`, and `typing`.
            - `apis` imports `infra`, `utils`, `types`, `regex`, and `typing`.
            - `files` imports `infra`, `utils`, `typing`, `types`, and `regex`.

`data` and `scripts` sit outside this relative-import graph. `data` holds no Python code -- it's a
resource-only namespace (YAML, Jinja templates) that `infra` reads via `importlib.resources`, not a
relative import. `scripts` are entry points that consume the finished public API through absolute
`from my import ...` statements rather than the relative imports tracked above, so nothing in the
tree depends on them.

### Contributing

I created this project over the course of 2025 for my own use, so it's definitely 'opinionated', for
better or worse. Specifically, it is influenced by:

- a weathered respect for polymorphism,
- an addiction to "ergonomic" code\*\*, and
- a reliance on symbolic (deterministic!) devtools, namely heavy use of typing, even at runtime.

If you're interested in contributing the project, simply get in touch, open an issue, or open a PR!

Note:
    __\*\*:__ This buzzword implies some trite promises--namely that the code is concise,
    clear, and/or generally satisfying--but I intend it with a bit more sincerity & specificity.

    In my usage, it is code that conforms to the design standards set out by the physical and
    interface design academies(/industries), especially the work of Don Norman.
    The most relevant are Consistency, Simplicity, Mapping, Visibility, Constraints, and Feedback.
```
"""

from typing import TYPE_CHECKING
import importlib

from .infra.types import (
    FuncT,
    MapT,
    VecT,
    StructT,
    Atom,
    Atoms,
    Stream,
    Streams,
    Func,
    Funcs,
    Map,
    Maps,
    Model,
    Real,
    Reals,
    Scalar,
    Scalars,
    Struct,
    Structs,
    String,
    Strings,
    Time,
    Times,
    Vec,
    Vecs,
)
from .utils import (
    Utils,
    ut,
    utils,
    IterUtils,
    iter_utils,
    TextUtils,
    text_utils,
    SystemUtils,
    system_utils,
    SemanticUtils,
    semantic_utils,
    SyntaxUtils,
    syntax_utils,
    MetricUtils,
    metric_utils,
)
from .caches import Cache, NestedCache, PickleCache, FileCache
from .typing import (
    AutocastModel,
    CastFlags,
    MyType,
    ty,
    tyc,
    tym,
    TypeArg,
    TypeCast,
    TypeCheck,
    TypeMatch,
    Typist,
    typist,
    tyt,
)
from .types import MyEnum, UniqueId, Uid, Span, Buffer, Predicate, Command, Platform
from .regex import (
    RegexStore,
    RegexDebugger,
    GroupKind,
    RgxAtom,
    GroupAtom,
    SetAtom,
    Regex,
    Tree,
    Quantifier,
    MatchData,
    ParseData,
    RegexParser,
    RegexTup,
    RegexList,
    RegexVal,
    RegexDef,
    META_RGXS,
    COMMON_RGXS,
)

# -- Lazy facade leaves (PEP 562) --------------------------------------------
# `apis` and `files` are the only *leaf* subpackages -- nothing else under `my/`
# imports them -- so they are deferred to first attribute access via `__getattr__`
# below. This keeps every `import my` that never touches them from paying their
# import cost, and from triggering `apis`'s import-time side effects (`load_dotenv`,
# the `os.environ` snapshot, filesystem path resolution). Type checkers and
# autocomplete still see the names through this `TYPE_CHECKING` block.
#
# Honest limits (do not "fix" by making these eager again): `from my import env`
# still pays the full `apis` import cost at *that* import, and `from my import *`
# or `hasattr(my, 'env')` force every lazy name to load. The win is for the many
# consumers that import only eager names (`ut`, `ty`, `Buffer`, ...).
if TYPE_CHECKING:
    from .apis import GoogleSheet, Environment, ENV, env, Filesystem, PATHS, FS, fs
    from .files import Markdown


__all__ = [
    # /infra/
    'FuncT',
    'MapT',
    'VecT',
    'StructT',
    'Atom',
    'Atoms',
    'Stream',
    'Streams',
    'Func',
    'Funcs',
    'Map',
    'Maps',
    'Model',
    'Real',
    'Reals',
    'Scalar',
    'Scalars',
    'Struct',
    'Structs',
    'String',
    'Strings',
    'Time',
    'Times',
    'Vec',
    'Vecs',
    # /utils/
    'iter_utils',
    'IterUtils',
    'metric_utils',
    'MetricUtils',
    'semantic_utils',
    'SemanticUtils',
    'syntax_utils',
    'SyntaxUtils',
    'system_utils',
    'SystemUtils',
    'text_utils',
    'TextUtils',
    'ut',
    'Utils',
    'utils',
    # /caches/
    'Cache',
    'FileCache',
    'NestedCache',
    'PickleCache',
    # /apis/
    'ENV',
    'env',
    'Environment',
    'Filesystem',
    'FS',
    'fs',
    'GoogleSheet',
    'PATHS',
    # /typing/
    'AutocastModel',
    'CastFlags',
    'MyType',
    'ty',
    'tyc',
    'tym',
    'TypeArg',
    'TypeCast',
    'TypeCheck',
    'TypeMatch',
    'Typist',
    'typist',
    'tyt',
    # /types/
    'Buffer',
    'Command',
    'MyEnum',
    'Platform',
    'Predicate',
    'Span',
    'Uid',
    'UniqueId',
    # /regex/
    'RegexStore',
    'RegexDebugger',
    'GroupKind',
    'RgxAtom',
    'GroupAtom',
    'SetAtom',
    'Regex',
    'Tree',
    'Quantifier',
    'MatchData',
    'ParseData',
    'RegexParser',
    'RegexTup',
    'RegexList',
    'RegexVal',
    'RegexDef',
    'META_RGXS',
    'COMMON_RGXS',
    # /files/
    'Markdown',
]


#: Facade names deferred to first access, mapped to the submodule that defines each.
_LAZY_ATTRS: dict[str, str] = {
    'GoogleSheet': 'my.apis',
    'Environment': 'my.apis',
    'ENV': 'my.apis',
    'env': 'my.apis',
    'Filesystem': 'my.apis',
    'PATHS': 'my.apis',
    'FS': 'my.apis',
    'fs': 'my.apis',
    'Markdown': 'my.files',
}


def __getattr__(name: str) -> object:
    """Lazily resolve the `apis`/`files` facade leaves on first access (PEP 562).

    Resolved values are cached back into the module globals, so subsequent attribute
    access skips this hook entirely.
    """
    module = _LAZY_ATTRS.get(name)
    if module is None:
        raise AttributeError(f'module {__name__!r} has no attribute {name!r}')
    value = getattr(importlib.import_module(module), name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(__all__)
