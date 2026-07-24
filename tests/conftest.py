############
### HEAD ###
############
### STANDARD
from __future__ import annotations
from pathlib import Path
from collections.abc import Iterator

### EXTERNAL
import pytest as pyt
import sublime as sb

### INTERNAL


############
### BODY ###
############
TEST_DIR = Path(__file__).parent
assert TEST_DIR.exists(), f'Test directory {TEST_DIR} does not exist.'


# --------
# Fixtures
# --------
@pyt.fixture
def make_view() -> Iterator[sb.View]:
    """Create a fresh mock view, yielding it and closing it after the test."""
    view = sb.active_window().new_file()
    yield view
    view.set_scratch(True)
    view.close()


@pyt.fixture
def text_view(make_view: sb.View) -> sb.View:
    """A view pre-loaded with the given text (via indirect parametrization)."""
    return make_view


def pytest_generate_tests(metafunc: pyt.Metafunc) -> None:
    """Inject text into the ``text_view`` fixture when a ``text`` indirect param is present."""
    if 'text_view' not in metafunc.fixturenames:
        return
    # The actual text is provided via @pyt.mark.parametrize('text', [...], indirect=True)
