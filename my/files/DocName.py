"""The canonical `creators__year__title` document name, minted and parsed in one place.

A document corpus's filenames are its only index. This module holds the grammar that
names them -- lowercase, `-` inside one semantic sub-unit, `_` between sub-units, `__`
between the three typed slots::

    arendt-h__1958__human-condition
    chomsky-n_pollin-r_et-al__1998__the-common-good
    aristotle__-0350__categories
    uid-arxiv__2025__2501-13956

The grammar and every normalization here are transcribed from the two places that
already implement it: `wikiparse.citations.CitationFactory` (`build_name`,
`name_creators`, `name_year`, `name_title`, `truncate_filename_section`) and the pure
half of `lit/scripts/normalize_slugs.py`. It lives in this package rather than in either
of them because both are applications, and an application may not import another for a
shared primitive (`policies/fleet_dependencies.md` DEP-direction) -- so the primitive
moves down here, beside `ut.clean_string`, which is the root all of it descends from.

**The author slot joins named creators with `_`.** This is the origin's own rule --
`name_creators` returns `ut.clean_string('_'.join(segments))` -- and it is what makes a
compound surname legible: `kauark-leite-p` is *one* person, `gendler-t_hawthorne-j` is
two. Some shelved names `-`-join their second author instead; those predate this module
and stay readable to :meth:`DocName.parse`, which accepts the wider grammar.

**Refusal over guessing.** :meth:`DocName.mint` returns ``None`` rather than invent a
name it cannot support, and the year of a document nobody has triaged is the literal
``'0000'`` -- distinct from ``'undated'``, which asserts that a date was sought and does
not exist. A wrong filename is worse than an honest unknown.

**Two deliberate divergences from wikiparse**, both toward what the shelf already does:

* *Initials, not given names.* `name_creators` builds `smith-jane`; this builds
  `smith-j`, because every shelved edition is initialled (`arendt-h`, `austin-jl`,
  `ansell-hs`) and a name is a sort key before it is a sentence.
* *No prose stopword dropping.* `truncate_filename_section(..., prose=True)` turns
  `A Study of Intense Polymers from Light` into `study-intense-polymers-light`. This
  keeps every internal word, following the newer rule the literature corpus adopted:
  `being-and-time` and `critique-of-pure-reason` are identities, and only a stopword
  left dangling *by a truncation* is detritus.

**The ladder is what keeps a document from being recorded but never shelved.** When the
creators cannot be read, a work that carries an identifier or a publisher is still
nameable, so :meth:`DocName.mint` falls through `uid-<scheme>` and then `site-<host>`
before it gives up. That ladder is `build_name`'s, with one deliberate change: where the
origin spends the *title* slot on the identifier and drops the real title, this keeps the
title and spends only the *creator* slot. The origin needs a dedup key; a shelf needs a
name a reader can find again.
"""

############
### HEAD ###
############
### STANDARD
from __future__ import annotations
from typing import ClassVar, Self
from collections.abc import Container, Iterable

### EXTERNAL
import pydantic as pyd
import regex as re

### INTERNAL
from ..utils import ut

############
### DATA ###
############
#: One semantic sub-unit inside a typed slot: `-` joins the words within it.
SLOT_UNIT: str = r'[a-z0-9]+(?:-[a-z0-9]+)*'

#: One typed slot: `_` delineates the sub-units within it.
SLOT: str = rf'{SLOT_UNIT}(?:_{SLOT_UNIT})*'

#: A signed four-digit year, or the literal `undated`. `0000` is a legal four-digit year
#: and carries the separate meaning documented on :data:`UNTRIAGED`.
YEAR: str = r'-?\d{4}|undated'

#: The whole grammar. Groups: creators, year, title.
SLUG_RGX: re.Pattern[str] = re.compile(rf'({SLOT})__({YEAR})__({SLOT})')

#: Longest one slot may be, in characters (wikiparse `THRESHOLDS['max_name']`).
MAX_SECTION: int = 48

#: A date was sought and genuinely does not exist.
UNDATED: str = 'undated'

#: Nobody has triaged this document's date yet. Not the same claim as :data:`UNDATED`.
UNTRIAGED: str = '0000'

#: Named creators kept before the rest collapse into an `et-al` sub-unit.
MAX_CREATORS: int = 2

