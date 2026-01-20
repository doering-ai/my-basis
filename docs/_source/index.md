# MyBasis: A Python Toolkit

MyBasis is a library built to provide a variety of useful doodads for high-level Python development of all kinds, with a special eye towards ergonomics, Unix-style composability, and thorough documentation & testing.

It's aimed at Python developers of all kinds, but it's especially worth a perusal if you're...

- ...iteratively **modifying text files**, e.g. while setting up a RAG corpus, converting files between formats, or cleaning up a dataset.

- ...convinced Python has accidentally become the best functional language ever released, and thus always on the lookout for ways to write more **readable, concise functional code**.

- ...building AI agents where **"vibe" typing** can save you a few thousand tokens per slightly-mistaken tool call.

- ...looking for a clean, easily-extensible way to interact with **Google Sheets**.

- ...interested in generic **caching mechanisms** in order to satisfy the guilty pleasure of premature optimzation.

- ...looking for some **code snippets** to lift out of this repo directly, saving you an import!

The package is organized into seven subpackages, which are (in rough order from most- to least-general):

```{toctree}
---
maxdepth: 2
---
1. My Utilities </api/my.utils>
2. Type Casting </api/my.typing>
3. Useful Types </api/my.types>
4. Regex Stores </api/my.regex>
5. Local Caches </api/my.caches>
6. API Wrappers </api/my.apis>
7. File Formats </api/my.files>
```
