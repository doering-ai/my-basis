"""Runtime mock for `sublime_plugin`.

Only the base classes that plugins subclass are needed; everything else is
accessed via class bodies (not instances) at import time, so MagicMock stubs
suffice for the remainder.
"""

############
### HEAD ###
############
### STANDARD
from __future__ import annotations
from typing import Any
from unittest.mock import MagicMock

### EXTERNAL

### INTERNAL
from ._sublime import Edit, View, Window


############
### BODY ###
############
import re as _re


class Command:
    def name(self) -> str:
        """Return the command name derived from the class name (like Sublime Text)."""
        cls_name = type(self).__name__
        if cls_name.endswith('Command'):
            cls_name = cls_name[:-len('Command')]
        # Convert CamelCase to snake_case
        s = _re.sub(r'(.)([A-Z][a-z]+)', r'\1_\2', cls_name)
        return _re.sub(r'([a-z0-9])([A-Z])', r'\1_\2', s).lower()
    pass


class TextCommand(Command):
    view: View

    def __init__(self, view: View) -> None:
        self.view = view

    def run(self, edit: Edit, **kwargs: Any) -> None:
        pass

    def is_enabled(self, **kwargs: Any) -> bool:
        return True

    def is_visible(self, **kwargs: Any) -> bool:
        return True

    def description(self, **kwargs: Any) -> str:
        return ''

    def want_event(self) -> bool:
        return False


class WindowCommand(Command):
    window: Window

    def __init__(self, window: Window) -> None:
        self.window = window

    def run(self, **kwargs: Any) -> None:
        pass

    def is_enabled(self, **kwargs: Any) -> bool:
        return True

    def is_visible(self, **kwargs: Any) -> bool:
        return True

    def description(self, **kwargs: Any) -> str:
        return ''


class ApplicationCommand(Command):
    def run(self, **kwargs: Any) -> None:
        pass

    def is_enabled(self, **kwargs: Any) -> bool:
        return True

    def is_visible(self, **kwargs: Any) -> bool:
        return True

    def description(self, **kwargs: Any) -> str:
        return ''


# ---------
# LISTENERS
# ---------
class EventListener:
    pass


class ViewEventListener:
    view: View

    def __init__(self, view: View) -> None:
        self.view = view

    @classmethod
    def is_applicable(cls, settings: Any) -> bool:
        return True

    @classmethod
    def applies_to_primary_view_only(cls) -> bool:
        return False


class TextChangeListener:
    pass


# --------------
# INPUT HANDLERS
# --------------
class CommandInputHandler:
    def name(self) -> str:
        return ''

    def placeholder(self) -> str:
        return ''

    def initial_text(self) -> str:
        return ''

    def preview(self, text: str) -> str:
        return ''

    def validate(self, text: str) -> bool:
        return True

    def cancel(self) -> None:
        pass

    def confirm(self, text: str) -> None:
        pass

    def next_input(self, args: Any) -> 'CommandInputHandler | None':
        return None

    def want_event(self) -> bool:
        return False


class TextInputHandler(CommandInputHandler):
    pass


class ListInputHandler(CommandInputHandler):
    def list_items(self) -> list:
        return []


class BackInputHandler(CommandInputHandler):
    pass


# ---------
# CATCH-ALL
# ---------
def __getattr__(name: str) -> Any:
    return MagicMock(name=f'sublime_plugin.{name}')