#: Leading articles whose removal cannot change a work's title identity on its own.
LEADING_ARTICLES: frozenset[str] = frozenset({'a', 'an', 'the'})

#: Only a stopword left exposed *at a truncation boundary* is detritus. Internal words
#: are identity: `being-and-time` and `art-of-war` keep every word they have.
TAIL_WORDS: frozenset[str] = frozenset(
    {
        'a',
        'an',
        'and',
        'as',
        'at',
        'by',
        'for',
        'from',
        'in',
        'into',
        'of',
        'on',
        'or',
        'the',
        'to',
        'with',
    }
)

#: Surname particles. Their *case* decides where they land: capitalized, a particle is
#: part of the surname proper (`De Cruz` -> `de-cruz`); lowercase, it is the detachable
#: nobiliary form and drops out of the sort name entirely (`de Beauvoir` -> `beauvoir`),
#: which is both the bibliographic rule and what the shelf already does. Either way it
#: never becomes an initial -- `de Beauvoir` must not yield `beauvoir-s-d`.
PARTICLES: frozenset[str] = frozenset(
    {
        'af',
        'al',
        'bin',
        'da',
        'de',
        'del',
        'della',
        'den',
        'der',
        'di',
        'do',
        'dos',
        'du',
        'el',
        'ibn',
        'la',
        'le',
        'mac',
        'mc',
        'st',
        'ten',
        'ter',
        'van',
        'von',
        'zu',
    }
)

#: The same particles as written when they belong to the surname, so the walk that
#: assembles a multi-word surname can test membership without re-casing every word.
PARTICLES_KEPT: frozenset[str] = frozenset(word.capitalize() for word in PARTICLES)

#: `uid_detritus`: characters that are noise inside an identifier, not structure.
_UID_DETRITUS_RGX: re.Pattern[str] = re.compile(r'[.\',"]')

#: Structural separators inside an identifier. Unlike the detritus above these carry the
#: identifier's own shape (`2501.13956`, `10.1145/3597503`), so they become `-` rather
#: than vanishing -- a narrow, deliberate divergence from the origin's `uid_clean`.
_UID_BREAK_RGX: re.Pattern[str] = re.compile(r'[./:\\|]+')

#: A run of digits and letters that can serve as one initial.
_WORD_RGX: re.Pattern[str] = re.compile(r'[^\W\d_]+')


############
### BODY ###
############
# --------
# Slot cleaning
# --------
def uid_clean(text: str) -> str:
    """Strip identifier detritus (dots, quotes, commas) and surrounding quote marks."""
    return ut.strip_quotes(_UID_DETRITUS_RGX.sub('', text))


def clean_section(text: str, max_length: int = MAX_SECTION) -> str:
    """Clean one slot's text and cut it back to the last whole word that fits.

    Never drops an internal article or preposition -- those are title identity. Only a
    stopword left dangling *by the cut* is removed, because it names nothing on its own.

    Punctuation that separated two phrases becomes the `_` sub-unit delimiter, so a slot
    keeps the shape its source had. Cutting a title at its subtitle mark is a different
    act, and belongs to :func:`title_slot`.

    Args:
        text: Raw slot text.
        max_length: Length cap, in characters.
    Returns:
        The cleaned, truncated slot, or `''` when nothing survives.
    Examples:
        Clean and cap a title, cutting back to a whole word::

            >>> from my.files import DocName
            >>> DocName.clean_section('The Structure of Scientific Revolutions')
            'the-structure-of-scientific-revolutions'
            >>> DocName.clean_section('Design for a Brain the Origin of Adaptive', 30)
            'design-for-a-brain-the-origin'

        Punctuation between phrases delimits sub-units::

            >>> DocName.clean_section('Design for a Brain: The Origin of Adaptive', 30)
            'design-for-a-brain_the-origin'
    """
    if not text:
        return ''

    text = ut.clean_string(uid_clean(text))
    if len(text) <= max_length:
        return text

    # I. Cut at the last separator ahead of the cap, unless the cap already lands on one
    result = text[:max_length]
    cutoff = max(result.rfind('_'), result.rfind('-'))
    if text[max_length] not in '_-' and cutoff > 0:
        result = result[:cutoff]

    # II. Drop only the stopwords the cut itself exposed
    words = result.split('-')
    while len(words) > 1 and words[-1] in TAIL_WORDS:
        words.pop()
    return '-'.join(words)


