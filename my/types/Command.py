############
### HEAD ###
############
### STANDARD
from typing import Any, Self, NamedTuple
from pathlib import Path
import asyncio as aio
import subprocess as sbp

### EXTERNAL
import pydantic as pyd
import more_itertools as mi

### INTERNAL
from ..infra.types import Vec


############
### DATA ###
############
_SAFE = frozenset('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789@%_-+=:,./')


def _shell_quote(s: str) -> str:
    """Quote a string for shell embedding using double quotes when necessary."""
    if not s or all(c in _SAFE for c in s):
        return s
    return '"' + s.replace('"', '\\"') + '"'


############
### BODY ###
############
class Command(pyd.BaseModel):
    """A builder for easily & durably issuing shell commands, async or otherwise.

    Positional arguments are handled separately from keyword arguments, which are converted to
    flags (e.g., `--key value` or `-k`). The class handles quoting, underscore-to-dash conversion
    in flag names, and various shell conventions.

    Commands can be manually finalized w/ `assemble()`, or executed directly via `execute()` /
    `execute_async()`. To chain commands together, use the provided `out` and `pipe` options.

    Examples:
        Build a command, inspect it, and execute it::

            >>> from my import Command
            >>> cmd = Command.new('ls', '-l', color='auto')
            >>> str(cmd)
            'ls --color auto -l'
            >>> Command.run('echo', 'hello')
            Result(code=0, out='hello', err='')

        Pipe one command into another::

            >>> piped = Command.new('echo', 'one two', options={'pipe': Command.new('wc', '-w')})
            >>> str(piped)
            'echo "one two" | wc -w'
            >>> piped.execute()
            Result(code=0, out='2', err='')
    """

    model_config = pyd.ConfigDict()

    class Options(pyd.BaseModel):
        """Configuration options for command assembly."""

        verbose: bool = False  #: Print the assembled command before execution.

        preserve_underscores: bool = False  #: Underscores in flag names are not changed to hyphens.
        single_dashes: bool = False  #: Use single dashes for all flags.
        named_args_last: bool = False  #: Positional arguments are placed after named arguments.
        flag_assignment: bool = False  #: Use "=" to connect flags to their values.
        always_quote: bool = False  #: Always quote argument values, even if not strictly necessary.

        cwd: str | None = None  #: Working directory for command execution.
        out: str | None = None  #: Redirect command output to a file. Not compatible w/ `pipe`.
        pipe: 'Command | None' = None  #: Pipe command output to another command.

    class Result(NamedTuple):
        """Structured result of command execution."""

        code: int  #: The process's return code (0 on success).
        out: str  #: The captured, stripped stdout text.
        err: str  #: The captured, stripped stderr text.

    command: str  #: Base command name.
    args: list[Any] = []  #: Positional arguments.
    kwargs: dict[str, Any] = {}  #: Keyword arguments (converted to flags).
    options: Options = pyd.Field(default_factory=Options)  #: Assembly options.

    # -------------------
    # `.` Initial Methods
    # -------------------
    @pyd.model_validator(mode='after')
    def _validate_command(self) -> Self:
        assert self.options.out is None or self.options.pipe is None, (
            'Cannot define both output and pipe at once.'
        )
        return self

    @classmethod
    def new(
        cls,
        command: str,
        *args: str,
        options: dict | Options | None = None,
        **kwargs: Any,
    ) -> Self:
        """Create a new command instance.

        Args:
            command: Base command string -- ostensibly but NOT necessarily a name.
            args: Positional arguments to the command.
            options: Assembly option flags.
            **kwargs: Keyword arguments to the command.
        Returns:
            Configured Command instance.
        Examples:
            Configure assembly via an `Options` dict::

                >>> from my import Command
                >>> opts = {'flag_assignment': True}
                >>> str(Command.new('grep', 'TODO', options=opts, max_count=3))
                'grep --max-count=3 TODO'
        """
        if options is None:
            options = cls.Options()
        elif isinstance(options, dict):
            if (pipe := options.get('pipe', None)) and not isinstance(pipe, Command):
                if isinstance(pipe, dict):
                    options['pipe'] = cls.new(**pipe)
                elif isinstance(pipe, Vec):
                    options['pipe'] = cls.new(*map(str, pipe))
                else:
                    options['pipe'] = cls.new(str(pipe))
            options = cls.Options(**options)

        return cls(command=command, args=list(args), kwargs=kwargs, options=options)

    # -------------------
    # `-` Private Methods
    # -------------------
    @property
    def positional_args(self) -> list[str]:
        """Convert positional arguments to shell-safe values.

        Returns:
            String representations with appropriate quoting.
        """
        return [_shell_quote(str(a)) for a in self.args]

    @property
    def named_args(self) -> list[str]:
        """Convert keyword arguments to shell-safe flags.

        Returns:
            Formatted command-line flags (e.g., `--key value`, `-k`).
        """
        ret = []
        for key, val in self.kwargs.items():
            # I.i. Format python identifiers for the command line (e.g. my_arg -> my-arg)
            if not self.options.preserve_underscores and '_' in key:
                key = key.replace('_', '-')
            # I.ii. Determine single vs double dash prefix
            key = ('-' if self.options.single_dashes or len(key) == 1 else '--') + key

            # II. Write plain arg if it's an atomic type, otherwise wrap in quotes

            if isinstance(val, bool) and val:
                ret.append(key)
            else:
                quoted = _shell_quote(str(val))
                if self.options.flag_assignment:
                    ret.append(f'{key}={quoted}')
                else:
                    ret.append(f'{key} {quoted}')
        return ret

    def _exec_key(self, key: str) -> str:
        """Format a kwarg key into a flag name, mirroring `named_args`'s key formatting."""
        if not self.options.preserve_underscores and '_' in key:
            key = key.replace('_', '-')
        return ('-' if self.options.single_dashes or len(key) == 1 else '--') + key

    @property
    def _exec_named_args(self) -> list[str]:
        """Convert keyword arguments to raw argv flag tokens (no shell quoting).

        Unlike `named_args`, each value is its own argv entry (e.g. `['--count', '5']`, not
        `['--count 5']`), since there is no shell here to split a quoted token back apart.

        Returns:
            Flag tokens ready to hand straight to a `shell=False` invocation.
        """
        ret: list[str] = []
        for key, val in self.kwargs.items():
            key = self._exec_key(key)
            if isinstance(val, bool) and val:
                ret.append(key)
            elif self.options.flag_assignment:
                ret.append(f'{key}={val}')
            else:
                ret.extend([key, str(val)])
        return ret

    @property
    def _exec_positional_args(self) -> list[str]:
        """Convert positional arguments to raw argv tokens (no shell quoting)."""
        return [str(a) for a in self.args]

    @property
    def _argv(self) -> list[str]:
        """Assemble this command's raw argv list for direct (non-shell) execution.

        Returns:
            Argument vector -- command name first -- safe to pass straight to `subprocess`/
            `asyncio` with `shell=False`; no value here is ever re-parsed by a shell.
        """
        parts = [self.command]
        if self.args or self.kwargs:
            sections = [self._exec_named_args, self._exec_positional_args]
            if self.options.named_args_last:
                sections = [sections[1], sections[0]]
            parts.extend(mi.flatten(sections))
        return parts

    # -------------------
    # `+` Primary Methods
    # -------------------
    def assemble(self) -> str:
        """Assemble a complete shell command from this instance's members.

        Examples:
            Assemble a command with values that require quoting::

                >>> from my import Command
                >>> cmd = Command.new('tar', 'x', options={'single_dashes': True}, file='a b.tar')
                >>> cmd.assemble()
                'tar -file "a b.tar" x'
        """
        parts = [self.command]
        if self.args or self.kwargs:
            # I. Assemble the main parts of the command
            sections = [self.named_args, self.positional_args]

            # II. Order the positional & keyword segments appropriately
            if self.options.named_args_last:
                sections = [sections[1], sections[0]]
            parts.extend(mi.flatten(sections))

        ret = ' '.join(parts)
        if self.options.out:
            ret += f' >> {self.options.out}'
        elif self.options.pipe:
            ret += f' | {self.options.pipe}'

        if self.options.verbose:
            print(ret)
        return ret

    # ------------------
    # `*` Public Methods
    # ------------------
    def __str__(self) -> str:
        """Get the assembled command as a string."""
        return self.assemble()

    def __bool__(self) -> bool:
        """A command is truthy if it has any content."""
        return bool(self.command or self.args)

    def execute(self) -> Result:
        """Execute a command synchronously via direct argv invocation (no shell).

        Note:
            Runs with `shell=False`, so argument values are handed to the OS exactly as given
            and are never re-parsed by a shell -- this is what prevents `$(...)`/backtick
            command-substitution injection from within an argument's contents.

        Returns:
            (`return_code`, `stdout`, `stderr`).
        Examples:
            Execute a command and capture its output::

                >>> from my import Command
                >>> Command.new('echo', 'hello').execute()
                Result(code=0, out='hello', err='')
        """
        self.assemble()  # side effect only: prints the human-readable form when `verbose` is set
        argv = self._argv

        if self.options.pipe:
            first = sbp.run(argv, capture_output=True, text=True, cwd=self.options.cwd)
            second = sbp.run(
                self.options.pipe._argv,
                input=first.stdout,
                capture_output=True,
                text=True,
                cwd=self.options.cwd,
            )
            return Command.Result(
                second.returncode or 0,
                (second.stdout or '').strip(),
                ((first.stderr or '') + (second.stderr or '')).strip(),
            )
        elif self.options.out:
            with Path(self.options.out).open('a') as fh:
                ret = sbp.run(argv, stdout=fh, stderr=sbp.PIPE, text=True, cwd=self.options.cwd)
            return Command.Result(ret.returncode or 0, '', (ret.stderr or '').strip())
        else:
            ret = sbp.run(argv, capture_output=True, text=True, shell=False, cwd=self.options.cwd)
            return Command.Result(
                ret.returncode or 0,
                (ret.stdout or '').strip(),
                (ret.stderr or '').strip(),
            )

    async def execute_async(self) -> Result:
        """Execute a command asynchronously via direct argv invocation (no shell).

        Note:
            Uses `create_subprocess_exec` (never `_shell`), so argument values are handed to
            the OS exactly as given and are never re-parsed by a shell -- this is what
            prevents `$(...)`/backtick command-substitution injection from within an
            argument's contents.

        Returns:
            (`return_code`, `stdout`, `stderr`).
        Examples:
            Execute a command from synchronous code::

                >>> import asyncio
                >>> from my import Command
                >>> asyncio.run(Command.new('echo', 'async!').execute_async())
                Result(code=0, out='async!', err='')
        """
        self.assemble()  # side effect only: prints the human-readable form when `verbose` is set
        argv = self._argv

        if self.options.pipe:
            first = await aio.create_subprocess_exec(
                *argv, stdout=aio.subprocess.PIPE, stderr=aio.subprocess.PIPE, cwd=self.options.cwd
            )
            first_out, first_err = await first.communicate()

            second_argv = self.options.pipe._argv
            second = await aio.create_subprocess_exec(
                *second_argv,
                stdin=aio.subprocess.PIPE,
                stdout=aio.subprocess.PIPE,
                stderr=aio.subprocess.PIPE,
                cwd=self.options.cwd,
            )
            second_out, second_err = await second.communicate(input=first_out)

            return Command.Result(
                second.returncode or 0,
                (second_out or b'').decode().strip(),
                ((first_err or b'') + (second_err or b'')).decode().strip(),
            )
        elif self.options.out:
            with Path(self.options.out).open('a') as fh:  # noqa: ASYNC230 -- tiny one-shot open
                subprocess = await aio.create_subprocess_exec(
                    *argv, stdout=fh, stderr=aio.subprocess.PIPE, cwd=self.options.cwd
                )
                _, stderr = await subprocess.communicate()
            return Command.Result(subprocess.returncode or 0, '', (stderr or b'').decode().strip())
        else:
            subprocess = await aio.create_subprocess_exec(
                *argv,
                stdout=aio.subprocess.PIPE,
                stderr=aio.subprocess.PIPE,
                cwd=self.options.cwd,
            )
            stdout, stderr = await subprocess.communicate()

            return Command.Result(
                subprocess.returncode or 0,
                (stdout or b'').decode().strip(),
                (stderr or b'').decode().strip(),
            )

    async def __call__(self) -> Result:
        """Execute the command asynchronously when the instance is called."""
        return await self.execute_async()

    @classmethod
    def run(cls, command: str, *args: Any, **kwargs: Any) -> Result:
        """Convenience method to build & execute a command in one statement.

        Args:
            command: Base command to execute.
            *args: Positional arguments.
            **kwargs: Keyword arguments (converted to flags).
        Returns:
            (return_code, stdout, stderr).
        Examples:
            Build and run in one call::

                >>> from my import Command
                >>> Command.run('echo', 'hello')
                Result(code=0, out='hello', err='')
        """
        return cls.new(command, *args, **kwargs).execute()

    @classmethod
    async def run_async(cls, command: str, *args: Any, **kwargs: Any) -> Result:
        """Convenience method to build & execute a command in one statement.

        Args:
            command: Base command to execute.
            *args: Positional arguments.
            **kwargs: Keyword arguments (converted to flags).
        Returns:
            (return_code, stdout, stderr).
        """
        return await cls.new(command, *args, **kwargs).execute_async()

    @classmethod
    async def exa(cls, *args: str, _cwd: str | Path | None = None, **kwargs: Any) -> Result:
        """Execute a command asynchronously, with a shorthand for overriding the working directory.

        Args:
            *args: The base command and its positional arguments, as for `run_async()`.
            _cwd: Working-directory override, applied via `options.cwd` whether or not an
                `options` value was passed alongside it.
            **kwargs: Keyword arguments (converted to flags).
        Returns:
            (`return_code`, `stdout`, `stderr`).
        """
        if _cwd is not None:
            _opts = kwargs.get('options', {})
            if isinstance(_opts, dict):
                _opts = Command.Options(**_opts)
            _opts.cwd = str(_cwd)
            kwargs['options'] = _opts
        return await cls.run_async(*args, **kwargs)
