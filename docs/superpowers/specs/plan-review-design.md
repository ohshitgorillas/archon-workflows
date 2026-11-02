Status: approved.

## Why

`plan-review` runs plan, prosecute, spec and arbitrate concurrently in one round: `spec` depends only on `plan`, so the specifier writes against a Plan nobody has passed. The owner's order is strictly sequential: plan, prosecute, then (only on a pass) spec against that approved Plan, then arbitrate. No research role exists; the planner and specifier read the tree themselves.

Copies of shared concerns in the tree:

- Prior-round state is read from five separate `$LOOP_PREV.<node>` references across two commands: `plan-review/commands/plan.md` reads `plan`, `prosecute`, `arbitrate`; `plan-review/commands/spec.md` reads `spec`, `prosecute`, `arbitrate`. Each assumes the producer ran last iteration, which a skipped node breaks.
- The review order is stated in five places: the `plan-review.yaml` description, the `feature/feature.yaml` description, the `refused` cancel text in `feature/feature.yaml` ("after two rounds"), the `plan-review` section of `docs/superpowers/specs/feature-pipeline-finish-design.md`, and its Homes rows for the review round and the test spec.
- No step resolves citations. The Plan carries none, and `plan-review/commands/prosecute.md` checks only that each path exists, so an agent would check every line number by hand.
- `feature/fixtures/round-2.stubs.yaml` is a copy of `feature/fixtures/approved.stubs.yaml` and proves no second round.
- The `plan` and `spec` stub values repeat across all eight `plan-review`, `finish` and `feature` fixtures. Archon's fixture format has no shared-stub key, so this copy stays.

## Modules

All paths below sit under `.archon/workflows/feature-pipeline/`.

### `plan-review/plan-review.yaml`, body of `rounds`

Each iteration is either a **plan round** (plan, cite, prosecute) or a **spec round** (spec, arbitrate). The previous iteration's `round` output picks which one runs. Spec and arbitrate read the Plan only from `round`, which hands on only a Plan the prosecutor passed. A spec round never re-cuts or re-prosecutes the Plan.

```yaml
- id: rounds
  loop_group:
    max_iterations: 8               # backstop: 4 Plan + 4 Spec attempts; round refuses first
    until_bash: |
      n=$round.output.next
      [ "$n" = done ] || [ "$n" = refused ]
    nodes:
      - id: plan                    # plan round entry; commands/plan.md
        command: plan
        when: "$LOOP_PREV.round.output.next != 'spec'"   # '' on iteration 1, so it runs
        context: fresh
        mutates_checkout: false
        allowed_tools: [Read, Grep, Glob, Agent]
        agents:
          detective:
            description: Answers the planner's questions from the checkout as a path:line Table
            prompt: |
              <the Detective role, below>
            tools: [Read, Grep, Glob]
        # reads $INPUTS.*, $LOOP_PREV.round.output.plan,
        # and $LOOP_PREV.round.output.findings with author: plan
        output_format: Plan         # each step gains optional cites (CitedPlan, below)

      - id: cite                    # the citation resolver; scripts/cite.py
        script: cite
        runtime: uv
        depends_on: [plan]          # skips with plan
        mutates_checkout: false
        timeout: 60000
        with:
          plan: $plan.output        # arrives as INPUTS_PLAN, canonical JSON
        output_format: Resolved

      - id: prosecute               # commands/prosecute.md
        depends_on: [cite]
        # reads $cite.output.plan, never $plan.output
        output_format: Verdict      # unchanged

      - id: spec                    # spec round entry; commands/spec.md
        command: spec
        when: "$LOOP_PREV.round.output.next == 'spec'"
        context: fresh
        mutates_checkout: false
        allowed_tools: [Read, Grep, Glob, Agent]
        sandbox: { enabled: true, network: { allowedDomains: [], allowManagedDomainsOnly: true } }
        agents:
          examiner:
            description: Measures behavior with a script on a throwaway copy of the checkout
            prompt: |
              <the Examiner role, below>
            tools: [Read, Grep, Glob, Bash, Write, Edit]
        # reads $INPUTS.*, $LOOP_PREV.round.output.plan (the approved Plan),
        # $LOOP_PREV.round.output.spec, and $LOOP_PREV.round.output.findings with author: spec
        output_format: Spec         # unchanged

      - id: arbitrate               # commands/arbitrate.md
        depends_on: [spec]          # skips with spec
        # reads $LOOP_PREV.round.output.plan and $spec.output
        output_format: Verdict      # unchanged

      - id: round                   # bash + jq; the one home of state carried between iterations
        depends_on: [prosecute, arbitrate]
        trigger_rule: all_done
        mutates_checkout: false
        output_format:
          type: object
          properties:
            next: { type: string, enum: [plan, spec, done, refused] }
            cuts: { type: integer }       # Plan attempts in this call of plan-review, cap 4
            specs: { type: integer }      # Spec attempts in this call of plan-review, cap 4
            plan: { type: object }        # the latest Plan
            spec: { type: [object, 'null'] }
            findings: { type: array, items: { type: object } }
          required: [next, cuts, specs, plan, spec, findings]
```

