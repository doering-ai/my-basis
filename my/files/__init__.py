"""File Formats.

The `files` subpackage provides structured representations and utilities for working with file
formats. It holds a somewhat-specialized (opinionated?) markdown format, and the canonical
`creators__year__title` name a document corpus indexes itself by.
"""

from .DocName import DocName
from .Markdown import Markdown

__all__ = ['DocName', 'Markdown']
