"""Architecture qualification for the 0.1.0a4 isolated executors."""

from __future__ import annotations

import ast
import importlib.util
from pathlib import Path

import pyruntimekit
import pyruntimekit.executors as executors
from pyruntimekit.executors import (
    ASYNC_EXECUTOR_CAPABILITIES,
    INLINE_EXECUTOR_CAPABILITIES,
    PROCESS_EXECUTOR_CAPABILITIES,
    SUBPROCESS_EXECUTOR_CAPABILITIES,
    THREAD_EXECUTOR_CAPABILITIES,
    ExecutorCapability,
)


def _package_path() -> Path:
    spec = importlib.util.find_spec("pyruntimekit")
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


def test_a4_root_api_remains_a2_compatible() -> None:
    assert pyruntimekit.__version__ == "0.1.0a3"
    assert pyruntimekit.__all__ == ["RunHandle", "Runtime", "__version__"]
    for name in (
        "ProcessExecutor",
        "SubprocessExecutor",
        "ProcessRuntime",
        "SubprocessRuntime",
        "AsyncRuntime",
        "ThreadRuntime",
    ):
        assert not hasattr(pyruntimekit, name)
    assert not hasattr(executors, "ProcessExecutor")
    assert not hasattr(executors, "SubprocessExecutor")


def test_a4_isolated_capabilities_are_exact() -> None:
    assert PROCESS_EXECUTOR_CAPABILITIES.values == frozenset(
        {
            ExecutorCapability.TRUSTED_ONLY,
            ExecutorCapability.PROCESS_EXECUTION,
            ExecutorCapability.PROCESS_ISOLATION,
            ExecutorCapability.SERIALIZED_BOUNDARY,
            ExecutorCapability.BOUNDED_CAPACITY,
        }
    )
    assert SUBPROCESS_EXECUTOR_CAPABILITIES.values == frozenset(
        {
            ExecutorCapability.TRUSTED_ONLY,
            ExecutorCapability.SUBPROCESS_EXECUTION,
            ExecutorCapability.PROCESS_ISOLATION,
            ExecutorCapability.BOUNDED_CAPACITY,
        }
    )
    for old in (
        INLINE_EXECUTOR_CAPABILITIES,
        ASYNC_EXECUTOR_CAPABILITIES,
        THREAD_EXECUTOR_CAPABILITIES,
    ):
        assert not old.supports(ExecutorCapability.PROCESS_EXECUTION)
        assert not old.supports(ExecutorCapability.SUBPROCESS_EXECUTION)
        assert not old.supports(ExecutorCapability.PROCESS_ISOLATION)


def test_a4_kernel_application_and_api_do_not_bind_to_new_backends() -> None:
    package = _package_path()
    disallowed = {
        "pyruntimekit.executors.process",
        "pyruntimekit.executors.subprocess",
        "pyruntimekit.executors.process_serialization",
    }
    violations = []
    for layer in ("kernel", "application", "api"):
        for path in (package / layer).rglob("*.py"):
            for module in _imports(path):
                if module in disallowed:
                    violations.append(f"{path.relative_to(package)}: {module}")
    assert not violations, violations


def test_a4_defers_persistence_workers_and_distributed_execution() -> None:
    package = _package_path()
    for name in (
        "stores",
        "checkpoints",
        "effects",
        "recovery",
        "workers",
        "coordination",
        "sandbox",
    ):
        assert not (package / name).exists()
        assert importlib.util.find_spec(f"pyruntimekit.{name}") is None
    for name in (
        "REMOTE_EXECUTION",
        "DURABLE_EXECUTION",
        "DISTRIBUTED_EXECUTION",
        "TIMEOUT",
        "DEADLINE",
        "HARD_CANCELLATION",
    ):
        assert name not in ExecutorCapability.__members__