`round` assigns `$cite.output`, `$prosecute.output`, `$spec.output`, `$arbitrate.output` and `$LOOP_PREV.round.output` to shell variables, then quotes each one. An empty value becomes `null` before `jq --argjson`. A skipped producer and iteration 1 both read as empty. Then:

- **Plan round** (prosecute ran). `plan` is `$cite.output.plan`, this round's Plan with its cites resolved, and `cuts` is the previous count plus 1. `specs` carries the previous count, or 0. `spec` carries the previous `spec`, or null. `findings` is the prosecutor's findings, plus one `author: plan` finding per `$cite.output.unresolved` entry (`target` the step id, `cause` the entry's path, line and reason, `fix` "cite the line whose text is the quote", `design_it_in` false), plus the previous round's `author: spec` findings. `next` is `spec` on a pass with no unresolved cite, and `plan` otherwise.
- **Spec round** (arbitrate ran). `plan` and `cuts` carry over unchanged, and `specs` is the previous count plus 1. `spec` is this round's Spec and `findings` is the arbiter's findings. `next` is `done` on a pass. Any `author: plan` finding sets `next` to `plan`, which reopens the Plan; the re-cut counts against the Plan cap. Otherwise `next` is `spec`, and the next round re-does spec and arbitrate against the same Plan.
- **Caps.** The Plan cap is 4 attempts and the Spec cap is 4 attempts, each counted over the whole call; a reopen resets neither count. After `next` is set, `round` turns it into `refused` when it is `plan` and `cuts` is 4, or when it is `spec` and `specs` is 4. `round` is the only place that refuses on a cap; `max_iterations: 8` is never the reason a call stops.

A failed body node fails `round` on its reference and fails the group, the same as today. Nothing retries.

### `plan-review/plan-review.yaml`, `verdict`

The node stays bash over `$rounds.output`, which is the last `round`. `verdict` is `pass` when `next` is `done` and `refused` otherwise. `plan` passes through. `spec` is `.spec // {}`, so a call refused at the Plan still meets the schema. `findings` is `.findings`. `decisions` is `.plan.decisions + (.spec.decisions // [])`, unique by id, minus every id a finding targets. The output schema does not change. The description states the sequential order, the Detective, the Examiner and the caps of 4 Plan attempts and 4 Spec attempts.

### `plan-review/scripts/cite.py`, the citation resolver

A `script:` node (Python, run by uv) between `plan` and `prosecute`. It is deterministic: no agent resolves, checks or corrects a line number. Archon has no citation check of its own, so this node fills that gap. It reads the Plan from `INPUTS_PLAN` and files from the run's checkout (its working directory), writes nothing, uses no network and imports only the standard library.

For each cite on each Plan step, comparing line text with leading and trailing whitespace stripped:

- The cited line's text contains the quote: the cite stands.
- Otherwise every line in the file containing the quote is a candidate. The one nearest the cited line wins, and the cite's `line` is rewritten to it. This fixes an off-by-one or drifted line with no round spent.
- No candidate, two candidates at the same distance, a missing or non-file path, a path outside the checkout, or an empty quote: the cite stands as written and goes on `unresolved` with the reason (`no such file`, `outside checkout`, `quote not found`, `quote ambiguous: lines <a>, <b>`, `empty quote`).

It prints `Resolved` on stdout and exits 0 whenever it could read `$plan.output`. Any other failure exits non-zero and fails the node; nothing retries.

```yaml
# Cite (on a Plan step's cites and a Detective Table row's cites)
type: object
properties:
  path: { type: string }            # repository-relative
  line: { type: integer, minimum: 1 }
  quote: { type: string, minLength: 1 }   # the cited line's text, verbatim
required: [path, line, quote]

# CitedPlan: the Plan schema, with each step gaining
#   cites: { type: array, items: Cite }   # optional; absent means none

# Resolved (cite's output_format)
type: object
properties:
  plan: { type: object }            # the CitedPlan, each cite's line resolved
  unresolved:
    type: array
    items:
      type: object
      properties:
        step: { type: string }
        path: { type: string }
        line: { type: integer }
        quote: { type: string }
        reason: { type: string }
      required: [step, path, line, quote, reason]
required: [plan, unresolved]
```

```python
# plan-review/scripts/cite.py
def resolve(cite: dict, root: pathlib.Path) -> tuple[dict, str | None]: ...  # (cite with line resolved, reason or None)
def main() -> int: ...  # reads INPUTS_PLAN, prints Resolved
```

### The Detective and the Examiner

There are two agents with two jobs. Neither one does the other's job.

**Detective** (reader). This is the `detective` inline agent on `plan`; its role is that agent's `prompt`. It answers the planner's questions all at once, as a file:line table, and returns a `Table`. It sees the checkout and has only Read, Grep and Glob. It writes nothing and runs nothing. Every cite is a `Cite`: path, line and the cited line's text as `quote`, verbatim. It never re-checks a line number; `cite` resolves every cite the Plan carries. A question it cannot answer from the tree is marked `unresolved`, with the reason, never guessed.

```yaml
# Table (the Detective's return)
type: object
properties:
  rows:
    type: array
    items:
      type: object
      properties:
        question: { type: string }
        answer: { type: string }
        cites: { type: array, minItems: 1, items: Cite }   # Cite, above
        status: { type: string, enum: [answered, unresolved] }
      required: [question, answer, cites, status]
required: [rows]
```

**Examiner** (scratch). This is the `examiner` inline agent on `spec`; its role is that agent's `prompt`. It measures the behavior a Spec line pins (the line's assertion), whenever the measurement needs a script or a rendered state. It gets one measurement and a scratch directory from the specifier. It copies the checkout's tracked and unignored untracked files (`git ls-files -co --exclude-standard`) into a fresh directory under the scratch directory and works only in that copy, which Archon discards when the run ends. It never writes to the checkout. It runs every command under `timeout` and `nice`, with at most half of `nproc` jobs, and has no network. It returns `question`, the measured `value`, the `script` it ran, that script's `output`, and `status` (`measured` or `unresolved`, with the reason).

