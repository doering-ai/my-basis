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
        target: bool | str | Path | None = True,
        **_kwargs,
    ) -> None:
        """Write the content to the specified file path.

        Args:
            target: If True, logs will be written to a default file in the current directory.
                    If a string or Path is provided, logs will be written to that file.
                    If False, disk logging will be disabled.
                    If None, logging behavior is toggled.
        """
        ut.log_to_disk(target)
