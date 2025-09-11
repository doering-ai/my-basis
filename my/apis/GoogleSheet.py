############
### HEAD ###
############
### STANDARD
from pathlib import Path
from typing import Any, ClassVar
import os
import functools as ft

### EXTERNAL
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials as GoogleCredentials
from google_auth_oauthlib.flow import InstalledAppFlow  # type: ignore[import-untyped]
from googleapiclient.discovery import build  # type: ignore[import-untyped]
import logfire as fire
import pandas as pd
import numpy as np
from ovld import ovld

### INTERNAL
from ..base import utils as ut
from ..type.Typist import typist

DataFrame = pd.DataFrame

############
### DATA ###
############
MY_CREDS = Path(os.environ.get('MY_CREDS', '~/my/.creds')).expanduser().resolve()
MY_CREDS.mkdir(parents=True, exist_ok=True)

MY_CACHE = Path(os.environ.get('MY_CACHE', '~/my/.cache')).expanduser().resolve()
MY_CACHE.mkdir(parents=True, exist_ok=True)


############
### BODY ###
############
class GoogleSheet:
    INST: ClassVar['GoogleSheet|None'] = None
    SCOPES: ClassVar[list[str]] = ['https://www.googleapis.com/auth/spreadsheets']

    # Metadata
    uid: str = ''
    name: str = ''
    worksheets: list[str] = []

    # Connection objects
    gcreds: GoogleCredentials | None = None

    # -------------------
    # `0` Initial Methods
    # -------------------
    def __new__(cls, *args, **kwargs):
        if cls.INST is None:
            cls.INST = super().__new__(cls)
        return cls.INST

    def connect(self, uid: str) -> None:
        # I. Store the sheet ID
        self.uid = uid

        # II. Fetch this sheet's metadata
        info = self.genexec('get')

        # III. Parse and record
        self.name = info['properties']['title']
        _worksheets = [ws['properties'] for ws in info['sheets']]
        self.worksheets = [ws['title'] for ws in sorted(_worksheets, key=lambda ws: ws['index'])]

    def disconnect(self) -> None:
        # I. Disconnect on their end
        if self.uid and self.gcreds is not None:
            self.sheets.close()

        # II. Clear cached properties
        ut.clear_cached_properties(self, 'sheets', 'values')

        # III. Null-out members
        self.gcreds = None
        self.uid = ''
        self.name = ''
        self.worksheets = []

        fire.info("Closed Google Sheets connection.")

    # -------------------
    # `-` Private Methods
    # -------------------
    @staticmethod
    def serialize_data(
        data: DataFrame,
        header: bool = True,
        index: bool = False,
    ) -> list[list[str]]:
        df = data.reset_index() if not index else data.copy()
        values = df.fillna('').astype(str).values.tolist()
        if header:
            values = [df.columns.tolist()] + values
        return values

    @staticmethod
    def deserialize_data(
        values: list[list],
        header: bool = True,
        index: str = '',
    ) -> DataFrame:
        df = DataFrame(values[1:], columns=values[0]) if header else DataFrame(values)

        if index:
            df.set_index(index, inplace=True)
        return df.replace('', np.nan).ffill()

    @staticmethod
    def shape_to_range(height: int, width: int, start: str = 'A1') -> str:
        def col_to_num(col: str) -> int:
            if not col:
                return 1
            num = 0
            for c in col:
                num = (num * 26) + (ord(c.upper()) - ord('A')) + 1
            return num

        def num_to_col(num: int) -> str:
            col = ''
            while num > 0:
                num, rem = divmod(num - 1, 26)
                col = chr(rem + ord('A')) + col
            return col

        start_col = ''.join(filter(str.isalpha, start))
        start_row = ''.join(filter(str.isdigit, start))
        assert start_row.isdigit(), "Invalid start cell provided."

        start_col_num = col_to_num(start_col)
        start_row_num = int(start_row)

        end_col_num = start_col_num + width - 1
        end_row_num = start_row_num + height - 1

        end_col = num_to_col(end_col_num)
        return f"{start_col}{start_row}:{end_col}{end_row_num}"

    # -------------------
    # `+` Primary Methods
    # -------------------
    @property
    def is_connected(self) -> bool:
        return bool(self.uid)

    @ft.cached_property
    def sheets(self) -> Any:
        if self.gcreds is None:
            self.auth()

        ret = build("sheets", "v4", credentials=self.gcreds).spreadsheets()
        assert ret is not None, "Failed to build Google Sheets API."
        return ret

    @ft.cached_property
    def values(self) -> Any:
        return self.sheets.values()

    def genexec(self, endpoint: str, **kwargs: Any) -> dict[str, Any]:
        fn = getattr(self.sheets, endpoint)
        return fn(spreadsheetId=self.uid, **kwargs).execute()

    def exec(self, endpoint: str, **kwargs: Any) -> dict[str, Any]:
        fn = getattr(self.values, endpoint)
        return fn(spreadsheetId=self.uid, **kwargs).execute()

    def auth(self) -> None:
        assert self.SCOPES, 'Must provide at least one scope to authenticate with Google APIs.'
        did_change = False
        gcreds_dir = MY_CREDS / 'google'
        gcreds_dir.mkdir(parents=True, exist_ok=True)

        # Load locally-cached creds
        token_file = gcreds_dir / 'google_token.json'
        if token_file.exists():
            creds = GoogleCredentials.from_authorized_user_file(token_file.as_posix(), self.SCOPES)

        # Refresh token
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                did_change = True
            except Exception:
                fire.info("Failed to refresh credentials!")
                creds = None

        # Log in
        if creds is None:
            creds_file = gcreds_dir / 'google_credentials.json'
            flow = InstalledAppFlow.from_client_secrets_file(creds_file.as_posix(), self.SCOPES)
            creds = flow.run_local_server(port=0)
            did_change = True

        assert creds is not None, "Failed to authenticate with Google Sheets."
        assert creds.valid, "Invalid Google credentials."

        # Save the credentials for the next run
        if did_change:
            typist.to_file(creds, token_file)

        self.gcreds = creds

    # ------------------
    # `x` Public Methods
    # ------------------
    def read(
        self,
        worksheet: str,
        cells: str = 'A1:Z',
        header: bool = True,
        index: str = '',
    ) -> DataFrame:
        """
        Load a single worksheet from the given google sheet via the Google Sheets API.

        Args:
            worksheet: The name (NOT ID) of the worksheet to load.
            cells: The range of cells to load.
            header: If true, use the first returned row as column names.
            index: The column to use as the index, if any.

        Returns:
            A pandas DataFrame with the worksheet data.
        """
        response = self.exec('get', range=f"{worksheet}!{cells}")
        return self.deserialize_data(response['values'], header=header, index=index)

    def batch_read(self, *args: str, **kwargs: dict[str, Any]) -> dict[str, DataFrame]:
        # I. Issue the request
        n_args = len(args)
        keys = [*args, *kwargs.keys()]
        response = self.exec(
            'batchGet',
            ranges=[(f'{key}!A1:Z' if not ut.has_any(key, '!', ':') else key) for key in keys]
        )

        # II. Parse the responses in turn
        ret = dict()
        for i, reply in enumerate(response['valueRanges']):
            sub_kwargs = kwargs[keys[i]] if i >= n_args else {}
            ret[reply['range']] = self.deserialize_data(reply['values'], **sub_kwargs)

        # III. Simplify the keys of the returned dictionary to worksheet names if they're unique
        if ut.all_has_all(ret.keys(), '!'):
            worksheets = [key.split('!', 1)[0] for key in ret.keys()]
            if len(set(worksheets)) == len(worksheets):
                ret = {worksheet: val for worksheet, val in zip(worksheets, ret.values())}

        return ret

    @ovld
    def clear(self, worksheet: str, cells: str):
        self.exec('clear', range=f'{worksheet}!{cells}')
        fire.info(f"Successfully cleared range {worksheet}!{cells}")

    @clear.register
    def clear_batch(self, worksheeets: list[str], cells: list[str]):
        assert worksheeets and cells, "Must provide at least one worksheeets and cell range."
        assert len(worksheeets) == len(cells), "Unequal worksheet:cell lists given."
        self.clear_ranges([f"{ws}!{cs}" for ws, cs in zip(worksheeets, cells)])

    @clear.register
    def clear_ranges(self, ranges: list[str], *args: Any):
        response = self.exec('batchClear', body=dict(ranges=ranges))
        fire.info(f"Successfully cleared ranges {response['clearedRanges']}.")

    def write(self, worksheet: str, data: DataFrame, cells: str = 'A1:Z', **kwargs) -> None:
        response = self.exec(
            'update',
            range=f"{worksheet}!{cells}",
            valueInputOption="RAW",
            body={'values': self.serialize_data(data, **kwargs)},
        )
        fire.info(f"Successfully updated range {response['updatedRange']}")

    def batch_write(self, **kwargs: DataFrame) -> None:
        # I. Build the requests, adding on cell info where needed
        requests = []
        for target, df in kwargs.items():
            header = False
            if not ut.has_any(target, '!', ':'):
                h, w = df.shape
                target += f'!{self.shape_to_range(h + 1, w)}'
                header = True
            elif 'A1' in target:
                header = True

            requests.append(dict(range=target, values=self.serialize_data(df, header=header)))

        # II. Issue the batch request
        response = self.exec('batchUpdate', body=dict(valueInputOption="RAW", data=requests))
        for resp in response['responses']:
            fire.info(f"Successfully updated range {resp['updatedRange']}")

    def add_worksheets(self, *args: str, **kwargs: Any) -> None:
        worksheets = [
            *(dict(title=worksheet) for worksheet in args),
            *(dict(title=worksheet, **properties) for worksheet, properties in kwargs.items()),
        ]

        response = self.genexec(
            'batchUpdate',
            body=dict(
                data=[dict(addSheet=dict(properties=worksheet)) for worksheet in worksheets],
            )
        )
        self.worksheets = [
            reply['addSheet']['properties']['title'] for reply in response['replies']
        ]

        fire.info(f"Created {len(worksheets)} new worksheets in {self.name}")


gsheet = GoogleSheet()
