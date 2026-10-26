"""Public client reference to one submitted Run."""

from __future__ import annotations

from typing import Protocol, cast

from pyruntimekit.domain.enums import RunState
from pyruntimekit.domain.ids import RunId
from pyruntimekit.domain.result import RunResult


class _RunHandleResolver(Protocol):
    """Read boundary used by RunHandle without owning a live Run."""

    def status(self, run_id: RunId) -> RunState: ...

    def result(self, run_id: RunId) -> RunResult[object]: ...


class RunHandle[T]:
    """Reference to one execution, not ownership of a live Run."""

    __slots__ = ("_resolver", "run_id")

    def __init__(
        self,
        *,
        run_id: RunId,
        _resolver: _RunHandleResolver,
    ) -> None:
        if not isinstance(run_id, RunId):
            raise TypeError("run_id must be a RunId")
        if not callable(getattr(_resolver, "status", None)):
            raise TypeError("resolver must provide status(run_id)")
        if not callable(getattr(_resolver, "result", None)):
            raise TypeError("resolver must provide result(run_id)")

        self.run_id = run_id
        self._resolver = _resolver

    def status(self) -> RunState:
        """Return the latest Run state visible to this handle."""
        return self._resolver.status(self.run_id)

    def result(self) -> RunResult[T]:
        """Return the terminal logical RunResult without waiting."""
        return cast(RunResult[T], self._resolver.result(self.run_id))

    def wait(self) -> RunResult[T]:
        """Return the terminal result.

        The bootstrap Runtime is synchronous, so no polling or sleeping is
        required. Future asynchronous/durable runtimes can provide a resolver
        with explicit waiting semantics without changing handle ownership.
        """
        return self.result()


__all__ = ["RunHandle"]
