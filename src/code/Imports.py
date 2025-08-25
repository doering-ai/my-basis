############
### HEAD ###
############
### STANDARD
from typing import ClassVar, Generator, Annotated
from collections import defaultdict, UserDict, Counter
from pathlib import Path
import itertools as it
import more_itertools as mi
import regex as re

### EXTERNAL
import logfire as fire
import pydantic as pyd

### INTERNAL
from my import Idx, ARCH, ROOT
from ..bases import utils as ut
from ..type import typist
from ..text import Buffer, RegexStore
from .Lang import Lang

############
### DATA ###
############
File = pyd.FilePath
Directory = pyd.DirectoryPath


class Section(UserDict[str, set[str]]):
    """ A custom dictionary to hold the imports for a section. """
    name: str

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.data = defaultdict(set, self.data or {})

    def add(self, module: str, *symbols: str) -> None:
        """
        Adds a given import to the section, combining with existing imports from this module
        if present.
        """
        symset = set(symbols)

        if ' as ' in module:
            module, alias = module.split(' ', 1)
            symset.add(alias)
        elif not symset:
            symset.add('')

        self.data[module] |= symset


SectionField = Annotated[Section, al.pyd_schemify(Section)]


############
### BODY ###
############
class Imports(pyd.BaseModel):
    """
    A simple dataclass to hold the imports for a source file.
    """
    SHORTCUTS: ClassVar[dict[Lang, dict[str, str]]] = defaultdict(dict)
    SECTIONS: ClassVar[tuple[str, str, str]] = ('standard', 'external', 'internal')
    RGXS: ClassVar[RegexStore] = RegexStore.new(
        options=dict(
            separator=r' *\n',
            autostrip_spaces=False,
            force_named_groups=True,
        ),
        type_base=r'^\w+',
        pascal_case=r'([[:upper:]][[:lower:]]+)+[[:upper:]]{0,2}',
        section_delim=r'(?mi)^[/#]{3} (STANDARD|INTERNAL|EXTERNAL)$',
        py_import=(
            '|sm', r'^', [
                r'import (?P<module>[.\w]+(as \w+)?)',
                r'from (?P<module>[.\w]+) import \(((?P<symbol>\w+(as \w+)?),?\s*)+\)',
                r'from (?P<module>[.\w]+) import ((?P<symbol>\w+(as \w+)?),? *)+',
            ], r'$'
        ),
    )

    lang: Lang = Lang.PY
    standard: SectionField = pyd.Field(default_factory=Section)
    external: SectionField = pyd.Field(default_factory=Section)
    internal: SectionField = pyd.Field(default_factory=Section)

    # -------------------
    # `0` Initial Methods
    # -------------------
    @classmethod
    def new(cls, text: str | Buffer = '', lang: Lang = Lang.PY, **kwargs: dict) -> 'Imports':
        inst = cls(lang=lang)
        if text:
            delims, sections = cls.RGXS.fullsplit('section_delim', text)
            assert len(sections) == 4, f'Expected 3 sections, got {len(sections) - 1}.'

            rgx = f'{lang.prefix}_import'
            for (name, acc), raw in zip(inst.sections, sections[1:]):
                for match in cls.RGXS.finditer(rgx, raw):
                    acc.add(match.at('module'), *match.get('symbol', ['']))

        if kwargs:
            for name, section in inst.sections:
                for module, symbols in kwargs.get(name, {}).items():
                    if isinstance(symbols, str):
                        symbols = [symbols]
                    section.add(module, *symbols)

        inst.normalize()
        return inst

    @pyd.field_validator('lang', mode='after')
    def validate_lang(cls, lang: Lang) -> Lang:
        assert lang in (Lang.PY, Lang.TS), f'Unsupported language for imports: {lang}'
        return lang

    @classmethod
    def setup(cls) -> None:
        if cls.SHORTCUTS:
            return
        cls.setup_shortcuts()

    @pyd.model_serializer(mode='plain')
    def serialize(self) -> dict[str, list[str]]:
        """
        Render the import statements for a given set of imports, grouped by section.

        Returns:
            Three lists of valid source code lines.
        """
        # I. Validate the chosen language
        assert self.lang in (Lang.PY, Lang.TS), f'Unsupported language: {self.lang}'
        _serialize = self.serialize_py if self.lang == Lang.PY else self.serialize_ts

        # II. Normalize the imports (e.g. applying known path shortcuts)
        self.normalize()

        # III. Render each section, sorting by module name
        return {
            name: list(mi.flatten(it.starmap(_serialize, sorted(section.items()))))
            for name, section in self.sections
        }

    # -------------------
    # `-` Private Methods
    # -------------------
    def serialize_py(self, module: str, symset: set[str]) -> Generator[str, None, None]:
        symset = set(symset)  # Make a copy to modify

        # I Check for bare module-level imports
        if '' in symset:
            yield f'import {module}'
            symset.remove('')

        # II. Check for aliased modules
        if aliases := set(filter(lambda symbol: symbol.startswith('as '), symset)):
            yield from (f'import {module} {alias}' for alias in aliases)
            symset -= aliases

        # III. Finally, import all other symbols in one block
        if symbols := list(sorted(symset)):
            yield f'from {module} import {", ".join(sorted(symbols))}'

    def serialize_ts(self, module: str, symset: set[str]) -> Generator[str, None, None]:
        symset = set(symset)  # Make a copy to modify

        # I. Check for bare module-level imports
        if '' in symset:
            yield f'import "{module}";'
            symset.remove('')

        # II. Check for a default symbol
        if '_DEFAULT' in symset:
            default = module.rsplit('/', 1)[-1].rsplit('.', 1)[-1].strip('_').title()
            default = f'{default}, '
            symset.remove('_DEFAULT')
        else:
            default = ''

        # III. Finally, import named symbols in one block
        if symbols := list(sorted(symset)):
            yield f'import {default}{{ {", ".join(symbols)} }} from "{module}";'

    def rename_internal(self, old: str, new: str) -> None:
        assert old in self.internal, f'Cannot rename non-internal import: {old}'
        self.internal.add(new, *self.internal.pop(old))

    # -------------------
    # `+` Primary Methods
    # -------------------
    def normalize(self) -> None:
        """
        Edits the passed imports in place, replacing long paths with dedicated shortcuts.

        Args:
            imports: A list of three lists of import strings, grouped by section.
            lang: The source language for which to normalize the imports.
        """
        if self.shortcuts and self.internal:
            for module in self.internal.keys():
                if orig := next(filter(module.startswith, self.shortcuts.keys()), None):
                    self.rename_internal(module, module.replace(orig, self.shortcuts[orig]))
                elif self.lang == Lang.TS and not module.startswith('@/'):
                    self.rename_internal(module, f'@/{module}')

    def universalize(self, origin: Path) -> None:
        """
        Modify the internal imports, changing relative imports to absolute ones.
        """
        if self.lang != Lang.PY:
            return
        elif not (relatives := set(filter(lambda _m: _m.startswith('.'), self.internal.keys()))):
            return

        if origin.is_absolute():
            origin = origin.relative_to(ROOT)
        if origin.is_file():
            origin = origin.parent

        for module in relatives:
            self.rename_internal(module, (origin / module).resolve().as_posix())

    # ------------------
    # `x` Public Methods
    # ------------------
    def __bool__(self) -> bool:
        return bool(self.standard or self.external or self.internal)

    def __len__(self) -> int:
        return len(self.standard) + len(self.external) + len(self.internal)

    def __ior__(self, other: 'Imports') -> 'Imports':
        """ Merge another Imports instance into this one, combining the sections. """
        assert isinstance(other, Imports), f'Invalid merge type: {type(other)}'
        assert self.lang == other.lang, f'Tried to merge languages ({self.lang} != {other.lang})'

        for (name, lhs), (_, rhs) in zip(self.sections, other.sections):
            for module, symbols in rhs.items():
                lhs.add(module, *symbols)
        return self

    def __or__(self, other: 'Imports') -> 'Imports':
        """ Create a new Imports instance that merges this one with another. """
        new = self.model_copy(deep=True)
        new |= other
        return new

    @property
    def shortcuts(self) -> dict[str, str]:
        return self.SHORTCUTS[self.lang]

    @property
    def sections(self) -> list[tuple[str, Section]]:
        return [(section, getattr(self, section)) for section in self.SECTIONS]

    def copymask(self, variables: set[str], origin: File) -> 'Imports':
        """
        Given a set of variable names, returns a list of three dictionaries representing the
        imports needed to cover those variables, split into STANDARD, MODULAR, and LOCAL imports.
        Obviously, only imports used by this file can be copied.

        Args:
            variables: The set of variable names to cover, e.g. "Buffer" or "al"
            origin: The origin file or directory for relative imports, if applicable.

        Returns:
            A list of three dictionaries mapping module names to sets of symbols to import.
            An empty string in the set indicates a bare import of the module itself.
        """
        new = Imports(lang=self.lang)

        # I. Clean up the passed arguments, looking for just the base of each type
        variables = set(match.text for match in self.RGXS.apply('type_base', variables) if match)
        if not variables:
            return new

        for (name, lhs), (_, rhs) in zip(self.sections, new.sections):
            for module, symbols in lhs.items():
                assert ' ' not in module
                # II. Compare variables to imported symbols (and their aliases)
                for symbol in symbols:
                    if self.lang == Lang.PY:
                        if symbol.startswith('as '):
                            # II.i. Catch module-level aliases
                            module_alias = symbol.split(' ', 1)[1]
                            if module_alias in variables:
                                variables.remove(module_alias)
                                rhs[module].add(symbol)
                            continue
                        elif ' as ' in symbol:
                            # II.ii. Check both sides of symbol aliases
                            base, alias = symbol.split(' as ', 1)
                            if alias in variables:
                                variables.remove(alias)
                                rhs[module].add(symbol)
                                continue
                            else:
                                symbol = base

                    # II.iii. Check normal, non-aliased symbols
                    if symbol in variables:
                        variables.remove(symbol)
                        rhs[module].add(symbol)

                # III. Compare variables to the module itself
                if module in variables:
                    # III.i. Compare variables to the bare module
                    variables.remove(module)
                    rhs[module].add('')
                elif self.lang == Lang.PY and '.' in module:
                    # III.ii. Compare variables to the base of a submodule
                    if (base := module.split('.', 1)[0]) in variables:
                        variables.remove(base)
                        rhs[base].add('')

        # IV. Fix any relative module paths for local imports
        if self.lang == Lang.PY and new.internal and origin:
            new.universalize(origin)

        return new
