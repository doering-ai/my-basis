############
### HEAD ###
############
### STANDARD
from pathlib import Path
from typing import Any
import os

### EXTERNAL
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials as GoogleCredentials
from google_auth_oauthlib.flow import InstalledAppFlow  # type: ignore[import-untyped]
from googleapiclient.discovery import build  # type: ignore[import-untyped]
import logfire as fire
import pandas as pd
import numpy as np

### INTERNAL
from my import ut, typist

############
### DATA ###
############
MY_CREDS = Path(os.environ.get('MY_CREDS', '~/my/.creds')).expanduser().resolve()
MY_CREDS.mkdir(parents=True, exist_ok=True)

MY_CACHE = Path(os.environ.get('MY_CACHE', '~/my/.cache')).expanduser().resolve()
MY_CACHE.mkdir(parents=True, exist_ok=True)

GSHEETS: Any = None


############
### BODY ###
############
def auth_google(scopes: list[str]) -> GoogleCredentials | None:
    assert scopes, 'Must provide at least one scope to authenticate with Google APIs.'
    did_change = False
    gcreds = None
    gcreds_dir = MY_CREDS / 'google'
    gcreds_dir.mkdir(parents=True, exist_ok=True)

    # Load locally-cached creds
    token_file = gcreds_dir / 'google_token.json'
    if token_file.exists():
        gcreds = GoogleCredentials.from_authorized_user_file(token_file.as_posix(), scopes)

    # Refresh token
    if gcreds and gcreds.expired and gcreds.refresh_token:
        try:
            gcreds.refresh(Request())
            did_change = True
        except Exception:
            fire.info("Failed to refresh credentials!")
            gcreds = None

    # Log in
    if gcreds is None:
        creds_file = gcreds_dir / 'google_credentials.json'
        flow = InstalledAppFlow.from_client_secrets_file(creds_file.as_posix(), scopes)
        gcreds = flow.run_local_server(port=0)
        did_change = True

    assert gcreds is not None, "Failed to authenticate with Google Sheets."
    assert gcreds.valid, "Invalid Google credentials."

    # Save the credentials for the next run
    if did_change:
        typist.to_file(gcreds, token_file)

    return gcreds


def connect_to_gsheets() -> None:
    gcreds = auth_google(scopes=["https://www.googleapis.com/auth/spreadsheets"])
    assert gcreds is not None, "Failed to authenticate with Google Sheets."

    global GSHEETS
    GSHEETS = build("sheets", "v4", credentials=gcreds).spreadsheets()
    assert GSHEETS is not None, "Failed to build Google Sheets API."


def index_spreadsheet(sheet: str) -> list[str]:
    """
    Get a list of worksheet names in the given google sheet via the Google Sheets API.

    Args:
        sheet: The ID of the google sheet (from the URL).

    Returns:
        A list of worksheet names.
    """
    assert GSHEETS is not None, "Failed to build Google Sheets API."
    index = GSHEETS.get(spreadsheetId=sheet).execute()
    assert index is not None, "Failed to load Google Sheet from the API."

    names = [info['properties']['title'] for info in index.get("sheets", [])]
    assert names is not None, "Failed to parse Google Sheet."
    return names


def load_spreadsheet(
    sheet: str,
    use_cache: bool | None = None,
    **kwargs: dict,
) -> dict[str, pd.DataFrame]:
    """
    Load the relevant worksheets from the given google sheet via the Google Sheets API.

    Args:
        sheet: The ID of the google sheet (from the URL).
        use_cache: Whether to use cached worksheets if available, or None to prompt.
        **kwargs: Additional arguments to pass to `read_worksheet` for each worksheet.
    """
    # I. Load cache if present
    gcache = MY_CACHE / 'google'
    cache = gcache / sheet
    if use_cache in [True, None] and gcache.exists() and cache.exists():
        if files := list(cache.glob('*.pkl')):
            latest_change = max(file.stat().st_mtime for file in files)
            time_since = ut.posix_since(latest_change)

            if use_cache or ut.confirm(f'Use cached worksheets from {time_since} ago?'):
                fire.info(f"Loading cache for {len(files)} worksheets.")
                return {file.stem: pd.read_pickle(file) for file in files}

    # II. Else, auth with google
    with fire.span('Connecting to google sheets...'):
        connect_to_gsheets()

    # III. Get a list of worksheets
    with fire.span('Loading spreadsheet index...'):
        worksheets = index_spreadsheet(sheet)
        fire.info(f'Found {len(worksheets)} worksheets: {worksheets}\n')

    # IV. Load each individual worksheet
    with fire.span('Loading worksheets...'):
        dataframes = {
            ut.clean_string(name): read_worksheet(sheet, name, **kwargs.get(name, {}))
            for name in worksheets
        }

    # V. Cache and return results
    cache.mkdir(parents=True, exist_ok=True)
    for worksheet, df in dataframes.items():
        df.to_pickle(cache / f"{worksheet}.pkl")

    return dataframes


def read_worksheet(
    sheet: str,
    worksheet: str,
    cells: str = 'A1:Z',
    header_rows: int = 1,
    idx: str = '',
) -> pd.DataFrame:
    """
    Load a single worksheet from the given google sheet via the Google Sheets API.

    Args:
        sheet: The ID of the google sheet (from the URL).
        worksheet: The name (NOT ID) of the worksheet to load.
        cells: The range of cells to load (default 'A1:Z' to load all columns).
        header_rows: The number of header rows, the last of which has the column names (default 1).
        idx: The column to use as the index, if any (default '').

    Returns:
        A pandas DataFrame with the worksheet data.
    """
    assert GSHEETS is not None, "Failed to build Google Sheets API."

    # I. Fetch from google
    cmd = GSHEETS.values().get(spreadsheetId=sheet, range=f"{worksheet}!{cells}")
    values = cmd.execute().get("values", [])

    # II. Form worksheet into a filled dataframe
    df = pd.DataFrame(values[header_rows:], columns=values[header_rows - 1])
    assert df is not None, f"Failed to parse worksheet {worksheet}."

    # III. Validate and fill in blanks
    if idx:
        df.set_index(idx, inplace=True)

    df.replace('', np.nan).ffill()

    return df


def write_worksheet(
    data: pd.DataFrame,
    sheet: str,
    worksheet: str,
    cells: str = 'A1:Z',
    header: bool = True,
    index: bool = True,
):
    assert GSHEETS is not None, "Failed to build Google Sheets API."

    # Convert the dataframe to a plain 2D array
    df = data.reset_index() if index else data.copy()
    values = df.fillna('').astype(str).values.tolist()
    if header:
        values = [df.columns.tolist()] + values

    # Write to google
    cmd = GSHEETS.values().update(
        spreadsheetId=sheet,
        range=f"{worksheet}!{cells}",
        valueInputOption="RAW",
        body={'values': values},
    )
    cmd.execute()

    # Determine if successful
    h, w = data.shape
    fire.info(f"Wrote {h} rows and {w} columns to {sheet[:4]}.../{worksheet}.")
