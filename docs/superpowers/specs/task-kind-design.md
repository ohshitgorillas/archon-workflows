Status: approved. Owner, 2026-11-02: "fix the goddamn plan file yourself and then execute it through subagents directly", after rejecting the prosecutor's ruling on the track.

## Why

The `feature-pipeline` pack runs every task down one path: a Plan of code steps, then a Spec of test steps, then a build of both. It has no notion of a task that changes only tests, or only code.

- A tests-only task (refactor a test suite) cannot be planned as one. `plan-review/plan-review.yaml` gives the Plan's `steps` `minItems: 1`, and `plan-review/commands/plan.md` and `plan-review/commands/prosecute.md` demand a step or a `landed` entry for every unit in scope. The planner must invent a code step or squeeze the test work into a Plan step through the "repairs or ports existing tests" exception, so test work has two homes, the Plan and the Spec.
- That exception is written three times: `plan-review/commands/plan.md`, `plan-review/commands/prosecute.md` and `plan-review/commands/arbitrate.md`.
- A test-free task (refactor the code, keep its behaviour) always goes through the specifier and the arbiter. `round` in `plan-review/plan-review.yaml` sends every passing Plan round to `spec`. Nothing tells the specifier that no test should change, so it may write new or changed tests for a task meant to touch none.
- The Spec already carries test-only work: a line whose `step` is null and a test step whose `before` is null, built after every Plan step. `plan-review/commands/spec.md`, `plan-review/commands/arbitrate.md`, `build-loop/commands/write.md` and `build-loop/commands/review.md` each state that rule. A tests-only task needs no new build machinery, only a Plan that may hold no code step.
- `finish/commands/bail.md`'s pin check already fails any committed test change that no Spec line names. With an empty Spec, that check is the test-free guard as it stands.

## Modules

All changes sit in the `feature-pipeline` pack at `.archon/workflows/feature-pipeline/`, as YAML and command prose. No script, node or file is added except two fixtures. `build-loop` and `finish` are unchanged.

### `plan-review/plan-review.yaml`

The Plan carries the task's track. `round` routes on it, and `verdict` returns it.

```yaml
# plan's output_format, top level, gains (required):
track: { type: string, enum: [full, tests-only, test-free] }
# plan's steps: minItems 1 removed (maxItems 20 stays)

# round (jq), plan-round branch; ($resolved.plan.track // "full") is the track:
#   blocking finding filed         -> next: plan        (as now)
#   none, track test-free          -> next: done, spec: {lines: [], helpers: [], steps: [], decisions: []}
#   none, track full or tests-only -> next: spec        (as now)
# spec-round branch, caps and refusal: unchanged

# verdict's output_format, top level, gains (required):
track: { type: string, enum: [full, tests-only, test-free] }
#   the plan's track; "full" when a recalled record's plan has none
```

Replaces: the Plan's `minItems: 1` on `steps`, and the unconditional route from a passing Plan round to `spec`.

### `plan-review/commands/plan.md`

The planner sets `track` from the design's words:

- `tests-only`: the task changes only tests and test support. No production path changes.
- `test-free`: the task changes production code and keeps its behaviour, and no test or test support has to change. A change that forces an existing test to change is `full`, with that test's edits pinned as port lines.
- `full`: every other task. Use `full` when the design does not settle the track.

Rules by track:

- `full`: the rules as they stand.
- `tests-only`: no step has `kind: code`. Plan steps are only `merge` steps from the prior cycle's sync conflicts, so `steps` may be empty. A unit with test work gets no step and is not listed in `landed`; the Spec serves it. A unit whose whole work is a green full gate is still listed in `landed`.
- `test-free`: at least one step. No path is a test file or test support, with no exception. Each step's check runs the existing tests that cover its section, and nothing else proves the step.

The "repairs or ports existing tests" exception holds only on the `full` track.

### `plan-review/commands/prosecute.md`

The prosecutor takes the Plan's `track` as given and never rules on it. It holds the Plan to the planner's rules for that track. On the `tests-only` track, "every unit in scope has a step or is listed in `landed`" is replaced by "no step is a code step". On the `test-free` track, the prosecutor allows no test path and requires each check to run the existing tests of its section.