### Commands

- `plan-review/commands/plan.md`. The prior Plan and findings come from `$LOOP_PREV.round.output.plan` and `.findings`, not from `$LOOP_PREV.plan/prosecute/arbitrate`. The planner works out its questions from the design, scope, survey, carry and the prior Plan and findings, and calls `detective` through the `Agent` tool before it plans. It calls the Detective again whenever more needs answering, and builds the Plan from the tables. Each step's `cites` carries, unchanged, every Detective cite the step relies on; the planner never edits a line number. It fixes every `author: plan` finding. Its rules are unchanged.
- `plan-review/commands/prosecute.md`. The Plan is `$cite.output.plan`, whose cites `cite` has resolved. The prosecutor never checks or corrects a cite's line; an unresolved cite reaches the planner from `round`, not from the prosecutor. Everything else is unchanged.
- `plan-review/commands/spec.md`. The Plan is `$LOOP_PREV.round.output.plan`, which the prosecutor approved. The prior Spec is `.spec` and the findings are `.findings`; it fixes the `author: spec` ones. The specifier decides what needs measuring and calls `examiner` through the `Agent` tool with the scratch directory `$ARTIFACTS_DIR/.archon/scratch/spec/`. It calls the Examiner again whenever more needs spiking, and builds the Spec from the measurements. It never changes the Plan. Its rules are unchanged.
- `plan-review/commands/arbitrate.md`. The Plan is `$LOOP_PREV.round.output.plan`. Everything else is unchanged.

### Callers

- `finish/finish.yaml`. No node changes. `build` still gates on `verdict == 'pass'` and binds `plan` and `spec`. `carry` still passes `$LOOP_PREV.planning.output`.
- `feature/feature.yaml`. The description states the sequential order and the caps of 4 Plan attempts and 4 Spec attempts. The `refused` cancel says "at the Plan or Spec cap" instead of "after two rounds" and still prints `$planning.output.findings`.

