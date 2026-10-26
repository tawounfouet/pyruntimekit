"""Architecture qualification tests for the application layer."""

from __future__ import annotations

import ast
import importlib.util
from pathlib import Path

import pyruntimekit
import pyruntimekit.application as application

FORBIDDEN_APPLICATION_IMPORT_ROOTS = frozenset(
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

FORBIDDEN_APPLICATION_PREFIXES = (
    "pyruntimekit.api",
    "pyruntimekit.executors.inline",
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


def _application_path() -> Path:
    spec = importlib.util.find_spec("pyruntimekit.application")
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


def test_application_is_importable_without_expanding_root_public_api() -> None:
    assert application.SimpleRunner is not None
    assert not hasattr(pyruntimekit, "SimpleRunner")
    assert not hasattr(pyruntimekit, "Runner")


def test_application_depends_on_executor_contract_not_concrete_backend() -> None:
    runner_path = _application_path() / "runner.py"
    imported = _imported_modules(runner_path)

    assert "pyruntimekit.executors.base" in imported
    assert "pyruntimekit.executors.inline" not in imported


def test_application_has_no_infrastructure_or_outer_layer_dependencies() -> None:
    violations: list[str] = []

    for path in sorted(_application_path().glob("*.py")):
        for module in sorted(_imported_modules(path)):
            root = module.split(".", maxsplit=1)[0]
            if root in FORBIDDEN_APPLICATION_IMPORT_ROOTS:
                violations.append(f"{path.name}: {module}")
                continue
            if module.startswith(FORBIDDEN_APPLICATION_PREFIXES):
                violations.append(f"{path.name}: {module}")

    assert violations == [], "forbidden application dependencies:\n" + "\n".join(violations)
