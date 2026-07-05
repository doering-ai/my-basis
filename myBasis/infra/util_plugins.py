############
### HEAD ###
############
### STANDARD
from __future__ import annotations
from pathlib import Path

### EXTERNAL
import sublime_plugin as sbp

### INTERNAL
from .utils import ut


############
### DATA ###
############


############
### BODY ###
############
class LogToDiskCommand(sbp.ApplicationCommand):
    """Controls whether the SublimeText log (normally accessible via console) is written to disk."""

    def run(
        self,
        *,
        target: bool | None | str | Path = True,
        fmt: str = '[%(relativeCreated)d] %(message)s',
        **_kwargs,
    ) -> None:
        """Write the content to the specified file path.

        Args:
            target: If True, logs will be written to a default file in the current directory.
                    If a string or Path is provided, logs will be written to that file.
                    If False, disk logging will be disabled.
                    If None, logging behavior is toggled.
            fmt: Format string for log messages.
        """
        # TODO: restore fmt param — log_to_disk was refactored to drop fmt/clear/level
        ut.log_to_disk(target)
