"""Tests for KernelDecision consistency guards."""

from datetime import UTC, datetime

import pytest

from pyruntimekit.domain import (
    RunCreated,
    RunResult,
    RunState,
    RunVersion,
    WorkloadId,
)
from pyruntimekit.kernel import CreateRun, KernelDecision, KernelInvariantError, RuntimeKernel

NOW = datetime(2026, 10, 25, 21, 0, tzinfo=UTC)


def _created_decision() -> KernelDecision:
    return RuntimeKernel().create(
        CreateRun(
            at=NOW,
            workload_id=WorkloadId.new(),
        )
    )


def test_decision_requires_emitted_event() -> None:
    valid = _created_decision()

    with pytest.raises(KernelInvariantError, match="at least one"):
        KernelDecision(
            run=valid.run,
            previous_state=None,
            next_state=RunState.CREATED,
            emitted_events=(),
        )


def test_decision_requires_event_version_to_match_run_version() -> None:
    valid = _created_decision()
    mismatched = RunCreated.create(
        run_id=valid.run.run_id,
        aggregate_version=RunVersion(1),
        occurred_at=NOW,
    )

    with pytest.raises(KernelInvariantError, match="aggregate_version"):
        KernelDecision(
            run=valid.run,
            previous_state=None,
            next_state=RunState.CREATED,
            emitted_events=(mismatched,),
        )


def test_decision_requires_event_run_identity_to_match() -> None:
    valid = _created_decision()
    other = _created_decision()
    mismatched = RunCreated.create(
        run_id=other.run.run_id,
        aggregate_version=valid.run.version,
        occurred_at=NOW,
    )

    with pytest.raises(KernelInvariantError, match="run_id"):
        KernelDecision(
            run=valid.run,
            previous_state=None,
            next_state=RunState.CREATED,
            emitted_events=(mismatched,),
        )


def test_decision_requires_event_time_to_match_run_update_time() -> None:
    valid = _created_decision()
    mismatched = RunCreated.create(
        run_id=valid.run.run_id,
        aggregate_version=valid.run.version,
        occurred_at=datetime(2026, 10, 25, 21, 0, 1, tzinfo=UTC),
    )

    with pytest.raises(KernelInvariantError, match="occurred_at"):
        KernelDecision(
            run=valid.run,
            previous_state=None,
            next_state=RunState.CREATED,
            emitted_events=(mismatched,),
        )


def test_created_decision_requires_created_state_and_version_zero() -> None:
    kernel = RuntimeKernel()
    created = _created_decision()
    admitted = kernel.apply(
        created.run,
        __import__("pyruntimekit.kernel", fromlist=["AdmitRun"]).AdmitRun(
            at=datetime(2026, 10, 25, 21, 0, 1, tzinfo=UTC)
        ),
    )

    with pytest.raises(KernelInvariantError, match="only Run creation"):
        KernelDecision(
            run=admitted.run,
            previous_state=None,
            next_state=RunState.ADMITTED,
            emitted_events=admitted.emitted_events,
        )


def test_non_terminal_decision_rejects_final_result() -> None:
    valid = _created_decision()
    result = RunResult[object].success(completed_at=NOW)

    with pytest.raises(KernelInvariantError, match="only valid"):
        KernelDecision(
            run=valid.run,
            previous_state=None,
            next_state=RunState.CREATED,
            emitted_events=valid.emitted_events,
            final_result=result,
        )
