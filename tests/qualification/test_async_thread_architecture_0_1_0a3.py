"""Architecture qualification for PyRuntimeKit 0.1.0a3 local concurrency."""

from __future__ import annotations

import ast
import importlib.util
from pathlib import Path

import pyruntimekit
from pyruntimekit.executors import ExecutorCapability

FORBIDDEN_EXECUTOR_PREFIXES = (
    "pyruntimekit.api",
    "pyruntimekit.application",
    "pyruntimekit.kernel",
)

DEFERRED_PACKAGES = (
    "stores",
    "checkpoints",
    "effects",
    "recovery",
    "workers",
    "coordination",
    "sandbox",
)

CONCRETE_CONCURRENT_EXECUTORS = frozenset(
    {
        "pyruntimekit.executors.async_",
        "pyruntimekit.executors.thread",
    }
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


def test_a3_executor_layer_does_not_own_runtime_lifecycle() -> None:
    package = _package_path()
    violations: list[str] = []

    for path in sorted((package / "executors").glob("*.py")):
        for module in sorted(_imports(path)):
            if module.startswith(FORBIDDEN_EXECUTOR_PREFIXES):
                violations.append(f"{path.name}: {module}")

    assert violations == [], "executor authority violations:\n" + "\n".join(violations)


def test_a3_kernel_and_application_do_not_bind_to_concurrent_backends() -> None:
    package = _package_path()
    violations: list[str] = []

    for layer in ("kernel", "application"):
        for path in sorted((package / layer).glob("*.py")):
            for module in sorted(_imports(path)):
                if module in CONCRETE_CONCURRENT_EXECUTORS:
                    violations.append(f"{path.relative_to(package)}: {module}")

    assert violations == [], "concrete executor coupling:\n" + "\n".join(violations)


def test_a3_does_not_introduce_deferred_runtime_packages() -> None:
    package = _package_path()

    for name in DEFERRED_PACKAGES:
        assert not (package / name).is_dir()
        assert importlib.util.find_spec(f"pyruntimekit.{name}") is None


def test_a3_executors_do_not_claim_deferred_execution_semantics() -> None:
    from pyruntimekit.executors import (
        ASYNC_EXECUTOR_CAPABILITIES,
        INLINE_EXECUTOR_CAPABILITIES,
        THREAD_EXECUTOR_CAPABILITIES,
    )

    deferred = {
        capability
        for name, capability in ExecutorCapability.__members__.items()
        if name
        in {
            "PROCESS_EXECUTION",
            "SUBPROCESS_EXECUTION",
            "PROCESS_ISOLATION",
            "SERIALIZED_BOUNDARY",
            "REMOTE_EXECUTION",
            "DURABLE_EXECUTION",
            "DISTRIBUTED_EXECUTION",
        }
    }

    for capabilities in (
        INLINE_EXECUTOR_CAPABILITIES,
        ASYNC_EXECUTOR_CAPABILITIES,
        THREAD_EXECUTOR_CAPABILITIES,
    ):
        assert capabilities.values.isdisjoint(deferred)


def test_a3_root_api_does_not_claim_public_async_or_thread_runtime() -> None:
    assert not hasattr(pyruntimekit, "AsyncRuntime")
    assert not hasattr(pyruntimekit, "ThreadRuntime")
    assert not hasattr(pyruntimekit, "AsyncExecutor")
    assert not hasattr(pyruntimekit, "ThreadExecutor")
