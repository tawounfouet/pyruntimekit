"""Architecture tests for the initial public API layer."""

from __future__ import annotations

import ast
import importlib.util
from pathlib import Path

import pyruntimekit

FORBIDDEN_API_IMPORT_ROOTS = frozenset(
    {
        "asyncio",
        "threading",
        "multiprocessing",
        "subprocess",
        "socket",
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


def _api_path() -> Path:
    spec = importlib.util.find_spec("pyruntimekit.api")
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


def test_runtime_and_run_handle_are_the_public_bootstrap_symbols() -> None:
    assert pyruntimekit.Runtime is not None
    assert pyruntimekit.RunHandle is not None
    assert set(pyruntimekit.__all__) == {"RunHandle", "Runtime", "__version__"}


def test_api_has_no_hidden_concurrency_or_infrastructure_dependencies() -> None:
    violations: list[str] = []
    for path in sorted(_api_path().glob("*.py")):
        for module in sorted(_imports(path)):
            if module.split(".", maxsplit=1)[0] in FORBIDDEN_API_IMPORT_ROOTS:
                violations.append(f"{path.name}: {module}")

    assert violations == [], "forbidden API dependencies:\n" + "\n".join(violations)
