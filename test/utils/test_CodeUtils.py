############
### HEAD ###
############
### STANDARD

### EXTERNAL
import pytest as pyt

### INTERNAL
from my.utils import CodeUtils

cls = CodeUtils


############
### BODY ###
############
class TestCodeUtils:
    @pyt.mark.parametrize('data, expected', [])
    def test_instance_fields(self, data: str, expected: str):
        pass

    @pyt.mark.parametrize('data, expected', [])
    def test_instance_aliases(self, data: str, expected: str):
        pass

    @pyt.mark.parametrize('data, expected', [])
    def test_nested_replace(self, data: str, expected: str):
        pass

    @pyt.mark.parametrize('data, expected', [])
    def test_import_module(self, data: str, expected: str):
        pass

    @pyt.mark.parametrize('data, expected', [])
    def test_clear_cached_properties(self, data: str, expected: str):
        pass
