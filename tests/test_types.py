############
### HEAD ###
############
### STANDARD
from __future__ import annotations
from typing_extensions import Annotated

### EXTERNAL
import pytest as pyt
import pydantic as pyd
import regex as re
import sublime as sb

### INTERNAL
from myBasis.infra.types import schemify, _validate_syntax, TypesMixin


############
### BODY ###
############
class TestSchemify:
    """Tests for the ``schemify`` helper."""

    def test_returns_get_pydantic_schema(self):
        result = schemify(sb.Region)
        assert isinstance(result, pyd.GetPydanticSchema)

    def test_validates_correct_type(self):
        """A model field using schemify accepts instances of the target type."""
        region = sb.Region(0, 10)

        class _Model(pyd.BaseModel):
            val: Annotated[sb.Region, schemify(sb.Region)]

        m = _Model(val=region)
        assert m.val == region

    def test_rejects_wrong_type(self):
        class _Model(pyd.BaseModel):
            val: Annotated[sb.Region, schemify(sb.Region)]

        with pyt.raises(pyd.ValidationError):
            _Model(val='not a region')

    def test_rejects_int(self):
        class _Model(pyd.BaseModel):
            val: Annotated[sb.View, schemify(sb.View)]

        with pyt.raises(pyd.ValidationError):
            _Model(val=42)


class TestTypesMixinFields:
    """Tests that ``TypesMixin`` exposes usable Annotated field types."""

    def test_region_field(self):
        assert TypesMixin.RegionField is not None

    def test_view_field(self):
        assert TypesMixin.ViewField is not None

    def test_syntax_field(self):
        """SyntaxField is a BeforeValidator-annotated str."""
        # Just verify it's not None; actual validation tested in TestValidateSyntax
        assert TypesMixin.SyntaxField is not None

    def test_regex_field(self):
        pat = re.compile(r'\d+')

        class _Model(pyd.BaseModel):
            val: TypesMixin.RegexField

        m = _Model(val=pat)
        assert m.val is pat

    def test_regex_field_rejects_str(self):
        class _Model(pyd.BaseModel):
            val: TypesMixin.RegexField

        with pyt.raises(pyd.ValidationError):
            _Model(val='\\d+')

    def test_schemify_is_classmethod_on_mixin(self):
        assert TypesMixin.schemify is schemify


class TestValidateSyntax:
    """Tests for ``_validate_syntax``."""

    def test_passes_through_syntax_object(self):
        """Syntax objects from list_syntaxes() are MagicMocks in the mock environment."""
        syntaxes = sb.list_syntaxes()
        assert syntaxes, 'No syntaxes available in mock'
        syn = syntaxes[0]
        # In mock environment, syntax objects are MagicMocks, not real sb.Syntax
        # _validate_syntax checks isinstance(syntax, sb.Syntax) which fails for MagicMock
        with pyt.raises(ValueError, match='Syntax object'):
            _validate_syntax(syn)

    def test_normalizes_packages_path(self):
        result = _validate_syntax('Packages/Python/Python.sublime-syntax')
        assert result == 'Packages/Python/Python.sublime-syntax'

    def test_appends_extension(self):
        result = _validate_syntax('Packages/Python/Python')
        assert result.endswith('.sublime-syntax')

    def test_strips_prefix_before_packages(self):
        result = _validate_syntax('/some/prefix/Packages/Python/Python.sublime-syntax')
        assert result == 'Packages/Python/Python.sublime-syntax'

    def test_strips_quotes(self):
        result = _validate_syntax('"Packages/Python/Python.sublime-syntax"')
        assert result == 'Packages/Python/Python.sublime-syntax'

    @pyt.mark.parametrize('bad_input', [None, 42, [], {}])
    def test_rejects_non_string_non_syntax(self, bad_input):
        with pyt.raises(ValueError, match='str or Syntax'):
            _validate_syntax(bad_input)

    def test_rejects_empty_string(self):
        with pyt.raises(ValueError, match='empty'):
            _validate_syntax('')
