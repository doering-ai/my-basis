############
### HEAD ###
############
### STANDARD

### EXTERNAL

### INTERNAL


############
### DATA ###
############
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
