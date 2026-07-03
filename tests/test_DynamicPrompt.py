############
### HEAD ###
############
### STANDARD
from __future__ import annotations
from typing import Any

### EXTERNAL
import pytest as pyt
import pydantic as pyd
import sublime as sb

### INTERNAL
from myBasis.types.DynamicPrompt import DynamicPrompt, ListHandler, NO_RESULTS


############
### DATA ###
############
class _FakeCommand:
    """A minimal stand-in for a ``_MyViewCommand`` exposing generator methods."""

    def __init__(self) -> None:
        self.calls: list[dict] = []

    def make_items(self, **kwargs: Any) -> list[str]:
        self.calls.append(kwargs)
        return ['alpha', 'beta']

    not_callable = 'just a string'


############
### BODY ###
############
class TestConstruction:
    """Tests for DynamicPrompt construction (inherits StaticPrompt validation)."""

    def test_requires_generator(self):
        with pyt.raises(pyd.ValidationError):
            DynamicPrompt(keyword='pick')

    def test_accepts_callable_generator(self):
        dp = DynamicPrompt(keyword='pick', generator=lambda: ['a'])
        assert callable(dp.generator)

    def test_accepts_str_generator(self):
        dp = DynamicPrompt(keyword='pick', generator='make_items')
        assert dp.generator == 'make_items'

    def test_inherits_static_prompt_classname(self):
        dp = DynamicPrompt(keyword='pick_one', generator='make_items')
        assert dp.classname == 'PickOneInputHandler'


class TestListItemKind:
    """Tests for the ``ListItemKind`` metadata NamedTuple."""

    def test_defaults(self):
        kind = DynamicPrompt.ListItemKind()
        assert kind.kind == sb.KindId.AMBIGUOUS
        assert kind.char == ''
        assert kind.name == ''

    def test_fields(self):
        kind = DynamicPrompt.ListItemKind(kind=sb.KindId.FUNCTION, char='f', name='func')
        assert (kind.kind, kind.char, kind.name) == (sb.KindId.FUNCTION, 'f', 'func')


class TestGenerateInputHandlerCallable:
    """A callable generator becomes the handler's ``list_items``."""

    def test_produces_list_handler_subclass(self):
        dp = DynamicPrompt(keyword='pick', generator=lambda: ['a', 'b'])
        handler_cls = dp.generate_input_handler(command=_FakeCommand(), raw_args={})
        assert isinstance(handler_cls, type)
        assert issubclass(handler_cls, ListHandler)

    def test_list_items_returns_generator_output(self):
        dp = DynamicPrompt(keyword='pick', generator=lambda: ['a', 'b'])
        handler = dp.generate_input_handler(command=_FakeCommand(), raw_args={})()
        assert handler.list_items() == ['a', 'b']

    def test_callable_branch_announces_itself(self, capsys: pyt.CaptureFixture):
        dp = DynamicPrompt(keyword='pick', generator=list)
        dp.generate_input_handler(command=_FakeCommand(), raw_args={})
        assert 'Using generator function' in capsys.readouterr().out

    def test_name_comes_from_keyword(self):
        dp = DynamicPrompt(keyword='pick', generator=list)
        handler = dp.generate_input_handler(command=_FakeCommand(), raw_args={})()
        assert handler.name() == 'pick'

    def test_static_prompt_features_still_apply(self):
        dp = DynamicPrompt(keyword='pick', generator=list, placeholder='Choose...')
        handler = dp.generate_input_handler(command=_FakeCommand(), raw_args={})()
        assert handler.placeholder() == 'Choose...'


class TestGenerateInputHandlerBoundMethod:
    """A string generator resolves to a bound method on the command."""

    def test_list_items_calls_bound_method(self):
        command = _FakeCommand()
        dp = DynamicPrompt(keyword='pick', generator='make_items')
        handler = dp.generate_input_handler(command=command, raw_args={})()
        assert handler.list_items() == ['alpha', 'beta']
        assert command.calls == [{}]

    def test_raw_args_forwarded_as_kwargs(self):
        command = _FakeCommand()
        dp = DynamicPrompt(keyword='pick', generator='make_items')
        handler = dp.generate_input_handler(command=command, raw_args={'depth': 2})()
        handler.list_items()
        assert command.calls == [{'depth': 2}]

    def test_missing_method_asserts(self):
        dp = DynamicPrompt(keyword='pick', generator='no_such_method')
        with pyt.raises(AssertionError, match='does not exist'):
            dp.generate_input_handler(command=_FakeCommand(), raw_args={})

    def test_non_callable_attribute_asserts(self):
        dp = DynamicPrompt(keyword='pick', generator='not_callable')
        with pyt.raises(AssertionError, match='is not callable'):
            dp.generate_input_handler(command=_FakeCommand(), raw_args={})


class TestNoResults:
    """The NO_RESULTS sentinel is a usable fallback item list."""

    def test_shape(self):
        assert len(NO_RESULTS) == 1
        assert NO_RESULTS[0].text == 'No Results'
        assert NO_RESULTS[0].value == ''
