############
### HEAD ###
############
### STANDARD
from collections.abc import Callable
from regex import Pattern

### EXTERNAL
import pydantic as pyd

### INTERNAL
from ..MatchData import MatchData


############
### BODY ###
############
class ParseData(pyd.BaseModel):
    """Private data structure for intermediate storage of match data during parsing.

    Holds captured values and their start positions while parsers are being applied.
    Supports merging, rearranging, and transforming captures based on parser functions.

    It is available for use via the public API, but should only really be useful if you're looking
    to extend `RegexStore`s parsing functionality considerably.
    """

    #: Current captured fields and their values.
    captures: dict[str, list[str]] = {}

    #: The start positions (within the original string) of the captured values.
    starts: dict[str, list[int]] = {}

    #: The cached name of the field that is currently being processed.
    field: str = ''

    #: Cached values.
    value: list[str] = []

    #: Cached start positions.
    start: list[int] = []

    # -------------------
    # `.` Initial Methods
    # -------------------

    # -------------------
    # `-` Private Methods
    # -------------------
    def interleave(self, src: str, dest: str, effects: list[tuple[int, str]]) -> None:
        """Merge new captures into destination field, maintaining position order.

        Optionally consumes values from a source field, moving them to the destination
        field while preserving the order of all captures by their start positions.

        Args:
            src: Source field to consume from (empty string to skip consumption).
            dest: Destination field to add captures to.
            effects: List of (start_position, value) tuples to add.
        """
        # I. Delete values that we have "consumed" here"
        if src and src[0] != '_' and src in self.captures:
            _starts = [start for start, _ in effects]
            src_updates = [
                tup
                for tup in zip(self.starts[src], self.captures[src], strict=True)
                if tup[0] not in _starts
            ]
            if src_updates:
                self.starts[src] = [start for start, _ in src_updates]
                self.captures[src] = [val for _, val in src_updates]
            else:
                del self.captures[src]
                del self.starts[src]

        # II. Add existing values into the mix, and sort
        if dest in self.captures:
            effects = sorted([*zip(self.starts[dest], self.captures[dest], strict=True), *effects])

        # III. Replace the values with the new ones
        self.starts[dest] = [start for start, _ in effects]
        self.captures[dest] = [val for _, val in effects]

    # -------------------
    # `+` Primary Methods
    # -------------------
    def apply_dict_parser(self, parser: dict[str, str], rgx: Pattern) -> None:
        """Apply a dictionary parser that remaps captured groups.

        Re-matches each captured value with the pattern, then uses the parser dict
        to move captures from source fields to destination fields.

        Args:
            parser: Mapping from destination field names to source field names.
            rgx: Pattern to re-match captured values with.
        """
        matches = [MatchData(match=rgx.fullmatch(val)) for val in self.value]
        trips: list[tuple[str, int, str]] = []
        trips = [
            (key, start + rel_start, value)
            for start, data in zip(self.start, matches, strict=True)
            for key, values in data.items()
            for rel_start, value in zip(data.starts(key), values, strict=True)
        ]

        affected_fields = set(parser.keys()) & {key for key, _, _ in trips}
        for dest in affected_fields:
            src = parser[dest]
            self.interleave(src, dest, [t[1:] for t in trips if t[0] == src])

    def apply_func_parser(self, parser: Callable[[str], dict[str, str] | str]) -> None:
        """Apply a function parser to transform captured values.

        Supports two types of parsers:
        - Functions returning dicts create new named captures from each value
        - Functions returning strings replace values in place

        Args:
            parser: Function transforming each captured string.
        """
        results = list(map(parser, self.value))
        if isinstance(results[0], dict):
            # I. A regex function that returns new captures
            dict_results: list[dict[str, str]] = results
            pairs = list(zip(self.start, dict_results, strict=True))

            affected_fields = {key for result in dict_results for key in result.keys()}
            src = self.field if self.field not in affected_fields else ''

            for dest in affected_fields:
                effects = [(start, result[dest]) for start, result in pairs if dest in result]
                self.interleave(src, dest, effects)
        else:
            # II. A simple substring function that just returns a new value for this name
            str_results: list[str] = results
            self.starts[self.field] = self.start
            self.captures[self.field] = str_results

    # ------------------
    # `*` Public Methods
    # ------------------
    def __contains__(self, field: str) -> bool:
        return field in self.captures and field in self.starts

    def __len__(self) -> int:
        return len(self.captures)

    def items(self) -> list[tuple[str, tuple[list[int], list[str]]]]:
        """Get all captured items as (field_name, (starts, values)) tuples."""
        return [(key, (self.starts[key], captures)) for key, captures in self.captures.items()]

    def keys(self) -> list[str]:
        """Get all captured field names."""
        return list(self.captures.keys())

    def values(self) -> list[tuple[list[int], list[str]]]:
        """Get all captured values as (starts, values) tuples."""
        return [tup for key, tup in self.items()]

    def set_field(self, field: str) -> None:
        """Set the active field for processing, extracting its data.

        Args:
            field: Name of field to make active.
        Raises:
            AssertionError: If field is not in captures.
        """
        assert field in self, f'Invalid field: {field}'
        self.field = field
        self.value = self.captures.pop(field)
        self.start = self.starts.pop(field)
