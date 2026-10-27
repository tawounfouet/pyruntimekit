# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Added

- Process and subprocess Executor contracts for the `0.1.0a4` isolated-execution milestone.
- Explicit `SubprocessCommand` / `ResolvedSubprocessWorkload` command boundary.
- Capability vocabulary for process execution, subprocess execution, process isolation and serialized boundaries.
- Initial `ProcessExecutor` backed by an owned `ProcessPoolExecutor`, with child-process isolation, result/failure normalization and explicit cleanup.
- Initial `SubprocessExecutor` with shell-free argv execution, cwd/env control, stdout/stderr capture, exit-code preservation and normalized non-zero exits.
- Explicit ProcessExecutor pickle boundary with input preflight, result serialization/deserialization normalization and qualified `SERIALIZED_BOUNDARY` capability.
- Bounded ProcessExecutor in-flight submission and SubprocessExecutor concurrency with observable load, cancellation-safe slot release and explicit close semantics.
- Capability-driven conformance matrix for ProcessExecutor and SubprocessExecutor covering shared isolation guarantees and backend-specific transport semantics.

## [0.1.0a3] - 2026-10-27

### Added

- Explicit asynchronous Executor contract and `ResolvedAsyncWorkload` for the `0.1.0a3` concurrency milestone.
- Executor capability vocabulary for async execution, thread execution, context propagation and bounded capacity.
- `AsyncExecutor` with explicit `asyncio.Task` execution, normalized async failures and cancellation-signal preservation.
- `ThreadExecutor` with owned `ThreadPoolExecutor`, explicit cleanup, thread failure normalization and truthful pre-context/pre-backpressure capabilities.
- Explicit per-execution `ContextVar` propagation and isolation for AsyncExecutor Tasks and ThreadExecutor pool submissions.
- Bounded local AsyncExecutor concurrency and ThreadExecutor in-flight submission with observable load and cancellation-safe thread capacity release.
- Standardized Executor conformance matrix shared by InlineExecutor, AsyncExecutor and ThreadExecutor.
- Transverse `0.1.0a3` Async/Thread milestone qualification covering compatibility, context isolation, bounded capacity, backpressure, cancellation truthfulness, cleanup and architecture boundaries.

## [0.1.0a2] - 2026-10-26

### Added

- `RuntimeKernel` command/decision authority for Run creation and canonical lifecycle transitions.
- Immutable kernel command contracts, pure transition engine and kernel architecture boundary tests.
- Immutable attempt-scoped `ExecutionContext` with correlation, optional tracing metadata and architecture isolation.
- `SimpleRunner` application orchestration for one configured executor, preserving Kernel lifecycle authority.
- Initial Executor contracts, `ResolvedWorkload`, capability declarations and deterministic in-process `InlineExecutor`.
- First synchronous public `Runtime.submit()` path with callable adaptation and application submission orchestration.
- Public `RunHandle` reference with `run_id`, `status()`, `result()` and `wait()` backed by an explicit ephemeral in-memory read registry.
- `0.1.0a2` transverse qualification suite covering lifecycle, events, public API and package-wide no-persistence/no-concurrency boundaries.

## [0.1.0a1] - 2026-10-25

### Added

- Initial repository bootstrap for the `0.1.0a1 — Domain Foundations` milestone.
- `src/` package layout and domain package boundary.
- Ruff, mypy, pytest, coverage and package-build baseline.
- GitHub Actions continuous integration workflow.
- Initial architecture decision records.
- Typed `RunId`, `WorkloadId`, `FailureId` and `EventId` domain identifiers.
- Canonical `RunState` enum with explicit stable string values and terminal-state classification.
- Backend-agnostic Workload model with durable references, descriptors and declarative resource hints.
- Principal `Run` aggregate with monotone `RunVersion` and immutable schema-versioned `RunSnapshot`.
- Immutable `Attempt` model with one-based `AttemptNumber` and stable terminal `AttemptOutcome` values.
- Normalized durable `Failure` model with normative category/origin/severity/scope taxonomies, symbolic codes and safe serialization.
- Backend-neutral generic `ExecutionResult` / `RunResult` contracts with immutable `ArtifactRef` and typed `ArtifactId`.
- Immutable versioned Run domain events with stable event types, UTC timestamps, aggregate versions and serializable payloads.
- Canonical Run lifecycle transition matrix with pure domain invariant validators and transition errors.
- Domain qualification checks for architectural boundaries, public exports, typed identifiers, PEP 561 packaging and the `>=95%` coverage gate.
