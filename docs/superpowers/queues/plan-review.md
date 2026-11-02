design docs/superpowers/specs/plan-review-design.md | order docs/superpowers/specs/plan-review-design.md | main c051517
section s1 | lead | steps: 1 | size: lead: 14 finished, peak context median 59105, p90 86307, max 94415; 32 overruns
  s1.d1 | builder | steps: 1 | writes: .archon/workflows/feature-pipeline/plan-review/scripts/cite.py, .archon/workflows/feature-pipeline/plan-review/fixtures/cites.txt | size: builder: 31 finished, peak context median 40070, p90 53365, max 70766; 0 overruns load: 5k
    queue docs/superpowers/queues/plan-review.md s1.d1
    design: docs/superpowers/specs/plan-review-design.md
    step: 1, its citation resolver `plan-review/scripts/cite.py` and the fixture text file `plan-review/fixtures/cites.txt`; s1.d2 builds the rest of step 1 on them
    paths: .archon/workflows/feature-pipeline/plan-review/scripts/cite.py, .archon/workflows/feature-pipeline/plan-review/fixtures/cites.txt
    behavior: A `script:` node (Python, run by uv) between `plan` and `prosecute`. It is deterministic: no agent resolves, checks or corrects a line number. Archon has no citation check of its own, so this node fills that gap. It reads the Plan from `INPUTS_PLAN` and files from the run's checkout (its working directory), writes nothing, uses no network and imports only the standard library.
    behavior: - The cited line's text contains the quote: the cite stands.
    behavior: - Otherwise every line in the file containing the quote is a candidate. The one nearest the cited line wins, and the cite's `line` is rewritten to it. This fixes an off-by-one or drifted line with no round spent.
    behavior: - No candidate, two candidates at the same distance, a missing or non-file path, a path outside the checkout, or an empty quote: the cite stands as written and goes on `unresolved` with the reason (`no such file`, `outside checkout`, `quote not found`, `quote ambiguous: lines <a>, <b>`, `empty quote`).
    behavior: It prints `Resolved` on stdout and exits 0 whenever it could read `$plan.output`. Any other failure exits non-zero and fails the node; nothing retries.
    behavior: def resolve(cite: dict, root: pathlib.Path) -> tuple[dict, str | None]: ...  # (cite with line resolved, reason or None)
    behavior: def main() -> int: ...  # reads INPUTS_PLAN, prints Resolved
    behavior: | `plan-review/fixtures/cites.stubs.yaml`, with `plan-review/fixtures/cites.txt` | plan with three cites into `cites.txt`: one exact, one a line off, one whose quote is in no line; prosecute `pass`; no spec, no arbitrate | `cite` alone fixes the line that is off and refuses the missing quote: verdict text contains the corrected line, `quote not found` and `"cuts":4`. `cites.txt` is a fixed text file only this fixture reads. |
    check: INPUTS_PLAN='{"steps":[]}' uv run python .archon/workflows/feature-pipeline/plan-review/scripts/cite.py
  s1.d2 | workflow-builder | steps: 1 | writes: .archon/workflows/feature-pipeline/plan-review/plan-review.yaml, .archon/workflows/feature-pipeline/plan-review/commands/plan.md, .archon/workflows/feature-pipeline/plan-review/commands/prosecute.md, .archon/workflows/feature-pipeline/plan-review/commands/spec.md, .archon/workflows/feature-pipeline/plan-review/commands/arbitrate.md, .archon/workflows/feature-pipeline/plan-review/fixtures/passed.stubs.yaml, .archon/workflows/feature-pipeline/plan-review/fixtures/refused.stubs.yaml, .archon/workflows/feature-pipeline/plan-review/fixtures/refused-at-plan.stubs.yaml, .archon/workflows/feature-pipeline/plan-review/fixtures/refused-at-spec.stubs.yaml, .archon/workflows/feature-pipeline/plan-review/fixtures/reopened.stubs.yaml, .archon/workflows/feature-pipeline/plan-review/fixtures/cites.stubs.yaml | size: calibration load: 9k
    queue docs/superpowers/queues/plan-review.md s1.d2
    pack: .archon/workflows/feature-pipeline
    workflows: plan-review
    design: docs/superpowers/specs/plan-review-design.md
    step: 1, all of it but `plan-review/scripts/cite.py` and `plan-review/fixtures/cites.txt`, which s1.d1 built and the lead committed before this dispatch
    behavior: 1. `workflow-builder`: `plan-review/plan-review.yaml`, `plan-review/scripts/cite.py` (new), `plan-review/commands/plan.md`, `plan-review/commands/prosecute.md`, `plan-review/commands/spec.md`, `plan-review/commands/arbitrate.md`, and `plan-review/fixtures/` (`passed.stubs.yaml` updated; `refused.stubs.yaml` replaced by `refused-at-plan.stubs.yaml`; `refused-at-spec.stubs.yaml`, `reopened.stubs.yaml`, `cites.stubs.yaml` and `cites.txt` new). `archon validate workflows` and `archon workflow test plan-review` must pass. The docs under `docs/reference/archon/` do not state the following, and this step's fixtures prove each one:
    behavior: - A bash or `until_bash` reference to a producer skipped in the current iteration injects `''` (`workflow-language.md`, "Reading across a skipped branch", says only that bindings never resolve to `''`).
    behavior: - Strict coverage treats a node as reached only when the simulation reaches it. `cli.md`, "workflow test", has no did-not-run key and does not say whether reach is static or simulated.
    behavior: - A `script:` node under `exec-code: true` has the root of its scratch worktree as its working directory. `cli.md`, "workflow test", says only that such nodes run in a scratch worktree of `HEAD`. So `cites.txt` reaches the `cites` fixture only once it is committed, and the step commits it before that fixture's run.
    behavior: - A body node may read `$cite.output` when `cite` is an ancestor of its `depends_on` but not listed there.
    behavior: - An inline agent's `tools` may go beyond the node's `allowed_tools`, and the node's `sandbox` binds its sub-agents. Neither "Inline sub-agents" nor `sandbox` in `workflow-language.md` says so. A fixture cannot prove this; the first live run shows it.
    behavior: - The reference does not name the Archon version it describes.
    behavior: If any of these fails, the builder stops and reports it with the failing output. It adds no workaround node.
    check: archon validate workflows plan-review
    check: archon workflow test plan-review
