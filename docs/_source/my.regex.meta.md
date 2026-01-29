---
numbering:
  title: true
---

# `my.regex.meta`: Internal, Purpose-Built Regex Metatypes

```{py:currentmodule} my.regex.meta
```

This subpackage contains a variety of classes (and a few constants!) for representing, analyzing, and modifying regular expressions in a structured manner. As opposed to the internal types within Python's standard `re` library, these types are **not** built to support regex evaluation; instead, they provide a more modern, ergonomic way to work with regular expressions *before* they're evaluated.

These modules are described as "internal" because they were clearly designed with the specific needs of `RegexStore` in mind--namely, optimizing branching expressions (e.g. `a|b`) and debugging complex expressions of any kind--but they are made available in the public API nonetheless. If you extend them, please consider submitting a PR so that others can benefit from your work!

```{toctree}
---
maxdepth: 1
---
my.regex.meta.Tree
my.regex.meta.Regex
my.regex.meta.Atom
my.regex.meta.GroupAtom
my.regex.meta.SetAtom
my.regex.meta.Quantifier
my.regex.meta.GroupKind
my.regex.meta.ParseData
my.regex.meta.meta_patterns
```
