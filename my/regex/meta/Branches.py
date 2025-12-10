############
### HEAD ###
############
### STANDARD
from typing import Self, Sequence, Iterator, Generator
from collections import deque
import itertools as it
import more_itertools as mi

### EXTERNAL
import pydantic as pyd

### INTERNAL
from my import ut
from .GroupKind import GroupKind
from .meta_patterns import META_RGXS
from .Quantifier import Quantifier
from .Atom import Atom
from .Atoms import Atoms


############
### DATA ###
############
class Branches(pyd.BaseModel):
    """
    A collection of alternative "branches" for a regex position.
    Examples:
        Branches("(?:br1|br2|br3)") -> {prefix: 'br', data: ['1', '2', '3'], suffix: ''} .
    """

    prefix: Atoms = Atoms()
    data: list[Atoms] = []
    suffix: Atoms = Atoms()
    quantifier: str = ''

    # -------------------
    # `0` Initial Methods
    # -------------------
    @classmethod
    def new(
        cls,
        *args: str | Atom | Atoms | Sequence[Atoms] | Iterator[Atoms] | Self,
        factor: bool = False,
    ) -> None:
        data = []
        for arg in args:
            if isinstance(arg, str):
                data.append(Atoms.atomize(arg))
            elif isinstance(arg, Atom):
                data.append(Atoms(arg))
            elif isinstance(arg, Atoms):
                data.append(arg)
            elif isinstance(arg, Sequence):
                data.extend(map(Atoms, arg))
            elif isinstance(arg, Branches):
                data.extend(arg.data)
        ret = cls(data=data)
        if factor:
            ret.factor()

    # -------------------
    # `-` Private Methods
    # -------------------
    @staticmethod
    def greatest_common_prefix(*args: Atoms) -> Atoms:
        if not args or not all(map(len, args)):
            return Atoms()
        elif len(args) == 1:
            return args[0]
        return Atoms(mi.longest_common_prefix(args))

    @staticmethod
    def greatest_common_suffix(*args) -> Atoms:
        if not args or not all(map(len, args)):
            return Atoms()
        elif len(args) == 1:
            return args[0]

        # Reverse the contents before and after invoking the `common_prefix` library function
        common_suffix = tuple(mi.longest_common_prefix(map(reversed, args)))
        return Atoms(reversed(common_suffix))

    @staticmethod
    def _supports_atomic_grouping(atom: Atom) -> bool:
        """Determines if the given atom can be safely included in a (new) atomic group."""
        return not (atom.is_set or atom.has_complex_quantifier or atom.is_complex_group)

    def _choose_joining_mark(self) -> str:
        """
        Decides whether the given branches can be safely grouped in an atomic group.

        Args:
            branches: The list of atom sequences representing alternative branches.
        Returns:
            The group mark to use (':' for regular, '>' for atomic).
        """
        if self.suffix:
            search_space = (atom for branch in self.data for atom in branch)
        else:
            search_space = (branch.first for branch in self.data)

        return '>' if all(map(self._supports_atomic_grouping, search_space)) else ':'

    # -------------------
    # `+` Primary Methods
    # -------------------
    @classmethod
    def expand_group(cls, atom: Atom, recursive: bool = False) -> Self:
        """
        Split a group atom into branches with shared prefixes, if possible.
        """
        assert atom.is_group, f'Expected group atom, got: {atom!r}'
        if atom.has_complex_quantifier:
            return cls(data=Atoms(atom))

        data: list[Atom] = []
        if atom.is_optional:
            data.append(Atom())

        kind, start, flags, body, quant = atom.as_group()
        if kind in GroupKind._SPLITTABLE:
            data = cls.condense(body, recursive)
            if quant == '?':
                ret = (tuple(),) + ret
            if flags:
                flag_group = (f'(?{flags})',)
                ret = tuple((flag_group + branch) if branch else branch for branch in ret)

            ret = ((atom[:-1],))

        return cls(data=data)

    @classmethod
    def expand_set(cls, atom: Atom) -> Self:
        assert atom.is_set, f'Expected set atom, got: {atom!r}'
        if atom.is_complex_set or atom.has_complex_quantifier:
            return cls(data=[Atoms(atom)])

        _, body, _ = atom.as_set()
        new_data = [Atoms(atom) for atom in Atoms.atomize(body, escape=True)]
        if atom.is_optional:
            new_data.insert(0, Atoms(Atom()))

        return cls(data=new_data)

    @classmethod
    def expand_atom(cls, atom: Atom) -> Self:
        if cls._is_group(atom):
            return cls.expand_group(atom, True)
        elif cls._is_simple_set(atom):
            return cls.expand_set(atom)
        elif cls._is_optional(atom):
            return cls(data=[Atoms(Atom()), Atoms(atom.quantify(''))])
        else:
            return cls(data=Atoms(atom))

    @classmethod
    def atomic_condense(cls, atoms: Atoms) -> Atom:
        """
        Given a collection of single atoms, attempt to combine them into a more succint set-based
        expression.

        NOTE: This is a special case of condense() above where all the alternatives are themselves
        atomic.

        Examples:
            _join_atomic_branches(['a', 'b', '']) -> '[ab]?'
            _join_atomic_branches(['(?:one)', '(?:two)', 'a', 'b', '']) -> '(?:one|two|[ab])?'

        Args:
            atoms: A list of valid atom strings.
        Returns:
            The optimized regex pattern string.
        """
        # I. Determine if the resulting atom should be optional
        quantity = ''
        for i, atom in enumerate(atoms):
            if atom.is_optional:
                quantity = '?'
                atoms[i] = atom.quantify('')
            elif not atom:
                quantity = '?'

        # II. Separate chars and simple sets from groups and complex sets
        complex_atoms, simple_atoms = map(list, mi.partition(lambda atom: atom.is_simple, atoms))

        # II.ii. Combine simple atoms into a new set
        if not simple_atoms:
            branches = []
        elif len(simple_atoms) == 1:
            branches = [simple_atoms[0]]
        else:
            chars, sets = map(list, mi.partition(lambda atom: atom.is_set, simple_atoms))
            set_chars = [
                _atom for _set in sets for _atoms in cls.split_set(_set) for _atom in _atoms
            ]
            set_body = ''.join(sorted({*set_chars, *chars}))
            branches = [Atom(f'[{set_body}]')]

        branches.extend(complex_atoms)

        # III. Render the resulting set alternated w/ the complex branches
        return cls._render_branches([(b,) for b in branches], has_suffix, quantity)


    # ------------------
    # `x` Public Methods
    # ------------------
    # --------------
    # `x0` Overrides
    # --------------
    def __len__(self) -> int:
        return len(self.data)

    def __str__(self) -> str:
        return str(self.data)

    def __repr__(self) -> str:
        return f'{self.data!r}'

    def __hash__(self) -> int:
        return hash(self.data)

    def __bool__(self) -> bool:
        return bool(self.data)

    def __getitem__(self, key: slice | int) -> Self:
        cls = self.__class__
        return cls(self.data[key])

    # ---------------
    # `x1` Properties
    # ---------------
    @property
    def last(self) -> list[Atoms]:
        """Returns all the atoms tied for the final position in this object."""
        return [self.suffix] if self.suffix else self.data

    # ------------
    # `x2` Methods
    # ------------
    def group_by_prefix(self) -> Generator[Self, None, None]:
        """
        Group the given branches into buckets by their common prefixes (if any exist).
        It is assumed that branches are already given in a meaningful (and likely alphabetical)
        order, so only adjacent branches are compared.
        """
        yield from map(
            list,
            mi.split_when(self.data, lambda lhs, rhs: not self.greatest_common_prefix(lhs, rhs)),
        )

    @classmethod
    def group_by_suffix(cls, *blocks: Self) -> Generator[list[Self], None, None]:
        """Group the given blocks by their common suffixes (if any exist)."""
        yield from map(
            list,
            mi.split_when(
                blocks, lambda lhs, rhs: not cls.greatest_common_suffix(*lhs.last, *rhs.last)
            ),
        )

    def condense(self, recursive: bool = False, max_split: int = 4) -> Self:
        """
        Condense a collection of alternative branches for a regex position, combining shared
        prefixes and suffixes into non-branched expressions where possible.
        """
        # 0. Validate & normalize parameters
        if not self:
            return self

        # I. Split into initial groupings based on hard branches
        new_data: list[Atoms] = []
        for branch in mi.split_at(self.data, lambda atom: atom == '|'):
            # II. Recursively split up to one set or group to create multiple branches
            if recursive:
                new_branches = []
                n_split = 0
                for atom in branch:
                    if n_split < max_split and len(branches := self.expand_atom(atom)) > 1:
                        new_branches.append(branches)
                        n_split += 1
                    else:
                        new_branches.append(Atoms(atom))

                if n_split:
                    new_data.extend(
                        [Atoms(mi.collapse(permutation)) for permutation in it.product(*new_branches)]
                    )
                    continue

            # I.ii. Otherwise, just return this branch as one branch
            new_data.append(Atoms(branch))

        return tuple(sorted(set(new_data)) if recursive else new_data)


    # --------------
    # `x3` Modifiers
    # --------------
    def sort(self) -> Self:
        """Ensure that all branches are unique and sorted."""
        self.data = list(sorted(set(self.data)))
        return self

    def factor(self) -> Self:
        """
        Factor out common prefixes and suffixes from the branches in the main data structure,
        modifying the object's member variables.
        """
        # 0. Return immediately if this is a single branch, or if we already are factored
        if self.prefix or self.suffix or len(self) <= 1:
            return self.model_copy(deep=True)

        # I. Determine the prefix for this block, which is guaranteed to exist
        new_body = [branch.model_copy() for branch in self.data]

        if prefix := self.greatest_common_prefix(*new_body):
            new_body = [branch[len(prefix) :] for branch in new_body]
            self.prefix += prefix

        # II. Check for a shared suffix
        if suffix := self.greatest_common_suffix(*new_body):
            new_body = [branch[: -len(suffix)] for branch in new_body]
            self.suffix += suffix

        # III. Recursively construct children branches
        return self.__class__(prefix=prefix, data=new_body, suffix=suffix)


    def clean(self) -> tuple[Self, bool]:
        """
        Clean the given branches by removing empty branches and combining optional ones.
        """
        to_drop: set[int] = set()
        inferred_optional = False

        # I. Identify branches to drop or combine
        for i, branch in enumerate(self.data):
            if (n := len(branch)) == 0 or not any(branch):
                # I.i. Empty branch -- whole thing is now optional
                to_drop.add(i)
                inferred_optional = True
            elif n == 1:
                # I.ii. Single atom -- check for optionality
                atom = branch[0]
                _q = cls._quantify(atom)
                if _q == '?':
                    inferred_optional = True
                    branches[i] = (atom[:-1],)
                elif quantity in ('', '?'):
                    if _q.startswith('{0'):
                        inferred_optional = True
                        branches[i] = (atom[: -len(_q)] + '{1' + _q[2:],)
                    elif _q.startswith('*'):
                        inferred_optional = True
                        branches[i] = (atom[: -len(_q)] + f'+{_q[1:]}',)
            else:
                # I.iii. Look for a copy of this branch w/ a prefix
                candidates = [
                    j for j, j_br in enumerate(branches) if j not in to_drop and len(j_br) == n + 1
                ]
                if (j := next((j for j in candidates if branches[j][1:] == branch), -1)) != -1:
                    to_drop.add(i)
                    j_br = branches[j]
                    branches[j] = (cls._apply_quantity(j_br[0], '?'), *j_br[1:])

        # II. Combine the branches into one atomic group
        self.data = Atoms(ut.drop_at(branches, to_drop))
        return , inferred_optional

    # ------------------
    # `x4` Serialization
    # ------------------
    def render(self, has_suffix: bool = False, quantity: str = '') -> Atoms:
        """
        Render the given branches into a regex group, applying optimizations where possible.

        Args:
            branches: The list of atom sequences representing alternative branches.
            has_suffix: Whether parent context implies a shared suffix exists across all branches.
            quantity: The quantifier string to apply to the entire group.
        Returns:
            A pattern representing the properly combined & wrapped branches.
        """
        # I. Clean the branch list, identifying optional branches and pre-combining where possible
        self.clean()

        # branches, inferred_optional = , quantity)
        n = len(self)
        if n == 0:
            raise ValueError('Cannot render empty Branches object')

        elif n == 1:
            # II.
            body = branches[0]
        else:
            # II.iii. Determine whether we can safely use an atomic grouping here
            mark = self._choose_joining_mark(has_suffix)
            body = f'(?{mark}{"|".join(map("".join, branches))})'

        # III. Apply quantity mark & optionality to the group, and return
        if inferred_optional:
            body = cls._apply_quantity(body, '?')
        if quantity:
            body = cls._apply_quantity(body, quantity)

        return self.prefix + body + self.suffix

    @classmethod
    def render_all(cls, section: list[Self]) -> Atoms:
        assert (n := len(section)), 'Iterated to empty section.'

        # I. Simple/base case is that each block is handled separately
        if n == 1:
            return section[0].render()

        # II. When adjacent blocks share (part of) their suffixes, handle here
        shared_suffix = cls._greatest_common_suffix(*map(cls._block_suffix, section))
        assert shared_suffix, f'Somehow collected multiple no-suffix sections: {section}'
        branches = [
            (prefix + body + suffix)[: -len(shared_suffix)] for prefix, body, suffix in section
        ]

        # III. Render the final result with the suffix at the end
        return (cls._render_branches(branches, True), *shared_suffix)
