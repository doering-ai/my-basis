############
### HEAD ###
############
### STANDARD
from typing import Self, Sequence, Iterator, Generator, Iterable, Any
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
from .GroupAtom import GroupAtom
from .SetAtom import SetAtom
from .Regex import Regex


############
### DATA ###
############
class Block(pyd.BaseModel):
    """
    A collection of alternative "branches" for a regex position.
    Examples:
        Block("(?:br1|br2|br3)") -> {prefix: 'br', branches: ['1', '2', '3'], suffix: ''} .
    """

    prefix: Regex = Regex()
    branches: list[Regex] = []
    suffix: Regex = Regex()
    quantifier: Quantifier = Quantifier()

    # -------------------
    # `0` Initial Methods
    # -------------------
    @classmethod
    def new(
        cls,
        *args: str | Atom | Regex | Sequence[Regex] | Iterator[Regex] | Self,
        **kwargs: Any,
    ) -> Self:
        return cls(
            branches=list(mi.flatten(map(cls._parse_arg, args))),
            **kwargs,
        )

    def copy_context(self) -> Self:
        """Copy just the context (prefix, suffix, quantifier) of this block to a new instance."""
        return self.model_copy(update=dict(branches=[]), deep=True)

    # -------------------
    # `-` Private Methods
    # -------------------
    @classmethod
    def _parse_arg(
        cls, arg: str | Atom | Regex | Sequence[Regex] | Iterator[Regex] | Self
    ) -> Generator[Regex, None, None]:
        # I. Copy from existing structures
        if isinstance(arg, cls):
            yield from arg.branches

        # II. Singular branches
        elif isinstance(arg, Atom):
            yield Regex(arg)

        # III. Handle args that MAY represent multiple branches (using r'|')
        elif isinstance(arg, (Regex, str)):
            yield from Regex(arg).split()
        elif isinstance(arg, (Sequence, Iterator)):
            # Assume each Regex object is its own branch
            for subarg in arg:
                yield from cls._parse_arg(subarg)

            # yield from Regex(*arg).split()
        else:
            raise TypeError(f'Unsupported type for Branches initialization: {type(arg)}')

    def supports_atomic_grouping(self) -> bool:
        """
        Decides whether the given branches can be safely grouped in an atomic group.

        Args:
            branches: The list of atom sequences representing alternative branches.
        Returns:
            True if this block can be joing atomically (i.e. with '(?>...)'), False otherwise.
        """
        if self.suffix:
            search_space = (atom for branch in self.branches for atom in branch)
        else:
            search_space = (branch.first for branch in self.branches)

        return all(map(self._atom_supports_atomic_grouping, search_space))

    def contextualize(self, data: Regex) -> Regex:
        """Add the context (prefix, suffix, quantifier) to the given atoms, usually a branch."""
        if self.prefix or self.suffix:
            data = self.prefix + data + self.suffix

        if self.quantifier:
            data = Regex.quantify(data, self.quantifier)
        return data

    @staticmethod
    def greatest_common_prefix(*args: Regex) -> Regex:
        if not args or not all(map(len, args)):
            return Regex()
        elif len(args) == 1:
            return args[0]
        return Regex(mi.longest_common_prefix(args))

    @staticmethod
    def greatest_common_suffix(*args) -> Regex:
        if not args or not all(map(len, args)):
            return Regex()
        elif len(args) == 1:
            return args[0]

        # Reverse the contents before and after invoking the `common_prefix` library function
        common_suffix = tuple(mi.longest_common_prefix(map(reversed, args)))
        return Regex(reversed(common_suffix))

    @staticmethod
    def _atom_supports_atomic_grouping(atom: Atom) -> bool:
        """Determines if the given atom can be safely included in a (new) atomic group."""
        return (
            atom.quantifier.is_simple
            and not isinstance(atom, SetAtom)
            and (not isinstance(atom, GroupAtom) or atom.is_simple)
        )

    @staticmethod
    def _is_clone_with_prefix(lhs: Regex, rhs: Regex) -> bool:
        return bool(lhs and rhs) and len(rhs) == len(lhs) + 1 and rhs[1:] == lhs

    @classmethod
    def group_branches_by_prefix(cls, *branches: Regex) -> Generator[list[Regex], None, None]:
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
        _split = lambda lhs, rhs: not (
            lhs.last and rhs.last and cls.greatest_common_suffix(*lhs.last, *rhs.last)
        )
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
        assert isinstance(atom, GroupAtom), f'Expected group atom, got: {atom!r}'
        if not atom.quantifier.is_simple or atom.kind not in GroupKind._SPLITTABLE:
            return cls.new(atom)

        # I. Split the group's contents into branches
        block = cls.new(atom.body, prefix=Regex(atom.inline_flags))
        block.expand()

        # II. Expand out an optional quantifier into a new, empty branch
        if atom.is_optional and all(block.branches):
            block.branches.append(Regex.empty())

        return block

    @classmethod
    def expand_set(cls, atom: Atom) -> Self:
        # 0. Validate
        assert isinstance(atom, SetAtom), f'Expected set atom, got: {atom!r}'
        if not atom.is_simple:
            return cls.new(atom)
        result: list[Regex] = []

        # I. Expand out optional quantifier into a new branch
        if atom.quantifier.is_optional:
            result.append(Regex.empty())

        # II. Atomize the set body into individual atomic branches
        result.extend(map(Regex, Regex.atomize(atom.body)))

        return cls.new(*result, quantifier=atom.quantifier.as_required())

    @classmethod
    def expand_atom(cls, atom: Atom) -> Self:
        if atom.is_group:
            return cls.expand_group(atom)
        elif atom.is_set:
            return cls.expand_set(atom)
        elif atom.is_optional:
            return cls.new(Regex.empty(), Regex(atom.as_required()))
        else:
            return cls.new(atom)

    @classmethod
    def collapse_atoms(cls, *args: Atom | Regex) -> Regex:
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
        # 0. Normalize args
        atoms = [(arg.one if isinstance(arg, Regex) else arg) for arg in args]

        # I. Determine if the resulting atom should be optional
        to_drop = set()
        is_optional = False
        for i, atom in enumerate(atoms):
            if atom.quantifier == '?':
                atoms[i] = atom.quantify('')
                is_optional = True
            elif not atom:
                to_drop.add(i)
                is_optional = True
        if to_drop:
            atoms = ut.drop_at(atoms, to_drop)

        # II. Separate chars and simple sets from groups and complex sets
        complex_atoms, simple_atoms = map(list, mi.partition(lambda atom: atom.is_simple, atoms))

        # III. Combine the simple results
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
                for set_atom in sets:
                    set_branches |= {branch.one for branch in cls.expand_set(set_atom).branches}
            branches = [Atom(f'[{"".join(map(str, sorted(set_branches)))}]')]

        # III. Render the resulting set alternated w/ the complex branches
        new_branch_obj = cls.new(*branches, *complex_atoms)
        if is_optional:
            assert new_branch_obj.make_optional(), 'Failed to make new, unquantified block optional'
        return new_branch_obj.render()

    @classmethod
    def collapse_blocks_by_suffix(cls, blocks: list[Self]) -> list[Regex]:
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
                shared_suffix = cls.greatest_common_suffix(*(br.last for br in group))
                assert (n_suf := len(shared_suffix)), 'Grouped blocks with no shared suffix.'
                for block in group:
                    if block.suffix:
                        block.suffix = block.suffix[:-n_suf]
                    else:
                        block.branches = [br[:-n_suf] for br in block.branches]

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
    def _get_branch(self, key: int) -> Regex:
        return self.branches[key]

    @__getitem__.register
    def _get_branches(self, key: slice) -> Self:
        return self.new(*self.branches[key])

    # ---------------
    # `x1` Properties
    # ---------------
    @property
    def lengths(self) -> list[int]:
        return list(map(len, self.branches)) if self else []

    @property
    def max_length(self) -> int:
        return max(*self.lengths) if self else 0

    @property
    def last(self) -> list[Regex]:
        """Returns all the atoms tied for the final position in this object."""
        return [self.suffix] if self.suffix else self.branches

    # --------------
    # `x2` Modifiers
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
                    self.branches[i] = Regex(branch.one.as_required())
            else:
                # I.iii. Look for a copy of this branch w/ a prefix
                for j, other_branch in enumerate(self.branches):
                    if j in to_drop or j == i:
                        continue
                    elif self._is_clone_with_prefix(branch, other_branch):
                        to_drop.add(i)
                        other_branch[0] = other_branch[0].as_optional()

        if to_drop:
            self.branches = ut.drop_at(self.branches, to_drop)
        return self

    def expand(self, max_split: int = 4) -> Self:
        """
        Recursively "expand" all branching clauses in this block, creating multiple explicit cases
        where there was previously implicit behavior.

        Args:
            max_split: The maximum number of atoms to split per branch (default: 4).
        Returns:
            The modified block instance with expanded branches.
        """
        if not self:
            return self

        new_data: list[Regex] = []
        for branch in self.branches:
            assert isinstance(branch, Regex)
            sub_branches: list[Regex] = []
            n_split = 0

            # I. Split any sets and groups we can find into nested branch objects
            for atom in branch:
                assert isinstance(atom, Atom)
                if n_split < max_split and len(sub_block := self.expand_atom(atom)) > 1:
                    sub_branches.extend(sub_block.export_branches())
                else:
                    sub_branches.append(Regex(atom))

            # II. Reconstruct the branches from the expanded atoms
            if len(sub_branches) > len(branch):
                # II.i. If any atoms were split, record all possible permutations
                all_branches = it.product(*(br.data for br in sub_branches))
                new_data.extend(map(Regex, all_branches))
            else:
                # II.ii. For all non-splittable atoms, just add them as-is
                new_data.append(branch)

        # III. Save to instance variables and sort the results (allowed b/c they're alternated)
        self.branches = new_data
        self.sort()
        return self

    @classmethod
    def expand_branches(cls, branches: Iterable[str]) -> Self:
        """
        Parse the given branches into a block, then expand its contents to be fully explicit.

        Args:
            branches: An iterable of branch strings to expand.
        Returns:
            A new block instance with expanded branches.
        """
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

    def optimize(self) -> Self:
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
        self.factor()
        self.clean()

        # II. Recursively replace the block's body with an equivalent tree
        if len(self) == 1:
            # II.i. Singular case: recurse into child groups
            # branch = self.branches[0]
            # for i, atom in enumerate(branch):
            #     if atom.is_group:
            #         # II.i. Recurse into any groups found here
            #         sub_block = cls.expand_group(atom).optimize()
            #         branch[i] = sub_block.render()
            pass
        elif self.max_length == 1:
            # II.ii. Atomic case: join them directly, as there are unique opportunities
            self.branches = [cls.collapse_atoms(*self.branches)]
        else:
            # II.iii. Main case: recurse into groups that share a prefix, then factor out shared
            #         suffixes of those results before returning
            prefix_groups = cls.group_branches_by_prefix(*self.branches)
            children = [cls(branches=branches).optimize() for branches in prefix_groups]
            self.branches = cls.collapse_blocks_by_suffix(children)

        return self

    # ------------------
    # `x3` Serialization
    # ------------------
    def render(self) -> Regex:
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
            start = '(?>' if self.supports_atomic_grouping() else '(?:'
            ret = Regex(f'{start}{r"|".join(map(str, self.branches))})')

        # III. Add contextual details (prefix, suffix, quantifier)
        return self.contextualize(ret)

    def export_branches(self) -> list[Regex]:
        """Export just the branches of this block."""
        return list(map(self.contextualize, self.branches))
