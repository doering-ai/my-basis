// Component fixture: every callout kind + a problem-space with an explicit terminus,
// with no report wrapper (so the raw components compile standalone).
#import "@dtm/basis:0.1.0": *

#for kind in callout-kinds {
  callout(kind: kind)[Callout of kind #raw(kind).]
  v(0.3em)
}

#problem-space(
  (
    (label: "A resolved frontier"),
  ),
  terminus: [nothing further remains here; the thread ends.],
)
