############
### HEAD ###
############
### EXTERNAL
import pytest as pyt

### INTERNAL
import my
from my import ut, utils
from my.utils import Utils


############
### BODY ###
############
class TestUtilsFacadeIsIntentional:
    """Guard the deliberate ``utils = ut = Utils`` aggregation (finding basis-A1).

    ``my.utils`` intentionally resolves to the ``Utils`` *class*, shadowing this submodule, so that
    ``from my import utils as ut`` yields the flat aggregating facade.
    Downstream code (e.g. ``means``) depends on this -- see the ``my/utils/__init__.py`` docstring.
    Do **not** "de-shadow" ``my.utils`` by dropping ``utils`` from the top-level facade.
    """

    @pyt.mark.parametrize('name', ['utils', 'ut'])
    def test_alias_is_the_class(self, name):
        """``utils`` and ``ut`` are the ``Utils`` class itself, not this submodule."""
        assert getattr(my, name) is Utils

    def test_from_my_import_utils_is_the_class(self):
        """The exact consumer pattern ``from my import utils`` yields the class."""
        assert utils is Utils
        assert ut is Utils

    def test_my_utils_attribute_shadows_the_submodule(self):
        """``my.utils`` is the class, so submodule singletons like ``iter_utils`` are not on it."""
        assert my.utils is Utils
        # Reach the singleton via the top-level facade (``my.iter_utils``) instead.
        assert not hasattr(my.utils, 'iter_utils')
        assert hasattr(my, 'iter_utils')

    # Every method real consumers (means) call through ``ut.<m>`` must stay reachable on the facade.
    @pyt.mark.parametrize(
        'method',
        [
            'validate_dir',
            'validate_file',
            'clean_string',
            'wrap',
            'split_into',
            'regex_dict',
            'get_terminal_width',
            'setup_logging',
            'fill_tree',
            'pyd_schemify',
        ],
    )
    def test_aggregated_methods_reachable(self, method):
        """A method ``means`` invokes via ``ut.<method>`` resolves on the combined facade."""
        assert hasattr(Utils, method)
