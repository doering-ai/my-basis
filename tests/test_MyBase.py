############
### HEAD ###
############
### STANDARD
from __future__ import annotations
from typing import Any, cast
import asyncio
import logging
import time
import warnings

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
    Comment,
)
from myBasis.plugins._MyBase import Meta, _CustomNamespace, LineComment, Indent

_Edit = cast('Any', sb.Edit)


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
        """A leading `view` param — autobound via signature-based implicit binding."""
        self.captured_view = view

    def process_edit(self, edit: sb.Edit) -> None:
        """A leading `edit` param — autobound via signature-based implicit binding."""
        self.captured_edit = edit

    def no_args(self) -> str:
        """Method without view/buffer/window/edit - should NOT be autobound."""
        return 'no_args_result'

    def helper(self, x: int, y: str = '') -> str:
        """Neither the name nor a leading view/edit/window param -> never autobound."""
        return f'{x}{y}'

    def is_enabled(self, **kwargs: Any) -> bool:
        return True


# A view command whose capture methods ARE autobound, via the explicit autobind list
class _AutobindViewCmd(_MyViewCommand[_SimpleArgs], autobind=['process', 'process_edit']):
    NAME = 'autobind_view_cmd'

    captured_view: sb.View | None = None
    captured_edit: sb.Edit | None = None

    def main(self) -> None:
        pass

    def process(self, view: sb.View) -> None:
        self.captured_view = view

    def process_edit(self, edit: sb.Edit) -> None:
        self.captured_edit = edit

    def unlisted_edit(self, edit: sb.Edit) -> None:
        """Not named in the autobind list, so it must stay unwrapped."""
        self.captured_edit = edit


# A view command with autobind disabled entirely — even signature-named methods stay unwrapped
class _NoAutobindViewCmd(_MyViewCommand[_SimpleArgs], autobind=False):
    NAME = 'no_autobind_view_cmd'

    captured_view: sb.View | None = None
    captured_edit: sb.Edit | None = None

    def main(self) -> None:
        pass

    def process(self, view: sb.View) -> None:
        """`autobind=False` must leave even a signature-named method unwrapped."""
        self.captured_view = view

    def process_edit(self, edit: sb.Edit) -> None:
        self.captured_edit = edit


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

    # -- signature-based implicit binding (non-empty sb_attrs, name not a base-class attr) --

    def test_binds_leading_view_param_not_in_sb_attrs(self):
        """A method whose name is unknown to the Sublime base class is still autobound
        via signature-based implicit binding when its leading param is named `view`."""

        def process(self, view: sb.View) -> None:
            pass

        assert Meta.do_bind_method(process, 'process', True, {'run', 'description'})

    def test_binds_leading_edit_param_not_in_sb_attrs(self):
        def process_edit(self, edit: sb.Edit) -> None:
            pass

        assert Meta.do_bind_method(process_edit, 'process_edit', True, {'run', 'description'})

    def test_binds_leading_window_param_not_in_sb_attrs(self):
        def process_window(self, window: sb.Window) -> None:
            pass

        assert Meta.do_bind_method(process_window, 'process_window', True, {'run', 'description'})

    def test_does_not_bind_leading_buffer_param_not_in_sb_attrs(self):
        """`buffer` is deliberately excluded from signature-based implicit binding — only
        `view`/`edit`/`window` leading params trigger it for non-base-class method names."""

        def process_buffer(self, buffer: sb.Buffer) -> None:
            pass

        assert not Meta.do_bind_method(
            process_buffer, 'process_buffer', True, {'run', 'description'}
        )

    def test_does_not_bind_non_signature_method_not_in_sb_attrs(self):
        """No false positive: an unrecognized name with unrelated leading params stays unwrapped."""

        def helper(self, x: int, y: str) -> str:
            return f'{x}{y}'

        assert not Meta.do_bind_method(helper, 'helper', True, {'run', 'description'})

    def test_does_not_bind_trailing_view_param_not_in_sb_attrs(self):
        """Only the *leading* param counts — a `view` param that isn't first does not qualify."""

        def process(self, count: int, view: sb.View) -> None:
            pass

        assert not Meta.do_bind_method(process, 'process', True, {'run', 'description'})

    # -- MEMY-76: signature edge cases (keyword-only leading param; `view` after `*args`) --

    def test_binds_keyword_only_leading_view_param(self):
        """A keyword-only leading param (`def process(self, *, view)`) still autobinds:
        `view` is the first parameter capable of carrying a meaningful name, even though
        it can only be passed by keyword. Verifies the contract -- not just documents the
        prior implementation's incidental behavior."""

        def process(self, *, view: sb.View) -> None:
            pass

        assert Meta.do_bind_method(process, 'process', True, {'run', 'description'})

    def test_binds_view_param_after_var_positional_args(self):
        """`view` following a `*args` catch-all (`def process(self, *args, view=None)`)
        autobinds: `*args` carries no meaningful name, so it is skipped when scanning for
        the first binding-relevant parameter, and `view` -- the next one -- qualifies."""

        def process(self, *args: Any, view: sb.View | None = None) -> None:
            pass

        assert Meta.do_bind_method(process, 'process', True, {'run', 'description'})

    def test_does_not_bind_var_positional_only_no_view(self):
        """A bare `*args` catch-all with no named `view`/`edit`/`window` afterward must not
        autobind -- there is no binding-relevant parameter to match against."""

        def process(self, *args: Any) -> None:
            pass

        assert not Meta.do_bind_method(process, 'process', True, {'run', 'description'})

    def test_binds_base_class_name_regardless_of_signature(self):
        """A method named after a real base-class attribute is bound via the original
        name/annotation check, unaffected by the new signature-based path."""

        def run(self, view: sb.View) -> None:
            pass

        assert Meta.do_bind_method(run, 'run', True, {'run', 'description'})

    def test_explicit_list_unaffected_by_signature_based_binding(self):
        """`autobind=[...]` semantics stay exactly as they were: only listed names bind,
        signature-based implicit binding never applies."""

        def process(self, view: sb.View) -> None:
            pass

        assert not Meta.do_bind_method(process, 'process', ['other_method'], {'run'})


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
        edit = _Edit(make_view)
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

    def test_split_true_different_col(self):
        """Adjacent rows but different columns start a new block."""
        lc1 = LineComment(sb.Region(0, 5), 0, 1, 'a', '#')
        lc2 = LineComment(sb.Region(6, 10), 1, 2, 'b', '#')
        assert lc1.split(lc2)

    def test_split_true_different_punct(self):
        """Adjacent rows but different punctuation start a new block."""
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


