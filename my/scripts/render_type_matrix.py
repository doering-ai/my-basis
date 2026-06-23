############
### HEAD ###
############
### STANDARD
from __future__ import annotations
from typing import ClassVar
import argparse as ap
import functools as ft
import itertools as it

### EXTERNAL
import pydantic as pyd
from pandas import DataFrame

### INTERNAL
from my import MyType, RegexStore, GoogleSheet, env
from my.typing.cast import TypeCast, Transform


############
### BODY ###
############
class Matrix(pyd.BaseModel):
    """Worker for calculating the coverage of `my.typing.check`."""

    RGXS: ClassVar[RegexStore] = RegexStore.new(
        implicit=(
            '|',
            r'\b',
            [
                r'(\d+)-\1\d*',  # super->sub transformations are assumed
                r'11[12]-11[12]',  # str|byte -> str|byte is handled by internal machinery
                r'12\d*-12\d*',  # Scalar -> Scalar
                r'(2[12])\d*-\1\d*',  # Vec and Map types handle intra-family conversions
            ],
            r'\b',
        ),
    )
    sheet_id: str

    # -------------------
    # `.` Initial Methods
    # -------------------
    @pyd.model_validator(mode='before')
    @classmethod
    def _init_matrix(cls, data: dict) -> dict:
        """Initialize the matrix, including user authentication w/ Google."""
        data['sheet'] = data.setdefault('sheet', GoogleSheet())
        return data

    @ft.cached_property
    def sheet(self) -> GoogleSheet:
        """Return the connected GoogleSheet instance, connecting if necessary."""
        assert self.sheet_id, 'Remote sheet ID is not configured.'
        sheet = GoogleSheet()
        if sheet.is_connected:
            assert sheet.uid == self.sheet_id, (
                f'Already connected to a different sheet ({sheet.uid[:8]}...).'
            )
        else:
            sheet.connect(self.sheet_id)
        return sheet

    @ft.cached_property
    def tc_sheet(self) -> DataFrame:
        """Return the typecast worksheet."""
        df = self.sheet.read('typecasts', 'A1:ZZ', header=2)
        # Drop unwanted rows and columns
        df = df.set_index('idx_0')
        df = df.drop([col for col in df.columns if not col.isdigit()], axis=1)
        return df

    @ft.cached_property
    def tr_sheet(self) -> DataFrame:
        """Return the typecast worksheet."""
        df = self.sheet.read('transforms', 'A1:ZZ', header=2)
        df = df.set_index(('source_idx', 'target_idx'))
        df = df.drop([col for col in df.columns if not col.isdigit()], axis=1)
        return df

    # -------------------
    # `-` Private Methods
    # -------------------
    def _render_transform(self, t0: MyType, t1: MyType, transform: Transform) -> list[str]:
        def _render(idx: str) -> str:
            is_from = idx.startswith(t0.idx)
            is_to = idx.startswith(t1.idx)
            n0 = len(idx) - len(t0.idx) + 1
            n1 = len(idx) - len(t1.idx) + 1
            if is_from and is_to:
                return ('+' * n1) + '/' + ('-' * n0)
            elif is_from:
                return '-' * n0
            elif is_to:
                return '+' * n1
            else:
                return ''

        return [str(t0), t0.idx, str(t1), t1.idx, *(map(_render, MyType.IDXS.keys()))]

    # -------------------
    # `+` Primary Methods
    # -------------------
    @classmethod
    def is_implicit(cls, source: MyType, target: MyType) -> bool:
        """Determine if a cast from source to target can be performed implicitly."""
        return bool(
            source.match(target) or cls.RGXS.fullmatch('implicit', f'{source.idx}-{target.idx}')
        )

    def render_transforms(self) -> list[list[str]]:
        """Render a row of cells for every one of our cast transforms."""
        n_header_col = 4
        return [
            [*('' for _ in range(n_header_col)), *(map(str, MyType.IDXS.values()))],
            [
                'source',
                'source_idx',
                'target',
                'target_idx',
                *(map(str, MyType.IDXS.keys())),
            ],
            *it.starmap(self._render_transform, TypeCast.TRANSFORMS),
        ]

    def render_typecasts(self) -> list[list[str]]:
        """Render a cell for every type combination."""
        n_header_col = 4
        return [
            [*('' for _ in range(n_header_col)), *(map(str, MyType.IDXS.values()))],
            [
                'name',
                'idx',
                'name_indented',
                'is_native',
                *(map(str, MyType.IDXS.keys())),
            ],
            *it.starmap(self._render_transform, TypeCast.TRANSFORMS),
        ]

    # ------------------
    # `*` Public Methods
    # ------------------
    def __call__(self) -> None:
        """Perform the work of the script."""


############
### MAIN ###
############
def _parse_args() -> ap.Namespace:
    parser = ap.ArgumentParser(
        description='Generate and upload data describing the coverage of `my.typing.check`.'
    )

    parser.add_argument(
        '-s',
        '--sheet_id',
        '--remote',
        default=env.MY_TYPE_GSHEET,
        help='The Google Sheet ID to use as a remote source.',
    )

    return parser.parse_args()


def main() -> None:
    """Render the type matrix and write it to the configured Google Sheet."""
    args = _parse_args()
    matrix = Matrix(**vars(args))
    matrix()


if __name__ == '__main__':
    main()
