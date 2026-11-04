Status: proposed.

# feature-pipeline: the writer fence

## Why

Every agent that writes the checkout writes it with built-in tools, bounded by its prompt alone. Five copies of write permission sit in the pack:

- `build-loop/build-loop.yaml`: one `write` node, `allowed_tools: [Read, Grep, Glob, Edit, Write, Bash]`, builds test steps and code steps alike, so the agent that writes a code step can also write its tests.
- `build-loop/build-loop.yaml`: `check` runs `$write.output.check` with `bash -c`, and `commit` stages `$write.output.paths`; the writer chooses the command the workflow runs and the paths it commits.
- `finish/finish.yaml`: `resolve` holds built-in `Edit` over the whole checkout.
- `plan-review/plan-review.yaml`: `plan`, `prosecute` and `arbitrate` hold built-in `Read`, `Grep` and `Glob` over the whole checkout.
- `plan-review/plan-review.yaml`: `spec`'s `examiner` holds `Bash`, `Write` and `Edit`, kept out of the checkout by its prompt and the node's `sandbox:`.

The Plan and Spec travel as node outputs, in four copies of one hand-off:

- `plan-review/plan-review.yaml`: `plan`, `cite`, `spec`, `route` and `verdict` carry the whole Plan and Spec from node to node and out of the block.
- `plan-review/plan-review.yaml`: `recall` and `keep` read and write a plan record under `$STATE_DIR/feature-pipeline/plans/`, keyed by design, design blob and scope.
- `feature/feature.yaml`: `gate` prints the Plan and Spec from `$planned.output`, and `approval` writes the owner's answer into the plan record.
- `finish/finish.yaml`: `build` passes `$planning.output.plan` and `$planning.output.spec` into `build-loop`, and `finish/commands/bail.md` reads them from `$planning.output`.

Three rules forbid the fence itself: the roster stub and the "Pack code" row of `docs/superpowers/specs/workflow-builder-design.md` forbid an MCP server; the "Pack code" row of `docs/superpowers/specs/feature-pipeline-finish-design.md` forbids an MCP server and any script but `plan-review/scripts/cite.py`; its "Writes outside a step" row forbids a fence script, and its "Hand-off between nodes" row forbids a file one node writes for another.

## Modules

### `reviews/` in the run's checkout

Every review document lives under one root in the checkout. Each file is written when its node runs.

```text
reviews/plans/plan.json            the Plan; written by the planner, cites resolved in place by cite
reviews/plans/findings/<n>.json    one per prosecutor round: { verdict, findings, question }
reviews/plans/approved/plan.json   the passed Plan; copied by the prosecutor
reviews/specs/spec.json            the Spec; written by the specifier from reviews/plans/approved/ only
reviews/specs/findings/<n>.json    one per arbiter round: { verdict, findings, question }
reviews/specs/approved/spec.json   the passed Spec; copied by the arbiter
reviews/answers.json               [{ design, question, text }]; written by recall
reviews/approval.json              { design, state: approved|rejected, text, plan, spec }; written by feature's approval
```

- `<n>` is one above the highest number in that findings folder, three digits, zero-padded. The newest findings file, by modification time across both findings folders, marks the last finished round.
- `plan` and `spec` in `approval.json` are the `git hash-object` blobs of the two approved files the owner answered on, `absent` for a missing one.
- The tests-only route writes no Plan: `reviews/plans/` stays as recall leaves it and nothing on that route reads it.
- Plan and Spec shapes are the `plan` and `spec` objects of today's `plan` and `spec` output formats.

### `.archon/workflows/feature-pipeline/fence/` (built)

Two stdio MCP servers, run by `uv run --script`, each started by Claude Code once per node from that node's config file. Both resolve every path against `CLAUDE_PROJECT_DIR`, which Claude Code sets to the run's checkout, and ignore the client's roots. Nothing in this design changes them.

```text
files.py   env: CLAUDE_PROJECT_DIR (required), FENCE_READ, FENCE_WRITE, FENCE_DENY
           (colon-separated folders relative to the root; "." is the whole root;
            FENCE_DENY bounds writes only)
           writes under .archon, .claude and .git are always refused
           tools: read_file(path, offset=0, limit=2000), list_directory(path="."),
                  find_files(pattern, path="."), grep(regex, path=".", glob=None),
                  write_file(path, content), edit_file(path, old, new, replace_all=False),
                  copy_file(src, dst), delete_file(path)
           copy_file: read access on src, write access on dst; creates missing
                      destination folders; overwrites an existing dst
checks.py  env: CLAUDE_PROJECT_DIR, FENCE_TEST_COMMAND (required), FENCE_TEST_TIMEOUT (default 900)
           tools: run_tests() -> "exit=<n> timed_out=<bool> seconds=<n>" and the output tail
```

