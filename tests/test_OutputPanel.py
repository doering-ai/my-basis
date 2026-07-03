############
### HEAD ###
############
### STANDARD
from __future__ import annotations
from pathlib import Path

### EXTERNAL
import pytest as pyt
import sublime as sb

### INTERNAL
from myBasis.types.OutputPanel import OutputPanel


############
### DATA ###
############
RED = '\x1b[31m'
GREEN = '\x1b[32m'
BOLD = '\x1b[1m'
EM = '\x1b[3m'
U = '\x1b[4m'
RESET = '\x1b[0m'


def _make_panel(**kwargs) -> OutputPanel:
    """Construct an OutputPanel against the mock window with plain-text defaults."""
    defaults: dict = dict(
        window=sb.active_window(),
        name='Test Panel',
        formats=('plain', 'plain'),
        container='panel',
    )
    defaults.update(kwargs)
    return OutputPanel(**defaults)


############
### BODY ###
############
class TestStyle:
    """Tests for the ``OutputPanel.Style`` state tracker."""

    def test_default_is_falsy(self):
        assert not OutputPanel.Style()

    def test_truthy_when_any_field_set(self):
        style = OutputPanel.Style(strong=5)
        assert style

    def test_reset_clears_everything(self):
        style = OutputPanel.Style(strong=1, em=2, u=3, span=4, span_val='class="red"')
        result = style.reset()
        assert result is style, 'reset must return self for chaining'
        assert not style
        assert style.span_val == ''

    def test_tags_ordered_by_position(self):
        style = OutputPanel.Style(span=1, strong=5, em=3)
        assert style.tags() == ['span', 'em', 'strong']

    def test_tags_empty_by_default(self):
        assert OutputPanel.Style().tags() == []


class TestTerminateTags:
    """Tests for ``OutputPanel._terminate_tags``."""

    def test_empty_style_yields_nothing(self):
        assert OutputPanel._terminate_tags(OutputPanel.Style()) == ''

    def test_closes_in_reverse_order(self):
        style = OutputPanel.Style(strong=1, span=2)
        assert OutputPanel._terminate_tags(style) == '</span></strong>'

    def test_resets_style(self):
        style = OutputPanel.Style(strong=1)
        OutputPanel._terminate_tags(style)
        assert not style


class TestApplyAnsiCode:
    """Tests for ``OutputPanel._apply_ansi_code``."""

    @pyt.mark.parametrize(
        'code, expected',
        [
            ('1', '<strong>'),
            ('3', '<em>'),
            ('4', '<u>'),
            ('31', '<span class="red">'),
            ('32', '<span class="green">'),
            ('97', '<span class="fg_hl">'),
        ],
    )
    def test_opens_tag(self, code: str, expected: str):
        assert OutputPanel._apply_ansi_code(0, code, OutputPanel.Style()) == expected

    @pyt.mark.parametrize('code', ['1', '3', '4'])
    def test_repeated_format_code_is_ignored(self, code: str):
        style = OutputPanel.Style()
        OutputPanel._apply_ansi_code(0, code, style)
        assert OutputPanel._apply_ansi_code(5, code, style) == ''

    def test_reset_code_terminates(self):
        style = OutputPanel.Style()
        OutputPanel._apply_ansi_code(0, '1', style)
        assert OutputPanel._apply_ansi_code(5, '0', style) == '</strong>'
        assert not style

    def test_unknown_code_is_noop(self):
        style = OutputPanel.Style()
        assert OutputPanel._apply_ansi_code(0, '77', style) == ''
        assert not style

    # ---- The span_val regression (fix: `style.span_val = new_color` after `style.span = pos`)
    def test_repeated_color_opens_only_one_span(self):
        """Regression: reapplying the *same* color must not emit a redundant span."""
        style = OutputPanel.Style()
        assert OutputPanel._apply_ansi_code(0, '31', style) == '<span class="red">'
        assert OutputPanel._apply_ansi_code(5, '31', style) == ''

    def test_color_change_closes_previous_span(self):
        style = OutputPanel.Style()
        OutputPanel._apply_ansi_code(0, '31', style)
        result = OutputPanel._apply_ansi_code(5, '32', style)
        assert result == '</span><span class="green">'

    def test_color_change_updates_span_val(self):
        """Regression: span_val must track the latest color so A->B->A round-trips."""
        style = OutputPanel.Style()
        OutputPanel._apply_ansi_code(0, '31', style)
        assert style.span_val == 'class="red"'
        OutputPanel._apply_ansi_code(5, '32', style)
        assert style.span_val == 'class="green"'
        result = OutputPanel._apply_ansi_code(9, '31', style)
        assert result == '</span><span class="red">'

    @pyt.mark.parametrize(
        'code, expected_color',
        [
            ('38;5;5;1', 'class="red"'),  # palette idx < 16 approximates the base colors
            ('38;5;5;7', 'class="fg"'),
            ('38;5;5;16', 'style="color: rgb(0, 0, 0)"'),  # 6x6x6 color cube
            ('38;5;5;231', 'style="color: rgb(255, 255, 255)"'),
            ('38;5;5;232', 'style="color: rgb(8, 8, 8)"'),  # grayscale ramp
            ('38;5;5;255', 'style="color: rgb(261, 261, 261)"'),
        ],
    )
    def test_256_palette_branch(self, code: str, expected_color: str):
        style = OutputPanel.Style()
        assert OutputPanel._apply_ansi_code(0, code, style) == f'<span {expected_color}>'


