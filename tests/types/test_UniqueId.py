############
### HEAD ###
############
### STANDARD
from uuid import uuid4

### EXTERNAL
import pydantic as pyd
import pytest as pyt

### INTERNAL
from my.types import UniqueId

############
### BODY ###
############


class TestUniqueId:
    @pyt.mark.parametrize(
        'uid_str,expected',
        [
            ('12345678-1234-1234-1234-123456789012', True),
            ('abcdef12-3456-7890-abcd-ef1234567890', True),
            ('ABCDEF12-3456-7890-ABCD-EF1234567890', True),
            ('00000000-0000-0000-0000-000000000000', True),
            ('ffffffff-ffff-ffff-ffff-ffffffffffff', True),
            # Invalid formats
            ('12345678-1234-1234-1234-12345678901', False),  # Too short
            ('12345678-1234-1234-1234-1234567890123', False),  # Too long
            ('12345678-1234-1234-1234', False),  # Missing segments
            ('12345678-1234-1234-1234-123456789012-', False),  # Extra hyphen
            ('12345678_1234_1234_1234_123456789012', False),  # Wrong separator
            ('12345678-1234-1234-1234-12345678901g', False),  # Invalid hex character
            ('', False),  # Empty string
            ('not-a-uuid', False),  # Completely invalid
        ],
    )
    def test_validate_uid(self, uid_str: str, expected: bool):
        """Test UUID validation with various valid and invalid formats."""
        if expected:
            # Should not raise an exception
            uid = UniqueId(uid_str)
            assert str(uid) == uid_str.lower()
        else:
            # Should raise an assertion error due to validation
            with pyt.raises(pyd.ValidationError):
                UniqueId(uid_str)

    def test_new_creates_valid_uuid(self):
        """Test that the new() classmethod creates a valid UUID."""
        uid = UniqueId.new()
        assert isinstance(uid, UniqueId)
        # Verify it matches the UUID pattern
        assert uid.RGX.match(str(uid))

        # Test that multiple calls create different UUIDs
        uid2 = UniqueId.new()
        assert uid != uid2

    @pyt.mark.parametrize(
        'uid1,uid2,expected',
        [
            ('12345678-1234-1234-1234-123456789012', '12345678-1234-1234-1234-123456789012', True),
            ('12345678-1234-1234-1234-123456789012', '12345678-1234-1234-1234-123456789013', False),
            (
                'abcdef12-3456-7890-abcd-ef1234567890',
                'ABCDEF12-3456-7890-ABCD-EF1234567890',
                True,
            ),  # Case insensitive
        ],
    )
    def test_equality_with_unique_id(self, uid1: str, uid2: str, expected: bool):
        """Test equality comparison between UniqueId instances."""
        u1 = UniqueId(uid1)
        u2 = UniqueId(uid2)
        assert (u1 == u2) == expected
        assert (u2 == u1) == expected  # Test symmetry

    @pyt.mark.parametrize(
        'uid_str,other,expected',
        [
            ('12345678-1234-1234-1234-123456789012', '12345678-1234-1234-1234-123456789012', True),
            ('12345678-1234-1234-1234-123456789012', '12345678-1234-1234-1234-123456789013', False),
            ('12345678-1234-1234-1234-123456789012', 12345678, False),  # int comparison
            ('12345678-1234-1234-1234-123456789012', None, False),  # None comparison
            ('12345678-1234-1234-1234-123456789012', [], False),  # List comparison
        ],
    )
    def test_equality_with_other_types(self, uid_str: str, other, expected: bool):
        """Test equality comparison with strings and other types."""
        uid = UniqueId(uid_str)
        assert (uid == other) == expected

    @pyt.mark.parametrize(
        'uid1,uid2,expected',
        [
            ('00000000-0000-0000-0000-000000000000', '00000000-0000-0000-0000-000000000001', True),
            ('00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000000', False),
            ('12345678-1234-1234-1234-123456789012', '12345678-1234-1234-1234-123456789013', True),
            ('abcdef12-3456-7890-abcd-ef1234567890', 'abcdef12-3456-7890-abcd-ef1234567891', True),
            ('12345678-1234-1234-1234-123456789012', '12345678-1234-1234-1234-123456789012', False),
        ],
    )
    def test_less_than_comparison(self, uid1: str, uid2: str, expected: bool):
        """Test less than comparison between UniqueId instances and strings."""
        u1 = UniqueId(uid1)
        u2 = UniqueId(uid2)
        assert (u1 < u2) == expected

        # Also test comparison with string
        assert (u1 < uid2) == expected

    def test_hash_consistency(self):
        """Test that hash values are consistent and equal for equal objects."""
        uid_str = '12345678-1234-1234-1234-123456789012'
        uid1 = UniqueId(uid_str)
        uid2 = UniqueId(uid_str)

        # Equal objects should have equal hashes
        assert hash(uid1) == hash(uid2)

        # Hash should be consistent across calls
        assert hash(uid1) == hash(uid1)

        # Different objects should (likely) have different hashes
        uid3 = UniqueId.new()
        assert hash(uid1) != hash(uid3)

    def test_string_representation(self):
        """Test string and repr methods."""
        uid_str = '12345678-1234-1234-1234-123456789012'
        uid = UniqueId(uid_str)

        assert str(uid) == uid_str
        assert repr(uid) == uid_str

    @pyt.mark.parametrize(
        'text,expected',
        [
            ('', ''),
            ('No UIDs here', 'No UIDs here'),
            ('Line with UID: 12345678-1234-1234-1234-123456789012', ''),
            (
                'First line\nLine with UID: 12345678-1234-1234-1234-123456789012\nLast line',
                'First line\nLast line',
            ),
            (
                'Multiple\nLines with: 12345678-1234-1234-1234-123456789012\nAnd another: abcdef12-3456-7890-abcd-ef1234567890\nClean line',  # noqa: E501
                'Multiple\nClean line',
            ),
            ('UUID at start: 12345678-1234-1234-1234-123456789012', ''),
            (
                'Some text before\n12345678-1234-1234-1234-123456789012 UUID in middle\nAfter',
                'Some text before\nAfter',
            ),
        ],
    )
    def test_remove_uids(self, text: str, expected: str):
        """Test removal of lines containing UIDs from text."""
        result = UniqueId.remove_uids(text)
        print(UniqueId.UID_LINE_RGX.pattern)
        assert result == expected

    def test_remove_uids_preserves_non_uid_lines(self):
        """Test that remove_uids preserves lines without UIDs."""
        text = '\n'.join(
            [
                'Line 1',
                'Line 2',
                'Line with UUID: 12345678-1234-1234-1234-123456789012',
                'Line 4',
                'Another UUID line: abcdef12-3456-7890-abcd-ef1234567890',
                'Line 6',
            ]
        )

        expected = '\n'.join(['Line 1', 'Line 2', 'Line 4', 'Line 6'])

        result = UniqueId.remove_uids(text)
        assert result == expected

    def test_integration_with_uuid4(self):
        """Test that new() creates UUIDs that are compatible with uuid4."""
        uid = UniqueId.new()

        # Should be able to create a new UniqueId from a uuid4
        py_uuid = uuid4()
        uid_from_uuid = UniqueId(str(py_uuid))
        assert str(uid_from_uuid) == str(py_uuid)

        # Verify the created UID follows UUID4 format
        uid_str = str(uid)
        parts = uid_str.split('-')
        assert len(parts) == 5
        assert tuple(map(len, parts)) == (8, 4, 4, 4, 12)
