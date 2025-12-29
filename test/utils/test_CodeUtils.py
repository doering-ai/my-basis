############
### HEAD ###
############
### STANDARD
from pathlib import Path
from collections import deque
from functools import cached_property

### EXTERNAL
import pytest as pyt
import pydantic as pyd

### INTERNAL
from my.utils import CodeUtils

cls = CodeUtils


############
### DATA ###
############
# Test models for instance_fields and instance_aliases
class SimpleModel(pyd.BaseModel):
    name: str
    age: int
    CONSTANT: str = "not_a_field"  # Uppercase, should be excluded


class ModelWithAliases(pyd.BaseModel):
    user_name: str = pyd.Field(alias="username")
    user_age: int = pyd.Field(validation_alias="age")


class ModelWithAliasChoices(pyd.BaseModel):
    email: str = pyd.Field(validation_alias=pyd.AliasChoices("e", "email_address"))


class ModelWithAliasPath(pyd.BaseModel):
    data: str = pyd.Field(validation_alias=pyd.AliasPath("nested", "value"))


class EmptyModel(pyd.BaseModel):
    pass


# Test class for cached properties
class CachedPropsClass:
    CACHED_PROPERTIES = ["prop1", "prop2"]

    def __init__(self):
        self._value = 0

    @cached_property
    def prop1(self):
        return self._value + 1

    @cached_property
    def prop2(self):
        return self._value + 2


############
### BODY ###
############
class TestCodeUtils:
    @pyt.mark.parametrize(
        'model_cls, expected',
        [
            (SimpleModel, {"name": str, "age": int}),
            (ModelWithAliases, {"user_name": str, "user_age": int}),
            (ModelWithAliasChoices, {"email": str}),
            (ModelWithAliasPath, {"data": str}),
            (EmptyModel, {}),
        ],
    )
    def test_instance_fields(self, model_cls: type[pyd.BaseModel], expected: dict[str, type]):
        """Test extraction of instance fields from Pydantic models."""
        result = cls.instance_fields(model_cls)
        assert result == expected

    @pyt.mark.parametrize(
        'model_cls, expected',
        [
            (SimpleModel, {"name": str, "age": int}),
            (ModelWithAliases, {"username": str, "age": int}),
            (ModelWithAliasChoices, {"e": str}),
            (ModelWithAliasPath, {"nested": str}),
            (EmptyModel, {}),
        ],
    )
    def test_instance_aliases(self, model_cls: type[pyd.BaseModel], expected: dict[str, type]):
        """Test extraction of field aliases from Pydantic models."""
        result = cls.instance_aliases(model_cls)
        assert result == expected

    @pyt.mark.parametrize(
        'obj, old, new, expected_result, expected_obj',
        [
            # Test lists
            ([1, 2, 3], 2, 99, True, [1, 99, 3]),
            ([1, 2, 3], 4, 99, False, [1, 2, 3]),
            # Test nested lists
            ([[1, 2], [3, 4]], 3, 99, True, [[1, 2], [99, 4]]),
            # Test tuples (immutable, so returns True but doesn't modify original)
            ((1, 2, 3), 2, 99, True, (1, 2, 3)),
            # Test sets
            ({1, 2, 3}, 2, 99, True, {1, 99, 3}),
            # Test deques
            (deque([1, 2, 3]), 2, 99, True, deque([1, 99, 3])),
            # Test dicts
            ({"a": 1, "b": 2}, 2, 99, True, {"a": 1, "b": 99}),
            ({"a": 1, "b": 2}, 3, 99, False, {"a": 1, "b": 2}),
            # Test nested dicts
            ({"a": {"b": 2}}, 2, 99, True, {"a": {"b": 99}}),
            # Test mixed nested structures
            ({"items": [1, 2, 3]}, 2, 99, True, {"items": [1, 99, 3]}),
            ([{"val": 5}], 5, 99, True, [{"val": 99}]),
            # Test depth limit (more than 10 levels deep should not replace)
            ([[[[[[[[[[[[12]]]]]]]]]]]], 12, 99, False, [[[[[[[[[[[[12]]]]]]]]]]]])
        ],
    )
    def test_nested_replace(self, obj, old, new, expected_result: bool, expected_obj):
        """Test recursive value replacement in nested data structures."""
        result = cls.nested_replace(obj, old, new)
        assert result == expected_result
        assert obj == expected_obj

    def test_nested_replace_pydantic(self):
        """Test nested_replace with Pydantic models."""
        model = SimpleModel(name="Alice", age=30, CONSTANT="test")
        result = cls.nested_replace(model, 30, 31)
        assert result is True
        assert model.age == 31

        result = cls.nested_replace(model, "Bob", "Charlie")
        assert result is False  # "Bob" not found

    @pyt.mark.parametrize(
        'file_path, root_path, expected_module',
        [
            # Test importing a module from my/utils
            ("my/utils/CodeUtils.py", ".", "my.utils.CodeUtils"),
            ("my/utils/IterUtils.py", ".", "my.utils.IterUtils"),
        ],
    )
    def test_import_module(self, file_path: str, root_path: str, expected_module: str):
        """Test dynamic module importing from file paths."""
        file = Path(file_path)
        root = Path(root_path)
        module = cls.import_module(file, root)
        assert module.__name__ == expected_module

    @pyt.mark.parametrize(
        'props_to_clear, expected_cleared',
        [
            # Clear all cached properties using CACHED_PROPERTIES
            ([], ["prop1", "prop2"]),
            # Clear specific property
            (["prop1"], ["prop1"]),
            # Clear multiple specific properties
            (["prop1", "prop2"], ["prop1", "prop2"]),
            # Try to clear non-existent property (should not error)
            (["nonexistent"], []),
        ],
    )
    def test_clear_cached_properties(self, props_to_clear: list[str], expected_cleared: list[str]):
        """Test clearing cached properties from object instances."""
        obj = CachedPropsClass()

        # Access properties to cache them
        _ = obj.prop1
        _ = obj.prop2

        # Verify they're cached
        assert "prop1" in obj.__dict__
        assert "prop2" in obj.__dict__

        # Clear properties
        if props_to_clear:
            cls.clear_cached_properties(obj, *props_to_clear)
        else:
            cls.clear_cached_properties(obj)

        # Verify expected properties were cleared
        for prop in expected_cleared:
            if prop in ["prop1", "prop2"]:  # Only check valid properties
                assert prop not in obj.__dict__
