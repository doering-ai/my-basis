// lib.typ — the public entrypoint for @dtm/basis.
//
//   #import "@dtm/basis:0.1.0": *
//
// exposes the theme (colors, fonts, apply-base, title-block), the callouts
// (callout + note/tip/important/warning/caution/hint/attention/danger/error),
// the per-genre report template + its envelope (report, report-genres,
// envelope-schema), and the problem-space frontier component.
//
// Blessed @preview re-exports live in the OPTIONAL `packages.typ` (a live-fetch
// dependency), imported explicitly by documents that want them — never from here,
// so the core stays reproducible offline.

#import "theme.typ": (
  accent-of, apply-base, colors, fonts, genre-chip, title-block,
)
#import "callouts.typ": (
  attention, callout, callout-kinds, caution, danger, error, hint, important,
  note, tip, warning,
)
#import "report.typ": envelope-schema, report, report-genres
#import "problem-space.typ": problem-space
