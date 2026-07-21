# Extended Regex Syntax in Python

This file provides a concise reference for [Matthew Barnett's `regex` package](https://github.com/mrabarnett/mrab-regex), a popular extension of [the standard `re` module](https://docs.python.org/3/library/re.html) that adds desperately-needed regex features (both long-awaited and brand-new).

Some of the additions -- say, better support for emojis and non-roman script -- likely seem arcane to the typical regex user, but I just can't stress enough how powerful this package really is:

- Normally-standard regex features such as [unicode properties](#unicode) and [POSIX classes](#posix) greatly improve readability -- both for your colleagues and your agents!

- Features like [subroutines](#subroutines), [repeated matches](#repeated-matches), and [fuzzy matching](#fuzzy-matching) make regex a feasible solution for whole new *classes* of problems.

- [Optimization syntax](#optimization) can improve your complex pattern's performance by *multiple orders of magnitude* with just a few characters.

...and on and on!

This document started as a simple reorganization of Matthew's fantastic `README.md`, but I have since added some brief elaborations, cross-references, & links to [https://regular-expressions.info](https://www.regular-expressions.info) in order to make it more useful to both beginners and experts.
Any allusions to "we" refer to Matthew and his fellow maintainers.

If you're new to regex in general, I recommend you start by reading [python's quick tutorial](https://docs.python.org/3/howto/regex.html), skimming [regular-expression.info's much more in-depth tutorials](https://www.regular-expressions.info), and/or consulting python's [documentation for the `re` module](https://docs.python.org/3/library/re.html) directly.
**For completeness, I have included brief quotes from the `re` documentation to set the stage for many of the extensions -- look out for "See Also" notes.**

## Flags

_([regular-expressions.info lesson](https://www.regular-expressions.info/modifiers.html))_

```{admonition} [Basic Syntax](https://docs.python.org/3/library/re.html#flags)
:class: hint
See Python's standard-library `re` documentation for the basic, global flag syntax; the sections below cover the scoped and extended flags added by the `regex` module.
```

### Scoped Flags

Scoped flags can apply to only part of a pattern and can be turned on or off.

#### Encoding

##### `(?u)` UNICODE
The default encoding of a regex string, matching everything according to international Unicode standards.

##### `(?a)` ASCII
Makes `\w`, `\W`, `\b`, `\B`, `\d`, `\D`, `\s` and `\S` match only ASCII characters.

##### `(?L)` LOCALE
Makes `\w`, `\W`, `\b`, `\B`, `\d`, `\D`, `\s` and `\S` match according to the current locale settings.

```{caution}
This flag is intended for legacy code and has limited support.
We recommended you use `UNICODE` instead.
```

#### Case

##### `(?i)` IGNORECASE
Upper and lower case alphabet characters are matched as if they were identical.

##### `(?f)` FULLCASE
When combined with `(?i)`, enables "full" [case-folding](https://www.w3.org/TR/charmod-norm/#definitionCaseFolding) of Unicode text, which is critical if dealing with non-romance languages.

The flag is off by default in V0, and on by default in V1.

```python
regex.match(r"(?iV1)strasse", "stra\N{LATIN SMALL LETTER SHARP S}e").span() # -> (0, 6)
regex.match(r"(?iV1)stra\N{LATIN SMALL LETTER SHARP S}e", "STRASSE").span() # -> (0, 7)
```

#### Whitespace

##### `(?m)` MULTILINE
_([regular-expressions.info lesson](https://www.regular-expressions.info/anchors.html))_

The `^` and `$` literals now match the beginnings and ends of lines, rather than of the whole string/file.

##### `(?s)` DOTALL
_([regular-expressions.info lesson](https://www.regular-expressions.info/dot.html))_

The catch-all literal `.` now also catches line separators.

##### `(?x)` VERBOSE (i.e. Extended)
_([regular-expressions.info lesson](https://www.regular-expressions.info/freespacing.html))_

Ignores all raw whitespace characters in the following pattern, allowing the user to include whitespace between components for clarity.
Also allows comments, which begin with an "#" and continue until the end of the line.

To match whitespace in an extended expression, wrap it in a character set (e.g. ` ?` -> `[ ]?`).

##### `(?w)` WORD
Changes the definition of a 'word boundary' (`\b`/`\B`) to that of a default Unicode word boundary, a better choice for a variety of non-romance languages.

It also affects line separators (and, in turn, `(?s)` and `(?m)`):

- *Without* this flag, the only line separator is `\n` (`\x0A`),
- *With* this flag, `\x0D\x0A`, `\x0A`, `\x0B`, `\x0C` and `\x0D` are valid line separators, plus `\x85`, `\u2028` and `\u2029` when working with Unicode.

### Global Flags

Global flags apply to the entire pattern and can only be turned on -- if these patterns are present anywhere in a given expression, they apply to the whole thing.
**They cannot be disabled.**

#### General

##### `(?p)` Posix
Enables POSIX (leftmost longest) matching.

Note that it will take longer to find matches because when it finds a match at a certain position, it won't return that immediately, but will keep looking to see if there's another longer match there.

```python
regex.search(r'Mr|Mrs', 'Mrs') # -> Mr
regex.search(r'(?p)Mr|Mrs', 'Mrs') # -> Mrs

regex.search(r'one(self)?(selfsufficient)?', 'oneselfsufficient') # -> oneself
regex.search(r'(?p)one(self)?(selfsufficient)?', 'oneselfsufficient') # -> oneselfsufficient
```

##### `(?r)` Reverse
Enables reverse matching (from the end of the string to the beginning).

```python
regex.findall(r".", "abc") # -> ['a', 'b', 'c']
regex.findall(r"(?r).", "abc") # -> ['c', 'b', 'a']
```

Note that the result of a reverse search is not necessarily the reverse of a forward search:

```python
regex.findall(r"..", "abcde") # -> ['ab', 'cd']
regex.findall(r"(?r)..", "abcde") # -> ['de', 'bc']
```

#### Version

##### `(?V0)` Version0
Enables version 0 behaviour (old behaviour, compatible with the re module).

##### `(?V1)` Version1
Enables version 1 behaviour (new behaviour, possibly different from the re module).

#### Fuzzy Match Modes

##### `(?b)` Best Match
Enables [fuzzy matching](#fuzzy-matching) search for the best match instead of the next match.

##### `(?e)` Enhance Match
Enables [fuzzy matching](#fuzzy-matching) to attempt to improve the fit of the next match that it finds.

## Sets

### Simple vs. Expanded Sets

In Version 0, only simple sets are supported.
For example, the pattern `[[a-z]--[aeiou]]` is mangled and interpreted as:

- Set containing a literal "\[" and the letters "a" to "z"
- Literal "--"
- Set containing letters "a", "e", "i", "o", "u"
- Literal "\]"

In version 1, the same pattern (`[[a-z]--[aeiou]]`) is a single set that uses a **set operator** to match all the lowercase letters from `a` to `z` *except* for the vowels (`a`, `e`, `i`, `o`, `u`).

### Set operators

_([regular-expressions.info lesson 1](https://www.regular-expressions.info/charclasssubtract.html), [lesson 2](https://www.regular-expressions.info/charclassintersect.html))_

Version 1's set operators allow a set (`[...]`) to be composed of smaller sets.
The operators, in order of increasing precedence, are:

| Syntax | Name                 | Boolean | Example                                                        |
| ------ | -------------------- | ------- | -------------------------------------------------------------- |
| `\|\|` | Union                | OR      | `[\w\|\|[:punct:]]` matches word and punctuation characters.   |
| `~~`   | Symmetric Difference | XOR     | `[\w~~[:punct:]]` matches words or punctuation, but *not* `_`. |
| `&&`   | Intersection         | AND     | `[\w&&[:punct:]]` matches *only* `_`.                          |
| `--`   | Difference           | SUB     | `[\w--[:punct:]]` matches all word characters *except* `_`.    |

```{note}
Implicit union, ie, simple juxtaposition like in `[ab]`, has the highest precedence.
Thus, `[ab&&cd]` is the same as `[[a||b]&&[c||d]]`.
```

**Examples:**

```python
r'[ab]' # Matches 'a' or 'b'
r'[a-z]' # Matches all lowercase letters (from 'a' to 'z')
r'[[a-z]--[qw]]' # Set containing 'a' .. 'z', but not 'q' or 'w'
r'[a-z--qw]' # Same as above
r'[\p{L}--QW]' # Set containing all letters except 'Q' and 'W'
r'[\p{N}--[0-9]]' # Set containing all numbers except '0' .. '9'
r'[\p{ASCII}&&\p{Letter}]' # Set containing all characters which are ASCII and letter
```

## Groups

_([regular-expressions.info lesson](https://www.regular-expressions.info/brackets.html))_

### Subroutines

_([regular-expressions.info lesson](https://www.regular-expressions.info/subroutine.html))_

All unnamed capturing groups (`(...)`) are assigned a group number, starting from 1.
Groups with the same group name will have the same group number, and groups with a different group name will have a different group number.

The same name can be used by more than one group, with later captures 'overwriting' earlier captures.
All the captures of the group will be available from the `captures` method of the match object.

#### Substituting & Invoking Subroutines

Subroutines are useful for two things:

1. ["Substitution"/"Backreferencing"](https://www.regular-expressions.info/backref.html) of their results: the exact text that the subroutine last matched will be sought out again.
   The quintessential usecase is matching quoted text: `(["\'])(\w+)(\1)`.

2. ["Invocation"](https://www.regular-expressions.info/subroutine.html) of their pattern: the subroutine itself is *re-run* at the current location, entirely separate from any previous uses.
   Like functions do for regular imperative programming languages, subroutines are *so* incredibly useful that it's impossible to pick any one quintessential usecase -- composition, recursion, and more are all possible.

Although the former is supported by `re`, the latter requires the full `regex` package.
Many different syntaxes are used across different languages, so for convenience, here is a table clarifying exactly which syntaxes are supported by `regex` for each of these functions:

| Group Type | Action Type  | Supported                            | Unsupported                                                              |
| ---------- | ------------ | ------------------------------------ | ------------------------------------------------------------------------ |
| Numbered   | Definition   | `(...)`                              |                                                                          |
| Numbered   | Substitution | `\1`, `\g<1>`, `(?P=1)`              |                                                                          |
| Numbered   | Invocation   | `(?1)`, `(?R)`                       | `(?-1)`, `(?+1)`                                                         |
| Named      | Definition   | `(?P<name>...)`                      | `(?<name>...)`, `(?P'name'...)`, `(?P"name"...)`                         |
| Named      | Substitution | `(?P=name)`, `\g<name>`              | `\k<name>`, `\k'name'`, `\k{name}`, `\g{name}`, `(?<name>)`, `(?'name')` |
| Named      | Invocation   | `(?&name)`, `(?P>name)`, `(?P&name)` |                                                                          |

When substituting, the result of the *most recent* invocation is used; sadly, [relative backreferences](https://www.regular-expressions.info/backrefrel.html) are not (yet?) supported.
To get around this, wrap your subroutine with a new name (e.g. `(?P<important_quote>(?P>quote))`) for the calls whose results you want to substitute later on.

Note that you can only invoke a group if there is only one unique group with that name -- else, an `"ambiguous group reference"` exception will be raised.

```python
# Basic backreference
regex.match(r"(Tarzan|Jane) loves (?1)", "Tarzan loves Jane").groups() # -> ('Tarzan',)
regex.match(r"(Tarzan|Jane) loves (?1)", "Jane loves Tarzan").groups() # -> ('Jane',)

# Recursive
m = regex.search(r"(\w)(?:(?R)|(\w?))\1", "kayak")
m.group(0, 1, 2) # -> ('kayak', 'k', None)

# By number
regex.match(r'(["\'])(\w+)(\g<1>)', '"abc\' "def"') # -> "def"
regex.match(r'(?P<quote>["\'])(\w+)(\g<1>)', "'abc\" 'def'") # -> 'def'

# By name
regex.match(r'(?P<quote>["\'])(\w+)(\g<quote>)', '"abc\' "def"') # -> "def"
regex.match(r'(?P<quote>["\'])(\w+)(?P=quote)', "'abc\" 'def'") # -> 'def'
```

#### Predefined Subroutines (`(?(DEFINE)...)`)

This special group can be placed at the start of a complex pattern to define subroutines that can be invoked later on in the pattern, but that will not themselves be matched against the string.
The normal rules for numbering groups still apply.

```{caution}
If you define a subroutine that shares the name `DEFINE`, this section will break.
```

```python
regex.search(r'(?(DEFINE)(?P<quant>\d+)(?P<item>\w+))(?&quant) (?&item)', '5 elephants') # -> 5 elephants
```

### Conditional Groups (`(?(1)then|else)`)

_([regular-expressions.info lesson](https://www.regular-expressions.info/conditional.html))_

#### Lookarounds in Conditionals

The test of a conditional pattern can be a lookaround:

```python
regex.match(r'(?(?=\d)\d+|\w+)', '123abc') # -> 123
regex.match(r'(?(?=\d)\d+|\w+)', 'abc123') # -> abc123
```

This is not quite the same as putting a lookaround in the first branch of a pair of alternatives:

```python
regex.match(r'(?:(?=\d)\d+\b|\w+)', '123abc') # -> 123abc
regex.match(r'(?(?=\d)\d+\b|\w+)', '123abc') # -> None
```

In the first example, the lookaround matched, but the remainder of the first branch failed to match, and so the second branch was attempted, whereas in the second example, the lookaround matched, and the first branch failed to match, but the second branch was **not** attempted.

### Branch Reset Groups (`(?|...)`)

_([regular-expressions.info lesson](https://www.regular-expressions.info/branchreset.html))_

The special "branch reset" group syntax (e.g. `(?|(first)|(second))`) allows group numbers to be reused across different branches (the given example has only group `1`).
If groups have different group names then they will still have different group numbers.

Group numbers will be reused across the alternatives, but groups with different names will have different group numbers.

In the regex `(\s+)(?|(?P<foo>[A-Z]+)|(\w+) (?P<foo>[0-9]+)` there are 2 groups:

- `(\s+)` is group 1.
- `(?P<foo>[A-Z]+)` is group 2, also called "foo".
- `(\w+)` is group 2 because of the branch reset.
- `(?P<foo>[0-9]+)` is group 2 because it's called "foo".

```python
# Note that there is only one group:
regex.match(r"(?|(first)|(second))", "first").groups() # -> ('first',)
regex.match(r"(?|(first)|(second))", "second").groups() # -> ('second',)
```

### Variable-length lookbehind (`(?<=^.*)`)

_([regular-expressions.info lesson](https://www.regular-expressions.info/lookbehind.html))_

A lookbehind can match a variable-length string.

## Other Literals

(unicode)=
### Unicode Properties (`\p{property}`)

_([regular-expressions.info lesson](https://www.regular-expressions.info/unicode.html))_

Unicode properties allow you to more flexibly match non-standard characters, and as such are highly recommended for production applications.
For example, `[A-Z]` will not match `Ö` as expected, but `[\p{Lu}]` and `[[:upper:]]` will.

Four syntaxes are accepted:

1. `\p{value}` matches characters *with* the given property.
2. `\P{value}` matches characters *without* the given property.
3. `\p{property=value}` matches characters whose property `property` *does* have value `value`.
4. `\P{property=value}` matches characters whose property `property` *does not* have value `value`.

There are four types of Unicode properties, which are checked in order:

1. [`General_Category`](https://www.regular-expressions.info/unicodecategory.html) properties describe all sorts of arbitrary information (e.g. Letter, Mark, Number, Punctuation, Symbol, Separator, Other)
2. [`Script`](https://www.regular-expressions.info/unicodescript.html) properties describe which real-life writing system the character belongs to (e.g. Latin, Cyrillic, Han).
3. [`Block`](https://www.regular-expressions.info/unicodeblock.html) properties describe which of the (somewhat-arbitrary) [Unicode Blocks](https://www.regular-expressions.info/refunicodeblock.html) the character was published within (e.g. Basic Latin, Greek and Coptic, CJK Unified Ideographs).
4. Finally, all other binary properties are checked.

A short form starting with `Is` indicates a script or binary property (e.g. `\p{IsLatin}` or `\p{IsAlphabetic}`), while a short form starting with `In` indicates a block property (e.g. `\p{InBasicLatin}`).

In addition to the usual properties, you can also use:

- `\p{Horiz_Space}`/`\p{H}` matches horizontal whitespace.
- `\p{Vert_Space}`/`\p{V}` matches vertical whitespace.

(posix)=
### POSIX Character Classes (`[[:class:]]`)

_([regular-expressions.info lesson](https://www.regular-expressions.info/posixbrackets.html))_

[POSIX character classes](https://www.regular-expressions.info/posixbrackets.html#class) are supported, e.g. `[[:alpha:]]` (matches alphabet characters) and its inverse `[[:^alpha:]]`.

These are normally treated as an alternative form of `\p{...}`, except for `alnum`, `digit`, `punct` and `xdigit`, whose definitions are different from those of Unicode:

|    POSIX Class | Equivalent Unicode Property |
| -------------: | --------------------------- |
|  `[[:alnum:]]` | `\p{posix_alnum}`           |
|  `[[:digit:]]` | `\p{posix_digit}`           |
|  `[[:punct:]]` | `\p{posix_punct}`           |
| `[[:xdigit:]]` | `\p{posix_xdigit}`          |

### Search Anchors (`\G`)

_([regular-expressions.info lesson](https://www.regular-expressions.info/continue.html))_

The [search anchor](https://www.regular-expressions.info/continue.html) matches at the position where each search started/continued from.

```python
# Can be used to find contiguous matches:
regex.findall(r"\w{2}", "abcd ef") # -> ['ab', 'cd', 'ef'], vs.
regex.findall(r"\G\w{2}", "abcd ef") # -> ['ab', 'cd']

# Or in negative variable-length lookbehinds to limit how far back the lookbehind goes
regex.findall(r"(?<!X.*)\w+", "aXa bXb") # -> ['aXa']
regex.findall(r"(?<!\G.*X.*)\w+", "aXa bXb") # -> ['aXa', 'bXb']
```

### Word boundaries (`\m\M\b\B`)

_([regular-expressions.info lesson](https://www.regular-expressions.info/wordboundaries.html))_

`\m` matches at the start of a word, and `\M` matches at the end of a word.

The definition of a 'word' character (`\w`) has also been expanded to conform to the Unicode specification at http://www.unicode.org/reports/tr29 -- see [regular-expressions.info](https://www.regular-expressions.info/unicodeboundaries.html)'s discussion for details.

### Named characters (`\N{name}`)

Named characters are supported.
Note that only those known by Python's Unicode database will be recognised.

### A single grapheme (`\X`)

_([regular-expressions.info lesson](https://www.regular-expressions.info/unicodechars.html))_

The grapheme matcher is supported.
It conforms to the Unicode specification at `http://www.unicode.org/reports/tr29/`.

## Optimization

### Atomic grouping `(?>...)`

_([regular-expressions.info lesson](https://www.regular-expressions.info/atomic.html))_

If the following pattern subsequently fails, then the subpattern as a whole will fail.

### Possessive quantifiers (`.*+`)

_([regular-expressions.info lesson](https://www.regular-expressions.info/possessive.html))_

`(?:...)?+` ; `(?:...)*+` ; `(?:...)++` ; `(?:...){min,max}+`

The subpattern is matched up to 'max' times.
If the following pattern subsequently fails, then all the repeated subpatterns will fail as a whole.
For example, `(?:...)++` is equivalent to `(?>(?:...)+)`.

### Backtracking Control Verbs (`(*VERB)`)

_([regular-expressions.info lesson](https://www.regular-expressions.info/verb.html))_

We support 3 of [the 7 control verbs](https://www.regular-expressions.info/refverb.html) (excluding `ACCEPT`, `COMMIT`, `MARK`, and `THEN`):

1. `(*PRUNE)` discards the backtracking info up to that point.
   When used in an atomic group or a lookaround, it won't affect the enclosing pattern.

2. `(*SKIP)` is similar to `(*PRUNE)`, except that it also sets where in the text the next attempt to match will start.
   When used in an atomic group or a lookaround, it won't affect the enclosing pattern.

3. `(*FAIL)`/`(*F)` causes immediate backtracking.

### Keep (`\K`)

_([regular-expressions.info lesson](https://www.regular-expressions.info/keep.html))_

Keeps the part of the entire match after the position where `\K` occurred; the part before it is discarded.
It does not affect what groups return.

```python
m = regex.search(r'(\w\w\K\w\w\w)', 'abcdef')
m[0] # -> cde
m[1] # -> abcde

m = regex.search(r'(?r)(\w\w\K\w\w\w)', 'abcdef')
m[0] # -> bc
m[1] # -> bcdef
```

### Named Lists (`\L<name>`)

There are occasions where you may want to include a list (actually, a set) of options in a regex.

One way is to build the pattern like this:

```python
p = regex.compile(r"first|second|third|fourth|fifth")
```

...but if the list is large, parsing the resulting regex can take considerable time, and care must also be taken that the strings are properly escaped and properly ordered, for example, "cats" before "cat".

The new alternative is to use a named list:

```python
option_set = ["first", "second", "third", "fourth", "fifth"]
p = regex.compile(r"\L<options>", options=option_set)
```

The order of the items is irrelevant, they are treated as a set.
The named lists are available as the `.named_lists` attribute of the pattern object:

```python
print(p.named_lists)
# -> {'options': frozenset({'third', 'first', 'fifth', 'fourth', 'second'})}
```

If there are any unused keyword arguments, `ValueError` will be raised unless you tell it otherwise:

```python

option_set = ["first", "second", "third", "fourth", "fifth"]
p = regex.compile(r"\L<options>", options=option_set, other_options=[])
# -> ValueError: unused keyword argument 'other_options'
```

## Python API

### Environment

- Python 2 is not supported.
- This module is targeted at CPython.
- Threading is supported **IF** strings don't change during matching.
- This module supports Unicode 17.0.0 and full Unicode case-folding.

### Repeated Matches

#### Captures & Spans

A match object has additional methods which return information on all the successful matches of a repeated group.
These methods are:

| Method                     | Description                                                         | Singular Counterpart    |
| -------------------------- | ------------------------------------------------------------------- | ----------------------- |
| `.captures([group1, ...])` | The strings matched for one group, or a list of lists for multiple. | `.group([group1, ...])` |
| `.starts([group])`         | The start positions for this group.                                 | `.start([group])`       |
| `.ends([group])`           | The end positions for this group.                                   | `.end([group])`         |
| `.spans([group])`          | The spans for this group.                                           | `.span([group])`        |
| `.allcaptures`             | All the captures of all the groups.                                 | N/A                     |
| `.allspans`                | All the spans of the all captures of all the groups.                | N/A                     |

```python
m = regex.search(r"(\w{3})+", "123456789")
m.group(1) # -> '789'
m.captures(1) # -> ['123', '456', '789']
m.start(1) # -> 6
m.starts(1) # -> [0, 3, 6]
m.end(1) # -> 9
m.ends(1) # -> [3, 6, 9]
m.span(1) # -> (6, 9)
m.spans(1) # -> [(0, 3), (3, 6), (6, 9)]

m = regex.match(r"(?:(?P<word>\w+) (?P<digits>\d+)\n)+", "one 1\ntwo 2\nthree 3\n")
m.allcaptures() # -> (['one 1\ntwo 2\nthree 3\n'], ['one', 'two', 'three'], ['1', '2', '3'])
m.allspans() # -> ([(0, 20)], [(0, 3), (6, 9), (12, 17)], [(4, 5), (10, 11), (18, 19)])
```

#### Capture Mappings

`capturesdict` returns a dict of the named groups and lists of all the captures of those groups.
It is a combination of `groupdict` and `captures`:

- `groupdict` returns a dict of the named groups and the last capture of those groups.
- `captures` returns a list of all the captures of a group

```python
m = regex.match(r'(?:(?P<word>\w+) (?P<digits>\d+)\n)+', "one 1\ntwo 2\nthree 3\n")
m.groupdict() # -> {'word': 'three', 'digits': '3'}
m.captures("word") # -> ['one', 'two', 'three']
m.captures("digits") # -> ['1', '2', '3']
m.capturesdict() # -> {'word': ['one', 'two', 'three'], 'digits': ['1', '2', '3']}
```

Group names can be duplicated:

```python
# ---------------
# OPTIONAL GROUPS
# ---------------
# Both groups capture, the second capture 'overwriting' the first.
m = regex.match(r"(?P<item>\w+)? or (?P<item>\w+)?", "first or second")
m.group("item") # -> 'second'
m.captures("item") # -> ['first', 'second']

# Only the second group captures.
m = regex.match(r"(?P<item>\w+)? or (?P<item>\w+)?", " or second")
m.group("item") # -> 'second'
m.captures("item") # -> ['second']

# Only the first group captures.
m = regex.match(r"(?P<item>\w+)? or (?P<item>\w+)?", "first or ")
m.group("item") # -> 'first'
m.captures("item") # -> ['first']

# ----------------
# MANDATORY GROUPS
# ----------------
# Both groups capture, the second capture 'overwriting' the first.
m = regex.match(r"(?P<item>\w\*) or (?P<item>\w\*)?", "first or second")
m.group("item") # -> 'second'
m.captures("item") # -> ['first', 'second']

# Again, both groups capture, the second capture 'overwriting' the first.
m = regex.match(r"(?P<item>\w\*) or (?P<item>\w\*)", " or second")
m.group("item") # -> 'second'
m.captures("item") # -> ['', 'second']

# And yet again, both groups capture, the second capture 'overwriting' the first.
m = regex.match(r"(?P<item>\w\*) or (?P<item>\w\*)", "first or ")
m.group("item") # -> ''
m.captures("item") # -> ['first', '']
```

#### Match Subscripting (`match[0]`)

Match objects now allow access to their results via subscripting and slicing:

```python
m = regex.search(r"(?P<before>.*?)(?P<num>\d+)(?P<after>.*)", "pqr123stu")
print(m["before"]) # -> pqr
print(len(m)) # -> 4
print(m[:]) # -> ('pqr123stu', 'pqr', '123', 'stu')
```

You can also use subscripting to get the captures of a repeated group for expandf and subf:

```python

m = regex.match(r'(\w)+', 'abc')
m.expandf('{1}') # -> c
m.expandf('{1[0]} {1[1]} {1[2]}') # -> a b c
m.expandf('{1[-1]} {1[-2]} {1[-3]}') # -> c b a'

m = regex.match(r'(?P<letter>\w)+', 'abc')
m.expandf('{letter}') # -> c
m.expandf('{letter[0]} {letter[1]} {letter[2]}') # -> a b c
m.expandf('{letter[-1]} {letter[-2]} {letter[-3]}') # -> c b a
```

### New Functions

#### `splititer()`

`regex.splititer` has been added.
It's a generator equivalent of `regex.split`.

#### `fullmatch()`

`fullmatch` behaves like `match`, except that it must match all of the string.

```python

print(regex.fullmatch(r"abc", "abc").span()) # -> (0, 3)
print(regex.fullmatch(r"abc", "abcx")) # -> None
print(regex.fullmatch(r"abc", "abcx", endpos=3).span()) # -> (0, 3)
print(regex.fullmatch(r"abc", "xabcy", pos=1, endpos=4).span()) # -> (1, 4)

regex.match(r"a.*?", "abcd").group(0) # -> 'a'
regex.fullmatch(r"a.*?", "abcd").group(0) # -> 'abcd'
```

#### `subf()` & `subfn()`

`subf` and `subfn` are alternatives to `sub` and `subn` respectively.
When passed a replacement string, they treat it as a format string.

```python

regex.subf(r"(\w+) (\w+)", "{0} => {2} {1}", "foo bar") # -> 'foo bar => bar foo'
regex.subf(r"(?P<word1>\w+) (?P<word2>\w+)", "{word2} {word1}", "foo bar") # -> 'bar foo'
```

#### `expandf()`

`expandf` is an alternative to `expand`.
When passed a replacement string, it treats it as a format string.

```python
m = regex.match(r"(\w+) (\w+)", "foo bar")
m.expandf("{0} => {2} {1}") # -> 'foo bar => bar foo'

m = regex.match(r"(?P<word1>\w+) (?P<word2>\w+)", "foo bar")
m.expandf("{word2} {word1}") # -> 'bar foo'
```

#### `detach_string()`

A match object contains a reference to the string that was searched, via its `string` attribute.
The `detach_string` method will 'detach' that string, making it available for garbage collection, which might save valuable memory if that string is very large.

```python
m = regex.search(r"\w+", "Hello world")
print(m.group()) # -> Hello
print(m.string) # -> Hello world

m.detach_string()
print(m.group()) # -> Hello
print(m.string) # -> None
```

### New Arguments

#### Partial Matches

A partial match is one that matches up to the end of string, but that string has been truncated and you want to know whether a complete match could be possible if the string had not been truncated.

Partial matches are supported by `match`, `search`, `fullmatch` and `finditer` with the `partial` keyword argument.

Match objects have a `partial` attribute, which is `True` if it's a partial match.

For example, if you wanted a user to enter a 4-digit number and check it character by character as it was being entered:

```python
pattern = regex.compile(r'\d{4}')

# Initially, nothing has been entered:
print(pattern.fullmatch('', partial=True))
# -> <regex.Match object; span=(0, 0), match='', partial=True>
# (An empty string is OK, but it's only a partial match.)

# The user enters a letter:
print(pattern.fullmatch('a', partial=True))
# -> None
# (It'll never match.)

# The user deletes that and enters a digit:
print(pattern.fullmatch('1', partial=True))
# -> <regex.Match object; span=(0, 1), match='1', partial=True>
# (It matches this far, but it's only a partial match.)

# The user enters 2 more digits:
print(pattern.fullmatch('123', partial=True))
# -> <regex.Match object; span=(0, 3), match='123', partial=True>
# (It matches this far, but it's only a partial match.)

# The user enters another digit:
print(pattern.fullmatch('1234', partial=True))
# -> <regex.Match object; span=(0, 4), match='1234'>
# (It's a complete match.)

# If the user enters another digit:
print(pattern.fullmatch('12345', partial=True))
# -> None
# (It's no longer a match.)

pattern.match('123', partial=True).partial # -> True
pattern.match('1233', partial=True).partial # -> False
```

#### Special Escapes

regex.escape has an additional keyword parameter `special_only`.
When True, only 'special' regex characters, such as '?', are escaped.

```python
regex.escape("foo!?", special_only=False) # -> 'foo\!\?'
regex.escape("foo!?", special_only=True) # -> 'foo!\?'

regex.escape("foo bar!?", literal_spaces=False) # -> 'foo\ bar!\?'
regex.escape("foo bar!?", literal_spaces=True) # -> 'foo bar!\?'
```

#### Boundaries

`regex.sub` and `regex.subn` support 'pos' and 'endpos' arguments.

#### Overlaps

`regex.findall` and `regex.finditer` support an 'overlapped' argument which permits overlapped matches.

#### Flags

`regex.split`, `regex.sub` and `regex.subn` support a 'flags' argument.

#### Timeouts

The matching methods and functions support timeouts.
The timeout (in seconds) applies to the entire operation:

```python
from time import sleep

def fast_replace(m):
    return 'X'

def slow_replace(m):
    sleep(0.5)
    return 'X'

regex.sub(r'[a-z]', fast_replace, 'abcde', timeout=2) # -> 'XXXXX'
regex.sub(r'[a-z]', slow_replace, 'abcde', timeout=2) # -> TimeoutError: regex timed out
```

## Fuzzy Matching

Regex usually attempts an exact match, but sometimes an approximate, or "fuzzy", match is needed, for those cases where the text being searched may contain errors in the form of inserted, deleted or substituted characters.

### Basics

A fuzzy regex specifies A) which types of errors are permitted, and, optionally, B) either the minimum and maximum or only the maximum permitted number of each type.
The 3 types of error are: Insertion (`i`), Deletion (`d`), Substitution (`s`), or any (`e`).
You can also use "\<" instead of "\<=" if you want an exclusive minimum or maximum.
You cannot specify only a minimum.

The fuzziness of a regex item is specified between `{` and `}` after the item:

- `foo` match "foo" exactly
- `(?:foo){i}` match "foo", permitting insertions
- `(?:foo){d}` match "foo", permitting deletions
- `(?:foo){s}` match "foo", permitting substitutions
- `(?:foo){i,s}` match "foo", permitting insertions and substitutions
- `(?:foo){e}` match "foo", permitting errors

If a certain type of error is specified, then any type not specified will **not** be permitted:

- `(...){d<=3}` permit at most 3 deletions, but no other types
- `(...){i<=1,s<=2}` permit at most 1 insertion and at most 2 substitutions, but no deletions
- `(...){1<=e<=3}` permit at least 1 and at most 3 errors
- `(...){i<3,d<=2,e<4}` permit at most 2 insertions, at most 2 deletions, at most 3 errors in total, but no substitutions

### Costs & Budgets

It's also possible to state the costs of each type of error and the maximum permitted total cost:

- `(...){2i+2d+1s<=4}` each insertion costs 2, each deletion costs 2, each substitution costs 1, the total cost must not exceed 4
- `(...){i<=1,d<=1,s<=1,2i+2d+1s<=4}` at most 1 insertion, at most 1 deletion, at most 1 substitution; each insertion costs 2, each deletion costs 2, each substitution costs 1, the total cost must not exceed 4

### Tests

You can add a test to perform on a character that's substituted or inserted.

**Examples:**

- `(...){s<=2:[a-z]}` at most 2 substitutions, which must be in the character set `[a-z]`.
- `(...){s<=2,i<=3:\d}` at most 2 substitutions, at most 3 insertions, which must be digits.

### Flags

By default, fuzzy matching searches for the first match that meets the given constraints.
The `ENHANCEMATCH` flag will cause it to attempt to improve the fit (i.e. reduce the number of errors) of the match that it has found.
The `BESTMATCH` flag will make it search for the best match instead.

**Examples:**

- `regex.search("(dog){e}", "cat and dog")[1]` returns `"cat"` because that matches `"dog"` with 3 errors (an unlimited number of errors is permitted).
- `regex.search("(dog){e<=1}", "cat and dog")[1]` returns `" dog"` (with a leading space) because that matches `"dog"` with 1 error, which is within the limit.
- `regex.search("(?e)(dog){e<=1}", "cat and dog")[1]` returns `"dog"` (without a leading space) because the fuzzy search matches `" dog"` with 1 error, which is within the limit, and the `(?e)` then it attempts a better fit.

In the first two examples there are perfect matches later in the string, but in neither case is it the first possible match.

The match object has an attribute `fuzzy_counts` which gives the total number of substitutions, insertions and deletions:

```python
# A 'raw' fuzzy match:
regex.fullmatch(r"(?:cats|cat){e<=1}", "cat").fuzzy_counts # -> (0, 0, 1)
# 0 substitutions, 0 insertions, 1 deletion.

# A better match might be possible if the ENHANCEMATCH flag used:
regex.fullmatch(r"(?e)(?:cats|cat){e<=1}", "cat").fuzzy_counts # -> (0, 0, 0)
# 0 substitutions, 0 insertions, 0 deletions.
```

The match object also has an attribute `fuzzy_changes` which gives a tuple of the positions of the substitutions, insertions and deletions:

```python
m = regex.search('(fuu){i<=2,d<=2,e<=5}', 'anaconda foo bar')
# -> <regex.Match object; span=(7, 10), match='a f', fuzzy_counts=(0, 2, 2)>
m.fuzzy_changes # -> ([], [7, 8], [10, 11])
```

What this means is that if the matched part of the string had been:

```python
'anacondfuuoo bar'
```

...it would've been an exact match.

However, there were insertions at positions 7 and 8:

```python
'anaconda fuuoo bar'
#       ^^
```

...and deletions at positions 10 and 11:

```python
'anaconda f~~oo bar'
#          ^^
```

So the actual string was:

```python
'anaconda foo bar'
```

## Known Issues / Complexities

### `*` operator not working correctly with sub()

Sometimes it's not clear how zero-width matches should be handled.
For example, should `.*` match 0 characters directly after matching >0 characters?

```python
regex.sub('.*', 'x', 'test') # -> xx
regex.sub('.*?', '|', 'test') # -> |||||||||
```
