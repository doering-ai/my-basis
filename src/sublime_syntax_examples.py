############
### HEAD ###
############
# Standard imports
from typing import Mapping, Self
import argparse as ap
import asyncio as aio
from pathlib import Path
from collections import Counter
import subprocess

# Modular imports
import pandas as pd
import regex as re
import pydantic as pyd

# Local imports
from my import PickleCache, env

############
### DATA ###
############
LANGS = dict(
    markdown='md',
    python='py',
    regexp='re',
    shell='sh',
)


############
### BODY ###
############
class Parser(pyd.BaseModel):
    target: pyd.DirectoryPath
    cache: PickleCache[str, Mapping]
    scope: str

    min_depth: int = 1
    regex: bool = False
    meta: bool = False
    subl: bool = False
    out: bool = False

    @classmethod
    async def new(cls, args: ap.Namespace) -> Self:
        target = Path(args.target).expanduser().absolute().resolve()
        assert target.is_dir(), f'target {target} is not a directory'

        cache = await cls.setup_cache(target)
        assert cache['scopes'], 'Scope cache is empty'

        return cls(
            target=target,
            cache=cache,
            scope=args.scope.strip(),
            min_depth=args.depth,
            regex=args.regex,
            meta=args.meta,
            subl=args.subl,
            out=args.out,
        )

    @classmethod
    async def setup_cache(cls, target: pyd.DirectoryPath) -> PickleCache[str, Mapping]:
        cache = PickleCache(
            file=env.path('MY_CACHE', '~/.cache') / 'sublime_syntax_scopes.pkl',
            func=lambda: cls.read_scopes(target),
        )
        await cache.read()
        return cache

    @classmethod
    async def read_scopes(cls, target: Path) -> dict[str, Mapping]:
        scopes = []
        for file in target.rglob('*'):
            if not file.is_file():
                continue
            content = file.read_text()
            new_scopes = re.findall(r'\b[\-\w]+(?:\.[\-\+\w]+)+(?!\w)', content)
            if new_scopes:
                scopes.extend(new_scopes)

        return dict(scopes=Counter(scopes))

    @property
    def scopes(self) -> Counter[str]:
        return self.cache['scopes']  # type:ignore

    def filter_scopes(self) -> pd.DataFrame:
        # I. Finalize the search regex
        assert self.scope, 'scope must be non-empty'

        if self.regex:
            expr = re.compile(self.scope)
        else:
            scope = self.scope.strip('.')
            expr = re.compile(rf'^{re.escape(scope)}(?:\.[-\w]+){{{self.min_depth}}}')

        # II. Filter known scopes by this regex
        tuples = []
        for other, count in self.scopes.items():
            if expr.search(other):
                other, lang = other.rsplit('.', 1)
                tuples.append((other, count, lang))

        # III. Clean result before returning
        df = pd.DataFrame(
            tuples,
            columns=['scope', 'count', 'lang'],  # type:ignore
        )

        # III.i. Use LANGS to replace language codes where possible
        df['lang'] = df['lang'].map(lambda x: LANGS.get(x, x))

        # III.ii. Remove trailing .regexp
        df['scope'] = df['scope'].str.removesuffix('.regexp')

        # III.iii. Filter out meta scopes if needed
        if not self.meta:
            df = df[~df['scope'].str.startswith('meta.')]

        return df

    def output(self, df: pd.DataFrame) -> None:
        df.sort_values(by='scope', ascending=False, inplace=True)

        # Accumulate langs into CSV and counts into sums for each unique scope
        summary = (
            df.groupby('scope')
            .agg(
                dict(
                    count='sum',
                    lang=lambda x: ', '.join(sorted(x)),
                )
            )
            .reset_index()
        )
        pd.set_option('display.max_rows', None)

        if self.out:
            out = '\n'.join(summary['scope'])
        else:
            # Remove the prefix from all of them
            if not self.regex:
                prefix = self.scope.strip(' .') + '.'
                summary['scope'] = summary['scope'].str.removeprefix(prefix)

            # Pretty-print the summary
            out = summary.to_markdown(index=False)

        if self.subl:
            # Open in Sublime Text
            proc = subprocess.Popen(['subl', '-'], stdin=subprocess.PIPE, text=True)
            proc.communicate(input=out)
        else:
            # Print to console
            print(out)

    async def main(self) -> None:
        # II. Find descendants
        df = self.filter_scopes()
        if df.empty:
            print('No descendants found.')
            return

        self.output(df)


############
### MAIN ###
############
def parse_args() -> ap.Namespace:
    parser = ap.ArgumentParser(description='Search for syntax descendants.')

    parser.add_argument(
        'scope',
        help='Dot-separated scope whose descendants we must find.',
    )

    parser.add_argument(
        '--target',
        type=Path,
        default=Path('~/3p/sublime-examples'),
        help='Directory to search within.',
    )

    parser.add_argument(
        '-d',
        '--depth',
        type=int,
        default=0,
        help='Descendants must have at least this many more parts.',
    )

    parser.add_argument(
        '-o',
        '--out',
        action='store_true',
        help='Print in a TOML-friendly format',
    )

    parser.add_argument(
        '-s',
        '--subl',
        action='store_true',
        help='Open results in Sublime Text',
    )

    parser.add_argument(
        '-r',
        '--regex',
        action='store_true',
        help='Interpret scope as a regex pattern',
    )
    parser.add_argument(
        '-m',
        '--meta',
        action='store_true',
        help='Include meta scopes in the results.',
    )

    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    parser = await Parser.new(args)
    await parser.main()


if __name__ == '__main__':
    aio.run(main())
