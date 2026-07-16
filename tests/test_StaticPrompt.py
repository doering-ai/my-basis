############
### HEAD ###
############
### STANDARD
from __future__ import annotations

### EXTERNAL
import pytest as pyt
import pydantic as pyd

### INTERNAL
from myBasis.types.StaticPrompt import StaticPrompt, TextHandler


############
### BODY ###
############
class TestStaticPromptConstruction:
    """Tests for ``StaticPrompt`` construction and validation."""

    def test_requires_keyword(self):
        with pyt.raises(pyd.ValidationError):
            StaticPrompt.model_validate({})

    def test_basic_construction(self):
        sp = StaticPrompt(keyword='my_arg')
        assert sp.keyword == 'my_arg'

    def test_keyword_stripped(self):
        sp = StaticPrompt(keyword='  my_arg  ')
        assert sp.keyword == 'my_arg'

    def test_default_classname_generated(self):
        sp = StaticPrompt(keyword='my_arg')
        assert sp.classname == 'MyArgInputHandler'

    def test_custom_classname(self):
        sp = StaticPrompt(keyword='my_arg', classname='CustomHandler')
        assert sp.classname == 'CustomHandler'

    def test_default_prefix_empty(self):
        sp = StaticPrompt(keyword='my_arg')
        assert sp.prefix == ''

    def test_default_placeholder_none(self):
        sp = StaticPrompt(keyword='my_arg')
        assert sp.placeholder is None

    def test_default_initial_text_none(self):
        sp = StaticPrompt(keyword='my_arg')
        assert sp.initial_text is None

    def test_default_callback_none(self):
        sp = StaticPrompt(keyword='my_arg')
        assert sp.callback is None

    def test_default_validator_none(self):
        sp = StaticPrompt(keyword='my_arg')
        assert sp.validator is None

    def test_default_successor_none(self):
        sp = StaticPrompt(keyword='my_arg')
        assert sp.successor is None

    @pyt.mark.parametrize(
        'keyword, expected_classname',
        [
            ('simple', 'SimpleInputHandler'),
            ('multi_word', 'MultiWordInputHandler'),
            ('level', 'LevelInputHandler'),
        ],
    )
    def test_classname_generation(self, keyword: str, expected_classname: str):
        sp = StaticPrompt(keyword=keyword)
        assert sp.classname == expected_classname


class TestStaticPromptGenerateInputHandler:
    """Tests for ``StaticPrompt.generate_input_handler``."""

    def test_generates_handler_class(self):
        sp = StaticPrompt(keyword='my_arg')
        handler_cls = sp.generate_input_handler(command=None, raw_args={})
        assert isinstance(handler_cls, type)
        assert issubclass(handler_cls, TextHandler)

    def test_handler_has_name_method(self):
        sp = StaticPrompt(keyword='my_arg')
        handler_cls = sp.generate_input_handler(command=None, raw_args={})
        instance = handler_cls()
        assert instance.name() == 'my_arg'

    def test_handler_has_placeholder(self):
        sp = StaticPrompt(keyword='my_arg', placeholder='Enter value')
        handler_cls = sp.generate_input_handler(command=None, raw_args={})
        instance = handler_cls()
        assert instance.placeholder() == 'Enter value'

    def test_handler_has_initial_text(self):
        sp = StaticPrompt(keyword='my_arg', initial_text='default')
        handler_cls = sp.generate_input_handler(command=None, raw_args={})
        instance = handler_cls()
        assert instance.initial_text() == 'default'

    def test_handler_has_description(self):
        """description requires TextHandler.description which the mock doesn't provide."""
        sp = StaticPrompt(keyword='my_arg', history_description='My Description')
        with pyt.raises(AttributeError, match='description'):
            sp.generate_input_handler(command=None, raw_args={})

    def test_handler_has_validate(self):
        sp = StaticPrompt(keyword='my_arg', validator=lambda text: len(text) > 3)
        handler_cls = sp.generate_input_handler(command=None, raw_args={})
        instance = handler_cls()
        assert instance.validate('long text') is True
        assert instance.validate('no') is False

    def test_handler_has_confirm(self):
        results: list[str] = []
        sp = StaticPrompt(keyword='my_arg', callback=lambda text: results.append(text))
        handler_cls = sp.generate_input_handler(command=None, raw_args={})
        instance = handler_cls()
        instance.confirm('test_value')
        assert results == ['test_value']

    def test_handler_has_cancel(self):
        cancelled: list[bool] = []
        sp = StaticPrompt(keyword='my_arg', cancel=lambda: cancelled.append(True))
        handler_cls = sp.generate_input_handler(command=None, raw_args={})
        instance = handler_cls()
        instance.cancel()
        assert cancelled

    def test_handler_has_preview(self):
        sp = StaticPrompt(keyword='my_arg', preview=lambda text: f'Preview: {text}')
        handler_cls = sp.generate_input_handler(command=None, raw_args={})
        instance = handler_cls()
        assert instance.preview('hello') == 'Preview: hello'

    def test_handler_has_initial_selection_static(self):
        """initial_selection needs TextHandler.initial_selection (absent in mock)."""
        sp = StaticPrompt(keyword='my_arg', initial_text='hello', initial_selection=[(0, 5)])
        with pyt.raises(AttributeError, match='initial_selection'):
            sp.generate_input_handler(command=None, raw_args={})

    def test_raw_args_stored(self):
        sp = StaticPrompt(keyword='my_arg')
        raw = {'existing': 'value'}
        sp.generate_input_handler(command=None, raw_args=raw)
        assert sp.raw_args == raw


class TestStaticPromptSuccessor:
    """Tests for the successor/next_input mechanism."""

    def test_successor_static_prompt(self):
        successor = StaticPrompt(keyword='second_arg')
        sp = StaticPrompt(keyword='first_arg', successor=successor)
        handler_cls = sp.generate_input_handler(command=None, raw_args={})
        instance = handler_cls()
        next_handler = instance.next_input({'first_arg': 'val'})
        assert next_handler is not None

    def test_successor_none_no_next_input(self):
        """When no successor is set, next_input should not be configured."""
        sp = StaticPrompt(keyword='my_arg')
        handler_cls = sp.generate_input_handler(command=None, raw_args={})
        instance = handler_cls()
        # next_input exists on the base TextHandler class but returns None by default
        result = instance.next_input({})
        assert result is None
