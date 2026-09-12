# `@dtm/basis` — the house Typst package

> Left-rule blocks mark artificial prose; quotations retain their own attribution.

<blockquote class="artificial-prose">

`@dtm/basis` is the fleet's shared Typst import. It provides an authored report with the house theme, callouts, per-genre templates, a queryable metadata envelope, and the problem-space frontier component. It complements [`myform`](https://gitlab.com/doering-ai/libs/myform): `myform` converts existing documents, while this package is imported when authoring a new `.typ` report. The two are deliberately visually aligned so converted and authored reports read as one corpus in the Latent Library.

The package is part of the fleet markdown-to-Typst migration (`MEMY-597`, wave W0.2 / `MEMY-599`).

</blockquote>

## Installation

<blockquote class="artificial-prose">

This local Typst package is independent of the Python package. From this `typst/` directory, choose a development symlink or a copy that won't follow later working-tree edits:

</blockquote>

```sh
./install.sh          # development symlink into the local Typst package tree
./install.sh --copy   # independent release snapshot
```

<blockquote class="artificial-prose">

With either form installed, `typst query` resolves `@dtm/basis` from the local package tree. The Latent Library collector and Nucleus also query the report envelope, so hosts that render or ingest house reports need this package available.

</blockquote>

## Repository and release boundary

<blockquote class="artificial-prose">

The package lives under `typst/` in the `my-basis` repository, but remains independently versioned as `@dtm/basis`. Its source is MIT-licensed under [`LICENSE`](LICENSE); the Python project at repository root remains MPL-2.0, and Python wheels and source distributions explicitly exclude this subtree.

Use `typst-vX.Y.Z` tags for this package. Bare `vX.Y.Z` tags belong to the Python package and may trigger PyPI publication. The package history was imported from `/home/robbd/my/libs/typst-basis` at source head `fc46f3700af5415db0692f30bc955df361638aee`.

</blockquote>

## Use

```typst
#import "@dtm/basis:0.1.0": *

#show: report.with(
  title: "Findings on X",
  agent: "claude",
  date: "2026-07-21",
  genre: "reference", // reference | explanation | lesson | instruction
  tagline: "one-line subtitle", // optional
)

= First section

Body text. #footnote[Ordinary Typst throughout.]

#note[A note callout.]
#warning(title: "Mind this")[A warning with a custom title.]

#problem-space(
  (
    (label: "Lock the envelope", keystone: true, children: (
      (label: "Prove the query round-trip"),
    )),
    (label: "Fan out W1"),
  ),
  terminus: none, // or a sentence when the frontier genuinely ends
)
```

## The envelope

<blockquote class="artificial-prose">

Typst has no YAML frontmatter. `report` emits the envelope as a metadata dictionary labeled `<dtm-report>`. Use strings for its field values so the envelope remains readable outside Typst. Query that label directly; callouts have their own metadata and don't belong in the result.

</blockquote>

```sh
typst eval 'query(<dtm-report>).first().value' --in report.typ --format json
```

<blockquote class="artificial-prose">

`typst query report.typ "<dtm-report>" --field value --one` remains available, but is deprecated in Typst 0.15.

</blockquote>

## Modules

| Module              | Exposes                                                                                                                      |
| ------------------- | ---------------------------------------------------------------------------------------------------------------------------- |
| `theme.typ`         | `colors`, `fonts`, `accent-of`, `apply-base`, `title-block`, `genre-chip`                                                    |
| `callouts.typ`      | `callout`; `note` / `tip` / `important` / `warning` / `caution` / `hint` / `attention` / `danger` / `error`; `callout-kinds` |
| `report.typ`        | `report`, `report-genres`, `envelope-schema`                                                                                 |
| `problem-space.typ` | `problem-space`                                                                                                              |
| `packages.typ`      | Optional blessed `@preview` re-exports; import explicitly because they live-fetch                                            |

<blockquote class="artificial-prose">

`lib.typ` re-exports every core module except `packages.typ`, so the core package compiles offline.

</blockquote>

## Tests

<blockquote class="artificial-prose">

Run the package's self-contained Typst 0.15 gate from this directory. It installs a temporary copy, compiles both fixtures, checks nonempty PDFs, verifies the copied release manifest, and queries the `dtm-report/1` envelope. Corpus retains the downstream integration gate in `tests/test_typst_basis.py`.

</blockquote>

```sh
./test.sh
```
