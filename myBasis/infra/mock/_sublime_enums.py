from __future__ import annotations
from enum import IntEnum, IntFlag


class HoverZone(IntEnum):
    """A zone in an open text sheet where the mouse may hover.

    See `EventListener.on_hover` and `ViewEventListener.on_hover`.

    For backwards compatibility these values are also available outside this enumeration with a
    `HOVER_` prefix.
    """

    TEXT = 1
    """The mouse is hovered over the text."""
    GUTTER = 2
    """The mouse is hovered over the gutter."""
    MARGIN = 3
    """The mouse is hovered in the white space to the right of a line."""


HOVER_TEXT = HoverZone.TEXT
"""The mouse is hovered over the text."""
HOVER_GUTTER = HoverZone.GUTTER
"""The mouse is hovered over the gutter."""
HOVER_MARGIN = HoverZone.MARGIN
"""The mouse is hovered in the white space to the right of a line."""


class NewFileFlags(IntFlag):
    """Flags for creating/opening files in various ways.

    See `Window.new_html_sheet`, `Window.new_file` and `Window.open_file`.

    For backwards compatibility these values are also available outside this enumeration (without a
    prefix).
    """

    NONE = 0
    ENCODED_POSITION = 1
    """Indicates that the file name should be searched for a `:row` or `:row:col` suffix."""
    TRANSIENT = 4
    """Open the file as a preview only: it won't have a tab assigned it until modified."""
    FORCE_GROUP = 8
    """
    Don't select the file if it is open in a different group. Instead make a new clone of that file
    in the desired group.
    """
    SEMI_TRANSIENT = 16
    """
    If a sheet is newly created, it will be set to semi-transient. Semi-transient sheets generally
    replace other semi-transient sheets. This is used for the side-bar preview. Only valid with
    `ADD_TO_SELECTION` or `REPLACE_MRU`.
    """
    ADD_TO_SELECTION = 32
    """Add the file to the currently selected sheets in the group."""
    REPLACE_MRU = 64
    """Causes the sheet to replace the most-recently used sheet in the current sheet selection."""
    CLEAR_TO_RIGHT = 128
    """
    All currently selected sheets to the right of the most-recently used sheet will be unselected
    before opening the file. Only valid in combination with `ADD_TO_SELECTION`.
    """
    FORCE_CLONE = 256
    """
    Don't select the file if it is open. Instead make a new clone of that file in the desired group.
    """


ENCODED_POSITION = NewFileFlags.ENCODED_POSITION
"""Indicates that the file name should be searched for a `:row` or `:row:col` suffix."""
TRANSIENT = NewFileFlags.TRANSIENT
"""Open the file as a preview only: it won't have a tab assigned it until modified."""
FORCE_GROUP = NewFileFlags.FORCE_GROUP
"""
Don't select the file if it is open in a different group. Instead make a new clone of that file in
the desired group.
"""
SEMI_TRANSIENT = NewFileFlags.SEMI_TRANSIENT
"""
If a sheet is newly created, it will be set to semi-transient. Semi-transient sheets generally
replace other semi-transient sheets. This is used for the side-bar preview. Only valid with
`ADD_TO_SELECTION` or `REPLACE_MRU`.
"""
ADD_TO_SELECTION = NewFileFlags.ADD_TO_SELECTION
"""Add the file to the currently selected sheets in the group."""
REPLACE_MRU = NewFileFlags.REPLACE_MRU
"""Causes the sheet to replace the most-recently used sheet in the current sheet selection."""
CLEAR_TO_RIGHT = NewFileFlags.CLEAR_TO_RIGHT
"""
All currently selected sheets to the right of the most-recently used sheet will be unselected before
opening the file. Only valid in combination with `ADD_TO_SELECTION`.
"""
FORCE_CLONE = NewFileFlags.FORCE_CLONE
"""
Don't select the file if it is open. Instead make a new clone of that file in the desired group.
"""


class FindFlags(IntFlag):
    """Flags for use when searching through a `View`.

    See `View.find` and `View.find_all`.

    For backwards compatibility these values are also available outside this enumeration (without a
    prefix).
    """

    NONE = 0
    LITERAL = 1
    """Whether the find pattern should be matched literally or as a regex."""
    IGNORECASE = 2
    """Whether case should be considered when matching the find pattern."""
    WHOLEWORD = 4
    """Whether to only match whole words."""
    REVERSE = 8
    """Whether to search backwards."""
    WRAP = 16
    """Whether to wrap around once the end is reached."""


