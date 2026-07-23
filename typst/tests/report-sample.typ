// Full-surface fixture: envelope + theme + callouts + problem-space + math.
// The corpus test compiles this and asserts the <dtm-report> envelope round-trips.
#import "@dtm/basis:0.1.0": *

#show: report.with(
  title: "A Sample House Report",
  agent: "claude",
  date: "2026-07-21",
  genre: "reference",
  tagline: "exercising every @dtm/basis surface",
  extra: (sid: "MEMY-599"),
)

= Introduction

This fixture exercises the house theme, the callouts, and the problem-space trailer.
Body prose sets in Libertinus Serif with a justified measure. A cross-reference to
#link(<sec-math>)[the math section] and a #link("https://typst.app")[link] pick up the accent.

Inline math $a^2 + b^2 = c^2$ and a block:

$ sum_(i=1)^n i = (n (n + 1)) / 2 $

== Callouts

#note[A plain note, default title.]

#tip(title: "Do this")[A tip with a custom title.]

#warning[Mind the frontier.]

#important[This one is load-bearing.]

= Math section <sec-math>

Referenced above. Code renders in the house mono face:

```python
def envelope() -> dict[str, str]:
    return {"schema": "dtm-report/1"}
```

#problem-space(
  (
    (
      label: "Lock the envelope",
      keystone: true,
      children: (
        (label: "Prove the query round-trip"),
        (label: "String-only values"),
      ),
    ),
    (label: "Fan out W1", note: "once conventions freeze"),
  ),
  terminus: none,
)
