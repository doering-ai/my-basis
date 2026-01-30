############
### HEAD ###
############
# --------
# Standard
# --------
from pathlib import Path
import os
import re

# --------
# External
# --------
import jinja2 as jn

# --------
# Internal
# --------

############
### DATA ###
############
env = os.environ

ADMIN_DIR = Path(env.get('MY_ADMIN', '~/my/admin')).expanduser()
assert ADMIN_DIR.exists() and ADMIN_DIR.is_dir(), f'Invalid admin directory {ADMIN_DIR}'

DIARY_DIR: Path = Path(env.get('MY_DIARIES', '~/my/admin/notes/diaries')).expanduser()
assert DIARY_DIR.exists() and DIARY_DIR.is_dir(), f'Invalid diary directory {DIARY_DIR}'

templates = ADMIN_DIR / 'env/sublime/User/templates'
JINJA_ENV = jn.Environment(
    loader=jn.FileSystemLoader(str(templates)), trim_blocks=True, lstrip_blocks=True
)

RGXS = dict(
    arch_dir=re.compile(r'^_\d_[a-z]+$'),
)


############
### BODY ###
############
def ordinal(day: str) -> str:
    if re.fullmatch(r'[023]1', day):
        ordinal = 'st'
    elif re.fullmatch(r'[02]2', day):
        ordinal = 'nd'
    elif re.fullmatch(r'[02]3', day):
        ordinal = 'rd'
    else:
        ordinal = 'th'

    return day.lstrip('0') + ordinal


####################################
### COPIED FROM MYBASIS/UTILS.PY ###
####################################
# --------------------
# 5. Semantic Coercion
# --------------------
ROMAN_ARR = ['M', 'D', 'C', 'L', 'X', 'V', 'I']
ROMAN_MAP = dict(
    M=1000,
    D=500,
    C=100,
    L=50,
    X=10,
    V=5,
    I=1,
)

QUAD_RGX = re.compile(r'C{4}|X{4}|I{4}')
ROMAN_RGX = re.compile(r'(?:M{1,4}|CM|C?D|D?C{1,3}|XC|X?L|L?X{1,3}|IX|I?V|V?I{1,3})', re.IGNORECASE)


def decimal_to_roman(decimal: int) -> str:
    ans = ''
    for char, val in ROMAN_MAP.items():
        while decimal >= val:
            ans += char
            decimal -= val

        if decimal == 0:
            break

    # Fix quads of tens-places (e.g. IIII -> IV, XXXX -> XL, CCCC -> CD)
    for match in reversed(list(QUAD_RGX.finditer(ans))):
        char = match[0][0]
        d_idx = ROMAN_ARR.index(char)
        x0, x1 = match.span()
        half = ROMAN_ARR[d_idx - 1]
        if x0 > 0 and ans[x0 - 1] == half:
            ans = ans[: x0 - 1] + char + ROMAN_ARR[d_idx - 2] + ans[x1:]
        else:
            ans = ans[:x0] + char + half + ans[x1:]

    return ans


def roman_to_decimal(roman: str) -> int:
    ans = 0
    last_index = 0
    for match in ROMAN_RGX.finditer(roman):
        if match.start() != last_index:
            return 0
        else:
            last_index = match.end()

        v = [ROMAN_MAP[char] for char in match[0]]
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