LITERAL = FindFlags.LITERAL
"""Whether the find pattern should be matched literally or as a regex."""
IGNORECASE = FindFlags.IGNORECASE
"""Whether case should be considered when matching the find pattern."""
WHOLEWORD = FindFlags.WHOLEWORD
"""Whether to only match whole words."""
REVERSE = FindFlags.REVERSE
"""Whether to search backwards."""
WRAP = FindFlags.WRAP
"""Whether to wrap around once the end is reached."""


class QuickPanelFlags(IntFlag):
    """Flags for use with a quick panel.

    See `Window.show_quick_panel`.

    For backwards compatibility these values are also available outside this enumeration (without a
    prefix).
    """

    NONE = 0
    MONOSPACE_FONT = 1
    """Use a monospace font."""
    KEEP_OPEN_ON_FOCUS_LOST = 2
    """Keep the quick panel open if the window loses input focus."""
    WANT_EVENT = 4
    """Pass a second parameter to the `on_done` callback, a `Event`."""


MONOSPACE_FONT = QuickPanelFlags.MONOSPACE_FONT
"""Use a monospace font."""
KEEP_OPEN_ON_FOCUS_LOST = QuickPanelFlags.KEEP_OPEN_ON_FOCUS_LOST
"""Keep the quick panel open if the window loses input focus."""
WANT_EVENT = QuickPanelFlags.WANT_EVENT
"""Pass a second parameter to the `on_done` callback, a `Event`."""


class PopupFlags(IntFlag):
    """Flags for use with popups.

    See `View.show_popup`.

    For backwards compatibility these values are also available outside this enumeration (without a
    prefix).
    """

    NONE = 0
    COOPERATE_WITH_AUTO_COMPLETE = 2
    """Causes the popup to display next to the auto complete menu."""
    HIDE_ON_MOUSE_MOVE = 4
    """Causes the popup to hide when the mouse is moved, clicked or scrolled."""
    HIDE_ON_MOUSE_MOVE_AWAY = 8
    """
    Causes the popup to hide when the mouse is moved (unless towards the popup), or when clicked or 
    scrolled.
    """
    KEEP_ON_SELECTION_MODIFIED = 16
    """Prevent the popup from hiding when the selection is modified."""
    HIDE_ON_CHARACTER_EVENT = 32
    """Hide the popup when a character is typed."""


COOPERATE_WITH_AUTO_COMPLETE = PopupFlags.COOPERATE_WITH_AUTO_COMPLETE
"""Causes the popup to display next to the auto complete menu."""
HIDE_ON_MOUSE_MOVE = PopupFlags.HIDE_ON_MOUSE_MOVE
"""Causes the popup to hide when the mouse is moved, clicked or scrolled."""
HIDE_ON_MOUSE_MOVE_AWAY = PopupFlags.HIDE_ON_MOUSE_MOVE_AWAY
"""
Causes the popup to hide when the mouse is moved (unless towards the popup), or when clicked or
scrolled.
"""
KEEP_ON_SELECTION_MODIFIED = PopupFlags.KEEP_ON_SELECTION_MODIFIED
"""Prevent the popup from hiding when the selection is modified."""
HIDE_ON_CHARACTER_EVENT = PopupFlags.HIDE_ON_CHARACTER_EVENT
"""Hide the popup when a character is typed."""


class RegionFlags(IntFlag):
    """Flags for use with added regions. See `View.add_regions`.

    For backwards compatibility these values are also available outside this enumeration (without a
    prefix).
    """

    NONE = 0
    DRAW_EMPTY = 1
    """Draw empty regions with a vertical bar. By default, they aren't drawn at all."""
    HIDE_ON_MINIMAP = 2
    """Don't show the regions on the minimap."""
    DRAW_EMPTY_AS_OVERWRITE = 4
    """Draw empty regions with a horizontal bar instead of a vertical one."""
    PERSISTENT = 16
    """Save the regions in the session."""
    DRAW_NO_FILL = 32
    """Disable filling the regions, leaving only the outline."""
    HIDDEN = 128
    """Don't draw the regions."""
    DRAW_NO_OUTLINE = 256
    """Disable drawing the outline of the regions."""
    DRAW_SOLID_UNDERLINE = 512
    """Draw a solid underline below the regions."""
    DRAW_STIPPLED_UNDERLINE = 1024
    """Draw a stippled underline below the regions."""
    DRAW_SQUIGGLY_UNDERLINE = 2048
    """Draw a squiggly underline below the regions."""
    NO_UNDO = 8192


