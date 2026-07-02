############
### HEAD ###
############
### STANDARD
from __future__ import annotations

### EXTERNAL
import pytest as pyt
import sublime as sb
import sublime_plugin as sbp

### INTERNAL
from myBasis import (
    _MyViewCommand,
    _MyWindowCommand,
    _MyAppCommand,
    CommandArguments,
)
from myBasis.plugins._MyBase import Meta, _CustomNamespace, LineComment, Indent


############
### DATA ###
############
class _EmptyArgs(CommandArguments):
    pass


class _SimpleArgs(CommandArguments):
    level: int = 1
    title: str = 'default'


# A concrete view command for testing autobind
class _TestViewCmd(_MyViewCommand[_SimpleArgs]):
    NAME = 'test_view_cmd'

    captured_view: sb.View | None = None
    captured_edit: sb.Edit | None = None

    def main(self) -> None:
        pass

    def process(self, view: sb.View) -> None:
        """Method with a view param - should be autobound."""
        self.captured_view = view

    def process_edit(self, edit: sb.Edit) -> None:
        """Method with an edit param - should be autobound."""
        self.captured_edit = edit

    def no_args(self) -> str:
        """Method without view/buffer/window/edit - should NOT be autobound."""
        return 'no_args_result'

    def is_enabled(self, view: sb.View) -> bool:
        return True


# A concrete window command for testing
class _TestWindowCmd(_MyWindowCommand[_EmptyArgs]):
    NAME = 'test_window_cmd'

    def main(self) -> None:
        pass


# A concrete app command for testing
class _TestAppCmd(_MyAppCommand[_EmptyArgs]):
    NAME = 'test_app_cmd'

    def main(self) -> None:
        pass


############
### BODY ###
############
class TestCustomNamespace:
    """Tests for ``_CustomNamespace``."""

    def test_setitem_normal(self):
        ns = _CustomNamespace()
        ns['key'] = 'value'
        assert ns['key'] == 'value'

    def test_setitem_property_replaces(self):
        ns = _CustomNamespace()
        ns['key'] = 'value'
        # A property should replace the plain value
        prop = property(lambda self: 'prop_value')
        ns['key'] = prop
        assert ns['key'] is prop

    def test_setitem_property_does_not_replace_property(self):
        """A non-property value does not replace an existing property."""
        ns = _CustomNamespace()
        prop1 = property(lambda self: 'first')
        ns['key'] = prop1
        # Setting a plain value should NOT replace the property
        ns['key'] = 'plain_value'
        assert ns['key'] is prop1


class TestMetaFindSublimeBase:
    """Tests for ``Meta.find_sublime_base``."""

    def test_finds_text_command(self):
        base = Meta.find_sublime_base((_MyViewCommand,))
        assert base is sbp.TextCommand

    def test_finds_window_command(self):
        base = Meta.find_sublime_base((_MyWindowCommand,))
        assert base is sbp.WindowCommand

    def test_finds_app_command(self):
        base = Meta.find_sublime_base((_MyAppCommand,))
        assert base is sbp.ApplicationCommand

    def test_returns_none_for_plain_class(self):
        base = Meta.find_sublime_base((object,))
        assert base is None

    def test_finds_indirect_base(self):
        """Finds the sublime base even through intermediate classes."""
        # _TestViewCmd inherits from _MyViewCommand which inherits from TextCommand
        result = Meta.find_sublime_base(_TestViewCmd.__bases__)
        assert result is sbp.TextCommand


class TestMetaDoBindMethod:
    """Tests for ``Meta.do_bind_method``."""

    def test_binds_view_param(self):
        def method(self, view: sb.View) -> None:
            pass

        assert Meta.do_bind_method(method, 'my_method', True, set())

    def test_binds_window_param(self):
        def method(self, window: sb.Window) -> None:
            pass

        assert Meta.do_bind_method(method, 'my_method', True, set())

    def test_binds_buffer_param(self):
        def method(self, buffer: sb.Buffer) -> None:
            pass

        assert Meta.do_bind_method(method, 'my_method', True, set())

    def test_binds_edit_param(self):
        def method(self, edit: sb.Edit) -> None:
            pass

        assert Meta.do_bind_method(method, 'my_method', True, set())

    def test_does_not_bind_no_relevant_params(self):
        def method(self, x: int, y: str) -> None:
            pass

        assert not Meta.do_bind_method(method, 'my_method', True, set())

    def test_does_not_bind_private_methods(self):
        def method(self, view: sb.View) -> None:
            pass

        assert not Meta.do_bind_method(method, '_private', True, set())

    def test_does_not_bind_is_methods(self):
        def method(self, view: sb.View) -> None:
            pass

        assert not Meta.do_bind_method(method, 'is_enabled', True, set())

    def test_does_not_bind_non_callable(self):
        assert not Meta.do_bind_method(42, 'value', True, set())

    def test_binds_with_explicit_list(self):
        def method(self, x: int) -> None:
            pass

        assert Meta.do_bind_method(method, 'specific_method', ['specific_method'], set())
        assert not Meta.do_bind_method(method, 'other_method', ['specific_method'], set())

    def test_returns_false_for_no_args(self):
        def method(self) -> None:
            pass

        assert not Meta.do_bind_method(method, 'no_args', True, set())


