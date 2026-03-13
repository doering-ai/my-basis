############
### HEAD ###
############
### STANDARD
from __future__ import annotations
from typing import TextIO
from typing_extensions import Annotated
import os

### EXTERNAL
import regex as re

import pydantic as pyd
from pydantic_core import core_schema as pyd_schema

import sublime as sb
import sublime_plugin as sbp

### INTERNAL


############
### BODY ###
############
def schemify(tvar: type) -> pyd.GetPydanticSchema:
    """Create Pydantic schema validator for instance type checking.

    Args:
        tvar: Type to create validator for.
    Returns:
        GetPydanticSchema validator for use with Annotated types.
    """
    return pyd.GetPydanticSchema(lambda *_: pyd_schema.is_instance_schema(cls=tvar))


def _validate_syntax(syntax: sb.Syntax | str) -> str:
    """Validate and normalize a syntax specification to a fully qualified resource path."""
    if isinstance(syntax, sb.Syntax):
        return syntax.path
    elif isinstance(syntax, str):
        syntax = syntax.strip(' "\'')
        if 'Packages/' in syntax:
            syntax = syntax[syntax.index('Packages/') :]
            if not syntax.endswith('.sublime-syntax'):
                syntax += '.sublime-syntax'
            return syntax
        elif syntax and not syntax.startswith('Packages/'):
            path, scope, name = '', '', ''
            if not syntax.endswith('.sublime-syntax'):
                path = syntax
            elif syntax.lower() and '.' in syntax:
                scope, name = syntax, ''
            elif os.path.sep in syntax:
                syntax += '.sublime-syntax'
            else:
                # Interpret as both name and syntax
                name = syntax
                syntax += '.sublime-syntax'

            _match = next(
                (
                    _syn.path
                    for _syn in sb.list_syntaxes()
                    if (_syn.path.endswith(path) or _syn.scope == scope or _syn.name == name)
                ),
                None,
            )
            if _match is None:
                raise ValueError(f'Could not find syntax matching "{syntax}".')
            syntax = _match

        if not syntax:
            raise ValueError('Syntax string cannot be empty.')
        return syntax
    else:
        raise ValueError(f'Expected syntax to be a str or Syntax object, got {type(syntax)}.')


class TypesMixin:
    """Mixin class providing type annotations for various usefule types (API or otherwise).

    This class is subclassed by `Utils`, so you'll likely never have to interact with it directly.
    """

    schemify = schemify

    RegionField = Annotated[sb.Region, schemify(sb.Region)]
    SelectionField = Annotated[sb.Selection, schemify(sb.Selection)]

    ViewField = Annotated[sb.View, schemify(sb.View)]
    BufferField = Annotated[sb.Buffer, schemify(sb.Buffer)]
    WindowField = Annotated[sb.Window, schemify(sb.Window)]
    EditField = Annotated[sb.Edit, schemify(sb.Edit)]
    SheetField = Annotated[sb.Sheet, schemify(sb.Sheet)]
    HtmlSheetField = Annotated[sb.HtmlSheet, schemify(sb.HtmlSheet)]

    CommandField = Annotated[sbp.Command, schemify(sbp.Command)]
    TextCommandField = Annotated[sbp.TextCommand, schemify(sbp.TextCommand)]
    WindowCommandField = Annotated[sbp.WindowCommand, schemify(sbp.WindowCommand)]
    ApplicationCommandField = Annotated[sbp.ApplicationCommand, schemify(sbp.ApplicationCommand)]

    ListenerField = Annotated[sbp.EventListener, schemify(sbp.EventListener)]
    TextChangeListenerField = Annotated[sbp.TextChangeListener, schemify(sbp.TextChangeListener)]
    ViewEventListenerField = Annotated[sbp.ViewEventListener, schemify(sbp.ViewEventListener)]

    InputHandlerField = Annotated[sbp.CommandInputHandler, schemify(sbp.CommandInputHandler)]
    TextInputHandlerField = Annotated[sbp.TextInputHandler, schemify(sbp.TextInputHandler)]
    ListInputHandlerField = Annotated[sbp.ListInputHandler, schemify(sbp.ListInputHandler)]

    # Non-sublime types
    RegexField = Annotated[re.Pattern, schemify(re.Pattern)]
    TextIOField = Annotated[TextIO, schemify(TextIO)]

    # Non-trivial types
    SyntaxField = Annotated[str, pyd.BeforeValidator(_validate_syntax)]