Replaces built-in `Read`, `Grep`, `Glob`, `Edit`, `Write` and `Bash` on every node below.

### Fence configs: `.archon/workflows/feature-pipeline/<workflow>/.archon/feature-pipeline-fence/<role>.json`

One MCP config file per fenced role, in the folder of the workflow that declares the node. A node names it as `mcp: .archon/feature-pipeline-fence/<role>.json`, so the node runs on `mcp__files__*` and `mcp__checks__*` and the built-in tools its `allowed_tools` lists, `[]` on every fenced node but `plan` and `spec`, which list `[Agent]`. Archon looks the path up in the checkout first, then in the declaring workflow's folder; the checkout match it could find is `<checkout>/.archon/feature-pipeline-fence/<role>.json`, under `.archon/`, which `files.py` refuses to every role.

Each server finds its script through `PACK_DIR`, and the checks server its command through `TEST_COMMAND`. The run's launcher exports both into Archon's environment (`PACK_DIR=/home/atom/dev/archon-workflows`, `TEST_COMMAND=<the target repository's single test command>`). Archon expands `${...}` only in `env`, so `command` and `args` read `PACK_DIR` from the server's own environment, and the `:?` guard turns an unset `PACK_DIR` (which Archon expands to `""` with a warning) into a start failure. An unset `TEST_COMMAND` leaves `FENCE_TEST_COMMAND` empty, and `checks.py` refuses to start.

```json
// the two server entries, shared by every config; <FENCE_*> per role below
"files": {
  "command": "sh",
  "args": ["-c", ": \"${PACK_DIR:?PACK_DIR unset}\"; exec uv run --script \"$PACK_DIR/.archon/workflows/feature-pipeline/fence/files.py\""],
  "env": { "PACK_DIR": "${PACK_DIR}", "FENCE_READ": "<read>", "FENCE_WRITE": "<write>", "FENCE_DENY": "<deny>" }
},
"checks": {
  "command": "sh",
  "args": ["-c", ": \"${PACK_DIR:?PACK_DIR unset}\"; exec uv run --script \"$PACK_DIR/.archon/workflows/feature-pipeline/fence/checks.py\""],
  "env": { "PACK_DIR": "${PACK_DIR}", "FENCE_TEST_COMMAND": "${TEST_COMMAND}" }
}
```

| Config file | Node | Servers | `FENCE_READ` | `FENCE_WRITE` | `FENCE_DENY` |
|---|---|---|---|---|---|
| `plan-review/.archon/feature-pipeline-fence/planner.json` | `plan` | files | `.` | `reviews/plans` | `reviews/plans/findings:reviews/plans/approved` |
| `plan-review/.archon/feature-pipeline-fence/prosecutor.json` | `prosecute` | files | `.` | `reviews/plans/findings:reviews/plans/approved` | `""` |
| `plan-review/.archon/feature-pipeline-fence/specifier.json` | `spec` | files | `.` | `reviews/specs` | `reviews/specs/findings:reviews/specs/approved` |
| `plan-review/.archon/feature-pipeline-fence/arbiter.json` | `arbitrate` | files | `reviews/specs:tests:reviews/plans/approved` | `reviews/specs/findings:reviews/specs/approved` | `""` |
| `build-loop/.archon/feature-pipeline-fence/test-writer.json` | `tests` | files, checks | `reviews/specs/approved:tests` | `tests` | `""` |
| `build-loop/.archon/feature-pipeline-fence/implementer.json` | `implement` | files, checks | `.` | `.` | `tests:reviews` |
| `build-loop/.archon/feature-pipeline-fence/testreview.json` | `testreview` | files | `reviews/specs/approved:tests` | `""` | `""` |
| `build-loop/.archon/feature-pipeline-fence/codereview.json` | `codereview` | files | `.` | `""` | `""` |
| `finish/.archon/feature-pipeline-fence/resolver-tests.json` | `resolvetests` | files | `reviews/specs/approved:tests` | `tests` | `""` |
| `finish/.archon/feature-pipeline-fence/resolver-plans.json` | `resolveplans` | files | `.` | `reviews/plans/findings:reviews/plans/approved` | `""` |
| `finish/.archon/feature-pipeline-fence/resolver-specs.json` | `resolvespecs` | files | `reviews/specs:tests:reviews/plans/approved` | `reviews/specs/findings:reviews/specs/approved` | `""` |
| `finish/.archon/feature-pipeline-fence/resolver.json` | `resolve` | files | `.` | `.` | `tests:reviews` |

