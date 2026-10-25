"""Architecture qualification tests for context models."""

from __future__ import annotations

import ast
import importlib.util
from pathlib import Path

import pyruntimekit
import pyruntimekit.contexts as contexts

FORBIDDEN_CONTEXT_IMPORT_ROOTS = frozenset(
    {
        "asyncio",
        "threading",
        "multiprocessing",
        "subprocess",
        "socket",
        "urllib",
        "http",
        "requests",
        "httpx",
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

FORBIDDEN_CONTEXT_PREFIXES = (
    "pyruntimekit.kernel",
    "pyruntimekit.application",
    "pyruntimekit.api",
    "pyruntimekit.executors",
    "pyruntimekit.stores",
    "pyruntimekit.checkpoints",
    "pyruntimekit.effects",
    "pyruntimekit.recovery",
    "pyruntimekit.workers",
    "pyruntimekit.coordination",
    "pyruntimekit.observability",
    "pyruntimekit.security",
    "pyruntimekit.sandbox",
)


def _contexts_path() -> Path:
    spec = importlib.util.find_spec("pyruntimekit.contexts")
    assert spec is not None
    assert spec.submodule_search_locations is not None
    return Path(next(iter(spec.submodule_search_locations)))


def _imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module is not None:
            modules.add(node.module)

    return modules


def test_contexts_package_is_importable_without_expanding_root_public_api() -> None:
    assert contexts.ExecutionContext is not None
    assert not hasattr(pyruntimekit, "ExecutionContext")


def test_contexts_depend_only_on_stdlib_and_domain() -> None:
    violations: list[str] = []

    for path in sorted(_contexts_path().glob("*.py")):
        for module in sorted(_imported_modules(path)):
            root = module.split(".", maxsplit=1)[0]
            if root in FORBIDDEN_CONTEXT_IMPORT_ROOTS:
                violations.append(f"{path.name}: {module}")
                continue

            if module.startswith(FORBIDDEN_CONTEXT_PREFIXES):
                violations.append(f"{path.name}: {module}")

    assert violations == [], "forbidden contexts dependencies:\n" + "\n".join(violations)