class TestLogDebugGating:
    """Debug messages are emitted exactly when the class has DEBUG enabled."""

    def test_debug_suppressed_when_debug_off(self, capsys: pyt.CaptureFixture):
        assert _TestViewCmd.DEBUG is False
        _TestViewCmd._log('hidden-debug-msg', log_level=logging.DEBUG)
        assert 'hidden-debug-msg' not in capsys.readouterr().out

    def test_debug_emitted_when_debug_on(self, capsys: pyt.CaptureFixture):
        class _DbgCmd(_MyViewCommand[_EmptyArgs], debug=True):
            def main(self) -> None:
                pass

        assert _DbgCmd.DEBUG is True
        _DbgCmd._log('visible-debug-msg', log_level=logging.DEBUG)
        assert 'visible-debug-msg' in capsys.readouterr().out

    def test_info_emitted_regardless(self, capsys: pyt.CaptureFixture):
        _TestViewCmd._log('info-msg', log_level=logging.INFO)
        assert 'info-msg' in capsys.readouterr().out


class TestViewProperty:
    """The `view` property must return the explicitly-set view, not `views[0]`."""

    def test_view_returns_explicit_view_not_first(self):
        window = sb.active_window()
        cmd = _TestWindowCmd(window)
        view1 = window.new_file()
        view2 = window.new_file()
        try:
            cmd.views = [view1, view2]
            cmd.view = view2
            assert cmd.view is view2, 'view property must return _view, not views[0]'
        finally:
            for v in (view1, view2):
                v.set_scratch(True)
                v.close()


