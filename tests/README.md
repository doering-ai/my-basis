# Testing Guidelines

The MyBasis test suite prioritizes clarity, organization, and comprehensive coverage through heavy use of parametrization.
By following these conventions, tests remain maintainable, easy to navigate, and serve as excellent documentation of expected behavior.

## Philosophy

The test suite emphasizes:

- **Comprehensive coverage**: All public methods, properties, and edge cases should be tested
- **Parametrization**: Use `@pyt.mark.parametrize` extensively to test multiple input scenarios
- **Organization**: Mirror the structure of the source code for easy navigation
- **Clarity**: Test names and docstrings should clearly describe what is being tested
- **Isolation**: Tests should be independent and use fixtures to ensure clean state

## File Structure

### Standard Layout

Test files follow the same HEAD/DATA/BODY structure as source files:

```python
############
### HEAD ###
############
### STANDARD
from pathlib import Path

### EXTERNAL
import pytest as pyt

### INTERNAL
from my.module import ClassName
from ..conftest import boolmap

cls = ClassName


############
### DATA ###
############
# Module-level test data or constants (if needed)


############
### BODY ###
############
class TestClassName:
    # Test methods organized into sections...
```

**Key conventions:**

- Use `cls = ClassName` to reference the class being tested throughout the file
- Import `pytest as pyt` for consistency
- Import shared utilities like `boolmap` from `conftest.py`

### Test Class Organization

Test classes are organized into hierarchical sections using comment headers, any of which may be missing for a particular class:

```python
class TestClassName:
    """Test suite for ClassName."""

    # -------------------
    # `.` Initial Methods
    # -------------------
    # Fixtures, __init__, constructors, validators, etc.

    # -------------------
    # `-` Private Methods
    # -------------------
    # Tests for private/internal methods (usually minimal, as these are tested through public API)

    # -------------------
    # `+` Primary Methods
    # -------------------
    # Core functionality methods

    # ------------------
    # `*` Public Methods
    # ------------------
    # The main public interface

    # --------------
    # `*0` Overrides
    # --------------
    # Dunder methods: __str__, __repr__, __getattr__, __len__, __bool__, etc.

    # ---------------
    # `*1` Properties
    # ---------------
    # Property accessors and cached properties

    # ------------
    # `*2` Methods
    # ------------
    # Standard public methods
```

This structure mirrors how classes are organized in the source code, making it easy to navigate between implementation and tests.

## Parametrization

### Basic Parametrization

Use `@pyt.mark.parametrize` extensively to test multiple scenarios:

```python
@pyt.mark.parametrize(
    'input_value, expected_output',
    [
        ('simple', 'SIMPLE'),
        ('with spaces', 'WITH SPACES'),
        ('', ''),
        ('123', '123'),
    ],
)
def test_to_uppercase(self, input_value: str, expected_output: str):
    """Test string conversion to uppercase."""
    result = cls.to_uppercase(input_value)
    assert result == expected_output
```

**Guidelines:**

- Parameter names should be descriptive
- Include edge cases (empty strings, None, boundary values)
- Type hint the parameters in the test function signature
- Add a clear docstring

### The `boolmap` Helper

For boolean tests, use the `boolmap` helper from `conftest.py`:

```python
from ..conftest import boolmap

@pyt.mark.parametrize(
    'value, expected',
    boolmap(
        true=['valid', 'acceptable', 'good'],
        false=['invalid', 'bad', ''],
    ),
)
def test_is_valid(self, value: str, expected: bool):
    """Test validation logic."""
    assert cls.is_valid(value) == expected
```

**For tuple parameters**, specify `base_type=tuple`:

```python
@pyt.mark.parametrize(
    'key, value, expected',
    boolmap(
        true=[('KEY1', 'val1', 5), ('KEY2', 'val2', 6)],
        false=[('bad', 'val', 5)],
        base_type=tuple,
    ),
)
def test_validation(self, key: str, value: str, expected: bool):
    """Test key-value validation."""
    assert cls.validate(key, value) == expected
```

This automatically adds the boolean expected value as the last parameter.

## Fixtures

### Basic Fixtures

Define fixtures for common setup:

```python
@pyt.fixture
def instance(self) -> ClassName:
    """Create a fresh instance for testing."""
    return cls()

@pyt.fixture
def temp_file(self, tmp_path: Path) -> Path:
    """Create a temporary file path."""
    return tmp_path / 'test_file.txt'
```

### Fixture Usage with Parametrization

Combine fixtures with parametrized tests:

```python
@pyt.fixture
def cache_instance(self, tmp_path: Path) -> Cache:
    """Create a cache instance with temporary storage."""
    return cls(file=tmp_path / 'cache.pkl')

@pyt.mark.parametrize(
    'key, value',
    [
        ('key1', 'value1'),
        ('key2', 42),
        (123, 'numeric_key'),
    ],
)
def test_cache_storage(self, cache_instance: Cache, key: any, value: any):
    """Test cache can store various types."""
    cache_instance[key] = value
    assert cache_instance[key] == value
```

### Cleanup Fixtures

For tests that modify global state (like environment variables), use fixtures with cleanup:

```python
@pyt.fixture
def temp_env_var(self, monkeypatch):
    """Fixture to temporarily set environment variables."""
    def _set_var(key: str, value: str):
        monkeypatch.setitem(cls._ENVIRON, key, value)
        cls._get.cache_clear()  # Clear any caches
    return _set_var
```

## Test Naming

### Test Method Names

Test names should be descriptive and follow this pattern:

```
test_<method_name>__<scenario>
```

**Examples:**

- `test_get` - Basic functionality of the `get` method
- `test_get__with_default` - Testing `get` with default values
- `test_get__missing_key` - Testing `get` when key doesn't exist
- `test_path__mkdir` - Testing path creation with mkdir option

