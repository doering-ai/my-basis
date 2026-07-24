# `@dtm/basis` — the house Typst package

The fleet's shared Typst import: one line gives an authored report the house theme, the callouts, a per-genre template, a queryable metadata envelope, and the problem-space frontier component.
It is the authoring counterpart to [`myform`](../../myform) (the universal `md↔typst` translator): `myform` *converts* existing documents and ships a self-contained callout prelude; `@dtm/basis` is what agents `#import` when they *author* a new `.typ` report.
The two are visually aligned on purpose, so converted and authored reports read as one corpus in the Latent Library.

Part of the fleet markdown→typst migration (`MEMY-597`, wave W0.2 / `MEMY-599`).

## Install

`typst query` resolves `@dtm/basis` from the local package tree, and the Latent Library collector and Nucleus ingest both query the envelope — so this must be installed wherever house reports are rendered or ingested.

```sh
./install.sh          # dev symlink into $XDG_DATA_HOME/typst/packages/dtm/basis/0.1.0
./install.sh --copy   # release snapshot instead of a symlink
```

## Repository and release boundary

This package lives under `typst/` in the `my-basis` repository, but it remains an independently versioned `@dtm/basis` package. Its sources are MIT-licensed under [`LICENSE`](LICENSE); the Python project at repository root remains MPL-2.0. Python wheels and source distributions explicitly exclude this subtree.

Use `typst-vX.Y.Z` tags for this package. Bare `vX.Y.Z` tags belong to the Python package and may trigger PyPI publication. The package history was imported from `/home/robbd/my/libs/typst-basis` at source head `fc46f3700af5415db0692f30bc955df361638aee`.

## Use

```typst
#import "@dtm/basis:0.1.0": *

#show: report.with(
  title: "Findings on X",
  agent: "claude",
  date: "2026-07-21",
  genre: "reference",           // reference | explanation | lesson | instruction
  tagline: "one-line subtitle",  // optional
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
  terminus: none,   // or a sentence when the frontier genuinely ends
)
```

## The envelope

Typst has no YAML frontmatter, so `report` emits the machine-readable envelope as a **labeled** metadata element, string-valued:

```typst
#metadata((schema: "dtm-report/1", title: .., agent: .., date: .., genre: ..)) <dtm-report>
```

Extract exactly it (never entangled with callout markers) with:

```sh
typst eval 'query(<dtm-report>).first().value' --in report.typ --format json
```

(`typst query report.typ "<dtm-report>" --field value --one` still works but is deprecated in Typst 0.15.)

## Modules

| Module              | Exposes                                                                                                       |
| ------------------- | ------------------------------------------------------------------------------------------------------------- |
| `theme.typ`         | `colors`, `fonts`, `accent-of`, `apply-base`, `title-block`, `genre-chip`                                     |
| `callouts.typ`      | `callout` + `note`/`tip`/`important`/`warning`/`caution`/`hint`/`attention`/`danger`/`error`; `callout-kinds` |
| `report.typ`        | `report`, `report-genres`, `envelope-schema`                                                                  |
| `problem-space.typ` | `problem-space`                                                                                               |
| `packages.typ`      | OPTIONAL blessed `@preview` re-exports (live-fetch; import explicitly)                                        |

`lib.typ` re-exports everything except `packages.typ`, so the core compiles offline.

## Tests

Run the package's self-contained Typst 0.15 gate from this directory:

```sh
./test.sh
```

It installs a temporary copy, compiles both fixtures, checks nonempty PDFs, verifies the copied release manifest, and queries the `dtm-report/1` envelope. The Corpus repository retains the downstream integration gate in `tests/test_typst_basis.py`.
