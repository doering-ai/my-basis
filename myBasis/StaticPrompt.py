############
### HEAD ###
############
# --------
# Standard
# --------
from __future__ import annotations
from typing import Any, TYPE_CHECKING
from typing_extensions import TypeAlias  # noqa: UP035
import functools as ft

if TYPE_CHECKING:
    from collections.abc import Callable
    import sublime as sb

# --------
# External
# --------
import sublime_plugin as sbp
import pydantic as pyd

# --------
# Internal
# --------
from .constants import RGXS

InputHandler = sbp.CommandInputHandler
TextHandler = sbp.TextInputHandler
Spans: TypeAlias = 'list[tuple[int, int]]'  # noqa: UP040


############
### BODY ###
############
class StaticPrompt(pyd.BaseModel):
    """The specification of a relatively simple `TextInputHandler`, for use by commands."""

    # ---- Metadata ----
    #: The argument identifier (i.e. `snake_case`) that this command's output will be found under.
    keyword: str = pyd.Field(alias='name')
    #: A custom name to be show to the left of the cursor in the input box.
    description: str = pyd.Field('', alias='input_description')
    #: The text to show when this input handler is not at the top of the stack.
    history_description: str = ''

    # Initial Content
    #: The ephemeral text shown before the user has entered anything.
    placeholder: str | None = None
    #: Initial text shown in the text entry box -- like a placeholder, but real editable text.
    initial_text: str | None = None
    #: Spans identifying pre-selected subsets of the initial text.
    initial_selection: Spans | Callable[[str], Spans] | None = None

    # ---- Handlers ----
    #: The main callback entry point, if you need one; called after an input has been validated.
    callback: Callable[[str], None] | None = pyd.Field(None, alias='confirm')
    #: Called when the user presses enter; return `false` to disallow the current value.
    validator: Callable[[str], bool] | None = None
    #: Called when the input handler is canceled (via backspace or escape).
    cancel: Callable[[], None] | None = None
    #: Generate a text or HTML "preview" of the results of the command so far.
    preview: Callable[[str], str] | Callable[[str], str | sb.Html] | None = None

    #: Identify the next interface to add to the stack after this one has finished.
    successor: StaticPrompt | InputHandler | Callable[[dict], InputHandler | None] | None = None

    #: Optional override for the resulting classe's name, if that matters to you for some reason
    classname: str = ''

    def generate_input_handler(self) -> type[TextHandler]:
        """Programatically define a new subclass of TextInputHandler based on this specification."""
        namespace: dict[str, Any] = dict()
        _setup = ft.partial(self._setup_method, namespace)

        # I. Setup metadata methods
        assert self.keyword, 'All static prompts must have a non-empty keyword "name".'
        _setup('name', lambda *_: self.keyword)

        if self.history_description:
            _setup('description', lambda *_: self.history_description)

        # II. Setup content methods
        if self.placeholder is not None:
            _setup('placeholder', lambda *_: self.placeholder)
        if self.initial_text is not None:
            _setup('initial_text', lambda *_: self.initial_text)
            if selector := self.initial_selection:
                if callable(selector):
                    _setup('initial_selection', lambda inst: selector(inst.initial_selection()))
                else:
                    _setup('initial_selection', lambda *_: selector)

        # III. Setup handler methods
        if (_preview := self.preview) is not None:
            _setup('preview', lambda _, text: _preview(text))
        if (_validator := self.validator) is not None:
            _setup('validate', lambda _, text: _validator(text))
        if (_cancel := self.cancel) is not None:
            _setup('cancel', lambda _: _cancel())
        if (_callback := self.callback) is not None:
            _setup('confirm', lambda _, text: _callback(text))

        # IV. Setup the next input
        if _successor := self.successor:
            if isinstance(_successor, StaticPrompt):
                fn = lambda *_, **__: _successor.generate_input_handler()()
            elif isinstance(_successor, InputHandler):
                fn = lambda *_, **__: _successor
            elif isinstance(_successor, type):
                assert issubclass(_successor, InputHandler), (
                    f'Expected InputHandler subclass, got {_successor!r}'
                )
                fn = lambda *_, **__: _successor()
            else:
                fn = lambda _self, args, *_, **__: _successor(args)

            _setup('next_input', fn)

        # V. Create the class using `type`
        if not self.classname:
            self.classname = (
                ''.join(map(str.title, RGXS['snake_separators'].split(self.keyword)))
                + 'InputHandler'
            )
        return type(self.classname, (TextHandler,), namespace)

    @staticmethod
    def _setup_method(namespace: dict[str, Any], name: str, method: Callable) -> None:
        namespace[name] = ft.update_wrapper(method, getattr(TextHandler, name))
