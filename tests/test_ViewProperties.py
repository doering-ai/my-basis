############
### HEAD ###
############
### STANDARD
from __future__ import annotations

### EXTERNAL
import pytest as pyt
import sublime as sb

### INTERNAL
from myBasis.infra.ViewProperties import ViewProperties, view_property


############
### DATA ###
############
class _MockHost:
    """Minimal host object for ViewProperties tests, simulating a view-bearing command."""

    _cache: ViewProperties

    def __init__(self, view: sb.View) -> None:
        self.view = view
        self._cache = ViewProperties()

    @view_property
    def simple(self) -> int:
        """A simple cached property that returns the view's change count."""
        return self.view.change_count()

    @view_property(dependencies=['simple'])
    def derived(self) -> int:
        """A property that depends on ``simple``."""
        return self.simple + 100

    @view_property(hash_fn=lambda self: self.view.size())
    def hashed(self) -> str:
        """A property with a hash function (reruns when view size changes)."""
        return f'size={self.view.size()}'

    @view_property(hash_by_cursor=True)
    def cursor_based(self) -> int:
        """A property that depends on cursor position (eager)."""
        sels = list(self.view.selection)
        return sels[0].begin() if sels else 0


############
### BODY ###
############
class TestViewPropertiesModel:
    """Tests for the ``ViewProperties`` pydantic model."""

    def test_is_pydantic_model(self):
        import pydantic as pyd

        assert issubclass(ViewProperties, pyd.BaseModel)

    def test_default_values(self):
        vp = ViewProperties()
        assert vp.view_id == 0
        assert len(vp.counts) == 0
        assert len(vp.hashes) == 0
        assert len(vp.values) == 0

    def test_contains(self):
        vp = ViewProperties()
        vp.counts['foo'] = 1
        assert 'foo' in vp
        assert 'bar' not in vp

    def test_contains_by_values(self):
        vp = ViewProperties()
        vp.values['baz'] = 42
        assert 'baz' in vp


class TestRegister:
    """Tests for ``ViewProperties.register``."""

    def test_register_sets_view_id(self):
        vp = ViewProperties()
        vp.register(42, 'my_prop', lambda self: 1)
        assert vp.view_id == 42

    def test_register_stores_method(self):
        vp = ViewProperties()
        fn = lambda self: 1
        vp.register(1, 'my_prop', fn)
        assert vp.methods['my_prop'] is fn

    def test_register_stores_hash_fn(self):
        vp = ViewProperties()
        hash_fn = lambda self: 'hash'
        vp.register(1, 'my_prop', lambda self: 1, hash_fn=hash_fn)
        assert vp.hash_fns['my_prop'] is hash_fn

    def test_register_stores_dependencies(self):
        vp = ViewProperties()
        vp.register(1, 'my_prop', lambda self: 1, dependencies=['dep1', 'dep2'])
        assert vp.dependencies['my_prop'] == ['dep1', 'dep2']

    def test_register_eager(self):
        vp = ViewProperties()
        vp.register(1, 'my_prop', lambda self: 1, eager=True)
        assert 'my_prop' in vp.eager_methods

    def test_register_not_eager_by_default(self):
        vp = ViewProperties()
        vp.register(1, 'my_prop', lambda self: 1)
        assert 'my_prop' not in vp.eager_methods

    def test_register_clears_on_view_id_change(self):
        vp = ViewProperties()
        vp.register(1, 'prop1', lambda self: 1)
        vp.counts['prop1'] = 5
        vp.values['prop1'] = 'val'
        # Changing view_id should clear
        vp.register(2, 'prop2', lambda self: 2)
        assert vp.view_id == 2
        assert 'prop1' not in vp.counts or vp.counts['prop1'] == -1

    def test_register_same_view_id_no_clear(self):
        vp = ViewProperties()
        vp.register(1, 'prop1', lambda self: 1)
        vp.counts['prop1'] = 5
        vp.register(1, 'prop2', lambda self: 2)
        assert vp.counts['prop1'] == 5


class TestShouldRerun:
    """Tests for ``ViewProperties.should_rerun``."""

    def test_rerun_on_first_access(self):
        """When count is -1 (default), should rerun."""
        vp = ViewProperties()
        vp.register(1, 'prop', lambda self: 1)
        host = _MockHost.__new__(_MockHost)
        host.view = type('V', (), {'change_count': lambda self: 0})()
        host._cache = vp
        assert vp.should_rerun(host, 'prop', now=0)

    def test_no_rerun_when_unchanged(self):
        vp = ViewProperties()
        vp.register(1, 'prop', lambda self: 1)
        vp.counts['prop'] = 5
        host = _MockHost.__new__(_MockHost)
        host.view = type('V', (), {'change_count': lambda self: 0})()
        host._cache = vp
        assert not vp.should_rerun(host, 'prop', now=5)

    def test_rerun_when_changed(self):
        vp = ViewProperties()
        vp.register(1, 'prop', lambda self: 1)
        vp.counts['prop'] = 3
        host = _MockHost.__new__(_MockHost)
        host.view = type('V', (), {'change_count': lambda self: 0})()
        host._cache = vp
        assert vp.should_rerun(host, 'prop', now=7)

    def test_eager_always_reruns(self):
        vp = ViewProperties()
        vp.register(1, 'prop', lambda self: 1, eager=True)
        vp.counts['prop'] = 5
        host = _MockHost.__new__(_MockHost)
        host.view = type('V', (), {'change_count': lambda self: 0})()
        host._cache = vp
        assert vp.should_rerun(host, 'prop', now=5)


