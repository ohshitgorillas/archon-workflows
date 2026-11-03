Status: approved. Owner, 2026-11-02: "fix the goddamn plan file yourself and then execute it through subagents directly"; cut to the request after "this is an extremely simple and small task".

## Why

The `feature-pipeline` pack runs every task down one path: a Plan of code steps, then a Spec of tests. A tests-only task (refactor a test suite) cannot be planned, because the Plan's `steps` has `minItems: 1` in `plan-review/plan-review.yaml`. A test-free task (refactor the code, keep behaviour) always goes through the specifier, which may write tests the task should not touch.

## Change

All paths are under `.archon/workflows/feature-pipeline/plan-review/`. Nothing else in the pack changes.

### `plan-review.yaml`

```yaml
# plan's output_format gains (optional; absent means full):
track: { type: string, enum: [full, tests-only, test-free] }
# plan's steps: minItems 1 removed

# round, plan-round branch, when no blocking finding is filed:
#   track test-free -> next: done, spec: {lines: [], helpers: [], steps: [], decisions: []}
#   otherwise       -> next: spec (as now)
```

### `commands/plan.md`

The planner sets `track` from the design's words:

- `tests-only`: only tests and test support change. The Plan has no code step.
- `test-free`: production code changes, behaviour is kept, and no test or test support changes. No step path is a test file or test support.
- `full`: anything else, and whenever the design does not settle it.

### Fixtures

- `fixtures/tests-only.stubs.yaml`: `plan` returns `track: tests-only` and `steps: []`; the run reaches `spec` and passes.
- `fixtures/test-free.stubs.yaml`: `plan` returns `track: test-free` and one code step; `spec` and `arbitrate` are not reached; `verdict` passes with the empty Spec.

## Order

1. `workflow-builder`: `plan-review/plan-review.yaml`, `plan-review/commands/plan.md`, the two new fixtures. Done-check: the "Checking the pack" home of `docs/superpowers/specs/feature-pipeline-finish-design.md`.
