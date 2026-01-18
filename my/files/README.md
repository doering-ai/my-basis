# Files

## Markdown

The `Markdown` class implements a complete hierarchical document model for markdown files. Documents are parsed into tree structures where each node represents a header section with its associated prose, tags, metadata, and child sections. The parser recognizes headers from level 1-6, extracts tags and indices from backtick-wrapped prefixes (like ``  `A tag` ## Title ``), and builds a nested hierarchy based on header levels.

Nodes are indexed using a base-62 encoding scheme (0-9, A-Z, a-z) to uniquely identify their position in the tree. The index string grows with depth, so a node at `1A3` is the 3rd child of the 10th child of the 1st child of the root. This indexing system enables efficient path tracing and node lookup operations.

Tree traversal is supported through multiple methods including depth-first walking with configurable direction and depth limits. The walker handles dynamic tree modifications during iteration, making it safe to add or remove nodes while traversing. Nodes can be retrieved by index, child position, title, or path, and the class provides methods for adding, removing, and replacing nodes while maintaining correct indices.

The class integrates YAML parsing for structured metadata, automatically extracting data from "Notes" sections and storing them in the node's `notes` dictionary. Prose content is stored in `Buffer` objects (from `my.types`), enabling efficient text manipulation operations. The entire tree can be rendered back to markdown text with optional formatting via `mdformat`, and templates from `my.templates` control the output structure.
