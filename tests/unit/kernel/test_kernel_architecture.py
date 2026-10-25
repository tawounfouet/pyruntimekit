"""Architecture qualification tests for the RuntimeKernel layer."""

from __future__ import annotations

import ast
import importlib.util
from pathlib import Path

import pyruntimekit
import pyruntimekit.kernel as kernel

FORBIDDEN_KERNEL_IMPORT_ROOTS = frozenset(
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

FORBIDDEN_HIGHER_LAYER_PREFIXES = (
    "pyruntimekit.api",
    "pyruntimekit.application",
    "pyruntimekit.contexts",
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


def _kernel_path() -> Path:
    spec = importlib.util.find_spec("pyruntimekit.kernel")
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


def test_kernel_package_is_importable_without_expanding_root_public_api() -> None:
    assert kernel.RuntimeKernel is not None
    assert not hasattr(pyruntimekit, "RuntimeKernel")


def test_kernel_has_no_infrastructure_or_higher_layer_dependencies() -> None:
    violations: list[str] = []

    for path in sorted(_kernel_path().glob("*.py")):
        for module in sorted(_imported_modules(path)):
            root = module.split(".", maxsplit=1)[0]
            if root in FORBIDDEN_KERNEL_IMPORT_ROOTS:
                violations.append(f"{path.name}: {module}")
                continue

            if module.startswith(FORBIDDEN_HIGHER_LAYER_PREFIXES):
                violations.append(f"{path.name}: {module}")

    assert violations == [], "forbidden kernel dependencies:\n" + "\n".join(violations)
