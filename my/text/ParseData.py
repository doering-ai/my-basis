############
### HEAD ###
############
### STANDARD
from typing import Callable
from regex import Pattern

### EXTERNAL
import pydantic as pyd

### INTERNAL
from .MatchData import MatchData

############
### DATA ###
############
Params = dict[str, str]
Captures = dict[str, list[str]]


############
### BODY ###
############
class ParseData(pyd.BaseModel):
    # Dynamic values
    captures: Captures = {}
    starts: dict[str, list[int]] = {}

    # Per-field cache values
    field: str = ''
    value: list[str] = []
    start: list[int] = []

    def __contains__(self, field: str) -> bool:
        return field in self.captures and field in self.starts

    def __len__(self) -> int:
        return len(self.captures)

    def items(self) -> list[tuple[str, tuple[list[int], list[str]]]]:
        return [(key, (self.starts[key], captures)) for key, captures in self.captures.items()]

    def keys(self) -> list[str]:
        return list(self.captures.keys())

    def values(self) -> list[tuple[list[int], list[str]]]:
        return [tup for key, tup in self.items()]

    def set_field(self, field: str) -> None:
        assert field in self, f'Invalid field: {field}'
        self.field = field
        self.value = self.captures.pop(field)
        self.start = self.starts.pop(field)

    def apply_dict_parser(self, parser: dict[str, str], rgx: Pattern) -> None:
        matches = [MatchData(match=match) for match in map(rgx.fullmatch, self.value)]
        trips: list[tuple[str, int, str]] = []
        trips = list((key, start + rel_start, value)
                     for start, data in zip(self.start, matches)
                     for key, values in data.items()
                     for rel_start, value in zip(data.starts(key), values))

        affected_fields = (set(parser.keys()) & {key for key, _, _ in trips})
        for dest in affected_fields:
            src = parser[dest]
            self.interleave(src, dest, [t[1:] for t in trips if t[0] == src])

    def apply_func_parser(self, parser: Callable[[str], dict[str, str] | str]) -> None:
        results = list(map(parser, self.value))
        if isinstance(results[0], dict):
            # I. A regex function that returns new captures
            dict_results: list[dict[str, str]] = results  # type: ignore
            pairs = list(zip(self.start, dict_results))

            affected_fields = {key for result in dict_results for key in result.keys()}
            src = self.field if self.field not in affected_fields else ''

            # Handle by field instead of by result
            for dest in affected_fields:
                effects = [(start, result[dest]) for start, result in pairs if dest in result]
                self.interleave(src, dest, effects)
        else:
            # III. A simple substring function that just returns a new value for this name
            str_results: list[str] = results  # type: ignore
            self.starts[self.field] = self.start
            self.captures[self.field] = str_results

    def interleave(self, src: str, dest: str, effects: list[tuple[int, str]]) -> None:
        """
        Adds the given value to an existing captures list, respecting the order of appearance
        in the source string of each match.
        """
        # I. Delete values that we have "consumed" here"
        if src and src[0] != '_' and src in self.captures:
            _starts = [start for start, _ in effects]
            src_updates = [
                tup for tup in zip(self.starts[src], self.captures[src]) if tup[0] not in _starts
            ]
            if src_updates:
                self.starts[src] = [start for start, _ in src_updates]
                self.captures[src] = [val for _, val in src_updates]
            else:
                del self.captures[src]
                del self.starts[src]

        # II. Add existing values into the mix, and sort
        if dest in self.captures:
            effects = sorted([*zip(self.starts[dest], self.captures[dest]), *effects])

        # III. Replace the values with the new ones
        self.starts[dest] = [start for start, _ in effects]
        self.captures[dest] = [val for _, val in effects]
