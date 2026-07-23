// packages.typ — the blessed @preview pin-list (COPY the lines you need).
//
// These are Typst Universe packages fetched from the network on first use and
// cached under ~/.cache/typst/packages/preview/. They are a LIVE-FETCH dependency,
// so they are kept OUT of lib.typ — the @dtm/basis core must compile offline.
//
// This file is NOT importable as a module. Typst 0.15 cannot subpath-import a
// package file: `#import "@dtm/basis:0.1.0/packages.typ"` fails with
// `0/packages is not a valid patch version` (it reads the subpath as a version).
// So this file is the single, compile-verified reference for the blessed pins —
// copy the exact `@preview` import line(s) you need straight into your document.
//
// Pins are deliberate: bump them consciously (mirrors the fleet version-pin canon)
// and re-verify against the pinned toolchain. The set is intentionally small —
// grow it as real reports need it. Verified to compile on typst 0.15.1.

// cetz — general vector drawing / diagrams (TikZ-analogue). 0.3.1 fails on 0.15.
#import "@preview/cetz:0.3.4" as cetz

// codly — nicer code blocks with line numbers + highlighting.
#import "@preview/codly:1.3.0": codly, codly-init

// fletcher — arrow/box diagrams built on cetz (state machines, DAGs). Needs 0.5.8 on 0.15.
#import "@preview/fletcher:0.5.8" as fletcher

// glossarium — glossaries / acronym expansion.
#import "@preview/glossarium:0.5.4": (
  gls, glspl, make-glossary, register-glossary,
)
