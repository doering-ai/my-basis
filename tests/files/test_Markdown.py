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

    def test_add_node__prepend(self):
        node = cls.new(
            title='Parent',
            nodes=[
                {'title': 'Existing'},
            ],
        )
        child = cls.new(title='New')

        node.add_node(child, left=True)
        assert len(node.nodes) == 2
        assert node.nodes[0].title == 'New'
        assert node.nodes[1].title == 'Existing'
        assert node.nodes[0].idx == '0'
        assert node.nodes[1].idx == '1'

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

    def test_get_title__not_found(self):
        node = cls.new(title='Root')
        found = node.get_title(title='Nonexistent')
        assert found is None

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

    def test_parse__code_fence_hash_not_header(self):
        # Regression: a `#` comment inside a fenced code block must stay prose, not be mistaken
        # for a header (which fabricated a phantom node and misnested the sections after it).
        text = (
            '# Title\n\nIntro.\n\n'
            '```python\n# this is a comment\ndef f():\n    pass\n```\n\n'
            '## Section Two\n\nMore.\n'
        )
        nodes = cls.parse(text)
        assert len(nodes) == 1
        assert nodes[0].title == 'Title'
        # `## Section Two` is a real child; the fenced `# comment` is not a node at all.
        assert [child.title for child in nodes[0].nodes] == ['Section Two']
        # The fence (including its `#` comment) is preserved verbatim in the title node's prose.
        assert '# this is a comment' in str(nodes[0].prose)

    def test_parse__tilde_fence_hash_not_header(self):
        text = '# T\n\n~~~\n### not a header\n~~~\n\n## Real\n\nx\n'
        nodes = cls.parse(text)
        assert len(nodes) == 1
        assert [child.title for child in nodes[0].nodes] == ['Real']
        assert '### not a header' in str(nodes[0].prose)

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
    def test_to_string__root_notes_render_as_frontmatter(self, fix: bool):
        """Root-level notes must render as YAML frontmatter, not be silently dropped."""
        node = cls.new(title='Test', level=1, prose='Test prose', notes={'key': 'value'})
        output = node.to_string(fix=fix)
        assert output.startswith('---')
        assert 'key: value' in output
        assert output.count('---') >= 2
        assert '# Test' in output
        assert 'Test prose' in output

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
