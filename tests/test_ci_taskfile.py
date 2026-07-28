############
### HEAD ###
############
### STANDARD
from __future__ import annotations
from pathlib import Path

### EXTERNAL
import pytest as pyt

### INTERNAL
# None -- this is a static-yaml consistency check, not a `my` import.


############
### DATA ###
############
# Every `task <name>` invocation in .gitlab-ci.yml must resolve to a task defined in
# either Taskfile.yaml (user overrides) or Taskfile.dist.yaml (generated). A copier template
# sync can drop project-specific tasks from Taskfile.dist.yaml; this test guards the
# contract so the CI job does not fail with "Task does not exist".
REPO_ROOT = Path(__file__).resolve().parents[1]
CI_FILE = REPO_ROOT / '.gitlab-ci.yml'
TASKFILE_YAML = REPO_ROOT / 'Taskfile.yaml'
TASKFILE_DIST_YAML = REPO_ROOT / 'Taskfile.dist.yaml'


############
### BODY ###
############
def _collect_task_invocations(ci_text: str) -> set[str]:
    """Return every `task <name>` invocation found in the CI script lines."""
    import re

    # Match `task <name>` or `task <name> <args>` in shell script lines.
    names: set[str] = set()
    for match in re.finditer(r'\btask\s+([A-Za-z0-9_:\-]+)', ci_text):
        names.add(match.group(1))
    return names


def _collect_task_definitions(*taskfile_paths: Path) -> set[str]:
    """Return every top-level task name defined in the given Taskfile YAMLs.

    Only keys indented under the top-level `tasks:` mapping are collected — the `vars:`
    section uses the same 4-space indentation, so a naive sweep would collect variable
    names as if they were tasks.
    """
    import re

    names: set[str] = set()
    for path in taskfile_paths:
        if not path.exists():
            continue
        text = path.read_text()
        tasks_match = re.search(r'^tasks:\s*$', text, flags=re.MULTILINE)
        if tasks_match is None:
            continue
        tasks_block = text[tasks_match.end() :]
        next_top = re.search(r'^\S', tasks_block, flags=re.MULTILINE)
        if next_top is not None:
            tasks_block = tasks_block[: next_top.start()]
        for match in re.finditer(r'^    ([A-Za-z0-9_:\-]+):\s*$', tasks_block, flags=re.MULTILINE):
            names.add(match.group(1))
    return names


@pyt.fixture(scope='module')
def ci_task_invocations() -> set[str]:
    return _collect_task_invocations(CI_FILE.read_text())


@pyt.fixture(scope='module')
def taskfile_definitions() -> set[str]:
    return _collect_task_definitions(TASKFILE_YAML, TASKFILE_DIST_YAML)


def test_all_ci_task_invocations_resolve(
    ci_task_invocations: set[str], taskfile_definitions: set[str]
):
    """Every `task <name>` in .gitlab-ci.yml must be defined in a Taskfile.

    Regression guard: the `Test Artifacts` CI job invokes `task test:artifacts`, which a
    copier template sync silently dropped from Taskfile.dist.yaml (commit 4b6167f). The job
    failed with "Task 'test:artifacts' does not exist".
    """
    # Filter out CLI subcommands of `task` itself (e.g. `task --list`) — only keep names
    # that look like task names (no leading dash).
    invocations = {name for name in ci_task_invocations if not name.startswith('-')}
    missing = invocations - taskfile_definitions
    assert not missing, (
        f'CI invokes `task <name>` for {sorted(missing)} but no task is defined in '
        f'Taskfile.yaml or Taskfile.dist.yaml.'
    )