### Fixtures

`archon workflow test` (Archon v0.13.2) runs one iteration of a `loop_group` and never runs its `until_bash`, even under `exec-code: true`, and a stub returns the same output on every iteration. In every fixture `rounds` therefore runs only iteration 1, a plan round: `plan`, `cite`, `prosecute` and `round` run, `spec` and `arbitrate` are skipped, and `verdict` reads that one `round` output, so its `verdict` field is `refused` whenever it runs. Fixtures cover only this single pass. Every route that needs a second iteration (a spec round, `next: done`, a reopen, either cap) is proved by the live-run checks below, and no fixture exists for it.

Each fixture sets `exec-code: true`, runs `cite` and `round` unstubbed, and lists its route in `fixture.reached`. A fixture proves "did not run" by leaving that node unstubbed: strict coverage fails a reached node that has no stub. `fixture.resolved-text-contains` takes one fragment per node, so a fixture with several checks puts each on a different node. `verdict`'s resolved text carries the `round` output as compact JSON in the key order `next`, `cuts`, `specs`, `plan`, `spec`, `findings`, so `"next":…,"cuts":…,"specs":…` is one contiguous fragment.

A caller's passing fixture stubs plan-review's `verdict` node with a `pass` result (`verdict: pass`, `plan`, `spec`, `findings: []`, `decisions: []`), keyed as `archon workflow run <caller> --dry-run --stubs-init` spells it (`planning__verdict` in `feature`). A caller's refused fixture leaves `verdict` unstubbed, so the real `round` and `verdict` produce the refusal. No caller fixture stubs `spec` or `arbitrate`.

| Fixture | Stubs | Route (`fixture.reached`) | Checks |
|---|---|---|---|
| `plan-review/fixtures/plan-passed.stubs.yaml` | plan; prosecute `pass` | rounds, plan, cite, prosecute, round, verdict | `verdict`: `"next":"spec","cuts":1,"specs":0`. A passed Plan with every cite resolved hands on to a spec round. |
| `plan-review/fixtures/plan-failed.stubs.yaml` | plan; prosecute `fail` (`author: plan`) | rounds, plan, cite, prosecute, round, verdict | `verdict`: `"next":"plan","cuts":1,"specs":0`. A failed Plan goes back to the planner. |
| `plan-review/fixtures/cites.stubs.yaml`, with `plan-review/fixtures/cites.txt` | plan with one step citing `cites.txt` three times: line 1 `alpha line one` (exact), line 4 `gamma line three` (the quote is on line 3), line 2 `omega line none` (in no line); prosecute `pass` | rounds, plan, cite, prosecute, round, verdict | `prosecute`: `"line":3,"quote":"gamma line three"`, so the prosecutor gets the Plan with the off line corrected. `round`: `"line":2,"quote":"omega line none","reason":"quote not found"`, so the missing quote is refused and its line left as written. `verdict`: `"next":"plan","cuts":1,"specs":0`, so an unresolved cite sends the Plan back despite the pass. `cites.txt` is a fixed, committed text file only this fixture reads. |
| `finish/fixtures/approved.stubs.yaml` | baseline, sync, plan, prosecute `pass`, the `verdict` pass stub, and today's build-loop, gate, bail and land stubs | baseline, cycle, sync, gate, bail, land | `finish` builds and lands on a passing plan-review result. |
| `finish/fixtures/refused.stubs.yaml` | baseline, sync, plan, prosecute `fail` (`author: plan`), and today's stubs after `planning`; `verdict` unstubbed | baseline, cycle, sync, gate, bail, ask | A refused verdict from the real `round` and `verdict` reaches `finish` and meets the schema. |
| `feature/fixtures/approved.stubs.yaml` | read-request, plan, prosecute `pass`, the `planning__verdict` pass stub, and today's gate stub | read-request, planning__verdict, gate | `feature` reaches its gate on a passing plan-review result. Expect `completed`. |
| `feature/fixtures/rejected.stubs.yaml` | as `approved`, with today's rejecting gate stub | read-request, planning__verdict, gate, rejected | A rejection at the gate cancels. Expect `cancelled`. |
| `feature/fixtures/refused.stubs.yaml` | read-request, plan, prosecute `fail` (`author: plan`); `planning__verdict` unstubbed | read-request, planning__verdict | The `refused` cancel reads findings from the real verdict. Expect `cancelled`. |

