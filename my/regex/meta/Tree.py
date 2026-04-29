############
### HEAD ###
############
### STANDARD
from typing import Self, Any, overload
from collections.abc import Sequence, Iterator, Generator
import itertools as it
import more_itertools as mi

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
class Tree(pyd.BaseModel):
    """A collection of alternative "branches" for a regex position, for use in optimization code.

    Examples:
        - `Tree('(?:br1|br2|br3)')` -> `{prefix: 'br', branches: ['1', '2', '3'], suffix: ''}`
    """

    # Primary data
    branches: list[Regex] = []

    # Context data
    prefix: Regex = Regex()
    suffix: Regex = Regex()
    quantifier: Quantifier = Quantifier()
    inner_quant: Quantifier = Quantifier()

    # Options
    max_expand: int = 4

    # -------------------
    # `.` Initial Methods
    # -------------------
    def __init__(
        self,
        *args: str | Atom | Regex | Sequence[Regex] | Iterator[Regex] | Self,
        prefix: str | Atom | Regex = "",
        branches: list[Regex] | None = None,
        suffix: str | Atom | Regex = "",
        quantifier: str | Quantifier = "",
        inner_quant: str | Quantifier = "",
        max_expand: int = 4,
        **kwargs: Any,
    ) -> None:
        """Construct a new instance from the given branches, casting flexibly."""
        data: dict = dict(branches=branches or [])
        if args:
            data["branches"].extend(mi.flatten(map(self._parse_arg, args)))
        if prefix != "":
            data["prefix"] = Regex(prefix)
        if suffix != "":
            data["suffix"] = Regex(suffix)
        if quantifier != "":
            data["quantifier"] = Quantifier(quantifier)
        if inner_quant != "":
            data["inner_quant"] = Quantifier(inner_quant)
        if max_expand != 4:
            data["max_expand"] = max_expand

        super().__init__(**data, **kwargs)

    @pyd.model_validator(mode="after")
    def _validate_branches(self) -> Self:
        self.branches = list(mi.unique_everseen(self.branches))
        return self

    @classmethod
    def new(
        cls,
        *args: str | Atom | Regex | Sequence[Regex] | Iterator[Regex] | Self,
        **kwargs: Any,
    ) -> Self:
        """Construct a new instance from the given branches, casting flexibly."""
        return cls(
            branches=list(mi.flatten(map(cls._parse_arg, args))),
            **kwargs,
        )

    def copy_context(self) -> Self:
        """Copy just the context (prefix, suffix, quantifier) of this tree to a new instance."""
        return self.model_copy(update=dict(branches=[]), deep=True)

    # -------------------
    # `-` Private Methods
    # -------------------
    @classmethod
    def _parse_arg(
        cls, arg: str | Atom | Regex | Sequence[Regex] | Iterator[Regex] | Self
    ) -> Generator[Regex]:
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
            raise TypeError(
                f"Unsupported type for Branches initialization: {type(arg)}"
            )

    def supports_atomic_grouping(self) -> bool:
        """Decides whether the given branches can be safely grouped in an atomic group.

        Args:
            branches: The list of atom sequences representing alternative branches.
        Returns:
            True if this tree can be joined atomically (i.e. with `(?>...)`), False otherwise.
        """
        if not all(self.branches):
            return False
        if self.suffix:
            search_space = (atom for branch in self.branches for atom in branch)
        else:
            search_space = (branch.first for branch in self.branches)

        # return all(atom.is_simple and not isinstance(atom, SetAtom) for atom in search_space)
        return all(atom.is_simple for atom in search_space)

    @staticmethod
    def _is_set_eligible(atom: Atom | Regex) -> bool:
        """Determine if the given atom can be isomorphically added to a (simple) character set.

        ```{note}
        For this purpose, clean() should have removed any simply-quantified (AKA optional)
        branches already *if* that were possible.
        Thus they should not be re-handled here, but rather ignored as complex.
        ```
        """
        if isinstance(atom, Regex):
            atom = atom.one
        return atom.is_simple and not (atom.is_group or atom.quantifier)

    @staticmethod
    def greatest_common_prefix(*args: Regex) -> Regex:
        """Identify the longest sub-expression appearing at the start of all the given branches."""
        if not args or not all(map(len, args)):
            return Regex()
        elif len(args) == 1:
            return args[0]
        return Regex(mi.longest_common_prefix(args))

    @staticmethod
    def greatest_common_suffix(*args: Regex) -> Regex:
        """Identify the longest sub-expression appearing at the end of all the given branches."""
        if not args or not all(map(len, args)):
            return Regex()
        elif len(args) == 1:
            return args[0]

        # Reverse the contents before and after invoking the `common_prefix` library function
        common_suffix = tuple(
            mi.longest_common_prefix(map(reversed, (a.data for a in args)))
        )
        return Regex(reversed(common_suffix))

    @staticmethod
    def _is_clone_with_prefix(lhs: Regex, rhs: Regex) -> bool:
        return bool(lhs and rhs) and len(rhs) == len(lhs) + 1 and rhs[1:] == lhs

    @classmethod
    def group_branches_by_prefix(cls, branches: list[Regex]) -> Generator[list[Regex]]:
        """Group the given branches into buckets by their common prefixes (if any exist).

        It is assumed that branches are already given in a meaningful (and likely alphabetical)
        order, so only adjacent branches are compared.

        Args:
            branches: A list of sorted expressions assumed to be alternated by their parent.
        Yields:
            Lists of atoms, each representing a contiguous subset of this tree's branches.
        """
        _split = lambda lhs, rhs: not cls.greatest_common_prefix(lhs, rhs)
        yield from mi.split_when(branches, _split)

    @classmethod
    def group_blocks_by_suffix(cls, trees: list[Self]) -> Generator[Self]:
        """Group the given trees by their common suffixes (if any exist).

        Uses the main body branches of a tree for this purpose if it lacks a suffix.

        Args:
            trees: A list of tree instances to group.
        Yields:
            Lists of Block instances, each representing a contiguous subset of the given trees.
        """
        _split = lambda lhs, rhs: not cls.greatest_common_suffix(*lhs, *rhs)
        serialized_blocks = list(map(cls.serialize, trees))
        for branch_group in mi.split_when(serialized_blocks, _split):
            yield cls.new(*mi.flatten(branch_group))

    def set_quantifier(
        self, quantifier: str | Quantifier, overwrite: bool = False
    ) -> bool:
        """Attempt to set the quantifier for this block to an optional version of itself.

        Determines whether to write to the main quantifier (wrapping everything) or the "inner"
        quantifier, which just applies to the branches themselves. If the tree has no context
        (i.e. prefix or suffix), then the main quantifier is used.

        Otherwise, it is assumed that the caller wants to promote/'bubble-up' a qualifier from the
        branches, so the inner quantifier is targeted instead.

        To reliably change the primary quantifier, write to the `Tree.quantifier` member directly.

        Args:
            quantifier: The quantifier to apply.
            overwrite: If True, overwrite any existing quantifier instead of combining.
        Returns:
            True if the quantifier is optional, False if this is not possible (e.g. `{3,5}`)
        """
        has_context = self.prefix or self.suffix
        field = "inner_quant" if has_context else "quantifier"
        value = getattr(self, field)
        new = Quantifier(quantifier)

        if value == new:
            return True
        elif overwrite:
            setattr(self, field, new)
            return True
        elif (prod := value & new) is not None:
            setattr(self, field, prod)
            return True
        else:
            return False

    def contextualize(self, data: Regex) -> Regex:
        """Add the context (prefix, suffix, quantifier) to the given atoms, usually a branch."""
        if self.inner_quant:
            data = data.quantify(self.inner_quant)

        if self.prefix or self.suffix:
            data = self.prefix + data + self.suffix

        if self.quantifier:
            data = data.quantify(self.quantifier)
        return data

    @classmethod
    def _partition_candidates(
        cls, branch: Regex, candidates: Iterator[Regex]
    ) -> tuple[Iterator[Regex], Iterator[Regex]]:
        rest, suffixed = mi.partition(lambda br: br.startswith(branch), candidates)
        _, prefixed = mi.partition(lambda br: br.endswith(branch), rest)
        return suffixed, prefixed

    # -------------------
    # `+` Primary Methods
    # -------------------
    def expand_branch(self, branch: Regex) -> Generator[Regex]:
        """Expand a branch into an equivelant alternation of multiple branches, if possible.

        If no atoms within are expandable, it will naturally return the same
        branch that was passed in, unchanged.

        Args:
            branch: The branch to expand.
        Yields:
            Every possible permutation we can make with the expanded contents of that branch, that
            are still nonetheless isomorphic to the original branch when taken as a set.
        """
        # 0. Special Case(s)
        # 0.i. Unneeded plain groups
        if (
            len(branch) == 1
            and isinstance(a := branch.one, GroupAtom)
            and a.is_simple
            and a.kind == GroupKind.PLAIN
            and not a.flags
        ):
            yield from self.expand_group(a).expand().export_branches()
            return

        # I. Build a list of positional subtrees, representing the possible values of each atom
        count = 0
        subtrees: list[list[Regex]] = []
        for atom in branch:
            if count < self.max_expand and len(_subtree := self.expand_atom(atom)) > 1:
                # I.i. Expand this atom into a multiple branches
                subtrees.append(_subtree.export_branches())
                count += 1
            else:
                # I.ii. Else just store it as one single-atom branch
                subtrees.append([Regex(atom)])

        # II. If any atoms were split, yield all possible permutations of the overall branch
        if count:
            yield from (Regex(*product) for product in it.product(*subtrees))
        else:
            yield branch

    def expand_group(self, atom: Atom) -> Self:
        """Split an alternating group into branches, grouped only by shared prefix."""
        # 0. Validate and normalize arguments
        assert isinstance(atom, GroupAtom), f"Expected group atom, got: {atom!r}"
        kwargs: dict = dict(max_expand=self.max_expand)
        if atom.inline_flags:
            kwargs["prefix"] = Regex(atom.inline_flags)

        # I. Don't try to split complex groups
        if not atom.quantifier.is_simple or atom.kind not in GroupKind._SPLITTABLE:
            return self.new(atom, **kwargs)

        # II. Split the group's contents into branches, then recursively expand them
        tree = self.new(atom.body, **kwargs).expand()

        # III. Expand out an optional quantifier into a new, empty branch
        if atom.is_optional and all(tree.branches):
            tree.branches.insert(0, Regex.empty())

        return tree

    @classmethod
    def expand_set(cls, atom: Atom) -> Self:
        """Split a set atom into individual branches, if possible."""
        # 0. Validate
        assert isinstance(atom, SetAtom), f"Expected set atom, got: {atom!r}"
        if not atom.is_simple:
            return cls.new(atom)
        result: list[Regex] = []

        # I. Expand out optional quantifier into a new branch
        if atom.quantifier.is_optional:
            result.append(Regex.empty())

        # II. Atomize the set body into individual atomic branches
        result.extend(map(Regex, atom.members))
        return cls.new(*result, quantifier=atom.quantifier.as_required())

    def expand_atom(self, atom: Atom) -> Self:
        """Expand a single atom into multiple branches, if possible."""
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
        """Condense a set of monatomic branches into an isomorphic, shorter version (if possible).

        ```{note}
        This is just a special case of condense() above where all the alternatives are themselves
        atomic.
        ```

        Examples:
        ```py
        _condense_atomic_branches(['a', 'b', '']) # -> '[ab]?'
        _condense_atomic_branches(['(?:one)', '(?:two)', 'a', 'b', '']) # -> '(?:one|two|[ab])?'
        ```

        Args:
            branches: A list of valid expressions, each of which has just one atom.
        Returns:
            An isomorphic version of the inputs that has been optimized as much as possible.
        """
        # I. Validate that this block only has single-atom branches
        atoms = [br.one for br in branches]

        # II. Separate out the "simple" branches, e.g. plain sets, individual characters, etc.
        rest, eligible = map(list, mi.partition(cls._is_set_eligible, atoms))
        if len(eligible) < 2:
            return branches

        # III. Combine multiple simple branches into a single set
        plain_atoms, set_atoms = map(
            set, mi.partition(lambda atom: atom.is_set, eligible)
        )
        expanded_sets = list(mi.flatten(cls.expand_set(a).branches for a in set_atoms))
        all_members = plain_atoms | {branch.one for branch in expanded_sets}
        new_set_body = "".join(map(str, sorted(all_members)))

        # IV. Save the results to this object
        return list(map(Regex, sorted([f"[{new_set_body}]", *rest])))

    @classmethod
    def condense_blocks(cls, trees: list[Self]) -> list[Regex]:
        """Construct a single tree from a list of trees, factoring out shared suffixes if possible.

        We don't check for shared prefixes because those would've been handled already as part of
        the primary factor() step -- each block represents a prefix group.

        Args:
            trees: The list of Block instances to condense.
        Returns:
            The optimized list of regex branches, isomorphic to the original set of trees.
        """
        ret = []
        for block in cls.group_blocks_by_suffix(trees):
            if len(block) > 1 and block.max_length > 1:
                block.factor()
            ret.extend(block.serialize())
        return ret

    # ------------------
    # `*` Public Methods
    # ------------------
    # --------------
    # `*0` Overrides
    # --------------
    def __len__(self) -> int:
        return len(self.branches)

    def __str__(self) -> str:
        return str(self.render())

    def __repr__(self) -> str:
        set_fields = [f"{key}={getattr(self, key)!r}" for key in self.model_fields_set]
        return f"Tree({', '.join(set_fields)})"

    def __hash__(self) -> int:
        return hash(str(self))

    def __bool__(self) -> bool:
        return any(map(bool, self.branches))

    def __eq__(self, other: object) -> bool:
        return (
            isinstance(other, Tree)
            and len(self) == len(other)
            and self.branches == other.branches
            and self.prefix == other.prefix
            and self.suffix == other.suffix
            and self.quantifier == other.quantifier
        )

    @overload
    def __getitem__(self, key: int) -> Regex: ...

    @overload
    def __getitem__(self, key: slice) -> Self: ...

    def __getitem__(self, key: int | slice) -> Regex | Self:
        if isinstance(key, int):
            return self.branches[key]
        return self.new(*self.branches[key])

    # ---------------
    # `*1` Properties
    # ---------------
    @property
    def lengths(self) -> list[int]:
        """The number of atoms in each branch of this tree."""
        return list(map(len, self.branches)) if self else []

    @property
    def max_length(self) -> int:
        """The maximum length (in atoms) of any branch in this tree."""
        return max(*self.lengths) if self else 0

    # --------------
    # `*2` Modifiers
    # --------------
    def clean(self) -> Self:
        """Clean the given branches by removing empty branches and combining optional ones.

        Uses the parent's context to allow for further optimizations that are only valid in the
        given context.

        Returns:
            A quantifier that can be applied to the whole set of branches.
        """
        # I. FIRST PASS
        to_drop: set[int] = set()
        for i, branch in enumerate(self.branches):
            n = len(branch)
            if not branch:
                # I.i. Empty branch -- whole thing is now optional, if that's possible
                if self.set_quantifier(r"?"):
                    to_drop.add(i)
            elif n == 1 and branch.one.is_optional and self.set_quantifier(r"?"):
                # I.ii. Single atom -- check for optionality
                branch[0] = branch.one.as_required()
        if to_drop:
            self.branches = ut.drop_at(self.branches, to_drop)
        to_drop.clear()

        return self

    def expand(self) -> Self:
        """Recursively split all our branches into more explicit, longer versions.

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
            self.branches.sort()
        return self

    def factor(self) -> Self:
        """Factor out common prefixes and suffixes from the branches in the main data structure."""
        # 0. Return immediately if this is a single branch
        if len(self) <= 1 or self.max_length <= 1:
            return self

        # I. Determine the prefix for this block (which should always exist if this func is called)
        if prefix := self.greatest_common_prefix(*self.branches):
            self.branches = [branch[len(prefix) :] for branch in self.branches]
            self.prefix += prefix

        # II. Check for a shared suffix
        if suffix := self.greatest_common_suffix(*self.branches):
            self.branches = [branch[: -len(suffix)] for branch in self.branches]
            self.suffix = suffix + self.suffix

        # III. Apply optimizations to newly mono-atomic branches
        if self.max_length == 1:
            # III.i. Factor out a quantifier shared between all branches
            if not self.quantifier:
                quantifiers = {
                    branch.one.quantifier for branch in self.branches if branch
                }
                if len(quantifiers) == 1 and self.set_quantifier(quantifiers.pop()):
                    self.branches = [branch.quantify("") for branch in self.branches]

            # III.ii. Condense simple branches into sets
            if any(map(self._is_set_eligible, self.branches)):
                self.branches = self.condense_atomic_branches(self.branches)

        return self

    def condense(self) -> Self:
        """Construct an optimized regex from branches by factoring common prefixes and suffixes.

        This method builds an efficient regex pattern by identifying and extracting common
        prefixes and suffixes from multiple branches, minimizing redundancy in the result.
        """
        cls = self.__class__

        # I. Prepare the block; the main stage is the "factor" step, where prefixes are found
        # breakpoint()
        self.sort().clean().factor().clean()

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
            children = []
            for branches in cls.group_branches_by_prefix(self.branches):
                child = cls(branches=branches)
                child.condense()
                children.append(child)
            self.branches = cls.condense_blocks(children)

        return self

    def sort(self) -> Self:
        """Sort the branches in this block in ascending order."""
        self.branches.sort()
        return self

    # ------------------
    # `*3` Serialization
    # ------------------
    def render(self) -> Regex:
        """Render the given branches into a regex group, applying optimizations where possible.

        Args:
            branches: The list of atom sequences representing alternative branches.
            quantity: The quantifier string to apply to the entire group.
        Returns:
            A pattern representing the properly combined & wrapped branches.
        """
        # I. Clean the branch list, identifying optional branches and pre-combining where possible
        if not self:
            body = Regex.empty()
        elif len(self) == 1:
            # II.i. Singular branch -- no need to choose a mark
            body = self.branches[0]
        else:
            # II.ii. Determine whether we can safely use an atomic grouping here
            start = "(?>" if self.supports_atomic_grouping() else "(?:"
            body = Regex(f"{start}{r'|'.join(map(str, self.branches))})")

        # III. Add contextual details (prefix, suffix, quantifier)
        return self.contextualize(body)

    def serialize(self) -> list[Regex]:
        """Serialize this tree into a list of branches with context applied, for intermediate use.

        This output is intended for consumption by other trees, rather than callers building
        expressions. For the output to serve as an isomorphic version of this tree, all the branches
        must be alternated together.
        """
        if len(self) == 0:
            return []
        elif self.prefix or self.suffix or self.quantifier or self.inner_quant:
            return [self.render()]
        else:
            return self.branches

    def export_branches(self) -> list[Regex]:
        """Export the branches of this block as standalone expressions."""
        return list(map(self.contextualize, self.branches))
