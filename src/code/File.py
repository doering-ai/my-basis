############
### HEAD ###
############
### STANDARD
from typing import ClassVar
from pathlib import Path

### EXTERNAL
import pydantic as pyd

### INTERNAL
from ..base import utilities as ut
from ..text import Buffer
from .Lang import Lang
from .Imports import Imports
from .Block import Block
from .Element import Element

BufferField = pyd.Field(default_factory=Buffer.new)


############
### BODY ###
############
class File(Block):
    """
    Represents a parsed sourcecode file, either Python or Typescript.
    Done via string-parsing instead of direct reflection to
        A) Avoid import issues (especially for WIP code), and
        B) Support the parsing of non-python files by the python-based Nexus
    """
    SECTIONS: ClassVar[tuple[str, ...]] = ('code', 'head', 'data', 'body', 'main')

    # Uses [name, lang, code] from base class
    # Tracks the (eventual) location of the file
    path: Path

    # Each file has 1-4 sections -- almost always HEAD, rarely MAIN
    head: Buffer = BufferField
    data: Buffer = BufferField
    body: Buffer = BufferField
    main: Buffer = BufferField

    # -------------------
    # `0` Initial Methods
    # -------------------
    @classmethod
    def new(cls, path: Path | None = None, **kwargs) -> 'File':
        if path is None:
            raise ValueError('A path must be provided to create a File.')

        # I. Populate the instance with info from a real file if there is one
        if path.exists():
            ut.validate_file(path)
            text = path.read_text()
            if 'name' not in kwargs:
                kwargs['name'] = path.stem
            if 'lang' not in kwargs:
                kwargs['lang'] = Lang.read_path(path)
            kwargs |= cls._delineate_file(text, kwargs['lang'])

        return cls(path=path, **kwargs)

    @pyd.field_validator('name', mode='after')
    @classmethod
    def _validate_name(cls, name: str) -> str:
        if not name:
            return ''
        elif name[0] == '_':
            return name.rsplit('_', 1)[-1]
        elif name.startswith('test_'):
            return 'Test' + name.rsplit('_', 1)[-1]
        else:
            return name

    # -------------------
    # `-` Private Methods
    # -------------------
    @classmethod
    def _delineate_file(cls, text: str, lang: Lang) -> dict[str, Buffer]:
        """
        Splits the given text into its 1-4 component sections if top-level headers are present.
        """
        ret: dict[str, Buffer] = {}
        delims, sections = cls.RGXS.fullsplit('file_delim', text)
        if not delims:
            return ret
        elif code := sections[0]:
            # Parse the section before HEAD, which very rarely exists
            if file_doc := cls._extract_doc(Buffer.new(code), lang):
                ret['doc'] = file_doc
            ret['code'] = Buffer.new(code.strip())

        for delim, section in zip(delims[1:], sections[1:]):
            if len(delim_parts := delim.split(' ', 2)) == 3:
                part = delim_parts[1].lower()
                assert part in cls.SECTIONS, f'Invalid section name {part} found.'
            ret[part] = Buffer.new(section.strip('\n'))
        return ret

    def _render_header(self, section: str) -> str:
        """ Renders commented-out top level header for the given section section. """
        c = '#' if self.lang == Lang.PY else '/'
        sep = c * 12
        return '\n'.join([sep, f'{c*3} {section.upper()} {c*3}', sep])

    # -------------------
    # `+` Primary Methods
    # -------------------
    def render_section(self, section: str) -> str:
        """ Renders the given section w/ header if it exists, and nothing if it's empty. """
        section = section.lower()
        assert section in self.SECTIONS, f'Invalid section name {section}'
        if val := str(getattr(self, section)).strip():
            return f'{self._render_header(section)}\n{val}' if section != 'code' else val
        else:
            return ''

    # ------------------
    # `x` Public Methods
    # ------------------
    @property
    def sections(self) -> dict[str, Buffer]:
        """ Returns the four sections of the source buffer in order. """
        return {name: text for name in self.SECTIONS if str(text := getattr(self, name)).strip()}

    def parse_imports(self) -> Imports:
        return Imports.new(text=self.head or self.code, lang=self.lang)

    def parse_methods(self) -> dict[str, list[Block]]:
        if elem := self.parse_element():
            return elem.parse_methods()
        elif self.code:
            return super().parse_methods()
        return dict()

    def parse_element(self) -> Element | None:
        """
        Seeks out and parses the "main" class of this file, which shares the same name as the file
        and is defined in the BODY section.
        """
        buf = self.body or self.data or self.code
        for match in self.RGXS.finditer(f'{self.lang.prefix}_class', buf):
            if match.at('name') == self.name:
                s0, s1 = match.span
                b0, b1 = self._block_span(buf, s1, self.lang)
                assert b0 != b1, f'Failed to identify block span for {self.name} @ {s1}'

                return Element.new(
                    sig=buf[s0:s1],
                    code=buf[b0:b1],
                    name=self.name,
                    lang=self.lang,
                )

        return None

    def __str__(self) -> str:
        return '\n\n\n'.join(filter(bool, map(self.render_section, self.SECTIONS)))
