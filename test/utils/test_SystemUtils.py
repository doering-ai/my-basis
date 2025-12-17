############
### HEAD ###
############
### STANDARD

### EXTERNAL
import pytest as pyt

### INTERNAL
from my.utils import SystemUtils

cls = SystemUtils


############
### BODY ###
############
class TestSystemUtils:
    @pyt.mark.parametrize('data,expected', [])
    def test_posix(self, data: str, expected: str):
        pass

    @pyt.mark.parametrize('data,expected', [])
    def test_posix_since(self, data: str, expected: str):
        pass

    @pyt.mark.parametrize('data,expected', [])
    def test_validate_dir(self, data: str, expected: str):
        pass

    @pyt.mark.parametrize('data,expected', [])
    def test_validate_file(self, data: str, expected: str):
        pass

    @pyt.mark.parametrize('data,expected', [])
    def test_path_sub(self, data: str, expected: str):
        pass

    @pyt.mark.parametrize('data,expected', [])
    def test_get_terminal_width(self, data: str, expected: str):
        pass

    @pyt.mark.parametrize('data,expected', [])
    def test_terminal_linewrap(self, data: str, expected: str):
        pass

    @pyt.mark.parametrize('data,expected', [])
    def test_auto_confirm(self, data: str, expected: str):
        pass

    @pyt.mark.parametrize('data,expected', [])
    def test_zsh_colorize(self, data: str, expected: str):
        pass

    @pyt.mark.parametrize('data,expected', [])
    def test_confirm(self, data: str, expected: str):
        pass

    @pyt.mark.parametrize('data,expected', [])
    def test_setup_py_logging(self, data: str, expected: str):
        pass

    @pyt.mark.parametrize('data,expected', [])
    def test_setup_fire_logging(self, data: str, expected: str):
        pass

    @pyt.mark.parametrize('data,expected', [])
    def test_get_package_name(self, data: str, expected: str):
        pass

    @pyt.mark.parametrize('data,expected', [])
    def test_setup_logging(self, data: str, expected: str):
        pass

    @pyt.mark.parametrize('data,expected', [])
    def test_setup_warnings(self, data: str, expected: str):
        pass

    @pyt.mark.parametrize('data,expected', [])
    def test_setup_metrics(self, data: str, expected: str):
        pass

    @pyt.mark.parametrize('data,expected', [])
    def test__measure(self, data: str, expected: str):
        pass

    @pyt.mark.parametrize('data,expected', [])
    def test__instrument(self, data: str, expected: str):
        pass

    @pyt.mark.parametrize('data,expected', [])
    def test_measure_context(self, data: str, expected: str):
        pass

    @pyt.mark.parametrize('data,expected', [])
    def test_monitor(self, data: str, expected: str):
        pass

    @pyt.mark.parametrize('data,expected', [])
    def test_print_in_color(self, data: str, expected: str):
        pass
