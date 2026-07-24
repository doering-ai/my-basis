############
### HEAD ###
############
### STANDARD
from pathlib import Path
from collections.abc import Callable
import json
import functools as ft

### EXTERNAL
import pytest as pyt
import regex as re

### INTERNAL
from my import ut
from my.caches import FileCache

############
### DATA ###
############
cls = FileCache


############
### BODY ###
############
class TestFileCache:
    # ------------------
    # Fixtures & Helpers
    # ------------------
    @pyt.fixture
    def cache_dir(self, tmp_path: Path) -> Path:
        """Create a temporary cache directory structure."""
        cache_dir = tmp_path / 'cache'
        cache_dir.mkdir()
        return cache_dir

    @pyt.fixture
    def splitter(self) -> Callable[[str], list[str]]:
        return ft.partial(str.split, sep='_')  # ty:ignore[invalid-return-type]

    @pyt.fixture
    def cache(self, cache_dir: Path, splitter) -> FileCache[str]:
        """Create a basic FileCache instance."""
        return FileCache[str](directory=cache_dir, max_size=100)

    @pyt.fixture
    def populated_cache(self, cache_dir: Path, splitter) -> FileCache[str]:
        """Create a FileCache with pre-existing files on disk."""
        # Create filedata
        group_dir = cache_dir / 'sys' / 'a/b/c'
        group_dir.mkdir(parents=True)
        file_data = {'abcfile_item1': 'sys_val1', 'abcfile_item2': 'sys_val2'}
        (group_dir / 'abcfile.json').write_text(json.dumps(file_data, indent=2))

        cache = FileCache[str](directory=cache_dir)

        # II. Set initial items data
        cache['mem', 'xyzfile_item1'] = 'mem_val1'
        cache['mem', 'xyzfile_item2'] = 'mem_val2'

        return cache

    # -------------------
    # `.` Initial Methods
    # -------------------
    def test_init(self, cache_dir: Path, splitter):
        cache = FileCache[str](directory=cache_dir)

        assert cache.directory == cache_dir
        assert cache.isize == 0
        assert cache.fsize == 0
        assert cache.max_size == cls.MAX_CACHE

    def test_init__custom_max_size(self, cache_dir: Path, splitter):
        cache = FileCache[str](directory=cache_dir, max_size=1000)
        assert cache.max_size == 1000

    def test_init__indexes_existing_files(self, populated_cache: FileCache[str]):
        # Should have indexed the pre-existing file
        assert 'sys' in populated_cache.files
        assert 'abcfile' in populated_cache.files['sys']['abc']

        # Should have found items in the file
        items = populated_cache.files['sys']['abc']['abcfile']
        assert ut.has_all(items, 'abcfile_item1', 'abcfile_item2')

    def test_init__directory_validation(self, splitter):
        with pyt.raises(AssertionError, match='Invalid cache directory'):
            FileCache(directory=Path('/nonexistent/path'))

    # -------------------
    # `-` Private Methods
    # -------------------
    @pyt.mark.parametrize(
        'filename, expected',
        [
            ('test', 'tes'),
            ('abc', 'abc'),
            ('a', 'a'),
            ('test_file', 'tes'),
            ('my-file', 'myf'),
            ('test_long_name', 'tes'),
            ('_-test', 'tes'),
        ],
    )
    def test_prefix(self, filename: str, expected: str):
        result = cls._prefix(filename)
        assert result == expected
        assert len(result) <= 3

    def test_get_mem(self, populated_cache: FileCache[str]):
        result = populated_cache._get_mem_items('mem', 'xyz', 'xyzfile')
        assert result is not None
        assert result['xyzfile_item1'] == 'mem_val1'
        assert result['xyzfile_item2'] == 'mem_val2'

    def test_get_mem__not_exists(self, cache: FileCache[str]):
        result = cache._get_mem_items('nonexistent', 'fil', 'file')
        assert result is None

    def test_get_sys(self, populated_cache: FileCache[str]):
        result = populated_cache._get_sys_items('sys', 'abc', 'abcfile')
        assert result is not None
        assert result == {'abcfile_item1', 'abcfile_item2'}

    def test_get_sys__not_exists(self, cache: FileCache[str]):
        result = cache._get_sys_items('nonexistent', 'pre', 'file')
        assert result is None

    # -------------------
    # `+` Primary Methods
    # -------------------
    # ------------------
    # `*` Public Methods
    # ------------------
    def test_set(self, cache: FileCache[str]):
        cache['tmp', 'abcfile_item1'] = 'value1'
        cache['tmp', 'abcfile_item2'] = 'value2'

        assert cache.isize == 2
        assert cache.items['tmp']['abc']['abcfile'] == dict(
            abcfile_item1='value1', abcfile_item2='value2'
        )

    def test_set__triggers_prune(self, cache: FileCache[str]):
        cache.max_size = 10

        # Fill to capacity
        for i in range(10):
            cache['group', f'abcfile_item{i}'] = f'value{i}'
        assert cache.isize == 10

        # Add one more, should trigger prune
        cache['group', 'xyzfile_item99'] = 'value'
        assert cache.isize < 10

    def test_get(self, populated_cache: FileCache[str]):
        cache = populated_cache
        isize0, fsize0 = cache.isize, cache.fsize

        # Read memory
        assert cache['mem', 'xyzfile_item2'] == 'mem_val2'
        assert cache.isize == isize0
        assert cache.fsize == fsize0

        # Read file
        assert cache['sys', 'abcfile_item2'] == 'sys_val2'
        assert cache.isize > isize0
        assert cache.fsize < fsize0

    def test_get__not_found(self, cache: FileCache[str]):
        assert cache['group', 'nonexistent'] is None

    def test_prune(self, cache: FileCache[str]):
        # Fill cache with items
        for i in range(50):
            cache['test', f'abcfile{i}_item'] = 'value'
        initial_size = cache.isize
        cache.prune(20)
        assert cache.isize == initial_size - 20

    def test_prune__proportional_distribution(self, cache: FileCache[str]):
        # Add items to different groups
        for i in range(30):  # 75%
            cache['group1', f'file{i}_item1'] = 'value1'

        for i in range(5):  # 25%
            cache['group2', f'file{i}A_item1'] = 'value1'
            cache['group2', f'file{i}B_item2'] = 'value2'

        assert cache.isize == 40
        assert abs(cache.group_isize('group1') - 30) <= 1
        assert abs(cache.group_isize('group2') - 10) <= 1
        cache.prune(20)

        # Should prune proportionally (group1 has 3x items, should prune ~15, group2 ~5)
        assert abs(cache.group_isize('group1') - 15) <= 1
        assert abs(cache.group_isize('group2') - 5) <= 3

    def test_prune__writes_to_disk(self, cache: FileCache[str], cache_dir: Path):
        cache['group', 'abcfile_newitem'] = 'value'
        cache.prune()
        assert 'abcfile.json' in [file.name for file in cache_dir.rglob('*')]

    def test_reindex__default_writer_roundtrip(self, cache: FileCache[str], cache_dir: Path):
        """Regression: shards from `_default_writer` re-index readable on a fresh instance."""
        cache['group', 'abcfile_newitem'] = 'value'
        cache.prune()

        fresh = FileCache[str](directory=cache_dir, max_size=100)
        assert fresh.read('group', 'abcfile_newitem') == 'value'

    @pyt.mark.parametrize(
        'entries',
        [
            pyt.param((), id='empty'),
            pyt.param((('group1', 'aaafile_item', 'value1'),), id='single'),
            pyt.param(
                (
                    ('group1', 'aaafile1_item1', 'value1'),
                    ('group1', 'aaafile1_item2', 'value2'),
                    ('group2', 'bbbfile2_item', 'value3'),
                ),
                id='multiple-digit-shards',
            ),
        ],
    )
    def test_flush(
        self,
        cache: FileCache[str],
        cache_dir: Path,
        capsys: pyt.CaptureFixture[str],
        entries: tuple[tuple[str, str, str], ...],
    ):
        """Test flush persists indexed, same-instance-readable shards without output."""
        for group, name, value in entries:
            cache[group, name] = value
        assert cache.isize == len(entries)

        cache.flush()

        assert cache.isize == 0
        assert cache.fsize == len(entries)
        assert len(cache) == len(entries)
        for group, name, _ in entries:
            file = name.partition('_')[0]
            prefix = file[:3]
            assert name in cache.files[group][prefix][file]
            assert cache_dir.joinpath(group, *prefix, f'{file}.json').exists()
        for group, name, value in entries:
            assert cache.read(group, name) == value
        captured = capsys.readouterr()
        assert (captured.out, captured.err) == ('', '')

    def test_search__by_file(self, cache: FileCache[str]):
        # Add items to memory
        cache['group', 'test_item'] = 'value1'
        cache['group', 'prod_item'] = 'value2'
        cache.isize = 2

        file_rgx = re.compile(r'test')
        name_rgx = re.compile(r'^$')
        results = list(cache.search('group', file_rgx, name_rgx))
        assert results == ['value1']

    def test_search__by_item(self, cache: FileCache[str]):
        cache['group', 'abcfile1_item1'] = 'value1'
        cache['group', 'abcfile2_item2'] = 'value2'
        cache.isize = 2

        file_rgx = re.compile(r'^$')
        name_rgx = re.compile(r'item2')
        results = list(cache.search('group', file_rgx, name_rgx))
        assert results == ['value2']

    def test_search__mode(self, cache: FileCache[str]):
        cache['group', 'abcfile_item1'] = 'value1'
        cache['group', 'abcfile_item2'] = 'value2'
        cache.isize = 2

        file_rgx = re.compile(r'^$')
        name_rgx = re.compile(r'item2')
        results = list(cache.search('group', file_rgx, name_rgx, mode='files'))
        assert results == []
