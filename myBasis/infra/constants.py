############
### HEAD ###
############
### STANDARD
from __future__ import annotations

### EXTERNAL
import regex as re
import sublime as sb

### INTERNAL
from .utils import Utils

############
### DATA ###
############k
NO_ESC = r'(?<![^\\]\\)(?<!\\{3})'

RGXS: dict[str, re.Pattern] = Utils.rgx_dict(
    snake_separators=r'(?<=[[:alnum:]])_(?=[[:alnum:]])',
)

EVENTS = dict(
    views=['init'],
    none=['exit'],
    view=[
        'new',
        'clone',
        'load',
        'reload',
        'revert',
        'pre_move',
        'post_move',
        'pre_close',
        'close',
        'save',
        'pre_save',
        'post_save',
        'modified',
        'selection_modified',
        'activated',
        'deactivated',
        'hover',
        'query_context',
        'query_completions',
        'text_command',
    ],
    window=[
        'window_command',
        'post_text_command',
        'post_window_command',
        'new_window',
        'pre_close_window',
        'new_project',
        'load_project',
        'pre_save_project',
        'post_save_project',
        'pre_close_project',
    ],
    buffer=[
        'associate_buffer',
    ],
)

ASYNCABLE_EVENTS = {
    'new',
    'clone',
    'load',
    'reload',
    'revert',
    'post_move',
    'pre_save',
    'post_save',
    'modified',
    'selection_modified',
    'activated',
    'deactivated',
    'new_window',
    'new_project',
    'load_project',
    'post_save_project',
    'associate_buffer',
}

KindId = sb.KindId

KIND_ARRAY = (KindId.TYPE, 'a', 'Array')
KIND_BOOLEAN = (KindId.VARIABLE, 'b', 'Boolean')
KIND_CLASS = (KindId.TYPE, 'c', 'Class')
KIND_COLOR = (KindId.MARKUP, 'c', 'Color')
KIND_CONSTANT = (KindId.VARIABLE, 'c', 'Constant')
KIND_CONSTRUCTOR = (KindId.FUNCTION, 'c', 'Constructor')
KIND_ENUM = (KindId.TYPE, 'e', 'Enum')
KIND_ENUMMEMBER = (KindId.VARIABLE, 'e', 'Enum Member')
KIND_EVENT = (KindId.FUNCTION, 'e', 'Event')
KIND_FIELD = (KindId.VARIABLE, 'f', 'Field')
KIND_FILE = (KindId.NAVIGATION, 'f', 'File')
KIND_FOLDER = (KindId.NAVIGATION, 'f', 'Folder')
KIND_FUNCTION = (KindId.FUNCTION, 'f', 'Function')
KIND_INTERFACE = (KindId.TYPE, 'i', 'Interface')
KIND_KEY = (KindId.NAVIGATION, 'k', 'Key')
KIND_KEYWORD = (KindId.KEYWORD, 'k', 'Keyword')
KIND_METHOD = (KindId.FUNCTION, 'm', 'Method')
KIND_MODULE = (KindId.NAMESPACE, 'm', 'Module')
KIND_NAMESPACE = (KindId.NAMESPACE, 'n', 'Namespace')
KIND_NULL = (KindId.VARIABLE, 'n', 'Null')
KIND_NUMBER = (KindId.VARIABLE, 'n', 'Number')
KIND_OBJECT = (KindId.TYPE, 'o', 'Object')
KIND_OPERATOR = (KindId.KEYWORD, 'o', 'Operator')
KIND_PACKAGE = (KindId.NAMESPACE, 'p', 'Package')
KIND_PROPERTY = (KindId.VARIABLE, 'p', 'Property')
KIND_REFERENCE = (KindId.NAVIGATION, 'r', 'Reference')
KIND_SNIPPET = (KindId.SNIPPET, 's', 'Snippet')
KIND_STRING = (KindId.VARIABLE, 's', 'String')
KIND_STRUCT = (KindId.TYPE, 's', 'Struct')
KIND_TEXT = (KindId.MARKUP, 't', 'Text')
KIND_TYPEPARAMETER = (KindId.TYPE, 't', 'Type Parameter')
KIND_UNIT = (KindId.VARIABLE, 'u', 'Unit')
KIND_VALUE = (KindId.VARIABLE, 'v', 'Value')
KIND_VARIABLE = (KindId.VARIABLE, 'v', 'Variable')