DRAW_EMPTY = RegionFlags.DRAW_EMPTY
"""Draw empty regions with a vertical bar. By default, they aren't drawn at all."""
HIDE_ON_MINIMAP = RegionFlags.HIDE_ON_MINIMAP
"""Don't show the regions on the minimap."""
DRAW_EMPTY_AS_OVERWRITE = RegionFlags.DRAW_EMPTY_AS_OVERWRITE
"""Draw empty regions with a horizontal bar instead of a vertical one."""
PERSISTENT = RegionFlags.PERSISTENT
"""Save the regions in the session."""
DRAW_NO_FILL = RegionFlags.DRAW_NO_FILL
"""Disable filling the regions, leaving only the outline."""
HIDDEN = RegionFlags.HIDDEN
"""Don't draw the regions."""
DRAW_NO_OUTLINE = RegionFlags.DRAW_NO_OUTLINE
"""Disable drawing the outline of the regions."""
DRAW_SOLID_UNDERLINE = RegionFlags.DRAW_SOLID_UNDERLINE
"""Draw a solid underline below the regions."""
DRAW_STIPPLED_UNDERLINE = RegionFlags.DRAW_STIPPLED_UNDERLINE
"""Draw a stippled underline below the regions."""
DRAW_SQUIGGLY_UNDERLINE = RegionFlags.DRAW_SQUIGGLY_UNDERLINE
"""Draw a squiggly underline below the regions."""
NO_UNDO = RegionFlags.NO_UNDO


class QueryOperator(IntEnum):
    """Enumeration of operators able to be used when querying contexts.

    See `EventListener.on_query_context` and `ViewEventListener.on_query_context`.

    For backwards compatibility these values are also available outside this enumeration with a
    `OP_` prefix.
    """

    EQUAL = 0
    NOT_EQUAL = 1
    REGEX_MATCH = 2
    NOT_REGEX_MATCH = 3
    REGEX_CONTAINS = 4
    NOT_REGEX_CONTAINS = 5


OP_EQUAL = QueryOperator.EQUAL
OP_NOT_EQUAL = QueryOperator.NOT_EQUAL
OP_REGEX_MATCH = QueryOperator.REGEX_MATCH
OP_NOT_REGEX_MATCH = QueryOperator.NOT_REGEX_MATCH
OP_REGEX_CONTAINS = QueryOperator.REGEX_CONTAINS
OP_NOT_REGEX_CONTAINS = QueryOperator.NOT_REGEX_CONTAINS


class PointClassification(IntFlag):
    """Flags that identify characteristics about a `Point` in a text sheet. See `View.classify`.

    For backwards compatibility these values are also available outside this enumeration with a
    `CLASS_` prefix.
    """

    NONE = 0
    WORD_START = 1
    """The point is the start of a word."""
    WORD_END = 2
    """The point is the end of a word."""
    PUNCTUATION_START = 4
    """The point is the start of a sequence of punctuation characters."""
    PUNCTUATION_END = 8
    """The point is the end of a sequence of punctuation characters."""
    SUB_WORD_START = 16
    """The point is the start of a sub-word."""
    SUB_WORD_END = 32
    """The point is the end of a sub-word."""
    LINE_START = 64
    """The point is the start of a line."""
    LINE_END = 128
    """The point is the end of a line."""
    EMPTY_LINE = 256
    """The point is an empty line."""


