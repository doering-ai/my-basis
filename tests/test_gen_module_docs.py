"""Exercise the module docs generator against isolated page trees."""

import shutil
import subprocess
import sys
from pathlib import Path

import pytest as pyt

ROOT = Path(__file__).resolve().parents[1]


def run_generator(root: Path, *args: str, expected_exit: int = 0) -> str:
    result = subprocess.run(
        [sys.executable, str(root / 'docs' / 'gen_module_docs.py'), *args],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == expected_exit, result.stdout + result.stderr
    return result.stdout


def setup_generator(root: Path) -> None:
    (root / 'docs').mkdir()
    shutil.copy(ROOT / 'docs' / 'gen_module_docs.py', root / 'docs')
    for package in ('files', 'utils'):
        (root / 'my' / package).mkdir(parents=True)
        shutil.copy(ROOT / 'my' / package / '__init__.py', root / 'my' / package)
        shutil.copy(ROOT / 'docs' / f'{package}.md', root / 'docs')


def test_target_and_check_match_write(tmp_path: Path) -> None:
    setup_generator(tmp_path)
    docs = tmp_path / 'docs'
    before = {p.name: p.read_bytes() for p in docs.glob('*.md')}
    check = run_generator(tmp_path, '--check', 'files')
    assert 'would update docs/files.md' in check
    assert {p.name: p.read_bytes() for p in docs.glob('*.md')} == before
    write = run_generator(tmp_path, 'files')
    after = {p.name: p.read_bytes() for p in docs.glob('*.md')}
    assert 'docs/files.md' in write
    assert {name for name in before if before[name] != after[name]} == {'files.md'}
    assert (
        before['files.md'].split(b'```{toctree}', 1)[1]
        == after['files.md'].split(b'```{toctree}', 1)[1]
    )


def test_refuses_to_remove_existing_directive(tmp_path: Path) -> None:
    setup_generator(tmp_path)
    page = tmp_path / 'docs' / 'utils.md'
    before = page.read_bytes()
    for args in (('--check', 'utils'), ('utils',)):
        assert 'REFUSE utils: existing MyST directive' in run_generator(
            tmp_path, *args, expected_exit=1
        )
        assert page.read_bytes() == before


def test_directive_in_docstring_survives(tmp_path: Path) -> None:
    setup_generator(tmp_path)
    init = tmp_path / 'my' / 'files' / '__init__.py'
    init.write_text('"""Files.\n\n```{note}\nKeep this.\n```\n"""\n')
    check = run_generator(tmp_path, '--check', 'files')
    assert 'would update docs/files.md' in check
    run_generator(tmp_path, 'files')
    assert '```{note}\nKeep this.\n```' in (tmp_path / 'docs' / 'files.md').read_text()
    assert 'up to date' in run_generator(tmp_path, '--check', 'files')


@pyt.mark.parametrize(
    'directive',
    [
        '  ```{note}\n  Keep this.\n  ```',
        '> ```{note}\n> Keep this.\n> ```',
        ':::{note}\nKeep this.\n:::',
    ],
)
def test_nested_existing_directive_refuses_without_writes(tmp_path: Path, directive: str) -> None:
    setup_generator(tmp_path)
    page = tmp_path / 'docs' / 'files.md'
    page.write_text(f'# Manual intro\n\n{directive}\n\n```{{toctree}}\nchild\n```\n')
    before = {p.name: p.read_bytes() for p in (tmp_path / 'docs').glob('*.md')}
    for args in (('--check', 'files'), ('files',)):
        output = run_generator(tmp_path, *args, expected_exit=1)
        assert 'REFUSE files: existing MyST directive' in output
        assert '0 package(s)' in output
        assert {p.name: p.read_bytes() for p in (tmp_path / 'docs').glob('*.md')} == before


@pyt.mark.parametrize('existing_page', [False, True])
@pyt.mark.parametrize('fence', ['```', '~~~', ':::'])
def test_directive_tagline_refuses(tmp_path: Path, existing_page: bool, fence: str) -> None:
    setup_generator(tmp_path)
    page = tmp_path / 'docs' / 'fresh.md'
    init = tmp_path / 'my' / 'fresh' / '__init__.py'
    init.parent.mkdir()
    init.write_text(f'"""{fence}{{note}}\nKeep this.\n{fence}\n"""\n')
    if existing_page:
        page.write_text('# Manual intro\n\nKeep this too.\n')
    before = {p.name: p.read_bytes() for p in (tmp_path / 'docs').glob('*.md')}
    for args in (('--check', 'fresh'), ('fresh',)):
        assert 'REFUSE fresh: directive cannot be used as a tagline' in run_generator(
            tmp_path, *args, expected_exit=1
        )
        assert {p.name: p.read_bytes() for p in (tmp_path / 'docs').glob('*.md')} == before


def test_directive_order_and_bodies_are_not_reconciled_by_substring(tmp_path: Path) -> None:
    setup_generator(tmp_path)
    first = '```{note}\nFirst.\n```'
    second = '```{warning}\nSecond.\n```'
    page = tmp_path / 'docs' / 'files.md'
    page.write_text(f'# Old intro\n\n{first}\n\n{second}\n')
    init = tmp_path / 'my' / 'files' / '__init__.py'
    init.write_text(f'"""New intro.\n\n{second}\n\n{first}\n"""\n')
    before = page.read_bytes()
    for args in (('--check', 'files'), ('files',)):
        assert 'REFUSE files: existing MyST directive' in run_generator(
            tmp_path, *args, expected_exit=1
        )
        assert page.read_bytes() == before


def test_refusal_does_not_mask_successful_target(tmp_path: Path) -> None:
    setup_generator(tmp_path)
    for args in (('--check', 'utils', 'files'), ('utils', 'files')):
        output = run_generator(tmp_path, *args, expected_exit=1)
        assert 'REFUSE utils:' in output
        assert '1 package(s)' in output
