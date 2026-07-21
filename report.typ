// report.typ — the per-genre report template and its queryable metadata envelope.
//
// Usage in an authored `.typ` report:
//
//   #import "@dtm/basis:0.1.0": *
//   #show: report.with(
//     title: "Findings on X",
//     agent: "claude",
//     date: "2026-07-21",
//     genre: "reference",          // reference | explanation | lesson | instruction
//     tagline: "one-line subtitle", // optional
//   )
//   = First section
//   ...
//
// THE ENVELOPE (load-bearing): the frontmatter substitute Typst lacks. It is a
// *labeled* metadata element — `#metadata((..)) <dtm-report>` — so the collector
// (W1.6) and Nucleus ingest (W2.1) extract it with
//   typst eval 'query(<dtm-report>).first().value' --in <file> --format json
// which returns exactly this one dict, never entangled with callout markers.
// (`typst query <file> "<dtm-report>" --field value` still works but is deprecated
// in 0.15.) Every value is a STRING: content values do not survive extraction.

#import "theme.typ": apply-base, colors, fonts, title-block

// The Diátaxis genre vocabulary the journal store recognizes, SINGULAR — the exact
// values a Markdown report carries in its `genre:` frontmatter (journal/README.md), so
// a `.typ` envelope and a `.md` frontmatter are indistinguishable to search and ingest.
// (The `journal/reports/` *directories* are the plural forms: references/, explanations/…)
#let report-genres = ("reference", "explanation", "lesson", "instruction")

// The envelope schema tag — bump when the envelope's shape changes.
#let envelope-schema = "dtm-report/1"

// report(...) — apply as `#show: report.with(...)`.
#let report(
  title: "",
  agent: none,
  date: none,
  genre: none,
  tagline: none,
  // Extra string key/values folded verbatim into the envelope (e.g. sid, module).
  extra: (:),
  body,
) = {
  // --- The machine-readable envelope: a single labeled element, string-valued. ---
  let envelope = (
    schema: envelope-schema,
    title: title,
  )
  if agent != none { envelope.insert("agent", agent) }
  if date != none { envelope.insert("date", date) }
  if genre != none { envelope.insert("genre", genre) }
  if tagline != none { envelope.insert("tagline", tagline) }
  for (k, v) in extra { envelope.insert(k, v) }

  [#metadata(envelope) <dtm-report>]

  // --- Page + document metadata (visible / PDF properties). ---
  set document(title: title, author: if agent != none { agent } else { () })
  set page(
    paper: "us-letter",
    fill: colors.paper,
    margin: (x: 1.1in, y: 1in),
    numbering: "1",
    footer: context {
      set text(
        font: fonts.mono,
        size: 0.68em,
        tracking: 0.03em,
        fill: colors.muted,
      )
      grid(
        columns: (1fr, auto),
        align: (left, right),
        text(title), counter(page).display("1"),
      )
    },
  )

  // --- Styling + header + body. ---
  show: apply-base
  title-block(
    title: title,
    tagline: tagline,
    agent: agent,
    date: date,
    genre: genre,
  )
  body
}
