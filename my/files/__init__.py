"""File Formats

The `files` subpackage provides structured representations and utilities for working with file formats. Currently it only contains one format, a somewhat-specialized (opinionated?) markdown format.
"""
from .Markdown import Markdown

__all__ = ['Markdown']
