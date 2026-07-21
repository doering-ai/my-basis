// theme.typ — the house look: palette, fonts, and the base document styling.
//
// Design grounding (policies/design-principles.md): the theme is a *conceptual model*
// made visible (N-02, N-05) with restrained constraint (N-06) — one accent, a serif
// body for reading at length, a sans for structure, generous measure. It harmonizes
// with the furo palette the Latent Library already serves, so a report reads the same
// whether you meet it as compiled PDF/SVG or as furo HTML.
//
// Typst output is a single fixed rendering, so only the *light* furo palette applies
// here; furo's own HTML handles dark mode downstream.

// --------------------------------------------------------------------------
// Palette — furo-harmonized (see furo.css: brand #0a4bff, content #2757dd).
// --------------------------------------------------------------------------
#let colors = (
  brand: rgb("#0a4bff"), // furo --color-brand-primary (light)
  link: rgb("#2757dd"), // furo --color-brand-content (light)
  ink: rgb("#131416"), // primary text
  muted: rgb("#5b5f66"), // secondary text, captions, metadata
  rule: rgb("#d7dae0"), // hairlines, borders
  surface: rgb("#f5f6f8"), // subtle panel / code fill
  // Admonition accents — the conventional furo/GitHub hues, text-contrast-safe.
  note: rgb("#0a4bff"),
  tip: rgb("#1a7f37"),
  hint: rgb("#1a7f37"),
  important: rgb("#8250df"),
  warning: rgb("#9a6700"),
  attention: rgb("#9a6700"),
  caution: rgb("#bc4c00"),
  danger: rgb("#cf222e"),
  error: rgb("#b30000"),
  admonition: rgb("#57606a"),
)

// Accent lookup for a callout/genre kind, defaulting to the neutral admonition slate.
#let accent-of(kind) = colors.at(kind, default: colors.admonition)

// --------------------------------------------------------------------------
// Fonts — embedded-first with system fallbacks, so a report compiles the same
// on any host (the collector/ingest hosts included).
// --------------------------------------------------------------------------
#let fonts = (
  body: "Libertinus Serif", // embedded in typst
  sans: ("Noto Sans", "Liberation Sans", "Libertinus Serif"), // headings, labels; embedded-serif fallback keeps it reproducible on bare hosts
  mono: ("DejaVu Sans Mono", "Liberation Mono"), // code
  math: "New Computer Modern Math", // embedded
)

// --------------------------------------------------------------------------
// apply-base — the base show-rules every house document shares. Applied via
// `#show: apply-base` or folded into `report` below.
// --------------------------------------------------------------------------
#let apply-base(body) = {
  set text(font: fonts.body, size: 11pt, lang: "en", fill: colors.ink)
  set par(justify: true, leading: 0.72em, spacing: 1.15em)
  show math.equation: set text(font: fonts.math)

  // Headings: sans, tight, with a hairline settling the top-level ones.
  show heading: set text(font: fonts.sans, weight: "semibold")
  show heading.where(level: 1): set text(size: 1.4em)
  show heading.where(level: 2): set text(size: 1.18em)
  show heading.where(level: 3): set text(size: 1.02em, style: "italic")

  // Links carry the accent; monospace picks up the code face.
  show link: set text(fill: colors.link)
  show raw: set text(font: fonts.mono, size: 0.92em)
  show raw.where(block: true): it => block(
    width: 100%,
    fill: colors.surface,
    inset: (x: 10pt, y: 8pt),
    radius: 4pt,
    stroke: 0.5pt + colors.rule,
    it,
  )

  body
}

// --------------------------------------------------------------------------
// title-block — the report header: title, optional tagline, and a metadata line
// (agent · date · genre chip). Purely presentational; the machine-readable copy
// is the labeled envelope emitted by `report`.
// --------------------------------------------------------------------------
#let genre-chip(genre) = box(
  fill: accent-of(genre).lighten(84%),
  inset: (x: 6pt, y: 2pt),
  radius: 3pt,
  text(
    font: fonts.sans,
    size: 0.72em,
    fill: accent-of(genre).darken(12%),
    weight: "medium",
    upper(genre),
  ),
)

#let title-block(
  title: "",
  tagline: none,
  agent: none,
  date: none,
  genre: none,
) = {
  set align(left)
  text(font: fonts.sans, size: 1.9em, weight: "bold", fill: colors.ink, title)
  if tagline != none {
    linebreak()
    v(0.2em)
    text(font: fonts.sans, size: 1.05em, fill: colors.muted, tagline)
  }
  v(0.5em)
  // metadata line
  set text(font: fonts.sans, size: 0.85em, fill: colors.muted)
  let bits = ()
  if agent != none {
    bits.push(text(fill: colors.ink, weight: "medium", agent))
  }
  if date != none { bits.push(date) }
  bits.join([ · ])
  if genre != none {
    h(0.6em)
    genre-chip(genre)
  }
  v(0.4em)
  line(length: 100%, stroke: 0.75pt + colors.rule)
  v(0.6em)
}
