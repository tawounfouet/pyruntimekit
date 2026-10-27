"""Package-wide architecture qualification for PyRuntimeKit 0.1.0a2."""

from __future__ import annotations

import ast
import importlib.util
from pathlib import Path

FORBIDDEN_CONCURRENCY_ROOTS = frozenset(
    {
        "asyncio",
        "threading",
        "multiprocessing",
        "subprocess",
        "concurrent",
        "queue",
    }
)

FORBIDDEN_PERSISTENCE_ROOTS = frozenset(
    {
        "sqlite3",
        "shelve",
        "dbm",
        "sqlalchemy",
        "asyncpg",
        "psycopg",
        "psycopg2",
        "redis",
        "pymongo",
        "motor",
    }
)

FUTURE_PACKAGES_NOT_IN_A2 = (
    "stores",
    "checkpoints",
    "effects",
    "recovery",
    "workers",
    "coordination",
    "concurrency",
    "observability",
    "policies",
    "security",
    "sandbox",
    "platform",
)

FILE_PERSISTENCE_CALLS = frozenset(
    {
        "open",
        "write_text",
        "write_bytes",
    }
)


def _package_path() -> Path:
    spec = importlib.util.find_spec("pyruntimekit")
    assert spec is not None
    assert spec.submodule_search_locations is not None
    return Path(next(iter(spec.submodule_search_locations)))


POST_A2_CONCURRENCY_FILES = frozenset(
    {
        Path("executors/async_.py"),
        Path("executors/process.py"),
        Path("executors/thread.py"),
    }
)


def _python_files() -> list[Path]:
    return sorted(_package_path().rglob("*.py"))


def _a2_concurrency_files() -> list[Path]:
    package = _package_path()
    return [
        path
        for path in _python_files()
        if path.relative_to(package) not in POST_A2_CONCURRENCY_FILES
    ]


def _tree(path: Path) -> ast.AST:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _imports(path: Path) -> set[str]:
    modules: set[str] = set()
    for node in ast.walk(_tree(path)):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            modules.add(node.module)
    return set(modules)


def test_a2_package_contains_only_bootstrap_runtime_layers() -> None:
    package = _package_path()

    assert {(package / name).is_dir() for name in FUTURE_PACKAGES_NOT_IN_A2} == {False}
    for name in FUTURE_PACKAGES_NOT_IN_A2:
        assert importlib.util.find_spec(f"pyruntimekit.{name}") is None


def test_a2_surfaces_have_no_hidden_concurrency_backend_imports() -> None:
    violations: list[str] = []

    for path in _a2_concurrency_files():
        for module in sorted(_imports(path)):
            if module.split(".", maxsplit=1)[0] in FORBIDDEN_CONCURRENCY_ROOTS:
                violations.append(f"{path.relative_to(_package_path())}: {module}")

    assert violations == [], "hidden concurrency dependencies:\n" + "\n".join(violations)


def test_a2_has_no_hidden_persistence_backend_imports() -> None:
    violations: list[str] = []

    for path in _python_files():
        for module in sorted(_imports(path)):
            if module.split(".", maxsplit=1)[0] in FORBIDDEN_PERSISTENCE_ROOTS:
                violations.append(f"{path.relative_to(_package_path())}: {module}")

    assert violations == [], "hidden persistence dependencies:\n" + "\n".join(violations)


def test_a2_has_no_hidden_file_persistence_or_sleep_calls() -> None:
    violations: list[str] = []

    for path in _python_files():
        for node in ast.walk(_tree(path)):
            if not isinstance(node, ast.Call):
                continue

            if isinstance(node.func, ast.Name) and node.func.id in FILE_PERSISTENCE_CALLS:
                violations.append(f"{path.relative_to(_package_path())}: call {node.func.id}()")
            elif isinstance(
                node.func, ast.Attribute
            ) and node.func.attr in FILE_PERSISTENCE_CALLS | {"sleep"}:
                violations.append(f"{path.relative_to(_package_path())}: call .{node.func.attr}()")

    assert violations == [], "hidden persistence/wait behavior:\n" + "\n".join(violations)


def test_a2_dependency_authorities_remain_separated() -> None:
    package = _package_path()
    kernel_modules = set()
    executor_modules = set()
    application_modules = set()

    for path in (package / "kernel").glob("*.py"):
        kernel_modules.update(_imports(path))
    for path in (package / "executors").glob("*.py"):
        executor_modules.update(_imports(path))
    for path in (package / "application").glob("*.py"):
        application_modules.update(_imports(path))

    assert not any(module.startswith("pyruntimekit.executors") for module in kernel_modules)
    assert not any(module.startswith("pyruntimekit.application") for module in kernel_modules)
    assert not any(module.startswith("pyruntimekit.kernel") for module in executor_modules)
    assert not any(module.startswith("pyruntimekit.application") for module in executor_modules)
    assert "pyruntimekit.executors.inline" not in application_modules
    assert "pyruntimekit.executors.base" in application_modules


def test_a2_does_not_depend_on_higher_level_pykits() -> None:
    forbidden = {"pyagentskit", "pyschedulekit"}
    violations: list[str] = []

    for path in _python_files():
        for module in sorted(_imports(path)):
            if module.split(".", maxsplit=1)[0] in forbidden:
                violations.append(f"{path.relative_to(_package_path())}: {module}")

    assert violations == [], "forbidden Py*Kit dependencies:\n" + "\n".join(violations)
