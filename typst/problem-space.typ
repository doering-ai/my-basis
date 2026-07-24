// problem-space.typ — the frontier trailer component.
//
// Renders the problem-space trailer that closes a significant report
// (policies/problem_space_trailer.md): nested next-step nodes, a highlighted
// keystone, and an explicit terminus when the frontier genuinely ends.
//
// Node model (arbitrarily nested):
//   (label: "…", note: "…"?, keystone: true?, children: (…)?)
//
// Usage:
//   #problem-space(
//     (
//       (label: "Lock the envelope", keystone: true, children: (
//         (label: "Prove the query round-trip"),
//       )),
//       (label: "Fan out W1"),
//     ),
//     terminus: none,   // or a sentence when there is no further frontier
//   )

#import "theme.typ": colors, fonts

#let _keystone-mark = text(fill: colors.brand, weight: "bold", sym.star.filled)

#let _render-node(node) = {
  let is-key = node.at("keystone", default: false)
  let label = node.at("label", default: "")
  let rendered = if is-key {
    [#_keystone-mark #text(fill: colors.brand, weight: "bold", label)]
  } else {
    [#label]
  }
  let note = node.at("note", default: none)
  if note != none {
    rendered = [#rendered #text(fill: colors.muted, size: 0.9em)[ — #note]]
  }
  let children = node.at("children", default: ())
  if children.len() > 0 {
    [#rendered
      #list(..children.map(_render-node))]
  } else {
    rendered
  }
}

#let problem-space(nodes, terminus: none, title: "Problem space") = {
  v(0.8em)
  block(
    breakable: true,
    {
      if title != none {
        text(
          font: fonts.sans,
          weight: "semibold",
          size: 1.05em,
          fill: colors.ink,
          title,
        )
        v(0.3em)
        line(length: 100%, stroke: 0.5pt + colors.rule)
        v(0.3em)
      }
      list(..nodes.map(_render-node))
      if terminus != none {
        v(0.4em)
        block(
          width: 100%,
          inset: (x: 9pt, y: 7pt),
          radius: 4pt,
          fill: colors.surface,
          stroke: (left: 2.5pt + colors.muted),
          [#text(
              font: fonts.sans,
              weight: "medium",
              fill: colors.muted,
            )[Terminus.] #terminus],
        )
      }
    },
  )
}