section s2 | lead | steps: 2, 3 | size: lead: 14 finished, peak context median 59105, p90 86307, max 94415; 32 overruns
  s2.d1 | workflow-builder | steps: 2 | writes: .archon/workflows/feature-pipeline/finish/fixtures/refused.stubs.yaml | size: calibration load: 6k
    queue docs/superpowers/queues/plan-review.md s2.d1
    pack: .archon/workflows/feature-pipeline
    workflows: finish
    design: docs/superpowers/specs/plan-review-design.md
    step: 2
    behavior: 2. `workflow-builder`: `finish/fixtures/refused.stubs.yaml`. `archon workflow test finish` must pass. Runs after step 1.
    behavior: | `finish/fixtures/refused.stubs.yaml` | prosecute `fail`; spec and arbitrate removed | A Plan refusal reaches `finish` as a valid refused verdict. |
    check: archon workflow test finish
  s2.d2 | workflow-builder | steps: 3 | writes: .archon/workflows/feature-pipeline/feature/feature.yaml, .archon/workflows/feature-pipeline/feature/fixtures/refused.stubs.yaml, .archon/workflows/feature-pipeline/feature/fixtures/round-2.stubs.yaml | size: calibration load: 6k
    queue docs/superpowers/queues/plan-review.md s2.d2
    pack: .archon/workflows/feature-pipeline
    workflows: feature
    design: docs/superpowers/specs/plan-review-design.md
    step: 3
    behavior: 3. `workflow-builder`: `feature/feature.yaml` and `feature/fixtures/refused.stubs.yaml`, and the deletion of `feature/fixtures/round-2.stubs.yaml`. `archon workflow test feature` must pass. Runs after step 1.
    behavior: - `feature/feature.yaml`. The description states the sequential order and the caps of 4 Plan attempts and 4 Spec attempts. The `refused` cancel says "at the Plan or Spec cap" instead of "after two rounds" and still prints `$planning.output.findings`.
    behavior: | `feature/fixtures/refused.stubs.yaml` | prosecute `fail`; spec and arbitrate removed | The `refused` cancel reads findings from a call refused at the Plan. |
    behavior: `feature/fixtures/round-2.stubs.yaml` is deleted.
    check: archon workflow test feature
section s3 | lead | steps: 4 | size: lead: 14 finished, peak context median 59105, p90 86307, max 94415; 32 overruns
  s3.d1 | architect | steps: 4 | writes: docs/superpowers/specs/feature-pipeline-finish-design.md | size: architect: 1 finished, peak context median 62409, p90 62409, max 62409; 0 overruns load: 11k
    queue docs/superpowers/queues/plan-review.md s3.d1
    rulings docs/superpowers/specs/feature-pipeline-finish-design.md
    design docs/superpowers/specs/plan-review-design.md, approved, whose Order step 4 this pass carries out
    lead new: 4. `architect` (a `rulings` pass): `docs/superpowers/specs/feature-pipeline-finish-design.md`. Its `plan-review` section, its round-2 and round-cap bullets, its `feature` paragraph (the round-2 route), and its Homes rows for the capped review round, the test spec and the Spec cross-check come to state this design's order, Detective, Examiner, citation resolver and caps of 4 Plan attempts and 4 Spec attempts. Runs after this design is approved.
