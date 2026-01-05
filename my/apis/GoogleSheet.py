############
### HEAD ###
############
### STANDARD
from typing import Any, ClassVar
import functools as ft
import itertools as it

### EXTERNAL
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials as OAuthCredentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from google.auth.external_account_authorized_user import Credentials as TokenCredentials
import logfire as fire
import pandas as pd

### INTERNAL
from ..utils import ut
from .Environment import env

DataFrame = pd.DataFrame

############
### DATA ###
############
MY_CREDS = env.path('MY_CREDS', '~/my/.creds', mkdir=True)
MY_CACHE = env.path('MY_CACHE', '~/my/.cache', mkdir=True)


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
    gcreds: OAuthCredentials | TokenCredentials | None = None

    # -------------------
    # `.` Initial Methods
    # -------------------
    def __new__(cls):
        if cls.INST is None:
            cls.INST = super().__new__(cls)
        return cls.INST

    def connect(self, uid: str) -> None:
        """
        Connect to a Google Sheet via its sheet ID, loading its conents into local memory.

        Args:
            uid: The Google Sheet ID (not URL).
        """
        # I. Store the sheet ID
        self.uid = uid

        # II. Fetch this sheet's metadata
        info = self.genexec('get')

        # III. Parse and record
        self.name = info['properties']['title']
        _worksheets = [ws['properties'] for ws in info['sheets']]
        self.worksheets = [ws['title'] for ws in sorted(_worksheets, key=lambda ws: ws['index'])]

    def disconnect(self) -> None:
        """
        Disconnect from the current Google Sheet, clearing all cached data and freeing memory.
        """
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

        fire.info('Closed Google Sheets connection.')

    # -------------------
    # `-` Private Methods
    # -------------------
    @staticmethod
    def serialize_data(
        data: DataFrame,
        header: bool = True,
        index: bool = False,
    ) -> list[list[str]]:
        """
        Serialize a pandas DataFrame into a list of lists for Google Sheets API consumption.

        Args:
            data: The DataFrame to serialize.
            header: If true, include column names as the first row.
            index: If true, include the index as the first column.
        Returns:
            A list of lists representing the DataFrame.
        """
        df = data.copy().reset_index()
        values = df.fillna('').astype(str).values.tolist()
        if header:
            values = [df.columns.tolist()] + values
        if not index:
            values = [row[1:] for row in values]
        return values

    @staticmethod
    def deserialize_data(values: list[list], header: bool = True, index: str = '') -> DataFrame:
        """
        Deserialize a list of lists from the Google Sheets API into a pandas DataFrame.
        Args:
            values: The list of lists to deserialize.
            header: If true, use the first row as column names.
            index: The column to use as the index, if any.
        Returns:
            A pandas DataFrame representing the data.
        """
        if not any(values):
            return DataFrame()
        if header:
            head, *rest = values
            if len(head) < (width := max(map(len, rest)) if rest else 0):
                head = [*head, *([f'Column {i + 1}' for i in range(len(head), width)])]
            df = DataFrame(rest, columns=head)
        else:
            df = DataFrame(values)

        if index:
            df.set_index(index, inplace=True)
        return df.fillna('').ffill()

    @staticmethod
    def shape_to_range(shape: tuple[int, int], start: str = 'A1') -> str:
        """
        Convert a shape (width, height) into an A1-style range string, starting from `start`.
        Args:
            shape: The (width, height) of the range.
            start: The starting cell (default 'A1').
        Returns:
            An A1-style range string.
        """

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

        width, height = shape
        start_col = ''.join(it.takewhile(str.isalpha, start))
        start_row = start[len(start_col) :]
        assert start_col, f'Invalid start cell provided: {start}.'
        assert start_row.isdigit(), f'Invalid start cell provided: {start}'

        start_col_num = col_to_num(start_col)
        start_row_num = int(start_row)

        end_col_num = start_col_num + width - 1
        end_row_num = start_row_num + height - 1

        end_col = num_to_col(end_col_num)
        return f'{start}:{end_col}{end_row_num}'

    # -------------------
    # `+` Primary Methods
    # -------------------
    def genexec(self, endpoint: str, **kwargs: Any) -> dict[str, Any]:
        """
        Generic executor for Google Sheets API endpoints (relatively rare).
        Args:
            endpoint: The endpoint to call.
            kwargs: Additional arguments to pass to the endpoint.
        Returns:
            The response from the API call.
        """
        fn = getattr(self.sheets, endpoint)
        return fn(spreadsheetId=self.uid, **kwargs).execute()

    def exec(self, endpoint: str, **kwargs: Any) -> dict[str, Any]:
        """
        Generic executor for Google Sheets API `values` endpoints (most data operations).
        Args:
            endpoint: The endpoint to call.
            kwargs: Additional arguments to pass to the endpoint.
        Returns:
            The response from the API call.
        """
        fn = getattr(self.values, endpoint)
        return fn(spreadsheetId=self.uid, **kwargs).execute()

    def auth(self) -> None:
        """
        Authenticate with Google APIs via OAuth2, caching tokens locally for future use in the
        $MY_CREDS directory.

        See: googleapis.dev/python/google-auth/latest/reference/google.oauth2.credentials.html
        """
        assert self.SCOPES, 'Must provide at least one scope to authenticate with Google APIs.'
        did_change = False
        gcreds_dir = MY_CREDS / 'google'
        gcreds_dir.mkdir(parents=True, exist_ok=True)
        creds_file = gcreds_dir / 'google_credentials.json'
        token_file = gcreds_dir / 'google_token.json'

        # I. Load locally-cached creds
        if token_file.exists():
            creds = OAuthCredentials.from_authorized_user_file(token_file.as_posix(), self.SCOPES)

            # II.Refresh token
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                    did_change = True
                except Exception:
                    fire.info('Failed to refresh credentials!')
                    creds = None
        else:
            creds = None

        # III. Log in
        if creds is None:
            flow = InstalledAppFlow.from_client_secrets_file(creds_file.as_posix(), self.SCOPES)
            creds = flow.run_local_server(port=0)
            did_change = True

        assert creds is not None, 'Failed to authenticate with Google Sheets.'
        assert creds.valid, 'Invalid Google credentials.'

        # IV. Save the credentials for the next run
        if did_change:
            token_file.write_text(creds.to_json())

        self.gcreds = creds

    # ------------------
    # `*` Public Methods
    # ------------------
    @property
    def is_connected(self) -> bool:
        """Check if currently connected to a Google Sheet."""
        return bool(self.uid)

    @ft.cached_property
    def sheets(self) -> Any:
        """Build and return the Google Sheets API client."""
        if self.gcreds is None:
            self.auth()

        ret = build('sheets', 'v4', credentials=self.gcreds).spreadsheets()
        assert ret is not None, 'Failed to build Google Sheets API.'
        return ret

    @ft.cached_property
    def values(self) -> Any:
        """Return the Google Sheets API `values` resource."""
        return self.sheets.values()

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
        response = self.exec('get', range=f'{worksheet}!{cells}')
        return self.deserialize_data(response['values'], header=header, index=index)

    def batch_read(self, *args: str, **kwargs: dict[str, Any]) -> dict[str, DataFrame]:
        """
        Load multiple worksheets/ranges from the given google sheet via the Google Sheets API.

        Args:
            *args: The worksheet names or ranges to load.
            **kwargs: Additional options for each range. Each value is a dictionary of options to
                pass to `deserialize_data`.
        """
        # I. Issue the request
        n_args = len(args)
        keys = [*args, *kwargs.keys()]
        ranges = [(f'{key}!A1:Z' if not ut.has_any(key, '!', ':') else key) for key in keys]
        response = self.exec('batchGet', ranges=ranges)
        assert response and 'valueRanges' in response, 'Invalid GoogleSheets response'

        # II. Parse the responses in turn
        ret = dict()
        for i, reply in enumerate(response['valueRanges']):
            sub_kwargs = kwargs[keys[i]] if i >= n_args else {}
            ret[reply['range']] = self.deserialize_data(reply['values'], **sub_kwargs)

        # III. Simplify the keys of the returned dictionary to worksheet names if they're unique
        if ut.all_has_all(ret.keys(), '!'):
            worksheets = [key.split('!', 1)[0] for key in ret.keys()]
            if len(set(worksheets)) == len(worksheets):
                ret = dict(zip(worksheets, ret.values(), strict=False))

        return ret

    def clear(self, worksheet: list[str] | str, cells: list[str] | str = '') -> None:
        """
        Clear the given range(s) from the Google Sheet.
        Args:
            worksheet: The worksheet name(s) to clear.
            cells: The cell range(s) to clear. If a single string is provided, it applies to all
                   worksheets. If a list is provided, it must match the length of `worksheet`.
        """
        if isinstance(worksheet, str):
            assert isinstance(cells, str)
            self.exec('clear', range=f'{worksheet}!{cells}')
            fire.info(f'Successfully cleared range {worksheet}!{cells}')
        else:
            if cells:
                assert isinstance(cells, list)
                assert worksheet and cells, 'Must provide at least one worksheeets and cell range.'
                assert len(worksheet) == len(cells), 'Unequal worksheet:cell lists given.'
                ranges = [f'{ws}!{cs}' for ws, cs in zip(worksheet, cells, strict=True)]
            else:
                ranges = worksheet
            response = self.exec('batchClear', body=dict(ranges=ranges))
            fire.info(f'Successfully cleared ranges {response["clearedRanges"]}.')

    def write(self, worksheet: str, data: DataFrame, cells: str = 'A1:Z', **kwargs) -> None:
        """
        Write data to a single worksheet in the Google Sheet.
        Args:
            worksheet: The name of the worksheet to write to.
            data: The DataFrame to write.
            cells: The range of cells to write to.
            **kwargs: Additional arguments to pass to `serialize_data`.
        """
        response = self.exec(
            'update',
            range=f'{worksheet}!{cells}',
            valueInputOption='RAW',
            body={'values': self.serialize_data(data, **kwargs)},
        )
        fire.info(f'Successfully updated range {response["updatedRange"]}')

    def batch_write(self, **kwargs: DataFrame) -> None:
        """
        Write multiple DataFrames to the Google Sheet in a single batch operation.
        Args:
            **kwargs: { 'worksheet!cells': DataFrame }
        """
        requests = []
        with fire.span(f'Writing {len(kwargs)} ranges to {self.name}...'):
            # I. Build the requests, adding on cell info where needed
            for target, df in kwargs.items():
                header = False
                index = False
                if not ut.has_any(target, '!', ':'):
                    h, w = df.shape
                    target += f'!{self.shape_to_range((w + 1, h + 1))}'
                    header = True
                    index = True
                elif 'A1' in target:
                    header = True
                    index = True

                requests.append(
                    dict(
                        range=target,
                        values=self.serialize_data(df, header=header, index=index),
                    )
                )

            # II. Issue the batch request
            response = self.exec('batchUpdate', body=dict(valueInputOption='RAW', data=requests))
            for resp in response['responses']:
                fire.info(f'Successfully updated range {resp["updatedRange"]}')

    def add_worksheets(self, *args: str, **kwargs: Any) -> None:
        """
        Add new worksheets to the Google Sheet.
        Args:
            *args: The names of the worksheets to add with default properties.
            **kwargs: A map of properties to set for each worksheet.
        """
        worksheets = [
            *(dict(title=worksheet) for worksheet in args),
            *(dict(title=worksheet, **properties) for worksheet, properties in kwargs.items()),
        ]

        response = self.genexec(
            'batchUpdate',
            body=dict(
                requests=[dict(addSheet=dict(properties=worksheet)) for worksheet in worksheets],
            ),
        )
        for reply in response['replies']:
            name = reply['addSheet']['properties']['title']
            if name not in self.worksheets:
                self.worksheets.append(name)

        fire.info(f'Created {len(worksheets)} new worksheets in {self.name}')


gsheet = GoogleSheet()
