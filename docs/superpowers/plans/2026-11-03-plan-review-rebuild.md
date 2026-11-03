# plan-review Rebuild Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Every build task runs on Opus; the lead session dispatches and reads, it does not build. Sonnet is not used for any task in this plan.

**Goal:** Replace the `rounds` section of `plan-review` with four persistent speaker sessions forked from one `brief` turn, a `route` node that reads only verdicts, and nothing else.

**Architecture:** `brief` reads the inputs once per call and returns `{ ok: true }`. `plan`, `prosecute`, `spec` and `arbitrate` each carry `context: { resume: brief }` and continue their own branch across every iteration of `rounds`. `route` is the only jq in the round: it maps the last verdict to the next phase and carries the Plan, the Spec and minor findings. `probe.py`, `hold`, the finding ledger, the matcher and the caps are deleted with no replacement. Memory, repetition and question legitimacy live in the agents.

**Tech Stack:** Archon 0.13.2 workflow YAML, command markdown, jq in bash nodes, `scripts/cite.py` (unchanged), `archon validate` and `archon workflow test` fixtures.

**Spec:** `docs/superpowers/specs/2026-11-03-plan-review-rebuild-design.md`. Executors read the spec and this plan. The spec's Standard, Shape, Outputs, Commands, Fixtures and Homes sections are the requirements; this plan only orders them and names who does each.

## Global Constraints

- Repository rules 1 to 5 of `CLAUDE.md`: no scaffolding; a missing Archon feature stops the work and is reported; token waste is a defect; a stop on a non-issue is a defect; one such defect condemns the file.
- The result contract to `feature` and `finish` is unchanged: `verdict`, `plan`, `spec`, `findings`, `decisions`, `questions`, `question`, `stopped`, `recalled`, `approval`, `key`; schema at `plan-review.yaml:707-726`. `questions` is always `[]`.
- The inputs block (`plan-review.yaml:32-65`), `track`, `keep`, `track.md` and `scripts/cite.py` are unchanged.
- No caller yaml changes. `feature.yaml` and `finish.yaml` are read, never edited.
- `max_iterations` of `rounds` stays 24. No check, no fixture, no command relies on it.
- Every fixture sets `exec-code: true`, leaves `recall` (except `recalled`), `cite`, `route` and `keep` unstubbed, stubs `brief` with `{ ok: true }` wherever it reaches `rounds`, and lists its route in `fixture.reached`.
- Forbidden in every file, from the spec's Homes table: a ledger, `$LOOP_PREV.<speaker>` in any command, inputs re-sent on a later turn, a matcher, a count, a cap, a diff of findings, a hold node, a decision id in `blocked_by`, a repair or alternative in a finding, a second router, jq that reads finding text, any agent ruling on a line number, any script ruling on a step, a speaker reading the checkout itself, a round node touching `$STATE_DIR`, a node added to expose a session to a fixture.
- Commands are the same text on every turn. No command branches on the turn number.

## Review Focus

Fixtures run one iteration, so these conditions are never exercised by a fixture. Each is pinned to the task that owns it and read from the live run in Task 4.

1. Iteration 2 of a spec round: `route` must add the previous `route`'s minor findings (the cite minors) to the arbiter's findings, or the build-loop never sees them. Owner: Task 1 `route` jq, read at L4.
2. A reviewer returns `fail` with an empty `findings` list: the author gets nothing to revise and the round burns a turn. Owner: Task 1, `prosecute.md` and `arbitrate.md` state that `fail` carries at least one blocking finding, and `output_format` cannot express it. Read at L1.
3. A reviewer returns `pass` while the author's `question` is not `""`: the question is lost and the build proceeds on an unanswered question. Owner: Task 1, the two reviewer commands state the rule from the spec's Outputs section. Read at L6.
4. A plan round after a spec round: the planner's branch was skipped one iteration and must still hold its Plan. Owner: Task 0 proves it on the spike (`b` skips iteration 2); read at L3.
5. A resumed call whose seed is `spec`: `brief` carries the question and `$INPUTS.answer`, and iteration 1 runs a spec round from `$recall.output.seed.plan` with `plan`, `cite` and `prosecute` skipped. Owner: Task 1 fixture `resumed`; read at L6.

