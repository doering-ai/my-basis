# Files

## Markdown

The `Markdown` class implements a hierarchical document model for Markdown files.
Documents are parsed into tree structures where each node represents a header section with its associated prose, tags, metadata, and child sections.
The parser recognizes headers from level 1-6, extracts tags and indices from backtick-wrapped prefixes (like ``  `A tag` ## Title ``), and builds a nested hierarchy based on header levels.

Nodes are indexed using a base-62 encoding scheme (0-9, A-Z, a-z) to uniquely identify their position in the tree.
The index string grows with depth, so a node at `1A3` is the 3rd child of the 10th child of the 1st child of the root.
This indexing system supports path tracing and node lookup.

Tree traversal is supported through multiple methods including depth-first walking with configurable direction and depth limits.
The walker handles dynamic tree modifications during iteration, making it safe to add or remove nodes while traversing.
Nodes can be retrieved by index, child position, title, or path, and the class provides methods for adding, removing, and replacing nodes while maintaining correct indices.

The class integrates YAML parsing for structured metadata, automatically extracting data from "Notes" sections and storing them in the node's `notes` dictionary.
Prose content is stored in `Buffer` objects from `my.types` for text manipulation.
The entire tree can be rendered back to markdown text with optional formatting via `mdformat`, and templates from `my.templates` control the output structure.

## DocName

The `DocName` class is the canonical `creators__year__title` name a document corpus indexes itself by: lowercase, `-` joining the words inside one semantic sub-unit, `_` delineating the sub-units of one typed slot, and `__` separating the three slots.
`arendt-h__1958__human-condition` names one work; `gendler-t_hawthorne-j__2002__conceivability-and-possibility` names two creators; `aristotle__-0350__categories` carries a signed BCE year.

The grammar and its normalizations are transcribed from the two applications that already implement it -- `wikiparse.citations.CitationFactory` and the pure half of the literature corpus's slug normalizer -- and live here because an application may not import another for a shared primitive.
`ut.clean_string`, in the neighbouring `utils` subpackage, is the root all of it descends from.

`DocName.mint()` walks an evidence ladder rather than inventing a name: named creators first, then the work's own identifier (`uid-arxiv`), then whoever published it (`site-example-org`).
It returns `None` when the metadata names nothing at all, and a year nobody has triaged is the literal `0000` -- a different claim from `undated`, which asserts a date was sought and does not exist.
The model is frozen and validates its own grammar, so a `DocName` that exists is a name that can be written to disk.
