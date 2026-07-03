---
numbering:
  title: true
---

# `my.apis`: API Wrappers

```{py:currentmodule} my.apis
```

This subpackage provides convenient interfaces for external services and system resources. It
currently covers three concerns: environment variable management (`Environment`), filesystem path
registration (`Filesystem`), and Google Sheets integration (`GoogleSheet`).

```{toctree}
---
maxdepth: 2
---
apis.Environment
apis.GoogleSheet
```
