"""Exercise the module docs generator against isolated page trees."""

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run_generator(root: Path, *args: str) -> str:
    result = subprocess.run(
        [sys.executable, str(root / 'docs' / 'gen_module_docs.py'), *args],
        check=True,
        capture_output=True,
        text=True,
    )
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


def test_refuses_to_remove_existing_directive(tmp_path: Path) -> None:
    setup_generator(tmp_path)
    page = tmp_path / 'docs' / 'utils.md'
    before = page.read_bytes()
    for args in (('--check', 'utils'), ('utils',)):
        assert 'REFUSE utils: existing MyST directive' in run_generator(tmp_path, *args)
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
