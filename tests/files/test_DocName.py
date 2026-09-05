############
### HEAD ###
############
### STANDARD
from collections.abc import Iterable

### EXTERNAL
import pydantic as pyd
import pytest as pyt

### INTERNAL
from my.files import DocName
from ..conftest import boolmap


############
### DATA ###
############
#: Shelved names, verbatim, covering every shape the corpus actually holds: a bare
#: mononym, initials of one and two letters, a BCE year, a compound surname, a `-`-joined
#: creator pair, and the `_et-al` sub-unit.
SHELVED: tuple[str, ...] = (
    'adler__1911__individual-psychology',
    'alfarabi__0950__book-of-dialectic',
    'ansell-hs-kovacs-ia__2005__unveiling-universal-aspects-cellular-anatomy',
    'arendt-h__1958__human-condition',
    'aristotle__-0350__categories',
    'austin-jl__1962__how-to-do-things-with-words',
    'brundage_et-al__2018__malicious-use-of-artificial-intelligence',
    'chomsky-n-pollin-r_et-al__1998__the-common-good',
    'kauark-leite-p__2010__transcendental-philosophy',
    'tzu-s__-0500__art-of-war',
    'wittgenstein-l-perez-i_et-al__2009__philosophical-investigations',
)


############
### BODY ###
############
class TestDocName:
    # -------------------
    # `.` Initial Methods
    # -------------------
    @pyt.mark.parametrize(
        'name, expected',
        [
            # Given-name first
            ('Hannah Arendt', 'arendt-h'),
            ('Marvin L. Minsky', 'minsky-ml'),
            ('Johannes Diderik van der Waals', 'waals-jd'),
            # Surname first, stated by the comma
            ('Austin, J. L.', 'austin-jl'),
            ('Ansell, H. S.', 'ansell-hs'),
            ('Papert, Seymour A.', 'papert-sa'),
            # Mononyms carry no initial
            ('Aristotle', 'aristotle'),
            ('Al-Farabi', 'al-farabi'),
            # A compound surname is one unit, and its hyphen is not a delimiter
            ('Patricia Kauark-Leite', 'kauark-leite-p'),
            # Particle case decides ownership: lowercase detaches, capitalized stays
            ('Simone de Beauvoir', 'beauvoir-s'),
            ('Constantin von Economo', 'economo-c'),
            ('Helen De Cruz', 'de-cruz-h'),
            # Diacritics fold rather than mangle
            ('Kurt Gödel', 'godel-k'),
            ('Henri Poincaré', 'poincare-h'),
            # Nothing nameable
            ('', ''),
            ('   ', ''),
        ],
    )
    def test_person_slot(self, name: str, expected: str):
        assert DocName.person_slot(name) == expected

    @pyt.mark.parametrize(
        'names, et_al, expected',
        [
            # One and two creators are named outright
            (['Hannah Arendt'], False, 'arendt-h'),
            (['Tamar Gendler', 'John Hawthorne'], False, 'gendler-t_hawthorne-j'),
            # A third collapses the tail into its own sub-unit
            (
                ['Noam Chomsky', 'Robert Pollin', 'C. J. Polychroniou'],
                False,
                'chomsky-n_pollin-r_et-al',
            ),
            # `et_al` forces the sub-unit onto an already-complete list
            (['Miles Brundage'], True, 'brundage-m_et-al'),
            # Unnameable creators drop out rather than becoming empty sub-units
            (['', 'Hannah Arendt'], False, 'arendt-h'),
            ([], False, ''),
        ],
    )
    def test_creators_slot(self, names: list[str], et_al: bool, expected: str):
        assert DocName.creators_slot(names, et_al) == expected

    @pyt.mark.parametrize(
        'value, expected',
        [
            # Four digits, signed and zero-padded
            (1958, '1958'),
            (950, '0950'),
            (-350, '-0350'),
            (-500, '-0500'),
            ('2025', '2025'),
            # The two non-numeric answers, which mean different things
            (None, '0000'),
            ('undated', 'undated'),
            ('UNDATED', 'undated'),
            # A year read out of freeform text
            ('c. 1265', '1265'),
            ('published 1972 by Chandler', '1972'),
            # Nothing readable is untriaged, never a guess
            ('', '0000'),
            ('n.d.', '0000'),
        ],
    )
    def test_year_slot(self, value: int | str | None, expected: str):
        assert DocName.year_slot(value) == expected

    @pyt.mark.parametrize(
        'title, expected',
        [
            # A subtitle is dropped at the mark that introduces it
            ('Steps to an Ecology of Mind: Collected Essays', 'steps-to-an-ecology-of-mind'),
            ('Sense and Sensibilia; A Reconstruction', 'sense-and-sensibilia'),
            # Internal articles and prepositions are identity, never dropped
            ('The Art of War', 'the-art-of-war'),
            ('Being and Time', 'being-and-time'),
            ('Critique of Pure Reason', 'critique-of-pure-reason'),
            # Quotes and emphasis are stripped; diacritics fold
            ('"Difference et Repetition"', 'difference-et-repetition'),
            # Nothing to name
            ('', ''),
        ],
    )
    def test_title_slot(self, title: str, expected: str):
        assert DocName.title_slot(title) == expected

    @pyt.mark.parametrize(
        'text, max_length, expected',
        [
            # Under the cap, nothing is cut
            ('Human Condition', 48, 'human-condition'),
            # Over it, the cut falls back to a whole word
            (
                'Design for a Brain the Origin of Adaptive Behaviour',
                30,
                'design-for-a-brain-the-origin',
            ),
            # A stopword the cut itself exposed is detritus and goes
            ('The Sensory Order an Inquiry into The', 34, 'the-sensory-order-an-inquiry'),
            ('', 48, ''),
        ],
    )
    def test_clean_section(self, text: str, max_length: int, expected: str):
        result = DocName.clean_section(text, max_length)
        assert result == expected
        assert len(result) <= max_length

    def test_clean_section__caps_at_the_house_threshold(self):
        """Every minted slot fits wikiparse's 48-character `max_name` threshold."""
        long_title = 'On the Electrodynamics of Moving Bodies and Their Relative Simultaneity'
        assert len(DocName.title_slot(long_title)) <= 48

    # -------------------
    # `+` Primary Methods
    # -------------------
    @pyt.mark.parametrize('slug', SHELVED)
    def test_is_valid__accepts_every_shelved_shape(self, slug: str):
        assert DocName.is_valid(slug)

    @pyt.mark.parametrize(
        'text, valid',
        boolmap(
            true=[
                'arendt-h__1958__human-condition',
                'aristotle__-0350__categories',
                'hayek-f__undated__sensory-order',
                'lenin-v__0000__what-is-to-be-done',
                'uid-arxiv__2025__2501-13956',
                'site-example-org__2024__some-press-release',
            ],
            false=[
                # `et-al` is its own sub-unit, never hyphenated onto a surname
                'cuneo-n-et-al__2005__the-normative-web',
                'brundage-etal__2018__malicious-use',
                # Wrong slot count
                'arendt-h__1958',
                'arendt-h__1958__human__condition',
                # Year is not four digits, or not a year
                'arendt-h__58__human-condition',
                'arendt-h__19582__human-condition',
                'arendt-h__nineteen__human-condition',
                # Case, whitespace, and empty slots
                'Arendt-H__1958__human-condition',
                'arendt h__1958__human-condition',
                '__1958__human-condition',
                'arendt-h__1958__',
                # Separators may not double up inside a slot
                'arendt--h__1958__human-condition',
                'arendt-h__1958__human--condition',
                '',
            ],
        ),
    )
    def test_is_valid(self, text: str, valid: bool):
        assert DocName.is_valid(text) is valid

    @pyt.mark.parametrize('slug', SHELVED)
    def test_parse__round_trips_every_shelved_name(self, slug: str):
        parsed = DocName.parse(slug)
        assert parsed is not None
        assert str(parsed) == slug

    @pyt.mark.parametrize(
        'text, expected',
        [
            # A bare name, a filename, and a path all name the same document
            ('arendt-h__1958__human-condition', 'arendt-h__1958__human-condition'),
            ('arendt-h__1958__human-condition.pdf', 'arendt-h__1958__human-condition'),
            ('/x/y/arendt-h__1958__human-condition.epub', 'arendt-h__1958__human-condition'),
            # A trailing identifier is a handle, not an extension
            ('uid-arxiv__2025__2501-13956', 'uid-arxiv__2025__2501-13956'),
            # Not a name at all
            ('garbage', None),
            ('delineation.py', None),
            ('', None),
        ],
    )
    def test_parse(self, text: str, expected: str | None):
        parsed = DocName.parse(text)
        assert (None if parsed is None else str(parsed)) == expected

    def test_parse__slots_are_addressable(self):
        parsed = DocName.parse('aristotle__-0350__categories')
        assert parsed is not None
        assert (parsed.creators, parsed.year, parsed.title) == ('aristotle', '-0350', 'categories')

    @pyt.mark.parametrize(
        'kwargs, expected',
        [
            # I. Creators name the work
            (
                dict(creators=['Hannah Arendt'], year=1958, title='The Human Condition'),
                'arendt-h__1958__the-human-condition',
            ),
            (
                dict(
                    creators=['Marvin L. Minsky', 'Seymour A. Papert'],
                    year=1969,
                    title='Perceptrons: An Introduction',
                ),
                'minsky-ml_papert-sa__1969__perceptrons',
            ),
            # II. The work's own identifier stands in, and the real title survives
            (
                dict(
                    title='Zep: A Temporal Knowledge Graph Architecture',
                    year=2025,
                    uids={'arxiv': '2501.13956'},
                ),
                'uid-arxiv__2025__zep',
            ),
            (
                dict(title='Memory Poisoning in Agent Systems', uids={'arxiv': '2607.06595'}),
                'uid-arxiv__0000__memory-poisoning-in-agent-systems',
            ),
            # III. Failing that, whoever published it
            (
                dict(title='Some Press Release', year=2024, site='https://example.org/news/x'),
                'site-example-org__2024__some-press-release',
            ),
            # IV. Last resort: an identifier with no readable title still names one work
            (
                dict(uids={'arxiv': '2501.13956'}, year=2025),
                'uid-arxiv__2025__2501-13956',
            ),
            # A year nobody triaged is `0000`, never a guess
            (
                dict(creators=['Vladimir Lenin'], title='What Is To Be Done'),
                'lenin-v__0000__what-is-to-be-done',
            ),
            # An unrecoverable year says so
            (
                dict(creators=['Friedrich Hayek'], year='undated', title='The Sensory Order'),
                'hayek-f__undated__the-sensory-order',
            ),
        ],
    )
    def test_mint(self, kwargs: dict, expected: str):
        minted = DocName.mint(**kwargs)
        assert minted is not None
        assert str(minted) == expected
        assert DocName.is_valid(str(minted))

    @pyt.mark.parametrize(
        'kwargs',
        [
            # Nothing here identifies a document
            dict(),
            dict(year=2025),
            dict(creators=['Hannah Arendt']),
            dict(site='example.org'),
            dict(title=''),
            # A title alone names no work -- there is no creator-shaped handle at all
            dict(title='Some Paper', year=2025),
        ],
    )
    def test_mint__refuses_rather_than_guessing(self, kwargs: dict):
        assert DocName.mint(**kwargs) is None

    @pyt.mark.parametrize(
        'creators, uids, expected_creators',
        [
            # Creators outrank an identifier when both are present
            (['Hannah Arendt'], {'arxiv': '2501.13956'}, 'arendt-h'),
            # The identifier only stands in once the creators are gone
            ([], {'arxiv': '2501.13956'}, 'uid-arxiv'),
            # Schemes resolve in sorted order, so one document mints one name
            ([], {'doi': '10.1145/3597503', 'arxiv': '2501.13956'}, 'uid-arxiv'),
        ],
    )
    def test_mint__ladder_order(
        self, creators: Iterable[str], uids: dict[str, str], expected_creators: str
    ):
        minted = DocName.mint(title='A Title', year=2025, creators=creators, uids=uids)
        assert minted is not None
        assert minted.creators == expected_creators

    def test_model__is_frozen(self):
        name = DocName.parse('arendt-h__1958__human-condition')
        assert name is not None
        with pyt.raises(pyd.ValidationError):
            name.year = '1959'  # pyrefly: ignore[read-only]

    @pyt.mark.parametrize(
        'creators, year, title',
        [
            ('Arendt-H', '1958', 'human-condition'),
            ('arendt h', '1958', 'human-condition'),
            ('arendt-h', '58', 'human-condition'),
            ('arendt-h', '1958', ''),
            ('', '1958', 'human-condition'),
        ],
    )
    def test_model__refuses_an_unwritable_name(self, creators: str, year: str, title: str):
        """A `DocName` that exists is a name that can be written to the shelf."""
        with pyt.raises(pyd.ValidationError):
            DocName(creators=creators, year=year, title=title)

    @pyt.mark.parametrize(
        'suffix, expected',
        [
            ('', 'arendt-h__1958__human-condition'),
            ('pdf', 'arendt-h__1958__human-condition.pdf'),
            ('.epub', 'arendt-h__1958__human-condition.epub'),
        ],
    )
    def test_filename(self, suffix: str, expected: str):
        name = DocName.parse('arendt-h__1958__human-condition')
        assert name is not None
        assert name.filename(suffix) == expected

    def test_disambiguated__returns_itself_when_free(self):
        name = DocName.parse('arendt-h__1958__human-condition')
        assert name is not None
        assert name.disambiguated(set(), 'pdf') is name

    @pyt.mark.parametrize(
        'taken_count, expected_title', [(1, 'human-condition_2'), (2, 'human-condition_3')]
    )
    def test_disambiguated__takes_an_ordinal_sub_unit(self, taken_count: int, expected_title: str):
        """Two different works may mint one name; the shelf must not absorb one into the other."""
        name = DocName.parse('arendt-h__1958__human-condition')
        assert name is not None
        # The base name plus `taken_count - 1` ordinal variants are already shelved.
        taken = {name.filename('pdf')}
        taken |= {
            f'{name.creators}__{name.year}__{name.title}_{n}.pdf' for n in range(2, taken_count + 1)
        }
        variant = name.disambiguated(taken, 'pdf')
        assert variant.title == expected_title
        assert DocName.is_valid(str(variant))


