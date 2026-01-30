############
### HEAD ###
############
# --------
# Standard
# --------
from typing import Any, Iterator, Union, Tuple, Dict, Iterable
import re
import inspect
import functools as ft
from abc import abstractmethod, ABC

# --------
# External
# --------
import sublime_plugin as sbp
from sublime import Region, Edit, Selection

# --------
# Internal
# --------
from src.Comment import Comment
from src.Header import Header


############
### BODY ###
############
class MyCommand(sbp.TextCommand, ABC):
    """A base class for Sublime Text commands with utilities for comment handling."""

    edit: Edit
    kwargs: dict

    # -------------------
    # `.` Initial Methods
    # -------------------
    def run(self, edit: Edit, **kwargs: Any):
        """Run the command with the given edit object and keyword arguments."""
        self.edit = edit
        self.kwargs = {}
        self.setup(**kwargs)
        for region in self.regions:
            self.main(region)

    def setup(self, **kwargs: Any) -> None:
        """Set up the command with the given keyword arguments."""
        self.kwargs = kwargs
        members = dict(inspect.getmembers(self))
        for key, value in kwargs.items():
            if key in members:
                setattr(self, key, value)

    # -------------------
    # `-` Private Methods
    # -------------------
    def _syntax_vars(self, pos: int = 0) -> Dict[str, str]:
        shell_vars = self.view.meta_info('shellVariables', pos)
        assert isinstance(shell_vars, list)
        return {item['name']: item['value'] for item in shell_vars}

    def _comment_mark(self, pos: int = 0) -> str:
        syntax_vars = self._syntax_vars(pos)
        return syntax_vars.get('TM_COMMENT_START', '#').strip(' ')

    def _parse_comment(self, region: Region) -> Comment:
        """Parse a comment from the given region."""
        data = {}
        data['lines'] = self.view.lines(region)
        assert data['lines'], 'No lines found in comment region.'

        raw_texts = list(map(self.read, data['lines']))
        data['texts'] = [text.strip(' \t') for text in raw_texts]

        # Read the line number (row) and indentation (column) of the comment's first line
        data['row'], _ = self.view.rowcol(region.begin())
        match = re.match(r'^\s*(?=\S)', raw_texts[0])
        assert match is not None
        data['col'] = len(match.group(0).replace('\t', '    ')) + 1

        # Remove the comment mark from texts, recording if it has been repeated for depth
        data['mark'] = mark = self._comment_mark(region.begin())
        for i, text in enumerate(data['texts']):
            if not text.startswith(mark):
                continue
            elif match := re.fullmatch(rf'({mark}+) (\S.*)', text):
                data['mark'], data['texts'][i] = match.groups()

        return Comment(**data)

    def _raw_comment_iter(self, pos: int = 0) -> Iterator[Comment]:
        for region in self.view.find_by_selector('comment.line'):
            if region and (pos <= 0 or region.begin() >= pos):
                yield self._parse_comment(region)

    def _yield_comment(
        self, comment: Comment, target: int = 0, window: bool = False
    ) -> Iterator[Comment]:
        n = comment.n_lines
        if target > 0 and n != target:
            if window and (n_windows := n - target + 1) > 0:
                for i in range(n_windows):
                    yield comment[i : i + target]
        else:
            yield comment

    def header_iter(self, level: int = 1, pos: int = 0) -> Iterator[Header]:
        """Iterate through the header comments found in this file.

        Args:
            level: The header level to filter by (-1 for any, 0 for BASE, 1 for sections).
            pos: The position in the file to start searching from.
        Yields:
            Objects representing three-line header comments in this file, in order.
        """
        assert -1 <= level <= 1, f'Invalid level: {level}'

        for comment in self.comment_iter(pos=pos, target=3, window=True):
            assert comment.n_lines == 3, 'Comment must have exactly 3 lines to be a header.'
            t0, _, t2 = comment.texts
            if Header._are_delims(t0, t2, level):
                yield Header.new(comment, level)

    # -------------------
    # `+` Primary Methods
    # -------------------
    def read(self, region: Region) -> str:
        """Read the text in the given region."""
        return self.view.substr(region)

    def write(self, pos: Union[Region, Tuple[int, int], int], text: str) -> None:
        """Write the given text at the given position or region."""
        if isinstance(pos, int):
            self.view.insert(self.edit, pos, text)
        elif isinstance(pos, tuple):
            pos = Region(pos[0], pos[1])  # type: ignore

        assert isinstance(pos, Region)
        self.view.replace(self.edit, pos, text)

    def show(self, region: Union[Region, int]) -> None:
        """Show the given region or position in the view, selecting it."""
        if isinstance(region, int):
            region = Region(region, region)

        self.selection.clear()
        self.selection.add(region)
        self.view.show(region)

    def write_comment(self, comment: Comment) -> int:
        """Write the given Comment back to the view."""
        old_text = self.read(comment.region)
        new_text = str(comment)
        if old_text != new_text:
            self.write(comment.region, new_text)

            new_region = Region(comment.start, comment.start + len(new_text))
            _parsed = self._parse_comment(new_region)
            comment.lines = _parsed.lines
            comment.texts = _parsed.texts
            comment.row = _parsed.row
            comment.col = _parsed.col

            return len(new_text) - len(old_text)
        return 0

    def comment_iter(
        self, pos: int = 0, target: int = 0, window: bool = False
    ) -> Iterator[Comment]:
        """Iterate through the comments found in this file, yielding Comment objects.

        Args:
            pos: The position in the file to start searching from.
            target: If set, only yield comments with exactly this many lines.
            window: If true, break up longer comments to fit the filter.
        Yields:
            Comment objects. Continuous series are merged & yielded together.
        """
        queued: Comment | None = None
        _yield = ft.partial(self._yield_comment, target=target, window=window)

        # Rely on Sublime Text's syntax system to find (non-block) comments
        for cur in self._raw_comment_iter(pos):
            if queued is None:
                queued = cur
            elif cur.follows(queued):
                queued += cur
            else:
                yield from _yield(queued)
                queued = cur

        if queued:
            yield from _yield(queued)

    # ------------------
    # `x` Public Methods
    # ------------------
    @property
    def regions(self) -> Iterator:
        """The regions currently selected in the view."""
        yield from self.view.sel()

    @property
    def points(self) -> Iterator:
        """The starting points of the currently selected regions in the view."""
        yield from (region.begin() for region in self.regions)

    @property
    def lines(self) -> Iterator:
        """The first lines of the currently selected regions in the view."""
        yield from (region.lines()[0] for region in self.regions)

    @property
    def selection(self) -> Selection:
        """The current selection object of the view."""
        return self.view.sel()

    @property
    def position(self) -> int:
        """The starting position of the first selected region in the view."""
        return self.selection[0].begin()

    @property
    def syntax(self) -> str:
        """The simplified syntax of the current view."""
        # Literal['py', 'ts', 'other']
        syntax = self.view.settings().get('syntax').lower()
        parts = set(syntax.split('.'))
        if 'python' in parts:
            return 'py'
        elif parts & {'typescript', 'javascript'}:
            return 'ts'
        else:
            return syntax

    @abstractmethod
    def main(self, region: Region) -> Any:
        """The main method to be overridden by subclasses."""
        raise NotImplementedError("Tried to call abstract class's main method.")
