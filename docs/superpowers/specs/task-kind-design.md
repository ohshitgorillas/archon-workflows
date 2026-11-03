Status: approved. Owner, 2026-11-02: "fix the goddamn plan file yourself and then execute it through subagents directly"; then "this is an extremely simple and small task" and "what is the point of having a fucking zero-code plan reviewed".

## Why

`plan-review` runs every task down one path: Plan rounds (planner, prosecutor), then Spec rounds (specifier, arbiter). A tests-only task (refactor a test suite) has no code to plan, and a test-free task (refactor the code, keep behaviour) has no tests to spec, yet both go through both.

## Change

All paths are under `.archon/workflows/feature-pipeline/plan-review/`. Nothing else in the pack changes.

- A first node, `track`, reads the design and scope and returns `full`, `tests-only` or `test-free`. `tests-only`: only tests and test support change. `test-free`: production code changes, behaviour is kept, no test changes. `full`: anything else, and whenever the design does not settle it. Nothing reviews it.
- `tests-only`: no Plan round runs. The Plan is empty (`steps: []`; `minItems: 1` goes) and the Spec rounds run as now.
- `test-free`: the Plan rounds run as now; no Spec round runs, and the Spec is empty.
- `full`: unchanged.

## Fixtures

- `fixtures/tests-only.stubs.yaml`: `track` returns `tests-only`; `plan` and `prosecute` are not reached; the Spec rounds pass.
- `fixtures/test-free.stubs.yaml`: `track` returns `test-free`; `spec` and `arbitrate` are not reached; the Plan rounds pass.
- Existing fixtures stub `track` as `full`.

## Order

1. `workflow-builder`: `plan-review/plan-review.yaml`, a command file for `track` if the node needs one, and the fixtures above. Done-check: the "Checking the pack" home of `docs/superpowers/specs/feature-pipeline-finish-design.md`.
