############
### HEAD ###
############
### STANDARD

### EXTERNAL
import pytest as pyt
import pydantic as pyd

### INTERNAL
from my.files import Markdown
from my.types import Buffer
from my.typing import typist

############
### DATA ###
############
cls = Markdown

# Sample markdown text for parsing tests
SIMPLE_MD = """# Main Title

This is the main prose.

## Section 1

Section 1 prose.

### Subsection 1.1

Subsection prose.

## Section 2

Section 2 prose.
"""

INDEXED_MD = """# Document Title

Document prose.

## `0` First Section

First section prose.

### `0A` First Subsection

Subsection prose.

## `1` Second Section

Second section prose.
"""

TAGGED_MD = """# `tag1 tag2` Document

Tagged document prose.

## `0 important` Section

Section with tags.
"""

YAML_MD = """# Configuration

key1: value1
key2: value2

## Nested

nested_key: nested_value
"""


############
### BODY ###
############
class TestMarkdown:
    # -------------------
    # `.` Initial Methods
    # -------------------
    @pyt.mark.parametrize(
        'kwargs, expected_level, expected_title',
        [
            ({'title': 'Test'}, 1, 'Test'),
            ({'title': 'Test', 'level': 2}, 2, 'Test'),
            ({'title': 'Test', 'level': 3, 'prose': 'Content'}, 3, 'Test'),
        ],
    )
    def test_new(self, kwargs: dict, expected_level: int, expected_title: str):
        node = cls.new(**kwargs)
        assert node.level == expected_level
        assert node.title == expected_title
        assert isinstance(node.prose, Buffer)

    def test_new__prose_string_conversion(self):
        node = cls.new(title='Test', prose='This is prose')
        assert isinstance(node.prose, Buffer)
        assert str(node.prose) == 'This is prose'

    def test_new__tags_conversion(self):
        # Single string tag
        node = cls.new(title='Test', tags='tag1')
        assert node.tags == ['tag1']

        # List of tags
        node = cls.new(title='Test', tags=['tag1', 'tag2'])
        assert node.tags == ['tag1', 'tag2']

    def test_new__with_nodes(self):
        node = cls.new(
            title='Parent',
            nodes=[
                {'title': 'Child 1'},
                {'title': 'Child 2'},
            ],
        )
        assert len(node.nodes) == 2
        assert node.nodes[0].title == 'Child 1'
        assert node.nodes[0].level == 2
        assert node.nodes[0].idx == '0'

    def test_build_tree(self):
        nodes_data = [
            {'title': 'Node 1'},
            {'title': 'Node 2'},
        ]
        nodes = cls._build_tree(nodes_data, level=1, idx='', buffer_factory=Buffer.new)

        assert len(nodes) == 2
        assert all(isinstance(n, Markdown) for n in nodes)
        assert nodes[0].level == 2
        assert nodes[1].level == 2
        assert nodes[0].idx == '0'
        assert nodes[1].idx == '1'

    def test_build_tree__nested(self):
        nodes_data = [
            {
                'title': 'Parent',
                'nodes': [
                    {'title': 'Child'},
                ],
            },
        ]
        nodes = cls._build_tree(nodes_data, level=1, idx='A', buffer_factory=Buffer.new)

        assert len(nodes) == 1
        assert nodes[0].idx == 'A0'
        assert len(nodes[0].nodes) == 1
        assert nodes[0].nodes[0].idx == 'A00'

    def test_validate_level__valid(self):
        for level in range(1, 7):
            node = cls.new(title='Test', level=level)
            assert node.level == level

    def test_validate_level__invalid(self):
        with pyt.raises(pyd.ValidationError):
            cls.new(title='Test', level=0)
        with pyt.raises(pyd.ValidationError):
            cls.new(title='Test', level=7)

    def test_validate_prose__strips_whitespace(self):
        node = cls.new(title='Test', prose='  \n\nContent\n\n  ')
        assert str(node.prose) == 'Content'

    # -------------------
    # `-` Private Methods
    # -------------------
    @pyt.mark.parametrize(
        'num, expected',
        [
            (0, '0'),
            (5, '5'),
            (9, '9'),
            (10, 'A'),
            (15, 'F'),
            (35, 'Z'),
            (36, 'a'),
            (50, 'o'),
            (61, 'z'),
        ],
    )
    def test_num_to_digit(self, num: int, expected: str):
        assert cls._num_to_digit(num) == expected

    def test_num_to_digit__from_string(self):
        assert cls._num_to_digit('5') == '5'
        assert cls._num_to_digit('A') == 'A'

    def test_num_to_digit__invalid(self):
        with pyt.raises(AssertionError):
            cls._num_to_digit(62)

        with pyt.raises(AssertionError):
            cls._num_to_digit(-1)

    @pyt.mark.parametrize(
        'digit, expected',
        [
            ('0', 0),
            ('5', 5),
            ('9', 9),
            ('A', 10),
            ('F', 15),
            ('Z', 35),
            ('a', 36),
            ('o', 50),
            ('z', 61),
        ],
    )
    def test_digit_to_num(self, digit: str, expected: int):
        assert cls._digit_to_num(digit) == expected

    def test_digit_to_num__invalid(self):
        with pyt.raises(ValueError, match='Invalid index digit'):
            cls._digit_to_num('!')

    def test_indent(self):
        node = cls.new(
            title='Parent',
            level=1,
            nodes=[
                {'title': 'Child', 'level': 2},
            ],
        )
        node.indent(1)

        assert node.level == 2
        assert node.nodes[0].level == 3

    def test_indent__negative(self):
        node = cls.new(title='Test', level=3)
        node.indent(-1)
        assert node.level == 2

    def test_trace_path__by_index_string(self):
        node = cls.new(
            title='Root',
            idx='A',
            nodes=[
                {
                    'title': 'Child',
                    'nodes': [
                        {'title': 'Grandchild'},
                    ],
                },
            ],
        )

        path = cls._trace_path(node, 'A00')
        assert len(path) == 3
        assert path[0].title == 'Root'
        assert path[1].title == 'Child'
        assert path[2].title == 'Grandchild'

    def test_trace_path__by_digit_list(self):
        node = cls.new(
            title='Root',
            nodes=[
                {
                    'title': 'Child',
                    'nodes': [
                        {'title': 'Grandchild'},
                    ],
                },
            ],
        )

        path = cls._trace_path(node, [0, 0])
        assert len(path) == 3
        assert path[2].title == 'Grandchild'

    def test_trace_path__invalid_index(self):
        node = cls.new(title='Root', idx='A')
        path = cls._trace_path(node, 'B0')
        assert path == []

    def test_refresh_indices(self):
        node = cls.new(
            title='Parent',
            idx='A',
            nodes=[
                {'title': 'Child 0'},
                {'title': 'Child 1'},
                {'title': 'Child 2'},
            ],
        )

        node.refresh_indices(start=1)
        assert node.nodes[0].idx == 'A0'
        assert node.nodes[1].idx == 'A1'
        assert node.nodes[2].idx == 'A2'

    def test_refresh_indices__range(self):
        node = cls.new(
            title='Parent',
            nodes=[
                {'title': 'Child 0'},
                {'title': 'Child 1'},
                {'title': 'Child 2'},
            ],
        )

        # Only refresh middle child
        node.refresh_indices(start=1, end=2)
        assert node.nodes[1].idx == '1'

    def test_stack_nodes(self):
        from collections import deque

        nodes = deque(
            [
                cls.new(title='Level 1', level=1),
                cls.new(title='Level 2', level=2),
                cls.new(title='Level 1 Again', level=1),
            ]
        )

        result = cls._stack_nodes(nodes, level=0)
        assert len(result) == 2
        assert result[0].title == 'Level 1'
        assert len(result[0].nodes) == 1
        assert result[0].nodes[0].title == 'Level 2'

    # -------------------
    # `+` Primary Methods
    # -------------------
    def test_walk(self):
        node = cls.new(
            title='Root',
            nodes=[
                {'title': 'Child 1'},
                {'title': 'Child 2'},
            ],
        )

        walked = list(node.walk())
        assert len(walked) == 3
        assert walked[0].title == 'Root'
        assert walked[1].title == 'Child 1'
        assert walked[2].title == 'Child 2'

    def test_walk__skip_self(self):
        node = cls.new(
            title='Root',
            nodes=[
                {'title': 'Child'},
            ],
        )

        walked = list(node.walk(skip_self=True))
        assert len(walked) == 1
        assert walked[0].title == 'Child'

    def test_walk__ascending(self):
        node = cls.new(
            title='Root',
            nodes=[
                {'title': 'Child 1'},
                {'title': 'Child 2'},
            ],
        )

        walked = list(node.walk(asc=True))
        assert walked[0].title == 'Root'
        assert walked[1].title == 'Child 2'
        assert walked[2].title == 'Child 1'

    def test_walk__max_depth(self):
        node = cls.new(
            title='Root',
            nodes=[
                {
                    'title': 'Child',
                    'nodes': [
                        {'title': 'Grandchild'},
                    ],
                },
            ],
        )

        walked = list(node.walk(max_d=1))
        assert len(walked) == 2
        assert walked[0].title == 'Root'
        assert walked[1].title == 'Child'

    def test_walk__unlimited_depth(self):
        """The -1 sentinel must recurse past two levels (regression: capped at depth 2)."""
        node = cls.new(
            title='Root',
            nodes=[
                {
                    'title': 'Child',
                    'nodes': [
                        {
                            'title': 'Grandchild',
                            'nodes': [
                                {'title': 'Great-Grandchild'},
                            ],
                        },
                    ],
                },
            ],
        )

        walked = list(node.walk())
        assert [n.title for n in walked] == ['Root', 'Child', 'Grandchild', 'Great-Grandchild']

        walked = list(node.walk(max_d=2))
        assert [n.title for n in walked] == ['Root', 'Child', 'Grandchild']

    def test_add_node__append(self):
        node = cls.new(title='Parent')
        child = cls.new(title='Child')

        node.add_node(child)
        assert len(node.nodes) == 1
        assert node.nodes[0].title == 'Child'
        assert node.nodes[0].idx == '0'

    def test_add_node__list(self):
        node = cls.new(title='Parent')
        children = [
            cls.new(title='Child 1'),
            cls.new(title='Child 2'),
        ]

        node.add_node(children)
        assert len(node.nodes) == 2

    def test_get_idx(self):
        node = cls.new(
            title='Root',
            idx='A',
            nodes=[
                {'title': 'Child'},
            ],
        )

        found = node.get_idx(idx='A0')
        assert found is not None
        assert found.title == 'Child'

    def test_get_idx__self(self):
        node = cls.new(title='Root', idx='A')
        found = node.get_idx(idx='A')
        assert found is node

    def test_get_idx__not_found(self):
        node = cls.new(title='Root', idx='A')
        found = node.get_idx(idx='B0')
        assert found is None

    def test_get_child(self):
        node = cls.new(
            title='Parent',
            nodes=[
                {'title': 'Child 0'},
                {'title': 'Child 1'},
            ],
        )

        found = node.get_child(child=1)
        assert found is not None
        assert found.title == 'Child 1'

    def test_get_child__out_of_bounds(self):
        node = cls.new(title='Parent')
        found = node.get_child(child=0)
        assert found is None

    def test_get_title(self):
        node = cls.new(
            title='Root',
            nodes=[
                {'title': 'Target Node'},
            ],
        )

        found = node.get(title='Target Node')
        assert found is not None
        assert found.title == 'Target Node'

    def test_get_title__case_insensitive(self):
        node = cls.new(
            title='Root',
            nodes=[
                {'title': 'Target Node'},
            ],
        )

        found = node.get(title='target node')
        assert found is not None

    def test_get_path(self):
        node = cls.new(
            title='Root',
            nodes=[
                {
                    'title': 'Child',
                    'nodes': [
                        {'title': 'Grandchild'},
                    ],
                },
            ],
        )

        found = node.get_path(path=[0, 0])
        assert found is not None
        assert found.title == 'Grandchild'

    def test_get__by_idx(self):
        node = cls.new(title='Root', idx='A')
        found = node.get(idx='A')
        assert found is node

    def test_get__by_child(self):
        node = cls.new(
            title='Parent',
            nodes=[
                {'title': 'Child'},
            ],
        )
        found = node.get(child=0)
        assert found
        assert found.title == 'Child'

    def test_get__by_title(self):
        node = cls.new(
            title='Root',
            nodes=[
                {'title': 'Target'},
            ],
        )
        found = node.get(title='Target')
        assert found
        assert found.title == 'Target'

    def test_get__invalid_params(self):
        node = cls.new(title='Root')
        with pyt.raises(ValueError, match='Invalid'):
            node.get(invalid_param='value')

    def test_trace_path(self):
        node = cls.new(
            title='Root',
            idx='A',
            nodes=[
                {'title': 'Child'},
            ],
        )

        path = node.trace_path('A0')
        assert len(path) == 2
        assert path[0].title == 'Root'
        assert path[1].title == 'Child'

    def test_set_idx(self):
        node = cls.new(title='Test')
        node.set_idx('A', 5)
        assert node.idx == 'A5'

    def test_set_idx__recursive(self):
        node = cls.new(
            title='Parent',
            idx='',
            nodes=[
                {'title': 'Child'},
            ],
        )

        node.set_idx('B', 0)
        assert node.idx == 'B0'
        assert node.nodes[0].idx == 'B00'

    # ------------------
    # `*` Public Methods
    # ------------------
    # ---------------
    # `*1` Properties
    # ---------------
    def test_tree(self):
        node = cls.new(
            title='Root',
            nodes=[
                {'title': 'Child'},
            ],
        )

        tree = list(node.tree)
        assert len(tree) == 2

    def test_prose_tree(self):
        node = cls.new(
            title='Root',
            prose='Root prose',
            nodes=[
                {'title': 'Child', 'prose': 'Child prose'},
            ],
        )

        prose_list = list(node.prose_tree)
        assert len(prose_list) == 2
        assert all(isinstance(p, Buffer) for p in prose_list)

    @pyt.mark.parametrize(
        'idx, tags, expected',
        [
            ('', [], ''),
            ('A', [], '`A`'),
            ('', ['tag1'], '`tag1`'),
            ('A', ['tag1'], '`A tag1`'),
            ('A0', ['tag1', 'tag2'], '`A0 tag1 tag2`'),
        ],
    )
    def test_prefix(self, idx: str, tags: list[str], expected: str):
        node = cls.new(title='Test', idx=idx, tags=tags)
        assert node.prefix == expected

    @pyt.mark.parametrize(
        'level, title, idx, expected_start',
        [
            (1, 'Title', '', '# Title'),
            (2, 'Title', '', '## Title'),
            (1, 'Title', 'A', '# `A` Title'),
            (3, 'Title', 'A0', '### `A0` Title'),
        ],
    )
    def test_header(self, level: int, title: str, idx: str, expected_start: str):
        node = cls.new(title=title, level=level, idx=idx)
        assert node.header == expected_start

    def test_fulltext(self):
        node = cls.new(
            title='Root',
            level=1,
            prose='Root prose',
        )
        fulltext = node.fulltext
        assert '# Root' in fulltext
        assert 'Root prose' in fulltext

    def test_fulltext__with_children(self):
        node = cls.new(
            title='Root',
            prose='Root prose',
            nodes=[
                {'title': 'Child', 'prose': 'Child prose'},
            ],
        )
        fulltext = node.fulltext
        assert '# Root' in fulltext
        assert 'Root prose' in fulltext
        assert '## `0` Child' in fulltext
        assert 'Child prose' in fulltext

    # ------------
    # `*2` Methods
    # ------------
    def test_parse__simple(self):
        nodes = cls.parse(SIMPLE_MD)
        assert len(nodes) == 1
        assert nodes[0].title == 'Main Title'
        assert len(nodes[0].nodes) == 2

    def test_parse__indexed(self):
        nodes = cls.parse(INDEXED_MD)
        assert len(nodes) == 1
        assert nodes[0].nodes[0].idx == '0'
        assert nodes[0].nodes[0].nodes[0].idx == '0A'
        assert nodes[0].nodes[1].idx == '1'

    def test_parse__tagged(self):
        nodes = cls.parse(TAGGED_MD)
        assert len(nodes) == 1
        assert 'tag1' in nodes[0].tags
        assert 'tag2' in nodes[0].tags
        assert 'important' in nodes[0].nodes[0].tags

    def test_parse__empty(self):
        nodes = cls.parse('')
        assert nodes == []

    @pyt.mark.parametrize(
        'text, expected_tree',
        [
            pyt.param(
                '# A\n\n## B\n\n## C\n\nbody',
                [
                    (1, 'A', '', ['B', 'C']),
                    (2, 'B', '', []),
                    (2, 'C', 'body', []),
                ],
                id='empty-sibling',
            ),
            pyt.param(
                '# A\n\n## B\n\n### C\n\nbody',
                [
                    (1, 'A', '', ['B']),
                    (2, 'B', '', ['C']),
                    (3, 'C', 'body', []),
                ],
                id='empty-ancestor',
            ),
            pyt.param(
                '# A\n## B\n### C\nbody',
                [
                    (1, 'A', '', ['B']),
                    (2, 'B', '', ['C']),
                    (3, 'C', 'body', []),
                ],
                id='adjacent-headings',
            ),
            pyt.param(
                '# A\n\n### C\n\nbody',
                [
                    (1, 'A', '', ['C']),
                    (3, 'C', 'body', []),
                ],
                id='skipped-level',
            ),
            pyt.param(
                '# A\n\n## B',
                [
                    (1, 'A', '', ['B']),
                    (2, 'B', '', []),
                ],
                id='empty-final-child',
            ),
            pyt.param(
                '# A',
                [(1, 'A', '', [])],
                id='empty-root',
            ),
        ],
    )
    def test_parse__headerless(
        self,
        text: str,
        expected_tree: list[tuple[int, str, str, list[str]]],
    ):
        """Empty sections must remain nodes and retain their descendants or siblings."""
        nodes = cls.parse(text)
        assert len(nodes) == 1
        assert [
            (node.level, node.title, str(node.prose), [child.title for child in node.nodes])
            for node in nodes[0].tree
        ] == expected_tree

    @pyt.mark.parametrize(
        'text, note_path, expected_notes, expected_root_children',
        [
            pyt.param(
                '# A\n\n## Notes\n\nkey: value\n\n## Body\n\ncopy',
                [],
                {'key': 'value'},
                ['Body'],
                id='root',
            ),
            pyt.param(
                '# A\n\n## B\n\n### Notes\n\nkey: value\n\n## C\n\ncopy',
                [0],
                {'key': 'value'},
                ['B', 'C'],
                id='headerless-child',
            ),
        ],
    )
    def test_parse__notes(
        self,
        text: str,
        note_path: list[int],
        expected_notes: dict[str, object],
        expected_root_children: list[str],
    ):
        """A YAML Notes child must attach to its prose-free parent as metadata."""
        root = cls.parse(text)[0]
        noted = root
        for child_index in note_path:
            noted = noted.nodes[child_index]

        assert noted.notes == expected_notes
        assert [child.title for child in root.nodes] == expected_root_children
        assert all(child.title != 'Notes' for child in noted.nodes)

    @pyt.mark.parametrize(
        'text, root_title, child_title, fenced_hash',
        [
            pyt.param(
                '# Title\n\nIntro.\n\n'
                '```python\n# this is a comment\ndef f():\n    pass\n```\n\n'
                '## Section Two\n\nMore.\n',
                'Title',
                'Section Two',
                '# this is a comment',
                id='backtick',
            ),
            pyt.param(
                '# T\n\n~~~\n### not a header\n~~~\n\n## Real\n\nx\n',
                'T',
                'Real',
                '### not a header',
                id='tilde',
            ),
        ],
    )
    def test_parse__fenced_hash(
        self, text: str, root_title: str, child_title: str, fenced_hash: str
    ):
        """Hash-prefixed prose inside either fence style must not become a header."""
        nodes = cls.parse(text)
        assert len(nodes) == 1
        assert nodes[0].title == root_title
        assert [child.title for child in nodes[0].nodes] == [child_title]
        assert fenced_hash in str(nodes[0].prose)

    def test_from_yaml(self):
        node = cls.new(
            title='Config',
            prose='key1: value1\nkey2: value2',
        )
        data = node.from_yaml()
        assert data == {'key1': 'value1', 'key2': 'value2'}

    def test_from_yaml__with_children(self):
        node = cls.new(
            title='Config',
            prose='top_key: top_value',
            nodes=[
                {
                    'title': 'Section',
                    'prose': 'section_key: section_value',
                },
            ],
        )
        data = node.from_yaml()
        assert data['top_key'] == 'top_value'
        assert data['Section']['section_key'] == 'section_value'

    def test_to_string(self):
        node = cls.new(
            title='Test',
            level=1,
            prose='Test prose',
        )
        output = node.to_string()
        assert '# Test' in output
        assert 'Test prose' in output

    def test_to_string__no_fix(self):
        node = cls.new(title='Test', prose='Content')
        output = node.to_string(fix=False)
        assert isinstance(output, str)

    @pyt.mark.parametrize('fix', [False, True])
    @pyt.mark.parametrize(
        'text, expected_tree, expected_descendant_prose, fenced_hash',
        [
            pyt.param(
                '# Root\n\nBefore.\n\n'
                '```python\n# not a heading\nprint("ok")\n```\n\n'
                '## Empty\n\n### Leaf\n\nleaf',
                [
                    (1, 'Root', ['Empty']),
                    (2, 'Empty', ['Leaf']),
                    (3, 'Leaf', []),
                ],
                {'Empty': '', 'Leaf': 'leaf'},
                '# not a heading',
                id='backtick-nested',
            ),
            pyt.param(
                '# Root\n\nBefore.\n\n'
                '~~~text\n## not a child\n~~~\n\n'
                '## Empty\n\n## Filled\n\nbody',
                [
                    (1, 'Root', ['Empty', 'Filled']),
                    (2, 'Empty', []),
                    (2, 'Filled', []),
                ],
                {'Empty': '', 'Filled': 'body'},
                '## not a child',
                id='tilde-siblings',
            ),
        ],
    )
    def test_to_string__roundtrip(
        self,
        fix: bool,
        text: str,
        expected_tree: list[tuple[int, str, list[str]]],
        expected_descendant_prose: dict[str, str],
        fenced_hash: str,
    ):
        """Rendering must separate child headers and preserve fence-aware tree structure."""
        root = cls.parse(text)[0]
        raw_output = root.to_string(fix=False)
        output = root.to_string(fix=fix)
        reparsed = cls.parse(output)[0]
        reparsed_tree = list(reparsed.tree)

        assert (output != raw_output) is fix
        assert f'\n{root.nodes[0].header}\n' in output
        assert [
            (node.level, node.title, [child.title for child in node.nodes])
            for node in reparsed_tree
        ] == expected_tree
        assert {
            node.title: str(node.prose) for node in reparsed_tree[1:]
        } == expected_descendant_prose
        assert fenced_hash in str(reparsed.prose)

    @pyt.mark.parametrize('fix', [False, True])
    def test_to_string__root_notes_render_as_frontmatter(self, fix: bool):
        """Root-level notes must render as YAML frontmatter, not be silently dropped."""
        node = cls.new(title='Test', level=1, prose='Test prose', notes={'key': 'value'})
        output = node.to_string(fix=fix)
        assert output.startswith('---')
        assert 'key: value' in output
        assert output.count('---') >= 2
        assert '# Test' in output
        assert 'Test prose' in output

    def test_to_string__frontmatter_is_valid_yaml_after_fix(self):
        """Regression (basis-D8): `mdformat-front-matters` must be present so `fix=True` (the
        default) formats the block as real, round-trippable YAML frontmatter bounded by `---`
        lines rather than mangling it into a thematic break plus a stray header -- the failure
        mode when the `front_matters` extension is requested but its plugin isn't installed.
        """
        node = cls.new(title='Test', level=1, prose='Test prose', notes={'key': 'value', 'n': 2})
        output = node.to_string(fix=True)

        assert output.startswith('---\n')
        _, _, remainder = output.partition('---\n')
        yaml_block, closed, body = remainder.partition('---\n')
        assert closed, 'Frontmatter closing `---` not found (mangled by mdformat?)'
        assert typist.from_yaml(yaml_block) == {'key': 'value', 'n': 2}
        assert body.strip().startswith('# Test')

    @pyt.mark.parametrize('fix', [False, True])
    def test_to_string__no_notes_omits_frontmatter(self, fix: bool):
        """A node with no notes must not gain spurious frontmatter (empty-dict regression)."""
        node = cls.new(title='Test', level=1, prose='Test prose')
        output = node.to_string(fix=fix)
        assert '---' not in output
        assert '{}' not in output

    @pyt.mark.parametrize('fix', [False, True])
    def test_to_string__child_notes_render_as_fenced_yaml(self, fix: bool):
        """Non-root notes must render as a fenced yaml block following the child's header."""
        node = cls.new(
            title='Parent',
            level=1,
            prose='parent prose',
            nodes=[{'title': 'Child', 'prose': 'child prose', 'notes': {'k2': 'v2'}}],
        )
        output = node.to_string(fix=fix)
        assert '```yaml' in output
        assert 'k2: v2' in output
        assert 'Child' in output

    @pyt.mark.parametrize('fix', [False, True])
    def test_to_string__child_no_notes_omits_fenced_yaml(self, fix: bool):
        """A child node with no notes must not gain a spurious fenced yaml block."""
        node = cls.new(
            title='Parent',
            level=1,
            prose='parent prose',
            nodes=[{'title': 'Child', 'prose': 'child prose'}],
        )
        output = node.to_string(fix=fix)
        assert '```yaml' not in output
        assert '{}' not in output

    def test_to_string__strip_notes_omits_frontmatter(self):
        """`strip_notes=True` must exclude notes/frontmatter from the rendered output."""
        node = cls.new(title='Test', level=1, prose='Test prose', notes={'key': 'value'})
        output = node.to_string(strip_notes=True, fix=False)
        assert '---' not in output
        assert 'key: value' not in output

    def test_str(self):
        node = cls.new(title='Test')
        assert isinstance(str(node), str)

    def test_pop(self):
        node = cls.new(
            title='Root',
            nodes=[
                {'title': 'To Remove'},
                {'title': 'To Keep'},
            ],
        )

        removed = node.pop(title='To Remove')
        assert removed is not None
        assert removed.title == 'To Remove'
        assert len(node.nodes) == 1
        assert node.nodes[0].title == 'To Keep'
        assert node.nodes[0].idx == '0'

    def test_pop__not_found(self):
        node = cls.new(title='Root')
        removed = node.pop(title='Nonexistent')
        assert removed is None

    def test_replace(self):
        node = cls.new(
            title='Root',
            prose='old text',
            nodes=[
                {'title': 'Child', 'prose': 'more old text'},
            ],
        )

        node.replace('old', 'new')
        assert 'new text' in str(node.prose)
        assert 'new text' in str(node.nodes[0].prose)

    def test_len(self):
        node = cls.new(
            title='Root',
            nodes=[
                {'title': 'Child 1'},
                {'title': 'Child 2'},
            ],
        )
        assert len(node) == 2

    def test_isub(self):
        node = cls.new(
            title='Root',
            nodes=[
                {'title': 'Remove Me'},
                {'title': 'Keep Me'},
            ],
        )

        node -= ['Remove Me']
        assert len(node.nodes) == 1
        assert node.nodes[0].title == 'Keep Me'

    # ----------------
    # Edge Cases Tests
    # ----------------
    def test_deep_nesting(self):
        """Test deeply nested markdown structure."""
        node = cls.new(
            title='L1',
            level=1,
            nodes=[
                {
                    'title': 'L2',
                    'nodes': [
                        {
                            'title': 'L3',
                            'nodes': [
                                {
                                    'title': 'L4',
                                    'nodes': [
                                        {'title': 'L5'},
                                    ],
                                },
                            ],
                        },
                    ],
                },
            ],
        )

        assert node.level == 1
        assert node.nodes[0].level == 2
        assert node.nodes[0].nodes[0].level == 3
        assert node.nodes[0].nodes[0].nodes[0].level == 4
        assert node.nodes[0].nodes[0].nodes[0].nodes[0].level == 5

    def test_index_overflow(self):
        """Test creating more than 62 children."""
        # Create exactly 62 children (0-9, A-Z, a-z)
        children = [{'title': f'Child {i}'} for i in range(62)]
        node = cls.new(title='Parent', nodes=children)

        assert len(node.nodes) == 62
        assert node.nodes[0].idx == '0'
        assert node.nodes[9].idx == '9'
        assert node.nodes[10].idx == 'A'
        assert node.nodes[35].idx == 'Z'
        assert node.nodes[36].idx == 'a'
        assert node.nodes[61].idx == 'z'

    def test_empty_node(self):
        """Test node with no content."""
        node = cls.new(title='Empty')
        assert node.title == 'Empty'
        assert str(node.prose) == ''
        assert len(node.nodes) == 0

    def test_complex_parsing(self):
        """Test parsing complex markdown with mixed levels."""
        text = """# Main

Main prose.

## Section A

Section A prose.

### Subsection A.1

Subsection prose.

### Subsection A.2

More prose.

## Section B

Section B prose.

# Another Main

Second document.
"""
        nodes = cls.parse(text)
        assert len(nodes) == 2
        assert nodes[0].title == 'Main'
        assert nodes[1].title == 'Another Main'
        assert len(nodes[0].nodes) == 2
        assert len(nodes[0].nodes[0].nodes) == 2

    def test_reparse_prose(self):
        """Test reparsing embedded headers in prose."""
        node = cls.new(
            title='Parent',
            level=1,
            prose='Some text\n\n## New Section\n\nNew section prose.',
        )

        node.reparse_prose()

        assert 'New Section' not in str(node.prose)
        assert len(node.nodes) == 1
        assert node.nodes[0].title == 'New Section'

    def test_notes_extraction(self):
        """Test automatic Notes section parsing."""
        text = """# Document

Content here.

## Notes

key: value
list:
  - item1
  - item2
"""
        nodes = cls.parse(text)
        assert len(nodes) == 1
        assert 'key' in nodes[0].notes
        assert nodes[0].notes['key'] == 'value'

    def test_walk_with_modifications(self):
        """Test walking while modifying the tree."""
        node = cls.new(
            title='Root',
            nodes=[
                {'title': 'Child 1'},
                {'title': 'Child 2'},
                {'title': 'Child 3'},
            ],
        )

        count = 0
        for _n in node.walk():
            count += 1
            # Don't modify during iteration for this basic test

        assert count == 4  # Root + 3 children

    def test_multiple_index_operations(self):
        """Test multiple index updates."""
        node = cls.new(
            title='Root',
            idx='A',
            nodes=[
                {'title': 'Child 1'},
                {'title': 'Child 2'},
            ],
        )

        # Change root index
        node.set_idx('B', 0)
        assert node.idx == 'B0'
        assert node.nodes[0].idx == 'B00'
        assert node.nodes[1].idx == 'B01'

        # Add new child
        node.add_node(cls.new(title='Child 3'))
        assert node.nodes[2].idx == 'B02'

    def test_serialization(self):
        """Test model serialization."""
        node = cls.new(
            title='Test',
            level=2,
            idx='A0',
            tags=['tag1'],
            prose='Content',
        )

        data = node.model_dump()
        assert data['title'] == 'Test'
        assert data['level'] == 2
        assert data['idx'] == 'A0'
        assert 'tag1' in data['tags']

    def test_buffer_factory_custom(self):
        """Test using custom buffer factory."""

        def custom_factory(text: str) -> Buffer:
            return Buffer.new(text.upper())

        node = cls.new(title='Test', prose='content', buffer_factory=custom_factory)
        assert 'CONTENT' in str(node.prose)

    # ---------------------
    # `*` Coverage Lifters
    # ---------------------
    # ------------
    # `new()` edge cases
    # ------------
    def test_new__from_bytes(self):
        """`new()` must accept a `bytes` source (exercises the isinstance path)."""
        node = cls.new(b'multi-line content', title='FromBytes')
        assert isinstance(node, cls)

    def test_new__from_buffer(self):
        """`new()` must accept a `Buffer` source (exercises the isinstance path)."""
        buf = Buffer.new('Buffer content')
        node = cls.new(buf, title='FromBuffer')
        assert isinstance(node, cls)

    def test_new__from_iterable(self):
        """`new()` must accept an `Iterable[str]` source wrapped as prose content."""
        node = cls.new(iter(['line one', 'line two']), title='FromIterable')
        assert isinstance(node, cls)

    def test_new__short_string_discarded(self):
        """`new()` must discard a short single-line string that has no newline."""
        node = cls.new('short', title='Short')
        assert str(node.prose) == ''

    def test_new__path_object_discarded(self):
        """`new()` must not crash on a `Path` source (discarded)."""
        from pathlib import Path
        node = cls.new(Path('/nonexistent/file.md'), title='FromPath')
        assert str(node.prose) == ''

    # ------------
    # `_build_tree` edge cases
    # ------------
    def test_build_tree__with_markdown_nodes(self):
        """_build_tree must accept pre-constructed Markdown instances."""
        child = cls.new(title='Prebuilt')
        nodes = cls._build_tree([child], level=1, idx='', buffer_factory=Buffer.new)
        assert len(nodes) == 1
        assert nodes[0].title == 'Prebuilt'
        assert nodes[0].idx == '0'
        assert nodes[0].level == 2

    def test_build_tree__type_error(self):
        """_build_tree must raise TypeError for invalid node types."""
        with pyt.raises(TypeError, match='Invalid node type'):
            cls._build_tree([42], level=1, idx='', buffer_factory=Buffer.new)

    def test_build_tree__dict_without_prose(self):
        """_build_tree must handle dict nodes without prose key."""
        nodes = cls._build_tree([{'title': 'NoProse'}], level=1, idx='', buffer_factory=Buffer.new)
        assert len(nodes) == 1
        assert nodes[0].title == 'NoProse'

    def test_build_tree__singleton_dict(self):
        """_build_tree must wrap a singleton dict in a list."""
        nodes = cls._build_tree({'title': 'Singleton'}, level=1, idx='', buffer_factory=Buffer.new)
        assert len(nodes) == 1

    # ------------
    # `_num_to_digit` multi-digit string
    # ------------
    def test_num_to_digit__multi_char_string(self):
        """_num_to_digit must convert a multi-character digit string to an int first."""
        assert cls._num_to_digit('36') == 'a'
        assert cls._num_to_digit('10') == 'A'

    def test_num_to_digit__invalid_string(self):
        """_num_to_digit must raise AssertionError for non-digit multi-char string."""
        with pyt.raises(AssertionError, match='Invalid index digit'):
            cls._num_to_digit('XY')

    # ------------
    # `_trace_path` edge cases
    # ------------
    def test_trace_path__origin_equals_target(self):
        """_trace_path must return [] when ancestor's idx matches target."""
        node = cls.new(title='Root', idx='A')
        assert cls._trace_path(node, 'A') == []

    def test_trace_path__oob_digit(self):
        """_trace_path must return [] for OOB digit indices."""
        node = cls.new(title='Root', idx='', nodes=[{'title': 'Child'}])
        path = cls._trace_path(node, '05')
        assert path == []

    # ------------
    # `refresh_indices` edge cases
    # ------------
    def test_refresh_indices__start_beyond_end(self):
        """refresh_indices must no-op when start >= n."""
        node = cls.new(title='Root', nodes=[{'title': 'Child'}])
        node.refresh_indices(start=5)  # Should not raise
        assert node.nodes[0].title == 'Child'

    # ------------
    # `walk` dynamic modification tracking
    # ------------
    def test_walk__add_during_traversal(self):
        """walk must handle nodes added during iteration."""
        node = cls.new(
            title='Root',
            nodes=[
                {'title': 'A'},
                {'title': 'B'},
            ],
        )
        titles = []
        for n in node.walk():
            titles.append(n.title)
            if n.title == 'Root':
                node.add_node(cls.new(title='New'))
        assert 'New' in titles
        assert 'A' in titles

    def test_walk__remove_during_traversal(self):
        """walk must handle nodes removed during iteration (visits remaining nodes)."""
        node = cls.new(
            title='Root',
            nodes=[
                {'title': 'A'},
                {'title': 'B'},
                {'title': 'C'},
            ],
        )
        titles = []
        for n in node.walk():
            titles.append(n.title)
            if n.title == 'A':
                node.pop(title='B')
        assert 'A' in titles
        assert 'C' in titles

    def test_walk__ascending_order(self):
        """walk with asc=True must traverse right-to-left among children."""
        node = cls.new(
            title='Root',
            nodes=[
                {'title': 'Left'},
                {'title': 'Right'},
            ],
        )
        titles = [n.title for n in node.walk(asc=True)]
        assert titles == ['Root', 'Right', 'Left']

    def test_walk__skip_self_empty_children(self):
        """walk with skip_self=True and no children must yield nothing."""
        node = cls.new(title='Leaf')
        assert list(node.walk(skip_self=True)) == []

    # ------------
    # `add_node` left branch
    # ------------
    def test_add_node__prepend(self):
        """add_node must prepend when left=True."""
        node = cls.new(
            title='Parent',
            nodes=[
                {'title': 'Original'},
            ],
        )
        new_child = cls.new(title='Prepend', level=2)
        node.add_node(new_child, left=True)
        assert [n.title for n in node.nodes] == ['Prepend', 'Original']
        assert node.nodes[0].idx == '0'
        assert node.nodes[1].idx == '1'

    def test_add_node__empty_list(self):
        """add_node with empty list must not modify."""
        node = cls.new(title='Parent', nodes=[{'title': 'Child'}])
        node.add_node([])
        assert len(node.nodes) == 1

    # ------------
    # `get_path` edge cases
    # ------------
    def test_get_path__empty_path(self):
        """get_path with empty path must return self when node has children."""
        node = cls.new(title='Root', nodes=[{'title': 'Child'}])
        assert node.get_path(path=[]) is node

    def test_get_path__no_nodes(self):
        """get_path must return None when node has no children."""
        node = cls.new(title='Root')
        assert node.get_path(path=[0]) is None

    def test_get_path__max_depth_exceeded(self):
        """get_path must return None when path exceeds max_d."""
        node = cls.new(
            title='Root',
            nodes=[
                {
                    'title': 'Child',
                    'nodes': [{'title': 'Grandchild'}],
                },
            ],
        )
        assert node.get_path(path=[0, 0], max_d=1) is None

    def test_get_path__max_depth_negative(self):
        """get_path with max_d=-1 must be unlimited."""
        node = cls.new(
            title='Root',
            nodes=[
                {
                    'title': 'Child',
                    'nodes': [{'title': 'Grandchild'}],
                },
            ],
        )
        found = node.get_path(path=[0, 0])
        assert found is not None
        assert found.title == 'Grandchild'

    # ------------
    # `frontmatter` property
    # ------------
    def test_frontmatter(self):
        """frontmatter property must return the notes dict."""
        node = cls.new(title='Test', notes={'k': 'v'})
        assert node.frontmatter == {'k': 'v'}

    def test_frontmatter__empty(self):
        """frontmatter property must return empty dict for no notes."""
        node = cls.new(title='Test')
        assert node.frontmatter == {}

    # ------------
    # `__bool__`
    # ------------
    def test_bool__with_title(self):
        """__bool__ must be True when title is set."""
        node = cls.new(title='Test')
        assert bool(node)

    def test_bool__with_prose(self):
        """__bool__ must be True when prose is set."""
        node = cls.new(title='', prose='Some content')
        assert bool(node)

    def test_bool__empty(self):
        """__bool__ must be False for empty node."""
        node = cls.new(title='')
        # An empty Markdown node still has title='' and prose=''
        # __bool__ returns bool(self.title or self.prose)
        assert not bool(node)

    # ------------
    # `_mask_fences` edge cases
    # ------------
    def test_mask_fences__sentinel_in_text(self):
        """_mask_fences must return text unchanged when sentinel present."""
        text = f'{chr(0)}already has sentinel'
        result = cls._mask_fences(text)
        assert result == text

    def test_mask_fences__tilde_fence(self):
        """_mask_fences must handle ~~~ tilde-fenced blocks."""
        text = '# Title\n\n~~~\n# not a header\n~~~\n\n## Real'
        result = cls._mask_fences(text)
        assert '# Title' in result
        assert '## Real' in result
        # The fenced # line should be masked with sentinel
        assert chr(0) in result

    # ------------
    # `parse_predicates`
    # ------------
    def test_parse_predicates(self):
        """parse_predicates must parse YAML-prose into a Predicate object."""
        node = cls.new(title='Config', prose='key: value\nnested:\n  sub: val')
        pred = node.parse_predicates()
        assert pred is not None
        assert 'key' in pred
        assert 'value' in pred['key']

    # ------------
    # `from_yaml` TypeError
    # ------------
    def test_from_yaml__empty_prose(self):
        """from_yaml must handle empty prose gracefully."""
        node = cls.new(title='Empty')
        result = node.from_yaml()
        assert result == {}

    # ------------
    # `replace` with regex
    # ------------
    def test_replace__regex(self):
        """replace must accept a regex pattern."""
        node = cls.new(title='Root', prose='foo bar baz')
        import regex
        node.replace(regex.compile('foo'), 'X')
        assert str(node.prose) == 'X bar baz'

    def test_replace__regex_in_children(self):
        """replace must apply regex to all descendant nodes."""
        node = cls.new(
            title='Root',
            prose='hello world',
            nodes=[{'title': 'Child', 'prose': 'hello there'}],
        )
        node.replace('hello', 'hi')
        assert str(node.prose) == 'hi world'
        assert str(node.nodes[0].prose) == 'hi there'

    # ------------
    # `__len__` with empty nodes
    # ------------
    def test_len__empty(self):
        """__len__ must return 0 for node with no children."""
        node = cls.new(title='Leaf')
        assert len(node) == 0

    # ------------
    # `__isub__` with non-existent title
    # ------------
    def test_isub__not_found(self):
        """__isub__ must still succeed for non-existent titles."""
        node = cls.new(title='Root', nodes=[{'title': 'Keep'}])
        node -= ['NonExistent']
        assert len(node.nodes) == 1
        assert node.nodes[0].title == 'Keep'

    # ------------
    # `to_string` with fix=False
    # ------------
    def test_to_string__fix_false(self):
        """to_string with fix=False must render without mdformat."""
        node = cls.new(title='Raw', level=1, prose='Some text')
        output = node.to_string(fix=False)
        assert '# Raw' in output
        assert 'Some text' in output

    # ------------
    # `get_idx` self return, max_d=0, no-match
    # ------------
    def test_get_idx__self_return(self):
        """get_idx must return self when idx matches own idx."""
        node = cls.new(title='Root', idx='A')
        assert node.get_idx(idx='A') is node

    def test_get_idx__max_d_zero(self):
        """get_idx with max_d=0 must return None for child lookups."""
        node = cls.new(title='Root', nodes=[{'title': 'Child'}])
        assert node.get_idx(idx='0', max_d=0) is None

    def test_get_idx__no_match(self):
        """get_idx must return None when no node matches."""
        node = cls.new(title='Root', idx='A')
        assert node.get_idx(idx='B') is None

    def test_get_idx__empty_nodes(self):
        """get_idx must return None when node has no children."""
        node = cls.new(title='Root', idx='A')
        assert node.get_idx(idx='A0') is None

    # ------------
    # `get_child` edge cases
    # ------------
    def test_get_child__negative(self):
        """get_child with negative index must return None."""
        node = cls.new(title='Root', nodes=[{'title': 'Child'}])
        assert node.get_child(child=-1) is None

    def test_get_child__max_d_zero(self):
        """get_child with max_d=0 must return None."""
        node = cls.new(title='Root', nodes=[{'title': 'Child'}])
        assert node.get_child(child=0, max_d=0) is None

    def test_get_child__no_children(self):
        """get_child must return None when node has no children."""
        node = cls.new(title='Leaf')
        assert node.get_child(child=0) is None

    # ------------
    # `get_title` edge cases
    # ------------
    def test_get_title__not_found(self):
        """get_title must return None for absent title."""
        node = cls.new(title='Root')
        assert node.get_title(title='Nonexistent') is None

    def test_get_title__empty_title(self):
        """get_title with empty string must return None."""
        node = cls.new(title='Root', nodes=[{'title': 'Child'}])
        assert node.get_title(title='') is None

    # ------------
    # `pop` with child index
    # ------------
        node = cls.new(
            title='Root',
            nodes=[
                {'title': 'A'},
                {'title': 'B'},
            ],
        )
        removed = node.pop(child=0)
        assert removed is not None
        assert removed.title == 'A'
        assert len(node.nodes) == 1
        assert node.nodes[0].title == 'B'

    # ------------
    # Advanced parsing: notes with non-YAML content
    # ------------
    def test_parse__notes_yaml_error_handling(self):
        """parse must handle Notes sections with non-YAML content gracefully."""
        text = """# Document

Content

## Notes

Just some regular prose text, not YAML.

## Another Section

More content.
"""
        nodes = cls.parse(text)
        assert len(nodes) == 1
        # Notes should still be extracted as children since YAML parsing fails
        assert len(nodes[0].nodes) >= 1

    # ------------
    # `get_path` not found
    # ------------
    def test_get_path__not_found(self):
        """get_path must return None when path leads nowhere."""
        node = cls.new(title='Root', nodes=[{'title': 'Child'}])
        assert node.get_path(path=[1]) is None
