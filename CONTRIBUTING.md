# Contributing to PyRuntimeKit

PyRuntimeKit is being implemented incrementally from explicit specifications and qualification gates.

## Requirements

- Python 3.12 or newer
- Git

## Setup

    python -m venv .venv
    source .venv/bin/activate
    python -m pip install -e ".[dev]"

## Branching

Use short-lived feature branches:

    feat/<scope>

Examples:

    feat/bootstrap
    feat/typed-identifiers
    feat/run-aggregate

## Pull requests

A pull request should be small, reviewable, single-purpose and testable. Avoid implementing an entire milestone in one PR.

Every PR must keep unrelated changes out of scope and, where relevant, reference the specification or ADR that motivates the change.

## Quality gate

Before opening or updating a PR, run:

    ruff check .
    ruff format --check .
    mypy src tests
    pytest --cov=pyruntimekit --cov-report=term-missing
    python -m build

## Architecture rules

- `domain/` must not depend on infrastructure or concrete execution mechanisms.
- Dependency direction must point inward toward domain contracts.
- New packages are created when their milestone begins, not as empty future scaffolding.
- Significant architectural divergence requires an ADR.

## Commit style

Prefer coherent conventional-style commits such as:

    feat(domain): add typed run identifiers
    test(domain): qualify run lifecycle invariants
    docs(adr): record runtime kernel transition ownership
    chore(ci): add package build check
