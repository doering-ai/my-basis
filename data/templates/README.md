# Templates

The `templates` subdirectory contains Jinja2 template files used throughout the package for code generation and document rendering. These templates provide consistent formatting and structure for various output types.

## Document Templates

The `document.md.jinja` template serves as the base for hierarchical document rendering. It defines a recursive structure with extensible blocks for headers, prose content, and child nodes. The template uses Jinja2's recursive loop feature to handle arbitrary nesting depth, rendering each node's header and content before recursing into its children.

`Markdown.md.jinja` extends the document template specifically for the `Markdown` class in `my.files`. It maps Markdown node properties (header, prose, nodes) to the document template's blocks and adds special handling for a "Notes" section. When a Markdown node has associated notes (typically parsed from YAML), they're rendered in a fenced YAML code block at the end of the node's content.

## Code Generation Templates

The `MyEnum.py.jinja` template generates Python enum class definitions following the package's standard structure. It creates a class inheriting from `MyEnum` (and optionally `Flag` for bit-flag enums), with proper imports based on the nesting depth in the package hierarchy. The template accepts variables for the class name, whether it's a flag enum, and the enum member content.

These templates are accessed via the `get_template()` function in `my.infra`, which handles template loading from this directory. Classes like `Markdown` reference templates by name (e.g., `TEMPLATE = 'Markdown.md.jinja'`) and render them with their data via `get_template(name).render(data)`.
