# APIs

> Left-rule blocks mark artificial prose; quotations retain their own attribution.

<blockquote class="artificial-prose">

The `my.apis` package gives scripts named interfaces to environment variables, filesystem conventions, and Google Sheets. The first two stay local; Sheets needs OAuth and a network connection. Install them through the [parent package](../../README.md#installation), with the `google` extra for Sheets.

</blockquote>

## Environment variables

<blockquote class="artificial-prose">

`Environment` loads `.env` values, snapshots the process environment at module import, and exposes the result through the `env` singleton. Attribute access, item access, and `get()` return strings; `paths` expands variables and user directories; `flags` turns approved truthy strings and integer strings into integer flags. Names must be uppercase and may contain digits and underscores.

The snapshot is cached, so changing `os.environ` later is not the same operation as changing `env`. Use `env.set()` (or assignment through the singleton) when a running process needs a new value; the setter clears the relevant cached conversions. `$VAR` and `${VAR}` references are interpolated when a value is read.

</blockquote>

```python
from my.apis import env

env.set('DEMO_GREETING', 'hello world')
assert env.DEMO_GREETING == 'hello world'
assert env.get('DEMO_MISSING', 'fallback') == 'fallback'
assert env['DEMO_UNSET'] == ''

env.set('DEMO_WORKERS', '4')
assert env.flags.DEMO_WORKERS == 4
```

## Filesystem paths

<blockquote class="artificial-prose">

`Filesystem` is a Pydantic path registry. Its default instance is exported as `fs`, `FS`, and `PATHS`; it carries platform directories such as `home`, `config`, `cache`, and `data`, plus workspace paths derived from `MY`, `MY_CREDS`, `MY_CORPUS`, `MY_LOCAL`, `MY_LOGS`, and `MY_MODELS`. The class also provides path predicates, project-root discovery, regexes for project files, and path formatting without requiring a particular instance.

</blockquote>

```python
from pathlib import Path
from my.apis import PATHS, fs

assert PATHS is fs
assert fs.home == Path.home()
```

## Google Sheets

<blockquote class="artificial-prose">

`GoogleSheet` is a singleton wrapper around Google Sheets API v4. Its methods are guarded by the optional `[google]` extra, which supplies the Google client libraries and pandas. `connect()` takes a sheet ID, performs the OAuth browser flow when no cached token exists, and records the sheet name and worksheet order. `read()` and `batch_read()` return DataFrames; `write()` and `batch_write()` send DataFrames back through A1-style ranges.

Authentication stores credentials and refreshed tokens under the configured credentials directory without encryption. Treat that directory as sensitive local state. The class has no useful offline connection shortcut, so examples that call `connect()`, `read()`, or `write()` require the extra, credentials, and an external Google service.

</blockquote>

```python
import pandas as pd
from my.apis import GoogleSheet

frame = pd.DataFrame({'name': ['ada', 'bob'], 'score': [92, 85]})
values = GoogleSheet.serialize_data(frame)
assert values == [['name', 'score'], ['ada', '92'], ['bob', '85']]
```