def without_leading_article(title: str) -> str:
    """Remove one identity-neutral leading article, preserving every internal word.

    Examples:
        Only the leading article goes; internal ones are the title's identity::

            >>> from my.files import DocName
            >>> DocName.without_leading_article('the-human-condition')
            'human-condition'
            >>> DocName.without_leading_article('being-and-time')
            'being-and-time'
    """
    words = title.replace('_', '-').split('-')
    if words and words[0] in LEADING_ARTICLES:
        words.pop(0)
    return '-'.join(words)


def is_conservative_title_candidate(established: str, candidate: str) -> bool:
    """Whether `candidate` may replace `established` without changing what work it names.

    A candidate qualifies only when it *is* the established title (modulo one leading
    article) or is a long, distinctive prefix of it. Anything shorter or vaguer would
    rename the work, and a rename that nobody reviewed is a lost document.

    Args:
        established: The title slot the shelf already holds.
        candidate: The title slot some other source proposes.
    Returns:
        Whether the replacement is safe to make automatically.
    """
    settled = without_leading_article(established)
    return bool(candidate) and (
        candidate == settled
        or (
            settled.startswith(f'{candidate}-')
            and len(candidate) >= 16
            and candidate.count('-') >= 2
        )
    )


def restore_internal_title_connectors(established: str, candidate: str) -> str:
    """Put back only the connector words `candidate` supplies between accepted tokens.

    `difference-repetition` beside a `Difference and Repetition` title becomes
    `difference-and-repetition`; it can never acquire a *content* word this way, because
    every addition must be a known connector and every established token must already
    appear in `candidate`, in order.

    Args:
        established: The title slot the shelf already holds.
        candidate: The title slot some other source proposes.
    Returns:
        The restored title, or `established` unchanged when the restoration is unsafe.
    """
    established_tokens = established.replace('_', '-').split('-')
    candidate_tokens = candidate.replace('_', '-').split('-')

    # Every established token must appear in the candidate, in order, or the candidate is
    # describing a different title and nothing may be taken from it.
    positions: list[int] = []
    cursor = 0
    for token in established_tokens:
        try:
            position = candidate_tokens.index(token, cursor)
        except ValueError:
            return established
        positions.append(position)
        cursor = position + 1

    span = candidate_tokens[positions[0] : positions[-1] + 1]
    accepted = {position - positions[0] for position in positions}
    additions = [token for index, token in enumerate(span) if index not in accepted]
    if additions and set(additions) <= TAIL_WORDS:
        return clean_section('-'.join(span))
    return established


# --------
# Slot minting
# --------
def split_person(name: str) -> tuple[str, str]:
    """Split one written name into `(surname, given)`.

    Reads both `Firstname Lastname` and `Lastname, Firstname` orders.

    A particle's own case decides whether it belongs to the surname, which is the
    bibliographic rule and the one the shelf follows: a lowercase particle is detachable
    and drops out of the sort form (`Simone de Beauvoir` files under `beauvoir-s`), while
    a capitalized one is part of the surname proper (`Helen De Cruz` stays `de-cruz-h`).

    Args:
        name: One person's name, as written.
    Returns:
        The surname and given-name halves, either of which may be `''`. A detached
        lowercase particle appears in neither -- it is not part of the sort form.
    """
    text = ut.strip_quotes(name).strip()
    if not text:
        return ('', '')

    # I. A comma states the order outright
    if ',' in text:
        surname, _, given = text.partition(',')
        return (surname.strip(), given.strip())

    # II. Otherwise the surname is the last word, plus any capitalized particles ahead
    #     of it. Lowercase particles are detachable, so the walk stops at the first one
    #     and it is dropped along with everything a `de`/`van` would carry.
    words = text.split()
    if len(words) < 2:
        return (text, '')
    cut = len(words) - 1
    while cut > 1 and words[cut - 1].strip('.') in PARTICLES_KEPT:
        cut -= 1
    given = [word for word in words[:cut] if word.lower().strip('.') not in PARTICLES]
    return (' '.join(words[cut:]), ' '.join(given))


