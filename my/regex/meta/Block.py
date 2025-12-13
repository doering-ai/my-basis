############
### HEAD ###
############
### STANDARD
from typing import Self, Sequence, Iterator, Generator, Iterable
import itertools as it
import more_itertools as mi
import functools as ft

### EXTERNAL
import pydantic as pyd

### INTERNAL
from ...utils import ut
from .GroupKind import GroupKind
from .Quantifier import Quantifier
from .Atom import Atom
from .Atoms import Atoms


############
### DATA ###
############
class Block(pyd.BaseModel):
    """
    A collection of alternative "branches" for a regex position.
    Examples:
        Block("(?:br1|br2|br3)") -> {prefix: 'br', branches: ['1', '2', '3'], suffix: ''} .
    """

    prefix: Atoms = Atoms()
    branches: list[Atoms] = []
    suffix: Atoms = Atoms()
    quantifier: Quantifier = Quantifier()

    # -------------------
    # `0` Initial Methods
    # -------------------
    @classmethod
    def new(
        cls,
        *args: str | Atom | Atoms | Sequence[Atoms] | Iterator[Atoms] | Self,
        **kwargs: Atoms | Quantifier,
    ) -> Self:
        branches = []
        for arg in args:
            if isinstance(arg, cls):
                # I. Copy from existing structures
                branches.extend(arg.branches)
            elif isinstance(arg, Atom):
                # II. Singular branches
                branches.append(Atoms(arg))
            elif isinstance(arg, (Sequence | Iterator)) and not isinstance(arg, str):
                # III. Handle args that represent multiple branches
                branches.extend(map(Atoms, arg))
            elif isinstance(arg, (Atoms | str)):
                # IV. Handle args that MAY represent multiple branches (using r'|')
                atoms = Atoms.atomize(arg)
                branches.extend(atoms.split())
            else:
                raise TypeError(f'Unsupported type for Branches initialization: {type(arg)}')

        return cls(branches=branches, **kwargs)

    def copy_context(self) -> Self:
        """Copy just the context (prefix, suffix, quantifier) of this block to a new instance."""
        return self.model_copy(update=dict(branches=[]), deep=True)

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
            search_space = (atom for branch in self.branches for atom in branch)
        else:
            search_space = (branch.first for branch in self.branches)

        return '>' if all(map(self._supports_atomic_grouping, search_space)) else ':'

    @classmethod
    def _is_clone_with_prefix(cls, lhs: Atoms, rhs: Atoms) -> bool:
        return bool(lhs and rhs) and len(rhs) == len(lhs) + 1 and rhs[1:] == lhs

    @classmethod
    def group_branches_by_prefix(cls, *branches: Atoms) -> Generator[list[Atoms], None, None]:
        """
        Group the given branches into buckets by their common prefixes (if any exist).
        It is assumed that branches are already given in a meaningful (and likely alphabetical)
        order, so only adjacent branches are compared.

        Yields:
            Lists of atoms, each representing a contiguous subset of this block's branches.
        """
        _split = lambda lhs, rhs: not cls.greatest_common_prefix(lhs, rhs)
        yield from mi.split_when(branches, _split)

    @classmethod
    def group_blocks_by_suffix(cls, *blocks: Self) -> Generator[list[Self], None, None]:
        """
        Group the given blocks by their common suffixes (if any exist).
        Uses the main body branches of a block for this purpose if it lacks a suffix.

        Yields:
            Lists of Block instances, each representing a contiguous subset of the given blocks.
        """
        _split = lambda lhs, rhs: not cls.greatest_common_suffix(*lhs.last, *rhs.last)
        yield from map(list, mi.split_when(blocks, _split))

    # -------------------
    # `+` Primary Methods
    # -------------------
    @classmethod
    def expand_group(cls, atom: Atom) -> Self:
        """
        Split a group atom into branches with shared prefixes, if possible.
        """
        # 0. Validate
        assert atom.is_group, f'Expected group atom, got: {atom!r}'
        if atom.has_complex_quantifier:
            return cls.new(atom)
        result: list[Atoms] = []

        # I. Expand out optional quantifier into a new branch
        if atom.quantifier == '?':
            result.append(Atoms.empty())

        kind, _, flags, body, _ = atom.as_group()
        if kind in GroupKind._SPLITTABLE:
            # II.i. Do the actual expansion
            blocks = cls.new(body).expand()

            # II.ii. Reapply any inline flags from the group start to each branch
            if flags:
                flag_atom = Atom(f'(?{flags})')
                for block in filter(bool, blocks):
                    block.branches.insert(0, flag_atom)
        else:
            result.append(Atoms(atom.quantify('')))

        return cls.new(*result)

    @classmethod
    def expand_set(cls, atom: Atom) -> Self:
        # 0. Validate
        assert atom.is_set, f'Expected set atom, got: {atom!r}'
        if atom.is_complex_set or atom.has_complex_quantifier:
            return cls.new(atom)
        result: list[Atoms] = []

        # I. Expand out optional quantifier into a new branch
        if atom.quantifier == '?':
            result.append(Atoms.empty())

        # II. Atomize the set body into individual atomic branches
        _, body, _ = atom.as_set()
        result.extend(map(Atoms, Atoms.atomize(body, escape=True)))
        # TODO: What about set-specific syntax, like posix groups?

        return cls.new(*result)

    @classmethod
    def expand_atom(cls, atom: Atom) -> Self:
        if atom.is_group:
            return cls.expand_group(atom)
        elif atom.is_simple_set:
            return cls.expand_set(atom)
        elif atom.is_optional:
            return cls.new(Atoms.empty(), Atoms(atom.as_required()))
        else:
            return cls.new(atom)

    @classmethod
    def collapse_atoms(cls, *args: Atom) -> Atom:
        """
        Given a collection of single atoms, attempt to combine them into a more succint set-based
        expression.

        NOTE: This is a special case of condense() above where all the alternatives are themselves
        atomic.

        Examples:
            _collapse_atomic_branches(['a', 'b', '']) -> '[ab]?'
            _collapse_atomic_branches(['(?:one)', '(?:two)', 'a', 'b', '']) -> '(?:one|two|[ab])?'

        Args:
            atoms: A list of valid atom strings.
        Returns:
            The optimized regex pattern string.
        """
        # I. Determine if the resulting atom should be optional
        quantity = ''
        to_drop = set()
        atoms = list(args)
        for i, atom in enumerate(atoms):
            if atom.quantifier == '?':
                quantity = '?'
                atoms[i] = atom.quantify('')
            elif not atom:
                to_drop.add(i)
                quantity = '?'
        if to_drop:
            atoms = ut.drop_at(atoms, to_drop)

        # II. Separate chars and simple sets from groups and complex sets
        complex_atoms, simple_atoms = map(list, mi.partition(lambda atom: atom.is_simple, atoms))

        # III. Combine the results
        branches: list[Atom]
        if not simple_atoms:
            # III.i. Null case
            branches = []
        elif len(simple_atoms) == 1:
            # III.ii. Singular case
            branches = [simple_atoms[0]]
        else:
            # III.iii. Main case: create a single set atom representing all these branches
            chars, sets = map(set, mi.partition(lambda atom: atom.is_set, simple_atoms))
            set_branches = chars
            if sets:
                set_branches.extend(
                    branch.first for _set in sets for branch in cls.expand_set(_set)
                )
            branches = [Atom(f'[{"".join(sorted(set_branches))}]')]

        # III. Render the resulting set alternated w/ the complex branches
        new_branch_obj = cls.new(*branches, *complex_atoms)
        rendered_atoms = new_branch_obj.render(quantity=quantity)
        return rendered_atoms.one

    @classmethod
    def collapse_blocks_by_suffix(cls, blocks: list[Self]) -> list[Atoms]:
        ret = []
        for group in cls.group_blocks_by_suffix(*blocks):
            n = len(group)
            if n == 0:
                raise ValueError('Somehow collected an empty block group')
            if n == 1:
                ret.append(group[0].render())
            else:
                # II. Factor out shared suffixes between *blocks* (usually only checking branches
                #     within them, as in `factor()`)
                shared_suffix = cls._greatest_common_suffix(*(br.last for br in group))
                assert (shared_len := len(shared_suffix)), 'Grouped blocks with no shared suffix.'
                for block in group:
                    if block.suffix:
                        block.suffix = block.suffix[:-shared_len]
                    else:
                        block.branches = [br[:-shared_len] for br in block.branches]

                # III. Render the final result with the suffix at the end
                sub_branches = [block.render() for block in group]
                ret.append(f'(?:{sub_branches})', *shared_suffix)
        return ret

    def make_optional(self) -> bool:
        """
        Attempt to set the quantifier for this block to an optional version of itself.

        Returns:
            True if the quantifier is optional, False if this is not possible (e.g. '{3,5}')
        """
        if self.quantifier.is_optional:
            return True
        elif (new_quant := self.quantifier.as_optional()) is not None:
            self.quantifier = new_quant
            return True
        return False

    # ------------------
    # `x` Public Methods
    # ------------------
    # --------------
    # `x0` Overrides
    # --------------
    def __len__(self) -> int:
        return len(self.branches)

    def __str__(self) -> str:
        return str(self.render())

    def __repr__(self) -> str:
        return f'{self.branches!r}'

    def __hash__(self) -> int:
        return hash(self.branches)

    def __bool__(self) -> bool:
        return any(map(bool, self.branches))

    @ft.singledispatchmethod
    def __getitem__(self, key):
        raise TypeError

    @__getitem__.register
    def _get_branch(self, key: int) -> Atoms:
        return self.branches[key]

    @__getitem__.register
    def _get_branches(self, key: slice) -> Self:
        return self.new(*self.branches[key])

    @property
    def lengths(self) -> list[int]:
        return list(map(len, self.branches)) if self else []

    @property
    def max_length(self) -> int:
        return max(*self.lengths) if self else 0

    @property
    def last(self) -> list[Atoms]:
        """Returns all the atoms tied for the final position in this object."""
        return [self.suffix] if self.suffix else self.branches

    # --------------
    # `x1` Modifiers
    # --------------
    def sort(self) -> Self:
        """Ensure that all branches are unique and sorted."""
        self.branches = list(sorted(set(self.branches)))
        return self

    def clean(self) -> Self:
        """
        Clean the given branches by removing empty branches and combining optional ones.
        Uses the parent's context to allow for further optimizations that are only valid in the
        given context.

        Returns:
            A quantifier that can be applied to the whole set of branches.
        """
        to_drop: set[int] = set()

        # I. Identify branches to drop or combine
        for i, branch in enumerate(self.branches):
            if not branch:
                # I.i. Empty branch -- whole thing is now optional, if that's possible
                if self.make_optional():
                    to_drop.add(i)
            elif len(branch) == 1:
                # I.ii. Single atom -- check for optionality
                if branch.one.is_optional and self.make_optional():
                    self.branches[i] = Atoms(branch.one.as_required())
            else:
                # I.iii. Look for a copy of this branch w/ a prefix
                for j, other_branch in enumerate(self.branches):
                    if j in to_drop or j == i:
                        continue
                    elif self._is_clone_with_prefix(branch, other_branch):
                        to_drop.add(i)
                        self.branches[j][0] = other_branch[0].optional()

        if to_drop:
            self.branches = ut.drop_at(self.branches, to_drop)
        return self

    def expand(self, max_split: int = 4) -> Self:
        """"""
        if not self:
            return self

        new_data: list[Atoms] = []
        for branch in self.branches:
            expanded_atoms: list[list[Atom]] = []
            n_split = 0

            # I. Split any sets and groups we can find into nested branch objects
            for atom in branch.data:
                if n_split < max_split and len(sub_block := self.expand_atom(atom)) > 1:
                    expanded_atoms.append(sub_block.render().data)
                    n_split += 1
                else:
                    expanded_atoms.append([atom])

            # II. Reconstruct the branches from the expanded atoms
            if n_split:
                # II.i. If any atoms were split, record all possible permutations
                new_data.extend(
                    Atoms(mi.collapse(permutation)) for permutation in it.product(*expanded_atoms)
                )
            else:
                # II.ii. For all non-splittable atoms, just add them as-is
                new_data.append(branch)

        # III. Save to instance variables and sort the results (allowed b/c they're alternated)
        self.branches = new_data
        self.sort()
        return self

    @classmethod
    def expand_branches(cls, branches: Iterable[str]) -> Self:
        block = cls.new(*sorted(set(branches)))
        return block.expand()

    def factor(self) -> Self:
        """
        Factor out common prefixes and suffixes from the branches in the main data structure,
        modifying the object's member variables.
        """
        # 0. Return immediately if this is a single branch, or if we already are factored
        if self.prefix or self.suffix or len(self) <= 1:
            return self

        # I. Determine the prefix for this block (which should always exist if this func is called)
        if prefix := self.greatest_common_prefix(*self.branches):
            self.branches = [branch[len(prefix) :] for branch in self.branches]
            self.prefix += prefix

        # II. Check for a shared suffix
        if suffix := self.greatest_common_suffix(*self.branches):
            self.branches = [branch[: -len(suffix)] for branch in self.branches]
            self.suffix = suffix + self.suffix

        # III. Check for a shared quantifier
        if not self.quantifier and self.max_length == 1:
            quantifiers = {branch.one.quantifier for branch in self.branches if branch}
            if len(quantifiers) == 1 and (common_quantifier := quantifiers.pop()):
                self.quantifier = common_quantifier
                for branch in self.branches:
                    branch[0] = branch[0].quantify('')

        return self

    def build_router_tree(self) -> Self:
        """
        Construct an optimized regex from branches by factoring common prefixes and suffixes.

        This method builds an efficient regex pattern by identifying and extracting common
        prefixes and suffixes from multiple branches, minimizing redundancy in the result.

        Args:
            block:
        Returns:
            Optimized regex string with factored common elements.
        """
        cls = self.__class__

        # I. Prepare the block; the main stage is the "factor" step, where prefixes are found
        self.clean()
        self.factor()

        # II. Recursively replace the block's body with an equivalent tree
        if len(self) == 1:
            # II.i. Singular case: return it as-is
            pass
        elif self.max_length == 1:
            # II.ii. Atomic case: join them directly, as there are unique opportunities
            union = cls.collapse_atoms(*(branch.first for branch in self.branches))
            self.branches = [Atoms(union)]
        else:
            # II.iii. Main case: recurse into groups that share a prefix, then factor out shared
            #         suffixes of those results before returning
            children = [
                cls(branches=branches).build_router_tree()
                for branches in cls.group_branches_by_prefix(*self.branches)
            ]
            self.branches = cls.collapse_blocks_by_suffix(children)

        return self

    # ------------------
    # `x2` Serialization
    # ------------------
    def render(self) -> Atoms:
        """
        Render the given branches into a regex group, applying optimizations where possible.

        Args:
            branches: The list of atom sequences representing alternative branches.
            quantity: The quantifier string to apply to the entire group.
        Returns:
            A pattern representing the properly combined & wrapped branches.
        """
        # I. Clean the branch list, identifying optional branches and pre-combining where possible
        if not self:
            raise ValueError('Cannot render empty Branches object')
        elif len(self) == 1:
            # II.i. Singular branch -- no need to choose a mark
            ret = self.branches[0]
        else:
            # II.ii. Determine whether we can safely use an atomic grouping here
            mark = self._choose_joining_mark()
            ret = Atoms(f'(?{mark}{r"|".join(map(str, self.branches))})')

        # III. Add contextual details (prefix, suffix, quantifier)
        if self.prefix or self.suffix:
            ret = self.prefix + ret + self.suffix

        if self.quantifier:
            ret = Atoms.quantify(ret, self.quantifier)
        return ret

    # ------------------
    # `x3` Top-level API
    # ------------------
