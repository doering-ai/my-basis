############
### HEAD ###
############
### STANDARD

### EXTERNAL
import pytest as pyt

### INTERNAL
from my.utils import SyntaxUtils

cls = SyntaxUtils


############
### BODY ###
############
class TestSyntaxUtils:
    @pyt.mark.parametrize('data,expected', [])
    def test_fill_tree(self, data: str, expected: str):
        pass

    @pyt.mark.parametrize('data,expected', [])
    def test_tree_size(self, data: str, expected: str):
        pass

    @pyt.mark.parametrize('data,expected', [])
    def test_pyd_schemify(self, data: str, expected: str):
        pass
