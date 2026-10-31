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
import regex as re

### INTERNAL
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
        Decompose an alternation, then factor its shared context back out::

            >>> from my import Tree
            >>> tree = Tree('(?:br1|br2|br3)').expand()
            >>> [str(branch) for branch in tree.branches]
            ['br1', 'br2', 'br3']
            >>> tree = tree.factor()
            >>> (str(tree.prefix), [str(branch) for branch in tree.branches])
            ('br', ['[123]'])
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
        prefix: str | Atom | Regex = '',
        branches: list[Regex] | None = None,
        suffix: str | Atom | Regex = '',
        quantifier: str | Quantifier = '',
        inner_quant: str | Quantifier = '',
        max_expand: int = 4,
        **kwargs: Any,
    ) -> None:
        """Construct a new instance from the given branches, casting flexibly."""
        data: dict = dict(branches=branches or [])
        if args:
            data['branches'].extend(mi.flatten(map(self._parse_arg, args)))
        if prefix != '':
            data['prefix'] = Regex(prefix)
        if suffix != '':
            data['suffix'] = Regex(suffix)
        if quantifier != '':
            data['quantifier'] = Quantifier(quantifier)
        if inner_quant != '':
            data['inner_quant'] = Quantifier(inner_quant)
        if max_expand != 4:
            data['max_expand'] = max_expand

        super().__init__(**data, **kwargs)

    @pyd.model_validator(mode='after')
    def _validate_branches(self) -> Self:
        if self.is_transformable:
            self.branches = list(mi.unique_everseen(self.branches))
        return self

    @classmethod
    def new(
        cls,
        *args: str | Atom | Regex | Sequence[Regex] | Iterator[Regex] | Self,
        **kwargs: Any,
    ) -> Self:
        """Construct a new instance from the given branches, casting flexibly.

        Examples:
            Alternated strings and standalone arguments both become branches::

                >>> from my import Tree
                >>> [str(branch) for branch in Tree.new('a|b', 'c').branches]
                ['a', 'b', 'c']
        """
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
            raise TypeError(f'Unsupported type for Branches initialization: {type(arg)}')

    def supports_atomic_grouping(self) -> bool:
        """Prove a unique endpoint for forward, simple-fold literal branches.

        Returns:
            True if this tree can be joined atomically (i.e. with `(?>...)`), False otherwise.
        """
        widths = [self._fixed_width(branch) for branch in self.branches]
        if not widths or any(width is None or width == 0 for width in widths):
            return False
        if len(set(widths)) == 1:
            return True

        # Different endpoints are safe only when the branches cannot compete at this
        # position. Restrict the disjointness proof to ASCII simple-fold classes.
        seen: set[str] = set()
        for branch in self.branches:
            first = branch.first
            members = self._literal_members(first)
            if not members or any(not char.isascii() for char in members):
                return False
            folded = {char.lower() for char in members}
            if seen & folded:
                return False
            seen |= folded
        return True

    @classmethod
    def _literal_members(cls, atom: Atom) -> list[str] | None:
        if isinstance(atom, SetAtom) and atom.is_simple:
            members = [member.literal for member in atom.members]
            return (
                [char for char in members if char is not None]
                if all(char is not None for char in members)
                else None
            )
        return [atom.literal] if atom.literal is not None else None

    @classmethod
    def _is_transformable(cls, atom: Atom) -> bool:
        if not atom.quantifier.is_simple:
            return False
        if isinstance(atom, GroupAtom):
            return (
                atom.kind == GroupKind.PLAIN
                and not atom.flags
                and all(
                    cls._is_transformable(child)
                    for branch in Regex(atom.body).split()
                    for child in branch
                )
            )
        return cls._literal_members(atom) is not None

    @classmethod
    def _fixed_width(cls, branch: Regex) -> int | None:
        width = 0
        for atom in branch:
            if atom.quantifier:
                return None
            if isinstance(atom, GroupAtom):
                if atom.kind not in GroupKind._SIMPLE or atom.flags:
                    return None
                widths = {cls._fixed_width(part) for part in Regex(atom.body).split()}
                if None in widths or len(widths) != 1:
                    return None
                part_width = widths.pop()
                assert part_width is not None
                width += part_width
            elif cls._literal_members(atom) is not None:
                width += 1
            else:
                return None
        return width

    @property
    def is_transformable(self) -> bool:
        """Whether every branch admits ordered finite literal factoring.

        Examples:
            Assertions remain opaque even if their bodies contain literals::

                >>> Tree('cat', 'car').is_transformable
                True
                >>> Tree('(?=a|b)c').is_transformable
                False
        """
        return all(self._is_transformable(atom) for branch in self.branches for atom in branch)

    @staticmethod
    def _is_set_eligible(atom: Atom | Regex) -> bool:
        """Determine if the given atom can be isomorphically added to a (simple) character set.

        .. note::
            For this purpose, `clean()` should have removed any simply-quantified (AKA optional)
            branches already *if* that were possible.
            Thus they should not be re-handled here, but rather ignored as complex.
        """
        if isinstance(atom, Regex):
            atom = atom.one
        return not atom.quantifier and Tree._literal_members(atom) is not None

    @staticmethod
    def greatest_common_prefix(*args: Regex) -> Regex:
        """Identify the longest sub-expression appearing at the start of all the given branches."""
        if not args or not all(map(len, args)):
            return Regex()
        elif len(args) == 1:
            return args[0]
        return Regex(mi.longest_common_prefix(args))

    @classmethod
    def _factoring_prefix(cls, *branches: Regex) -> Regex:
        # Moving a backtracking prefix outside an ordered alternation can change which
        # branch wins: a?a|a?b on "ab" must choose "a", not "ab".
        prefix = cls.greatest_common_prefix(*branches)
        return Regex(it.takewhile(lambda atom: cls._fixed_width(Regex(atom)) is not None, prefix))

    @staticmethod
    def greatest_common_suffix(*args: Regex) -> Regex:
        """Identify the longest sub-expression appearing at the end of all the given branches."""
        if not args or not all(map(len, args)):
            return Regex()
        elif len(args) == 1:
            return args[0]

        # Reverse the contents before and after invoking the `common_prefix` library function
        common_suffix = tuple(mi.longest_common_prefix(map(reversed, (a.data for a in args))))
        return Regex(reversed(common_suffix))

    @staticmethod
    def _is_clone_with_prefix(lhs: Regex, rhs: Regex) -> bool:
        return bool(lhs and rhs) and len(rhs) == len(lhs) + 1 and rhs[1:] == lhs

    @classmethod
    def _regroup_independent(cls, branches: list[Regex]) -> list[Regex]:
        # Capture-free fixed-width alternatives all succeed at the same endpoint, so
        # their order cannot change the chosen span or an enclosing continuation.
        widths = {cls._fixed_width(branch) for branch in branches}
        if None not in widths and len(widths) == 1:
            return sorted(branches)

        # Recover shared structure across interleaved disjoint literal starts. Never
        # reorder competitors in the same ASCII simple-fold class, or cross an atom
        # whose first-character language is not proved here.
        result: list[Regex] = []
        buckets: dict[str, list[Regex]] = {}
        for branch in branches:
            atom = branch.first if branch else None
            char = atom.literal if atom is not None and not atom.quantifier else None
            if char is None or not char.isascii():
                result.extend(mi.flatten(buckets.values()))
                buckets.clear()
                result.append(branch)
            else:
                buckets.setdefault(char.lower(), []).append(branch)
        result.extend(mi.flatten(buckets.values()))
        return result

    @classmethod
    def group_branches_by_prefix(cls, branches: list[Regex]) -> Generator[list[Regex]]:
        """Group the given branches into buckets by their common prefixes (if any exist).

        It is assumed that branches are already given in a meaningful (and likely alphabetical)
        order, so only adjacent branches are compared.

        Args:
            branches: A list of sorted expressions assumed to be alternated by their parent.
        Yields:
            Lists of branches, each representing a contiguous subset of the given branches.
        """
        _split = lambda lhs, rhs: not cls._factoring_prefix(lhs, rhs)
        yield from mi.split_when(branches, _split)

    @classmethod
    def group_blocks_by_suffix(cls, trees: list[Self]) -> Generator[Self]:
        """Group the given trees by their common suffixes (if any exist).

        Uses the main body branches of a tree for this purpose if it lacks a suffix.

        Args:
            trees: A list of tree instances to group.
        Yields:
            Tree instances, each merging a contiguous subset of the given trees.
        """
        _split = lambda lhs, rhs: not cls.greatest_common_suffix(*lhs, *rhs)
        serialized_blocks = list(map(cls.serialize, trees))
        for branch_group in mi.split_when(serialized_blocks, _split):
            yield cls.new(*mi.flatten(branch_group))

    def set_quantifier(self, quantifier: str | Quantifier, overwrite: bool = False) -> bool:
        """Attempt to apply the given quantifier to this tree.

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
            True if the quantifier was set (or combined with the existing one), False if the two
            cannot be combined without nested groups (e.g. `{3,5}` plus `?`).
        """
        has_context = self.prefix or self.suffix
        field = 'inner_quant' if has_context else 'quantifier'
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
        """Expand a branch into an equivalent alternation of multiple branches, if possible.

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
        assert isinstance(atom, GroupAtom), f'Expected group atom, got: {atom!r}'
        kwargs: dict = dict(max_expand=self.max_expand)
        # I. Don't try to split complex groups
        if not self._is_transformable(atom):
            return self.new(atom, **kwargs)

        # II. Split the group's contents into branches, then recursively expand them
        tree = self.new(atom.body, **kwargs).expand()

        # III. Expand out an optional quantifier into a new, empty branch
        if atom.is_optional and all(tree.branches):
            tree.branches.append(Regex.empty())

        return tree

    @classmethod
    def expand_set(cls, atom: Atom) -> Self:
        """Split a set atom into individual branches, if possible.

        Examples:
            An optional set contributes an extra empty branch::

                >>> from my.regex.meta import SetAtom
                >>> tree = Tree.expand_set(SetAtom('[abc]?'))
                >>> ([str(branch) for branch in tree.branches], str(tree.quantifier))
                (['a', 'b', 'c', ''], '')
        """
        # 0. Validate
        assert isinstance(atom, SetAtom), f'Expected set atom, got: {atom!r}'
        if not cls._is_transformable(atom):
            return cls.new(atom)
        result: list[Regex] = []

        # I. Expand out optional quantifier into a new branch
        # II. Atomize the set body into individual atomic branches
        result.extend(map(Regex, atom.members))
        if atom.quantifier.is_optional:
            result.append(Regex.empty())
        return cls.new(*result, quantifier=atom.quantifier.as_required())

    def expand_atom(self, atom: Atom) -> Self:
        """Expand a single atom into multiple branches, if possible."""
        if atom.is_group:
            return self.expand_group(atom)
        elif atom.is_set:
            return self.expand_set(atom)
        elif atom.quantifier == '?':
            return self.new(Regex(atom.as_required()), Regex.empty())
        else:
            return self.new(atom)

    @classmethod
    def condense_atomic_branches(cls, branches: list[Regex]) -> list[Regex]:
        """Condense a set of monatomic branches into an isomorphic, shorter version (if possible).

        .. note::
            This is just a special case of `condense()` below where all the alternatives are
            themselves atomic.

        Args:
            branches: A list of valid expressions, each of which has just one atom.
        Returns:
            An isomorphic version of the inputs that has been optimized as much as possible.
        Examples:
            Set-eligible branches merge into one character set; the rest pass through::

                >>> from my import Regex
                >>> branches = [Regex('a'), Regex('b'), Regex('(?:one)')]
                >>> [str(branch) for branch in Tree.condense_atomic_branches(branches)]
                ['[ab]', '(?:one)']
        """
        # I. Validate that this block only has single-atom branches
        atoms = [br.one for br in branches]

        # Only contiguous eligible alternatives may move into a set. An opaque branch
        # between them must retain its original priority.
        result: list[Regex] = []
        for eligible, group in it.groupby(atoms, cls._is_set_eligible):
            members = list(group)
            if not eligible or len(members) < 2:
                result.extend(map(Regex, members))
                continue
            characters = {char for atom in members for char in (cls._literal_members(atom) or [])}
            body = ''.join(re.escape(char, special_only=False) for char in sorted(characters))
            result.append(Regex(f'[{body}]'))
        return result

    @classmethod
    def condense_blocks(cls, trees: list[Self]) -> list[Regex]:
        """Construct a single tree from a list of trees, factoring out shared suffixes if possible.

        We don't check for shared prefixes because those would've been handled already as part of
        the primary `factor()` step -- each tree represents a prefix group.

        Args:
            trees: The list of tree instances to condense.
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
        set_fields = [f'{key}={getattr(self, key)!r}' for key in self.model_fields_set]
        return f'Tree({", ".join(set_fields)})'

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
        """Absorb an edge empty branch while preserving its ordered choice.

        Uses the parent's context to allow for further optimizations that are only valid in the
        given context.

        Returns:
            This tree, cleaned in place.
        Examples:
            An empty branch is absorbed into an optional quantifier::

                >>> from my import Tree
                >>> tree = Tree('a', 'b', '').clean()
                >>> ([str(branch) for branch in tree.branches], str(tree.quantifier))
                (['a', 'b'], '?')
        """
        # An interior empty branch is an ordered choice, not global optionality.
        # Never promote optional atoms from individual branches across their neighbors.
        if len(self.branches) > 1 and not (self.quantifier or self.inner_quant):
            if not self.branches[-1]:
                self.set_quantifier('?')
                self.branches.pop()
            elif not self.branches[0]:
                self.set_quantifier('??')
                self.branches.pop(0)
        return self

    def expand(self) -> Self:
        """Recursively split all our branches into more explicit, longer versions.

        The number of atoms expanded per branch is capped by the `max_expand` field.

        Returns:
            This tree, with its branches expanded in place.
        Examples:
            Expand an optional suffix into explicit branches::

                >>> from my import Tree
                >>> [str(branch) for branch in Tree(r'confirm(?:ation)?').expand().branches]
                ['confirmation', 'confirm']

            Character sets expand too::

                >>> [str(branch) for branch in Tree(r'a[bc]d').expand().branches]
                ['abd', 'acd']
        """
        if self and self.is_transformable:
            self.branches = list(
                mi.unique_everseen(mi.flatten(map(self.expand_branch, self.branches)))
            )
        return self

    def factor(self) -> Self:
        """Factor out common prefixes and suffixes from the branches in the main data structure.

        Examples:
            A shared prefix moves into the tree's context::

                >>> from my import Tree
                >>> tree = Tree('street', 'stream', 'strap').factor()
                >>> (str(tree.prefix), str(tree.render()))
                ('str', 'str(?:eet|eam|ap)')
        """
        # 0. Return immediately if this is a single branch
        if not self.is_transformable or len(self) <= 1 or self.max_length <= 1:
            return self

        # I. Determine the prefix for this block (which should always exist if this func is called)
        if prefix := self._factoring_prefix(*self.branches):
            self.branches = [branch[len(prefix) :] for branch in self.branches]
            self.prefix += prefix

        # II. Check for a shared suffix
        if suffix := self.greatest_common_suffix(*self.branches):
            self.branches = [branch[: -len(suffix)] for branch in self.branches]
            self.suffix = suffix + self.suffix

        # III. Apply optimizations to newly mono-atomic branches
        if self.max_length == 1:
            # Shared optional quantifiers remain branch-local: a?|b? on "b"
            # chooses the first branch's empty match, whereas [ab]? would consume "b".
            # III.ii. Condense simple branches into sets
            if any(map(self._is_set_eligible, self.branches)):
                self.branches = self.condense_atomic_branches(self.branches)

        return self

    def condense(self) -> Self:
        """Construct an optimized regex from branches by factoring common prefixes and suffixes.

        This method builds an efficient regex pattern by identifying and extracting common
        prefixes and suffixes from multiple branches, minimizing redundancy in the result.

        Examples:
            The `expand()` / `condense()` cycle is the core of `RegexStore`'s optimization::

                >>> from my import Tree
                >>> tree = Tree('grape', 'grapefruit', 'apple').expand()
                >>> str(tree.condense().render())
                '(?:grape(?:fruit)??|apple)'
        """
        cls = self.__class__

        # I. Prepare the block; the main stage is the "factor" step, where prefixes are found
        # breakpoint()
        if not self.is_transformable:
            return self
        self.clean().factor().clean()
        self.branches = cls._regroup_independent(self.branches)

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
        """Render this tree's branches into a regex group, applying optimizations where possible.

        Returns:
            A pattern representing the properly combined & wrapped branches.
        Examples:
            Simple branches are joined atomically, with the context applied around them::

                >>> from my import Tree
                >>> str(Tree('a', 'b', quantifier='?').render())
                '(?>a|b)?'
        """
        # I. Clean the branch list, identifying optional branches and pre-combining where possible
        if not self:
            body = Regex.empty()
        elif len(self) == 1:
            # II.i. Singular branch -- no need to choose a mark
            body = self.branches[0]
        else:
            # II.ii. Determine whether we can safely use an atomic grouping here
            start = '(?>' if self.supports_atomic_grouping() else '(?:'
            body = Regex(f'{start}{r"|".join(map(str, self.branches))})')

        # III. Add contextual details (prefix, suffix, quantifier)
        return self.contextualize(body)

    def serialize(self) -> list[Regex]:
        """Serialize this tree into a list of branches with context applied, for intermediate use.

        This output is intended for consumption by other trees, rather than callers building
        expressions. For the output to serve as an isomorphic version of this tree, all the branches
        must be alternated together.

        Examples:
            Contextual trees serialize to a single rendered branch::

                >>> from my import Tree
                >>> [str(branch) for branch in Tree('a', 'b', prefix='x').serialize()]
                ['x(?>a|b)']
        """
        if len(self) == 0:
            return []
        elif self.prefix or self.suffix or self.quantifier or self.inner_quant:
            return [self.render()]
        else:
            return self.branches

    def export_branches(self) -> list[Regex]:
        """Export the branches of this tree as standalone expressions.

        Examples:
            Each branch gets its own copy of the tree's context::

                >>> from my import Tree
                >>> [str(branch) for branch in Tree('a', 'b', prefix='x').export_branches()]
                ['xa', 'xb']
        """
        return list(map(self.contextualize, self.branches))