CLASS_WORD_START = PointClassification.WORD_START
"""The point is the start of a word."""
CLASS_WORD_END = PointClassification.WORD_END
"""The point is the end of a word."""
CLASS_PUNCTUATION_START = PointClassification.PUNCTUATION_START
"""The point is the start of a sequence of punctuation characters."""
CLASS_PUNCTUATION_END = PointClassification.PUNCTUATION_END
"""The point is the end of a sequence of punctuation characters."""
CLASS_SUB_WORD_START = PointClassification.SUB_WORD_START
"""The point is the start of a sub-word."""
CLASS_SUB_WORD_END = PointClassification.SUB_WORD_END
"""The point is the end of a sub-word."""
CLASS_LINE_START = PointClassification.LINE_START
"""The point is the start of a line."""
CLASS_LINE_END = PointClassification.LINE_END
"""The point is the end of a line."""
CLASS_EMPTY_LINE = PointClassification.EMPTY_LINE
"""The point is an empty line."""


class AutoCompleteFlags(IntFlag):
    """Flags controlling how asynchronous completions function. See `CompletionList`.

    For backwards compatibility these values are also available outside this enumeration (without a
    prefix).
    """

    NONE = 0
    INHIBIT_WORD_COMPLETIONS = 8
    """Prevent Sublime Text from showing completions based on the contents of the view."""
    INHIBIT_EXPLICIT_COMPLETIONS = 16
    """Prevent Sublime Text from showing completions based on `.sublime-completions` files."""
    DYNAMIC_COMPLETIONS = 32
    """If completions should be re-queried as the user types."""
    INHIBIT_REORDER = 128
    """Prevent Sublime Text from changing the completion order."""


INHIBIT_WORD_COMPLETIONS = AutoCompleteFlags.INHIBIT_WORD_COMPLETIONS
"""Prevent Sublime Text from showing completions based on the contents of the view."""
INHIBIT_EXPLICIT_COMPLETIONS = AutoCompleteFlags.INHIBIT_EXPLICIT_COMPLETIONS
"""Prevent Sublime Text from showing completions based on `.sublime-completions` files."""
DYNAMIC_COMPLETIONS = AutoCompleteFlags.DYNAMIC_COMPLETIONS
"""If completions should be re-queried as the user types."""
INHIBIT_REORDER = AutoCompleteFlags.INHIBIT_REORDER
"""Prevent Sublime Text from changing the completion order."""


class CompletionItemFlags(IntFlag):  # undocumented
    NONE = 0
    KEEP_PREFIX = 1


COMPLETION_FLAG_KEEP_PREFIX = CompletionItemFlags.KEEP_PREFIX


class DialogResult(IntEnum):
    """The result from a yes/no/cancel dialog. See `yes_no_cancel_dialog`.

    For backwards compatibility these values are also available outside this enumeration with a
    `DIALOG_` prefix.
    """

    CANCEL = 0
    YES = 1
    NO = 2


DIALOG_CANCEL = DialogResult.CANCEL
DIALOG_YES = DialogResult.YES
DIALOG_NO = DialogResult.NO


class PhantomLayout(IntEnum):
    """How a `Phantom` should be positioned. See `PhantomSet`.

    For backwards compatibility these values are also available outside this enumeration with a
    `LAYOUT_` prefix.
    """

    INLINE = 0
    """The phantom is positioned inline with the text at the beginning of its `Region`."""
    BELOW = 1
    """The phantom is positioned below the line, left-aligned with the beginning of its `Region`."""
    BLOCK = 2
    """The phantom is positioned below the line, left-aligned with the beginning of the line."""


LAYOUT_INLINE = PhantomLayout.INLINE
"""The phantom is positioned inline with the text at the beginning of its `Region`."""
LAYOUT_BELOW = PhantomLayout.BELOW
"""The phantom is positioned below the line, left-aligned with the beginning of its `Region`."""
LAYOUT_BLOCK = PhantomLayout.BLOCK
"""The phantom is positioned below the line, left-aligned with the beginning of the line."""


class KindId(IntEnum):
    """For backwards compatibility, these values are also available via the `KIND_ID_` prefix."""

    AMBIGUOUS = 0
    KEYWORD = 1
    TYPE = 2
    FUNCTION = 3
    NAMESPACE = 4
    NAVIGATION = 5
    MARKUP = 6
    VARIABLE = 7
    SNIPPET = 8
    COLOR_REDISH = 9
    COLOR_ORANGISH = 10
    COLOR_YELLOWISH = 11
    COLOR_GREENISH = 12
    COLOR_CYANISH = 13
    COLOR_BLUISH = 14
    COLOR_PURPLISH = 15
    COLOR_PINKISH = 16
    COLOR_DARK = 17
    COLOR_LIGHT = 18


