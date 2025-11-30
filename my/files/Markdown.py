############
### HEAD ###
############
### STANDARD
from typing import Annotated, ClassVar, Iterator, Any, Collection, TypeVar, Callable
from collections import deque

### EXTERNAL
import pydantic as pyd
from regex import Pattern
import mdformat
import logfire

### INTERNAL
from ..infra import get_template
from ..utils import ut
from ..typing import typist
from ..types import Buffer, Predicate
from ..regex import RegexStore

############
### DATA ###
############
SubType = TypeVar('SubType', bound='Markdown')


############
### BODY ###
############
class Markdown(pyd.BaseModel):
    TEMPLATE: ClassVar[str] = 'Markdown.md.jinja'
    RGXS: ClassVar[RegexStore] = RegexStore.new(
        options=dict(
            separator=r' *\n+',
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
        node=[r'(?sm)(?P=header)', r'(?P=prose)', r'(?=^#{1,6} |\Z)'],
    )
    BUFFER_FACTORY: ClassVar[Callable[..., Buffer]] = Buffer.new

    # Metadata
    level: Annotated[int, pyd.Field(ge=1, le=6)] = 1
    idx: str = ''
    tags: list[str] = []
    notes: dict[str, Any] = {}

    # Data
    title: str = ''
    prose: Buffer = pyd.Field(default_factory=BUFFER_FACTORY)
    nodes: list['Markdown'] = []

    buffer_factory: Callable[..., Buffer] = pyd.Field(default=BUFFER_FACTORY, exclude=True)

    # -------------------
    # `0` Initial Methods
    # -------------------
    @classmethod
    def new(cls: type[SubType], **kwargs: Any) -> SubType:
        """
        Creates a new Markdown object with the given parameters.
        """
        if 'buffer_factory' not in kwargs:
            kwargs['buffer_factory'] = cls.BUFFER_FACTORY

        # I. Cast simple fields to the right data types
        if 'prose' in kwargs and isinstance(kwargs['prose'], str):
            kwargs['prose'] = kwargs['buffer_factory'](kwargs['prose'])
        if 'tags' in kwargs and not isinstance(kwargs['tags'], list):
            kwargs['tags'] = Predicate.cast_to_list(kwargs['tags'])

        # II. Create descendant nodes
        if 'nodes' in kwargs:
            kwargs['nodes'] = cls._build_tree(
                kwargs['nodes'],
                kwargs.get('level', 1),
                kwargs.get('idx', ''),
                kwargs['buffer_factory'],
            )
        return cls(**kwargs)

    @classmethod
    def _build_tree(
        cls,
        nodes: list | dict,
        level: int,
        idx: str,
        buffer_factory: Callable[..., Buffer],
    ) -> list['Markdown']:
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

        assert typist.all_are(nodes, Markdown) and isinstance(nodes, list)
        return nodes

    @pyd.field_validator('level', mode='after')
    @classmethod
    def _validate_level(cls, level: int) -> int:
        assert 1 <= level <= 6
        return level

    @pyd.field_validator('prose', mode='after')
    @classmethod
    def _validate_prose(cls, prose: Buffer) -> Buffer:
        return prose.strip()

    @pyd.model_serializer
    def _serialize_md(self) -> dict[str, Any]:
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
        """Transforms a number [0, 61] into a single digit, 0-9, then A-Z, then a-z."""
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
        """Transforms a single digit, 0-9, then a-z, then A-Z, into a number [0, 61]."""
        if digit.isdigit():
            return int(digit)
        elif 'A' <= digit <= 'Z':
            return ord(digit) - ord('A') + 10
        elif 'a' <= digit <= 'z':
            return ord(digit) - ord('a') + 36
        else:
            raise ValueError(f'Invalid index digit: {digit}')

    def indent(self: SubType, num: int) -> SubType:
        """Indents this markdown object by a number of levels."""
        for node in self.tree:
            node.level += num
        return self

    @classmethod
    def _trace_path(cls, ancestor: 'Markdown', target: str | list[int]) -> list['Markdown']:
        """
        Returns all nodes between the ancestor (inclusive) and descendant (exclusive).
        """
        origin = ancestor.idx
        if isinstance(target, str):
            if origin == target:
                return []
            elif not target.startswith(origin):
                logfire.error(f'{origin} is not an ancestor of {target}')
                return []
            digits = list(map(cls._digit_to_num, target[len(origin) :]))
        else:
            digits = target

        # I. Find the path from the ancestor to the descendant
        ret: list[Markdown] = [ancestor]
        for digit in digits:
            n = len(ret[-1].nodes)
            if digit >= n:
                logfire.error(f'Index {digit} OOB of {ret[-1].title} (n={n})')
                return []
            ret.append(ret[-1].nodes[digit])
        return ret

    def refresh_indices(self, start: int = 0, end: int | None = None) -> None:
        n = len(self.nodes)
        end = end if end is not None else n
        assert 0 <= start <= end <= n, f'Invalid range: ({start}, {end}) where n={n}'
        for i, child in enumerate(self.nodes[start:end], start):
            child.set_idx(self.idx, i)

    @classmethod
    def _stack_nodes(cls, nodes: deque['Markdown'], level: int) -> list['Markdown']:
        ret = []

        while nodes and nodes[0].level > level:
            child = nodes.popleft()
            if descendants := cls._stack_nodes(nodes, child.level):
                # Don't normally parse Notes nodes that are parseable as yaml data
                note_idx = ut.find(descendants, lambda n: n.title == 'Notes')
                if note_idx and (note_data := descendants[note_idx].from_yaml()):
                    descendants.pop(note_idx)
                    child.notes = note_data
                child.nodes = descendants
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
    ) -> Iterator['Markdown']:
        """A depth-first walk of the document tree."""

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

    def add_node(self, new_nodes: 'Markdown|list[Markdown]', left: bool = False) -> 'Markdown':
        """Appends a node to this markdown object."""
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

    def get(self, **kwargs) -> 'Markdown | None':
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

    def get_idx(self, *, idx: str = '', asc: bool = False, max_d: int = -1) -> 'Markdown | None':
        if idx == self.idx:
            return self
        elif not self.nodes or not max_d or not idx or not idx.startswith(self.idx):
            pass
        elif path := self.trace_path(idx):
            return path[-1]
        return None

    def get_child(
        self, *, child: int = -1, asc: bool = False, max_d: int = -1
    ) -> 'Markdown | None':
        if max_d and 0 <= child < len(self.nodes):
            return self.nodes[child]
        else:
            return None

    def get_title(
        self, *, title: str = '', asc: bool = False, max_d: int = -1
    ) -> 'Markdown | None':
        if not self.nodes or not max_d:
            return None

        title = title.lower()
        return next(
            filter(
                lambda node: node and node.title.lower() == title,
                self.walk(False, asc, max_d),
            ),
            None,
        )

    def get_path(
        self, *, path: list[int] | None = None, asc: bool = False, max_d: int = -1
    ) -> 'Markdown | None':
        if not self.nodes or not max_d or not path:
            return None

        if len(path) > max_d:
            logfire.warn(f'Exceeded max depth {max_d} w/ {len(path)} digits')
            return None
        return trace[-1] if (trace := self.trace_path(path)) else None

    def trace_path(self, target: str | list[int]) -> list['Markdown']:
        """
        Returns all nodes between this node (inclusive) and the target (exclusive).
        """
        return Markdown._trace_path(self, target)

    def set_idx(self, base_idx: str = '', rel_idx: int | str = 0) -> None:
        new_idx = base_idx + self._num_to_digit(rel_idx)
        if new_idx == self.idx:
            return
        else:
            self.idx = new_idx
            for i, child in enumerate(self.nodes):
                child.set_idx(new_idx, i)

    # ------------------
    # `x` Public Methods
    # ------------------
    @property
    def tree(self) -> Iterator['Markdown']:
        """Iterates over all nodes in this markdown object."""
        return self.walk()

    @property
    def prose_tree(self) -> Iterator['Buffer']:
        """Iterates over all prose in this markdown object."""
        return (node.prose for node in self.tree)

    @property
    def prefix(self) -> str:
        if self.idx or self.tags:
            return '`' + ' '.join(filter(bool, [self.idx, *self.tags])) + '`'
        return ''

    @property
    def header(self) -> str:
        return ' '.join(filter(bool, (self.level * '#', self.prefix, self.title)))

    @property
    def fulltext(self) -> str:
        """Returns the full text of this markdown object."""
        parts = [self.header, str(self.prose), *(node.fulltext for node in self.nodes)]
        return '\n\n'.join(parts).strip()

    @classmethod
    def parse(cls, text: str | Buffer, base_level: int = 0) -> list['Markdown']:
        """
        Parses a document into one or more markdown objects, each of depth 1.
        """
        nodes = deque(
            cls.new(
                # Data
                title=match.at('title'),
                prose=match.at('prose'),
                # Metadata
                level=len(match.at('marks')),
                tags=match.get('tag'),
                idx=match.at('idx'),
            )
            for match in Markdown.RGXS.finditer('node', text)
        )
        return cls._stack_nodes(nodes, level=base_level)

    def parse_predicates(self) -> Predicate:
        return Predicate.new(self.from_yaml())

    def reparse_prose(self) -> None:
        if first_node := Markdown.RGXS.search('node', self.prose):
            node_text = self.prose[first_node.start :]
            self.prose.drop((first_node.start, len(self.prose)))
            self.add_node(Markdown.parse(node_text, base_level=1), left=True)

    def from_yaml(self) -> dict[str, Any]:
        # Handle top-level data
        ret = typist.from_yaml(str(self.prose)) if self.prose else {}

        # Interpret children as sub-dictionaries
        for child in self.nodes:
            if c_data := child.from_yaml():
                ret[child.title] = c_data

        return ret

    def to_string(self, strip_notes: bool = False, fix: bool = True) -> str:
        data = self.model_dump()
        if strip_notes and 'notes' in data:
            del data['notes']

        body = get_template(self.TEMPLATE).render(data)
        if fix:
            body = mdformat.text(body)
        return body

    def __str__(self) -> str:
        return self.to_string()

    def pop(self, **kwargs) -> 'Markdown | None':
        """Pops a node from this markdown object."""
        # I. Find the target node
        if not (target := self.get(**kwargs)):
            return None

        # II. Identify the parent of the target node
        assert (path := self.trace_path(target.idx)), 'Path trace failed'
        parent = path[-1]

        # III. Remove the node and update its siblings' matrices
        index = parent.nodes.index(target)
        parent.nodes.pop(index)
        parent.refresh_indices(index)
        return target

    def replace(self, orig: str | Pattern, new: str) -> None:
        for node in self.tree:
            node.prose.replace(orig, new)

    def __len__(self) -> int:
        """Returns the number of nodes in this markdown object."""
        return len(self.nodes)

    def __isub__(self, nodes: Collection[str]) -> None:
        """
        Removes nodes with the given indices from this markdown object.
        """
        for title in nodes:
            if node := self.pop(title=title):
                logfire.info(f'Removed node: {node.title} ({node.idx})')
            else:
                logfire.warn(f'Node not found: {title}')