`plan-review/fixtures/passed.stubs.yaml`, `plan-review/fixtures/refused.stubs.yaml` and `feature/fixtures/round-2.stubs.yaml` are deleted.

### Live-run checks

These checks replace a fixture for every route that needs a second `rounds` iteration. Each is read from a live run's trace: which body nodes ran in each iteration, each iteration's `round` output, and `verdict`. L1, L2, L3 and L8 are read on the first live run of the rebuilt `plan-review` (through `feature` or `finish`). L4 to L7 are each read on the first live run that takes that route; a route no live run has taken stays unproved.

| Check | Route | The run must show |
|---|---|---|
| L1 Loop end | every call | `rounds` stops after the first iteration whose `round.next` is `done` or `refused`, through `until_bash`; it never runs to `max_iterations: 8`. |
| L2 Plan round | every iteration whose previous `round.next` is not `spec` | `plan`, `cite` and `prosecute` ran; `spec` and `arbitrate` were skipped; `cuts` is the previous count plus 1 and `specs` is unchanged. |
| L3 Spec round | every iteration whose previous `round.next` is `spec` | `spec` and `arbitrate` ran; `plan`, `cite` and `prosecute` were skipped; `round.plan` and `cuts` equal the previous iteration's and `specs` is the previous count plus 1. |
| L4 Pass | the arbiter passes a Spec | that iteration's `round.next` is `done`, the loop ends there, and `verdict` is `pass` with that `round`'s `plan` and `spec`. |
| L5 Spec retry and Spec cap | the arbiter fails a Spec with only `author: spec` findings | the next iteration is a spec round against the same Plan; the round where `specs` reaches 4 with `next` `spec` sets `next` to `refused`, and `verdict` is `refused`. |
| L6 Reopen | the arbiter returns an `author: plan` finding | the next iteration is a plan round whose planner reads that finding; `cuts` is the previous count plus 1 and `specs` is not reset. |
| L7 Plan cap | the prosecutor or an unresolved cite fails the Plan four times | the round where `cuts` reaches 4 with `next` `plan` sets `next` to `refused`, no spec round follows, and `verdict` is `refused`. |
| L8 Sub-agents | every call | `plan` calls `detective` and `spec` calls `examiner` through the `Agent` tool; the Examiner writes only under `$ARTIFACTS_DIR/.archon/scratch/spec/` and the run's checkout is unchanged. |

## Homes