class TestInvoke:
    """Tests for ``invoke`` / ``invoke_async`` argument forwarding."""

    @staticmethod
    def _capture(view: sb.View) -> dict[str, Any]:
        recorded: dict[str, Any] = {}

        def fake_run_command(name: str, args: 'dict | None' = None) -> None:
            recorded['name'] = name
            recorded['args'] = args

        view.run_command = fake_run_command  # type: ignore[method-assign]
        return recorded

    def test_invoke_does_not_leak_internal_kwargs(self, make_view: sb.View):
        cmd = _TestViewCmd(make_view)
        recorded = self._capture(make_view)
        cmd.invoke('foo_cmd', bar=1)  # mock set_timeout runs synchronously
        assert recorded['name'] == 'foo_cmd'
        assert recorded['args'] == {'bar': 1}

    def test_invoke_async_does_not_leak_async_flag(self, make_view: sb.View):
        cmd = _TestViewCmd(make_view)
        recorded = self._capture(make_view)
        asyncio.run(cmd.invoke_async('foo_cmd', bar=1))
        assert recorded['name'] == 'foo_cmd'
        assert '_async' not in (recorded['args'] or {}), '_async must not reach the command args'
        assert recorded['args'] == {'bar': 1}

    def test_invoke_async_flag_routes_to_async_timeout(
        self, make_view: sb.View, monkeypatch: pyt.MonkeyPatch
    ):
        used: list[int] = []

        def fake_timeout_async(cb: Any, delay: int = 0) -> None:
            used.append(delay)
            cb()

        monkeypatch.setattr(sb, 'set_timeout_async', fake_timeout_async)
        cmd = _TestViewCmd(make_view)
        recorded = self._capture(make_view)
        cmd.invoke('foo_cmd', _async=True, bar=2)
        assert used, '_async=True must schedule via sublime.set_timeout_async'
        assert recorded['args'] == {'bar': 2}


class TestFilterComments:
    """``filter_comments`` must yield Comment objects on every branch."""

    @staticmethod
    def _comment(row: int, start: int, end: int) -> Comment:
        return Comment(lines=[sb.Region(start, end)], texts=['text'], row=row, col=1)

    def _make_cmd(self, view: sb.View) -> Any:
        c0 = self._comment(0, 0, 5)
        c2 = self._comment(2, 10, 15)
        comments = {0: c0, 2: c2}

        class _CommentsCmd(_MyViewCommand[_EmptyArgs]):
            line_comments = property(lambda self: comments)

            def main(self) -> None:
                pass

        return _CommentsCmd(view), c0, c2

    def test_no_filters_yields_comments(self, make_view: sb.View):
        cmd, c0, c2 = self._make_cmd(make_view)
        result = list(cmd.filter_comments())
        assert result == [c0, c2]
        assert all(isinstance(c, Comment) for c in result)

    def test_filtered_yields_comments(self, make_view: sb.View):
        cmd, _c0, c2 = self._make_cmd(make_view)
        result = list(cmd.filter_comments(lambda c: c.row == 2))
        assert result == [c2]
        assert all(isinstance(c, Comment) for c in result)


class _FakeLoadingView:
    """A view whose ``is_loading`` walks through a scripted sequence of states."""

    def __init__(self, states: 'list[bool]') -> None:
        self._states = list(states)
        self.polls = 0

    def is_loading(self) -> bool:
        self.polls += 1
        return self._states.pop(0) if self._states else False


class _FakeWindow:
    def __init__(self, view: _FakeLoadingView) -> None:
        self._view = view
        self.opened: 'tuple | None' = None

    def open_file(self, path: str, flags: int = 0, group: int = -1) -> _FakeLoadingView:
        self.opened = (path, group)
        return self._view


class TestOpen:
    """``open`` must wait *while* the view is loading, and not block for loaded files."""

    def test_loaded_file_returns_immediately(self, tmp_path):
        cmd = _TestAppCmd()
        fake_view = _FakeLoadingView([False])
        fake_window = _FakeWindow(fake_view)
        start = time.monotonic()
        with warnings.catch_warnings():
            warnings.simplefilter('error')  # the 3s-load warning must not fire
            view = cmd.open(tmp_path / 'file.txt', window=fake_window)  # type: ignore[arg-type]
        assert view is fake_view
        assert time.monotonic() - start < 1.0, 'loaded files must not block ~3s'

    def test_loading_file_is_polled_until_ready(self, tmp_path):
        cmd = _TestAppCmd()
        fake_view = _FakeLoadingView([True, True, False])
        fake_window = _FakeWindow(fake_view)
        view = cmd.open(tmp_path / 'file.txt', window=fake_window)  # type: ignore[arg-type]
        assert view is fake_view
        assert fake_view.polls >= 3, 'open() must poll is_loading() until it turns False'