No other folder is named in any config. `.archon/`, `.claude/` and `.git/` are refused by `files.py` itself and appear in no config. Each `finish` resolver config carries the `FENCE_*` values of the role that writes its folder: `resolver-tests.json` the test writer's, `resolver-plans.json` the prosecutor's, `resolver-specs.json` the arbiter's, `resolver.json` the implementer's.

Unmeasured, shown by the first live run: whether Claude Code passes `CLAUDE_PROJECT_DIR`, `PATH` and the rest of the environment the test command needs to a stdio server given an `env` block; whether a session resumed from `brief` starts the node's servers; whether an inline sub-agent reaches its node's MCP servers; whether the `examiner` keeps built-in tools its node's `allowed_tools` does not list.

### `.archon/workflows/feature-pipeline/plan-review/`

Each agent returns only its verdict and question; every Plan, Spec and finding is a file under `reviews/`.

```yaml
- id: recall        # bash; reads and writes reviews/ (no $STATE_DIR, no key)
  # design blob as today (checkout, else design_ref, else "absent")
  # last = newest commit touching reviews/plans or reviews/specs (git log -1, default
  #        history simplification), with its Design, Design-Blob and Planning trailers
  # stale: last exists and its Design or Design-Blob differs from this design -> rm -rf
  #        reviews/plans reviews/specs before anything reads them
  # answer given: append { design, question: stopped.question, text: answer } to
  #        reviews/answers.json; answers = its entries for this design
  # approval = reviews/approval.json's state when its design is this design and its plan
  #        and spec blobs match the approved files as they stand, else none
  # next: reuse when no resume, last is not stale, last's Planning is done,
  #        `git status --porcelain -- reviews/plans reviews/specs` is empty and approval
  #        is not rejected; else rounds
  # start: resume's round when resume is given; else from the newest findings file:
  #        none -> plan; a plans file -> spec on pass, plan otherwise; a specs file ->
  #        plan on fail with a blocking finding whose author is plan, spec otherwise;
  #        plan whenever last's Planning is done
  mutates_checkout: true
  output_format: { design, design_blob, read, from, root, branch, head, next: rounds|reuse,
                   start: plan|spec, answers, approval: approved|rejected|none }
- id: plan          # commands/plan.md; writes reviews/plans/plan.json
  allowed_tools: [Agent]
  mcp: .archon/feature-pipeline-fence/planner.json
  agents:
    detective:
      tools: [mcp__files__read_file, mcp__files__list_directory, mcp__files__find_files, mcp__files__grep]
  output_format: { question: string }
- id: cite          # script cite.py: reads reviews/plans/plan.json, resolves each cite in place,
                    # rewrites the file (plan.json.tmp, then mv); outputs { unresolved }
- id: prosecute     # commands/prosecute.md, carries $cite.output.unresolved; writes its findings
                    # file, unresolved cites as minor findings; on pass,
                    # copy_file(reviews/plans/plan.json, reviews/plans/approved/plan.json)
  allowed_tools: []
  mcp: .archon/feature-pipeline-fence/prosecutor.json
  output_format: { verdict: pass|fail|refused|blocked, question: string }
- id: spec          # commands/spec.md; writes reviews/specs/spec.json from
                    # reviews/plans/approved/plan.json (no Plan on the tests-only route)
  allowed_tools: [Agent]
  mcp: .archon/feature-pipeline-fence/specifier.json
  sandbox: # as today
  agents:
    examiner:
      tools: [Bash, Write, Edit, mcp__files__read_file, mcp__files__list_directory, mcp__files__find_files, mcp__files__grep]
  output_format: { question: string }
- id: arbitrate     # commands/arbitrate.md; writes its findings file; on pass,
                    # copy_file(reviews/specs/spec.json, reviews/specs/approved/spec.json)
  allowed_tools: []
  mcp: .archon/feature-pipeline-fence/arbiter.json
  output_format: { verdict: pass|fail|refused|blocked, question: string }
- id: route         # bash: next from the verdict that ruled this round, as today; reads the
                    # arbiter's findings file with jq for a blocking plan finding
  output_format: { next: plan|spec|done|refused|blocked, resume: plan|spec|null, question: string }
- id: reviews       # bash, when route's next is spec or done:
                    # git add -A -- reviews; git commit -q -m "reviews: <plan|spec> approved"
                    #   --trailer "Design: <design>" --trailer "Design-Blob: <blob>"
                    #   --trailer "Planning: <spec|done>" -- reviews
  depends_on: [route]
- id: verdict       # verdict, question, stopped (route's output plus answers, when blocked),
                    # recalled, approval (recall's), findings (the newest findings file's, [] on reuse)
```