def person_slot(name: str) -> str:
    """One creator as `surname-initials`, or a bare surname when no given name is known.

    Args:
        name: One person's name, as written.
    Returns:
        The sub-unit for this person, or `''` when no surname survives cleaning.
    Examples:
        Name a person in either written order::

            >>> from my.files import DocName
            >>> DocName.person_slot('Hannah Arendt')
            'arendt-h'
            >>> DocName.person_slot('Austin, J. L.')
            'austin-jl'
            >>> DocName.person_slot('Aristotle')
            'aristotle'
    """
    surname, given = split_person(name)
    stem = ut.clean_string(surname)
    if not stem:
        return ''
    marks = ''.join(word[0] for word in _WORD_RGX.findall(ut.clean_string(given)))
    return f'{stem}-{marks}' if marks else stem


def creators_slot(names: Iterable[str], et_al: bool = False, limit: int = MAX_CREATORS) -> str:
    """The creator slot for `names`: up to `limit` people, `_`-joined, then `_et-al`.

    Args:
        names: Creator names, as written, most significant first.
        et_al: Force the `et-al` sub-unit even when `names` was already complete.
        limit: How many named creators the slot holds before the rest collapse.
    Returns:
        The creator slot, or `''` when no name survives cleaning.
    Examples:
        Two creators join with `_`; a third collapses into `et-al`::

            >>> from my.files import DocName
            >>> DocName.creators_slot(['Tamar Gendler', 'John Hawthorne'])
            'gendler-t_hawthorne-j'
            >>> DocName.creators_slot(['Noam Chomsky', 'Robert Pollin', 'C. J. Polychroniou'])
            'chomsky-n_pollin-r_et-al'
    """
    slots = [slot for name in names if (slot := person_slot(name))]
    if not slots:
        return ''
    kept = slots[:limit]
    if et_al or len(slots) > limit:
        kept.append('et-al')
    # The origin caps this slot too (`truncate_filename_section(name_creators())`), so a
    # pair of very long surnames cannot push one slot past the whole name's budget.
    return clean_section('_'.join(kept))


def year_slot(value: int | str | None) -> str:
    """The year slot for `value`: signed and zero-padded to four digits.

    Args:
        value: A year as an integer or string, the literal `'undated'`, or `None`.
    Returns:
        A signed four-digit year, `'undated'`, or `'0000'` when nothing was readable.
    Examples:
        Pad, sign, and pass through the two non-numeric answers::

            >>> from my.files import DocName
            >>> DocName.year_slot(1958), DocName.year_slot(-350), DocName.year_slot(950)
            ('1958', '-0350', '0950')
            >>> DocName.year_slot(None), DocName.year_slot('undated')
            ('0000', 'undated')
    """
    if value is None:
        return UNTRIAGED

    if isinstance(value, str):
        text = value.strip().lower()
        if text == UNDATED:
            return UNDATED
        match = re.search(r'-?\d{1,4}', text)
        if not match:
            return UNTRIAGED
        value = int(match.group())

    sign = '-' if value < 0 else ''
    return f'{sign}{abs(value):04d}'


def uid_slot(scheme: str, value: str) -> str:
    """The creator-slot stand-in for a work identified by `scheme`, e.g. `uid-arxiv`.

    Args:
        scheme: The identifier's namespace (`arxiv`, `doi`, `isbn`, ...).
        value: The identifier itself. Only used to prove one exists.
    Returns:
        The `uid-<scheme>` sub-unit, or `''` when neither half survives cleaning.
    """
    tag = clean_section(scheme)
    return f'uid-{tag}' if tag and uid_handle(value) else ''


def uid_handle(value: str) -> str:
    """One identifier as a slot sub-unit, keeping its internal structure as `-`.

    Args:
        value: The identifier, as written.
    Returns:
        The cleaned handle, or `''` when nothing survives.
    Examples:
        An arXiv id and a DOI keep their shape::

            >>> from my.files import DocName
            >>> DocName.uid_handle('2501.13956')
            '2501-13956'
            >>> DocName.uid_handle('10.1145/3597503')
            '10-1145-3597503'
    """
    return clean_section(_UID_BREAK_RGX.sub('-', value.strip()))


