############
### HEAD ###
############
### STANDARD
from __future__ import annotations
from typing import Any
from pathlib import Path
import inspect
import sys
import itertools as it

### EXTERNAL
import regex as re

### INTERNAL
from .utils import ut

############
### DATA ###
############k
NO_ESC = r'(?<![^\\]\\)(?<!\\{3})'

RGXS: dict[str, re.Pattern] = ut.rgx_dict(
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

__all__ = ['NO_ESC', 'RGXS', 'EVENTS', 'ASYNCABLE_EVENTS']
