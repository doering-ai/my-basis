############
### HEAD ###
############
### STANDARD
from __future__ import annotations
from typing import ClassVar, TypeGuard
from collections.abc import Callable, Iterable
from pathlib import Path
import argparse as ap

### EXTERNAL
import pydantic as pyd
import more_itertools as mi
import regex as re

### INTERNAL
from my import RegexStore, ut, typist, Regex, Tree, GroupAtom, GroupKind, Atom

type Action = Callable[[Storefront], Iterable[str]]
_ACTIONS: dict[str, Action] = dict()


def _register_action[A: Action](fn: A) -> A:
    name = (fn.__name__ or '').strip()
    assert name, f'Action function {fn} must have a name.'
    assert name not in _ACTIONS, f'Action name {name} is already registered.'
    _ACTIONS[name] = fn
    return fn


type Pattern = re.Pattern[str]


############
### BODY ###
############
class Storefront(pyd.BaseModel):
    """Provides command-line access to RegexStore's features."""

    _ACTIONS: ClassVar[dict[str, Action]] = _ACTIONS

    store: RegexStore = RegexStore.new()

    actions: list[str] = []
    target: Path | None = None
    source: Path | None = None
    pretty_print: bool = False
    verbose: bool = False

    @pyd.field_validator('source', 'target')
    @classmethod
    def _validate_path(cls, val: str | Path | None) -> Path | None:
        return Path(str(val)).expanduser().resolve() if val else None

    @pyd.field_validator('actions')
    @classmethod
    def _validate_actions(cls, actions: str | list[str]) -> list[str]:
        _actions = set(
            filter(
                bool,
                mi.flatten(
                    ut.to_words(a.lower().strip())
                    for a in ([actions] if isinstance(actions, str) else actions)
                ),
            )
        )
        if missing := _actions - set(cls._ACTIONS.keys()):
            raise ValueError(f'Unknown actions: {missing}')

        return sorted(_actions)

    def execute_all(self) -> Iterable[str]:
        """Execute all actions in the order they were provided."""
        print(f'Executing actions: {self.actions}')
        for action_name in self.actions:
            action_fn = self._ACTIONS[action_name]
            with ut.debug_fence(f'Executing action: {action_name}', mark='==>'):
                yield from action_fn(self)

    def _do_drill(self, atom: Atom) -> TypeGuard[GroupAtom]:
        return (
            isinstance(atom, GroupAtom)
            and atom.kind in GroupKind._SIMPLE
            and atom.quantifier == ''
            and not Regex.is_split(atom.body)
        )

    @_register_action
    def condense(self) -> list[str]:
        """Build optimized branching expressions from lists of options."""
        out: list[str] = []
        assert self.source and self.target, 'Condense action requires both source and target files.'
        text = self.source.read_text().strip()
        branches = ut.to_words(text)
        assert len(branches) > 0, f'Invalid source file {self.source}.'
        print(f'Loaded {len(branches)} branches from {self.source.name}')
        self.store['storefront'] = ('<|>', branches)
        breakpoint()
        _ = self.store.load

        new_expr = str(self.store.patterns['storefront'].pattern)
        self.target.parent.mkdir(parents=True, exist_ok=True)
        self.target.write_text(new_expr)
        ut.multiprint(
            title=f'Wrote {len(new_expr)} chars to `{self.target.name}`',
            lines=[new_expr],
        )
        if self.pretty_print:
            print(' pretty_print '.center(32, '_'))
            self.store.pretty_print('storefront')
            print('_' * 32)

        return out


cls = Storefront


############
### MAIN ###
############
def _parse_args() -> Storefront:
    """Create a Storefront instance from command-line arguments."""
    parser = ap.ArgumentParser(
        'Regex Storefront',
        description="Provides command-line access to RegexStore's features.",
    )

    parser.add_argument(
        'actions',
        choices=cls._ACTIONS,
        nargs='+',
        default=[],
        help='Which function(s) to perform.',
    )
    parser.add_argument(
        '-s',
        '--source',
        default=None,
        help='The file that actions read from.',
    )
    parser.add_argument(
        '-t',
        '--target',
        default=None,
        help='The file that actions write to.',
    )
    parser.add_argument(
        '-p',
        '--pretty-print',
        '--pretty',
        '--pp',
        action='store_true',
        help='Whether to pretty-print the output (if applicable).',
    )
    parser.add_argument(
        '-v',
        '--verbose',
        action='store_true',
        help='Whether to print verbose output.',
    )

    args = parser.parse_args()

    kwargs = dict(
        actions=args.actions or [],
        target=str(args.target) if args.target else None,
        source=str(args.source) if args.source else None,
        pretty_print=args.pretty_print or False,
        verbose=args.verbose or False,
    )
    if args.verbose:
        print('KWARGS:')
        for key, val in kwargs.items():
            print(f'\t{key} ({type(val)}): {val}')
        print('')
    return cls(**kwargs)


def main() -> None:
    """Entry point for the script."""
    inst = _parse_args()
    if inst.verbose:
        print('Created Storefront instance.')
    out = '\n\n'.join(inst.execute_all())
    print(out)


if __name__ == '__main__':
    main()
