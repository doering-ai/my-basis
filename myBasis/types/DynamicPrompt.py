############
### HEAD ###
############
# --------
# Standard
# --------
from __future__ import annotations
from typing import Any, NamedTuple
from types import MethodType
from typing_extensions import TypeAlias
from collections.abc import Callable
import functools as ft

# --------
# External
# --------
import sublime as sb
import sublime_plugin as sbp

# --------
# Internal
# --------
from .StaticPrompt import StaticPrompt


############
### DATA ###
############


InputHandler = sbp.CommandInputHandler
TextHandler = sbp.TextInputHandler
ListHandler = sbp.ListInputHandler
Spans: TypeAlias = 'list[tuple[int, int]]'
_ListItems: TypeAlias = 'list[str] | list[tuple[str, Any]] | list[sb.ListInputItem]'
ListItems: TypeAlias = '_ListItems | tuple[_ListItems, int]'

NO_RESULTS = [sb.ListInputItem('No Results', '')]


############
### BODY ###
############
class DynamicPrompt(StaticPrompt):
    """A ListInputHandler which can update its items while typing in the input field.

    ```{caution}
    ## DO NOT USE -- OUT OF DATE
    ```

    Subclasses of DynamicPrompt must not implement the `list_items` method, but can
    override `get_list_items` for the initial list items. The `on_modified` method will be called
    after a small delay (debounced) whenever changes were made to the input text. You can use this
    to call the `update` method with a list of `ListInputItem`s to update the list items.

    To create an instance of the derived class pass the command instance and the command arguments
    to the constructor, like this:
    """

    class ListItemKind(NamedTuple):
        """Metadata for a list item, used for styling and other purposes."""

        kind: sb.KindId = sb.KindId.AMBIGUOUS
        char: str = ''
        name: str = ''

    generator: Callable[..., ListItems] | str

    # -------------------
    # `.` Initial Methods
    # -------------------
    # def execute(self, command: StaticPrompt._MyCommand) -> dict:
    #     self.command = command  # type: ignore
    #     data = {}
    #     self.view = self.command.window.show_input_panel(
    #         caption=self.prefix,
    #         initial_text=self.initial_text(),
    #     )
    #     return data

    # -------------------
    # `-` Private Methods
    # -------------------
    @staticmethod
    def _setup_method(namespace: dict[str, Any], name: str, method: Callable) -> None:
        namespace[name] = ft.update_wrapper(method, getattr(ListHandler, name))

    def _generate_namespace(
        self, command: StaticPrompt._MyCommand
    ) -> tuple[dict, type[ListHandler]]:
        # I. Build initial namespace from super classes' fields
        namespace, _ = super()._generate_namespace(command)
        _setup = ft.partial(self._setup_method, namespace)

        if isinstance(self.generator, str):
            # III. Fetch bound method names
            _name = type(command).__name__
            generator: MethodType | None = getattr(command, self.generator, None)
            assert generator, f'`{_name}.{self.generator}` does not exist.'
            assert callable(generator), f'`{_name}.{self.generator}` is not callable.'
            _setup('list_items', lambda _, _gen=generator, _args=self.raw_args: _gen(**_args))
        else:
            # IV. Use unbound functions directly
            print(f'Using generator function `{self.generator}` for list items.')
            _setup('list_items', lambda _, _gen=self.generator: _gen())

        return namespace, ListHandler

    # -------------------
    # `+` Primary Methods
    # -------------------

    # ------------------
    # `*` Public Methods
    # ------------------


# class DynamicListHandler(ListHandler):
#     """A ListInputHandler which can update its items while typing in the input field."""

#     class _InputListener(sbp.TextChangeListener):
#         def __init__(self, generator: Callable[[str], ListItems]) -> None:
#             super().__init__()
#             self.generator = generator

#         @classmethod
#         def is_applicable(cls, buffer: sb.Buffer) -> bool:
#             """Only attach via manual `attach` commands."""
#             return False

#         @ut.debounced
#         def on_text_changed(self, changes: list[sb.TextChange]) -> None:
#             view = self.buffer.primary_view()
#             if view and view.id():
#                 self.generator(view.substr(sb.Region(0, view.size())))

