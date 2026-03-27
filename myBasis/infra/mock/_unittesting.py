"""Runtime mock for the `unittesting` package.

Provides the same public API as UnitTesting's `unittesting` package so that
test files can use identical imports (`from unittesting import ViewTestCase`)
both inside ST (where the real package runs) and outside ST (where this mock
is injected instead).

DeferrableTestCase is a plain TestCase here — deferrable tests should be
marked @pytest.mark.st_only and skipped offline.
"""

############
### HEAD ###
############
### STANDARD
from __future__ import annotations
from typing import Any
from collections.abc import Generator
from unittest import TestCase, expectedFailure

### EXTERNAL

### INTERNAL
from unittest import IsolatedAsyncioTestCase

# ruff: noqa


############
### BODY ###
############
class ViewTestCaseMixin:
    """Mirrors UnitTesting's ViewTestCaseMixin, but backed by the mock View."""

    view_settings: dict

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.view_settings = {}

    def setUp(self) -> None:  # type: ignore[override]
        import sublime

        self.window = sublime.active_window()
        self.view = self.window.new_file()
        settings = self.view.settings()
        for key, value in getattr(self.__class__, 'view_settings', {}).items():
            settings.set(key, value)

    def tearDown(self) -> None:  # type: ignore[override]
        if self.view:
            self.view.set_scratch(True)
            self.view.close()

    # -- caret helpers -------------------------------------------------------
    def addCaretAt(self, row: int, col: int) -> None:
        self.view.sel().add(self.textPoint(row, col))

    def setCaretTo(self, row: int, col: int) -> None:
        self.view.sel().clear()
        self.view.sel().add(self.textPoint(row, col))

    def textPoint(self, row: int, col: int) -> int:
        return self.view.text_point(row, col)

    # -- text helpers --------------------------------------------------------
    def getRowText(self, row: int) -> str:
        return self.view.substr(self.view.line(self.view.text_point(row, 0)))

    def getText(self) -> str:
        import sublime

        return self.view.substr(sublime.Region(0, self.view.size()))

    def setText(self, text: str) -> None:
        self.clearText()
        self.insertText(text)

    def clearText(self) -> None:
        self.view.run_command('select_all')
        self.view.run_command('right_delete')

    def insertText(self, text: str) -> None:
        self.view.run_command('insert', {'characters': text})

    # -- assertion helpers (mirror UnitTesting's ViewTestCase) ---------------
    def assertCaretAt(self, row: int, col: int) -> None:
        self.assertEqual(self.view.sel()[0].begin(), self.textPoint(row, col))  # type: ignore[attr-defined]

    def assertCaretsAt(self, carets: Any) -> None:
        expected = tuple(self.textPoint(r, c) for r, c in carets)
        found = tuple(s.begin() for s in self.view.sel())
        self.assertEqual(found, expected)  # type: ignore[attr-defined]

    def assertRowContentsEqual(self, row: int, text: str) -> None:
        self.assertEqual(self.getRowText(row), text)  # type: ignore[attr-defined]

    def assertViewContentsEqual(self, text: str) -> None:
        self.assertEqual(self.getText(), text)  # type: ignore[attr-defined]


class ViewTestCase(ViewTestCaseMixin, TestCase):
    """Infrastructure to run unit tests on dedicated ``sublime.View()`` objects.

    A new ``view`` object is created within the active ``window`` for each ``ViewTestCase``.
    The view is accessible via ``self.view`` from within each test method.
    The owning window can be accessed via ``self.window``.

    ```py
    class MyTestCase(ViewTestCase):
        # settings to apply to the created view
        view_settings = {
            'detect_indentation': False,
            'tab_size': 4,
            'translate_tabs_to_spaces': False,
            'word_wrap': False,
        }

        def test_editing(self):
            self.setText('foo')
            self.setCaretTo(0, 0)
            self.setText('foo')
            self.assertRowContentsEqual(0, 'foofoo')
    ```
    """


class DeferrableTestCase(TestCase):
    """Outside ST: a plain TestCase.

    Mark subclass tests with @pytest.mark.st_only if they genuinely require
    ST's event loop (i.e. they yield conditions/delays).
    """


class DeferrableViewTestCase(ViewTestCaseMixin, DeferrableTestCase):
    """Infrastructure to run async unit tests on dedicated ``sublime.View()`` objects.

    A new ``view`` object is created within the active ``window`` for each ``ViewTestCase``.
    The view is accessible via ``self.view`` from within each test method.
    The owning window can be accessed via ``self.window``.

    ```py
    class MyTestCase(DeferrableViewTestCase):
        # settings to apply to the created view
        view_settings = {
            'detect_indentation': False,
            'tab_size': 4,
            'translate_tabs_to_spaces': False,
            'word_wrap': False,
        }

        def test_editing(self):
            self.setText('foo')
            self.setCaretTo(0, 0)
            self.defer(100, self.insertText, 'foo')
            yield 200
            self.assertRowContentsEqual(0, 'foofoo')
    ```
    """


AWAIT_WORKER = 'AWAIT_WORKER'
DeferrableMethod = Generator

__all__ = [
    'AWAIT_WORKER',
    'DeferrableMethod',
    'DeferrableTestCase',
    'DeferrableViewTestCase',
    'expectedFailure',
    'IsolatedAsyncioTestCase',
    'TestCase',
    'ViewTestCase',
]
