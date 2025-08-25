############
### HEAD ###
############
### STANDARD

### EXTERNAL

### INTERNAL
from my.code import Lang, Imports

############
### BODY ###
############


class ArchImports(Imports):
    # -------------------
    # `0` Initial Methods
    # -------------------

    # -------------------
    # `-` Private Methods
    # -------------------
    @classmethod
    def setup_shortcuts(cls) -> None:
        """
        Load the abbreviations for Python imports from the parameters file.
        """
        # I. Find all the symlink directories in ROOT/my, and register them w/ Python
        al.validate_dir(mydir := ROOT / 'my')
        for symlink in filter(lambda d: d.is_dir() and d.is_symlink(), mydir.iterdir()):
            dest = symlink.resolve()
            if dest.exists() and dest.is_dir() and dest.is_relative_to(ROOT):
                module_path = '.'.join(dest.relative_to(ROOT).parts)
                cls.SHORTCUTS[Lang.PY][module_path] = f'my.{symlink.name}'

        # II. Load TypeScript shortcuts from tsconfig file
        ts_paths = typist.from_json(ROOT / 'tsconfig.json').get('paths', {})
        cls.SHORTCUTS[Lang.TS] = {
            module_path: key[:-2]
            for key, values in ts_paths.items()
            for value in values
            if (module_path := value[2:-2])
        }

    # -------------------
    # `+` Primary Methods
    # -------------------
    def _arch_module(self, target: File | Idx, origin: Path | Idx | None = None) -> str:
        """
        Construct a module string for the targeting architectonic file, using relative paths
        if possible.
        """
        if isinstance(target, Idx):
            target = ARCH.get_file(target, self.lang.value)
        al.validate_arch_file(target)

        # II. Build a relative import if feasible and requested to
        if self.lang == Lang.PY and origin is not None:
            # II.i. Validate origin file
            if isinstance(origin, Idx):
                origin = ARCH.get_dir(origin)
            elif origin.is_file():
                origin = origin.parent
            al.validate_arch_dir(origin)

            relation = target.relative_to(origin, walk_up=True).parts
            depth = mi.ilen(it.takewhile(lambda p: p == '..', relation))
            if depth <= 2:
                module = '.'.join(['.' * depth, *relation[depth:]])
            else:
                module = '.'.join(target.relative_to(ROOT).parts)
            return module.rstrip('.py')

        elif self.lang == Lang.TS:
            parts = list(target.relative_to(ROOT).parts)
            if target.suffix not in ('css', 'json', 'html'):
                parts[-1] = parts[-1].rsplit(".", 1)[0]
            return '/'.join(parts)

        else:
            fire.error(f'Cannot build import for {target} in {self.lang} syntax.')
            return ''

    # ------------------
    # `x` Public Methods
    # ------------------
    def add_arch_import(
        self,
        target: Idx | File,
        *symbols: str,
        origin: Path | Idx | None = None,
    ) -> None:
        """
        Add an architectonic import to this file. Opinionated defaults are applied if any args
        are not provided.

        Args:
            target: The file or index to import from.
            symbols: The symbols to import.
            origin: [PY-ONLY] The origin file or directory for relative imports.
        """
        module = self._arch_module(target, origin)
        if symbols:
            symset = set(symbols)
        if isinstance(target, Idx):
            parent = ARCH[target].singular.title()
            symset = {parent, f'{parent}Data'}
        elif isinstance(target, Path):
            parent = target.stem.title()
            symset = {parent}
            if (dc := f'{parent}Data') in target.read_text():
                symset.add(dc)

        self.internal.add(module, *symset)

    def count_edges(self, origin: Path) -> Counter[Idx]:
        self.universalize(origin)
        counter: Counter[Idx] = Counter()
        for module in self.internal.keys():
            if digits := ''.join(re.findall(r'_([0123ab])_[[:lower:]]+', module)):
                counter[Idx.new(digits)] += 1
        return counter
