############
### HEAD ###
############
### STANDARD
import itertools as it

### EXTERNAL
import regex as re

### INTERNAL
from ..base import utils as ut
from .Buffer import Buffer
from .MatchData import MatchData
from .RegexStore import RegexStore, GroupKind


############
### BODY ###
############
def curate_rgx(
    store: RegexStore,
    atoms: tuple[str, ...],
    atom_ends: list[int],
    failed_idx: int,
    body: Buffer,
    definitions: dict[str, str],
    remaining_text: str,
) -> str:
    x0 = x1 = failed_idx
    while x0 > 0 and ut.has_any(store._quantify(atoms[x0 - 1]), '?', '*'):
        x0 -= 1

    snippet = body.slice(atom_ends[x0 - 1] if x0 else 0, atom_ends[x1])
    rgx_snippet = store.sanitize_pattern(snippet)
    invocations = store.parse_invocations(rgx_snippet)

    return '\n'.join([
        r'(?(DEFINE)',
        *[definitions[group] for group in invocations],
        rf')(?m)^{rgx_snippet}',
    ])


def debug_failed_match(store: RegexStore, name: str, rgx: str, text: Buffer) -> list[str]:
    cls = RegexStore
    output = []

    # I. Split the regex up by the root-level groups present
    head, body_rgx = rgx.split(f'(?P<{name}>', 1)
    body_rgx = body_rgx[:-1]
    body = Buffer.new(body_rgx, fence_rgxs=['arrays'])
    atoms = cls.atomize(str(body))
    while len(atoms) == 1 and cls._is_group(atoms[0]):
        kind, start, flags, group_body, quant = cls._parse_group(atoms[0])
        if kind in GroupKind._SIMPLE and quant == '' and not cls._is_split(group_body):
            body.set(group_body)
            atoms = cls.atomize(group_body)
        else:
            break
    atom_ends = list(it.accumulate(map(len, atoms)))

    # II. Iterate through the groups, matching until we fail
    n = 0
    data: MatchData = MatchData()
    for end in atom_ends:
        rgx = head + body[:end]
        match = text.match(re.compile(rgx))
        if match is not None:
            data = store.parse(match)
            n += 1
        else:
            break

    # III. Exit early if we completely failed or completely succeeded
    out_rgx = store.sanitize_pattern(head + body_rgx)
    if n == 0:
        output.extend([
            f'Returned FAILED MATCH (n={n}) for entire RGX:',
            out_rgx,
            '',
        ])
        remaining_text = str(text)
    elif n == len(atoms):
        output.extend([
            'Returned UNEXPECTED MATCH for RGX:',
            '',
            out_rgx,
            '',
            '...returning:',
            '',
            f'\t{data}',
        ])
        if data.end < len(text):
            output.extend(['Unmatched text:', text.slice(data.end, len(text))])
        return output
    else:
        output.extend([
            f'Returned PARTIAL MATCH up to clause {n}, returning data:',
            f'\t{data}',
        ])
        remaining_text = str(text.slice(data.end, len(text)))

    # IV. Return just the clauses that we think failed
    head_buf = Buffer.new(head[len('(?(DEFINE)'):-1], fence_rgxs=['arrays'])
    definitions = {
        name: head_buf.slice(*span)
        for span, _, name, _, _ in cls.group_iterator(head_buf, mask=GroupKind.PARAM, mode='roots')
    }
    curated_rgx = curate_rgx(store, atoms, atom_ends, n, body, definitions, remaining_text)
    if not curated_rgx:
        output.extend(['Failed to curate RGX:', '', out_rgx])
    else:
        output.extend([
            '-' * 80,
            'This test RGX:',
            '',
            curated_rgx,
            '',
            '...needs to match this remaining text:',
            '',
            remaining_text,
            '-' * 80,
        ])

    return output


def debug_regex(
    store: RegexStore,
    names: list[str],
    text: str,
    matched: bool,
    expected: bool = True,
    func: str = '',
) -> str:
    assert names
    _name = names[0].upper() + (f'.{func}()' if func else '')
    output: list[str] = []

    status = str(int(matched)) + str(int(expected))
    rgxs_str = '\n\n'.join(map(store.sanitize_pattern, names))
    if status == '11':
        output.extend([
            f'RGX `{_name}` returned INCORRECT results for text:',
            '',
            text,
            '',
            '...VIA PATTERN:',
            '',
            rgxs_str,
            '',
        ])

    elif status == '10':
        output.extend([
            f'RGX `{_name}` returned UNEXPECTED success for text:',
            '',
            text,
            '',
            '...VIA PATTERN:',
            '',
            rgxs_str,
            '',
        ])

    elif status == '01':
        output.extend([
            f'RGX `{_name}` returned FAILURE to match text:',
            '',
            text,
            '',
            '...VIA PATTERN:',
            '',
            rgxs_str,
            '',
        ])
        buf = Buffer.new(text, fence_rgxs=['arrays'])
        for i, name in enumerate(names):
            if len(names) > 1:
                header = f'## `{i}` output for {name.upper()} ##'
                output.extend([
                    '',
                    '#' * len(header),
                    header,
                    '#' * len(header),
                ])

            rgx = store[name].pattern
            output.extend(debug_failed_match(store, name, rgx, buf))
    else:
        raise ValueError('No match, when we expected none -- why call debug_regex_test()?')

    return '\n'.join(output)