class TestAutobindEndToEnd:
    """Drive autobound methods end-to-end: the Meta wrapper must cache args before the body."""

    def test_process_receives_and_caches_view(self, make_view: sb.View):
        """Calling `process(view)` on a bare instance both runs the body and caches the view."""
        cmd = _AutobindViewCmd.__new__(_AutobindViewCmd)
        cmd._view = None
        cmd._views = None
        cmd.process(make_view)
        assert cmd.captured_view is make_view, 'the method body must still receive the view'
        assert cmd.view is make_view, 'the Meta wrapper must have cached the view'

    def test_process_caches_view_by_kwarg(self, make_view: sb.View):
        cmd = _AutobindViewCmd.__new__(_AutobindViewCmd)
        cmd._view = None
        cmd._views = None
        cmd.process(view=make_view)
        assert cmd.captured_view is make_view
        assert cmd.view is make_view

    def test_process_edit_caches_edit(self, make_view: sb.View):
        """The edit handle is cached by the wrapper alone — the body never touches `self.edit`."""
        cmd = _AutobindViewCmd(make_view)
        edit = _Edit(make_view)
        assert not cmd.has_edit()
        cmd.process_edit(edit)
        assert cmd.captured_edit is edit
        assert cmd.has_edit(), 'the Meta wrapper must have cached the edit token'
        assert cmd.edit is edit

    def test_unlisted_method_is_not_wrapped(self, make_view: sb.View):
        """Methods outside the explicit autobind list must stay unwrapped."""
        cmd = _AutobindViewCmd(make_view)
        edit = _Edit(make_view)
        cmd.unlisted_edit(edit)
        assert cmd.captured_edit is edit
        assert not cmd.has_edit(), 'unlisted methods must not cache their arguments'

    def test_default_autobind_binds_signature_named_edit_method(self, make_view: sb.View):
        """With `autobind=True` (default), a method not named on the Sublime base class is
        still bound when its leading parameter is named `edit` — signature-based implicit
        binding, in addition to base-class method names."""
        cmd = _TestViewCmd(make_view)
        edit = _Edit(make_view)
        assert not cmd.has_edit()
        cmd.process_edit(edit)
        assert cmd.captured_edit is edit, 'the method body must still receive the edit token'
        assert cmd.has_edit(), 'process_edit has a leading `edit` param -> now autobound by default'
        assert cmd.edit is edit

    def test_default_autobind_binds_signature_named_view_method(self, make_view: sb.View):
        """Same contract as above, but for a leading `view` parameter."""
        cmd = _TestViewCmd.__new__(_TestViewCmd)
        cmd._view = None
        cmd._views = None
        cmd.process(make_view)
        assert cmd.captured_view is make_view, 'the method body must still receive the view'
        assert cmd.view is make_view, (
            'process has a leading `view` param -> now autobound by default'
        )

    def test_default_autobind_ignores_non_signature_methods(self, make_view: sb.View):
        """A method that is neither a Sublime base-class name nor has a leading
        view/edit/window parameter must never be autobound — no false positives."""
        cmd = _TestViewCmd(make_view)
        assert not cmd.has_edit()
        result = cmd.helper(1, 'x')
        # `helper` takes (x, y) — neither name matches a base-class attr nor view/edit/window
        assert result == '1x'
        assert not cmd.has_edit(), 'helper must not have been wrapped to cache anything'

    def test_autobind_false_leaves_signature_named_methods_unwrapped(self, make_view: sb.View):
        """`autobind=False` must disable binding entirely, even for a method whose leading
        parameter is named `view`/`edit`/`window`."""
        cmd = _NoAutobindViewCmd.__new__(_NoAutobindViewCmd)
        cmd._view = None
        cmd._views = None
        cmd.process(make_view)
        assert cmd.captured_view is make_view
        assert cmd._view is None, (
            'autobind=False must not cache the view even though the leading param is named `view`'
        )

    def test_run_caches_edit_positionally(self, make_view: sb.View):
        """`run` itself caches sublime handles from its positional args."""
        cmd = _TestViewCmd(make_view)
        edit = _Edit(make_view)
        cmd.run(edit)
        assert cmd.has_edit()
        assert cmd.edit is edit


