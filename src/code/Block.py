############
### HEAD ###
############
### STANDARD
from typing import ClassVar, Any, Iterator, Self
import textwrap
import functools as ft

### EXTERNAL
import pydantic as pyd
import regex as re
import logfire as fire

### INTERNAL
from my import AutocastModel, aliases as al
from my._010_types._0_enumerations import SrcLang
from ..text.Span import Span
from ..text.Buffer import Buffer
from ..text.RegexStore import RegexStore

NO_ESC = RegexStore.NO_ESC
BufferField = pyd.Field(default_factory=Buffer.new)


############
### BODY ###
############
class SrcBlock(AutocastModel):
    RGXS: ClassVar[RegexStore] = RegexStore.new(
        options=dict(
            separator=r' *\n',
            autostrip_spaces=False,
            force_named_groups=True,
        ),
        # General
        _in=r'(?m)^( {4}| {8}| {12,})',
        _qm=r'[\'"]',

        # Delimiters
        bracket=('|:', NO_ESC, [r'(?P<start>\{)', r'(?P<end>\})'], r''),

        # File sections
        file_delim=[
            r'(?m)^[/#]{12}',
            r'[/#]{3} (?P<name>[[:upper:]]{4}) [/#]{3}',
            r'[/#]{12}\n',
        ],

        # Parsing docstrings
        idx=r'(?P<idx>[0123ab]{0,4})',
        arch_docstr=[
            r' *`(?P=idx)`: (?P<division>[[:upper:]]+ [[:upper:]]+)',
            r'( *\(\.{3} (?P<ancestors>([[:lower:]]+ [[:lower:]]+( -> )?)+)\))?',
        ],

        # Classes
        py_class=r'(?sm)^class (?P<name>\w+)(\((?P<parents>.+?)\))?:$',
        ts_class=(
            '|sm', r'^(export )?', [
                r'class (?P<name>\w+)( *extends *(?P<parents>.+?))?',
                r'const (?P<name>\w+) = \(.+?\) =>',
            ], r' *{$'
        ),

        # Class sections
        class_delim=[
            r'(//|#) -{8,}',
            r'(//|#) `[-0+x]` [^\n]+',
            r'(//|#) -{8,}\n',
        ],
        dataclass_members=(
            '|:m+', r'\n*^', [
                r'static ',
                r'[_[:upper:]]+: ',
                r'// ',
                r'# ',
                r'(?P<symbol>\w+\??): (?P<types>[^\n=\(\)]+)',
            ], r'[^\n]*$'
        ),

        # Methods
        py_method=(
            '[]:sm', [
                ('P<annotation>*', [r'^@[^\n]+$\n+']),
                (
                    '[]:', r'^', [
                        r'(async )?def (?P<name>\w+)(\[\w+\])?',
                        r'\((?P<args>.*?)\)',
                        r'( -> (?P<type>[^\n:]+?))?',
                    ], r':$'
                ),
            ]
        ),
        ts_method=(
            '|:sm', r'^(export )?', [
                r'const (?P<name>\w+) = (async )?\((?P<args>.*?)\)(: (?P<type>.+?))? =>',
                r'(async )?function (?P<name>\w+)\((?P<args>.*?)\)(: (?P<type>.+?))?'
            ], r' {$'
        ),

        # Method args
        # py_arg=('[ *]:', [r'(?P<name>\w+)', r'(: (?P<type>.+?))?', r'( = (?P<value>.+))?']),
        arg_parts=(
            '[ *]:', [
                ('|P<key>', [r'[*]{0,2}\w+', r'{[^\}]+}']),
                r'(: (?P<ann>.+?))?',
                r'( = (?P<val>.+))?',
            ]
        ),

        # Block Sections
        py_doc=(
            '|sm', rf'^ *{NO_ESC}', [
                rf'"""\n*(?P<text>.+?)\s*{NO_ESC}"""',
                rf"'''\n*(?P<text>.+?)\s*{NO_ESC}'''",
            ], r' *$'
        ),
        ts_doc=rf'(?sm)^ *{NO_ESC}\/\*\* *\n*(?P<text>.+?)\s*{NO_ESC}\*\/ *$',

        # Misc
        typesplit=r' *\| *',
        module=(
            '[]:m', [
                ('|<=', r'^', [r'from', r'import'], r' '),
                r'\w+(\.\w+)*',
                ('|=', [r' ', r'$']),
            ]
        ),
        internal_imports=(':sm', [
            r'^[#/]{3} INTERNAL',
            r'(?P<content>.+?)',
            r'^[#/]{12}$',
        ]),
        no_indent=r'\n\S',
    )
    TYPE_BASES: ClassVar[dict[str, re.Pattern]] = al.regex_dict(
        dict(
            str=r'Buffer|(?:re\.)?Pattern',
            list=r'Iter\w+|Sequence',
            dict=r'MatchData|Predicates|Mapping|Counter',
            tuple=r'Span',
        ),
        compile_function=lambda rgx: re.compile(rf'\b(?:{rgx})\b')
    )

    class Arg(pyd.BaseModel):

        key: str = ''
        ann: str = ''
        val: str = ''

        @classmethod
        def new(cls, text: str) -> Self:
            if match := SrcBlock.RGXS.fullmatch('arg_parts', text):
                data = {key: SrcBlock._clean_sig_part(val) for key, val in match.flat.items()}
                return cls(**data)
            return cls(key='')

        @pyd.model_validator(mode='after')
        def _validate_arg(self) -> Self:
            if self.key.startswith('**'):
                self.key = self.key[2:]
                self.ann = f'dict[{self.ann}]' if self.ann else 'dict'
            elif self.key.startswith('*'):
                self.key = self.key[1:]
                self.ann = f'list[{self.ann}]' if self.ann else 'list'
            return self

        @pyd.computed_field  # type: ignore
        @property
        def base(self) -> str:
            return self.ann_base(self.ann)

        def all_bases(self) -> set[str]:
            return set(SrcBlock.RGXS['typesplit'].split(self.base))

        @staticmethod
        def ann_base(ann: str) -> str:
            if not ann:
                return ''
            ret = Buffer.RGXS['arrays'].sub('', ann)
            for base, rgx in SrcBlock.TYPE_BASES.items():
                ret = rgx.sub(base, ret)
                if ret == base:
                    break
            return ret

        def __bool__(self) -> bool:
            return self.key != ''

        def __str__(self) -> str:
            ret = self.key
            if self.ann:
                ret += f': {self.ann}'
            if self.val:
                ret += f' = {self.val}'
            return ret

    # Basic data
    sig: str = ''
    doc: Buffer = BufferField
    code: Buffer = BufferField
    lang: SrcLang = SrcLang.PY
    indent: int = 0

    # Functional data (optional)
    annotations: list[str] = []
    name: str = ''
    args: list[Arg] = []
    type: str = ''

    # -------------------
    # `0` Initial Methods
    # -------------------
    @classmethod
    def new(cls, **kwargs: Any) -> Self:
        if isinstance(kwargs.get('args', None), str):
            kwargs['args'] = list(cls._extract_args(kwargs['args']))
        if isinstance(kwargs.get('annotations', None), str):
            kwargs['annotations'] = kwargs['annotations'].splitlines()
        return cls(**kwargs)

    @pyd.model_validator(mode='after')
    def _build_source_block(self) -> Self:
        # I. Strip string fields
        self.sig = self.sig.strip('\n')
        if not self.indent and (raw_indent := self.RGXS.match('_in', self.sig)):
            self.indent = max((len(raw_indent.text) // 4), 0)
            self.sig = self.sig.strip()

        self.name = self.name.strip()
        self.type = self._clean_sig_part(self.type)
        self.annotations = list(map(str.strip, self.annotations))

        # II. Unindent the code, if necessary
        self.code.dedent()
        if self.sig and not self.code and self.lang == SrcLang.PY:
            self.code = Buffer.new('pass')

        # III. Extract docstring from the code text
        if self.code and not self.doc:
            self.doc = self._extract_doc(self.code, self.lang)

        return self

    @pyd.model_serializer(mode='plain')
    def serialize(self) -> str:
        return str(self)

    # -------------------
    # `-` Private Methods
    # -------------------
    @classmethod
    def _clean_sig_part(cls, text: str) -> str:
        """
        Clean a signature component by stripping whitespace and removing quotes.
        """
        return cls.RGXS['_qm'].sub('', text.strip())

    @classmethod
    def _render_doc(cls, text: str, lang: SrcLang) -> str:
        """
        Renders a docstring for the given text and language.
        """
        if not text:
            return ''
        text = al.wrap_paragraphs(text.strip('\n'))
        if '\n' not in text and len(text) < 80:
            sep = ' '
        else:
            sep = '\n'
            if lang == SrcLang.TS:
                text = textwrap.indent(text, ' * ', lambda line: not line.startswith(' *'))

        start, end = ('"""', '"""') if lang == SrcLang.PY else ('/**', '*/')
        return sep.join([start, text, end])

    @classmethod
    def _py_block_span(cls, text: Buffer, pos: int) -> Span:
        """
        Delineates a python block based on indentation alone, returning the span from the given
        position to the last character after it that is in the same block.
        """
        assert 0 < pos < len(text), f'Index {pos} out of range.'
        pos -= 1
        s0, s1 = text.linespan(pos)
        b0 = s1 + 1
        sig = text[s0:s1]
        assert not sig.startswith(' '), f'Signature is indented: "{sig}"'

        if match := cls.RGXS.search('no_indent', text[s1:]):
            b1 = s1 + match.start
        else:
            b1 = len(text)

        return Span(b0, b1)

    @classmethod
    def _ts_block_span(cls, text: Buffer, pos: int) -> Span:
        """
        Delineates a TypeScript block from the given text starting at the specified index.
        Returns a Span object with the pos and end indices of the block.
        """
        assert 0 <= pos < len(text), f'Index {pos} out of range.'
        if (char := text[pos]) in '{}':
            rgx = cls.RGXS['bracket']
        else:
            raise ValueError(f'Unsupported block char {char} passed.')

        if tup := text.find_pair_match(rgx, pos):
            return tup[0]
        return Span(0, 0)

    @classmethod
    def _block_span(cls, text: Buffer, pos: int, lang: SrcLang) -> Span:
        """
        Returns a Span object representing the block of code starting at the specified position.
        The block is determined by the language of the source code.
        """
        if lang == SrcLang.PY:
            return cls._py_block_span(text, pos)
        elif lang == SrcLang.TS:
            return cls._ts_block_span(text, pos)
        else:
            raise ValueError(f'Unsupported language {lang} for block extraction.')
        return Span(0, 0)

    @classmethod
    def _imported_type_filter(cls, name: str) -> bool:
        """ Filters out implicit (i.e. non-imported) type names. """
        return bool(name) and name not in cls.TYPE_BASES and name not in ('None', 'set', 'bool')

    # -------------------
    # `+` Primary Methods
    # -------------------
    @classmethod
    def _extract_args(cls, args: str) -> Iterator[Arg]:
        """
        Extracts arguments from a method signature string.
        Returns a list of tuples containing the argument name, type, and default value.

        Args:
            args: A single string containing all the args found in a function's signature.

        Yields:
            SrcBlock.Arg objects representing individual arguments, positional or otherwise.
        """
        args = re.sub(r'[ \n]{2,}|\n', ' ', args.strip())
        yield from cls._extract_args__manual(args)

    @classmethod
    def _extract_args__manual(cls, args: str) -> Iterator[Arg]:
        # I. Prep the arg string by collapsing it into a one-line buffer
        buf = Buffer.new(args, fence_rgxs=['arrays'])

        # II. Split only by commas that appear outside type brackets
        prev = 0
        for split_match in buf.rgx_iterator(r' ?, ?'):
            x0, x1 = split_match.span()
            text = buf[prev:x0]
            prev = x1
            if arg := cls.Arg.new(text):
                yield arg

        # III. Yield the last argument
        if prev < len(buf) and (arg := cls.Arg.new(buf[prev:])):
            yield arg

    @classmethod
    def _extract_doc(cls, text: Buffer, lang: SrcLang) -> Buffer:
        """
        Extracts the docstring from the given text based on the language.

        Args:
            text: Text buffer that will be modified if a docstring is found.
            lang: The language of this block.
        """
        if (match := cls.RGXS.search(f'{lang.prefix}_doc', text)) and match.start <= 8:
            text.drop(match.span).strip('\n')
            return Buffer.new(al.unwrap_paragraphs(match.at('text').strip('\n')))
        else:
            return Buffer()

    @staticmethod
    def _extract_methods(block: Buffer, lang: SrcLang) -> list['SrcBlock']:
        """
        Returns a list of SrcBlock objects representing the methods in the specified section.
        If no section is specified, returns methods from all sections.
        """
        ret = []
        for match in SrcBlock.RGXS.finditer(f'{lang.prefix}_method', block):
            s0, s1 = match.span
            b0, b1 = SrcBlock._block_span(block, s1, lang)
            if b0 == b1:
                continue
            ret.append(
                SrcBlock.new(
                    sig=block[s0:s1],
                    code=block[b0:b1],
                    annotations=match.get('annotation', []),
                    name=match.at('name', ''),
                    args=match.at('args', ''),
                    type=match.at('type', ''),
                    lang=lang,
                )
            )
        return ret

    @pyd.computed_field  # type: ignore
    @property
    def type_base(self) -> str:
        """
        The 'base' type returned by this block, if any. Base types are the underlying,
        non-parameterized versions of the original types, e.g. "dict" instead of "dict[str, str]".
        """
        return self.Arg.ann_base(self.type)

    # ------------------
    # `x` Public Methods
    # ------------------
    def render(self) -> tuple[str, str]:
        """
        Renders the signature and code of this block into a tuple of strings.
        Written with the intention that subclasses will override it.

        Returns:
            - The "signature" of this block (if any), such as a class or function declaration line.
            - The "code" of this block, which is all its content other than the signature.
        """
        # I. Render signature
        sig = '\n'.join([*self.annotations, self.sig])

        # II. Render body
        code = str(self.code).strip('\n')
        if self.doc:
            code = f'{self._render_doc(str(self.doc), self.lang)}\n\n{code}'
        return sig, code

    def __str__(self) -> str:
        """ Returns a properly-indented string representation of this block. """
        # I. Rely on the subclass' render method for the majority of the work
        sig, code = self.render()

        # II. Ensure TS blocks are wrapped in braces
        if self.lang == SrcLang.TS:
            if not sig.endswith('{'):
                sig += '{'
            if not code.endswith('\n}'):
                code += '\n}'

        # III. Indent everything if necessary
        ret = f'{sig}\n{al.indent(code, 4)}'
        if self.indent:
            ret = al.indent(ret, self.indent * 4)
        return ret

    def parse_methods(self) -> dict[str, list['SrcBlock']]:
        """
        Returns a list of SrcBlock objects representing the methods in this block.
        If no methods are found, returns an empty list.
        """
        if methods := self._extract_methods(self.code, self.lang):
            return dict(code=methods)
        return dict()

    def typeset(self) -> set[str]:
        """
        Collects a set of all the non-implicit types referenced by this block's signature,
        both in its arguments and in its return value (if either are present in the first place).

        Returns:
            A set of strings naming type "bases", e.g. "dict" rather than "dict[str, str]".
        """
        types: set[str] = set()
        if self.type_base:
            types |= set(filter(bool, self.RGXS['typesplit'].split(self.type_base)))
        if self.args:
            types |= set(t for arg in self.args for t in arg.all_bases())
        return set(filter(self._imported_type_filter, types))

    @ft.cached_property
    def is_static(self) -> bool:
        """ Returns True if the method is static, False otherwise. """
        return al.any_has_any(self.annotations, '@staticmethod', '@classmethod')

    @ft.cached_property
    def is_property(self) -> bool:
        """ Returns True if the method is a property, False otherwise. """
        return al.any_has_any(self.annotations, 'property')
