############
### HEAD ###
############
### STANDARD
from __future__ import annotations
from typing import ClassVar, TextIO, Literal, Protocol
from typing_extensions import Self, TypeAlias
from collections import deque
from collections.abc import Iterator, Callable
from threading import Lock
from pathlib import Path
from io import StringIO
from traceback import format_exc
import sys
import functools as ft
import contextlib as ctx
import html

### EXTERNAL
import pydantic as pyd
import sublime as sb
import regex as re
import more_itertools as mi

### INTERNAL
from ..infra.utils import ut

Format: TypeAlias = Literal['plain', 'html', 'shell']


############
### DATA ###
############
class _IOProtocol(Protocol):
    """Protocol for file-like IO objects."""

    def write(self, text: str) -> int: ...
    def flush(self) -> None: ...
    def close(self) -> None: ...
    def isatty(self) -> bool: ...
    def readable(self) -> bool: ...
    def writable(self) -> bool: ...
    @property
    def closed(self) -> bool: ...


class _StreamWrapper(StringIO):
    """A simple wrapper around StringIO that allows us to intercept writes and flushes."""

    parent: _IOProtocol
    stdout: TextIO
    also_log: bool = False

    def __init__(self, parent: _IOProtocol, stdout: TextIO, also_log: bool, *args, **kwargs):
        """Initialize the wrapper."""
        super().__init__(*args, **kwargs)
        self.parent = parent
        self.stdout = stdout
        self.also_log = also_log

    def write(self, text: str) -> int:
        """Write text to the stream."""
        super().write(text)
        if self.also_log:
            self.stdout.write(text)
        return self.parent.write(text)

    def flush(self) -> None:
        """Flush the stream."""
        super().flush()
        if self.also_log:
            self.stdout.flush()
        self.parent.flush()


