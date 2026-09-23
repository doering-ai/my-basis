"""A singleton, registry-backed tee writer for stdout/stderr.

Ported from mySublimeBasis's `infra/Multiplex.py` (LIBS-62): pure stdlib, zero Sublime
dependency, so it moves upstream unchanged. `Multiplex` lets several independent consumers
(a log file, an output panel, a test harness, ...) each register a stream and receive every
byte written to `sys.stdout`/`sys.stderr`, without stepping on each other or on the real
console.
"""

############
### HEAD ###
############
### STANDARD
from __future__ import annotations
from typing import TextIO, Protocol, NamedTuple, Literal, ClassVar
from typing import Self
from collections.abc import Iterator
from enum import Enum, auto
from io import StringIO
import functools as ft
import sys

### EXTERNAL

### INTERNAL


############
### DATA ###
############
class _IOProtocol(Protocol):
    """Protocol for file-like IO objects."""

    def write(self, text: str, /) -> int: ...
    def flush(self) -> None: ...
    def close(self) -> None: ...
    def isatty(self) -> bool: ...
    def readable(self) -> bool: ...
    def writable(self) -> bool: ...
    @property
    def closed(self) -> bool: ...


@ft.total_ordering
class _Mode(Enum):
    """The relation of each stream to STDOUT."""

    #: Does not have any direct relation to STDOUT
    PASSIVE = auto()

    #: Intercepts messages to STDOUT before passing them along.
    #: If any consuming streams are active, these streams are made temporarily inactive.
    WRAPPER = auto()

    #: Intercepts messages to STDOUT without passing them along
    CONSUME = auto()

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, _Mode):
            return False
        return self.value < other.value


class _Stream(NamedTuple):
    name: str
    mode: _Mode
    root: _IOProtocol


############
### BODY ###
############
class Multiplex(StringIO):
    """A simple wrapper around StringIO that allows us to intercept writes and flushes."""

    _INST: ClassVar[Self | None] = None

    _streams: dict[str, _Stream]
    _stdout: TextIO
    _stderr: TextIO

    # -------------------
    # `.` Initial Methods
    # -------------------
    def __init__(self, *args, **kwargs):
        """Initialize the wrapper."""
        super().__init__(*args, **kwargs)
        self._streams = {}

        self._stdout = self.unwrap_stdout(sys.stdout)
        self._stderr = self.unwrap_stderr(sys.stderr)
        sys.stdout = self._stdout
        sys.stderr = self._stderr

    @classmethod
    def inst(cls) -> Self:
        """Implement the singleton pattern, creating or fetching one global object."""
        if cls._INST is None:
            cls._INST = cls()
        return cls._INST

    # -------------------
    # `-` Private Methods
    # -------------------
    def consume_stdout(self) -> bool:
        """Whether to prevent stdout input from flowing to base Sublime/system stdout."""
        return any(stream.mode == _Mode.CONSUME for stream in self._streams.values())

    def wrap_stdout(self) -> None:
        """Replace STDOUT with this instance, allowing it to intercept writes and flushes."""
        if sys.stdout is not self:
            sys.stdout = self
        if sys.stderr is not self:
            sys.stderr = self

    def unwrap_stdout(self, val: TextIO) -> TextIO:
        """Ensure that stdout isn't set to some old instance of this class."""
        ret = val
        while type(ret).__name__ == 'Multiplex':
            ret = ret._stdout  # type: ignore
        return ret

    def unwrap_stderr(self, val: TextIO) -> TextIO:
        """Ensure that stdout isn't set to some old instance of this class."""
        ret = val
        while type(ret).__name__ == 'Multiplex':
            ret = ret._stderr  # type: ignore
        return ret

    @property
    def _active_streams(self) -> Iterator[_IOProtocol]:
        consume = self.consume_stdout()
        if not consume:
            yield self._stdout

        for stream in self._streams.values():
            if stream.mode != _Mode.WRAPPER or not consume:
                yield stream.root

    def _print_streams(self) -> None:
        self.debug(
            '\n'.join(
                [
                    '\tSTREAMS:',
                    *[
                        f'\t\t<{s.mode.name} name={s.name}, root={type(s.root).__name__}>'
                        for s in self._streams.values()
                    ],
                ]
            )
        )

    def debug(self, msg: str) -> None:
        """Print a debug message straight to stdout."""
        self._stdout.write(f'{msg}\n')

    @classmethod
    def _debug(cls, msg: str) -> None:
        cls.inst().debug(msg)

    # -------------------
    # `+` Primary Methods
    # -------------------
    def write(self, text: str) -> int:
        """Write text to the stream."""
        for stream in self._active_streams:
            stream.write(text)
        return len(text)

    def flush(self) -> None:
        """Flush the stream."""
        for stream in self._active_streams:
            stream.flush()

    def close(self) -> None:
        """Close the stream."""
        self.debug(f'Multiplex.close({len(self._streams)})')
        for stream in self._streams.values():
            stream.root.close()
        self._streams.clear()

        sys.stdout = self.unwrap_stdout(self._stdout)
        sys.stderr = self.unwrap_stderr(self._stderr)

    # ------------------
    # `*` Public Methods
    # ------------------
    @classmethod
    def has(cls, name: str) -> bool:
        """Return whether the specified stream is in the registry."""
        return name in cls.inst()._streams

    @classmethod
    def get(cls, name: str) -> _IOProtocol | None:
        """Get the root stream for the specified name if present."""
        if stream := cls.inst()._streams.get(name, None):
            return stream.root
        return None

    @classmethod
    def add(
        cls,
        name: str,
        stream: _IOProtocol,
        mode: _Mode | Literal['PASSIVE', 'WRAPPER', 'CONSUME'] = _Mode.PASSIVE,
    ) -> Self:
        """Add the specified stream to the registry if not already present.

        If this is the first active stream, STDOUT will be replaced with the multiplexer as the
        default stream.
        """
        if isinstance(mode, str):
            mode = _Mode[mode]

        self = cls.inst()
        if name not in self._streams:
            self._streams[name] = _Stream(name=name, mode=mode, root=stream)
            if len(self._streams) == 1:
                self.wrap_stdout()

        return self

    @classmethod
    def remove(cls, name: str) -> Self:
        """Remove the specified stream from the registry if present.

        If this was the last active stream, STDOUT will be restored as the default stream.
        """
        self = cls.inst()
        if name in self._streams:
            self._streams.pop(name, None)

        if len(self._streams) == 0:
            sys.stdout = self.unwrap_stdout(self._stdout)
            sys.stderr = self.unwrap_stderr(self._stderr)

        return self
