############
### HEAD ###
############
### STANDARD

### EXTERNAL
import pytest as pyt

### INTERNAL
from my._010_types._0_enumerations import SrcLang
from my._010_types._1_dataclasses.text import Buffer
from my._010_types._1_dataclasses.src.SrcBlock import SrcBlock

cls = SrcBlock


############
### BODY ###
############
class TestSrcBlock:
    @pyt.fixture
    def inst(self) -> SrcBlock:
        return cls()

    # -------------------
    # `0` Initial Methods
    # -------------------

    # -------------------
    # `-` Private Methods
    # -------------------
    @pyt.mark.parametrize('text, expected', [
        ('', ''),
        ('', ''),
        ('', ''),
    ])
    def test_clean_sig_part(self, text: str, expected: str):
        ret = cls._clean_sig_part(text)
        assert ret == expected

    @pyt.mark.parametrize('text, lang, expected', [
        ('', '', ''),
        ('', '', ''),
        ('', '', ''),
    ])
    def test_render_doc(self, text: str, lang: SrcLang, expected: str):
        ret = cls._render_doc(text, lang)
        assert ret == expected

    @pyt.mark.parametrize(
        'text, pos, expected', [
            ('', 0, (0, 1)),
            ('', 0, (0, 1)),
            ('', 0, (0, 1)),
        ]
    )
    def test_py_block_span(self, text: str, pos: int, expected: tuple):
        ret = cls._py_block_span(Buffer.new(text), pos)
        assert ret == expected

    @pyt.mark.parametrize(
        'text, pos, expected', [
            ('', 0, (0, 1)),
            ('', 0, (0, 1)),
            ('', 0, (0, 1)),
        ]
    )
    def test_ts_block_span(self, text: str, pos: int, expected: tuple):
        ret = cls._ts_block_span(Buffer.new(text), pos)
        assert ret == expected

    @pyt.mark.parametrize(
        'text, pos, lang, expected', [
            ('', 0, '', (0, 1)),
            ('', 0, '', (0, 1)),
            ('', 0, '', (0, 1)),
        ]
    )
    def test_block_span(self, text: str, pos: int, lang: SrcLang, expected: tuple):
        ret = cls._block_span(Buffer.new(text), pos, lang)
        assert ret == expected

    @pyt.mark.parametrize('name, expected', [
        ('', ''),
        ('', ''),
        ('', ''),
    ])
    def test_imported_type_filter(self, name: str, expected: bool):
        ret = cls._imported_type_filter(name)
        assert ret == expected

    # -------------------
    # `+` Primary Methods
    # -------------------
    # SrcBlock._extract_args untested

    @pyt.mark.parametrize('text, lang, expected', [
        ('', '', ''),
        ('', '', ''),
        ('', '', ''),
    ])
    def test_extract_doc(self, text: str, lang: SrcLang, expected: str):
        ret = cls._extract_doc(Buffer.new(text), lang)
        assert ret == expected

    @pyt.mark.parametrize('kwargs, expected', [
        (dict(), ''),
        (dict(), ''),
        (dict(), ''),
    ])
    def test_type_base(self, kwargs: dict, expected: str):
        inst = cls.new(**kwargs)
        ret = inst.type_base
        assert ret == expected

    # ------------------
    # `x` Public Methods
    # ------------------
    @pyt.mark.parametrize(
        'kwargs, expected', [
            (dict(), (0, 1)),
            (dict(), (0, 1)),
            (dict(), (0, 1)),
        ]
    )
    def test_render(self, kwargs: dict, expected: tuple):
        inst = cls.new(**kwargs)
        ret = inst.render()
        assert ret == expected

    @pyt.mark.parametrize('kwargs, expected', [
        (dict(), ''),
        (dict(), ''),
        (dict(), ''),
    ])
    def test_str(self, kwargs: dict, expected: str):
        inst = cls.new(**kwargs)
        ret = inst.__str__()
        assert ret == expected

    @pyt.mark.parametrize('block, lang, expected', [
        ('', '', []),
        ('', '', []),
        ('', '', []),
    ])
    def test_extract_methods(self, block: str, lang: SrcLang, expected: list):
        ret = cls._extract_methods(Buffer.new(block), lang)
        assert ret == expected

    @pyt.mark.parametrize('kwargs, expected', [
        (dict(), ''),
        (dict(), ''),
        (dict(), ''),
    ])
    def test_typeset(self, kwargs: dict, expected: set):
        inst = cls.new(**kwargs)
        ret = inst.typeset()
        assert ret == expected

    @pyt.mark.parametrize('kwargs, expected', [
        (dict(), ''),
        (dict(), ''),
        (dict(), ''),
    ])
    def test_is_static(self, kwargs: dict, expected: bool):
        inst = cls.new(**kwargs)
        assert inst.is_static == expected

    @pyt.mark.parametrize('kwargs, expected', [
        (dict(), ''),
        (dict(), ''),
        (dict(), ''),
    ])
    def test_is_property(self, kwargs: dict, expected: bool):
        inst = cls.new(**kwargs)
        assert inst.is_property == expected
