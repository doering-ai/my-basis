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

    Commands can be manually finalized w/ `assemble()`, or executed directly via `execute()`
     / `execute_async()`. To chain commands together, use the provided `out` and `pipe` options.
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

        code: int
        out: str
        err: str

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
            args: Positional arguments ot the command.
            options: Assembly option flags.
            **kwargs: Keyword arguments to the command.
        Returns:
            Configured Command instance.
        """
        if options is None:
            options = cls.Options()
        elif isinstance(options, dict):
            if (pipe := options.get('pipe', None)) and not isinstance(pipe, Command):
                if isinstance(pipe, dict):
                    options['pipe'] = cls.new(**pipe)
                elif isinstance(pipe, Vec):
                    options['pipe'] = cls.new(*pipe)
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

    # -------------------
    # `+` Primary Methods
    # -------------------
    def assemble(self) -> str:
        """Assemble a complete shell command from this instance's members."""
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
        """Execute a shell command synchronously.

        Returns:
            (`return_code`, `stdout`, `stderr`).
        """
        cmd = self.assemble()
        ret = sbp.run(cmd, capture_output=True, text=True, shell=True, cwd=self.options.cwd)
        return Command.Result(
            ret.returncode or 0,
            (ret.stdout or '').strip(),
            (ret.stderr or '').strip(),
        )

    async def execute_async(self) -> Result:
        """Execute a shell command asynchronously.

        Returns:
            (`return_code`, `stdout`, `stderr`).
        """
        cmd = self.assemble()
        subprocess = await aio.create_subprocess_shell(
            cmd,
            stdout=aio.subprocess.PIPE,
            stderr=aio.subprocess.PIPE,
            shell=True,
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
        """Executes a command in the virtual environment asynchronously."""
        if _cwd is not None:
            _opts = kwargs.get('options', {})
            if isinstance(_opts, dict):
                _opts = Command.Options(**_opts)
            else:
                _opts.cwd = str(_cwd)
            kwargs['options'] = _opts
        return await cls.run_async(*args, **kwargs)