def site_slot(site: str) -> str:
    """The creator-slot stand-in for an author-less work, named by who published it.

    Args:
        site: A publisher, website, or bare domain.
    Returns:
        The `site-<host>` sub-unit, or `''` when nothing survives cleaning.
    Examples:
        A domain keeps its labels; a publisher name is cleaned like any other text::

            >>> from my.files import DocName
            >>> DocName.site_slot('https://example.org/news/x')
            'site-example-org'
            >>> DocName.site_slot('Cambridge University Press')
            'site-cambridge-university-press'
    """
    # A URL arrives here with or without its scheme; the host is what stands in for the
    # missing byline, so everything from the first path separator on is noise. A domain's
    # dots are structure, not detritus, so they hyphenate the way an identifier's do.
    host = uid_handle(re.sub(r'^[a-z]+://', '', site.strip()).split('/', 1)[0])
    return f'site-{host}' if host else ''


def title_slot(title: str, max_length: int = MAX_SECTION) -> str:
    """The title slot for `title`, cut at its first subtitle mark then cleaned.

    Args:
        title: The work's title, as written.
        max_length: Length cap, in characters.
    Returns:
        The cleaned title slot, or `''` when nothing survives.
    Examples:
        A subtitle is dropped at the mark that introduces it::

            >>> from my.files import DocName
            >>> DocName.title_slot('Steps to an Ecology of Mind: Collected Essays')
            'steps-to-an-ecology-of-mind'
    """
    if ': ' in title:
        title = title.split(': ', 1)[0]
    elif '; ' in title:
        title = title.split('; ', 1)[0]
    return clean_section(ut.strip_quotes(title), max_length)