class TestInvalidate:
    """Tests for ``ViewProperties.invalidate``."""

    def test_invalidate_resets_count(self):
        vp = ViewProperties()
        vp.counts['prop'] = 5
        vp.invalidate('prop')
        assert vp.counts['prop'] == -1

    def test_invalidate_resets_hash(self):
        vp = ViewProperties()
        vp.hashes['prop'] = 123
        vp.invalidate('prop')
        assert vp.hashes['prop'] == -1

    def test_invalidate_multiple(self):
        vp = ViewProperties()
        vp.counts['a'] = 1
        vp.counts['b'] = 2
        vp.invalidate('a', 'b')
        assert vp.counts['a'] == -1
        assert vp.counts['b'] == -1

    def test_invalidate_nonexistent_noop(self):
        vp = ViewProperties()
        vp.invalidate('nonexistent')  # Should not raise


class TestRevalidate:
    """Tests for ``ViewProperties.revalidate``."""

    def test_revalidate_count(self):
        vp = ViewProperties()
        vp.revalidate('prop', count=10)
        assert vp.counts['prop'] == 10

    def test_revalidate_hash(self):
        vp = ViewProperties()
        vp.revalidate('prop', _hash=999)
        assert vp.hashes['prop'] == 999

    def test_revalidate_value(self):
        vp = ViewProperties()
        vp.revalidate('prop', value='hello')
        assert vp.values['prop'] == 'hello'

    def test_revalidate_all(self):
        vp = ViewProperties()
        vp.revalidate('prop', count=1, _hash=2, value='x')
        assert vp.counts['prop'] == 1
        assert vp.hashes['prop'] == 2
        assert vp.values['prop'] == 'x'


class TestSetValue:
    """Tests for ``ViewProperties.set_value``."""

    def test_set_simple_value(self):
        vp = ViewProperties()
        vp.set_value('prop', 42)
        assert vp.values['prop'] == 42

    def test_set_value_returns_value(self):
        vp = ViewProperties()
        result = vp.set_value('prop', 'hello')
        assert result == 'hello'

    def test_set_value_mutate_list(self):
        vp = ViewProperties()
        vp.values['prop'] = [1, 2, 3]
        vp.set_value('prop', [4, 5])
        assert vp.values['prop'] == [4, 5]

    def test_set_value_mutate_dict(self):
        vp = ViewProperties()
        vp.values['prop'] = {'a': 1}
        vp.set_value('prop', {'b': 2})
        assert vp.values['prop'] == {'b': 2}

    def test_set_value_no_mutate_different_type(self):
        vp = ViewProperties()
        vp.values['prop'] = [1, 2]
        vp.set_value('prop', 'string', mutate=True)
        assert vp.values['prop'] == 'string'


class TestViewPropertyDecorator:
    """Tests for the ``view_property`` decorator."""

    def test_basic_caching(self, make_view: sb.View):
        """Property is calculated once and cached until change_count changes."""
        host = _MockHost(make_view)
        # First access computes
        val1 = host.simple
        assert val1 == make_view.change_count()
        # Second access returns cached value (no recompute)
        val2 = host.simple
        assert val2 == val1

    def test_cache_invalidates_on_change(self, make_view: sb.View):
        """After editing the view, the property is recomputed."""
        host = _MockHost(make_view)
        val1 = host.simple
        make_view.run_command('append', {'characters': 'hello'})
        val2 = host.simple
        assert val2 == val1 + 1  # change_count incremented

    def test_derived_property(self, make_view: sb.View):
        """Derived property depends on simple and only reruns when simple changes."""
        host = _MockHost(make_view)
        d1 = host.derived
        assert d1 == host.simple + 100
        # No change → cached
        d2 = host.derived
        assert d2 == d1

    def test_hashed_property(self, make_view: sb.View):
        """Hashed property reruns when view size changes."""
        host = _MockHost(make_view)
        h1 = host.hashed
        assert 'size=0' in h1
        # Change content → size changes → recompute
        make_view.run_command('append', {'characters': 'hello'})
        h2 = host.hashed
        assert 'size=5' in h2

    def test_cursor_based_property(self, make_view: sb.View):
        """Eager property reruns on any change, including cursor changes."""
        host = _MockHost(make_view)
        c1 = host.cursor_based
        assert c1 == 0
        # Move cursor
        make_view.sel().clear()
        make_view.sel().add(sb.Region(3, 3))
        # Eager properties rerun on any change_count change
        c2 = host.cursor_based
        assert c2 == 3

    def test_view_property_with_scopes(self, make_view: sb.View):
        """view_property with scopes uses hash_scope_executor."""

        class _Host:
            _cache: ViewProperties
            view: sb.View

            def __init__(self, view: sb.View) -> None:
                self.view = view
                self._cache = ViewProperties()

            @view_property(scopes=('comment.line',))
            def comments(self) -> int:
                regions = self.view.find_by_selector('comment.line')
                return len(regions)

        host = _Host(make_view)
        assert host.comments == 0  # no comments yet

    def test_assert_multiple_hash_methods(self):
        """Cannot specify more than one hash method at once."""
        with pyt.raises(AssertionError):
            view_property(scopes=('comment',), hash_by_syntax=True)


class TestHashScopeExecutor:
    """Tests for ``ViewProperties._hash_scope_executor``."""

    def test_empty_view(self, make_view: sb.View):
        result = ViewProperties._hash_scope_executor(make_view, 'comment.line')
        assert result == hash(())

    def test_with_content(self, make_view: sb.View):
        make_view.run_command('append', {'characters': '# hello\n'})
        result = ViewProperties._hash_scope_executor(make_view, 'comment.line')
        assert isinstance(result, int)