class TestReplaceAnsiColors:
    """End-to-end ANSI -> HTML conversion through ``_replace_ansi_colors``."""

    def test_plain_text_passthrough(self):
        assert OutputPanel._replace_ansi_colors('no codes here') == 'no codes here'

    @pyt.mark.parametrize(
        'text, expected',
        [
            (f'{RED}red{RESET}', '<span class="red">red</span>'),
            (f'{BOLD}bold{RESET}', '<strong>bold</strong>'),
            (f'{EM}italic{RESET}', '<em>italic</em>'),
            (f'{U}under{RESET}', '<u>under</u>'),
            (f'pre {GREEN}mid{RESET} post', 'pre <span class="green">mid</span> post'),
        ],
    )
    def test_single_code_paths(self, text: str, expected: str):
        assert OutputPanel._replace_ansi_colors(text) == expected

    def test_unterminated_tags_closed_at_end(self):
        result = OutputPanel._replace_ansi_colors(f'{RED}dangling')
        assert result == '<span class="red">dangling</span>'

    def test_nested_open_close_order(self):
        result = OutputPanel._replace_ansi_colors(f'{BOLD}a{RED}b{RESET}c')
        assert result == '<strong>a<span class="red">b</span></strong>c'

    def test_same_color_twice_is_one_span(self):
        """Regression (span_val): a re-asserted color must not re-open the span."""
        result = OutputPanel._replace_ansi_colors(f'{RED}one{RED}two{RESET}')
        assert result == '<span class="red">onetwo</span>'

    def test_color_switch_mid_text(self):
        result = OutputPanel._replace_ansi_colors(f'{RED}r{GREEN}g{RESET}')
        assert result == '<span class="red">r</span><span class="green">g</span>'


class TestConversions:
    """Tests for the classmethod format converters."""

    def test_shell_to_plain_strips_codes(self):
        assert OutputPanel.shell_to_plain(f'{RED}red{RESET} plain') == 'red plain'

    def test_shell_to_html_escapes_and_colors(self):
        result = OutputPanel.shell_to_html(f'{RED}a < b{RESET}')
        assert result == '<span class="red">a &lt; b</span>'

    def test_html_to_plain_strips_tags(self):
        assert OutputPanel.html_to_plain('<p>hi <strong>there</strong></p>') == 'hi there'

    def test_html_to_plain_unescapes(self):
        assert OutputPanel.html_to_plain('a &lt; b') == 'a < b'

    def test_html_to_plain_removes_head_block(self):
        assert OutputPanel.html_to_plain('<head><style>x</style></head>body') == 'body'

    def test_html_to_shell_is_passthrough(self, capsys: pyt.CaptureFixture):
        assert OutputPanel.html_to_shell('<b>x</b>') == '<b>x</b>'
        assert 'WARNING' in capsys.readouterr().out

    @pyt.mark.parametrize(
        'text, f0, f1, expected',
        [
            ('same', 'html', 'html', 'same'),
            ('plain in', 'plain', 'html', 'plain in'),  # plain input is never transformed
            (f'{RED}x{RESET}', 'shell', 'plain', 'x'),
            (f'{RED}x{RESET}', 'shell', 'html', '<span class="red">x</span>'),
            ('<em>y</em>', 'html', 'plain', 'y'),
        ],
    )
    def test_format_dispatch(self, text: str, f0: str, f1: str, expected: str):
        assert OutputPanel.format(text, f0, f1) == expected


