design docs/superpowers/specs/feature-pipeline-finish-design.md | order docs/superpowers/specs/feature-pipeline-finish-design.md | main f02aada
landed 1 | f73fd20
landed 3 | 03bd26b
landed 4 | 4b365ad
landed 5 | bd4ea74
landed 6 | 82a6c27
landed 7 | 5de99e0
landed 8 | 4de98bd
section s1 | lead | steps: 2, 9 | size: lead: 14 finished, peak context median 59105, p90 86307, max 94415; 32 overruns
  s1.d1 | role-author | steps: 2 | writes: /home/atom/.claude/agents/workflow-builder.md | size: calibration load: 13k
    queue docs/superpowers/queues/feature-pipeline-finish.md s1.d1
    role workflow-builder
    design docs/superpowers/specs/feature-pipeline-finish-design.md
    2. `role-author`: `~/.claude/agents/workflow-builder.md`, pointed at this design for the pack homes, with pack code written only under `.archon/workflows/feature-pipeline/`.
  s1.d2 | architect | steps: 9 | writes: docs/superpowers/specs/plan-review-design.md | size: architect: 1 finished, peak context median 62409, p90 62409, max 62409; 0 overruns load: 17k
    queue docs/superpowers/queues/feature-pipeline-finish.md s1.d2
    rulings docs/superpowers/specs/plan-review-design.md
    design docs/superpowers/specs/feature-pipeline-finish-design.md
    lead new: 9. `architect`: `docs/superpowers/specs/plan-review-design.md`, its node settings and fixtures stated with `recall`, `rounds` skipped on `reuse`, `verdict` as an inline script returning Result, `keep` and the `recalled` fixture, pointed at this design for the plan record.
section s2 | lead | steps: 10 | size: lead: 14 finished, peak context median 59105, p90 86307, max 94415; 32 overruns
  s2.d1 | workflow-builder | steps: 10 | writes: .archon/workflows/feature-pipeline/plan-review/plan-review.yaml .archon/workflows/feature-pipeline/plan-review/commands/plan.md .archon/workflows/feature-pipeline/plan-review/commands/spec.md .archon/workflows/feature-pipeline/plan-review/fixtures/*.stubs.yaml | size: calibration load: 22k
    queue docs/superpowers/queues/feature-pipeline-finish.md s2.d1
    pack .archon/workflows/feature-pipeline/
    revise plan-review
    design docs/superpowers/specs/feature-pipeline-finish-design.md
    design docs/superpowers/specs/plan-review-design.md
    10. `workflow-builder`: `.archon/workflows/feature-pipeline/plan-review/plan-review.yaml`, `.archon/workflows/feature-pipeline/plan-review/commands/plan.md`, `.archon/workflows/feature-pipeline/plan-review/commands/spec.md`, `.archon/workflows/feature-pipeline/plan-review/fixtures/*.stubs.yaml`: `recall`, `rounds` skipped on `reuse`, `verdict` as an inline script returning Result, `keep`; the planner and specifier starting from a recalled record; the new `recalled` fixture.
section s3 | lead | steps: 11 | size: lead: 14 finished, peak context median 59105, p90 86307, max 94415; 32 overruns
  s3.d1 | workflow-builder | steps: 11 | writes: .archon/workflows/feature-pipeline/finish/finish.yaml .archon/workflows/feature-pipeline/finish/fixtures/*.stubs.yaml | size: calibration load: 12k
    queue docs/superpowers/queues/feature-pipeline-finish.md s3.d1
    pack .archon/workflows/feature-pipeline/
    revise finish
    design docs/superpowers/specs/feature-pipeline-finish-design.md
    11. `workflow-builder`: `.archon/workflows/feature-pipeline/finish/finish.yaml`, `.archon/workflows/feature-pipeline/finish/fixtures/*.stubs.yaml`: `tally`, `until_bash` reading `$tally.output.done`, `planning`'s `carry` reading `$LOOP_PREV.tally.output.build`, `ask` depending on `tally`; `verdict` stubs carrying `recalled`, `approval` and `key`.
section s4 | lead | steps: 12 | size: lead: 14 finished, peak context median 59105, p90 86307, max 94415; 32 overruns
  s4.d1 | workflow-builder | steps: 12 | writes: .archon/workflows/feature-pipeline/feature/feature.yaml .archon/workflows/feature-pipeline/feature/fixtures/*.stubs.yaml | size: calibration load: 11k
    queue docs/superpowers/queues/feature-pipeline-finish.md s4.d1
    pack .archon/workflows/feature-pipeline/
    revise feature
    design docs/superpowers/specs/feature-pipeline-finish-design.md
    12. `workflow-builder`: `.archon/workflows/feature-pipeline/feature/feature.yaml`, `.archon/workflows/feature-pipeline/feature/fixtures/*.stubs.yaml`: `gate` skipped on a recalled approval, the `approval` node, `rejected` depending on `approval`; the new `recalled-approved` fixture.
