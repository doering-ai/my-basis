############
### HEAD ###
############
### STANDARD
from typing import ClassVar, Any, Self
import textwrap

### EXTERNAL
import pydantic as pyd

### INTERNAL
from ..base import utils as ut
from ..text import Buffer, RegexStore
from .Lang import Lang
from .Block import Block

############
### DATA ###
############
NO_ESC = RegexStore.NO_ESC

BufferField = pyd.Field(default_factory=Buffer.new)


############
### BODY ###
############
class Element(Block):
    SECTIONS: ClassVar[dict[str, str]] = {
        '': 'members',
        '0': 'initial',
        '-': 'private',
        '+': 'primary',
        'x': 'public',
    }

    # Universal sections
    members: Buffer = BufferField

    # Element-specific sections
    initial: Buffer = BufferField
    private: Buffer = BufferField
    primary: Buffer = BufferField
    public: Buffer = BufferField

    # -------------------
    # `0` Initial Methods
    # -------------------
    @classmethod
    def new(
        cls,
        *,
        sig: str = '',
        name: str = '',
        code: str = '',
        lang: Lang = Lang.PY,
        **kwargs: Any,
    ) -> Self:
        assert sig and code, 'Element text cannot be empty.'
        code = textwrap.dedent(code.strip('\n'))

        # I. Split up the class according to sections (if present)
        delims, sections = cls.RGXS.fullsplit('class_delim', code)

        # I.i. The first section comes before any headers
        kwargs['members'] = Buffer.new(sections[0].strip('\n'))

        # I.ii. Identify other sections by the 1-char symbol ([0-+x]) in bactics
        for delim, section in zip(delims[1:], sections[1:]):
            parts = delim.split('`', 2)
            assert len(parts) == 3 and len(parts[1]) <= 1, f'Invalid delim in {sig}'
            kwargs[cls.SECTIONS[parts[1]]] = Buffer.new(section.strip('\n'))
        return cls(sig=sig, name=name, lang=lang, **kwargs)

    @pyd.model_validator(mode='after')
    def _build_source_element(self) -> Self:
        if self.members and not self.doc:
            self.doc = self._extract_doc(self.members, self.lang)
        return self

    # -------------------
    # `-` Private Methods
    # -------------------
    @classmethod
    def _render_header(cls, symbol: str, section: str, lang: Lang) -> str:
        # Members section has no header
        if not symbol:
            return ''

        content = f'`{symbol}` {section.title()} Methods'
        prefix = '# ' if lang == Lang.PY else '// '
        sep = prefix + ("-" * len(content))
        return '\n'.join([sep, prefix + content, sep])

    # -------------------
    # `+` Primary Methods
    # -------------------
    def render_section(self, section: str) -> str:
        if section in self.SECTIONS:
            symbol = section
            section = self.SECTIONS[symbol]
        else:
            section = section.lower()
            key = ut.find_key(self.SECTIONS, section)
            assert key is not None, f'Invalid section {section}'
            symbol = key

        return '\n'.join([
            self._render_header(symbol, section, self.lang),
            str(getattr(self, section)).strip('\n'),
        ])

    # ------------------
    # `x` Public Methods
    # ------------------
    @property
    def sections(self) -> list[tuple[str, Buffer]]:
        return [(key, getattr(self, key)) for key in self.SECTIONS.values()]

    def render(self) -> tuple[str, str]:
        sig = '\n'.join([*self.annotations, self.sig])
        sections = [
            self._render_doc(str(self.doc), self.lang),
            *map(self.render_section, self.SECTIONS.keys()),
        ]
        code = '\n\n'.join(filter(bool, sections))
        return sig, code

    def parse_methods(self) -> dict[str, list[Block]]:
        """
        Returns a list of Block objects representing the methods in the specified section.
        If no section is specified, returns methods from all sections.
        """
        ret = {}
        for key, section in self.sections:
            ret[key] = Block._extract_methods(section, self.lang)
        return ret

    def parse_doc(self) -> dict[str, str]:
        if match := self.RGXS.match('arch_docstr', self.doc):
            return match.flat | dict(body=self.doc[match.end:].lstrip('\n'))
        return dict(body=str(self.doc))
