############
### HEAD ###
############
# Standard imports
from typing import ClassVar, Any, Iterator, Iterable
import json
import itertools as it
import more_itertools as mi
import functools as ft
from pathlib import Path

# External imports
import regex as re
import pydantic as pyd
import jinja2 as jn
import logfire as fire

# Internal imports
from ..constants import ROOT
from ..aliases import validate_file, validate_dir, next_in, regex_dict
from .Idx import Idx
from .Typist import typist

############
### DATA ###
############
ARCH: 'Architectonic'
ENTRIES_DIR = 'my/_000_files/_1_entries'
JINJA_CACHE: dict[str, jn.Template] = {}


############
### BODY ###
############
class Architectonic(pyd.BaseModel):
    """A very commonly used tree of all the elements in the system; also in the DB"""
    class Cell(pyd.BaseModel):
        idx: Idx

        # Names
        singular: str
        plural: str

        # Division
        division: str

        # Methods
        antithesis: str
        thesis: str
        synthesis: str

        @classmethod
        def read(cls, idx: str, array: list[str]) -> 'Architectonic.Cell':
            """Read a cell from the JSON file."""
            assert len(array) == 6, f'Malformed cell for {idx}: {array}'
            return cls(
                idx=Idx.new(idx),
                singular=array[0],
                plural=array[1],
                division=array[2],
                antithesis=array[3],
                thesis=array[4],
                synthesis=array[5],
            )

        def __lt__(self, other: 'Architectonic.Cell') -> bool:
            """Compare cells by their index."""
            return self.idx < other.idx

    file: pyd.FilePath
    data: dict[Idx, Cell] = {}
    parameters: dict[Idx, dict[str, dict[str, Any]]] = {}

    SIZE: ClassVar[int] = 510  # 2 + 4 + 8 + 16 + 32 + 64 + 128 + 256
    BASE: ClassVar[tuple[str, str]] = ('Element', 'Elements')
    INST: ClassVar['Architectonic | None'] = None
    ROOT: ClassVar[pyd.DirectoryPath] = ROOT
    JINJA: ClassVar[jn.Environment]
    NEG_IRIX: ClassVar[list[list[list[str]]]] = []
    POS_IRIX: ClassVar[list[list[list[str]]]] = []
    IRIX_MAP: ClassVar[list[list[str]]] = []

    RGXS: ClassVar[dict[str, re.Pattern]] = regex_dict(
        dict(
            arch_file=r'^\w+\.(?:py|tsx)$',
            arch_dir=r'^_\d_[[:lower:]]+$',
        )
    )

    # -------------------
    # `0` Initial Methods
    # -------------------
    def __new__(cls, **kwargs: Any) -> 'Architectonic':
        if cls.INST is None:
            cls.INST = super().__new__(cls)
        return cls.INST

    @classmethod
    def new(cls, **kwargs: Any) -> 'Architectonic':
        if cls.INST is not None:
            return cls.INST
        entries = cls.ROOT / ENTRIES_DIR
        file = entries / 'architectonic.json'
        validate_file(file)

        if not (data := kwargs.pop('data', {})):
            # Set base
            base = cls.Cell(
                idx=Idx(''),
                singular='Element',
                plural='Elements',
                division='',
                antithesis='antithesis',
                thesis='thesis',
                synthesis='synthesis',
            )

            # Load architectonic
            arch = json.loads(file.read_text())
            assert arch is not None and len(arch) == cls.SIZE, f'Malformed arch file: {file}'

            cells = [base, *sorted(it.starmap(cls.Cell.read, arch.items()))]
            data = {cell.idx: cell for cell in cells}
        assert len(data) == cls.SIZE + 1, f'Malformed data length: {len(data)} != {cls.SIZE + 1}'

        # Read color data in once per system
        cls.NEG_IRIX = cls._read_irix(entries / 'irix/irix-dark.yaml')
        cls.POS_IRIX = cls._read_irix(entries / 'irix/irix-light.yaml')

        inst = cls(file=file, data=data, **kwargs)
        inst.connect()
        return inst

    def connect(self) -> None:
        self.parameters = self.read_parameter_cache()

    # -------------------
    # `-` Private Methods
    # -------------------
    @classmethod
    def _read_irix(cls, file: pyd.FilePath) -> list[list[list[str]]]:
        """Read the irix file and return a dictionary of colors."""
        # I. Read the file
        irix = typist.from_yaml(file)
        chambers: list = list(map(list, mi.sliced(list(irix.keys()), 4)))
        assert len(chambers) == 5, f'Malformed irix file: {file}'

        # II. Save chamber and hue names once
        if not cls.IRIX_MAP:
            cls.IRIX_MAP = chambers

        # III. Parse and return the main values
        return [[list(irix[shade].values()) for shade in chamber] for chamber in chambers]

    def determine_filetypes(self, idx: Idx) -> list[str]:
        ret = []
        if re.match(r'^(?:[012].*|[ab])$', str(idx)):
            ret.append('py')
        if re.match(r'^(?:[3].*|[ab])$', str(idx)):
            ret.append('tsx')
        return ret

    def infer_idx(self, path: Path) -> Idx | None:
        if path.is_absolute():
            if str(path).startswith(str(ARCH.ROOT)):
                path = path.relative_to(ARCH.ROOT)
            else:
                fire.error(f'Path {path} is not relative to the ARCH root: {ARCH.ROOT}')
                return None

        if arch_parts := list(it.takewhile(self.RGXS['arch_dir'].match, path.parts)):
            return Idx.new(''.join(part[1] for part in mi.take(4, arch_parts)))
        else:
            fire.error(f'Path {path} does not match ARCH directory pattern.')
            return None

    def dir_filter(self, paths: Iterable[Path]) -> list[pyd.DirectoryPath]:
        dirs = [p for p in paths if p.is_dir() and self.RGXS['arch_dir'].match(p.name)]
        return list(sorted(dirs, key=lambda d: d.name))

    def file_filter(self, paths: Iterable[Path]) -> list[pyd.FilePath]:
        files = [p for p in paths if p.is_file() and self.RGXS['arch_file'].match(p.name)]
        return list(sorted(files, key=Path.as_posix))

    # -------------------
    # `+` Primary Methods
    # -------------------
    def read_parameter_cache(self) -> dict[Idx, dict[str, dict[str, Any]]]:
        """Get the directory where parameters are stored."""
        directory = self.get_dir(Idx('0001')) / 'parameters'
        validate_dir(directory)
        return {
            Idx(file.stem.split('_')[1]): typist.from_yaml(file)
            for file in directory.glob('_*.yaml')
        }

    # ------------------
    # `x` Public Methods
    # ------------------
    ### ---------------
    ### `x.i` Overrides
    ### ---------------
    def __contains__(self, idx: Idx) -> bool:
        return Idx.new(idx) in self.data

    def __len__(self) -> int:
        return self.SIZE

    def __getitem__(self, idx: Idx | str) -> 'Architectonic.Cell':
        return self.data[Idx.new(idx)]

    def keys(self) -> list[Idx]:
        return list(self.data.keys())

    def values(self) -> list['Architectonic.Cell']:
        return list(self.data.values())

    def items(self) -> list[tuple[Idx, 'Architectonic.Cell']]:
        return list(self.data.items())

    def idx_iter(self) -> Iterator[Idx]:
        yield from self.data.keys()

    ### -----------------
    ### `x.ii` Filesystem
    ### -----------------
    def get_filename(self, idx: Idx | str, filetype: str = '') -> str:
        idx = Idx.new(idx)
        prefix = '_' if idx.is_concrete else f'_{idx[-1]}_'
        suffix = '.' + filetype if filetype else ''
        return f'{prefix}{self[idx].singular}{suffix}'

    def get_dirname(self, idx: Idx | str) -> str:
        idx = Idx.new(idx)
        if len(idx) == 0:
            return ''
        elif not idx.is_concrete:
            return self.get_dirname(idx - 1)

        return f'_{idx[-1]}_{self[idx].plural.lower()}'

    def get_dir(self, idx: Idx | str) -> pyd.DirectoryPath:
        idx = Idx.new(idx)
        ancestors = list(map(self.get_dirname, idx.concrete_ancestors))
        if idx.is_concrete:
            ancestors.append(self.get_dirname(idx))

        return self.ROOT / '/'.join(ancestors)

    def get_file(self, idx: Idx | str, filetype: str = '') -> pyd.FilePath:
        idx = Idx.new(idx)
        if not filetype:
            filetype = 'py' if 'py' in self.determine_filetypes(idx) else 'tsx'
        return self.get_dir(idx) / self.get_filename(idx, filetype)

    # -----------
    # Incidentals
    # -----------
    def get_template(self, filename: str) -> jn.Template:
        if not hasattr(Architectonic, 'JINJA'):
            template_dir = self.get_dir(Idx('0001')) / 'templates'
            validate_dir(template_dir)
            Architectonic.JINJA = jn.Environment(
                loader=jn.FileSystemLoader(template_dir), trim_blocks=True, lstrip_blocks=True
            )
        if filename in JINJA_CACHE:
            return JINJA_CACHE[filename]
        else:
            JINJA_CACHE[filename] = ret = self.JINJA.get_template(filename)
            return ret

    def render(self, filename: str, data: dict[str, Any], **kwargs: Any) -> str:
        template = self.get_template(filename)
        return template.render(data, **kwargs)

    def get_parameters(self, idx: Idx, name: str) -> dict[str, Any]:
        if idx in self.parameters:
            # I. Primary case: This element has paramters
            return self.parameters[idx].get(name, {})
        elif anc_idx := next_in(self.parameters, reversed(list(idx.concrete_ancestors))):
            # II. Fallback case: An ancestor's file contains this element's parameters
            return self.parameters[anc_idx].get(name, {})
        else:
            # III. Null case: Most elements have no static parameters
            return {}

    def index_file(self, idx: Idx) -> pyd.FilePath:
        """Get the index file for a given index."""
        return self.get_dir(idx) / f'{self[idx].singular.lower()}_index.yaml'


ARCH = Architectonic.new()
