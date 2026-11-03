Status: approved.

## Why

`plan-review` runs plan, prosecute, spec and arbitrate concurrently in one round: `spec` depends only on `plan`, so the specifier writes against a Plan nobody has passed. The owner's order is strictly sequential: plan, prosecute, then (only on a pass) spec against that approved Plan, then arbitrate. No research role exists; the planner and specifier read the tree themselves.

Copies of shared concerns in the tree:

- Prior-round state is read from five separate `$LOOP_PREV.<node>` references across two commands: `plan-review/commands/plan.md` reads `plan`, `prosecute`, `arbitrate`; `plan-review/commands/spec.md` reads `spec`, `prosecute`, `arbitrate`. Each assumes the producer ran last iteration, which a skipped node breaks.
- The review order is stated in five places: the `plan-review.yaml` description, the `feature/feature.yaml` description, the `refused` cancel text in `feature/feature.yaml` ("after two rounds"), the `plan-review` section of `docs/superpowers/specs/feature-pipeline-finish-design.md`, and its Homes rows for the review round and the test spec.
- No step resolves citations. The Plan carries none, and `plan-review/commands/prosecute.md` checks only that each path exists, so an agent would check every line number by hand.
- `feature/fixtures/round-2.stubs.yaml` is a copy of `feature/fixtures/approved.stubs.yaml` and proves no second round.
- The `plan` and `spec` stub values repeat across all eight `plan-review`, `finish` and `feature` fixtures. Archon's fixture format has no shared-stub key, so this copy stays.
- No node in `plan-review/plan-review.yaml` writes anything that outlives its run, so a failed, resumed or later run plans from nothing. `verdict` is a bash node over `$rounds.output` and cannot run when `rounds` is skipped. `docs/superpowers/specs/feature-pipeline-finish-design.md` holds the plan record that `recall` reads and `keep` writes: its path, key, `Recall`, `Record`, `Approval` and `Result` schemas, and the reuse rule.

## Review rules

A round fails only when the Plan or Spec would build the wrong thing, break something, skip something the design asks for, add work nobody asked for, run steps in an order that cannot work, or use a check that cannot pass or would not prove the step did its job. Everything else is minor and never costs a round; the build-loop writer corrects it.

- Steps may name test files and test support. Repairing or porting tests needs no code step and no invented production change.
- A unit whose whole work is a green full gate then the merge is listed in `landed` and gets no step. A step check may run the full gate.
- `blocked_by`, worded the same in all four commands: a decision id waits on the owner's answer; a step id waits until that step's check passes; no step waits on itself, directly or through other steps.
- A bulk port is one Spec line naming a whole test file or directory, setup and assertion null.
- Cites are optional; an unresolved cite is a minor finding.
- A design/rule conflict is a blocking decision in the touched step's `blocked_by`, so the call stops and asks the owner at once. Caps are 3 Plan and 3 Spec attempts; a capped call returns `refused` and `finish` asks the owner.
- Gone as gates: test-path bans and their repair/port exception, no-full-gate checks, cut-by-count, declare-once, same-claim, the machinery rule, `before` equal to the line's step, cite-no-test-id, and "one sensible answer" as blocking.

## Modules

All paths below sit under `.archon/workflows/feature-pipeline/`.

### `plan-review/plan-review.yaml`, top-level nodes

The block runs `recall`, then `rounds` only when `recall` finds no record to reuse, then `verdict`, then `keep`. A reused record runs no agent.

```yaml
- id: recall                        # bash + jq; the only reader of the plan record
  mutates_checkout: false
  # computes the key from $INPUTS.design, $INPUTS.scope and `git hash-object`, never HEAD,
  # reads $STATE_DIR/feature-pipeline/plans/<key>.json when present, lists moved paths against
  # the record's head, and sets next,
  # all as feature-pipeline-finish-design.md's plan record states
  output_format: Recall             # schema in feature-pipeline-finish-design.md

- id: rounds                        # body below
  depends_on: [recall]
  when: "$recall.output.next == 'rounds'"   # skipped on reuse

- id: verdict                       # inline script (Python, standard library only); the block's returns
  script: |
    <the verdict script, below>
  runtime: uv                       # no deps
  depends_on: [recall, rounds]
  trigger_rule: all_done            # runs when rounds is skipped
  mutates_checkout: false
  timeout: 60000
  with:
    recall: $recall.output                              # arrives as INPUTS_RECALL
    round: { from: $rounds.output, if_skipped: null }   # the last round; INPUTS_ROUND
  output_format: Result             # schema in feature-pipeline-finish-design.md

- id: keep                          # bash + jq; plan-review's only writer of the plan record
  depends_on: [verdict]
  mutates_checkout: false
  # writes the Record for $recall.output.key from $recall.output, $WORKFLOW_ID,
  # $INPUTS.carry and $verdict.output, as feature-pipeline-finish-design.md states:
  # jq to <key>.json.tmp, then mv over <key>.json
```