KIND_ID_AMBIGUOUS = KindId.AMBIGUOUS
KIND_ID_KEYWORD = KindId.KEYWORD
KIND_ID_TYPE = KindId.TYPE
KIND_ID_FUNCTION = KindId.FUNCTION
KIND_ID_NAMESPACE = KindId.NAMESPACE
KIND_ID_NAVIGATION = KindId.NAVIGATION
KIND_ID_MARKUP = KindId.MARKUP
KIND_ID_VARIABLE = KindId.VARIABLE
KIND_ID_SNIPPET = KindId.SNIPPET
KIND_ID_COLOR_REDISH = KindId.COLOR_REDISH
KIND_ID_COLOR_ORANGISH = KindId.COLOR_ORANGISH
KIND_ID_COLOR_YELLOWISH = KindId.COLOR_YELLOWISH
KIND_ID_COLOR_GREENISH = KindId.COLOR_GREENISH
KIND_ID_COLOR_CYANISH = KindId.COLOR_CYANISH
KIND_ID_COLOR_BLUISH = KindId.COLOR_BLUISH
KIND_ID_COLOR_PURPLISH = KindId.COLOR_PURPLISH
KIND_ID_COLOR_PINKISH = KindId.COLOR_PINKISH
KIND_ID_COLOR_DARK = KindId.COLOR_DARK
KIND_ID_COLOR_LIGHT = KindId.COLOR_LIGHT

KIND_AMBIGUOUS: tuple[int, str, str]
KIND_KEYWORD: tuple[int, str, str]
KIND_TYPE: tuple[int, str, str]
KIND_FUNCTION: tuple[int, str, str]
KIND_NAMESPACE: tuple[int, str, str]
KIND_NAVIGATION: tuple[int, str, str]
KIND_MARKUP: tuple[int, str, str]
KIND_VARIABLE: tuple[int, str, str]
KIND_SNIPPET: tuple[int, str, str]


class SymbolSource(IntEnum):
    """See `Window.symbol_locations`.

    For backwards compatibility these values are also available via the `SYMBOL_SOURCE_` prefix.
    """

    ANY = 0
    """Use any source - both the index and open files."""
    INDEX = 1
    """Use the index created when scanning through files in a project folder."""
    OPEN_FILES = 2
    """Use the open files, unsaved or otherwise."""


SYMBOL_SOURCE_ANY = SymbolSource.ANY
"""Use any source - both the index and open files."""
SYMBOL_SOURCE_INDEX = SymbolSource.INDEX
"""Use the index created when scanning through files in a project folder."""
SYMBOL_SOURCE_OPEN_FILES = SymbolSource.OPEN_FILES
"""Use the open files, unsaved or otherwise."""


class SymbolType(IntEnum):
    """See `Window.symbol_locations` and `View.indexed_symbol_regions`.

    For backwards compatibility these values are also available via the `SYMBOL_TYPE_` prefix.
    """

    ANY = 0
    """Any symbol type - both definitions and references."""
    DEFINITION = 1
    """Only definitions."""
    REFERENCE = 2
    """Only references."""


SYMBOL_TYPE_ANY = SymbolType.ANY
"""Any symbol type - both definitions and references."""
SYMBOL_TYPE_DEFINITION = SymbolType.DEFINITION
"""Only definitions."""
SYMBOL_TYPE_REFERENCE = SymbolType.REFERENCE
"""Only references."""


class CompletionFormat(IntEnum):
    """The format completion text can be in. See `CompletionItem`.

    For backwards compatibility these values are also available via the `COMPLETION_FORMAT_`
    prefix.
    """

    TEXT = 0
    """Plain text, upon completing the text is inserted verbatim."""
    SNIPPET = 1
    """A snippet, with `$` variables."""
    COMMAND = 2
    """A command string, in the format returned by `format_command()`."""


COMPLETION_FORMAT_TEXT = CompletionFormat.TEXT
"""Plain text, upon completing the text is inserted verbatim."""
COMPLETION_FORMAT_SNIPPET = CompletionFormat.SNIPPET
"""A snippet, with `$` variables."""
COMPLETION_FORMAT_COMMAND = CompletionFormat.COMMAND
"""A command string, in the format returned by `format_command()`."""
