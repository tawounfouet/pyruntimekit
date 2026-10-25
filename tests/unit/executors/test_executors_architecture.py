"""Architecture qualification tests for executors."""

from __future__ import annotations

import ast
import importlib.util
from pathlib import Path

import pyruntimekit
import pyruntimekit.executors as executors
from pyruntimekit.executors.inline import InlineExecutor

FORBIDDEN_EXECUTOR_IMPORT_ROOTS = frozenset(
    {
        "asyncio",
        "threading",
        "multiprocessing",
        "subprocess",
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
    assert InlineExecutor is not None
    assert not hasattr(executors, "InlineExecutor")
    assert not hasattr(pyruntimekit, "InlineExecutor")
    assert not hasattr(pyruntimekit, "Executor")


def test_executors_have_no_hidden_concurrency_or_outer_dependencies() -> None:
    violations: list[str] = []
    for path in sorted(_executors_path().glob("*.py")):
        for module in sorted(_imports(path)):
            root = module.split(".", maxsplit=1)[0]
            if root in FORBIDDEN_EXECUTOR_IMPORT_ROOTS:
                violations.append(f"{path.name}: {module}")
                continue
            if module.startswith(FORBIDDEN_EXECUTOR_PREFIXES):
                violations.append(f"{path.name}: {module}")

    assert violations == [], "forbidden executor dependencies:\n" + "\n".join(violations)
