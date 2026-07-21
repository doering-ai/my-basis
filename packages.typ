// packages.typ — OPTIONAL blessed @preview re-exports.
//
// These are Typst Universe packages fetched from the network on first use and
// cached under ~/.cache/typst/packages/preview/. They are a LIVE-FETCH dependency,
// so they live here and NOT in lib.typ — the @dtm/basis core must compile offline.
// A document that wants them imports this module explicitly:
//
//   #import "@dtm/basis:0.1.0/packages.typ": codly-init, cetz, fletcher
//
// Pins are deliberate: bump them consciously (mirrors the fleet version-pin canon).
// The set is intentionally small — dogfood and grow it as real reports need it
// (charter answer #3: "seek out the best/latest Typst plugins when the urge strikes").

// cetz — general vector drawing / diagrams (TikZ-analogue). Cached: 0.3.1.
#import "@preview/cetz:0.3.1" as cetz

// codly — nicer code blocks with line numbers + highlighting.
#import "@preview/codly:1.3.0": codly, codly-init

// fletcher — arrow/box diagrams built on cetz (state machines, DAGs).
#import "@preview/fletcher:0.5.5" as fletcher

// glossarium — glossaries / acronym expansion.
#import "@preview/glossarium:0.5.4": (
  gls, glspl, make-glossary, register-glossary,
)
