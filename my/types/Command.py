############
### HEAD ###
############
### STANDARD
import asyncio as aio
from typing import Any, Self
import subprocess as sbp

### EXTERNAL
import pydantic as pyd
import more_itertools as mi

### INTERNAL
from ..infra import Series


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

        out: str | None = None  #: Redirect command output to a file. Not compatible w/ `pipe`.
        pipe: 'Command | None' = None  #: Pipe command output to another command.

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
            command: Base command name.
            args: Positional arguments.
            **kwargs: Keyword arguments -- both flags and options.
        Returns:
            Configured Command instance.
        """
        if options is None:
            options = cls.Options()
        elif isinstance(options, dict):
            if (pipe := options.get('pipe', None)) and not isinstance(pipe, Command):
                if isinstance(pipe, dict):
                    options['pipe'] = cls.new(**pipe)
                elif isinstance(pipe, Series):
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
        return list(map(self.quote_value, self.args))

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
            # I.iii. Determine assignment vs space separator
            sep = '=' if self.options.flag_assignment else ' '

            # II. Write plain arg if it's an atomic type, otherwise wrap in quotes
            if isinstance(val, bool) and val:
                ret.append(key)
            else:
                ret.append(f'{key}{sep}{self.quote_value(val)}')
        return ret

    def quote_value(self, value: Any) -> str:
        """Quote a value for safe shell usage."""
        value = str(value)
        if '"' in value:
            if "'" not in value:
                return f"'{value}'"
            else:
                return f'"{value.replace('"', '\\"')}"'
        elif ' ' in value or self.options.always_quote:
            return f'"{value}"'
        return value

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

        if self.options.out:
            parts.append(f'>> {self.options.out}')
        elif self.options.pipe:
            parts.append(f'| {self.options.pipe}')

        ret = ' '.join(parts)
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

    def execute(self) -> tuple[int, str, str]:
        """Execute a shell command synchronously.

        Returns:
            (return_code, stdout, stderr).
        """
        cmd = self.assemble()
        ret = sbp.run(cmd, capture_output=True, text=True, shell=True)
        return (
            ret.returncode or 0,
            (ret.stdout or '').strip(),
            (ret.stderr or '').strip(),
        )

    async def execute_async(self) -> tuple[int, str, str]:
        """Execute a shell command asynchronously.

        Returns:
            (return_code, stdout, stderr).
        """
        cmd = self.assemble()
        subprocess = await aio.create_subprocess_shell(
            cmd,
            stdout=aio.subprocess.PIPE,
            stderr=aio.subprocess.PIPE,
            shell=True,
        )
        stdout, stderr = await subprocess.communicate()

        return (
            subprocess.returncode or 0,
            (stdout or b'').decode().strip(),
            (stderr or b'').decode().strip(),
        )

    async def __call__(self) -> tuple[int, str, str]:
        """Execute the command asynchronously when the instance is called."""
        return await self.execute_async()

    @classmethod
    def run(cls, command: str, *args: Any, **kwargs: Any) -> tuple[int, str, str]:
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
    async def run_async(cls, command: str, *args: Any, **kwargs: Any) -> tuple[int, str, str]:
        """Convenience method to build & execute a command in one statement.

        Args:
            command: Base command to execute.
            *args: Positional arguments.
            **kwargs: Keyword arguments (converted to flags).
        Returns:
            (return_code, stdout, stderr).
        """
        return await cls.new(command, *args, **kwargs).execute_async()
