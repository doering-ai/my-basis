############
### HEAD ###
############
### STANDARD
from typing import Self, Sequence, Iterator, Generator, Any
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

    # Primary data
    branches: list[Regex] = []

    # Context data
    prefix: Regex = Regex()
    suffix: Regex = Regex()
    quantifier: Quantifier = Quantifier()

    # Options
    max_expand: int = 4

    # -------------------
    # `0` Initial Methods
    # -------------------
    def __init__(
        self,
        *args: str | Atom | Regex | Sequence[Regex] | Iterator[Regex] | Self,
        prefix: str | Atom | Regex = '',
        branches: list[Regex] | None = None,
        suffix: str | Atom | Regex = '',
        quantifier: str | Quantifier = '',
        max_expand: int = 4,
        **kwargs: Any,
    ) -> None:
        if branches is None:
            branches = []
        if args:
            branches.extend(mi.flatten(map(self._parse_arg, args)))

        super().__init__(
            branches=branches,
            prefix=Regex(prefix),
            suffix=Regex(suffix),
            quantifier=Quantifier(quantifier),
            max_expand=max_expand,
            **kwargs,
        )

    @pyd.model_validator(mode='after')
    def _validate_branches(self) -> Self:
        self.branches = list(mi.unique_everseen(self.branches))
        return self

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

        return all(atom.is_simple and not isinstance(atom, SetAtom) for atom in search_space)

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
    def expand_branch(self, branch: Regex) -> Generator[Regex, None, None]:
        """
        Expand the given branch into (potentially) multiple branches by expanding any expandable
        atoms within it. If no atoms within are expandable, it will naturally return the same
        branch that was passed in, unchanged.

        Args:
            branch: The branch to expand.
        Yields:
            Every possible permutation we can make with the expanded contents of that branch, that
            are still nonetheless isomorphic to the original branch when taken as a set.
        """

        # I. Build a list of positional subblocks, representing the possible values of each atom
        count = 0
        atom_blocks: list[list[Regex]] = []
        for atom in branch:
            if count < self.max_expand and len(atom_block := self.expand_atom(atom)) > 1:
                # I.i. Expand this atom into a multiple branches
                atom_blocks.append(atom_block.export_branches())
                count += 1
            else:
                # I.ii. Else just store it as one single-atom branch
                atom_blocks.append([Regex(atom)])

        # II. If any atoms were split, yield all possible permutations of the overall branch
        if count:
            yield from map(Regex, it.product(*atom_blocks))
        else:
            yield branch

    def expand_group(self, atom: Atom) -> Self:
        """
        Split a group atom into branches with shared prefixes, if possible.
        """
        # 0. Validate and normalize arguments
        assert isinstance(atom, GroupAtom), f'Expected group atom, got: {atom!r}'
        kwargs: dict = dict(max_expand=self.max_expand)
        if atom.inline_flags:
            kwargs['prefix'] = Regex(atom.inline_flags)

        # I. Don't try to split complex groups
        if not atom.quantifier.is_simple or atom.kind not in GroupKind._SPLITTABLE:
            return self.new(atom, **kwargs)

        # II. Split the group's contents into branches, then recursively expand them
        block = self.new(atom.body, **kwargs).expand()

        # III. Expand out an optional quantifier into a new, empty branch
        if atom.is_optional and all(block.branches):
            block.branches.insert(0, Regex.empty())

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
        body_atoms = Regex.atomize(atom.body)
        result.extend(map(Regex, body_atoms))

        return cls.new(*result, quantifier=atom.quantifier.as_required())

    def expand_atom(self, atom: Atom) -> Self:
        if atom.is_group:
            return self.expand_group(atom)
        elif atom.is_set:
            return self.expand_set(atom)
        elif atom.is_optional:
            return self.new(Regex.empty(), Regex(atom.as_required()))
        else:
            return self.new(atom)

    @classmethod
    def condense_atomic_branches(cls, branches: list[Regex]) -> list[Regex]:
        """
        Given a collection of single atoms, attempt to combine them into a more succint set-based
        expression.

        NOTE: This is a special case of condense() above where all the alternatives are themselves
        atomic.

        Examples:
            _condense_atomic_branches(['a', 'b', '']) -> '[ab]?'
            _condense_atomic_branches(['(?:one)', '(?:two)', 'a', 'b', '']) -> '(?:one|two|[ab])?'

        Args:
            atoms: A list of valid atom strings.
        Returns:
            The optimized regex pattern string.
        """
        # I. Validate that this block only has single-atom branches
        atoms = [br.one for br in branches]

        # II. Separate out the "simple" branches, e.g. plain sets, individual characters, etc.
        #     Note that for this purpose, clean() should have removed any simply-quantified (AKA
        #     optional) branches already *if* that were possible, so they should not be re-handled
        #     here, but rather ignored as complex.
        complex_branches, simple_branches = map(
            list,
            mi.partition(lambda a: a.is_simple and not (a.is_group or a.quantifier), atoms),
        )

        if len(simple_branches) <= 1:
            return branches

        # III. Combine multiple simple branches into a single set
        non_sets, sets = map(set, mi.partition(lambda atom: atom.is_set, simple_branches))
        all_members = non_sets | {
            branch.one for _set in sets for branch in cls.expand_set(_set).branches
        }
        new_set_body = ''.join(map(str, sorted(all_members)))

        # IV. Save the results to this object
        return list(map(Regex, [f'[{new_set_body}]', *complex_branches]))

    @classmethod
    def condense_blocks(cls, blocks: list[Self]) -> list[Regex]:
        """
        Condense a collection of blocks (branching expressions) back into a single set of branches,
        factoring out shared suffixes along the way where possible.

        We don't check for shared prefixes because those would've been handled already as part of
        the primary factor() step -- each block represents a prefix group.

        Args:
            blocks: The list of Block instances to condense.
        Returns:
            The optimized list of regex branches, isomorphic to the original set of blocks.
        """
        ret = []
        for group in cls.group_blocks_by_suffix(*blocks):
            assert group, 'Somehow collected an empty block group.'
            if len(group) == 1:
                # I. Render monoblock groups directly
                ret.append(group[0].render())
            else:
                # II. Factor out shared suffixes between blocks
                shared_suffix = cls.greatest_common_suffix(*(br.last for br in group))
                assert (n_suf := len(shared_suffix)), 'Grouped blocks with no shared suffix.'
                for block in group:
                    if block.suffix:
                        assert len(block.suffix) >= n_suf, 'Shared suffix longer than block suffix.'
                        block.suffix = block.suffix[:-n_suf]
                    else:
                        block.branches = [br[:-n_suf] for br in block.branches]

                new_block = cls(branches=[block.render() for block in group], suffix=shared_suffix)
                ret.append(new_block.render())
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
        return str(self)

    def __hash__(self) -> int:
        return hash(str(self))

    def __bool__(self) -> bool:
        return any(map(bool, self.branches))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Block):
            return False
        return str(self) == str(other)

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

    def expand(self) -> Self:
        """
        Recursively "expand" all branching clauses in this block, creating multiple explicit cases
        where there was previously implicit behavior.

        Examples:
            - expand(r'confirm(?:ation)?') -> r'(?:confirm|confirmation)'
            - expand(r'a[bc]d') -> r'(?:abd|acd)'
        Args:
            max_per_branch: The maximum number of atoms to split per branch (default: 4).
        Returns:
            The modified block instance with expanded branches.
        """
        if self:
            self.branches = list(mi.flatten(map(self.expand_branch, self.branches)))
            self.sort()
        return self

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

    def condense(self) -> Self:
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
        if not self:
            return self
        elif len(self) == 1:
            # II.i. Singular case: NOOP if expand() didn't create multiple branches at this level
            pass
        elif self.max_length == 1:
            # II.ii. Atomic case: attempt to join mono-atom branches into a single set
            self.branches = cls.condense_atomic_branches(self.branches)
        else:
            # II.iii. Main case: recurse into groups that share a prefix, rebuilding the whole tree
            child_blocks = []
            for branches in cls.group_branches_by_prefix(*self.branches):
                child_blocks.append(cls(branches=branches).condense())
            self.branches = cls.condense_blocks(child_blocks)

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
