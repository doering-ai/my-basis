############
### HEAD ###
############
# ruff: noqa: E402
### STANDARD
from __future__ import annotations
from typing import Any, ClassVar
from types import FunctionType
from datetime import datetime
import functools as ft
import itertools as it
import logging
from pathlib import Path

### EXTERNAL
INSTALLED: bool = True
try:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials as OAuthCredentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    from google.auth.external_account_authorized_user import Credentials as TokenCredentials
    import pandas as pd
except ImportError:
    INSTALLED = False
    from unittest.mock import MagicMock

    names = ('pd', 'Request', 'OAuthCredentials', 'InstalledAppFlow', 'build', 'TokenCredentials')
    for name in names:
        globals()[name] = MagicMock(name=name)


### INTERNAL
from ..utils import ut
from .Environment import env

logger = logging.getLogger()


############
### BODY ###
############
class GoogleSheet:
    """A singleton wrapping the Google Sheets API v4 for usage in scripts and notebooks.

    This code is written against `Google's v4 REST API
    <https://developers.google.com/workspace/sheets/api/reference/rest>`__ for their Google
    Sheets product. They have multiple official python packages, but they all are fatally
    flawed in one way or another.

    .. important::
       These methods are only present if the **optional** `google` dependency is installed
       (`pip install my-basis[google]`). If you try to call them without it, an `ImportError`
       will be thrown.

    Authentication is handled automatically via Google's `OAuth2.0 for Web Server Applications
    <https://developers.google.com/identity/protocols/oauth2/web-server>`__ flow, which works by
    prompting the user to log in via an auto-launched browser window. From there, this class
    handles token caching and refresh, storing credentials in the `creds_dir` directory.

    .. caution::
       Credentials are stored unencrypted. Though they do expire quickly, please do not use this
       on an unsecure system without setting up some sort of encryption!

    Data is seamlessly converted between Google Sheets' list-of-lists format and pandas
    DataFrames. The class supports both single and batch operations for reading and writing
    worksheets, with intelligent handling of headers, indices, and cell ranges. Methods like
    `read()`/`batch_read()` and `write()`/`batch_write()` abstract away the complexity of the
    underlying API while preserving flexibility through A1-notation cell ranges.

    The singleton pattern ensures a single authenticated connection is maintained throughout
    your application's lifecycle, with explicit `connect()` and `disconnect()` methods for
    resource management.

    Examples:
        Connect once, then move worksheets in and out as DataFrames (requires the `google`
        extra, plus a browser for the first OAuth run)::

            >>> from my.apis import GoogleSheet
            >>> sheet = GoogleSheet()  # doctest: +SKIP
            >>> sheet.connect('1BxiM...your-sheet-id...upms')  # doctest: +SKIP
            >>> sheet.worksheets  # doctest: +SKIP
            ['Roster', 'Scores']
            >>> df = sheet.read('Roster')  # doctest: +SKIP
            >>> sheet.write('Scores', df)  # doctest: +SKIP
    """

    INST: ClassVar[GoogleSheet | None] = None
    SCOPES: ClassVar[list[str]] = [
        'https://www.googleapis.com/auth/spreadsheets',
        'https://www.googleapis.com/auth/drive.metadata.readonly',
    ]
    LOGGER: ClassVar[logging.Logger] = logger

    _CREDS_DIR: ClassVar[str] = ''
    _CACHE_DIR: ClassVar[str] = ''

    # Metadata
    uid: str = ''
    name: str = ''
    worksheets: list[str]

    # Connection objects
    gcreds: OAuthCredentials | TokenCredentials | None = None

    # -------------------
    # `.` Initial Methods
    # -------------------
    def __new__(cls):
        """Implement the singleton pattern."""
        if cls.INST is None:
            cls.INST = super().__new__(cls)
        return cls.INST

    def __init__(self) -> None:
        """Initialize the GoogleSheet singleton."""
        self.worksheets = []

    @staticmethod
    def _import_guard[F: FunctionType](fn: F) -> F:
        @ft.wraps(fn)
        def _wfn(*args: Any, **kwargs: Any):
            if not INSTALLED:
                name = fn.__name__
                raise ImportError(
                    f'{name}() requires the optional [google] extra: pip install my-basis[google]'
                )
            return fn(*args, **kwargs)

        return _wfn  # type: ignore

    @_import_guard
    def connect(self, uid: str) -> None:
        """Connect to a Google Sheet via its sheet ID, loading its contents into local memory.

        Fetches the sheet's metadata, recording its display `name` and the ordered list of its
        `worksheets`. Triggers the OAuth flow on first use (see `auth()`).

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

    @_import_guard
    def disconnect(self) -> None:
        """Disconnect from the current Google Sheet, clearing all cached data and freeing memory."""
        # I. Disconnect on their end
        if self.uid and self.gcreds is not None:
            self.sheets_api.close()

        # II. Clear cached properties
        ut.clear_cached_properties(self, 'sheets', 'values')

        # III. Null-out members
        self.gcreds = None
        self.uid = ''
        self.name = ''
        self.worksheets = []

        self.LOGGER.info('Closed Google Sheets connection.')

    # ---------------------------
    # `-` Serialization Utilities
    # ---------------------------
    @staticmethod
    @_import_guard
    def serialize_data(
        data: pd.DataFrame,
        header: bool = True,
        index: bool = False,
    ) -> list[list[str]]:
        """Serialize a pandas DataFrame into a list of lists for Google Sheets API consumption.

        Args:
            data: The DataFrame to serialize.
            header: If true, include column names as the first row.
            index: If true, include the index as the first column.
        Returns:
            A list of lists representing the DataFrame.
        Examples:
            Serialize a small frame, with and without its index::

                >>> import pandas as pd
                >>> from my.apis import GoogleSheet
                >>> df = pd.DataFrame({'name': ['ada', 'bob'], 'score': [92, 85]})
                >>> GoogleSheet.serialize_data(df)
                [['name', 'score'], ['ada', '92'], ['bob', '85']]
                >>> GoogleSheet.serialize_data(df, index=True)
                [['index', 'name', 'score'], ['0', 'ada', '92'], ['1', 'bob', '85']]
        """
        df = data.copy().reset_index()
        values = df.fillna('').astype(str).to_numpy().tolist()
        if header:
            values = [df.columns.tolist(), *values]
        if not index:
            values = [row[1:] for row in values]
        return values

    @staticmethod
    @_import_guard
    def deserialize_data(values: list[list], header: int = 1, index: str = '') -> pd.DataFrame:
        """Deserialize a list of lists from the Google Sheets API into a pandas DataFrame.

        Args:
            values: The list of lists to deserialize.
            header: The 1-based row number to use as column names (rows before it are dropped),
                or 0 to number the columns instead. Short header rows are padded with
                `Column N` placeholders.
            index: The column to use as the index, if any.
        Returns:
            A pandas DataFrame representing the data.
        Examples:
            Rebuild a DataFrame from raw cell values::

                >>> from my.apis import GoogleSheet
                >>> GoogleSheet.deserialize_data([['name', 'score'], ['ada', '92'], ['bob', '85']])
                  name score
                0  ada    92
                1  bob    85
        """
        if not any(values):
            return pd.DataFrame()
        if header:
            if header > 1:
                values = values[header - 1 :]
            head, *rest = values
            if rest and len(head) < (width := max(map(len, rest))):
                head = [*head, *([f'Column {i + 1}' for i in range(len(head), width)])]
            df = pd.DataFrame(rest, columns=head)
        else:
            df = pd.DataFrame(values)

        if index:
            df = df.set_index(index)
        return df.fillna('').ffill()

    @staticmethod
    @_import_guard
    def shape_to_range(shape: tuple[int, int], start: str = 'A1') -> str:
        """Convert a shape (width, height) into an A1-style range string.

        Args:
            shape: The dimensions of the range, i.e. `(num_columns, num_rows)`.
            start: The cell to place the top-left corner of the block on (default `A1`).
        Returns:
            An A1-style range string.
        Examples:
            Anchor a block at the origin or at an arbitrary cell::

                >>> from my.apis import GoogleSheet
                >>> GoogleSheet.shape_to_range((3, 5))
                'A1:C5'
                >>> GoogleSheet.shape_to_range((2, 2), start='B2')
                'B2:C3'
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
    @_import_guard
    def genexec(self, endpoint: str, **kwargs: Any) -> dict[str, Any]:
        """Generic executor for Google Sheets API endpoints (relatively rare).

        Args:
            endpoint: The endpoint to call.
            kwargs: Additional arguments to pass to the endpoint.
        Returns:
            The response from the API call.
        """
        fn = getattr(self.sheets_api, endpoint)
        return fn(spreadsheetId=self.uid, **kwargs).execute()

    @_import_guard
    def exec(self, endpoint: str, **kwargs: Any) -> dict[str, Any]:
        """Generic executor for Google Sheets API `values` endpoints (most data operations).

        Args:
            endpoint: The endpoint to call.
            kwargs: Additional arguments to pass to the endpoint.
        Returns:
            The response from the API call.
        """
        fn = getattr(self.values, endpoint)
        return fn(spreadsheetId=self.uid, **kwargs).execute()

    @_import_guard
    def auth(self) -> None:
        """Authenticate with Google APIs, caching tokens locally in `creds_dir`.

        If the user already has credentials stored on disk, those are read by this method and no
        unnecessary work is performed. The credentials are automatically refreshed if necessary &
        possible.

        See Google's authentication flow documentation for further guidance:
        googleapis.dev/python/google-auth/latest/reference/google.oauth2.credentials.html
        """
        assert self.SCOPES, 'Must provide at least one scope to authenticate with Google APIs.'
        did_change = False
        gcreds_dir = self.creds_dir / 'google'
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
                    self.LOGGER.info('Failed to refresh credentials!')
                    creds = None
        else:
            creds = None

        # III. Log in
        if creds is None:
            if not creds_file.exists():
                creds_file.parent.mkdir(parents=True, exist_ok=True)
                creds_file.touch(exist_ok=True)
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
    def creds_dir(self) -> Path:
        """Get the directory where credentials are stored, creating it if it doesn't exist."""
        return env.path('MY_CREDS', self._CREDS_DIR or '~/my/.creds', mkdir=True)

    @ft.cached_property
    def cache_dir(self) -> Path:
        """Get the directory where cache files are stored, creating it if it doesn't exist."""
        return env.path('MY_CACHE', self._CACHE_DIR or '~/my/.cache', mkdir=True)

    @ft.cached_property
    def sheets_api(self) -> Any:
        """Build and return the Google Sheets API client."""
        if self.gcreds is None:
            self.auth()

        service = build('sheets', 'v4', credentials=self.gcreds)
        ret = getattr(service, 'spreadsheets')()
        assert ret is not None, 'Failed to build Google Sheets API.'
        return ret

    @ft.cached_property
    def files_api(self) -> Any:
        """Build and return the Google Drive API client for file-level operations."""
        if self.gcreds is None:
            self.auth()
        service = build('drive', 'v3', credentials=self.gcreds)
        ret = getattr(service, 'files')()
        assert ret is not None, 'Failed to build Google Drive API.'
        return ret

    @ft.cached_property
    def values(self) -> Any:
        """Return the Google Sheets API `values` resource."""
        return self.sheets_api.values()

    @_import_guard
    def mtime(self) -> datetime | None:
        """Get the last modified time of the connected Google Sheet, or `None` if not connected."""
        if self.is_connected:
            response = self.files_api.get(fileId=self.uid).execute()
            return datetime.fromisoformat(response['modifiedTime'])

    @_import_guard
    def read(
        self,
        worksheet: str,
        cells: str = 'A1:Z',
        header: int = 1,
        index: str = '',
    ) -> pd.DataFrame:
        """Load a single worksheet from the given google sheet via the Google Sheets API.

        Args:
            worksheet: The name (NOT ID) of the worksheet to load.
            cells: The range of cells to load.
            header: The index of the row to use as column names; rows before it are ignored.
            index: The index of the column to use as the row names (i.e. the 'index'), if any.
        Returns:
            A pandas DataFrame with the worksheet data.
        Examples:
            Load a range, optionally naming the header and index (requires a connection)::

                >>> df = sheet.read(
                ...     'Roster', cells='A1:C10', header=1, index='name')  # doctest: +SKIP
        """
        response = self.exec('get', range=f'{worksheet}!{cells}')
        return self.deserialize_data(response['values'], header=header, index=index)

    @_import_guard
    def batch_read(self, *args: str, **kwargs: dict[str, Any]) -> dict[str, pd.DataFrame]:
        """Load multiple worksheets/ranges from the given google sheet via the Google Sheets API.

        Args:
            *args: The worksheet names or ranges to load.
            **kwargs: Additional options for each range. Each value is a dictionary of options to
                pass to `deserialize_data`.
        Returns:
            A map from range strings to DataFrames, with keys simplified to bare worksheet
            names whenever those are unique.
        Examples:
            Load several worksheets in one API call (requires a connection)::

                >>> frames = sheet.batch_read('Roster', 'Scores!A1:D20')  # doctest: +SKIP
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
            ret[reply['range']] = self.deserialize_data(reply['values'], **sub_kwargs)  # type: ignore

        # III. Simplify the keys of the returned dictionary to worksheet names if they're unique
        if ut.all_has_all(ret.keys(), '!'):
            worksheets = [key.split('!', 1)[0] for key in ret.keys()]
            if len(set(worksheets)) == len(worksheets):
                ret = dict(zip(worksheets, ret.values(), strict=False))

        return ret

    @_import_guard
    def clear(self, worksheet: list[str] | str, cells: list[str] | str = '') -> None:
        """Clear the given range(s) from the Google Sheet.

        If a single cell is provided, it applies to all given worksheets. If a list is provided, it
        must match the length of `worksheet`, identifying cells for each.

        Args:
            worksheet: The worksheet name(s) to clear.
            cells: The cell range(s) to clear.
        Examples:
            Clear one range, or several worksheets at once (requires a connection)::

                >>> sheet.clear('Roster', 'A2:C100')  # doctest: +SKIP
                >>> sheet.clear(['Roster', 'Scores'])  # doctest: +SKIP
        """
        if isinstance(worksheet, str):
            assert isinstance(cells, str)
            self.exec('clear', range=f'{worksheet}!{cells}')
            self.LOGGER.info(f'Successfully cleared range {worksheet}!{cells}')
        else:
            if cells:
                assert isinstance(cells, list)
                assert worksheet and cells, 'Must provide at least one worksheeets and cell range.'
                assert len(worksheet) == len(cells), 'Unequal worksheet:cell lists given.'
                ranges = [f'{ws}!{cs}' for ws, cs in zip(worksheet, cells, strict=True)]
            else:
                ranges = worksheet
            response = self.exec('batchClear', body=dict(ranges=ranges))
            self.LOGGER.info(f'Successfully cleared ranges {response["clearedRanges"]}.')

    @_import_guard
    def write(self, worksheet: str, data: pd.DataFrame, cells: str = 'A1:Z', **kwargs: Any) -> None:
        """Write data to a single worksheet in the Google Sheet.

        Args:
            worksheet: The name of the worksheet to write to.
            data: The DataFrame to write.
            cells: The range of cells to write to.
            **kwargs: Additional arguments to pass to `serialize_data`.
        Examples:
            Write a DataFrame into a worksheet, headers included (requires a connection)::

                >>> sheet.write('Scores', df, cells='A1:Z')  # doctest: +SKIP
        """
        response = self.exec(
            'update',
            range=f'{worksheet}!{cells}',
            valueInputOption='RAW',
            body={'values': self.serialize_data(data, **kwargs)},
        )
        self.LOGGER.info(f'Successfully updated range {response["updatedRange"]}')

    @_import_guard
    def batch_write(self, **kwargs: pd.DataFrame) -> None:
        """Write multiple DataFrames to the Google Sheet in a single batch operation.

        Bare worksheet names have a range (and headers/index) computed from each DataFrame's
        shape; explicit `Sheet!A1:...` targets are written as-is.

        Args:
            **kwargs: A mapping from worksheet names or cell ranges to `DataFrame` objects.
        Examples:
            Write two worksheets in one API call (requires a connection)::

                >>> sheet.batch_write(Roster=roster_df, Scores=scores_df)  # doctest: +SKIP
        """
        requests = []
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
            self.LOGGER.info(f'Successfully updated range {resp["updatedRange"]}')

    @_import_guard
    def add_worksheets(self, *args: str, **kwargs: Any) -> None:
        """Add new worksheets to the Google Sheet.

        Args:
            *args: The names of the worksheets to add with default properties.
            **kwargs: A map of properties to set for each worksheet.
        Examples:
            Add plain and customized worksheets together (requires a connection)::

                >>> sheet.add_worksheets(
                ...     'Notes', Wide=dict(gridProperties=dict(columnCount=40)))  # doctest: +SKIP
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

        self.LOGGER.info(f'Created {len(worksheets)} new worksheets in {self.name}')

    # ------------------
    # `&` Styling Helpers
    # ------------------
    @staticmethod
    def hex_color(color: str) -> dict[str, float]:
        """Convert a `#RRGGBB` hexcode into the API's fractional RGB color object.

        Args:
            color: The hexcode, with or without the leading `#`.
        Returns:
            A `{red, green, blue}` dict of 0..1 floats, as Sheets API formatting
            expects.
        Examples:
            Convert a theme hexcode::

                >>> {k: round(v, 4) for k, v in GoogleSheet.hex_color('#5A6169').items()}
                {'red': 0.3529, 'green': 0.3804, 'blue': 0.4118}
        """

        def channel(part: str) -> float:
            return int(part, 16) / 255

        h = color.lstrip('#')
        assert len(h) == 6, f'Expected #RRGGBB, got {color!r}.'
        return dict(red=channel(h[0:2]), green=channel(h[2:4]), blue=channel(h[4:6]))

    @staticmethod
    def repeat_cell(
        sheet_id: int,
        col0: int,
        col1: int,
        row0: int,
        row1: int,
        cell: dict[str, Any],
        fields: str = 'userEnteredFormat',
    ) -> dict[str, Any]:
        """Build a `repeatCell` request applying one cell format over a rectangle.

        All indices are 0-based and half-open (end-exclusive), matching the API.

        Args:
            sheet_id: The worksheet's `sheetId` (not the spreadsheet ID).
            col0: First styled column index.
            col1: One past the last styled column index.
            row0: First styled row index.
            row1: One past the last styled row index.
            cell: The cell payload, e.g. `{'userEnteredFormat': {...}}`.
            fields: The field mask of `cell` to apply.
        Returns:
            The request dict, ready for `batch()`.
        """
        return {
            'repeatCell': {
                'range': {
                    'sheetId': sheet_id,
                    'startColumnIndex': col0,
                    'endColumnIndex': col1,
                    'startRowIndex': row0,
                    'endRowIndex': row1,
                },
                'cell': cell,
                'fields': fields,
            }
        }

    @classmethod
    def set_widths(cls, sheet_id: int, widths: list[int], start: int = 0) -> list[dict[str, Any]]:
        """Build `updateDimensionProperties` requests setting per-column pixel widths.

        Args:
            sheet_id: The worksheet's `sheetId`.
            widths: Pixel widths, one per column from `start`.
            start: The first column index to size.
        Returns:
            One request per column, ready for `batch()`.
        """
        return [
            {
                'updateDimensionProperties': {
                    'range': {
                        'sheetId': sheet_id,
                        'dimension': 'COLUMNS',
                        'startIndex': start + i,
                        'endIndex': start + i + 1,
                    },
                    'properties': {'pixelSize': width},
                    'fields': 'pixelSize',
                }
            }
            for i, width in enumerate(widths)
        ]

    @classmethod
    def add_banding(
        cls,
        sheet_id: int,
        n_cols: int,
        n_rows: int,
        header: str = '',
        first: str = '',
        second: str = '',
    ) -> dict[str, Any]:
        """Build an `addBanding` request with row bands over a rectangle.

        Args:
            sheet_id: The worksheet's `sheetId`.
            n_cols: Number of banded columns.
            n_rows: Number of banded rows (including the header row).
            header: Header band hexcode, or `''` for the theme default.
            first: First band hexcode, or `''` for the theme default.
            second: Second band hexcode, or `''` for the theme default.
        Returns:
            The request dict, ready for `batch()`.
        """
        row_props: dict[str, Any] = {}
        for key, hexcode in (
            ('headerColor', header),
            ('firstBandColor', first),
            ('secondBandColor', second),
        ):
            if hexcode:
                row_props[key] = cls.hex_color(hexcode)
        return {
            'addBanding': {
                'bandedRange': {
                    'range': {
                        'sheetId': sheet_id,
                        'startRowIndex': 0,
                        'endRowIndex': n_rows,
                        'startColumnIndex': 0,
                        'endColumnIndex': n_cols,
                    },
                    'rowProperties': row_props,
                }
            }
        }

    @classmethod
    def gradient_rule(
        cls,
        sheet_id: int,
        col: int,
        row1: int,
        lo: str,
        mid: str,
        hi: str,
        lo_color: str,
        mid_color: str,
        hi_color: str,
        row0: int = 1,
        index: int = 0,
    ) -> dict[str, Any]:
        """Build a 3-point `gradientRule` conditional format for one column.

        Args:
            sheet_id: The worksheet's `sheetId`.
            col: The conditioned column index.
            row1: One past the last conditioned row index.
            lo: The number mapping to the low color.
            mid: The number mapping to the midpoint color.
            hi: The number mapping to the high color.
            lo_color: Low hexcode.
            mid_color: Midpoint hexcode.
            hi_color: High hexcode.
            row0: First conditioned row index.
            index: Insert position among the sheet's conditional format rules.
        Returns:
            The request dict, ready for `batch()`.
        """
        points = (
            ('minpoint', lo, lo_color),
            ('midpoint', mid, mid_color),
            ('maxpoint', hi, hi_color),
        )
        return {
            'addConditionalFormatRule': {
                'index': index,
                'rule': {
                    'ranges': [
                        {
                            'sheetId': sheet_id,
                            'startColumnIndex': col,
                            'endColumnIndex': col + 1,
                            'startRowIndex': row0,
                            'endRowIndex': row1,
                        }
                    ],
                    'gradientRule': {
                        key: {'color': cls.hex_color(color), 'type': 'NUMBER', 'value': str(value)}
                        for key, value, color in points
                    },
                },
            }
        }

    @classmethod
    def text_rule(
        cls,
        sheet_id: int,
        col: int,
        row1: int,
        value: str,
        fg: str = '',
        bg: str = '',
        bold: bool = False,
        row0: int = 1,
        index: int = 0,
    ) -> dict[str, Any]:
        """Build a `TEXT_EQ` boolean conditional format rule for one column.

        Args:
            sheet_id: The worksheet's `sheetId`.
            col: The conditioned column index.
            row1: One past the last conditioned row index.
            value: The exact cell text to match.
            fg: Text color hexcode, or `''` to leave color unset.
            bg: Background hexcode tint, or `''` to leave background unset.
            bold: Whether matched cells render bold.
            row0: First conditioned row index.
            index: Insert position among the sheet's conditional format rules.
        Returns:
            The request dict, ready for `batch()`.
        """
        text_format: dict[str, Any] = {'bold': bold}
        if fg:
            text_format['foregroundColor'] = cls.hex_color(fg)
        cell_format: dict[str, Any] = {'textFormat': text_format}
        if bg:
            cell_format['backgroundColor'] = cls.hex_color(bg)
        return cls._boolean_rule(sheet_id, col, row1, 'TEXT_EQ', [value], cell_format, row0, index)

    @classmethod
    def formula_rule(
        cls,
        sheet_id: int,
        col: int,
        row1: int,
        condition: str,
        fg: str = '',
        row0: int = 1,
        index: int = 0,
    ) -> dict[str, Any]:
        """Build a formula boolean conditional format rule for one column.

        Args:
            sheet_id: The worksheet's `sheetId`.
            col: The conditioned column index.
            row1: One past the last conditioned row index.
            condition: A condition string starting with `=`, used as the rule's
                sole criterion (e.g. `=TODAY()` with condition type
                `NUMBER_LESS_THAN` -- see `formula_condition`).
            fg: Text color hexcode.
            row0: First conditioned row index.
            index: Insert position among the sheet's conditional format rules.
        Returns:
            The request dict, ready for `batch()`.
        """
        cell_format: dict[str, Any] = {'textFormat': {'foregroundColor': cls.hex_color(fg)}}
        parts = condition.split(' ')
        cond_type, cond_values = parts[0], parts[1:]
        return cls._boolean_rule(
            sheet_id, col, row1, cond_type, cond_values, cell_format, row0, index
        )

    @staticmethod
    def formula_condition(cond_type: str, *formulas: str) -> str:
        """Render a condition string for `formula_rule` as `TYPE =f1 =f2 ...`.

        Args:
            cond_type: The API condition type, e.g. `NUMBER_LESS_THAN` or
                `NUMBER_BETWEEN`.
            *formulas: The criterion formulas, each starting with `=`.
        Returns:
            The packed condition string.
        Examples:
            Pack a between-today-and-fortnight condition::

                >>> GoogleSheet.formula_condition('NUMBER_BETWEEN', '=TODAY()', '=TODAY()+14')
                'NUMBER_BETWEEN =TODAY() =TODAY()+14'
        """
        return ' '.join((cond_type, *formulas))

    @classmethod
    def _boolean_rule(
        cls,
        sheet_id: int,
        col: int,
        row1: int,
        cond_type: str,
        cond_values: list[str],
        cell_format: dict[str, Any],
        row0: int,
        index: int,
    ) -> dict[str, Any]:
        """Build a booleanRule request from a condition type and criterion formulas."""
        values = [{'userEnteredValue': v} for v in cond_values]
        return {
            'addConditionalFormatRule': {
                'index': index,
                'rule': {
                    'ranges': [
                        {
                            'sheetId': sheet_id,
                            'startColumnIndex': col,
                            'endColumnIndex': col + 1,
                            'startRowIndex': row0,
                            'endRowIndex': row1,
                        }
                    ],
                    'booleanRule': {
                        'condition': {'type': cond_type, 'values': values},
                        'format': cell_format,
                    },
                },
            }
        }

    @classmethod
    def data_validation(
        cls,
        sheet_id: int,
        col: int,
        row1: int,
        formula: str,
        strict: bool = False,
        row0: int = 1,
    ) -> dict[str, Any]:
        """Build a `setDataValidation` request with a one-of-range dropdown.

        Args:
            sheet_id: The worksheet's `sheetId`.
            col: The validated column index.
            row1: One past the last validated row index.
            formula: A range formula feeding the allowed values, e.g.
                `=meta!$A$2:$A$10`.
            strict: `True` rejects invalid input; `False` (the default) shows a
                warning but accepts it, so pre-existing prose survives until
                the cell is edited.
            row0: First validated row index.
        Returns:
            The request dict, ready for `batch()`.
        """
        return {
            'setDataValidation': {
                'range': {
                    'sheetId': sheet_id,
                    'startColumnIndex': col,
                    'endColumnIndex': col + 1,
                    'startRowIndex': row0,
                    'endRowIndex': row1,
                },
                'rule': {
                    'condition': {
                        'type': 'ONE_OF_RANGE',
                        'values': [{'userEnteredValue': formula}],
                    },
                    'showCustomUi': True,
                    'strict': strict,
                },
            }
        }

    @staticmethod
    def insert_columns(sheet_id: int, at: int, count: int = 1) -> dict[str, Any]:
        """Build an `insertDimension` request inserting blank columns at `at`.

        Args:
            sheet_id: The worksheet's `sheetId`.
            at: The 0-based index the first new column occupies.
            count: How many columns to insert.
        Returns:
            The request dict, ready for `batch()`.
        """
        return {
            'insertDimension': {
                'range': {
                    'sheetId': sheet_id,
                    'dimension': 'COLUMNS',
                    'startIndex': at,
                    'endIndex': at + count,
                },
                'inheritFromBefore': False,
            }
        }

    @classmethod
    def sheet_properties(
        cls,
        sheet_id: int,
        *,
        frozen_rows: int | None = None,
        frozen_cols: int | None = None,
        hide_gridlines: bool | None = None,
        tab_color: str = '',
    ) -> dict[str, Any]:
        """Build an `updateSheetProperties` request for common sheet surfaces.

        Args:
            sheet_id: The worksheet's `sheetId`.
            frozen_rows: Frozen row count, or `None` to leave unchanged.
            frozen_cols: Frozen column count, or `None` to leave unchanged.
            hide_gridlines: `True` hides gridlines, `None` leaves unchanged.
            tab_color: Tab color hexcode, or `''` to leave unchanged.
        Returns:
            The request dict, ready for `batch()`.
        """
        grid_properties: dict[str, Any] = {}
        fields: list[str] = []
        if frozen_rows is not None:
            grid_properties['frozenRowCount'] = frozen_rows
            fields.append('gridProperties.frozenRowCount')
        if frozen_cols is not None:
            grid_properties['frozenColumnCount'] = frozen_cols
            fields.append('gridProperties.frozenColumnCount')
        if hide_gridlines is not None:
            grid_properties['hideGridlines'] = hide_gridlines
            fields.append('gridProperties.hideGridlines')
        properties: dict[str, Any] = {'sheetId': sheet_id, 'gridProperties': grid_properties}
        if tab_color:
            properties['tabColor'] = cls.hex_color(tab_color)
            fields.append('tabColor')
        return {
            'updateSheetProperties': {
                'properties': properties,
                'fields': ','.join(fields),
            }
        }

    @_import_guard
    def batch(self, requests: list[dict[str, Any]], chunk: int = 90) -> list[dict[str, Any]]:
        """Execute styling/structure requests through `batchUpdate`, chunked.

        Args:
            requests: Request dicts from the builders (`repeat_cell`,
                `set_widths`, `gradient_rule`, ...).
            chunk: Requests per API call; bounded to keep responses small.
        Returns:
            The concatenated `replies` from all calls.
        """
        replies: list[dict[str, Any]] = []
        for i in range(0, len(requests), chunk):
            response = self.genexec('batchUpdate', body={'requests': requests[i : i + chunk]})
            replies.extend(response.get('replies', []))
        self.LOGGER.info(f'Executed {len(requests)} requests against {self.name}.')
        return replies


#: Global instance of this class for convenient access.
gsheet = GoogleSheet()
