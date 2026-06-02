r"""Technical Overview of the `my-basis` python package.

### Subpackage Dependency Tree

When adding new relative imports to any of the modules in this package, make sure to either respect
or update this structure (in order to prevent circular dependencies).

- `utils` imports nothing.
  - `caches` imports `utils`
    - `typing` imports `utils` and `caches`
      - `types` imports `utils` and `typing`
        - `apis` imports `utils` and `types`
        - `regex` imports `utils` and `types`
          - `files` imports `utils`, `typing`, `types`, and `regex`

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

from .infra.types import (
    _Func,
    _Map,
    _Vec,
    _Struct,
    Atom,
    Atoms,
    Stream,
    Streams,
    Func,
    Funcs,
    Map,
    Maps,
    Model,
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
)
from .caches import Cache, NestedCache, PickleCache, FileCache
from .typing import MyType, Typist, typist, TypeArg, AutocastModel
from .types import MyEnum, UniqueId, Uid, Span, Buffer, Predicate, Command, Platform
from .apis import GoogleSheet, Environment, ENV, env, Filesystem, PATHS, FS, fs
from .regex import (
    RegexStore,
    RegexDebugger,
    GroupKind,
    Atom as RegexAtom,
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
from .files import Markdown


__all__ = [
    # /infra/
    '_Func',
    '_Map',
    '_Vec',
    '_Struct',
    'Atom',
    'Atoms',
    'Stream',
    'Streams',
    'Func',
    'Funcs',
    'Map',
    'Maps',
    'Model',
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
    'GoogleSheet',
    'Environment',
    'ENV',
    'env',
    'Filesystem',
    'PATHS',
    'FS',
    'fs',
    # /typing/
    'TypeArg',
    'MyType',
    'Typist',
    'typist',
    'AutocastModel',
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
    'RegexAtom',
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