############
### BODY ###
############
class OutputPanel(pyd.BaseModel):
    """A simple, thread-safe wrapper around a Sublime Text output panel.

    Implements the protocol for file IO objects, allowing the user to treat it like a regular file
    stream. The text is buffered in a queue and only flushed to the panel when `flush()` is called,
    allowing for efficient writes from multiple threads without overwhelming the Sublime Text API.
    """

    RGXS: ClassVar[dict[str, re.Pattern]] = ut.rgx_dict(
        ansi=r'\x1b\[(?P<code>\d+)m',
        html=ut.multi_rgx(
            r'< *head *>.*?< */ *head *>',
            r'</? *\w+ *[^>]*+(?<!\\)>',
            pre=r'(?s)(?<!\\)',
        ),
    )

    # ---- Main ----
    #: The Sublime Text window in which to create the output panel. Defaults to the active window.
    window: ut.WindowField = pyd.Field(default_factory=sb.active_window)

    #: The name of the output panel to create. Defaults to a unique name based on the current time.
    name: str = 'Output Panel'

    #: The input and output formats for the panel content.
    formats: tuple[Format, Format] = ('html', 'html')

    #: Syntax highlighting to apply to the output panel view. Does not apply to html.
    syntax: ut.SyntaxField | None = None

    #: Which container to write plain content to (HTML content is implied to be a sheet).
    container: Literal['panel', 'sheet'] = 'panel'

    #: Optional middleware functions to apply to the text before writing it to the panel.
    middleware: tuple[Callable[[str], str], ...] = tuple()

    #: The path to the file that is filled with the contents of this panel/sheet
    hardcopy: Path | tuple[Path | None, Path | None] | None = None

    # ---- View Settings ----
    file_regex: str = ''
    line_regex: str = ''
    base_dir: str | None = None
    word_wrap: bool = False
    line_numbers: bool = False
    gutter: bool = False
    scroll_past_end: bool = False

    # ---- State ----
    #: The output panel view, if using a standard output panel.
    panel: ut.ViewField | None = None
    #: The output panel sheet, if using a standard sheet instead of a panel.
    sheet: ut.SheetField | None = None
    #: The output panel sheet, if using an html sheet.
    html: ut.HtmlSheetField | None = None

    #: The current of the panel; note that closed panels cannot be written to.
    status: Literal['open', 'closed', 'failed'] = 'open'

    # ---- Private ----
    #: The current content of the output panel, including any unflushed text in the queue.
    _content: tuple[str, str] = ('', '')
    #: Internal wrapper around the standard output streams to intercept writes and flushes.
    _wrapper: StringIO | None = None
    #: Lock to synchronize access to the text queue.
    _lock: Lock = pyd.PrivateAttr(default_factory=Lock)
    #: Queue to buffer text before flushing it to the panel.
    _queue: deque = pyd.PrivateAttr(default_factory=deque)
    #: Original standard output and error streams, to restore when the panel is closed.
    _std_streams: tuple[TextIO, TextIO] | None = None

    # -------------------
    # `.` Initial Methods
    # -------------------
    @pyd.model_validator(mode='after')
    def _open_panel(self) -> Self:
        # Default to the current file directory
        if not self.base_dir and (_v := self.window.active_view()) and (_f := _v.file_name()):
            self.base_dir = str(Path(_f).parent)

        if self.hardcopy:
            print(f'{self.hardcopies=}')
            for _hardcopy in self.hardcopies:
                if _hardcopy is not None:
                    assert _hardcopy.parent.is_dir(), f'{_hardcopy.parent} does not exist.'
                    assert not _hardcopy.is_dir(), f'{_hardcopy} already exists and is not a file.'
                    _hardcopy.write_text('')

        self.status = 'open'
        if self.f1 == 'html':
            self.html = self._create_html()
        elif self.container == 'panel':
            self.panel = self._create_panel()
        else:
            self.sheet = self._create_sheet()

        return self

    def __del__(self):
        if self._std_streams:
            sys.stdout, sys.stderr = self._std_streams
            self._std_streams = None
            print('\nWARNING: Output panel stream wrapper was not properly closed.')

    def __repr__(self) -> str:
        args = [
            f'window={self.window.id()}',
            f'uid={self.uid}',
            f'status={self.status}',
            f'size={len(self.content)}',
        ]

        return f'OutputPanel[{self.f0}, {self.f1}]({", ".join(args)})'

    def close(self):
        """Hides the output panel."""
        if self.status == 'closed':
            return
        self.status = 'closed'

        if self.html is not None:
            self.html.close()
        if self.panel is not None:
            self.window.run_command('hide_panel', dict(panel=f'output.{self.panel_name}'))
        if self.sheet is not None:
            self.sheet.close()

    def reset(self) -> None:
        """Clears the output panel content and resets the text queue."""
        self._content = ('', '')
        self.status = 'open'
        with self._lock:
            self._queue.clear()

        # I. Clear the HTML sheet
        if self.html is not None:
            if self.html in self.window.sheets():
                if self._reselect_sheet(self.html):
                    self.html.set_contents(self.html_content)
                    return
            else:
                self.html = self._create_html()

        # II. Clear the panel
        if self.panel is not None:
            if self.panel.is_valid():
                self.panel.run_command('select_all')
                self.panel.run_command('right_delete')
                self.window.run_command('show_panel', dict(panel=f'output.{self.panel_name}'))
                return
            else:
                self.panel = self._create_panel()

        # II. Clear the panel
        if self.sheet is not None:
            if (
                (v := self.sheet.view())
                and v.is_valid()
                and (v.file_name() or '').startswith(self.name)
            ):
                v.run_command('select_all')
                v.run_command('right_delete')
                return
            else:
                self.sheet = self._create_sheet()

    # -------------------
    # `-` Private Methods
    # -------------------
    def _create_html(self) -> sb.HtmlSheet:
        w = self.window
        if existing := self._existing_html():
            group, index = w.get_sheet_index(existing)
            existing.close()
        else:
            group = (w.active_group() + 1) % w.num_groups()
            index = -1

        sheet = self.window.new_html_sheet(self.name, '', group=group)
        if index != -1:
            w.set_sheet_index(sheet, group, index)
        return sheet

    def _create_panel(self) -> sb.View:
        panel = self.window.create_output_panel(self.panel_name)
        self._apply_settings(panel)
        self.window.run_command('show_panel', dict(panel=f'output.{self.panel_name}'))
        return panel

    def _create_sheet(self) -> sb.Sheet:
        w = self.window
        if existing := self._existing_sheet():
            group, index = w.get_sheet_index(existing)
        else:
            group = (w.active_group() + 1) % w.num_groups()
            index = -1

        # if path := self.hardcopies[1]:
        #     # I. If pointed to a real file, rely on Sublime to find an existing version.
        #     assert path.exists(), f'Hardcopy file {path} does not exist.'
        #     print('opening...')
        #     view = w.open_file(str(path), group=group)
        #     print('open!')
        #     assert view is not None, f'Failed to open hardcopy file {path} in sheet mode.'
        #     sheet = view.sheet()
        if existing and (v := existing.view()) and v.is_valid():
            sheet, view = existing, v
        else:
            if existing:
                existing.close()
            view = w.new_file(syntax=self.syntax or '')
            sheet = view.sheet()

        assert isinstance(sheet, sb.TextSheet), 'Output panel sheets must be text sheets.'
        sheet.set_name(self.name)
        self._apply_settings(view)
        w.set_sheet_index(sheet, group, index)
        if window := view.window():
            window.focus_view(view)
        return sheet

    def _apply_settings(self, view: sb.View) -> None:
        view.set_read_only(True)
        view.set_scratch(True)
        if self.syntax:
            view.assign_syntax(self.syntax)

        settings = view.settings()
        settings.set('result_file_regex', self.file_regex)
        settings.set('result_line_regex', self.line_regex)
        settings.set('result_base_dir', self.base_dir)
        settings.set('word_wrap', self.word_wrap)
        settings.set('line_numbers', self.line_numbers)
        settings.set('gutter', self.gutter)
        settings.set('scroll_past_end', self.scroll_past_end)

    def _existing_html(self) -> sb.HtmlSheet | None:
        return next(
            (
                sheet
                for sheet in self.window.sheets()
                if isinstance(sheet, sb.HtmlSheet) and not sheet.file_name()
            ),
            None,
        )

    def _existing_sheet(self) -> sb.Sheet | None:
        ut.multiprint(
            title='Existing sheets:',
            lines=(
                f'{sheet.file_name()}: '
                + ', '.join(
                    [
                        f'(group, index)={self.window.get_sheet_index(sheet)}',
                        f'trans={sheet.is_transient()}',
                        f'semitrans={sheet.is_semi_transient()}',
                    ]
                )
                for sheet in self.window.sheets()
            ),
        )

        def _test(sheet: sb.Sheet) -> bool:
            return (
                not isinstance(sheet, sb.HtmlSheet)
                and sheet.file_name() is None
                and (v := sheet.view()) is not None
                and v.size() > 0
                and '.pytest' in v.scope_name(0)
            )

        return next(filter(_test, self.window.sheets()), None)

    HTML_STYLES: ClassVar[str] = (Path(__file__).parent / '../infra/output_styles.html').read_text()
    ANSI_CSS_CLASSES: ClassVar[dict[str, str]] = {
        '30': 'class="bg"',
        '31': 'class="red"',
        '32': 'class="green"',
        '33': 'class="yellow"',
        '34': 'class="blue"',
        '35': 'class="purple"',
        '36': 'class="cyan"',
        '37': 'class="fg"',
        '90': 'class="bg_hl"',
        '91': 'class="red_hl"',
        '92': 'class="green_hl"',
        '93': 'class="yellow_hl"',
        '94': 'class="blue_hl"',
        '95': 'class="purple_hl"',
        '96': 'class="cyan_hl"',
        '97': 'class="fg_hl"',
    }

    class Style(pyd.BaseModel):
        """Helper class to track the current text style when processing ANSI codes."""

        strong: int = -1
        em: int = -1
        u: int = -1
        span: int = -1

        span_val: str = ''

        def reset(self) -> Self:
            """Resets all styles to their default state and returns self for chaining."""
            self.strong = -1
            self.em = -1
            self.u = -1
            self.span = -1
            self.span_val = ''
            return self

        def __bool__(self) -> bool:
            return max([self.strong, self.em, self.u, self.span]) >= 0

        def tags(self) -> list[str]:
            """Returns a list of the currently active tags in the order they were applied."""
            pairs = [
                (pos, field)
                for field in ('strong', 'em', 'u', 'span')
                if (pos := getattr(self, field)) >= 0
            ]
            return [field for _, field in sorted(pairs)]

    @staticmethod
    def _terminate_tags(style: Style) -> str:
        ret = ''
        if not style:
            return ret

        ret = ''.join(f'</{tag}>' for tag in reversed(style.tags()))
        style.reset()
        return ret

    @classmethod
    def _apply_ansi_code(cls, pos: int, code: str, style: Style) -> str:
        new_color = ''

        # I. Set strong/italic/underline
        if code == '0':
            return cls._terminate_tags(style)
        if code == '1':
            if style.strong == -1:
                style.strong = pos
                return '<strong>'
            return ''
        elif code == '3':
            if style.em == -1:
                style.em = pos
                return '<em>'
            return ''
        elif code == '4':
            if style.u == -1:
                style.u = pos
                return '<u>'
            return ''

        # II. Set colors
        elif new_color := cls.ANSI_CSS_CLASSES.get(code):
            # II.i. Set predefined colors
            pass
        elif code.startswith('38;5;'):
            parts = code[len('38;5;') :].split(';')
            if len(parts) == 3 and parts[0] == '2':
                # II.ii. Apply truecolor RGB
                new_color = f'style="color: rgb({parts[1]}, {parts[2]}, {parts[3]})"'
            elif len(parts) == 2 and parts[0] == '5':
                # II.iii. Apply 256-color palette (not supported in html so we must approximate)
                idx = int(parts[1])
                if idx < 16:
                    new_color = cls.ANSI_CSS_CLASSES.get(str(30 + (idx % 8)))
                elif 16 <= idx < 232:
                    idx -= 16
                    r = (idx // 36) * 51
                    g = ((idx % 36) // 6) * 51
                    b = (idx % 6) * 51
                    new_color = f'style="color: rgb({r}, {g}, {b})"'
                elif idx >= 232:
                    gray = ((idx - 232) * 11) + 8
                    new_color = f'style="color: rgb({gray}, {gray}, {gray})"'

        # II.iv. Apply color changes
        if new_color and new_color != style.span_val:
            ret = f'<span {new_color}>'
            if style.span > -1:
                ret = f'</span>{ret}'
            style.span = pos
            return ret
        return ''

    @classmethod
    def _replace_ansi_colors(cls, text: str) -> str:
        """Transforms ANSI escape codes into html span tags."""
        parts = deque()
        style = cls.Style()

        # 0. If no ANSI escape codes are found, return the text as-is
        delims, sections = ut.rgx_fullsplit(cls.RGXS['ansi'], text)
        if not delims:
            return text

        # I. Iteratively handle the ANSI escape codes
        pos = 0
        for delim, next_section in zip(delims, sections):
            if not delim:
                parts.append(next_section)
                pos += len(next_section)
                continue

            codes = {(pos + m.start(), m['code']) for m in cls.RGXS['ansi'].finditer(delim)}

            # I.ii. Handle remaining codes
            starts = ''.join(cls._apply_ansi_code(_pos, _code, style) for _pos, _code in codes)

            # I.iii. Add the tags before the coming content (if there are any)
            parts.extend((starts, next_section))
            pos += len(starts) + len(next_section)

        # IV. Terminate any remaining tags at the end of the text
        if style:
            parts.append(cls._terminate_tags(style))

        return ''.join(parts)

    def _reselect_sheet(self, sheet: sb.Sheet) -> bool:
        if sheet.is_selected():
            return True
        elif (g_id := sheet.group()) is None:
            return False

        sheets = self.window.selected_sheets()
        match = mi.first(mi.locate(sheets, lambda s: s.group() == g_id), default=-1)
        if match != -1:
            self.window.select_sheets([*sheets[:match], sheet, *sheets[match + 1 :]])
            return True
        else:
            return False

    def apply_middleware(self, text: str) -> str:
        """Applies all middleware functions to the given text in order."""
        for func in self.middleware:
            text = func(text)
        return text

    # -------------------
    # `+` Primary Methods
    # -------------------
    @classmethod
    def shell_to_html(cls, text: str) -> str:
        """Converts CLI output with ANSI codes into html suitable for Sublime Text."""
        return cls._replace_ansi_colors(html.escape(text, quote=False))

    @classmethod
    def shell_to_plain(cls, text: str) -> str:
        """Converts CLI output with ANSI codes into html suitable for Sublime Text."""
        return cls.RGXS['ansi'].sub('', text)

    @classmethod
    def html_to_plain(cls, text: str) -> str:
        """Strips all html tags from the given text."""
        text = cls.RGXS['html'].sub('', text)
        return html.unescape(text)

    @classmethod
    def html_to_shell(cls, text: str) -> str:
        """Converts html with inline styles into CLI output with ANSI codes."""
        print('WARNING: Cannot convert html to shell output yet; returning as-is.')
        return text  # TODO

    @staticmethod
    @ft.lru_cache(maxsize=64)
    def format(text: str, f0: Format, f1: Format) -> str:
        """Normalizes the given text according to the specified input and output formats."""
        cls = OutputPanel
        if f0 in (f1, 'plain'):
            return text
        elif f0 == 'shell':
            return cls.shell_to_plain(text) if f1 == 'plain' else cls.shell_to_html(text)
        elif f0 == 'html':
            return cls.html_to_plain(text) if f1 == 'plain' else cls.html_to_shell(text)

    # ------------------
    # `*` Public Methods
    # ------------------
    @property
    def uid(self) -> str:
        """Returns a unique identifier for the output panel."""
        if self.html:
            return f's{self.html.id()}'
        elif self.panel:
            return f'v{self.panel.id()}'
        elif self.sheet:
            return f's{self.sheet.id()}'
        elif self.window:
            return f'w{self.window.id()}'
        else:
            return '-1'

    @property
    def panel_name(self) -> str:
        """A normalized, lowercase version of the original, human-readable name."""
        return re.sub(r'\s+', '_', self.name.lower().strip())

    @property
    def view(self) -> sb.View | None:
        """Shorthand for the view inside the output's non-html sheet, which is assumed to exist."""
        view = None
        if self.panel:
            view = self.panel
        elif self.sheet:
            view = self.sheet.view()
        return view if view and view.is_valid() else None

    @ctx.contextmanager
    def eavesdrop(self, also_log: bool = False) -> Iterator[StringIO]:
        """Context manager that redirects standard output and error to the output panel."""
        self._wrapper = _StreamWrapper(self, sys.stdout, also_log)
        sys.stdout = self._wrapper

        try:
            yield self._wrapper
        except Exception:
            self._wrapper.write(f'INTERNAL ERROR: {format_exc()}')
            self._wrapper.flush()
            self.status = 'failed'
        finally:
            sys.stdout = self._wrapper.stdout
            self._wrapper = None

        self.flush()

    def flush(self) -> None:
        """Flushes the text queue to the output panel."""
        if self.status in {'closed', 'failed'} or not self._queue:
            return

        with self._lock:
            raw_text = ''.join(self._queue)
            self._queue.clear()

        text = self.format(raw_text, *self.formats)
        text = self.apply_middleware(text)
        self._content = (self._content[0] + raw_text, self._content[1] + text)

        # Add the content
        if self.html:
            self.html.set_contents(self.html_content)
        elif v := self.view:
            size0 = v.size()
            v.run_command('append', {'characters': text, 'force': True})
            if (
                len(v.selection) == 1
                and (cursor := v.selection[0]).empty()
                and (size0 - cursor.a) < 128
            ):
                v.selection.clear()
                v.selection.add(_new := size0 + len(text))
                v.show(_new)
        self.write_to_disk()

    @ut.debounced(delta=1000)
    def write_to_disk(self) -> None:
        """Writes current content to disk at the specified hardcopy path, if any."""
        for path, content in zip(self.hardcopies, self._content):
            if path:
                path.write_text(content)

    def write(self, text: str) -> int:
        """Writes a string to the output panel, returning the number of characters written."""
        if self.status in {'closed', 'failed'}:
            return 0
        with self._lock:
            self._queue.append(text)
        return len(text)

    def writeln(self, text) -> int:
        """Writes a string followed by a newline to the output panel."""
        return self.write(text + '\n')

    def edit(self, *functions: Callable[[str], str]) -> None:
        """Applies the given functions to the current content of the output panel in order."""
        self.flush()
        for func in functions:
            self.content = func(self.content)

        if self.html:
            self.html.set_contents(self.html_content)
        elif v := self.view:
            v.run_command('select_all')
            v.run_command('right_delete')
            v.run_command('append', {'characters': self.content, 'force': True})
            v.show(0)
        self.write_to_disk()

    def readable(self) -> bool:
        """Returns False since the output panel is write-only."""
        return False

    def writable(self) -> bool:
        """Returns True since the output panel is writable."""
        return True

    def isatty(self) -> bool:
        """Returns False since the output panel is not a terminal."""
        return False

    @property
    def closed(self) -> bool:
        """Whether the output panel is closed or has encountered an error."""
        return self.status in {'failed', 'closed'}

    @property
    def f0(self) -> Format:
        """The format in which the content was originally written to the output panel."""
        return self.formats[0]

    @property
    def f1(self) -> Format:
        """The format in which the content is currently being displayed in the output panel."""
        return self.formats[1]

    @property
    def content(self) -> str:
        """The current content of the output panel in its final format."""
        return self._content[1]

    @content.setter
    def content(self, value: str) -> None:
        """Sets the content of the output panel, applying the necessary formatting."""
        self._content = (self._content[0], value)

    @property
    def shell_content(self) -> str:
        """The current content of the output panel as shell-ready markup."""
        if self.f0 == 'shell':
            return self._content[0]
        elif self.f1 == 'shell':
            return self._content[1]
        else:
            return self.format(self.content, self.f1, 'shell')

    @property
    def html_content(self) -> str:
        """The current content of the output panel as html."""
        if not self.content:
            return ''
        elif self.f0 == 'html':
            body = self._content[0]
        elif self.f1 == 'html':
            body = self._content[1]
        else:
            body = self.format(self.content, self.f1, 'html')
        return '\n'.join(
            [
                '<head>',
                self.HTML_STYLES,
                '</head>',
                '<body>',
                '<p class="ws">',
                body,
                '</p>',
                '</body>',
            ]
        )

    @property
    def plain_content(self) -> str:
        """The current content of the output panel with all styling stripped."""
        if self.f0 == 'plain':
            return self._content[0]
        elif self.f1 == 'plain':
            return self._content[1]
        return self.format(self.content, self.f1, 'plain')

    @property
    def hardcopies(self) -> tuple[Path | None, Path | None]:
        """Convient form of passed hardcopy paths for each of the two formats."""
        if not self.hardcopy:
            return None, None
        elif isinstance(self.hardcopy, Path):
            return None, self.hardcopy
        else:
            return self.hardcopy