`recall` and `keep` follow the plan record rules of `docs/superpowers/specs/feature-pipeline-finish-design.md` and restate none of them. `keep` runs on every call that reaches `verdict`, reuse included. A failed `rounds` fails `verdict`'s binding and the block, and `keep` does not run.

### `plan-review/plan-review.yaml`, body of `rounds`

Each iteration is either a **plan round** (plan, cite, prosecute) or a **spec round** (spec, arbitrate). The previous iteration's `round` output picks which one runs. Spec and arbitrate read the Plan only from `round`, which hands on only a Plan the prosecutor passed. A spec round never re-cuts or re-prosecutes the Plan.

```yaml
- id: rounds
  loop_group:
    max_iterations: 6               # backstop: 3 Plan + 3 Spec attempts; round refuses first
    until_bash: |
      n=$round.output.next
      [ "$n" = done ] || [ "$n" = refused ]
    nodes:
      - id: plan                    # plan round entry; commands/plan.md
        command: plan
        when: "$LOOP_PREV.round.output.next != 'spec'"   # '' on iteration 1, so it runs
        context: fresh
        mutates_checkout: false
        allowed_tools: [Read, Grep, Glob, Agent]   # Archon caps the detective's tools at these; the planner itself reads the checkout only through the Detective, by plan.md
        agents:
          detective:
            description: Answers the planner's questions from the checkout as a path:line Table
            prompt: |
              <the Detective role, below>
            tools: [Read, Grep, Glob]
        # reads $INPUTS.*, $LOOP_PREV.round.output.plan,
        # and $LOOP_PREV.round.output.findings with author: plan;
        # on iteration 1, $recall.output.record when not null; every iteration, its carry
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
        output_format: Verdict      # findings carry basis and severity (feature-pipeline-finish-design.md)

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
        # $LOOP_PREV.round.output.spec, and $LOOP_PREV.round.output.findings with author: spec;
        # with no prior Spec in this call, the spec of $recall.output.record when not null;
        # every iteration, the record's carry
        output_format: Spec         # unchanged

      - id: arbitrate               # commands/arbitrate.md
        depends_on: [spec]          # skips with spec
        # reads $LOOP_PREV.round.output.plan and $spec.output
        output_format: Verdict      # findings carry basis and severity (feature-pipeline-finish-design.md)

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

- **Plan round** (prosecute ran). `plan` is `$cite.output.plan`, this round's Plan with its cites resolved, and `cuts` is the previous count plus 1. `specs` carries the previous count, or 0. `spec` carries the previous `spec`, or null. `findings` is the prosecutor's findings, plus one `author: plan` finding per `$cite.output.unresolved` entry (`target` the step id, `cause` the entry's path, line and reason, `basis` the cite's quote, `severity` minor, `design_it_in` false), plus the previous round's `author: spec` findings. `next` is `spec` when no finding is blocking, and `plan` otherwise; `round` decides from blocking findings and probe findings, never from a minor finding or an unresolved cite. Minor findings stay in `findings` for the record and reach the next author when a round is spent anyway.
- **Spec round** (arbitrate ran). `plan` and `cuts` carry over unchanged, and `specs` is the previous count plus 1. `spec` is this round's Spec and `findings` is the arbiter's findings plus the previous round's minor `author: plan` findings, so they reach the build-loop writer. `next` is `done` when no finding is blocking. Any blocking `author: plan` finding sets `next` to `plan`, which reopens the Plan; the re-cut counts against the Plan cap. Otherwise `next` is `spec`, and the next round re-does spec and arbitrate against the same Plan.
- **Caps.** The Plan cap is 3 attempts and the Spec cap is 3 attempts, each counted over the whole call; a reopen resets neither count. After `next` is set, `round` turns it into `refused` when it is `plan` and `cuts` is 3, or when it is `spec` and `specs` is 3. `round` is the only place that refuses on a cap; `max_iterations: 6` is never the reason a call stops.

A failed body node fails `round` on its reference and fails the group, the same as today. Nothing retries.

### `plan-review/plan-review.yaml`, `verdict`

An inline script that builds the block's `Result` from `INPUTS_RECALL` and `INPUTS_ROUND`, both canonical JSON, and prints it on stdout as one line of compact JSON (`separators=(",", ":")`), keys in the order `verdict`, `recalled`, `findings`, `decisions`, `approval`, `key`, `plan`, `spec`.

- **Reuse** (`round` is null, `recall.next` is `reuse`). `verdict`, `plan`, `spec`, `findings`, `decisions` and `approval` are the record's, `recalled` is true, and `key` is `recall.key`.
- **Rounds** (`round` is the last `round` output, `recall.next` is `rounds`). `verdict` is `pass` when `next` is `done` and `refused` otherwise. `plan` passes through. `spec` is the round's `spec`, or `{}` when null, so a call refused at the Plan still meets the schema. `findings` is the round's `findings`. `decisions` is the Plan's decisions followed by the Spec's, unique by id; a decision a finding targets stays. `recalled` is false, `approval` is `{ state: none, text: "" }`, and `key` is `recall.key`.
- Any other pairing (`round` null with `next` `rounds`, or `round` set with `next` `reuse`) exits non-zero and fails the node. Nothing retries.

The `plan-review.yaml` description states `recall` and reuse, the sequential order, the Detective, the Examiner, the caps of 3 Plan attempts and 3 Spec attempts, and `keep`.

```python
# verdict, inline in plan-review.yaml
def decisions(plan: dict, spec: dict) -> list: ...  # every decision of the Plan and Spec, unique by id
def main() -> int: ...  # reads INPUTS_RECALL and INPUTS_ROUND, prints Result as compact JSON in the key order above
```

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

- `plan-review/commands/plan.md`. The prior Plan and findings come from `$LOOP_PREV.round.output.plan` and `.findings`, not from `$LOOP_PREV.plan/prosecute/arbitrate`. The planner works out its questions from the design, scope, survey, carry and the prior Plan and findings, and calls `detective` through the `Agent` tool before it plans. It calls the Detective again whenever more needs answering, and builds the Plan from the tables. Each step's `cites` carries, unchanged, every Detective cite the step relies on; the planner never edits a line number. It addresses every `author: plan` finding its own way and may leave an unfounded one. A Plan code step lists a test file or test support in `paths` only when it repairs or ports existing tests or support and changes no production behaviour. A unit whose whole work is a green full gate then the merge is listed in `landed`, with no step: `finish` lands only after its `gate` node runs the full gate green, and a step check tests its own section only. `blocked_by` lists only decision ids and ids of earlier steps; a step id means that step's check must pass first. When design text and a rule in these instructions conflict, it lists a decision quoting both, whether or not the design leaves the choice open. On iteration 1, when `$recall.output.record` is not null, it revises the record's Plan from the record's `author: plan` findings, and a `rejected` approval's `text` is one more `author: plan` finding. Every iteration it reads the record's `carry` beside `$INPUTS.carry`, so an owner answer already given is not asked again. It never reads `$STATE_DIR`. Its rules are unchanged.
- `plan-review/commands/prosecute.md`. The Plan is `$cite.output.plan`, whose cites `cite` has resolved. The prosecutor never checks or corrects a cite's line; an unresolved cite reaches the planner from `round`, not from the prosecutor. Every unit in scope has a step or is listed in `landed`; it demands no step check that runs the full gate. Its findings carry `basis` and `severity` (`minor`: wording, clarity, or anything whose fix would not change what is built or tested; otherwise `blocking`; a `design_it_in` finding is always `blocking`), and it passes a Plan with no blocking finding. It files `design_it_in` true only when the basis quotes the design text or fact that gives the one answer; a choice only the owner can make is never failed as having one sensible answer. On a conflict between design text and a rule in these instructions it files one finding quoting both, and the author lists it as a decision. It checks `blocked_by` lists only decision ids and ids of earlier steps, and never writes the planner's `blocked_by`. Everything else is unchanged.
- `plan-review/commands/spec.md`. The Plan is `$LOOP_PREV.round.output.plan`, which the prosecutor approved. The prior Spec is `.spec` and the findings are `.findings`; it addresses the `author: spec` ones its own way and may leave an unfounded one. `step` and a test step's `before` are null only for test-only work, and a line with `step` null is mark GREEN. A port line (`preserves` set, mark GREEN, test moved or ported with its assertion unchanged) may give setup and assertion null; file is still required. No test builds machinery for one condition: no class, subclass, factory, registry or option-taking helper that only one line uses, where a direct setup in that test would do; a fixture, literal input or plain setup for an edge case is not machinery. `blocked_by` lists only decision ids and ids of earlier steps. When design text and a rule in these instructions conflict, it lists a decision quoting both, whether or not the design leaves the choice open. The specifier decides what needs measuring and calls `examiner` through the `Agent` tool with the scratch directory `$ARTIFACTS_DIR/.archon/scratch/spec/`. It calls the Examiner again whenever more needs spiking, and builds the Spec from the measurements. It never changes the Plan. When `.spec` is null and `$recall.output.record` is not null, it revises the record's Spec from the record's `author: spec` findings. Every iteration it reads the record's `carry` beside `$INPUTS.carry`. It never reads `$STATE_DIR`. Its rules are unchanged.
- `plan-review/commands/arbitrate.md`. The Plan is `$LOOP_PREV.round.output.plan`. Its cross-check reads "every `step` and `before` names a Plan step, or is null for test-only work" and "a test step's `before` equals its lines' `step`", allows a test file in a code step's paths only for a step that repairs or ports existing tests or support, accepts a port line's null setup and assertion, and checks `blocked_by` lists only decision ids and ids of earlier steps. Its findings carry `basis` and `severity` as the prosecutor's do: "State the cause and the basis: quote the design or plan text the finding rests on; never write a remedy." Everything else is unchanged.

### Callers

- `finish/finish.yaml`. `build` still gates on `verdict == 'pass'` and binds `plan` and `spec`. `carry` still passes `$LOOP_PREV.planning.output`.
- Neither caller reads `$STATE_DIR` or looks up a record. Each reads `recalled`, `approval` and `key` only from the Result, as `docs/superpowers/specs/feature-pipeline-finish-design.md` states for `finish` and `feature`.
- `feature/feature.yaml`. The description states the sequential order and the caps of 3 Plan attempts and 3 Spec attempts. The `refused` cancel says "at the Plan or Spec cap" instead of "after two rounds" and still prints `$planning.output.findings`.

### Fixtures

`archon workflow test` (Archon v0.13.2) runs one iteration of a `loop_group` and never runs its `until_bash`, even under `exec-code: true`, and a stub returns the same output on every iteration. In every fixture that reaches `rounds` it therefore runs only iteration 1, a plan round: `plan`, `cite`, `prosecute` and `round` run, `spec` and `arbitrate` are skipped, and `verdict` reads that one `round` output, so its `verdict` field is `refused` whenever it runs. Fixtures cover only this single pass. Every route that needs a second iteration (a spec round, `next: done`, a reopen, either cap) is proved by the live-run checks below, and no fixture exists for it.

Each fixture sets `exec-code: true`, runs `cite`, `round` and `keep` unstubbed, runs `recall` unstubbed everywhere but the `recalled` fixture, and lists its route in `fixture.reached`. An unstubbed `recall` reads the simulation's own empty `$STATE_DIR`, so it returns `next: rounds` and a null record; an unstubbed `keep` writes only there. A fixture proves "did not run" by leaving that node unstubbed: strict coverage fails a reached node that has no stub. `fixture.resolved-text-contains` takes one fragment per node, so a fixture with several checks puts each on a different node. A `script:` node receives its `with:` bindings only as `INPUTS_<UPPER_SNAKE>` environment variables, and its resolved text carries none of them, so no fixture checks a `script:` node's resolved text. No node substitutes `$round.output` into its text within one iteration, so `round`'s `next`, `cuts` and `specs` are proved by live-run check L2, not by a fixture. A fixture proves what `round` hands on through `keep`, a bash node whose resolved text carries `$verdict.output` verbatim: `verdict`'s compact JSON, opening `"verdict":…,"recalled":…,"findings":…`. A stubbed finding lists `author` first, `target` second and `cause` third, so its opening keys form one contiguous fragment.

A caller's passing fixture stubs plan-review's `verdict` node with a `pass` result (`verdict: pass`, `plan`, `spec`, `findings: []`, `decisions: []`, `recalled: false`, `approval: { state: none, text: "" }`, `key`; `feature`'s `recalled-approved` fixture uses the recalled stub `docs/superpowers/specs/feature-pipeline-finish-design.md` states), keyed as `archon workflow run <caller> --dry-run --stubs-init` spells it (`planning__verdict` in `feature`). A caller's refused fixture leaves `verdict` unstubbed, so the real `round` and `verdict` produce the refusal. No caller fixture stubs `spec`, `arbitrate`, `recall` or `keep`.

| Fixture | Stubs | Route (`fixture.reached`) | Checks |
|---|---|---|---|
| `plan-review/fixtures/plan-passed.stubs.yaml` | plan; prosecute `pass` | recall, rounds, plan, cite, prosecute, round, verdict, keep | `keep`: `"verdict":"refused","recalled":false,"findings":[]`. A Plan the prosecutor passed with every cite resolved reaches the Result from `rounds` with no finding. |
| `plan-review/fixtures/plan-failed.stubs.yaml` | plan; prosecute `fail` with one finding, `author: plan` | recall, rounds, plan, cite, prosecute, round, verdict, keep | `keep`: `"verdict":"refused","recalled":false,"findings":[{"author":"plan"`. The prosecutor's `author: plan` finding reaches the Result. |
| `plan-review/fixtures/cites.stubs.yaml`, with `plan-review/fixtures/cites.txt` | plan with one step citing `cites.txt` three times: line 1 `alpha line one` (exact), line 4 `gamma line three` (the quote is on line 3), line 2 `omega line none` (in no line); prosecute `pass`; spec and arbitrate `pass` | recall, rounds, plan, cite, prosecute, round, spec, arbitrate, verdict, keep | `prosecute`: `"line":3,"quote":"gamma line three"`, so the prosecutor gets the Plan with the off line corrected. `round`: `"line":2,"quote":"omega line none","reason":"quote not found"`, so the missing quote is refused and its line left as written. `keep`: `"findings":[{"author":"plan","target":"c1","cause":".archon/workflows/feature-pipeline/plan-review/fixtures/cites.txt:2: quote not found"`, so an unresolved cite becomes a minor `author: plan` finding, carried to the end, and the review passes. `cites.txt` is a fixed, committed text file only this fixture reads. |
| `plan-review/fixtures/recalled.stubs.yaml` | recall with `next: reuse` and a record whose `verdict` is `pass`, `approval` `{ state: none, text: "" }` and `run` another run's id; no stub for `plan`, `prosecute`, `spec` or `arbitrate` | recall, verdict, keep | `keep`: `"verdict":"pass","recalled":true`. A reusable record skips `rounds`, runs no agent, and `verdict` returns the record. |
| `finish/fixtures/approved.stubs.yaml` | baseline, sync, plan, prosecute `pass`, the `verdict` pass stub, and today's build-loop, gate, bail and land stubs | baseline, cycle, sync, gate, bail, land | `finish` builds and lands on a passing plan-review result. |
| `finish/fixtures/refused.stubs.yaml` | baseline, sync, plan, prosecute `fail` (`author: plan`), and today's stubs after `planning`; `verdict` unstubbed | baseline, cycle, sync, gate, bail, ask | A refused verdict from the real `round` and `verdict` reaches `finish` and meets the schema. |
| `feature/fixtures/approved.stubs.yaml` | read-request, plan, prosecute `pass`, the `planning__verdict` pass stub, and today's gate stub | read-request, planning__verdict, gate | `feature` reaches its gate on a passing plan-review result. Expect `completed`. |
| `feature/fixtures/rejected.stubs.yaml` | as `approved`, with today's rejecting gate stub | read-request, planning__verdict, gate, rejected | A rejection at the gate cancels. Expect `cancelled`. |
| `feature/fixtures/refused.stubs.yaml` | read-request, plan, prosecute `fail` (`author: plan`); `planning__verdict` unstubbed | read-request, planning__verdict | The `refused` cancel reads findings from the real verdict. Expect `cancelled`. |

`plan-review/fixtures/passed.stubs.yaml`, `plan-review/fixtures/refused.stubs.yaml` and `feature/fixtures/round-2.stubs.yaml` are deleted.

### Live-run checks

These checks replace a fixture for every route that needs a second `rounds` iteration. Each is read from a live run's trace: which body nodes ran in each iteration, each iteration's `round` output, and `verdict`. L1, L2, L3, L8 and L9 are read on the first live run of the rebuilt `plan-review` (through `feature` or `finish`). L4 to L7, L10 and L11 are each read on the first live run that takes that route; a route no live run has taken stays unproved.

| Check | Route | The run must show |
|---|---|---|
| L1 Loop end | every call | `rounds` stops after the first iteration whose `round.next` is `done` or `refused`, through `until_bash`; it never runs to `max_iterations: 6`. |
| L2 Plan round | every iteration whose previous `round.next` is not `spec` | `plan`, `cite` and `prosecute` ran; `spec` and `arbitrate` were skipped; `cuts` is the previous count plus 1 and `specs` is unchanged, 0 on iteration 1; `next` is `spec` when the prosecutor passed and `cite` left no cite unresolved, and `plan` (or `refused` at the cap) otherwise. |
| L3 Spec round | every iteration whose previous `round.next` is `spec` | `spec` and `arbitrate` ran; `plan`, `cite` and `prosecute` were skipped; `round.plan` and `cuts` equal the previous iteration's and `specs` is the previous count plus 1. |
| L4 Pass | the arbiter passes a Spec | that iteration's `round.next` is `done`, the loop ends there, and `verdict` is `pass` with that `round`'s `plan` and `spec`. |
| L5 Spec retry and Spec cap | the arbiter fails a Spec with only `author: spec` findings | the next iteration is a spec round against the same Plan; the round where `specs` reaches 4 with `next` `spec` sets `next` to `refused`, and `verdict` is `refused`. |
| L6 Reopen | the arbiter returns an `author: plan` finding | the next iteration is a plan round whose planner reads that finding; `cuts` is the previous count plus 1 and `specs` is not reset. |
| L7 Plan cap | the prosecutor fails the Plan three times | the round where `cuts` reaches 3 with `next` `plan` sets `next` to `refused`, no spec round follows, and `verdict` is `refused`. |
| L8 Sub-agents | every call | `plan` calls `detective` and `spec` calls `examiner` through the `Agent` tool; the Examiner writes only under `$ARTIFACTS_DIR/.archon/scratch/spec/` and the run's checkout is unchanged. |
| L9 Record written | every call | `keep` ran after `verdict`, and `$STATE_DIR/feature-pipeline/plans/<key>.json` for `recall`'s `key` holds that call's Result with `run` equal to the run's `$WORKFLOW_ID`. |
| L10 Reuse | `recall` finds a record with `verdict` `pass`, approval not `rejected`, written by another run, with `moved` empty, its `head` this commit or an earlier one | `recall.next` is `reuse`, `rounds` and every body node were skipped, and `verdict` returns the record's Plan and Spec with `recalled: true`. |
| L11 Start from a record | `recall` finds a record it does not reuse | `recall.next` is `rounds`; the first plan round's Plan revises the record's Plan, and the first spec round's Spec revises the record's Spec. |

## Homes

| Concern | Home | Forbidden elsewhere |
|---|---|---|
| Review order: plan, prosecute, then spec and arbitrate against the approved Plan | `plan-review`'s `rounds` body; `round.next` picks each iteration | A spec or arbitrate depending on `plan` or `prosecute`; a spec written beside an unpassed Plan; a separate route, approval or counter node |
| State carried between iterations (latest Plan, latest Spec, findings, Plan and Spec attempt counts, next phase) | `round` | `$LOOP_PREV.plan`, `$LOOP_PREV.prosecute`, `$LOOP_PREV.spec` or `$LOOP_PREV.arbitrate` in any command; a `script:` node or artifact file carrying it |
| Detective role | the `detective` inline agent on `plan` | A Detective on any other node; a Detective that writes or runs anything; a second copy of the Detective prompt; an on-disk `.claude/agents/` detective; Detective rules restated in `plan.md` |
| Examiner role | the `examiner` inline agent on `spec` | An Examiner on any other node; measuring in the checkout; a second copy of the Examiner prompt; an on-disk `.claude/agents/` examiner; Examiner rules restated in `spec.md` |
| Research for the Plan | `plan` calling `detective` through the `Agent` tool, as often as it needs | The planner reading, measuring or spiking the checkout itself; a file tool in `plan`'s `allowed_tools` beyond the Read, Grep and Glob the Detective needs (Archon caps an inline agent's tools at its node's); a separate Detective node for the Plan |
| Research for the Spec | `spec` calling `examiner` through the `Agent` tool, as often as it needs | A separate Examiner node for the Spec |
| Citation resolution (a cite's line checked against its quote, and corrected) | `cite`, `plan-review/scripts/cite.py` | Any agent checking, correcting or arguing a line number; the prosecutor ruling on a cite's line; a second resolver or a resolver written into a command; a cite with no `quote` |
| Throwaway copies | `$ARTIFACTS_DIR/.archon/scratch/`, which Archon removes when the run ends | Any write to the run's checkout during `plan-review` |
| Caps: 3 Plan attempts and 3 Spec attempts per call | `round`, through `cuts`, `specs` and `next: refused`; `rounds.max_iterations: 6` is only a backstop the caps always reach first | A count of attempts in a command or in a caller; a cap enforced by `max_iterations`; a counter node beside `round` |
| Did-not-run proof in fixtures | the node left unstubbed under strict coverage | A stub for a node the case says never runs |
| Proof of `round`'s `next`, `cuts` and `specs`, and of every route that needs a second `rounds` iteration (spec round, `next: done`, reopen, both caps) | the live-run checks L1 to L8 | A fixture for such a route; a stub, node or loop setting that fakes a later iteration; a node, binding or output field added to expose `round`'s fields to a fixture; a fixture check on a `script:` node's resolved text |
| Plan record reads and writes within `plan-review` (path, key, schemas and reuse rule homed in `docs/superpowers/specs/feature-pipeline-finish-design.md`) | `recall` reads; `keep` writes | Any other `plan-review` node or command reading or writing `$STATE_DIR`; a key, record path, `Recall` or `Record` schema restated in this block's commands; `round` carrying the record |
| Result assembly, recalled or from `rounds` | `verdict`, the inline script | A bash `verdict`; a caller or `keep` building or patching a Result; a second node combining `recall` and `rounds` |
| Authors starting from a recalled record | `plan.md` on iteration 1 and `spec.md` with no prior Spec, reading `$recall.output.record` | `round` seeding the Plan or Spec from the record; an author reading a record by path |
| `recall` and `keep` in fixtures | unstubbed in every fixture, but `recall` stubbed in `plan-review`'s `recalled` fixture | A stub on `keep`; a stub on `recall` in any other fixture; a fixture writing outside the simulation's `$STATE_DIR` |
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
4. `architect` (a `rulings` pass): `docs/superpowers/specs/feature-pipeline-finish-design.md`. Its `plan-review` section, its round-2 and round-cap bullets, its `feature` paragraph (the round-2 route), and its Homes rows for the capped review round, the test spec and the Spec cross-check come to state this design's order, Detective, Examiner, citation resolver and caps of 3 Plan attempts and 3 Spec attempts. Runs after this design is approved.
5. `workflow-builder`: `plan-review/plan-review.yaml` (`recall`, `rounds` skipped on reuse, `verdict` as the inline script returning Result, `keep`, the description), `plan-review/commands/plan.md`, `plan-review/commands/spec.md`, and `plan-review/fixtures/` (`plan-passed.stubs.yaml`, `plan-failed.stubs.yaml` and `cites.stubs.yaml` with `recall` and `keep` on their routes, `recalled.stubs.yaml` new). This is the same work as step 10 of `docs/superpowers/specs/feature-pipeline-finish-design.md`'s Order and is built once. `archon validate workflows plan-review` must pass with no `dag_node_output_ref_unknown_node` warning, and `archon workflow test plan-review` must pass. Runs after steps 1 to 4. The docs under `docs/reference/archon/` do not state the following, and this step's fixtures prove each one:
   - A bash node's resolved text carries a whole-output reference to an executed `script:` node as that node's stdout, verbatim. The `plan-passed` fixture's `keep` check proves it.
   - A `rounds` body node may read `$recall.output`, a top-level node upstream of `rounds`. Every fixture that reaches `plan` proves it.
   - A `when:`-skipped `loop_group` binds `if_skipped` through `with:`. The `recalled` fixture proves it.

   If any of these fails, the builder stops and reports it with the failing output. It adds no workaround node.
