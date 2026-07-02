############
### HEAD ###
############
### STANDARD
from __future__ import annotations

### EXTERNAL
import pydantic as pyd

### INTERNAL
from myBasis.types.CommandArguments import CommandArguments
from myBasis.types.StaticPrompt import StaticPrompt


############
### BODY ###
############
class TestCommandArguments:
    """Tests for the ``CommandArguments`` pydantic model."""

    def test_is_pydantic_model(self):
        assert issubclass(CommandArguments, pyd.BaseModel)

    def test_prompt_default_is_none(self):
        assert CommandArguments.PROMPT is None

    def test_can_instantiate_empty(self):
        args = CommandArguments()
        assert args.model_dump() == {}

    def test_can_instantiate_with_fields(self):
        class _Args(CommandArguments):
            level: int = 1
            title: str = 'test'

        args = _Args(level=2, title='hello')
        assert args.level == 2
        assert args.title == 'hello'

    def test_subclass_prompt(self):
        """PROMPT is a ClassVar on CommandArguments, accessible on subclasses."""
        prompt = StaticPrompt(keyword='my_arg')
        assert prompt is not None

        class _Args(CommandArguments):
            my_arg: str = ''

        _Args.PROMPT = prompt
        assert _Args.PROMPT is prompt

    def test_subclass_without_prompt(self):
        class _Args(CommandArguments):
            value: int = 0

        assert _Args.PROMPT is None


class TestInterpolate:
    """Tests for ``CommandArguments._interpolate``."""

    def test_no_character_key_noop(self):
        data = {'key': 'value', 'other': 42}
        original = dict(data)
        CommandArguments._interpolate(data)
        assert data == original

    def test_replaces_character_in_string(self):
        data = {'character': 'x', 'target': '<character> + y'}
        CommandArguments._interpolate(data)
        assert data['target'] == 'x + y'

    def test_replaces_character_and_converts_digit(self):
        data = {'character': '5', 'target': '<character>'}
        CommandArguments._interpolate(data)
        assert data['target'] == 5
        assert isinstance(data['target'], int)

    def test_multiple_replacements(self):
        data = {'character': 'a', 'first': '<character>_1', 'second': '<character>_2'}
        CommandArguments._interpolate(data)
        assert data['first'] == 'a_1'
        assert data['second'] == 'a_2'

    def test_no_placeholder_unchanged(self):
        data = {'character': 'x', 'target': 'no placeholder here'}
        CommandArguments._interpolate(data)
        assert data['target'] == 'no placeholder here'

    def test_interpolates_in_nested_dict(self):
        """Nested dicts are interpolated in-place but need their own 'character' key."""
        data = {'character': 'z', 'nested': {'character': 'z', 'inner': '<character>_val'}}
        CommandArguments._interpolate(data)
        assert data['nested']['inner'] == 'z_val'

    def test_interpolates_in_list(self):
        data = {'character': 'w', 'items': ['<character>', 'static', '<character>_end']}
        CommandArguments._interpolate(data)
        assert data['items'][0] == 'w'
        assert data['items'][1] == 'static'
        assert data['items'][2] == 'w_end'

    def test_interpolates_digit_in_list(self):
        data = {'character': '7', 'items': ['<character>']}
        CommandArguments._interpolate(data)
        assert data['items'][0] == 7
        assert isinstance(data['items'][0], int)

    def test_empty_character_value(self):
        data = {'character': '', 'target': '<character>_test'}
        CommandArguments._interpolate(data)
        assert data['target'] == '_test'

    def test_does_not_affect_non_string_values(self):
        data = {'character': 'x', 'num': 42, 'flag': True}
        CommandArguments._interpolate(data)
        assert data['num'] == 42
        assert data['flag'] is True
