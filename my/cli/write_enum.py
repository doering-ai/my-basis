############
### HEAD ###
############
### STANDARD
import argparse
from pathlib import Path
import regex as re

### EXTERNAL
import pydantic as pyd

### INTERNAL
from my import Idx, ARCH, typist, aliases as al

############
### DATA ###
############
ENUM_ROOT = ARCH.get_dir(Idx('0100'))


############
### BODY ###
############
def serialize(value: dict, ancestors: list[str] = []) -> list[str]:
    lines = []
    # I. Render header for top-level groups
    if len(ancestors) == 1:
        sep = '-' * len(ancestors[0])
        lines.extend([
            '',
            f'    # {sep}',
            f'    # {ancestors[0].title()}',
            f'    # {sep}',
        ])

    # II. Render main contents
    for key, val in value.items():
        if isinstance(val, dict):
            lines.extend(serialize(val, ancestors + [key]))
        else:
            lines.append(f'    {key.upper()} = auto()  # {val}')

    # III. Render footer for all groups
    if len(ancestors) > 0:
        # Each group is a union of its contents
        union = ' | '.join(map(str.upper, value.keys()))
        lines.append(f'    {ancestors[-1].upper()} = {union}')

        # Add spacer to nested groups
        if len(ancestors) > 1:
            lines.append('')

    return lines


TARGET_RGX = re.compile(
    r'(?m)(?<=^class \w+\(MyEnum, Flag\):)(?:(?:\n+    #.*$)*\n+    [[:upper:]]{2,} = .+)+'
)


def write_out(data: dict[str, str | dict], out: pyd.FilePath) -> None:
    """ Produce a python file from a template. """
    content = '\n'.join(serialize(data))
    if out.exists():
        text = out.read_text()
        if match := TARGET_RGX.search(text):
            x0, x1 = match.span()
            out.write_text('\n'.join([text[:x0], content, text[x1:]]))
            return
        elif (n_chars := len(text.strip())) > 0:
            cont = input(f'No match found -- replace file w/ {n_chars} chars? [y/N] ')
            if not cont.lower().startswith('y'):
                print('Aborting.')
                return

    render_data = dict(
        content=content,
        depth=len(out.relative_to(ENUM_ROOT).parents),
        name=out.stem,
        flag=True,
    )
    text = ARCH.render('MyEnum.py.jinja', render_data)
    out.write_text(text)


def main():
    parser = argparse.ArgumentParser(
        description='Parse a given .yaml specification into a flag class.'
    )
    parser.add_argument('src', type=Path, help='The specification to use.')
    parser.add_argument('out', type=Path, help='Where to write the results')
    args = parser.parse_args()

    src = ENUM_ROOT / args.src
    al.validate_file(src)
    assert src.suffix == '.yaml', f'Source must be a .yaml file: {src}'

    out = ENUM_ROOT / args.out
    if not out.parent.exists():
        out.parent.mkdir(parents=True, exist_ok=True)
    assert out.suffix == '.py', f'Output must be a .py file: {out}'

    write_out(typist.from_yaml(src), out)


if __name__ == '__main__':
    main()
