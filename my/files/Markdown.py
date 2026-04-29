############
### HEAD ###
############
### STANDARD
from __future__ import annotations
from typing import Annotated, ClassVar, Any, Self, cast
from collections.abc import Iterator, Collection, Callable, Iterable
from collections import deque
from pathlib import Path
import logging

### EXTERNAL
import pydantic as pyd
from regex import Pattern
import mdformat

### INTERNAL
from ..infra import get_template
from ..utils import ut
from ..typing import typist
from ..types import Buffer, Predicate
from ..regex import RegexStore


############
### BODY ###
############
class Markdown(pyd.BaseModel):
    """Hierarchical markdown document model with parsing and manipulation.

    Supports parsing from text, tree traversal, node manipulation, YAML data
    extraction, and rendering back to markdown with optional formatting.
    """

    LOGGER: ClassVar[logging.Logger] = logging.getLogger('Markdown')
    TEMPLATE: ClassVar[str] = 'Markdown.md.jinja'
    BUFFER_FACTORY: ClassVar[Callable[..., Buffer]] = Buffer.new
    RGXS: ClassVar[RegexStore] = RegexStore.new(
        options=dict(
            separator=r' *\n+',
            lazy_load=True,
        ),
        # Components
        marks=r'(?m)^#{1,6} +',
        idx=r'(?<=## `)[\dA-Za-z]+\b',
        tag=(r' ?\b[^\s`]+\b', str.strip),
        tags=(r'`(?P=idx)?(?P=tag)*` +', lambda s: s.strip('` ')),
        title=(r'(?m)[^\n]+$', str.strip),
        prose=r'(?sm)^.+?$',
        # Patterns
        header=r'(?P=marks)(?P=tags)?(?P=title)',
        document=[
            r'(?sm)^# (?P=tags)?(?P=title)',
            r'(?P=prose)(?=\n+# |\Z)',
        ],
        node=[r'(?sm)(?P=header) *\n+(?P=prose)\n*(?=^#{1,6} |\Z)'],
    )

    # Metadata
    #: The index string for this markdown node, determined by its position among siblings.
    idx: str = ''

    #: Optional tags associated with this markdown node, stored as a list of strings.
    #: Rendered as a bactic-wrapped, space-separated string immediately following the header hashes.
    tags: list[str] = []

    #: Arbitrary YAML data attached to this markdown node. This is rendered as YAML frontmatter for
    #: root-level nodes, and as fenced yaml blocks immediately following the header for any
    #: others.
    notes: dict[str, Any] = {}

    #: The header level of this markdown node (1-6). Root-level nodes should have level 1.
    level: Annotated[int, pyd.Field(ge=1, le=6)] = 1

    #: The header title of this markdown node, excluding tags and indices.
    title: str = ''

    #: The raw text content of this markdown node, excluding child nodes.
    #: Stored as a Buffer, but it can be initialized from a string or Buffer.
    prose: Buffer = pyd.Field(default_factory=BUFFER_FACTORY)

    #: Child nodes, ordered as they appear in the document.
    #: Each node's `idx` is determined by its position among siblings.
    nodes: list[Markdown] = []

    #: A factory for the Buffer subtype that this (sub)class uses.
    buffer_factory: Callable[..., Buffer] = pyd.Field(default=BUFFER_FACTORY, exclude=True)

    # -------------------
    # `.` Initial Methods
    # -------------------
    @pyd.model_validator(mode='before')
    @classmethod
    def _new(cls, kwargs: dict) -> dict:
        """Validates and coerces incoming data upon instantiation.

        Handles conversion of prose strings to Buffers, tags to lists, and recursive
        construction of child nodes with automatic index assignment.

        Args:
            kwargs: Node properties (level, idx, tags, title, prose, nodes, etc.).
        """
        if 'buffer_factory' not in kwargs:
            kwargs['buffer_factory'] = cls.BUFFER_FACTORY

        # I. Cast simple fields to the right data types
        if 'prose' in kwargs and isinstance(kwargs['prose'], str):
            kwargs['prose'] = kwargs['buffer_factory'](kwargs['prose']).strip()
        if 'tags' in kwargs and not isinstance(kwargs['tags'], list):
            kwargs['tags'] = typist.cast(kwargs['tags'], list[str]) or [str(kwargs['tags'])]

        # II. Create descendant nodes
        if 'nodes' in kwargs:
            kwargs['nodes'] = cls._build_tree(
                kwargs['nodes'],
                kwargs.get('level', 1),
                kwargs.get('idx', ''),
                kwargs['buffer_factory'],
            )

        return kwargs

    @classmethod
    def new(cls, source: str | Path | Iterable[str] | None = None, **kwargs: Any) -> Self:
        """Create a new Markdown node with proper type conversions and tree building.

        Handles conversion of prose strings to Buffers, tags to lists, and recursive
        construction of child nodes with automatic index assignment.

        Args:
            source: Markdown text or iterable of lines to initialize the prose buffer.
            **kwargs: Node properties (level, idx, tags, title, prose, nodes, etc.).
        Returns:
            New Markdown instance with properly initialized tree structure.
        """
        if source is None:
            return cls(**kwargs)
        elif isinstance(source, (str, bytes, Path, Buffer)):
            text = str(source)
            if '\n' in text or len(text) > 256:
                kwargs['prose'] = cls.BUFFER_FACTORY(text)

    @classmethod
    def _build_tree(
        cls,
        nodes: list | dict,
        level: int,
        idx: str,
        buffer_factory: Callable[..., Buffer],
    ) -> list[Markdown]:
        """Recursively build a tree of Markdown nodes from raw data.

        Args:
            nodes: List of raw node data (dicts or Markdown instances).
            level: Parent node's header level.
            idx: Parent node's index string.
            buffer_factory: Factory function to create Buffer instances.
        Returns:
            List of constructed Markdown nodes that are direct children.
        """
        if not isinstance(nodes, list):
            nodes = [nodes]

        for i, node in enumerate(nodes):
            if isinstance(node, dict):
                node_data = (
                    dict(
                        level=level + 1,
                        idx=idx + cls._num_to_digit(i),
                        prose=buffer_factory(nodes[i].pop('prose', '')),
                    )
                    | nodes[i]
                )
                nodes[i] = Markdown.new(**node_data)
            elif isinstance(node, Markdown):
                node.level = level + 1
                node.set_idx(idx, i)
            else:
                raise TypeError(f'Invalid node type: {type(node)}')
        assert typist.check(nodes, list[Markdown]), f'Invalid node type: {list(map(type, nodes))}'
        return nodes

    @pyd.model_serializer
    def _serialize_md(self) -> dict[str, Any]:
        """Custom serializer to convert the Markdown object into a dictionary."""
        ret = dict(
            level=self.level,
            idx=self.idx,
            tags=self.tags,
            title=self.title,
            header=self.header,
            prose=self.prose,
            nodes=[node.model_dump() for node in self.nodes],
            notes=typist.to_yaml(self.notes),
        )
        return ret

    # -------------------
    # `-` Private Methods
    # -------------------
    @staticmethod
    def _num_to_digit(num: int | str) -> str:
        """Transforms a number [0, 61] into a single digit (0-9), then A-Z, then a-z.

        Args:
            num: Number or single-character digit to convert.
        Returns:
            Single-character digit string.
        """
        if isinstance(num, str):
            if len(num) == 1:
                return num
            else:
                assert num.isdigit(), f'Invalid index digit: {num}'
                num = int(num)
        assert 0 <= num <= 61, f'Invalid index number: 0 <= {num} <= 61'
        if num < 10:
            return str(num)
        elif num < 36:
            return chr(ord('A') + num - 10)
        else:
            return chr(ord('a') + num - 36)

    @staticmethod
    def _digit_to_num(digit: str) -> int:
        """Transforms a single digit (0-9) then a-z, then A-Z, into a number [0, 61].

        Args:
            digit: Single-character digit to convert.
        Returns:
            Corresponding decimal integer.
        """
        if digit.isdigit():
            return int(digit)
        elif 'A' <= digit <= 'Z':
            return ord(digit) - ord('A') + 10
        elif 'a' <= digit <= 'z':
            return ord(digit) - ord('a') + 36
        else:
            raise ValueError(f'Invalid index digit: {digit}')

    def indent(self, num: int) -> Self:
        """Increase the header level of this node and all descendants.

        Args:
            num: Number of levels to indent (can be negative to outdent).
        Returns:
            Self for chaining.
        """
        for node in self.tree:
            node.level += num
        return self

    @classmethod
    def _trace_path(cls, ancestor: Markdown, target: str | list[int]) -> list[Markdown]:
        """Returns all nodes between the ancestor and descendant (inclusive).

        Args:
            ancestor: Starting Markdown node (ancestor).
            target: Target index string or list of child indices.
        Returns:
            List of nodes from ancestor to target.
        """
        origin = ancestor.idx
        if isinstance(target, str):
            if origin == target:
                return []
            elif not target.startswith(origin):
                cls.LOGGER.error(f'{origin} is not an ancestor of {target}')
                return []
            digits = list(map(cls._digit_to_num, target[len(origin) :]))
        else:
            digits = target

        # I. Find the path from the ancestor to the descendant
        ret: list[Markdown] = [ancestor]
        for digit in digits:
            if digit >= (n := len(ret[-1].nodes)):
                cls.LOGGER.error(f'Index {digit} OOB of {ret[-1].title} (n={n})')
                return []
            ret.append(ret[-1].nodes[digit])
        return ret

    def refresh_indices(self, start: int = 0, end: int | None = None) -> None:
        """Update the indices of child nodes in a range.

        Args:
            start: First child index to update (default: 0).
            end: Last child index (exclusive, default: all children).
        """
        n = len(self.nodes)
        if start >= n:
            return

        end = end if end is not None else n
        assert 0 <= start <= end <= n, f'Invalid range: ({start}, {end}) where n={n}'
        for i, child in enumerate(self.nodes[start:end], start):
            child.set_idx(self.idx, i)

    @classmethod
    def _stack_nodes(cls, nodes: deque[Self], level: int) -> list[Self]:
        """Recursively stack nodes into a hierarchical tree based on header levels.

        Args:
            nodes: Deque of Markdown nodes to process.
            level: Current header level to consider.
        Returns:
            List of the "top-level" nodes (ones without parents).
        """
        ret = []

        while nodes and nodes[0].level > level:
            child = nodes.popleft()
            if descendants := cls._stack_nodes(nodes, child.level):
                # Don't normally parse Notes nodes that are parseable as yaml data
                note_idx = ut.find(descendants, lambda n: n.title == 'Notes')
                if note_idx != -1 and (note_data := descendants[note_idx].from_yaml()):
                    descendants.pop(note_idx)
                    child.notes = note_data
                child.nodes = cast('list[Markdown]', descendants)
            ret.append(child)

        return ret

    # -------------------
    # `+` Primary Methods
    # -------------------
    def walk(
        self,
        skip_self: bool = False,
        asc: bool = False,
        max_d: int = -1,
    ) -> Iterator[Markdown]:
        """Perform depth-first traversal of the document tree.

        Handles dynamic tree modifications during iteration by tracking size changes.

        Args:
            skip_self: Whether to exclude this node from iteration.
            asc: Whether to traverse in reverse order (right to left).
            max_d: Maximum depth to traverse (-1 for unlimited).
        Yields:
            Markdown nodes in depth-first order.
        """
        # I. Yield the root by default
        if not skip_self:
            yield self

        # II. Exit immediately if we've run out of room
        if max_d == 0 or not self.nodes:
            return
        new_depth = max_d - 1 if max_d != -1 else -1

        n = len(self.nodes)
        i = n - 1 if asc else 0
        while 0 <= i < n:
            yield self.nodes[i]

            # II.i. If this child wasn't removed, recurse into its children
            if (delta := len(self.nodes) - n) >= 0 and new_depth > 0:
                yield from self.nodes[i].walk(True, asc, new_depth)

            # II.ii. Update the index only if the caller (likely) modified what's ahead
            if delta > 0 if asc else delta < 0:
                i += delta

            # II.iii. Advance to the next node according to direction
            n += delta
            i += -1 if asc else 1

    def add_node(self, new_nodes: Markdown | list[Markdown], left: bool = False) -> Markdown:
        """Add child nodes to this markdown node.

        Args:
            new_nodes: Single node or list of nodes to add.
            left: Whether to prepend (True) or append (False).
        Returns:
            Self for chaining.
        """
        if isinstance(new_nodes, Markdown):
            new_nodes = [new_nodes]

        if new_nodes:
            n_cur = len(self.nodes)
            if left:
                # I.i. Refresh the entire index
                self.nodes = new_nodes + self.nodes
                self.refresh_indices(start=0)
            else:
                # I.ii. Just refresh the new nodes
                self.nodes.extend(new_nodes)
                self.refresh_indices(start=n_cur)

        return self

    def get(self, **kwargs: Any) -> Markdown | None:
        """Get a descendant node by one of various criteria.

        Args:
            **kwargs: One of: idx, child, title, or path.
        Returns:
            Matching Markdown node or None.
        Raises:
            ValueError: If invalid parameter combination.
        """
        if 'idx' in kwargs:
            return self.get_idx(**kwargs)
        elif 'child' in kwargs:
            return self.get_child(**kwargs)
        elif 'title' in kwargs:
            return self.get_title(**kwargs)
        elif 'path' in kwargs:
            return self.get_path(**kwargs)
        else:
            raise ValueError(f'Invalid Markdown.get() parameters: {list(kwargs.keys())}')

    def get_idx(self, *, idx: str = '', asc: bool = False, max_d: int = -1) -> Markdown | None:
        """Get a descendant node by its index string.

        Args:
            idx: Target index string.
            asc: Whether to traverse in reverse order (right to left).
            max_d: Maximum depth to traverse (-1 for unlimited).
        Returns:
            Matching Markdown node or None.
        """
        if idx == self.idx:
            return self
        elif not self.nodes or not max_d or not idx or not idx.startswith(self.idx):
            pass
        elif path := self.trace_path(idx):
            return path[-1]
        return None

    def get_child(self, *, child: int = -1, asc: bool = False, max_d: int = -1) -> Markdown | None:
        """Get a direct child node by its index.

        Args:
            child: Child index (0-based).
            asc: Whether to traverse in reverse order (right to left).
            max_d: Maximum depth to traverse (-1 for unlimited).
        Returns:
            Matching Markdown node or None.
        """
        if max_d != 0 and 0 <= child < len(self.nodes):
            return self.nodes[child]
        else:
            return None

    def get_title(self, *, title: str = '', asc: bool = False, max_d: int = -1) -> Markdown | None:
        """Get a descendant node by its title.

        Args:
            title: Target title string.
            asc: Whether to traverse in reverse order (right to left).
            max_d: Maximum depth to traverse (-1 for unlimited).
        Returns:
            Matching Markdown node or None.
        """
        title = title.lower()
        return next(
            filter(
                lambda node: node.title.lower() == title,
                self.walk(False, asc, max_d),
            ),
            None,
        )

    def get_path(
        self, *, path: list[int] | None = None, asc: bool = False, max_d: int = -1
    ) -> Markdown | None:
        """Get a descendant node by a path of child indices (each relative to its parent).

        Args:
            path: List of child indices leading to the target node.
            asc: Whether to traverse in reverse order (right to left).
            max_d: Maximum depth to traverse (-1 for unlimited).
        Returns:
            Matching Markdown node or None.
        """
        if not self.nodes or not max_d or path is None:
            return None
        elif not path:
            return self
        elif len(path) > max_d > 0:
            self.LOGGER.warning(f'Exceeded max depth {max_d} w/ {len(path)} digits')
            return None
        return trace[-1] if (trace := self.trace_path(path)) else None

    def trace_path(self, target: str | list[int]) -> list[Markdown]:
        """Get all nodes along the path from this node to a target.

        Args:
            target: Target index string or list of child indices.
        Returns:
            List of nodes from this node to target (inclusive).
            Empty list if target not found or invalid.
        """
        return Markdown._trace_path(self, target)

    def set_idx(self, base_idx: str = '', rel_idx: int | str = 0) -> None:
        """Set this node's index and recursively update all descendants.

        Args:
            base_idx: Parent's index string.
            rel_idx: This node's position relative to parent (0-61).
        """
        new_idx = base_idx + self._num_to_digit(rel_idx)
        if new_idx == self.idx:
            return
        else:
            self.idx = new_idx
            for i, child in enumerate(self.nodes):
                child.set_idx(new_idx, i)

    # ------------------
    # `*` Public Methods
    # ------------------
    # ---------------
    # `*0` Properties
    # ---------------
    @property
    def frontmatter(self) -> dict[str, Any]:
        """The YAML data attached to this markdown node."""
        return self.notes

    @property
    def tree(self) -> Iterator[Markdown]:
        """Iterates depth-first over all nodes in this markdown object. See walk()."""
        return self.walk()

    @property
    def prose_tree(self) -> Iterator[Buffer]:
        """Iterates depth-first over all text content in this markdown object."""
        return (node.prose for node in self.tree)

    @property
    def prefix(self) -> str:
        """The bactic-escaped prefix for this node's title, or emptystring if there is none."""
        if self.idx or self.tags:
            return '`' + ' '.join(filter(bool, [self.idx, *self.tags])) + '`'
        return ''

    @property
    def header(self) -> str:
        """Returns the full, markdown-ready header line for this node."""
        return ' '.join(filter(bool, (self.level * '#', self.prefix, self.title)))

    @property
    def fulltext(self) -> str:
        """Returns the full text of this markdown object."""
        parts = [self.header, str(self.prose), *(node.fulltext for node in self.nodes)]
        return '\n\n'.join(parts).strip()

    # -------------
    # `*1` Standard
    # -------------
    def __str__(self) -> str:
        return self.to_string()

    def __bool__(self) -> bool:
        return bool(self.title or self.prose)

    def pop(self, **kwargs: Any) -> Markdown | None:
        """Remove and return a descendant node.

        Args:
            **kwargs: Node search criteria (passed to get()).
        Returns:
            Removed node, or None if not found.
        """
        # I. Find the target node
        if not (target := self.get(**kwargs)):
            return None

        # II. Identify the parent of the target node
        path = self.trace_path(target.idx)
        assert len(path) >= 2, 'Path trace failed'
        parent = path[-2]

        # III. Remove the node and update its siblings' matrices
        child_index = self._digit_to_num(target.idx[-1])
        parent.nodes.pop(child_index)
        parent.refresh_indices(start=child_index)
        return target

    def replace(self, orig: str | Pattern, new: str) -> None:
        """Replace text in all prose buffers throughout the tree.

        Args:
            orig: String or regex pattern to replace.
            new: Replacement string.
        """
        for node in self.tree:
            node.prose.replace(orig, new)

    def __len__(self) -> int:
        """Returns the number of nodes in this markdown object."""
        return len(self.nodes)

    def __isub__(self, nodes: Collection[str]) -> Self:
        """Removes nodes with the given indices from this markdown object."""
        for title in nodes:
            if node := self.pop(title=title):
                self.LOGGER.info(f'Removed node: {node.title} ({node.idx})')
            else:
                self.LOGGER.warning(f'Node not found: {title}')
        return self

    # -------------
    # `*1` Standard
    # -------------
    @classmethod
    def parse(cls, text: str | Buffer, base_level: int = 0) -> list[Self]:
        """Parse markdown text into a hierarchical tree structure.

        Recognizes headers, tags, indices, and prose to build nested Markdown nodes.
        Automatically handles "Notes" sections by parsing them as YAML.

        Args:
            text: Markdown text or Buffer to parse.
            base_level: Minimum header level to parse (default: 0 for all).
        Returns:
            List of top-level Markdown nodes with nested children.
        """
        nodes = deque(
            cls.new(
                # Data
                title=match.at('title'),
                prose=match.at('prose'),
                # Metadata
                level=len(match.at('marks')),
                tags=match['tag'],
                idx=match.at('idx'),
            )
            for match in Markdown.RGXS.finditer('node', text)
        )
        return cls._stack_nodes(nodes, level=base_level)

    def parse_predicates(self) -> Predicate:
        """Parse a YAML-filled markdown document into a Predicate object."""
        return Predicate.new(self.from_yaml())

    def reparse_prose(self) -> None:
        """Identify and parse newly-created header nodes embedded in this node's raw prose."""
        if first_node := Markdown.RGXS.search('node', self.prose):
            node_text = self.prose[first_node.start :]
            self.prose.drop((first_node.start, len(self.prose)))
            self.add_node(Markdown.parse(node_text, base_level=1), left=True)

    def from_yaml(self) -> dict[str, Any]:
        """Parses prose as YAML and recursively collects child nodes as nested dicts.

        Returns:
            Dictionary of parsed YAML data with child nodes as nested keys.
        """
        # Handle top-level data
        ret = {}
        if self.prose:
            try:
                ret = typist.from_yaml(str(self.prose))
            except TypeError:
                return {}

        # Interpret children as sub-dictionaries
        for child in self.nodes:
            if c_data := child.from_yaml():
                ret[child.title] = c_data

        return ret

    def to_string(self, strip_notes: bool = False, fix: bool = True) -> str:
        """Render this node and its children as markdown text.

        Args:
            strip_notes: Whether to exclude notes from output.
            fix: Whether to apply mdformat formatting.
        Returns:
            Formatted markdown string.
        """
        data = self.model_dump()
        if strip_notes and 'notes' in data:
            del data['notes']

        body = get_template(self.TEMPLATE).render(data)
        if fix:
            body = mdformat.text(body)
        return body
