// theme.typ — the house look: palette, fonts, and the base document styling.
//
// Design grounding (policies/design-principles.md): the theme is a *conceptual model*
// made visible (N-02, N-05) with restrained constraint (N-06) — a serif body for
// reading at length, mono kickers for structure, one blue accent, generous measure.
//
// The vibe is lifted from the `odyssey` page (ai/src/pages/odyssey.astro): a warm,
// editorial, Quanta-style register — Charter serif on warm-sand paper, Monaspace-Neon
// kickers/chips, a single Radix-blue accent, airy line-height. Fonts name the odyssey
// faces *first* and fall back to embedded typst faces (Libertinus Serif, DejaVu Sans
// Mono), so a report is odyssey-authentic where those fonts exist and still compiles
// identically on a bare collector/ingest host.
//
// Typst output is a single fixed rendering (light); the Latent Library's furo HTML
// handles dark mode downstream.

// --------------------------------------------------------------------------
// Palette — Radix "sand" warm neutrals + one Radix-blue accent, with muted
// editorial semantic hues (shared with the codex report palette so authored and
// converted reports read as one corpus).
// --------------------------------------------------------------------------
#let colors = (
  brand: rgb("#0090ff"), // Radix blue-9 — the odyssey accent
  link: rgb("#0d74ce"), // Radix blue-11 — link text, contrast-safe on paper
  ink: rgb("#21201c"), // Radix sand-12 — warm near-black body text
  muted: rgb("#60646c"), // odyssey metadata gray — captions, kickers
  rule: rgb("#dad9d6"), // Radix sand-6 — hairlines, borders
  surface: rgb("#f1f0ef"), // Radix sand-3 — subtle panel / code fill
  paper: rgb("#fdfdfc"), // Radix sand-1 — warm page background
  // Admonition accents — muted editorial hues that sit on warm-sand paper.
  note: rgb("#246a8d"), // muted teal-blue
  tip: rgb("#1b7f5c"), // muted green
  hint: rgb("#1b7f5c"),
  important: rgb("#6e56cf"), // muted violet
  warning: rgb("#a66312"), // muted amber
  attention: rgb("#a66312"),
  caution: rgb("#bc4c00"), // muted orange
  danger: rgb("#ae3f43"), // muted red
  error: rgb("#ae3f43"),
  admonition: rgb("#60646c"), // neutral sand
)

// Accent lookup for a callout/genre kind, defaulting to the neutral admonition slate.
#let accent-of(kind) = colors.at(kind, default: colors.admonition)

// --------------------------------------------------------------------------
// Fonts — odyssey faces first, embedded typst faces as reproducible fallbacks.
// The serif carries prose AND headings (editorial register); mono carries code,
// kickers, chips, and metadata. `sans` is kept as a serif alias for back-compat.
// --------------------------------------------------------------------------
#let fonts = (
  body: ("Charter", "Georgia", "Libertinus Serif"), // odyssey serif; Libertinus embedded
  sans: ("Charter", "Georgia", "Libertinus Serif"), // alias → serif (headings are serif here)
  mono: ("Monaspace Neon", "DejaVu Sans Mono", "Liberation Mono"), // code + kickers + chips
  math: "New Computer Modern Math", // embedded
)

// --------------------------------------------------------------------------
// apply-base — the base show-rules every house document shares. Applied via
// `#show: apply-base` or folded into `report` below.
// --------------------------------------------------------------------------
#let apply-base(body) = {
  set text(font: fonts.body, size: 11pt, lang: "en", fill: colors.ink)
  set par(justify: true, leading: 0.8em, spacing: 1.25em)
  show math.equation: set text(font: fonts.math)

  // Headings: serif, editorial — bold, a touch larger; H3 settles to italic.
  show heading: set text(font: fonts.body, weight: "bold", fill: colors.ink)
  show heading.where(level: 1): set text(size: 1.5em)
  show heading.where(level: 2): set text(size: 1.22em)
  show heading.where(level: 3): set text(
    size: 1.05em,
    style: "italic",
    weight: "semibold",
  )

  // Links carry the accent; monospace picks up the code face.
  show link: set text(fill: colors.link)
  show raw: set text(font: fonts.mono, size: 0.9em)
  show raw.where(block: true): it => block(
    width: 100%,
    fill: colors.surface,
    inset: (x: 11pt, y: 9pt),
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
  fill: accent-of(genre).lighten(88%),
  inset: (x: 6pt, y: 2.5pt),
  radius: 3pt,
  text(
    font: fonts.mono,
    size: 0.66em,
    tracking: 0.08em,
    fill: accent-of(genre).darken(10%),
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
  text(font: fonts.body, size: 2.0em, weight: "bold", fill: colors.ink, title)
  if tagline != none {
    linebreak()
    v(0.25em)
    text(
      font: fonts.body,
      size: 1.08em,
      style: "italic",
      fill: colors.muted,
      tagline,
    )
  }
  v(0.55em)
  // metadata kicker line — mono, tracked, muted (the odyssey kicker register).
  set text(font: fonts.mono, size: 0.72em, tracking: 0.04em, fill: colors.muted)
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
  v(0.7em)
}
