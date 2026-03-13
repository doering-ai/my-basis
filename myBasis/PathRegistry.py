############
### HEAD ###
############
### STANDARD
from __future__ import annotations
from pathlib import Path

### EXTERNAL
import pydantic as pyd
import sublime as sb

### INTERNAL


############
### BODY ###
############
def parse(path: str | Path) -> Path:
    """Parse a string or Path into an expanded and resolved Path object."""
    return Path(path).expanduser().resolve()


class PathRegistry(pyd.BaseModel):
    """A registry of file paths, mapping string names to Path objects."""

    cache: pyd.DirectoryPath = parse(sb.cache_path())
    packages: pyd.DirectoryPath = parse(sb.packages_path())
    installed_packages: pyd.DirectoryPath = parse(sb.installed_packages_path())
    storage: pyd.DirectoryPath = parse(Path(sb.cache_path()) / 'Package Storage')

    @staticmethod
    def new(**kwargs: str | Path) -> dict[str, Path]:
        """Expand the given dictionary of paths, mapping names to Paths.

        Args:
            **kwargs: A mapping of string names to file paths (as strings or Paths).
        Returns:
            The paths mapping with all values now expanded to Paths.
        """
        return {key: Path(val).expanduser().resolve() for key, val in kwargs.items()}

    parse = parse


PATHS = PathRegistry()