---

### Task 0: Spike session continuation across loop iterations

**Agent:** `spiker`, model `opus`. Throwaway pack under the spiker's scratchpad, never under this repository. Run with the cheapest Claude model Archon accepts (`model:` is a per-node field, `docs/reference/archon/workflow-language.md:123`).

**Files:**
- Create (scratchpad only): one pack folder with one workflow yaml, three command files, one text file for `a` to read.
- Nothing in `/home/atom/dev/archon-workflows`.

**Interfaces:**
- Consumes: `docs/reference/archon/workflow-language.md` (loop groups at 219 and 228, inline agents at 647, `context: { resume }`).
- Produces: a report, per node and iteration, of: the list returned, the session ID preview, whether `a`'s read was refused, whether `a`'s output met its schema, whether `b`'s agent ran. Task 1's brief carries this report verbatim.

- [ ] **Step 1: Build the pack as the spec's Order step 0 states.** One command node `seed` outside a `loop_group` of three iterations, `allowed_tools: [Read]`, told that two nodes will continue from its session and that it only reads the named file. Body nodes `a` and `b`, both `context: { resume: seed }`. `a`: `allowed_tools: []`, an `output_format` the seed does not have (`{ list: integer[], read: string }`, `required`, `additionalProperties: false`), told to append the iteration number to the list it remembers, to try to read the named file and report the result, and to return in the schema. `b`: `when:` that skips iteration 2, `allowed_tools: [Agent]`, one inline agent that returns one fixed word, told to append the iteration number to its remembered list and to have the agent return the word; `output_format` `{ list: integer[], word: string }`.

- [ ] **Step 2: Run it.** `archon validate workflows <pack>` then one live run with the cheapest model. Record the trace path.

- [ ] **Step 3: Read the trace and report against the pass line.** Pass is: both lists grow across iterations; `b`'s list skips 2 and still holds 1 on iteration 3; the two lists are not shared; `a` cannot read; `a`'s schema holds; `b`'s agent runs. Any miss is reported with the trace line as a missing Archon feature. Nothing further is built on a miss.

- [ ] **Step 4: Report** the table, the trace path, the pass or the named misses. No commit; nothing to commit.

---

### Task 1: Rebuild `plan-review`

**Agent:** `workflow-builder`, model `opus`. Starts only with Task 0's pass report in its brief.

