---
numbering:
  title: true
---

# `my.typing`: Vibe Typists

```{py:currentmodule} my.typing
```

This subpackage provides tools for advanced type operations: parsing, checking, matching, coercion,
manipulation, and more, alongside some high-level functional utilities built upon those features.
The vast majority of the logic is implemented within the (mostly-)static class `Typist`.

I may facetiously refer to this "Vibe Typing" throughout these docs because of its original usecase:
coercing the attempts of latent models to output symbolic data, an event that occurs every time a
chatbot or agent calls a tool beyond itself.

One could use this library to add some 'just-in-case' magic to one of the many existing solutions,
but I was personally motivated by the kind of second-level flexibility only possible when working
in a system diffuse with these tools (secret, Free, open-source, or otherwise).

```{toctree}
:maxdepth: 2
typing.Typist
typing.MyType
typing.AutocastModel
typing.cast
typing.check
typing.match
typing.Metatype
```
