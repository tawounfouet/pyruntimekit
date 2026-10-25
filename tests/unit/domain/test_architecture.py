"""Architecture qualification tests for the Domain Foundations milestone."""

from __future__ import annotations

import ast
import importlib.resources
import importlib.util
from pathlib import Path

import pyruntimekit
import pyruntimekit.domain as domain


FORBIDDEN_DOMAIN_IMPORT_ROOTS = frozenset(
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

FORBIDDEN_INTERNAL_PREFIXES = (
    "pyruntimekit.api",
    "pyruntimekit.application",
    "pyruntimekit.kernel",
    "pyruntimekit.contexts",
    "pyruntimekit.executors",
    "pyruntimekit.stores",
    "pyruntimekit.checkpoints",
    "pyruntimekit.effects",
    "pyruntimekit.recovery",
    "pyruntimekit.workers",
    "pyruntimekit.coordination",
    "pyruntimekit.concurrency",
    "pyruntimekit.observability",
    "pyruntimekit.policies",
    "pyruntimekit.security",
    "pyruntimekit.sandbox",
    "pyruntimekit.platform",
)


def _domain_path() -> Path:
    spec = importlib.util.find_spec("pyruntimekit.domain")
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


def test_package_and_domain_are_importable() -> None:
    assert pyruntimekit.__version__ == "0.1.0a1"
    assert domain.RunState.CREATED.value == "CREATED"


def test_domain_public_exports_are_unique_and_resolvable() -> None:
    assert len(domain.__all__) == len(set(domain.__all__))
    assert all(not name.startswith("_") for name in domain.__all__)
    assert all(hasattr(domain, name) for name in domain.__all__)


def test_domain_has_no_forbidden_infrastructure_dependencies() -> None:
    violations: list[str] = []

    for path in sorted(_domain_path().glob("*.py")):
        for module in sorted(_imported_modules(path)):
            root = module.split(".", maxsplit=1)[0]
            if root in FORBIDDEN_DOMAIN_IMPORT_ROOTS:
                violations.append(f"{path.name}: {module}")
                continue

            if module.startswith(FORBIDDEN_INTERNAL_PREFIXES):
                violations.append(f"{path.name}: {module}")

    assert violations == [], "forbidden domain dependencies:\n" + "\n".join(violations)


def test_typed_package_declares_pep561_marker() -> None:
    marker = importlib.resources.files("pyruntimekit").joinpath("py.typed")

    assert marker.is_file()