class TestMyBaseOperationalSurface:
    """Operational methods of ``MyBase``: paths, io, navigation, logging, settings."""

    TEXT = 'alpha\n  beta\n  gamma\ndelta'

    def _loaded_cmd(self, view: sb.View, text: str | None = None) -> _TestViewCmd:
        view.insert(_Edit(view), 0, self.TEXT if text is None else text)
        return _TestViewCmd(view)

    # ---- error handling ----
    def test_catch_reraises_by_default(self, make_view: sb.View):
        cmd = _TestViewCmd(make_view)
        with pyt.raises(ValueError, match='original'):
            cmd.catch(ValueError('original'))

    # ---- levels & identity ----
    @pyt.mark.parametrize(
        'factory, expected',
        [
            (lambda v: _TestViewCmd(v), 'view'),
            (lambda v: _TestWindowCmd(sb.active_window()), 'window'),
            (lambda v: _TestAppCmd(), 'app'),
        ],
    )
    def test_api_level(self, make_view: sb.View, factory, expected: str):
        assert factory(make_view).api_level == expected

    # ---- path helpers ----
    def test_path_for_none_is_empty_path(self):
        from pathlib import Path

        assert _TestViewCmd._path_for(None) == Path()

    def test_path_for_expands_and_resolves(self, tmp_path):
        result = _TestViewCmd._path_for(str(tmp_path) + '/sub/../file.txt')
        assert result == tmp_path / 'file.txt'

    def test_path_for_view_without_file(self, make_view: sb.View):
        from pathlib import Path

        assert _TestViewCmd._path_for(make_view) == Path()

    # ---- read / write ----
    def test_read_full_buffer(self, make_view: sb.View):
        cmd = self._loaded_cmd(make_view)
        assert cmd.read() == self.TEXT

    def test_read_region_overloads(self, make_view: sb.View):
        cmd = self._loaded_cmd(make_view)
        assert cmd.read(sb.Region(0, 5)) == 'alpha'
        assert cmd.read(0, 5) == 'alpha'
        assert cmd.read(6) == self.TEXT[6:]

    def test_write_inserts_at_empty_region(self, make_view: sb.View):
        cmd = self._loaded_cmd(make_view, 'ad')
        cmd.edit = _Edit(make_view)
        cmd.write(1, 'bc')
        assert cmd.read() == 'abcd'

    def test_write_replaces_region(self, make_view: sb.View):
        cmd = self._loaded_cmd(make_view, 'aXXd')
        cmd.edit = _Edit(make_view)
        cmd.write(sb.Region(1, 3), 'bc')
        assert cmd.read() == 'abcd'

    def test_write_accepts_tuple(self, make_view: sb.View):
        cmd = self._loaded_cmd(make_view, 'aXd')
        cmd.edit = _Edit(make_view)
        cmd.write((1, 2), 'b')
        assert cmd.read() == 'abd'

    # ---- coordinates ----
    def test_row_col_of(self, make_view: sb.View):
        cmd = self._loaded_cmd(make_view)
        pos = self.TEXT.index('beta')
        assert cmd.row_of(pos) == 1
        assert cmd.col_of(pos) == 2
        assert cmd.row_of(sb.Region(pos, pos + 4)) == 1

    def test_n_rows(self, make_view: sb.View):
        cmd = self._loaded_cmd(make_view)
        assert cmd.n_rows == 4

    # ---- indent analysis ----
    def test_indents_groups_by_level(self, make_view: sb.View):
        from myBasis.plugins._MyBase import Indent

        cmd = self._loaded_cmd(make_view)
        assert cmd.indents == [Indent(0, 0), Indent(1, 2), Indent(3, 0)]

    def test_indent_at(self, make_view: sb.View):
        cmd = self._loaded_cmd(make_view)
        assert cmd.indent_at(2).val == 2
        assert cmd.indent_at(0).val == 0

    def test_shares_indent(self, make_view: sb.View):
        cmd = self._loaded_cmd(make_view)
        assert cmd.shares_indent(1, 2), 'beta and gamma share the same indent block'
        assert not cmd.shares_indent(1, 3), 'delta dedents below beta, ending the block'
        assert not cmd.shares_indent(2, 0), 'an earlier row is never a child of a later one'

    # ---- syntax ----
    def test_syntax_is(self, make_view: sb.View):
        make_view.assign_syntax('Packages/Python/Python.sublime-syntax')
        cmd = _TestViewCmd(make_view)
        assert cmd.syntax == 'source.python'
        assert cmd.syntax_is('python', 'rust')
        assert not cmd.syntax_is('rust')

    def test_syntax_empty_without_assignment(self, make_view: sb.View):
        cmd = _TestViewCmd(make_view)
        assert cmd.syntax == ''

    # ---- navigation ----
    def test_navigate_subl_invokes_command(self, make_view: sb.View):
        cmd = _TestViewCmd(make_view)
        recorded: dict[str, Any] = {}

        def fake_run_command(name: str, args: 'dict | None' = None) -> None:
            recorded['name'] = name
            recorded['args'] = args

        make_view.run_command = fake_run_command  # type: ignore[method-assign]
        cmd.navigate('subl:foo_cmd "key": "val"')
        assert recorded['name'] == 'foo_cmd'
        assert recorded['args'] == {'key': 'val'}

    def test_navigate_http_opens_url(self, make_view: sb.View, monkeypatch: pyt.MonkeyPatch):
        cmd = _TestViewCmd(make_view)
        recorded: dict[str, Any] = {}
        monkeypatch.setattr(
            sb, 'run_command', lambda name, args=None: recorded.update(name=name, args=args)
        )
        cmd.navigate('https://example.com')
        assert recorded['name'] == 'open_url'
        assert recorded['args'] == {'url': 'https://example.com'}

    def test_navigate_file_opens_path(self, make_view: sb.View):
        cmd = _TestViewCmd(make_view)
        opened: list[str] = []
        cmd.open = opened.append  # type: ignore[method-assign]
        cmd.navigate('file:/some/path.txt')
        assert opened == ['/some/path.txt']

    # ---- logging ----
    def test_log_uses_uid_as_name(self, make_view: sb.View, capsys: pyt.CaptureFixture):
        cmd = _TestViewCmd(make_view)
        cmd.log('operational message')
        out = capsys.readouterr().out
        assert 'operational message' in out
        assert f'[{cmd.uid}]' in out

    def test_log_method_formats_signature(self, make_view: sb.View, capsys: pyt.CaptureFixture):
        cmd = _TestViewCmd(make_view)
        cmd.log_method(args=(1,), kwargs={'k': 2}, result='ret', name='my_fn')
        assert 'my_fn(1, k=2) -> ret' in capsys.readouterr().out

    def test_log_method_infers_caller_name(self, make_view: sb.View, capsys: pyt.CaptureFixture):
        cmd = _TestViewCmd(make_view)

        def some_caller() -> None:
            cmd.log_method()

        some_caller()
        assert 'some_caller()' in capsys.readouterr().out

    def test__log_indents_output(self, capsys: pyt.CaptureFixture):
        _TestViewCmd._log('msg', time=False, indent=4)
        assert capsys.readouterr().out.startswith('    [')

    def test__log_custom_name_bracketed(self, capsys: pyt.CaptureFixture):
        _TestViewCmd._log('msg', time=False, name='custom')
        assert capsys.readouterr().out.startswith('[custom]')

    # ---- context & settings ----
    def test_with_context_edit_restores(self, make_view: sb.View):
        cmd = _TestViewCmd(make_view)
        edit = _Edit(make_view)
        with cmd.with_context(edit=edit):
            assert cmd.edit is edit
        assert not cmd.has_edit()

    def test_settings_prefers_view(self, make_view: sb.View):
        cmd = _TestViewCmd(make_view)
        assert cmd.settings is make_view.settings()

    def test_tabsize_default(self, make_view: sb.View):
        cmd = _TestViewCmd(make_view)
        assert cmd.tabsize == 4

    def test_mutable_settings_rejects_empty(self, make_view: sb.View):
        cmd = _TestViewCmd(make_view)
        with pyt.raises(AssertionError, match='non-empty'), cmd.mutable_settings(''):
            pass

    def test_mutable_settings_rejects_paths(self, make_view: sb.View):
        cmd = _TestViewCmd(make_view)
        with pyt.raises(AssertionError, match='single name'), cmd.mutable_settings('sub/dir'):
            pass

    def test_mutable_settings_yields_settings(self, make_view: sb.View):
        cmd = _TestViewCmd(make_view)
        with cmd.mutable_settings('Preferences') as settings:
            assert isinstance(settings, sb.Settings)

    # ---- selection properties ----
    def test_selection_properties(self, make_view: sb.View):
        cmd = self._loaded_cmd(make_view)
        pos = self.TEXT.index('beta')
        cmd.selections.clear()
        cmd.selections.add(sb.Region(pos, pos + 4))
        assert cmd.selection == sb.Region(pos, pos + 4)
        assert cmd.pos == pos
        assert cmd.cursor == pos + 4, 'cursor is the b end of the selection'
        assert cmd.row == 1
        assert cmd.col == 6, 'cursor column counts from the b end'

    def test_line_of_cursor(self, make_view: sb.View):
        cmd = self._loaded_cmd(make_view)
        pos = self.TEXT.index('beta')
        cmd.selections.clear()
        cmd.selections.add(pos)
        line_start = self.TEXT.index('  beta')
        assert cmd.line == sb.Region(line_start, line_start + len('  beta'))