`keep` is removed. `plan`, `cite`, `spec` and `route` lose their Plan and Spec fields; `route`'s `plan`, `spec` and `findings` fields go. Every node in the block drops `mutates_checkout: false` but `track` and `brief`.

- `commands/brief.md` carries no plan record and no seed Plan or Spec: the Plan and Spec to start from are `reviews/plans/plan.json` and `reviews/specs/spec.json` as they stand, the owner's word on them is `$recall.output.approval`, and the owner's answers are `$recall.output.answers`.
- `commands/plan.md` writes the Plan to `reviews/plans/plan.json` with `write_file` and returns only `question`; the detective reads through the `files` tools.
- `commands/prosecute.md` and `commands/arbitrate.md` name the `files` tools in place of `Read`, `Grep` and `Glob`, write the round's findings file, copy the passed file to `approved/` with `copy_file`, and return only `verdict` and `question`. `arbitrate.md` states that the arbiter reads only `reviews/specs/`, `tests/` and `reviews/plans/approved/` and holds the design from `brief`.
- `commands/spec.md` writes the Spec to `reviews/specs/spec.json` and returns only `question`. It reads the Plan from `reviews/plans/approved/plan.json` alone and may read source. It writes the Spec's test steps in build order: in the Plan order of the code step each step's `before` names, steps with `before` null last. `commands/arbitrate.md` adds that order to its cross-check, as a `field: order` finding.
- The examiner writes only its scratch copy under `$ARTIFACTS_DIR/.archon/scratch/spec/`.
- `scripts/cite.py` reads and rewrites `reviews/plans/plan.json` under the working directory and prints `{"unresolved": [...]}`; it takes no `INPUTS_PLAN`.

### `.archon/workflows/feature-pipeline/build-loop/`

The `write` node becomes two writers, `tests` for test steps and `implement` for code steps. `review` becomes `testreview`, on test steps, and `codereview`, on every step. The workflow, not a writer, holds each step's check and paths, read from the approved files.

```yaml
# build-loop.yaml (include block)
inputs: {}
returns: result

nodes:
  - id: before        # bash: { status: git status --porcelain -- . ':(exclude)reviews',
                      #         first } from the approved files with jq
  - id: steps
    depends_on: [before]
    loop_group:
      max_iterations: 200
      until_bash: |
        r=$codereview.output.remaining; [ "$r" = 0 ]
      nodes:
        - id: tests       # test writer: sonnet, medium; commands/tests.md; context: fresh
          when: "$LOOP_PREV.codereview.output.kind == 'test' || $LOOP_PREV.codereview.output == '' && $before.output.first == 'test'"
          allowed_tools: []
          mcp: .archon/feature-pipeline-fence/test-writer.json
          settingSources: []
          output_format: Built
        - id: implement   # implementer: sonnet, medium; commands/implement.md; context: fresh
          when: "$LOOP_PREV.codereview.output.kind == 'code' || $LOOP_PREV.codereview.output == '' && $before.output.first == 'code'"
          allowed_tools: []
          mcp: .archon/feature-pipeline-fence/implementer.json
          output_format: Built
        - id: check       # bash: step id is $tests.output.step_id$implement.output.step_id (the skipped
                          # writer reads ''); jq finds that step in reviews/plans/approved/plan.json or
                          # reviews/specs/approved/spec.json and runs its `check` with bash -c;
                          # always exits 0; outputs status green|red and the output tail
          depends_on: [tests, implement]
          trigger_rule: none_failed_min_one_success
        - id: commit      # bash, when check is green: git add and git commit of that step's `paths`,
                          # read the same way; then outputs git status --porcelain -- . ':(exclude)reviews'
          depends_on: [check]
          trigger_rule: all_done
        - id: testreview  # opus, medium; commands/testreview.md; context: fresh
          depends_on: [commit]
          when: "$tests.output.step_id != ''"
          allowed_tools: []
          mcp: .archon/feature-pipeline-fence/testreview.json
          output_format: TestReview
        - id: codereview  # opus, medium; commands/codereview.md; context: fresh
          depends_on: [commit, testreview]
          trigger_rule: none_failed_min_one_success
          allowed_tools: []
          mcp: .archon/feature-pipeline-fence/codereview.json
          output_format: Review
  - id: result        # collector: the last iteration's Review
    depends_on: [steps]
```