#     # ---- Given ----
#     command: StaticPrompt._MyCommand
#     generator: Callable[[str], ListItems]
#     raw_args: dict = pyd.Field(default_factory=dict)

#     # ---- Internal ----
#     text: str = ''
#     view: sb.View | None = None
#     items: list[sb.ListInputItem] = pyd.Field(default_factory=list)
#     listener: sbp.TextChangeListener | None = None

#     def list_items(self) -> ListItems:  # type: ignore
#         """The list items which are shown in the command palette.

#         This is called by Sublime Text, so don't call it directly -- instead, call `update` with
#         new list items whenever you want to update the list.
#         """
#         return (self.items if self.text else self.generator('')) or NO_RESULTS

#     def update(self, items: list[sb.ListInputItem]) -> None:
#         """Call this method to update the list items."""
#         if not self.view:
#             return
#         self.items = items
#         self.text = self.view.substr(sb.Region(0, self.view.size()))

#         # Refresh the command palette
#         self.command.window.run_command(
#             'chain', {'commands': [['hide_overlay', {}], [self.command.classname, self.raw_args]]}
#         )

#     def attach(self) -> None:
#         """Attach the listener to the command pallette's view."""
#         ############ DEBUG #############
#         print('\n'.join(['=' * 128, f'{"=== KNOWN VIEWS ===":=^128}']))
#         out = {window.window_id: self._debug_window(window) for window in sb.windows()}
#         stream = StringIO()
#         ut.YAML.dump(out, stream=stream)
#         print(stream.getvalue())
#         print('=' * 128)
#         ############ DEBUG #############

#         self.view = next(
#             (
#                 view
#                 for view in self.command.window.views()
#                 if view.element() == 'command_palette:input'
#             ),
#             None,
#         )
#         if self.view is none:
#             print(f'could not find command palette view in window[{self.command.window.id()}].')
#             self.detach()
#             return

#         self.listener = DynamicListHandler._InputListener(self.generator)
#         self.listener.attach(self.view.buffer())
#         print(f'Attached listener to View[{self.view.id()}] of Buffer[{self.view.buffer().id()}].')

#     def _debug_window(self, window: sb.Window) -> dict:
#         group = window.active_group()
#         return dict(
#             window_id=window.window_id,
#             views=[
#                 dict(
#                     id=view.id(),
#                     sheet=sheet.sheet_id if (sheet := view.sheet()) is not None else -1,
#                     buffer=view.buffer().buffer_id,
#                     file=_fn.rsplit('/', 1)[-1] if (_fn := view.file_name()) else '',
#                     name=view.name(),
#                     isScratch=view.is_scratch(),
#                     element=view.element(),
#                 )
#                 for view in window.views()
#             ],
#             sheets=[
#                 dict(
#                     id=sheet.sheet_id,
#                     is_transient=sheet.is_transient(),
#                     is_semi_transient=sheet.is_semi_transient(),
#                     view=v.id() if (v := sheet.view()) else None,
#                 )
#                 for sheet in window.sheets()
#             ],
#             transient_sheet=window.transient_sheet_in_group(group),
#             transient_view=window.transient_view_in_group(group),
#             panels=window.panels(),
#             active_panel=window.active_panel(),
#             output_panel=window.find_output_panel('command_palette'),
#         )

#     def detach(self) -> None:
#         """Detach the listener from the command pallette's view."""
#         if self.listener and self.listener.is_attached():
#             self.listener.detach()

#     def initial_text(self) -> str:
#         """The initial text shown in the command palette input field."""
#         sb.set_timeout(self.attach, 500)
#         return self.text

#     def initial_selection(self) -> list[tuple[int, int]]:
#         """The initial selection in the input field, as a list of (begin, end) tuples."""
#         pt = len(self.text)
#         return [(pt, pt)]

#     def confirm(self, text: str) -> None:
#         """Called after user hits enter."""
#         self.detach()

#     def cancel(self) -> None:
#         """Called when the user cancels the input (via backspace or escape)."""
#         self.detach()
