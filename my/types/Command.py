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

    command: str
    args: list[str] = []
    kwargs: dict[str, Any] = {}

    preserve_underscores: bool = False
    single_dashes: bool = False
    named_args_last: bool = False
    verbose: bool = False

    out: str | None = None
    pipe: Self | None = None

    # -------------------
    # `.` Initial Methods
    # -------------------
    @pyd.model_validator(mode='after')
    def _validate_command(self) -> Self:
        assert self.out is None or self.pipe is None, 'Cannot define both output and pipe at once.'
        return self

    @classmethod
    def new(cls, command: str, *args: str, **kwargs: Any) -> Self:
        """Create a new command instance.

        Args:
            command: Base command name.
            args: Positional arguments.
            **kwargs: Keyword arguments -- both flags and options.
        Returns:
            Configured Command instance.
        """
        options = {}
        if opt_keys := set(kwargs.keys()) & _command_fields:
            options = {k: kwargs.pop(k) for k in opt_keys}

        return cls(command=command, args=list(args), kwargs=kwargs, **options)

    # -------------------
    # `-` Private Methods
    # -------------------
    @property
    def positional_args(self) -> list[str]:
        """Convert positional arguments to shell-safe values.

        Returns:
            String representations with appropriate quoting.
        """
        ret = []
        for arg in self.args:
            if isinstance(arg, int | float):
                ret.append(f'{arg}')
            else:
                arg = str(arg)
                ret.append(f'"{arg}"' if '"' not in arg else f'{arg}')
        return ret

    @property
    def named_args(self) -> list[str]:
        """Convert keyword arguments to shell-safe flags.

        Returns:
            Formatted command-line flags (e.g., `--key value`, `-k`).
        """
        ret = []
        for key, val in self.kwargs.items():
            # I.i. Format python identifiers for the command line (e.g. my_arg -> my-arg)
            if not self.preserve_underscores and '_' in key:
                key = key.replace('_', '-')
            # I.ii. Determine single vs double dash prefix
            key = ('-' if self.single_dashes or len(key) == 1 else '--') + key

            # II. Write plain arg if it's an atomic type, otherwise wrap in quotes
            if isinstance(val, bool) and val:
                ret.append(key)
            elif isinstance(val, int | float):
                ret.append(f'{key} {val}')
            else:
                # Find the quote style least likely to cause problems for this value
                valstr = str(val)
                if '"' in valstr:
                    if "'" not in valstr:
                        ret.append(f"{key} '{valstr}'")
                        continue
                    else:
                        valstr = valstr.replace('"', '\\"')
                ret.append(f'{key} "{valstr}"')
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
            if self.named_args_last:
                sections = [sections[1], sections[0]]
            parts.extend(mi.flatten(sections))

        if self.out:
            parts.append(f'>> {self.out}')
        elif self.pipe:
            parts.append(f'| {self.pipe}')

        ret = ' '.join(parts)
        if self.verbose:
            print(ret)
        return ret

    # ------------------
    # `*` Public Methods
    # ------------------
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


_command_fields = set(Command.model_fields.keys()) - {'cmd', 'args', 'kwargs'}
