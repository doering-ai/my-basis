# RegexStore adoption and DSL

RegexStore earns its dependency when patterns form a vocabulary or grammar. It
adds named reusable definitions, compositional marks, parsed match data, router
trees, and a deadline on public matching paths.

## Start explicit

For a small production grammar, concatenate exactly and compile during startup:

```python
from regex import escape
from my import RegexStore

COMMAND_RGXS = RegexStore.new(
    options=dict(separator='', lazy_load=False),
    verb=(
        '<|>:i',
        r'\b',
        [escape(word) for word in ['publish', 'published', 'publishing']],
        r'\b',
    ),
)

assert COMMAND_RGXS.fullmatch('verb', 'Publishing')
assert not COMMAND_RGXS.fullmatch('verb', 'publisher')
```

Lists otherwise use `r' *'` as their default separator. Set `separator=''` when
composition must be exact.

## Marks

A tuple is `(mark, children)` or `(mark, prefix, children, suffix)`.

- `':'` creates a non-capturing group.
- `'|'` creates an alternation.
- `'|:i'` creates a case-insensitive non-capturing alternation.
- `'<|>'` creates an optimized atomic alternation.
- quantifiers can follow the group mark.

Keep golden behavior tests around optimized alternations: condensation may alter
branch boundaries when a grammar mixes prefixes, suffixes, and optional segments.

## Reuse and captures

```python
from my import RegexStore

TOKEN_RGXS = RegexStore.new(
    options=dict(separator='', lazy_load=False),
    sign=r'[+-]?',
    digits=r'\d+',
    number=r'(?P<value>(?P>sign)(?P>digits)(?:\.(?P>digits))?)',
)

match = TOKEN_RGXS.fullmatch('number', '-22.5')
assert match['value'] == ['-22.5']
assert match.data['digits'] == ['22', '5']
assert match.flat == {'sign': '-', 'digits': '5', 'value': '-22.5'}
```

`MatchData` preserves every named capture as a list through `match[name]` and
`match.data`; `match.flat` selects the last non-empty capture for each name.
`(?P>digits)` is a subroutine invocation: match the named pattern again.
`\g<digits>` is a backreference: match the text captured earlier. With
`force_reinvocations=True` (the default), `(?P=digits)` is normalized to a
subroutine, so write true backreferences as `\g<digits>`.

Reusable flags belong inside the definition, for example `(?i:...)`. Do not depend
on flags attached only to a precompiled pattern when that pattern will be composed
into another definition.

## Router trees

```python
from my import RegexStore

TOKENS = RegexStore.new(options=dict(separator='', lazy_load=False))
TOKENS.define_router_tree(
    'token',
    {
        'number': r'[+-]?\d+(?:\.\d+)?',
        'identifier': r'[\p{L}_][\p{L}\p{N}_-]*',
    },
)

assert TOKENS.route_match('token', '22') == 'number'
assert TOKENS.route_match('token', 'alpha_2') == 'identifier'
assert TOKENS.route_match('token', '+foo') == ''
```

Protect routers with positive, negative, overlap, and near-miss examples. Order is
part of the classification contract.

## Recursive JSON candidate example

Use recursion to find candidates, then validate them with the application's real
schema. Regex finds boundaries; it does not replace JSON validation.

```python
JSON_RGXS = RegexStore.new(
    options=dict(separator='', lazy_load=False),
    _string=r'"(?:\\.|[^"\\])*"',
    _unit=(
        '|:',
        [
            r'(?P>_string)',
            r'\{(?P>_unit)*\}',
            r'\[(?P>_unit)*\]',
            r'[^{}\[\]"]+',
        ],
    ),
    value=('|:', [r'\{(?P>_unit)*\}', r'\[(?P>_unit)*\]']),
)
```

Test nested arrays and objects, escaped quotes, braces inside strings, invalid
candidates before valid ones, empty containers, and adversarially long inputs.

## Review checklist

- Is this a grammar rather than one isolated pattern?
- Are literal vocabularies escaped?
- Are anchors and token boundaries preserved?
- Are flags scoped where reused definitions keep them?
- Is each `(?P>name)` invocation intentional?
- Does any true backreference use `\g<name>`?
- Does matching go through a timeout-enforced public store method?
- Are security-sensitive definitions eagerly compiled?
- Do differential tests cover success, near misses, malformed inputs, and length
  boundaries?
- Does the report show the DSL and explain it in domain language?

Use `RegexDebugger` for atom-level diagnosis. Use optimization only after the
unoptimized grammar is correct and covered.