| Concern | Home | Forbidden elsewhere |
|---|---|---|
| Review order: plan, prosecute, then spec and arbitrate against the approved Plan | `plan-review`'s `rounds` body; `round.next` picks each iteration | A spec or arbitrate depending on `plan` or `prosecute`; a spec written beside an unpassed Plan; a separate route, approval or counter node |
| State carried between iterations (latest Plan, latest Spec, findings, Plan and Spec attempt counts, next phase) | `round` | `$LOOP_PREV.plan`, `$LOOP_PREV.prosecute`, `$LOOP_PREV.spec` or `$LOOP_PREV.arbitrate` in any command; a `script:` node or artifact file carrying it |
| Detective role | the `detective` inline agent on `plan` | A Detective on any other node; a Detective that writes or runs anything; a second copy of the Detective prompt; an on-disk `.claude/agents/` detective; Detective rules restated in `plan.md` |
| Examiner role | the `examiner` inline agent on `spec` | An Examiner on any other node; measuring in the checkout; a second copy of the Examiner prompt; an on-disk `.claude/agents/` examiner; Examiner rules restated in `spec.md` |
| Research for the Plan | `plan` calling `detective` through the `Agent` tool, as often as it needs | The planner measuring or spiking itself; a separate Detective node for the Plan |
| Research for the Spec | `spec` calling `examiner` through the `Agent` tool, as often as it needs | A separate Examiner node for the Spec |
| Citation resolution (a cite's line checked against its quote, and corrected) | `cite`, `plan-review/scripts/cite.py` | Any agent checking, correcting or arguing a line number; the prosecutor ruling on a cite's line; a second resolver or a resolver written into a command; a cite with no `quote` |
| Throwaway copies | `$ARTIFACTS_DIR/.archon/scratch/`, which Archon removes when the run ends | Any write to the run's checkout during `plan-review` |
| Caps: 4 Plan attempts and 4 Spec attempts per call | `round`, through `cuts`, `specs` and `next: refused`; `rounds.max_iterations: 8` is only a backstop the caps always reach first | A count of attempts in a command or in a caller; a cap enforced by `max_iterations`; a counter node beside `round` |
| Did-not-run proof in fixtures | the node left unstubbed under strict coverage | A stub for a node the case says never runs |
| Proof of every route that needs a second `rounds` iteration (spec round, `next: done`, reopen, both caps) | the live-run checks L1 to L8 | A fixture for such a route; a stub, node or loop setting that fakes a later iteration |
| plan-review's result in a caller's passing fixture | a `pass` stub on plan-review's `verdict` node | A caller fixture stubbing `spec` or `arbitrate`; a caller fixture faking a pass through the `rounds` body |

## Order

No step touches the live run `55246a548b9023ebcebb00db7cc448a7`. Archon snapshots include and command bodies when a run loads, so file edits do not reach it.

1. `workflow-builder`: `plan-review/plan-review.yaml`, `plan-review/scripts/cite.py` (new), `plan-review/commands/plan.md`, `plan-review/commands/prosecute.md`, `plan-review/commands/spec.md`, `plan-review/commands/arbitrate.md`, and `plan-review/fixtures/` (`plan-passed.stubs.yaml` replacing `passed.stubs.yaml`, `plan-failed.stubs.yaml` replacing `refused.stubs.yaml`, `cites.stubs.yaml` and `cites.txt` new). `archon validate workflows` must pass with no warning on the `allowed_tools` of `plan` or `spec`, and `archon workflow test plan-review` must pass. The docs under `docs/reference/archon/` do not state the following, and this step's fixtures prove each one except where a live-run check is named:
   - A bash reference to a producer skipped in the current iteration injects `''` (`workflow-language.md`, "Reading across a skipped branch", says only that bindings never resolve to `''`). `round` reads the skipped `spec` and `arbitrate` in every fixture. The `until_bash` read of `$round.output.next` is live-run check L1.
   - A stubbed command node's resolved text is its command body with each reference substituted, an object as compact JSON. The `cites` fixture's `prosecute` check proves it.
   - `allowed_tools` names the sub-agent tool `Agent`; the validator warns that `Task` is silently ignored, while `workflow-language.md`, "Inline sub-agents", still names `Task`. This step's `archon validate workflows` run proves it.
   - Strict coverage treats a node as reached only when the simulation reaches it. `cli.md`, "workflow test", has no did-not-run key and does not say whether reach is static or simulated.
   - A `script:` node under `exec-code: true` has the root of its scratch worktree as its working directory. `cli.md`, "workflow test", says only that such nodes run in a scratch worktree of `HEAD`. So `cites.txt` reaches the `cites` fixture only once it is committed, and the step commits it before that fixture's run.
   - A body node may read `$cite.output` when `cite` is an ancestor of its `depends_on` but not listed there.
   - An inline agent's `tools` may go beyond the node's `allowed_tools`, and the node's `sandbox` binds its sub-agents. Neither "Inline sub-agents" nor `sandbox` in `workflow-language.md` says so. A fixture cannot prove this; live-run check L8 shows it.
   - The reference does not name the Archon version it describes.

   If any of these fails, the builder stops and reports it with the failing output. It adds no workaround node.
2. `workflow-builder`: `finish/fixtures/approved.stubs.yaml` and `finish/fixtures/refused.stubs.yaml`. `archon workflow test finish` must pass. Runs after step 1. The docs do not state that under `exec-code: true` a stubbed `bash:` node takes its stub and does not run; the `approved` fixture's `verdict` stub proves it, and if it fails the builder stops and reports it with the failing output.
3. `workflow-builder`: `feature/feature.yaml`, `feature/fixtures/approved.stubs.yaml`, `feature/fixtures/rejected.stubs.yaml` and `feature/fixtures/refused.stubs.yaml`, and the deletion of `feature/fixtures/round-2.stubs.yaml`. `archon workflow test feature` must pass. Runs after step 1.
4. `architect` (a `rulings` pass): `docs/superpowers/specs/feature-pipeline-finish-design.md`. Its `plan-review` section, its round-2 and round-cap bullets, its `feature` paragraph (the round-2 route), and its Homes rows for the capped review round, the test spec and the Spec cross-check come to state this design's order, Detective, Examiner, citation resolver and caps of 4 Plan attempts and 4 Spec attempts. Runs after this design is approved.