class TestUpstreamSpec:
    """The cases wikiparse and the literature corpus already pin, run against the port.

    These are the port's contract with its two origins. A divergence here is either a bug
    or a decision, and each of the two decisions below is named as such.
    """

    @pyt.mark.parametrize(
        'slug, valid',
        [
            # Verbatim from lit's `TestIsValidSlug`
            ('deleuze-g_et-al__1968__difference-et-repetition', True),
            ('pearce-j__2008__animal-learning_cognition', True),
            ('deleuze-g-et-al__1968__difference-et-repetition', False),
            ('deleuze-g___1968__difference-et-repetition', False),
        ],
    )
    def test_is_valid_slug__matches_lit(self, slug: str, valid: bool):
        assert DocName.is_valid(slug) is valid

    def test_truncate__matches_lit_exposed_tail_rule(self):
        """Verbatim from lit's `truncate_filename_section` exposed-tail-detritus case."""
        title = 'one-two-three-four-five-six-seven-eight-nine-and-ten'
        assert DocName.clean_section(title, 48) == 'one-two-three-four-five-six-seven-eight-nine'

    @pyt.mark.parametrize(
        'established, expected',
        [
            # Verbatim from lit's leading-article and internal-word rules
            ('the-human-condition', 'human-condition'),
            ('being-and-time', 'being-and-time'),
            ('art-of-war', 'art-of-war'),
        ],
    )
    def test_leading_article__matches_lit(self, established: str, expected: str):
        assert DocName.without_leading_article(established) == expected

    @pyt.mark.parametrize(
        'established, candidate, expected',
        [
            # lit: `restores_only_missing_internal_connectors`
            ('difference-repetition', 'difference-and-repetition', 'difference-and-repetition'),
            # lit: `cannot_restore_new_content_words` -- a content word is not a connector
            ('deleuze', 'deleuzes-kants-critical-philosophy', 'deleuze'),
            # A candidate describing a different title supplies nothing
            ('being-and-time', 'sein-und-zeit', 'being-and-time'),
        ],
    )
    def test_restore_connectors__matches_lit(self, established: str, candidate: str, expected: str):
        assert DocName.restore_internal_title_connectors(established, candidate) == expected

    @pyt.mark.parametrize(
        'established, candidate, conservative',
        [
            # lit: `distinctive_prefix_is_conservative`
            (
                'linking-contemporary-high-resolution-magnetic-resonance-imaging',
                'linking-contemporary-high-resolution-magnetic',
                True,
            ),
            # The established title itself, modulo one leading article
            ('the-human-condition', 'human-condition', True),
            # Too short, and too few words, to be distinctive
            ('linking-contemporary-high-resolution-magnetic', 'linking', False),
            ('the-human-condition', 'human', False),
            # Not a prefix at all
            ('being-and-time', 'sein-und-zeit', False),
            ('the-human-condition', '', False),
        ],
    )
    def test_conservative_candidate__matches_lit(
        self, established: str, candidate: str, conservative: bool
    ):
        assert DocName.is_conservative_title_candidate(established, candidate) is conservative

    def test_creators__joins_with_underscore_like_wikiparse(self):
        """wikiparse's own `test_name_creators` pins `smith-jane_mason-alice_et-al`.

        The join is `_`; the divergence is initials, not given names -- see the module
        docstring. Everything about the *delimiters* matches the origin exactly.
        """
        slot = DocName.creators_slot(['Jane Smith', 'Alice Mason', 'Bob Woodward'])
        assert slot == 'smith-j_mason-a_et-al'
        assert slot.count('_') == 2 and DocName.is_valid(f'{slot}__2024__a-title')

    def test_creators__is_capped_like_every_other_slot(self):
        """wikiparse truncates `name_creators()` too, so one slot cannot eat the budget."""
        slot = DocName.creators_slot(['Wolfeschlegelsteinhausenbergerdorff Aaaa', 'Bbbb' * 12])
        assert len(slot) <= 48

    def test_prose_stopwords_are_kept(self):
        """The documented divergence: wikiparse's prose path would drop `a`, `of`, `from`."""
        assert DocName.title_slot('A Study of Intense Polymers from Light', 30) == (
            'a-study-of-intense-polymers'
        )