class TestMetaCacheArgs:
    """Tests for ``Meta.cache_args``."""

    def test_caches_view(self, make_view: sb.View):
        cmd = _TestViewCmd.__new__(_TestViewCmd)
        cmd._view = None
        Meta.cache_args(cmd, (make_view,), {})
        assert cmd.view is make_view

    def test_caches_window(self):
        window = sb.active_window()
        cmd = _TestWindowCmd.__new__(_TestWindowCmd)
        cmd._window = None
        Meta.cache_args(cmd, (window,), {})
        assert cmd.window is window

    def test_caches_edit(self, make_view: sb.View):
        edit = sb.Edit(make_view)
        cmd = _TestViewCmd.__new__(_TestViewCmd)
        cmd._edit = None
        Meta.cache_args(cmd, (edit,), {})
        assert cmd.edit is edit

    def test_caches_view_by_kwarg(self, make_view: sb.View):
        cmd = _TestViewCmd.__new__(_TestViewCmd)
        cmd._view = None
        Meta.cache_args(cmd, (), {'view': make_view})
        assert cmd.view is make_view

    def test_caches_none_view(self):
        cmd = _TestViewCmd.__new__(_TestViewCmd)
        cmd._view = None
        cmd._views = None
        Meta.cache_args(cmd, (), {'view': None})
        assert cmd._view is None

    def test_caches_views_list(self, make_view: sb.View):
        cmd = _TestViewCmd.__new__(_TestViewCmd)
        cmd._views = None
        views = [make_view]
        Meta.cache_args(cmd, (), {'views': views})
        assert cmd.views == views


class TestMetaCacheDetails:
    """Tests for ``Meta.cache_details``."""

    def test_returns_tuple_of_sets(self):
        names, types = Meta.cache_details()
        assert isinstance(names, set)
        assert isinstance(types, set)

    def test_contains_view(self):
        names, types = Meta.cache_details()
        assert 'view' in names
        assert sb.View in types

    def test_contains_window(self):
        names, types = Meta.cache_details()
        assert 'window' in names
        assert sb.Window in types

    def test_contains_buffer(self):
        names, types = Meta.cache_details()
        assert 'buffer' in names
        assert sb.Buffer in types

    def test_contains_edit(self):
        names, types = Meta.cache_details()
        assert 'edit' in names
        assert sb.Edit in types

    def test_caches(self):
        """cache_details uses lru_cache."""
        r1 = Meta.cache_details()
        r2 = Meta.cache_details()
        assert r1 is r2


class TestMyBaseInit:
    """Tests for ``MyBase.__init__`` and basic attributes."""

    def test_init_creates_cache(self, make_view: sb.View):
        cmd = _TestViewCmd(make_view)
        assert hasattr(cmd, '_cache')

    def test_view_set_on_view_command(self, make_view: sb.View):
        cmd = _TestViewCmd(make_view)
        assert cmd.view is make_view

    def test_window_set_on_window_command(self):
        window = sb.active_window()
        cmd = _TestWindowCmd(window)
        assert cmd.window is window


class TestMyBaseRun:
    """Tests for ``MyBase.run``."""

    def test_run_calls_main(self, make_view: sb.View):
        called: list[bool] = []

        class _Cmd(_MyViewCommand[_EmptyArgs]):
            def main(self) -> None:
                called.append(True)

        cmd = _Cmd(make_view)
        cmd.run()
        assert called

    def test_run_sets_args_from_kwargs(self, make_view: sb.View):
        class _Cmd(_MyViewCommand[_SimpleArgs]):
            received_level: int = 0

            def main(self) -> None:
                self.received_level = self.args.level

        cmd = _Cmd(make_view)
        cmd.run(level=5, title='test')
        assert cmd.received_level == 5

    def test_run_catch_propagates_by_default(self, make_view: sb.View):
        class _Cmd(_MyViewCommand[_EmptyArgs]):
            def main(self) -> None:
                raise ValueError('test error')

        cmd = _Cmd(make_view)
        with pyt.raises(ValueError, match='test error'):
            cmd.run()


class TestMyBaseInitSubclass:
    """Tests for ``MyBase.__init_subclass__``."""

    def test_sets_interface_from_generic(self):
        assert _TestViewCmd.Interface is _SimpleArgs

    def test_sets_interface_to_commandarguments_when_no_generic(self):
        class _Cmd(_MyAppCommand):
            def main(self) -> None:
                pass

        assert _Cmd.Interface is CommandArguments

    def test_window_command_interface(self):
        assert _TestWindowCmd.Interface is _EmptyArgs

    def test_app_command_interface(self):
        assert _TestAppCmd.Interface is _EmptyArgs