### Multiple Underscores

Use double underscores (`__`) to separate the method name from the scenario:

```python
def test_interpolate__nested(self):
    """Test nested variable interpolation."""
    ...

def test_flag__as_boolean(self):
    """Test that flags work correctly with bool() coercion."""
    ...
```

## Docstrings

Every test method should have a concise docstring:

```python
def test_set__validates_name(self, instance: Environment, invalid_key: str):
    """Test that set validates environment variable names."""
    with pyt.raises(AssertionError):
        instance.set(invalid_key, 'value')
```

**Guidelines:**

- Start with a verb (Test, Verify, Ensure)
- Be specific about what is being tested
- Keep it to one line when possible
- Mention the expected behavior or outcome

## Assertions

### Basic Assertions

Use clear, simple assertions:

```python
assert result == expected
assert value in collection
assert instance.property == 'expected_value'
```

### Exception Testing

Use `pyt.raises` for exception tests:

```python
def test_invalid_input(self):
    """Test that invalid input raises ValueError."""
    with pyt.raises(ValueError):
        cls.process_data(None)

# With message matching
def test_error_message(self):
    """Test specific error message."""
    with pyt.raises(ValueError, match='Invalid format'):
        cls.parse('bad_format')
```

### Type Assertions

Verify types when relevant:

```python
def test_returns_path(self):
    """Test that method returns Path object."""
    result = cls.get_path('~/test')
    assert isinstance(result, Path)
    assert result.is_absolute()
```

## Async Tests

For async methods, use `@pyt.mark.asyncio`:

```python
@pyt.mark.asyncio
async def test_async_read(self, cache_instance: Cache):
    """Test asynchronous cache reading."""
    result = await cache_instance.read()
    assert result is not None
```

## Common Patterns

### Testing Dunder Methods

```python
def test_len(self, instance: ClassName):
    """Test __len__ returns correct count."""
    assert len(instance) == expected_length

def test_contains(self, instance: ClassName):
    """Test __contains__ for membership testing."""
    assert 'key' in instance
    assert 'missing' not in instance

def test_getitem(self, instance: ClassName):
    """Test __getitem__ for dict-style access."""
    assert instance['key'] == 'value'

def test_bool(self, instance: ClassName):
    """Test __bool__ coercion."""
    assert bool(instance) == expected_bool
```

## Running Tests

```zsh
# Run All Tests
task test

# Run Specific Test File
task test -- -v test/apis/test_Environment.py

# Run Specific Test
task test -- -v test/apis/test_Environment.py::TestEnvironment::test_get__basic

# Calculate Coverage
task test:cov

# Debug Mode
task test:pdb  # Drops into debugger on failure
task test:dev  # For debugging one test at a time
```

## Best Practices

### DO:

- ✓ Write tests for all public methods and properties
- ✓ Use parametrization to cover multiple scenarios
- ✓ Test edge cases and error conditions
- ✓ Use fixtures for setup and teardown
- ✓ Keep tests independent and isolated
- ✓ Write clear, descriptive test names and docstrings
- ✓ Follow the established section structure
- ✓ Clear caches when testing cached methods

### DON'T:

- ✗ Test implementation details (test behavior, not internals)
- ✗ Write tests that depend on execution order
- ✗ Use hard-coded paths (use fixtures and tmp_path)
- ✗ Leave tests without docstrings
- ✗ Skip edge case testing
- ✗ Write overly complex test logic (tests should be simple)

## Example: Complete Test File

Here's a condensed example showing all the patterns:

```python
############
### HEAD ###
############
### STANDARD

### EXTERNAL
import pytest as pyt

### INTERNAL
from my.module import MyClass
from ..conftest import boolmap

cls = MyClass


############
### BODY ###
############
class TestMyClass:
    # -------------------
    # `.` Initial Methods
    # -------------------
    @pyt.fixture
    def instance(self) -> MyClass:
        """Create a fresh instance."""
        return cls()

    def test_init__basic(self):
        """Test basic initialization."""
        obj = cls()
        assert obj.value is None

    # -------------------
    # `+` Primary Methods
    # -------------------
    @pyt.mark.parametrize(
        'input_val, expected',
        [
            (1, 2),
            (0, 0),
            (-1, -2),
        ],
    )
    def test_process(self, instance: MyClass, input_val: int, expected: int):
        """Test processing with various inputs."""
        result = instance.process(input_val)
        assert result == expected

    # ------------------
    # `*` Public Methods
    # ------------------
    # --------------
    # `*0` Overrides
    # --------------
    def test_len(self, instance: MyClass):
        """Test __len__ returns item count."""
        assert len(instance) == 0

    @pyt.mark.parametrize(
        'value, expected',
        boolmap(
            true=['a', 'b'],
            false=['x', 'y'],
        ),
    )
    def test_contains(self, instance: MyClass, value: str, expected: bool):
        """Test membership checking."""
        assert (value in instance) == expected

    # ---------------
    # `*1` Properties
    # ---------------
    def test_my_property(self, instance: MyClass):
        """Test property returns expected value."""
        assert instance.my_property == 'expected'

    # ------------
    # `*2` Methods
    # ------------
    def test_public_method(self, instance: MyClass):
        """Test public method behavior."""
        result = instance.public_method()
        assert result is not None

    # ----------------
    # Edge Cases Tests
    # ----------------
    def test_empty_input(self, instance: MyClass):
        """Test handling of empty input."""
        result = instance.process('')
        assert result == ''

    def test_unicode(self, instance: MyClass):
        """Test Unicode character handling."""
        result = instance.process('世界')
        assert '世界' in result
```