```yaml
# First (the first field of before's output)
first: test | code | none   # test: a Spec step's `before` is the Plan's first step, or there is
                            # no Plan step and the Spec has one; code: the Plan has a first step and
                            # no Spec step precedes it; none: neither has a step. A missing approved
                            # file has no steps.

# Built (output_format of tests and implement)
step_id: string
design_gap: string | null

# TestReview (output_format of testreview)
verdict: pass | fix | stuck
findings: [{ cause, basis }]
fixed: [{ cause, basis }]

# Review (output_format of codereview): as in feature-pipeline-finish-design.md, plus
kind: test | code | null    # the kind of the step in `next`; null when next is null
```

- `commands/tests.md` holds no `$` reference and nothing from the lead or any other node, and the node loads no setting sources. The test writer reads `reviews/specs/approved/spec.json` and `tests/` and takes direction from the Spec alone. It builds the first test step in the Spec's `steps` order that has a line not yet written in its file as the line states, writes a test only from a line carrying file, shared, setup and assertion (a port line as in the preserved test) and a helper only from its `helpers` entry, and returns that step's id. A line it cannot build as written gets a `design_gap` and nothing written. It may call `run_tests` to see its tests fail or pass.
- `commands/implement.md` carries `$LOOP_PREV.codereview.output`. The implementer reads the Plan and Spec from `reviews/plans/approved/plan.json` and `reviews/specs/approved/spec.json`, builds the step named by `next` (on iteration 1, the Plan's first step), writes the code that serves the Spec lines whose `step` is that step, fixes each finding the review gives it, reverts each stray path it is named for, and returns the step's id. It may call `run_tests`.
- `commands/testreview.md` carries the writer's `step_id`, `check` and `commit` output and `$LOOP_PREV.codereview.output`. The test reviewer reads `reviews/specs/approved/spec.json` and `tests/` alone, checks the tests against their lines, and returns the test step's verdict, findings and fixed list.
- `commands/codereview.md` is today's `review.md`, naming the `files` tools, carrying `before`, the writer's output, `check`, `commit`, `$testreview.output` (`''` on a code step) and `$LOOP_PREV.codereview.output`, and reading the Plan and Spec from the approved files. On a test step it takes the step's verdict, findings and fixed list from `testreview` and judges no test itself; on every step it keeps the build order: `next`, `kind`, `remaining`, `done`, `stuck`, `design_gaps` and `stray`.
- `commands/write.md` and `commands/review.md` are removed.
- Test steps are built strictly in Spec order. The code reviewer sets `next` to a test step only when every earlier test step in Spec order has passed; once a test step is `stuck` or left unbuilt, no later test step is built this cycle, and no code step whose test step is unbuilt is built.
- A review `fix` on a test step reruns the test writer with no findings; it re-reads the Spec and its tests. A finding with the same cause and basis as one in `fixed` makes the step `stuck`. A stray path under `tests/`, or a `step_id` that differs from `next`, makes a test step `stuck` at once.
- The code reviewer checks each writer's `step_id` against `next` and the code against the lines that cite its step. A path under `reviews/` is never stray. Everything else in the build-loop module of `feature-pipeline-finish-design.md` holds as written there, with `write` read as whichever writer ran and `review` as `codereview`.

### `.archon/workflows/feature-pipeline/finish/`

A sync conflict is fixed by the resolver whose fence writes the conflicted path's folder. Four resolver nodes replace the one `resolve`, all `context: fresh`, `allowed_tools: []`, with `resolve`'s output format `{ resolved: boolean, reason: string }`.

```yaml
# finish.yaml, cycle body
- id: sync          # as today, plus four outputs splitting `paths`, one path per line:
                    # tests (under tests/), plans (under reviews/plans/findings/ and
                    # reviews/plans/approved/), specs (under reviews/specs/findings/ and
                    # reviews/specs/approved/), other (every conflicted path outside tests/ and reviews/);
                    # every other conflicted path under reviews/ takes the branch's side
                    # (git checkout --ours --) and is in none of the four
- id: resolvespecs  # commands/resolve-specs.md, carries $sync.output.specs
  depends_on: [sync]
  when: "$sync.output.specs != ''"
  allowed_tools: []
  mcp: .archon/feature-pipeline-fence/resolver-specs.json
- id: resolveplans  # commands/resolve-plans.md, carries $sync.output.plans
  depends_on: [sync]
  when: "$sync.output.plans != ''"
  allowed_tools: []
  mcp: .archon/feature-pipeline-fence/resolver-plans.json
- id: resolve       # commands/resolve.md, carries $sync.output.other
  depends_on: [sync]
  when: "$sync.output.other != ''"
  allowed_tools: []
  mcp: .archon/feature-pipeline-fence/resolver.json
- id: resolvetests  # test writer as resolver; commands/resolve-tests.md
  depends_on: [sync, resolvespecs]
  trigger_rule: none_failed_min_one_success
  when: "$sync.output.tests != ''"
  allowed_tools: []
  mcp: .archon/feature-pipeline-fence/resolver-tests.json
  settingSources: []
- id: merge         # as today, but resolved is true only when every resolver that ran
                    # returned resolved: true (a skipped one reads ''), and reason joins
                    # each resolver's reason
  depends_on: [sync, resolvetests, resolveplans, resolvespecs, resolve]
  trigger_rule: none_failed_min_one_success
  when: "$sync.output.conflicted == true"
- id: build         # include build-loop, no `with`
```

- `commands/resolve.md`, `commands/resolve-plans.md` and `commands/resolve-specs.md` are today's `resolve.md`, each listing its own `$sync.output.<folder>` paths, naming the `files` tools in place of `Read`, `Edit`, `Grep` and `Glob`, and resolving from the two sides and what its fence reads.
- `commands/resolve-tests.md` holds no `$` reference and nothing from the lead or any other node, and the node loads no setting sources. The resolver finds the conflicted files with the `files` `grep` for marker lines under `tests/`, resolves each block from the two sides and `reviews/specs/approved/` alone, and returns `resolved` and `reason` as `resolve` does. A block `reviews/specs/approved/` does not settle is left.
- `resolvetests` runs after `resolvespecs`, so it reads `reviews/specs/approved/` with its conflicts resolved.
- `unmerged` is unchanged: a marker left in any path, `.archon/`, `.claude/` and `.git/` included, ends the run through its cancel.
- `planning`'s `carry` names the previous plan-review result as verdict, question and findings.
- `commands/bail.md` reads the Plan, the Spec and their decisions from `reviews/plans/approved/plan.json` and `reviews/specs/approved/spec.json`.

### `.archon/workflows/feature-pipeline/feature/`

`feature` writes and commits `reviews/` through `plan-review`; the workflow drops `mutates_checkout: false` and its description says so.

```yaml
- id: gate          # as today, when: "$planned.output.approval != 'approved'"; attention names
                    # reviews/plans/approved/plan.json and reviews/specs/approved/spec.json and
                    # the open decisions in each, and prints neither
- id: approval      # bash: writes reviews/approval.json { design, state, text, plan, spec }
                    # (written to approval.json.tmp, then mv), then
                    # git commit -q -m "reviews: owner approval" -- reviews/approval.json
```

## Homes

| Concern | Home | Forbidden elsewhere |
|---|---|---|
| An agent's writes to the checkout | the node's fence config, served by `fence/files.py`, with `allowed_tools: []` (`[Agent]` on `plan` and `spec`) | Built-in `Edit`, `Write`, `NotebookEdit` or `Bash` on any node or sub-agent but `spec`'s `examiner`; a fence folder in a prompt, a YAML file or the launcher's environment; a folder in a config that the config table above does not name; a role writing `.archon/`, `.claude/` or `.git/`. |
| An agent's reads of the checkout, on a fenced node | the same config's `FENCE_READ` | Built-in `Read`, `Grep` or `Glob` on a fenced node or its sub-agents. |
| A writer's test runs | `fence/checks.py`'s `run_tests`, on the command in `TEST_COMMAND` | Built-in `Bash` on a writer; a test command in a prompt or config. |
| Locating the fence scripts | `PACK_DIR` in each config's `env`, read by `sh -c` with the `:?` guard | A pack path literal in a config, a YAML file or a prompt; a server started from the checkout. |
| Fence config location | `<workflow>/.archon/feature-pipeline-fence/<role>.json`, named by `mcp: .archon/feature-pipeline-fence/<role>.json` | A config path whose checkout match lies outside `.archon/`; a config file anywhere in the checkout; one config copied into two workflow folders; a `finish` resolver config whose `FENCE_*` differ from the role's row it carries. |
| Review documents | `reviews/` in the checkout, laid out as the `reviews/` module states | A Plan, Spec or finding in a node output, a node input or a prompt `$` reference; anything under `$STATE_DIR`; a plan record or its key. |
| Hand-off between nodes | agents return a verdict, a question or a step id only; `route` passes `next`, `resume` and `question`; everything else is read from `reviews/` | Any other agent output field but a writer's `design_gap` and the build-loop reviewers' outputs; `build-loop` inputs. |
| Approval copy | `copy_file` by the prosecutor into `reviews/plans/approved/` and by the arbiter into `reviews/specs/approved/` | Any other writer of an `approved/` folder; an approved file written with `write_file`. |
| Commits of `reviews/` | `plan-review`'s `reviews` node, one commit per approval with `Design`, `Design-Blob` and `Planning` trailers; `feature`'s `approval` for `reviews/approval.json` alone | `reviews/` staged by `build-loop`'s `commit` or any other node; `reviews/` left out of the branch. |
| Reuse, resume and stale reviews | `recall`, from `reviews/`, the last `reviews` commit's trailers and the newest findings file | A round counter, a record or a cache anywhere else; a node but `recall` deleting under `reviews/`. |
| The owner's answers and approval | `reviews/answers.json`, written by `recall`; `reviews/approval.json`, written by `feature`'s `approval` | An answer or approval kept anywhere else. |
| Pack code | the "Pack code" row of `feature-pipeline-finish-design.md`, plus `fence/files.py`, `fence/checks.py`, their tests, the twelve fence configs, the `mcp:` paths, `plan-review`'s `recall` and `reviews` as stated here, `cite.py` reading `reviews/plans/plan.json`, `build-loop`'s `before` with `first`, `sync`'s reviews split, and `feature`'s `approval` | Any other MCP server, script, config or bash job. |
| A step's check and committed paths | the step in `reviews/plans/approved/plan.json` or `reviews/specs/approved/spec.json`, found with `jq` by the writer's `step_id` in `check` and `commit` | A writer's output carrying a check or paths; `check` running any other command. |
| The test writers' direction | `reviews/specs/approved/`: for `tests`, its `spec.json`, written only by the arbiter's copy; for `resolvetests`, the folder as `resolvespecs` leaves it | A `$` reference, or anything from the lead or another node, in `commands/tests.md` or `commands/resolve-tests.md`; a setting source on `tests` or `resolvetests`; any file in `reviews/specs/approved/` but `spec.json` read by `tests`. |
| Which writer runs | `tests`' and `implement`'s `when:`, on `codereview`'s `kind` and, on iteration 1, `before`'s `first` | A writer choosing between test and code steps; a step kind decided anywhere else. |
| A test step's verdict | `testreview`, from `reviews/specs/approved/` and `tests/` | `codereview` judging a test; `testreview` reading code or the Plan. |
| Test-step order | the Spec's `steps` order, written by the specifier and checked by the arbiter | A test writer told which step to build; a test step built out of Spec order. |
| Writes outside a step | `codereview`, from `before` and `commit` status output, which exclude `reviews/` | A hook; a node that reverts on its own; a "did `tests/` change" check after a step; a path under `reviews/` named stray. |
| Sync conflicts under `reviews/` | `resolveplans` and `resolvespecs` for `findings/` and `approved/`; `sync` takes the branch's side for every other path under `reviews/` | A resolver given a path outside its folder; one resolver for every folder; a conflict under `tests/` fixed by any node but `resolvetests`. |
| Tests | `docs/testing.md`, binding every Python suite and workflow fixture this design produces | A test or fixture written to any other rule. |

## Order

1. `architect`: `docs/superpowers/specs/workflow-builder-design.md`: the roster stub's MCP-server line and the "Pack code" row admit `fence/files.py`, `fence/checks.py` and the fence configs as this design places them, pointed at `docs/superpowers/specs/writer-fence-design.md`.
2. `architect`: `docs/superpowers/specs/feature-pipeline-finish-design.md`: the Modules preamble (bash jobs, script files), the plan-review module (the hand-off of the Plan and Spec through files under `reviews/`, `recall`, `route`, `reviews`, `verdict`, `keep` removed, no plan record, `prosecute`, `arbitrate`, `spec` and examiner lines), the build-loop module, the finish module's `sync`, `resolve`, `merge`, `build` and `bail` lines, its sync-conflict paragraph and its `resolved` and `unresolved` fixture lines, the feature module's `gate` and `approval`, and the "Pack code", "Writes outside a step", "Hand-off between nodes" and "Checking the pack" rows, stated as this design holds them.
3. `role-author`: `~/.claude/agents/workflow-builder.md`: `mcp:` paths under `.archon/feature-pipeline-fence/` and the fence config files in each workflow folder admitted; `fence/` left unwritable.
4. `workflow-builder`: `.archon/workflows/feature-pipeline/plan-review/plan-review.yaml`, `.archon/workflows/feature-pipeline/plan-review/scripts/cite.py`, `.archon/workflows/feature-pipeline/plan-review/commands/brief.md`, `.archon/workflows/feature-pipeline/plan-review/commands/plan.md`, `.archon/workflows/feature-pipeline/plan-review/commands/prosecute.md`, `.archon/workflows/feature-pipeline/plan-review/commands/spec.md`, `.archon/workflows/feature-pipeline/plan-review/commands/arbitrate.md`, `.archon/workflows/feature-pipeline/plan-review/.archon/feature-pipeline-fence/planner.json`, `.archon/workflows/feature-pipeline/plan-review/.archon/feature-pipeline-fence/prosecutor.json`, `.archon/workflows/feature-pipeline/plan-review/.archon/feature-pipeline-fence/specifier.json`, `.archon/workflows/feature-pipeline/plan-review/.archon/feature-pipeline-fence/arbiter.json`, `.archon/workflows/feature-pipeline/plan-review/fixtures/*`: `recall`, `route`, `reviews` and `verdict` on `reviews/`, `keep` removed, the four speakers on their configs returning verdict and question only, `cite.py` in place, the Spec's test steps in build order checked by the arbiter; fixtures stubbing the new outputs, with a reused, a resumed and a stale-cleared route.
5. `workflow-builder`: `.archon/workflows/feature-pipeline/build-loop/build-loop.yaml`, `.archon/workflows/feature-pipeline/build-loop/commands/tests.md`, `.archon/workflows/feature-pipeline/build-loop/commands/implement.md`, `.archon/workflows/feature-pipeline/build-loop/commands/testreview.md`, `.archon/workflows/feature-pipeline/build-loop/commands/codereview.md`, `.archon/workflows/feature-pipeline/build-loop/commands/review.md` (removed), `.archon/workflows/feature-pipeline/build-loop/commands/write.md` (removed), `.archon/workflows/feature-pipeline/build-loop/.archon/feature-pipeline-fence/test-writer.json`, `.archon/workflows/feature-pipeline/build-loop/.archon/feature-pipeline-fence/implementer.json`, `.archon/workflows/feature-pipeline/build-loop/.archon/feature-pipeline-fence/testreview.json`, `.archon/workflows/feature-pipeline/build-loop/.archon/feature-pipeline-fence/codereview.json`, `.archon/workflows/feature-pipeline/build-loop/fixtures/*.stubs.yaml`: no inputs, `before` with `first`, the two writers, `check` and `commit` reading the step from the approved files, the two reviewers; every fixture stubbing `before`, `tests`, `implement`, `testreview` and `codereview` as it reaches them, with a fixture whose first step is a test step and one whose first step is a code step.
6. `workflow-builder`: `.archon/workflows/feature-pipeline/finish/finish.yaml`, `.archon/workflows/feature-pipeline/finish/commands/resolve.md`, `.archon/workflows/feature-pipeline/finish/commands/resolve-plans.md`, `.archon/workflows/feature-pipeline/finish/commands/resolve-specs.md`, `.archon/workflows/feature-pipeline/finish/commands/resolve-tests.md`, `.archon/workflows/feature-pipeline/finish/commands/bail.md`, `.archon/workflows/feature-pipeline/finish/.archon/feature-pipeline-fence/resolver.json`, `.archon/workflows/feature-pipeline/finish/.archon/feature-pipeline-fence/resolver-plans.json`, `.archon/workflows/feature-pipeline/finish/.archon/feature-pipeline-fence/resolver-specs.json`, `.archon/workflows/feature-pipeline/finish/.archon/feature-pipeline-fence/resolver-tests.json`, `.archon/workflows/feature-pipeline/finish/fixtures/*.stubs.yaml`: `sync`'s folder outputs and its branch-side `reviews/` paths, the four resolvers on their configs, `merge` over all four, `build` with no `with`, `bail` on the approved files; `resolved` stubs a conflict in `tests/` and one in another folder, each resolved by its own resolver; `unresolved` stubs `resolvetests` leaving a conflict; every fixture stubbing plan-review's new outputs.
7. `workflow-builder`: `.archon/workflows/feature-pipeline/feature/feature.yaml`, `.archon/workflows/feature-pipeline/feature/fixtures/*.stubs.yaml`: `gate` naming the approved files and skipping on `approval == 'approved'`, `approval` writing and committing `reviews/approval.json`, the workflow's `mutates_checkout: false` and description; fixtures stubbing plan-review's new outputs.

Each step's done-check is the "Checking the pack" home of `feature-pipeline-finish-design.md`.
