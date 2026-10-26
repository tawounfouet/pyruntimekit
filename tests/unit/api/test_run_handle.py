"""Tests for RunHandle reference semantics."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, cast

import pytest

from pyruntimekit import RunHandle
from pyruntimekit.domain import RunId, RunResult, RunState


class FakeResolver:
    def __init__(self, result: RunResult[object], state: RunState) -> None:
        self._result = result
        self._state = state
        self.status_calls: list[RunId] = []
        self.result_calls: list[RunId] = []

    def status(self, run_id: RunId) -> RunState:
        self.status_calls.append(run_id)
        return self._state

    def result(self, run_id: RunId) -> RunResult[object]:
        self.result_calls.append(run_id)
        return self._result


def test_handle_stores_reference_not_live_run() -> None:
    run_id = RunId.new()
    result = RunResult[object].success(
        completed_at=datetime(2026, 10, 26, 0, 45, tzinfo=UTC),
        value=42,
    )
    resolver = FakeResolver(result, RunState.SUCCEEDED)

    handle = RunHandle[object](run_id=run_id, _resolver=resolver)

    assert handle.run_id == run_id
    assert not hasattr(handle, "run")
    assert not hasattr(handle, "submission")
    assert not hasattr(handle, "runner_outcome")


def test_handle_reads_status_and_result_through_resolver() -> None:
    run_id = RunId.new()
    result = RunResult[object].success(
        completed_at=datetime(2026, 10, 26, 0, 45, tzinfo=UTC),
        value="done",
    )
    resolver = FakeResolver(result, RunState.SUCCEEDED)
    handle = RunHandle[object](run_id=run_id, _resolver=resolver)

    assert handle.status() is RunState.SUCCEEDED
    assert handle.result() is result
    assert handle.wait() is result
    assert resolver.status_calls == [run_id]
    assert resolver.result_calls == [run_id, run_id]


def test_handle_validates_run_id_and_resolver_contract() -> None:
    run_id = RunId.new()
    result = RunResult[object].success(
        completed_at=datetime(2026, 10, 26, 0, 45, tzinfo=UTC),
    )
    resolver = FakeResolver(result, RunState.SUCCEEDED)

    with pytest.raises(TypeError, match="RunId"):
        RunHandle[object](run_id=cast(Any, "run"), _resolver=resolver)

    with pytest.raises(TypeError, match="status"):
        RunHandle[object](run_id=run_id, _resolver=cast(Any, object()))

    class StatusOnly:
        def status(self, value: RunId) -> RunState:
            return RunState.SUCCEEDED

    with pytest.raises(TypeError, match="result"):
        RunHandle[object](run_id=run_id, _resolver=cast(Any, StatusOnly()))
