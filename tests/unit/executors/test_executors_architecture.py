"""Architecture qualification tests for executors."""

from __future__ import annotations

import ast
import importlib.util
from pathlib import Path

import pyruntimekit
import pyruntimekit.executors as executors
from pyruntimekit.executors.async_ import AsyncExecutor
from pyruntimekit.executors.inline import InlineExecutor
from pyruntimekit.executors.thread import ThreadExecutor

FORBIDDEN_EXECUTOR_IMPORT_ROOTS = frozenset(
    {
        "asyncio",
        "threading",
        "multiprocessing",
        "subprocess",
        "concurrent",
        "sqlalchemy",
        "asyncpg",
        "psycopg",
        "psycopg2",
        "redis",
        "celery",
        "docker",
        "opentelemetry",
        "pyagentskit",
        "pyschedulekit",
    }
)

ALLOWED_CONCURRENCY_IMPORTS_BY_FILE = {
    "async_.py": frozenset({"asyncio"}),
    "thread.py": frozenset({"asyncio", "concurrent"}),
}

FORBIDDEN_EXECUTOR_PREFIXES = (
    "pyruntimekit.api",
    "pyruntimekit.application",
    "pyruntimekit.kernel",
    "pyruntimekit.stores",
    "pyruntimekit.workers",
    "pyruntimekit.coordination",
)


def _executors_path() -> Path:
    spec = importlib.util.find_spec("pyruntimekit.executors")
    assert spec is not None
    assert spec.submodule_search_locations is not None
    return Path(next(iter(spec.submodule_search_locations)))


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            modules.add(node.module)
    return modules


def test_executors_package_is_importable_without_root_api_expansion() -> None:
    assert executors.Executor is not None
    assert executors.AsyncExecutorContract is not None
    assert AsyncExecutor is not None
    assert InlineExecutor is not None
    assert ThreadExecutor is not None
    assert not hasattr(executors, "AsyncExecutor")
    assert not hasattr(executors, "InlineExecutor")
    assert not hasattr(executors, "ThreadExecutor")
    assert not hasattr(pyruntimekit, "AsyncExecutor")
    assert not hasattr(pyruntimekit, "InlineExecutor")
    assert not hasattr(pyruntimekit, "ThreadExecutor")
    assert not hasattr(pyruntimekit, "Executor")


def test_executor_concurrency_imports_are_backend_scoped() -> None:
    violations: list[str] = []

    for path in sorted(_executors_path().glob("*.py")):
        allowed = ALLOWED_CONCURRENCY_IMPORTS_BY_FILE.get(path.name, frozenset())
        for module in sorted(_imports(path)):
            root = module.split(".", maxsplit=1)[0]
            if root in FORBIDDEN_EXECUTOR_IMPORT_ROOTS and root not in allowed:
                violations.append(f"{path.name}: {module}")

    assert violations == [], "forbidden executor dependencies:\n" + "\n".join(violations)


def test_executors_have_no_outer_layer_dependencies() -> None:
    violations: list[str] = []

    for path in sorted(_executors_path().glob("*.py")):
        for module in sorted(_imports(path)):
            if module.startswith(FORBIDDEN_EXECUTOR_PREFIXES):
                violations.append(f"{path.name}: {module}")

    assert violations == [], "forbidden executor dependencies:\n" + "\n".join(violations)