**Files:**
- Modify: `.archon/workflows/feature-pipeline/plan-review/plan-review.yaml` (`recall` and `verdict` question handling; new `brief` node after `track`; `rounds` body replaced; `verdict` reads `route`).
- Create: `.archon/workflows/feature-pipeline/plan-review/commands/brief.md`.
- Rewrite from nothing: `commands/plan.md`, `commands/prosecute.md`, `commands/spec.md`, `commands/arbitrate.md`. The uncommitted working-tree versions are overwritten; nothing in them is kept.
- Delete: `scripts/probe.py`; fixtures `probe-bad`, `probe-fixed`, `same-field`, `repeated`, `blocked`, `decision-kept`, `minor-passed`, `design-ref` (the last four may instead be rewritten to a row of the fixture table, under that row's name).
- Create or rewrite fixtures: `plan-passed`, `test-free`, `tests-only`, `plan-failed`, `plan-refused`, `plan-blocked`, `cites` (+ `cites.txt`), `resumed`, `spec-reopen`, `recalled` (unchanged).
- Unchanged: `commands/track.md`, `scripts/cite.py`, the inputs block, `track`, `keep`.

**Interfaces:**
- Consumes: Task 0's report; the spec's Shape, Outputs, Commands, Fixtures and Homes sections; `plan-review.yaml:154,173` (`recall` seed), `:209,362` (tests-only skips the Plan), `:220-277` (plan schema), `:380-453` (spec schema), `:707-726` (contract).
- Produces: `rounds` terminal node `route` with output `{ next, resume, plan, spec, findings, question }`; `plan` output `{ plan, question }`; `spec` output `{ spec, question }`; `prosecute` and `arbitrate` output `{ verdict, findings, question }` with `verdict` in `pass|fail|refused|blocked` and findings of `{ author, target, field, cause, severity }`. Task 2 stubs `prosecute` in that shape.

- [ ] **Step 1: Delete** `scripts/probe.py` and the four probe/matcher fixtures. Remove the `probe` and `hold` nodes and the `round` node from `plan-review.yaml` with every reference to them, so the yaml fails validation until the new body is in. Run `archon validate workflows plan-review` and note the failure.

- [ ] **Step 2: `recall` and `verdict`.** `seed` carries `plan`, `spec`, `question`; `answers` pairs that question with `$INPUTS.answer`; `verdict`'s `stopped` is `{ next: blocked, resume, question }`; `questions` is `[]`; `verdict` reads `$rounds.output` as `route`'s JSON. Nothing else in either node changes.

- [ ] **Step 3: `brief` node** after `track`, `allowed_tools: []`, `output_format` `{ ok: boolean }` with `required` and `additionalProperties: false`, command `brief.md` carrying the design, scope, survey, carry, the record's Plan and Spec when `recall` found one, the stopped question and `$INPUTS.answer` when resuming, and the sentence that four roles will continue from this session and this turn only reads.

- [ ] **Step 4: `rounds` body** as the spec's table: `plan` (inline agent `detective` unchanged, resume `brief`), `cite` (unchanged script, `depends_on: [plan]`), `prosecute` (resume `brief`), `spec` (inline agent `examiner` unchanged, resume `brief`), `arbitrate` (resume `brief`), `route` (bash, `trigger_rule: all_done`, terminal). Phase `when:` on iteration 1 from `$track.output.track` and `$recall.output.start`, after that from `$LOOP_PREV.route.output.next`; every iteration-1 read of `$LOOP_PREV.route.output` is `''` and is treated as none. `until_bash` ends the group on `done`, `refused` or `blocked`. `output_format` on every Claude node with `required` and `additionalProperties: false`; `blocked_by` patterns `^c[0-9]+$` on plan steps and `^[cw][0-9]+$` on spec steps.

- [ ] **Step 5: `route` jq**, the spec's two bullet lists and nothing more. Plan round: `fail` to `plan`; `refused` to `refused`; `blocked` to `blocked` with `resume: plan`; `pass` to `done` on `test-free`, else `spec`; `plan` is `$cite.output.plan`; `findings` is the prosecutor's plus one minor `author: plan`, `field: cites` finding per unresolved cite. Spec round: `pass` to `done`; `refused` to `refused`; `blocked` to `blocked` with `resume: spec`; `fail` to `plan` when any finding has `author: plan` and the track is not `tests-only`, else `spec`; `plan` carried; `spec` is `$spec.output.spec`; `findings` is the arbiter's plus the previous `route`'s minor findings. `question` is the blocking reviewer's question or `""`.

- [ ] **Step 6: The four speaker commands** from nothing, each per its paragraph in the spec's Commands section, each the same text on every turn, each stating its role in its first line, what this turn carries, and what the speaker already holds. The reviewer commands carry the Review Focus rules 2 and 3 as one sentence each: `fail` carries at least one blocking finding; a non-empty author `question` is never answered with `pass`.

- [ ] **Step 7: Fixtures** as the spec's table, ten in all. Each stub for `prosecute` or `arbitrate` is in the `{ verdict, findings, question }` shape. `resumed` stubs `recall` with a stopped `spec` seed carrying `plan` and `question` and sets `answer`; its `resolved-text-contains` on `brief` carries the question and the answer. `cites` keeps `cites.txt` and proves one corrected line and one unresolved cite as a minor finding.

- [ ] **Step 8: Validate.** `archon validate workflows plan-review` from the repository root. Expected: no `Task`-ignored warning on `allowed_tools`, no `dag_node_output_ref_unknown_node` warning.

- [ ] **Step 9: Test.** `archon workflow test plan-review`. Expected: every fixture passes.

- [ ] **Step 10: Done-check.** The "Checking the pack" row of `docs/superpowers/specs/feature-pipeline-finish-design.md:513`, read with `route` in place of `hold` and `round`, exits 0. `archon workflow test .archon/workflows/feature-pipeline` will fail on the thirteen caller fixtures until Task 2; report that as expected and do not touch them.

- [ ] **Step 11: Commit** own paths by name: `plan-review.yaml`, the six command files, `fixtures/`, the deletion of `scripts/probe.py`. Report any path left uncommitted.

---

### Task 2: Caller fixtures

**Agent:** `workflow-builder`, model `opus`.

**Files:**
- Modify: `.archon/workflows/feature-pipeline/finish/fixtures/{approved,refused,blocked,red-gate,stuck-decision,stuck-cancelled,unresolved,resolved,refused-cancelled}.stubs.yaml`; `.archon/workflows/feature-pipeline/feature/fixtures/{approved,rejected,refused,recalled-approved}.stubs.yaml`.
- Unchanged: `feature.yaml`, `finish.yaml`, every `planning__verdict` pass stub.

**Interfaces:**
- Consumes: Task 1's `prosecute` output shape `{ verdict, findings, question }`.
- Produces: thirteen fixtures passing.

- [ ] **Step 1: Rewrite each `prosecute` stub** to the new shape. A blocked fixture stubs `verdict: blocked` with a free-text `question`; its expected ask text is that string. A refused fixture stubs `verdict: refused` with one blocking finding `{ author, target, field, cause, severity }`.

- [ ] **Step 2: Test.** `archon workflow test finish` and `archon workflow test feature`, then `archon workflow test .archon/workflows/feature-pipeline`. Expected: all pass, no `dag_node_output_ref_unknown_node` warning.

- [ ] **Step 3: Commit** the thirteen fixture paths by name.

---

### Task 3: Rulings pass on the design documents

**Agent:** `caveman:cavecrew-builder`, model `opus`. Two files.

**Files:**
- Modify: `docs/superpowers/specs/feature-pipeline-finish-design.md` (its `plan-review` section, its Homes rows, the "Checking the pack" row at line 513).
- Modify: `docs/superpowers/specs/plan-review-design.md` (first line only).

**Interfaces:**
- Consumes: the approved spec; Task 1's committed yaml as the ground truth for node names.
- Produces: the finish design states `brief`, the four sessions and `route`; no mention of caps, hold, ledger, `round`, probe or matcher remains.

- [ ] **Step 1: Finish design.** First discard the file's uncommitted working-tree changes from session 07f333b8 with `git checkout -- docs/superpowers/specs/feature-pipeline-finish-design.md`; the spec's Order step 3 rules nothing in them is kept. Then, in the `plan-review` section and the Homes rows, remove the caps, the hold, the ledger, `round` and probe; state `brief`, `context: { resume: brief }` on the four speakers, and `route`. In the "Checking the pack" row, the unstubbed bash list reads `cite`, `route`, `keep` and the collectors. The plan record, key, reuse and resume-after-blocked text stays, with `stopped` as `{ next, resume, question }` and `questions` always `[]`.

- [ ] **Step 2: Old design.** Replace line 1 of `plan-review-design.md` with `Status: superseded by 2026-11-03-plan-review-rebuild-design.md`. Discard the file's other uncommitted working-tree changes with `git checkout -- docs/superpowers/specs/plan-review-design.md` before the edit; the owner has ruled nothing in them is kept.

- [ ] **Step 3: Verify.** `grep -n -i -E 'probe|hold|ledger|matcher|\bcuts\b|\bspecs\b|\$given|addressed' docs/superpowers/specs/feature-pipeline-finish-design.md` returns no line about `plan-review`'s round.

- [ ] **Step 4: Commit** the two paths by name.

---

### Task 4: Owner's first live run

**Agent:** none. The owner runs `feature` or `finish`; the lead session reads the trace.

- [ ] **Step 1:** Read L1 to L6 from the spec's Live-run checks table against the trace, with the Review Focus lines above.

- [ ] **Step 2:** Report each check as shown or not shown, with the trace line. A failure of L1 to L4 is a missing Archon feature, reported and not patched.