############
### MAIN ###
############
class DocName(pyd.BaseModel):
    """One document's canonical `creators__year__title` name.

    The model is frozen and validates its own grammar, so a `DocName` that exists is a
    name that can be written to disk. Build one with :meth:`mint` from bibliographic
    metadata, or with :meth:`parse` from a name that already exists.

    Examples:
        Mint a name from what a document's front matter yielded::

            >>> from my.files import DocName
            >>> str(DocName.mint(creators=['Hannah Arendt'], year=1958,
            ...                  title='The Human Condition'))
            'arendt-h__1958__the-human-condition'

        Fall through to the identifier when the creators could not be read::

            >>> str(DocName.mint(title='A Survey of Agent Memory', year=2025,
            ...                  uids={'arxiv': '2501.13956'}))
            'uid-arxiv__2025__a-survey-of-agent-memory'

        Parse a name back into its slots::

            >>> DocName.parse('aristotle__-0350__categories').year
            '-0350'
    """

    model_config = pyd.ConfigDict(frozen=True)

    creators: str
    year: str
    title: str

    #: The slot separator, exposed so callers never spell it themselves.
    DELIM: ClassVar[str] = '__'

    # The module's pure helpers, reachable from the class so one import serves everything.
    clean_section = staticmethod(clean_section)
    creators_slot = staticmethod(creators_slot)
    is_conservative_title_candidate = staticmethod(is_conservative_title_candidate)
    person_slot = staticmethod(person_slot)
    restore_internal_title_connectors = staticmethod(restore_internal_title_connectors)
    site_slot = staticmethod(site_slot)
    split_person = staticmethod(split_person)
    title_slot = staticmethod(title_slot)
    uid_handle = staticmethod(uid_handle)
    uid_slot = staticmethod(uid_slot)
    without_leading_article = staticmethod(without_leading_article)
    year_slot = staticmethod(year_slot)

    # -------------------
    # `.` Initial Methods
    # -------------------
    @pyd.model_validator(mode='after')
    def _check_grammar(self) -> Self:
        """Refuse to exist as a name that could not be written to the shelf."""
        if not SLUG_RGX.fullmatch(str(self)):
            raise ValueError(f'not a canonical document name: {str(self)!r}')
        return self

    @classmethod
    def mint(
        cls,
        title: str = '',
        creators: Iterable[str] = (),
        year: int | str | None = None,
        uids: dict[str, str] | None = None,
        site: str = '',
        et_al: bool = False,
    ) -> Self | None:
        """Build the best canonical name the given metadata can support.

        Walks the evidence ladder, best first: named creators, then the work's own
        identifier, then whoever published it. Each rung yields a name a reader can find
        again; only a work with no title and no identifier at all is unnameable.

        Args:
            title: The work's title, as written.
            creators: Creator names, as written, most significant first.
            year: Publication year, `'undated'`, or `None` when untriaged.
            uids: Identifiers by scheme, e.g. `{'arxiv': '2501.13956'}`.
            site: Publisher, website, or bare domain, for an author-less work.
            et_al: Force the `et-al` sub-unit even when `creators` was complete.
        Returns:
            The minted name, or `None` when the metadata names nothing.
        """
        slot_year = year_slot(year)
        slot_title = title_slot(title)
        uids = uids or {}

        # I. Main case: the creators name the work
        if (slot_creators := creators_slot(creators, et_al)) and slot_title:
            return cls(creators=slot_creators, year=slot_year, title=slot_title)

        # II. The work's own identifier stands in for the missing byline. Unlike the
        #     origin, which spends the title slot on the identifier, this keeps the real
        #     title -- a shelf is read by people, and a dedup key is not a name.
        scheme, value = next(iter(sorted(uids.items())), ('', ''))
        if (slot_uid := uid_slot(scheme, value)) and slot_title:
            return cls(creators=slot_uid, year=slot_year, title=slot_title)

        # III. The publisher stands in instead -- the only creator-shaped handle left
        if (slot_site := site_slot(site)) and slot_title:
            return cls(creators=slot_site, year=slot_year, title=slot_title)

        # IV. Last resort: an identifier with no readable title still names one work
        if slot_uid and (handle := uid_handle(value)):
            return cls(creators=slot_uid, year=slot_year, title=handle)

        # V. Nothing here identifies a document. Refuse rather than invent a name.
        return None

    @classmethod
    def parse(cls, text: str) -> Self | None:
        """Read an existing document name, tolerating a path and a file extension.

        Args:
            text: A name, filename, or directory name.
        Returns:
            The parsed name, or `None` when `text` does not obey the grammar.
        """
        stem = text.rsplit('/', 1)[-1]
        # Only a real suffix is dropped: `2501.13956` is a handle, not an extension.
        if '.' in stem and stem.rsplit('.', 1)[-1].isalpha():
            stem = stem.rsplit('.', 1)[0]
        if not (match := SLUG_RGX.fullmatch(stem)):
            return None
        return cls(creators=match.group(1), year=match.group(2), title=match.group(3))

    @staticmethod
    def is_valid(text: str) -> bool:
        """Whether `text` obeys the typed-slot grammar and creator delineation.

        Args:
            text: A candidate name.
        Returns:
            Whether the shelf would accept it.
        Examples:
            The `et-al` sub-unit must be delineated, not hyphenated on::

                >>> from my.files import DocName
                >>> DocName.is_valid('cuneo-n_et-al__2005__the-normative-web')
                True
                >>> DocName.is_valid('cuneo-n-et-al__2005__the-normative-web')
                False
        """
        if not (match := SLUG_RGX.fullmatch(text)):
            return False
        return not match.group(1).endswith(('-et-al', '-etal'))

    # -------------------
    # `+` Primary Methods
    # -------------------
    def __str__(self) -> str:
        return self.DELIM.join((self.creators, self.year, self.title))

    def filename(self, suffix: str = '') -> str:
        """This name as a filename.

        Args:
            suffix: A file extension, with or without its leading dot.
        Returns:
            The name, with `suffix` appended when one was given.
        """
        if not suffix:
            return str(self)
        return f'{self}.{suffix.lstrip(".")}'

    def disambiguated(self, taken: Container[str], suffix: str = '') -> Self:
        """A variant of this name that `taken` does not already hold.

        Two different works can mint one name -- a second edition, a reprint, two papers
        a year apart with one title. The shelf must never silently absorb one into the
        other, so the copy takes an ordinal sub-unit on its title slot:
        `syntactic-structures` becomes `syntactic-structures_2`.

        Args:
            taken: The names already shelved. Membership is tested against
                :meth:`filename`, so pass the same shape you store.
            suffix: The file extension `taken` is keyed by, if any.
        Returns:
            This name when it is free, else the first free ordinal variant.
        """
        if self.filename(suffix) not in taken:
            return self
        # `_` is the sub-unit delimiter, so the ordinal is grammatical, not decoration.
        for ordinal in range(2, 1000):
            # Built through the constructor, not `model_copy`, so the ordinal variant is
            # held to the same grammar as any other name.
            variant = type(self)(
                creators=self.creators, year=self.year, title=f'{self.title}_{ordinal}'
            )
            if variant.filename(suffix) not in taken:
                return variant
        raise ValueError(f'no free variant of {self} within 1000 ordinals')
