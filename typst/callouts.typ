// callouts.typ — the house admonitions.
//
// One primitive, `callout(kind, title, body)`, plus friendly aliases. The kind set
// is the full MyST/myform admonition vocabulary, so a *converted* report (myform's
// Typst writer, which inlines its own self-contained prelude) and a *hand-authored*
// report (this package) render as the same visual family: a left-stroked, faintly
// tinted block titled in the kind's accent.
//
// Structural parity with myform: each callout carries an invisible
// `#metadata((kind: "dtm-callout", value: <kind>))` marker so the corpus can census
// callouts across the store. The report *envelope* is a separately-labeled element
// (see report.typ) — never confuse the two at the query layer.

#import "theme.typ": accent-of, colors, fonts

// The canonical MyST/myform admonition kinds this package renders.
#let callout-kinds = (
  "admonition",
  "attention",
  "caution",
  "danger",
  "error",
  "hint",
  "important",
  "note",
  "tip",
  "warning",
)

// callout(kind, title, body) — kind selects the accent; title defaults to the
// capitalized kind; body is the content.
#let callout(kind: "note", title: none, body) = {
  let accent = accent-of(kind)
  let heading = if title == none {
    upper(kind.slice(0, 1)) + kind.slice(1)
  } else { title }
  block(
    width: 100%,
    inset: (x: 11pt, y: 9pt),
    radius: 4pt,
    fill: accent.lighten(92%),
    stroke: (left: 2.5pt + accent),
    {
      // Invisible census marker (parity with myform's callout metadata).
      metadata((kind: "dtm-callout", value: kind))
      text(
        font: fonts.sans,
        weight: "semibold",
        fill: accent.darken(8%),
        heading,
      )
      v(0.35em)
      set text(fill: colors.ink)
      body
    },
  )
}

// Named aliases. The five the charter calls out first, then the rest of the set
// so converted documents using any MyST admonition render identically.
#let note(title: none, body) = callout(kind: "note", title: title, body)
#let tip(title: none, body) = callout(kind: "tip", title: title, body)
#let important(title: none, body) = callout(
  kind: "important",
  title: title,
  body,
)
#let warning(title: none, body) = callout(kind: "warning", title: title, body)
#let caution(title: none, body) = callout(kind: "caution", title: title, body)
#let hint(title: none, body) = callout(kind: "hint", title: title, body)
#let attention(title: none, body) = callout(
  kind: "attention",
  title: title,
  body,
)
#let danger(title: none, body) = callout(kind: "danger", title: title, body)
#let error(title: none, body) = callout(kind: "error", title: title, body)