### `plan-review/commands/spec.md`

The specifier reads the Plan's `track`; it never runs on `test-free`. On `tests-only`, every line has `step` null and mark GREEN, and every test step has `before` null. Every unit in scope that is not in `landed` is served by at least one test step. On `full`, the rules stand as written.

### `plan-review/commands/arbitrate.md`

On `tests-only`, the arbiter checks that every line has `step` null and every test step has `before` null. It also checks that every unit in scope that is not in `landed` is served by a test step. On `full`, its checks stand as written. The Plan-path test-file check holds the exception only on `full`.

### `feature/feature.yaml`

`gate`'s attention text opens with the line `Track: $planning.output.track`, above the Plan.

### Fixtures

- Every existing `plan` stub in `plan-review/fixtures/*.stubs.yaml` gains `track: full`. Every existing `verdict` stub in `feature/fixtures/*.stubs.yaml` gains `track: full`.
- `plan-review/fixtures/tests-only.stubs.yaml`: `plan` returns `track: tests-only` and `steps: []`. `prosecute` passes. `spec` returns lines with `step` null and one test step with `before` null, and `arbitrate` passes. `cite`, `probe`, `round`, `verdict` and `keep` run unstubbed. `verdict`'s `track` is `tests-only`, and `keep`'s resolved text holds the spec's test step.
- `plan-review/fixtures/test-free.stubs.yaml`: `plan` returns `track: test-free` and one code step, and `prosecute` passes. `spec` and `arbitrate` are not reached. `round`'s `next` is `done`, and `verdict` is `pass` with `track: test-free` and the empty spec.
- `feature/fixtures/approved.stubs.yaml`: `gate`'s resolved text holds `Track: full`.

## Homes

| Concern | Home | Forbidden elsewhere |
|---|---|---|
| A task's track | the Plan's `track`, set by the planner alone; no reviewer rules on it | A track or kind field in the Spec, a record, `build-loop` or `finish`; any other agent or node classifying or reviewing the track |
| Routing by track | `plan-review`'s `round`, the only node that reads `track` to choose a path | A `when:` on `track`; `build-loop`, `finish` or `bail` branching on it |
| Test work | the Spec, on every track; on `full` only, a Plan step that repairs or ports existing tests and changes no production behaviour | A test path in a `tests-only` or `test-free` Plan step; a Spec on `test-free` |
| Behaviour kept on `test-free` | each Plan step's check, running the existing tests of its section; `finish`'s `gate`; `bail`'s pin check against the empty Spec | New tests, a mutation run or a witness for a `test-free` task |
| Showing the track to the owner | `verdict`'s `track`, shown by `feature`'s `gate` | Any other node composing or rewording the track for the owner |

## Order

Each step's done-check is the "Checking the pack" home of `docs/superpowers/specs/feature-pipeline-finish-design.md`. Build on `main` as it stands. `docs/superpowers/specs/plan-review-escalate-design.md`'s unmerged build edits the same `plan-review.yaml` `round` and `verdict`, the `plan.md`, `spec.md` and `arbitrate.md` commands, and `feature.yaml`'s `gate`. Whichever lands second merges onto the other. When that build is merged, the gate line reads `$review.output.track`, and `track` is declared wherever `review` re-emits `verdict`'s fields.

1. `workflow-builder`: `.archon/workflows/feature-pipeline/plan-review/plan-review.yaml`, `.archon/workflows/feature-pipeline/plan-review/commands/plan.md`, `.archon/workflows/feature-pipeline/plan-review/commands/prosecute.md`, `.archon/workflows/feature-pipeline/plan-review/commands/spec.md`, `.archon/workflows/feature-pipeline/plan-review/commands/arbitrate.md` and `.archon/workflows/feature-pipeline/plan-review/fixtures/*.stubs.yaml`, with the new `tests-only` and `test-free` fixtures.
2. `workflow-builder`: `.archon/workflows/feature-pipeline/feature/feature.yaml` and `.archon/workflows/feature-pipeline/feature/fixtures/*.stubs.yaml`.
3. `architect`: `docs/superpowers/specs/plan-review-design.md`, stated with the Plan's `track`, `round`'s route on it, `verdict`'s `track` and the two fixtures.
