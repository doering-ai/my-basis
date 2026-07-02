############
### HEAD ###
############
### STANDARD
from pathlib import Path

### EXTERNAL
import pytest as pyt

### INTERNAL
from my import typist
from my.regex import COMMON_RGXS, RegexDebugger
from my.regex.meta import META_RGXS

EXAMPLES = typist.from_yaml(Path(__file__).parent / 'common-rgx-tests.yaml')

cls = RegexDebugger


############
### BODY ###
############
class TestCommonRegexes:
    # -------------------
    # `.` Initial Methods
    # -------------------
    @pyt.mark.parametrize(
        'name, index',
        [
            (name, index)
            for name, cases in EXAMPLES.items()
            for index in range(len(cases) if cases else 0)
            if cases
        ],
    )
    def test_common_rgxs(self, name: str, index: int, pytestconfig):
        # I. Parse the example into its full form
        text, func, expected = cls.parse_pytest(name, EXAMPLES[name][index])
        cls.pytest(
            store=COMMON_RGXS,
            name=name,
            index=index,
            text=text,
            func=func,
            expected=expected,
            verbose=pytestconfig.getoption('verbose') > 1,
        )

    # -------------------
    # `+` Primary Methods
    # -------------------
    @pyt.mark.parametrize(
        'target',
        [
            'web.archive.org/web/20081205101019/http://www.site.org',
            'http://example.com/page#section',
            "example.com/page.,'",
            'http://example.com/clean/path',
        ],
    )
    def test_url_detritus__reexported_from_common_rgxs(self, target: str):
        # basis-12 item 2 regression: `url_detritus` used to live only on the internal
        # `META_RGXS`, so consuming it via the public `COMMON_RGXS` surface (as wikiparse's
        # `CITATION_RGXS` does) raised a `KeyError`. It's re-exported now -- verify the key
        # exists and behaves identically to the internal source of truth.
        assert 'url_detritus' in COMMON_RGXS

        common_result = COMMON_RGXS['url_detritus'].sub('', target).strip('/. ')
        meta_result = META_RGXS['url_detritus'].sub('', target).strip('/. ')
        assert common_result == meta_result