class TestMyBaseProperties:
    """Tests for MyBase properties."""

    def test_classname(self, make_view: sb.View):
        cmd = _TestViewCmd(make_view)
        assert cmd.classname == 'test_view_cmd'

    def test_uid_view_command(self, make_view: sb.View):
        cmd = _TestViewCmd(make_view)
        uid = cmd.uid
        assert 'test_view_cmd' in uid

    def test_uid_app_command(self):
        cmd = _TestAppCmd()
        assert cmd.uid == 'test_app_cmd'

    def test_name_uses_name_attr(self, make_view: sb.View):
        cmd = _TestViewCmd(make_view)
        assert cmd.name() == 'test_view_cmd'

    def test_prompt_is_none_by_default(self, make_view: sb.View):
        cmd = _TestViewCmd(make_view)
        assert cmd.prompt is None

    def test_prompt_with_static_prompt(self, make_view: sb.View):
        from myBasis.types.StaticPrompt import StaticPrompt

        prompt = StaticPrompt(keyword='my_arg')

        class _PromptArgs(CommandArguments):
            my_arg: str = ''

        _PromptArgs.PROMPT = prompt

        class _Cmd(_MyViewCommand[_PromptArgs]):
            def main(self) -> None:
                pass

        cmd = _Cmd(make_view)
        assert cmd.prompt is prompt

    def test_args_getter(self, make_view: sb.View):
        cmd = _TestViewCmd(make_view)
        cmd.run(level=3)
        assert cmd.args.level == 3

    def test_args_setter(self, make_view: sb.View):
        cmd = _TestViewCmd(make_view)
        new_args = _SimpleArgs(level=7, title='set')
        cmd.args = new_args
        assert cmd.args.level == 7


class TestMyBaseWithContext:
    """Tests for ``MyBase.with_context``."""

    def test_with_context_view(self):
        """Window commands allow view overrides (_ALLOW_OVERRIDES = True)."""
        window = sb.active_window()
        cmd = _TestWindowCmd(window)
        view1 = window.new_file()
        view2 = window.new_file()
        try:
            with cmd.with_context(view=view1):
                assert cmd.view is view1
            # After context, view is restored to None (was not set before)
        finally:
            view1.set_scratch(True)
            view1.close()
            view2.set_scratch(True)
            view2.close()

    def test_with_context_window(self):
        """Test with_context for window parameter."""
        window = sb.active_window()
        cmd = _TestAppCmd()
        with cmd.with_context(window=window):
            assert cmd.window is window
        # After context, window restored


class TestMyBaseMain:
    """Tests for ``MyBase.main`` default behavior."""

    def test_main_raises_not_implemented(self, make_view: sb.View):
        class _Cmd(_MyViewCommand[_EmptyArgs]):
            pass

        cmd = _Cmd(make_view)
        with pyt.raises(NotImplementedError):
            cmd.main()


class TestLineComment:
    """Tests for the ``LineComment`` NamedTuple."""

    def test_fields(self):
        lc = LineComment(region=sb.Region(0, 10), row=0, col=1, text='hello', punct='#')
        assert lc.region == sb.Region(0, 10)
        assert lc.row == 0
        assert lc.col == 1
        assert lc.text == 'hello'
        assert lc.punct == '#'

    def test_split_true_different_row(self):
        lc1 = LineComment(sb.Region(0, 5), 0, 1, 'a', '#')
        lc2 = LineComment(sb.Region(6, 10), 2, 1, 'b', '#')
        assert lc1.split(lc2)

    def test_split_false_same_row(self):
        lc1 = LineComment(sb.Region(0, 5), 0, 1, 'a', '#')
        lc2 = LineComment(sb.Region(6, 10), 1, 1, 'b', '#')
        assert not lc1.split(lc2)

    def test_split_false_different_col(self):
        lc1 = LineComment(sb.Region(0, 5), 0, 1, 'a', '#')
        lc2 = LineComment(sb.Region(6, 10), 1, 2, 'b', '#')
        assert lc1.split(lc2)

    def test_split_false_different_punct(self):
        lc1 = LineComment(sb.Region(0, 5), 0, 1, 'a', '#')
        lc2 = LineComment(sb.Region(6, 10), 1, 1, 'b', '//')
        assert lc1.split(lc2)


class TestIndent:
    """Tests for the ``Indent`` NamedTuple."""

    def test_fields(self):
        ind = Indent(row=5, val=4)
        assert ind.row == 5
        assert ind.val == 4

    def test_equality(self):
        assert Indent(1, 2) == Indent(1, 2)
        assert Indent(1, 2) != Indent(1, 3)
