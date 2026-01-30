############
### HEAD ###
############
### STANDARD
import asyncio as aio
from pathlib import Path
import sys
import inspect
import importlib

### EXTERNAL

### INTERNAL

SCRIPT_DIR = Path(__file__).parents[1] / 'src'


############
### BODY ###
############
async def invoke(file: Path, argv: list[str]):
    """Wrap a 3.13 python command from this 3.8 runtime, passing sublime calls through a socket."""


############
### MAIN ###
############
def main():
    target, *argv = sys.argv[1:]
    if not target.endswith('.py'):
        target += '.py'
    file = next(SCRIPT_DIR.rglob(target), None)
    assert file is not None, f'Unable to find script "{target}"'

    aio.run(invoke(file, argv))


if __name__ == '__main__':
    main()