class TestPanelLifecycle:
    """Instance-level behavior against the mock window (plain panel container)."""

    def test_open_creates_panel_view(self):
        panel = _make_panel()
        assert panel.status == 'open'
        assert panel.panel is not None
        assert panel.sheet is None and panel.html is None
        assert panel.view is panel.panel

    def test_panel_settings_applied(self):
        panel = _make_panel(word_wrap=True, line_numbers=True, file_regex='^ERR')
        settings = panel.panel.settings()
        assert settings.get('word_wrap') is True
        assert settings.get('line_numbers') is True
        assert settings.get('result_file_regex') == '^ERR'

    def test_panel_read_only_by_default(self):
        panel = _make_panel()
        assert panel.panel.is_read_only()

    def test_panel_name_normalized(self):
        panel = _make_panel(name='  My Cool  Panel ')
        assert panel.panel_name == 'my_cool_panel'

    def test_uid_prefixes(self):
        panel = _make_panel()
        assert panel.uid == f'v{panel.panel.id()}'

    def test_repr_mentions_formats_and_status(self):
        panel = _make_panel()
        assert 'OutputPanel[plain, plain]' in repr(panel)
        assert 'status=open' in repr(panel)

    def test_io_protocol_flags(self):
        panel = _make_panel()
        assert panel.writable() and not panel.readable() and not panel.isatty()

    def test_write_returns_length(self):
        panel = _make_panel()
        assert panel.write('hello') == 5

    def test_write_flush_appends_to_view(self):
        panel = _make_panel()
        panel.write('hello ')
        panel.writeln('world')
        panel.flush()
        view = panel.view
        assert view.substr(sb.Region(0, view.size())) == 'hello world\n'
        assert panel.content == 'hello world\n'

    def test_flush_applies_middleware(self):
        panel = _make_panel(middleware=(str.upper,))
        panel.write('quiet')
        panel.flush()
        assert panel.content == 'QUIET'

    def test_close_prevents_writes(self):
        panel = _make_panel()
        panel.close()
        assert panel.status == 'closed'
        assert panel.closed
        assert panel.write('ignored') == 0

    def test_close_is_idempotent(self):
        panel = _make_panel()
        panel.close()
        panel.close()
        assert panel.status == 'closed'

    def test_reset_clears_content_and_reopens(self):
        panel = _make_panel()
        panel.write('data')
        panel.flush()
        panel.close()
        panel.reset()
        assert panel.status == 'open'
        assert panel.content == ''
        assert panel.view.size() == 0

    def test_format_properties(self):
        panel = _make_panel(formats=('shell', 'plain'))
        assert panel.f0 == 'shell'
        assert panel.f1 == 'plain'

    def test_shell_to_plain_pipeline(self):
        panel = _make_panel(formats=('shell', 'plain'))
        panel.write(f'{RED}error{RESET}\n')
        panel.flush()
        assert panel.content == 'error\n'
        assert panel.shell_content == f'{RED}error{RESET}\n', 'raw shell input is preserved'

    def test_content_setter_via_edit(self):
        panel = _make_panel()
        panel.write('abc')
        panel.edit(str.upper)
        assert panel.content == 'ABC'
        assert panel.view.substr(sb.Region(0, panel.view.size())) == 'ABC'

    def test_hardcopy_written_to_disk(self, tmp_path: Path):
        target = tmp_path / 'out.txt'
        panel = _make_panel(hardcopy=target)
        panel.write('persisted')
        panel.flush()
        panel.write_to_disk()
        assert target.read_text() == 'persisted'

    def test_hardcopies_single_path_is_final_format(self, tmp_path: Path):
        panel = _make_panel(hardcopy=tmp_path / 'out.txt')
        assert panel.hardcopies == (None, tmp_path / 'out.txt')

    def test_hardcopies_none(self):
        panel = _make_panel()
        assert panel.hardcopies == (None, None)


class TestHtmlLifecycle:
    """Instance-level behavior for the html sheet container."""

    def test_open_creates_html_sheet(self):
        panel = _make_panel(formats=('html', 'html'))
        assert panel.html is not None
        assert panel.panel is None
        assert panel.view is None
        assert panel.uid == f's{panel.html.id()}'

    def test_flush_sets_sheet_contents(self):
        panel = _make_panel(formats=('html', 'html'))
        panel.write('<em>hi</em>')
        panel.flush()
        assert '<em>hi</em>' in panel.html._text
        assert panel.html._text == panel.html_content

    def test_html_content_wraps_body(self):
        panel = _make_panel(formats=('html', 'html'))
        panel.write('payload')
        panel.flush()
        html = panel.html_content
        assert html.startswith('<head>')
        assert 'payload' in html
        assert html.endswith('</body>')

    def test_html_content_empty_when_no_content(self):
        panel = _make_panel(formats=('html', 'html'))
        assert panel.html_content == ''


class TestEavesdrop:
    """The ``eavesdrop`` context manager reroutes stdout into the panel."""

    def test_captures_prints(self):
        panel = _make_panel()
        with panel.eavesdrop():
            print('intercepted')
        assert 'intercepted' in panel.content
        assert panel.status == 'open'

    def test_exception_marks_failed(self):
        panel = _make_panel()
        with panel.eavesdrop():
            raise ValueError('boom')
        assert panel.status == 'failed'
