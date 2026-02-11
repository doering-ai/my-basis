############
### HEAD ###
############
# --------
# Standard
# --------
from __future__ import annotations
from typing import Any, TYPE_CHECKING
import functools as ft
# from typing_extensions import ParamSpec  # noqa: UP035

if TYPE_CHECKING:
    from collections.abc import Callable

# --------
# External
# --------
import sublime as sb
import sublime_plugin as sbp
import pydantic as pyd

# --------
# Internal
# --------

Spans = list[tuple[int, int]]
# Params = ParamSpec('Params')


############
### BODY ###
############
class StaticInterface(pyd.BaseModel):
    """A static dataclass describing a plugin's `TextInputHandler`."""

    # Metadata
    name: str = ''
    description: str = ''
    want_event: bool = False

    # Initial Content
    placeholder: str = ''
    initial_text: str = ''
    initial_selection: Spans | Callable[[str], Spans] = []

    # Handlers
    preview: Callable[[str], str] | None = None
    validate: Callable[[str], bool] | None = None
    cancel: Callable[[], None] | None = None
    confirm: Callable[[str], None] | None = None

    # Next interface in a chain
    successor: StaticInterface | sbp.CommandInputHandler | None = None

    def generate_input_handler(self) -> type[sbp.TextInputHandler]:
        """Programatically define a new subclass of TextInputHandler."""
        namespace: dict[str, Any] = dict()

        def _wrap(name: str, method: Callable) -> None:
            namespace[name] = ft.update_wrapper(method, getattr(sbp.TextInputHandler, name))

        # I. Setup metadata methods
        if self.name:
            _wrap('placeholder', lambda *_: self.placeholder)
        if self.placeholder:
            _wrap('placeholder', lambda *_: self.placeholder)
        if self.description:
            _wrap('description', lambda *_: self.description)
        if self.want_event:
            _wrap('want_event', lambda *_: True)

        # II. Setup content methods
        if self.placeholder:
            _wrap('placeholder', lambda *_: self.placeholder)
        if self.initial_text:
            _wrap('initial_text', lambda *_: self.initial_text)
            if selector := self.initial_selection:
                if callable(selector):
                    _wrap('initial_selection', lambda inst: selector(inst.initial_selection()))
                else:
                    _wrap('initial_selection', lambda *_: selector)

        # III. Setup handler methods
        if preview := self.preview:
            _wrap('preview', lambda _, text: preview(text))
        if validate := self.validate:
            _wrap('preview', lambda _, text: validate(text))
        if cancel := self.cancel:
            _wrap('cancel', lambda _: cancel())
        if confirm := self.confirm:
            _wrap('confirm', lambda _, text: confirm(text))

        # IV. Setup successor instance
        if successor_interface := self.successor:
            if isinstance(successor_interface, sbp.CommandInputHandler):
                successor = successor_interface
            else:
                successor = successor_interface.generate_input_handler()()

            _wrap('next_input', lambda *_, **__: successor)

        # V. Create the class using `type`
        return type(self.name, (sbp.TextInputHandler,), namespace)
