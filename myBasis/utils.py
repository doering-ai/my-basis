############
### HEAD ###
############
### STANDARD
from __future__ import annotations
from typing import ClassVar, TypeVar, TYPE_CHECKING
from typing_extensions import Annotated  # noqa: UP035

if TYPE_CHECKING:
    from collections.abc import Callable

### EXTERNAL
import sublime as sb
import sublime_plugin as sbp
import regex as re
from regex import Pattern
import pydantic as pyd
from pydantic_core import core_schema as pyd_schema

### INTERNAL

re.DEFAULT_VERSION = re.VERSION1

T = TypeVar("T")

NO_ESC = r"(?<![^\\]\\)(?<!\\{3})"


def pyd_schemify(tvar: type) -> pyd.GetPydanticSchema:
    """Create Pydantic schema validator for instance type checking.

    Args:
        tvar: Type to create validator for.
    Returns:
        GetPydanticSchema validator for use with Annotated types.
    """
    return pyd.GetPydanticSchema(lambda _, __: pyd_schema.is_instance_schema(cls=tvar))


############
### BODY ###
############
# Copied from mybasis PyPi plugin (same original developer 🙂)
class Utils:
    """Simple static class for exporting typed utilities en-masse."""

    RGXS: ClassVar[dict[str, Pattern]] = dict(
        no_esc=re.compile(NO_ESC),
        roman=re.compile(
            r"(?xi:M{1,4} | CM | C?D | D?C{1,3} | XC | X?L | L?X{1,3} | IX | I?V | V?I{1,3})"
        ),
        roman_quad=re.compile(r"(?i:C{4}|X{4}|I{4})"),
        rgx_reference=re.compile(
            NO_ESC + r"\{\{\.(?P<name>[_[:lower:]][_[:lower:]\d]*)\}\}"
        ),
    )

    pyd_schemify = pyd_schemify

    @staticmethod
    def rgx_dict(
        compile_function: Callable[[str], Pattern] = re.compile,
        **kwargs: str | Pattern,
    ) -> dict[str, Pattern]:
        """Compile the expression strings in the given dictionary, mapping names to Patterns.

        Args:
            expressions: A mapping of string names to regular expressions (compiled or otherwise).
            compile_function: Function to compile patterns (default: re.compile).
            **kwargs: Additional named patterns to include.
        Returns:
            The expressions mapping with all values now compiled.
        """
        ret = {}
        for key, val in kwargs.items():
            if isinstance(val, Pattern):
                ret[key] = val
            else:
                ret[key] = compile_function(val)
        return ret

    @staticmethod
    def multi_rgx(
        *expressions: str | list[str],
        branching: bool = False,
        sep: str = r" ?",
        pre: str = "",
        suf: str = "",
    ) -> str:
        """Combine expression clauses into a single alternating group that matches any of them.

        Args:
            *expressions: Regex patterns to be combined.
            sep: Separator for joining list patterns (default: ` ?`).
            pre: Prefix to add before combined pattern (default: empty).
            suf: Suffix to add after combined pattern (default: empty).
            branching: If True, use branching group (resets group names b/w branches)
        Returns:
            Combined regex pattern in group format `(?|...)` or `(?:...)`.
        """
        parts = [
            (expr if isinstance(expr, str) else sep.join(expr)) for expr in expressions
        ]
        contents = r"|".join(parts)
        start = "?|" if branching else "?:"
        return rf"{pre}({start}{contents}){suf}"

    @staticmethod
    def define_rgx(**kwargs: str) -> str:
        """Define a regex pattern with named capture groups.

        Args:
            **kwargs: A map from group names to raw, unwrapped expresisons.
        Returns:
            A `(?(DEFINE)...)` expression ready to be concatenated to another.
        """
        if not kwargs:
            return ""
        return "".join(
            [
                r"(?(DEFINE)",
                *(rf"(?P<{name}>{expr})" for name, expr in kwargs.items()),
                r")",
            ]
        )

    ROMAN_ARR: ClassVar[str] = "MDCLXVI"
    ROMAN_MAP: ClassVar[dict[str, int]] = dict(
        M=1000, D=500, C=100, L=50, X=10, V=5, I=1
    )

    @staticmethod
    def decimal_to_roman(decimal: int) -> str:
        """Convert a decimal number to its Roman numeral representation.

        Only supports numbers up to 3999 (MMMCMXCIX).
        """
        assert decimal <= 3999, (
            f"Decimal {decimal} too large for Roman numeral form (max 3999)."
        )
        ans = ""
        for char, val in Utils.ROMAN_MAP.items():
            while decimal >= val:
                ans += char
                decimal -= val

            if decimal == 0:
                break

        # Fix quads of tens-places (e.g. IIII -> IV, XXXX -> XL, CCCC -> CD)
        for match in reversed(list(Utils.RGXS["roman_quad"].finditer(ans))):
            char = match[0][0]
            d_idx = Utils.ROMAN_ARR.index(char)
            x0, x1 = match.span()
            half = Utils.ROMAN_ARR[d_idx - 1]
            if x0 > 0 and ans[x0 - 1] == half:
                ans = ans[: x0 - 1] + char + Utils.ROMAN_ARR[d_idx - 2] + ans[x1:]
            else:
                ans = ans[:x0] + char + half + ans[x1:]

        return ans

    @staticmethod
    def roman_to_decimal(roman: str) -> int:
        """Convert a Roman numeral string to its decimal representation.

        Only supports valid Roman numeral strings up to MMMCMXCIX (3999).
        Invalid strings will return 0.
        """
        ans = 0
        last_index = 0
        for match in Utils.RGXS["roman"].finditer(roman):
            if match.start() != last_index:
                return 0
            else:
                last_index = match.end()

            v = [Utils.ROMAN_MAP[char] for char in match[0]]
            n_unique = len(set(v))
            if n_unique == 2:
                mod = v[0] * (-1 if v[1] > v[0] else 1)
                main = v[1] * (len(v) - 1)
                ans += main + mod
            elif n_unique == 1:
                ans += v[0] * len(v)
            else:
                return 0
        if last_index != len(roman):
            return 0

        return ans

    schemify = pyd_schemify

    RegionField = Annotated[sb.Region, schemify(sb.Region)]
    SelectionField = Annotated[sb.Selection, schemify(sb.Selection)]

    ViewField = Annotated[sb.View, schemify(sb.View)]
    BufferField = Annotated[sb.Buffer, schemify(sb.Buffer)]
    WindowField = Annotated[sb.Window, schemify(sb.Window)]
    EditField = Annotated[sb.Edit, schemify(sb.Edit)]

    CommandField = Annotated[sbp.Command, schemify(sbp.Command)]
    TextCommandField = Annotated[sbp.TextCommand, schemify(sbp.TextCommand)]
    WindowCommandField = Annotated[sbp.WindowCommand, schemify(sbp.WindowCommand)]
    ApplicationCommandField = Annotated[
        sbp.ApplicationCommand, schemify(sbp.ApplicationCommand)
    ]

    ListenerField = Annotated[sbp.EventListener, schemify(sbp.EventListener)]
    TextChangeListenerField = Annotated[
        sbp.TextChangeListener, schemify(sbp.TextChangeListener)
    ]
    ViewEventListenerField = Annotated[
        sbp.ViewEventListener, schemify(sbp.ViewEventListener)
    ]

    InputHandlerField = Annotated[
        sbp.CommandInputHandler, schemify(sbp.CommandInputHandler)
    ]
    TextInputHandlerField = Annotated[
        sbp.TextInputHandler, schemify(sbp.TextInputHandler)
    ]
    ListInputHandlerField = Annotated[
        sbp.ListInputHandler, schemify(sbp.ListInputHandler)
    ]

    # Non-sublime types
    RegexField = Annotated[re.Pattern, schemify(re.Pattern)]
