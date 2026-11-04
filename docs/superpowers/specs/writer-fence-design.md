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

Every review document lives under one folder per design in the checkout, one file per round. Each file is written once, when its node runs; nothing under `reviews/` is overwritten or deleted.

```text
reviews/<slug>/plans/<n>.json            plan round <n>: the Plan; written by the planner, cites resolved in place by cite
reviews/<slug>/plans/findings/<n>.json   the prosecutor's ruling on plan round <n>: { verdict, findings, question }
reviews/<slug>/plans/approved.json       the passed Plan; copied once by the prosecutor
reviews/<slug>/specs/<n>.json            spec round <n>: the Spec; written by the specifier from plans/approved.json only
reviews/<slug>/specs/findings/<n>.json   the arbiter's ruling on spec round <n>: { verdict, findings, question }
reviews/<slug>/specs/approved.json       the passed Spec; copied once by the arbiter
reviews/<slug>/answers/<n>.json          one owner answer: { question, text }; written by recall
reviews/<slug>/approvals/<n>.json        one owner answer at the gate: { state: approved|rejected, text, plan, spec };
                                         written by feature's approval
```

- `<slug>` is the design file's name without `.md`. The run's launcher exports it as `DESIGN_SLUG`, beside `PACK_DIR` and `TEST_COMMAND`; `recall` fails the run when `DESIGN_SLUG` is not the slug of its `design` input.
- `<n>` is three digits, zero-padded. A plan or spec round takes one above the highest round number in `plans/` and `specs/` together, so the two kinds share one count and the highest number is the newest round. A findings file takes the number of the round file it rules on. An answers or approvals file takes one above the highest number in its own folder.
- The newest round is the only one ever edited: the planner, the specifier and `cite` revise the round file of the round in progress, and `fence/files.py` refuses every write to a round file with a higher-numbered file beside it. A round file is never deleted.
- `approved.json` is written once, by `copy_file`, which refuses an existing destination. A plan round started while `plans/approved.json` exists, or a spec round while `specs/approved.json` exists, cannot pass: `recall` and `route` stop planning `blocked` before such a round runs, with a question naming the approved file.
- `plan` and `spec` in an approvals file are the `git hash-object` blobs of the two approved files the owner answered on, `absent` for a missing one.
- The tests-only route writes no Plan: `plans/` holds no round and nothing on that route reads it.
- Plan and Spec shapes are the `plan` and `spec` objects of today's `plan` and `spec` output formats.

### `.archon/workflows/feature-pipeline/fence/` (built)

Two stdio MCP servers, run by `uv run --script`, each started by Claude Code once per node from that node's config file. Both resolve every path against `CLAUDE_PROJECT_DIR`, which Claude Code sets to the run's checkout, and ignore the client's roots. Nothing in this design changes them.

```text
files.py   env: CLAUDE_PROJECT_DIR (required), FENCE_READ, FENCE_WRITE, FENCE_DENY, FENCE_ROUNDS
           (colon-separated folders relative to the root; "." is the whole root;
            FENCE_DENY bounds writes only)
           writes under .archon, .claude and .git are always refused
           round file: a file named \d+.json anywhere under a FENCE_ROUNDS folder;
                       write_file and edit_file on it raise PermissionError while a
                       numerically higher \d+.json sits in the same folder;
                       delete_file on it always raises PermissionError
           tools: read_file(path, offset=0, limit=2000), list_directory(path="."),
                  find_files(pattern, path="."), grep(regex, path=".", glob=None),
                  write_file(path, content), edit_file(path, old, new, replace_all=False),
                  copy_file(src, dst), delete_file(path)
           copy_file: read access on src, write access on dst; creates missing
                      destination folders; raises FileExistsError when dst exists
checks.py  env: CLAUDE_PROJECT_DIR, FENCE_TEST_COMMAND (required), FENCE_TEST_TIMEOUT (default 900)
           tools: run_tests() -> "exit=<n> timed_out=<bool> seconds=<n>" and the output tail
```

Replaces built-in `Read`, `Grep`, `Glob`, `Edit`, `Write` and `Bash` on every node below.

### Fence configs: `.archon/workflows/feature-pipeline/<workflow>/.archon/feature-pipeline-fence/<role>.json`

One MCP config file per fenced role, in the folder of the workflow that declares the node. A node names it as `mcp: .archon/feature-pipeline-fence/<role>.json`, so the node runs on `mcp__files__*` and `mcp__checks__*` and the built-in tools its `allowed_tools` lists, `[]` on every fenced node but `plan` and `spec`, which list `[Agent]`. Archon looks the path up in the checkout first, then in the declaring workflow's folder; the checkout match it could find is `<checkout>/.archon/feature-pipeline-fence/<role>.json`, under `.archon/`, which `files.py` refuses to every role.

Each server finds its script through `PACK_DIR`, the checks server its command through `TEST_COMMAND`, and the files server the design's review folder through `DESIGN_SLUG`. The run's launcher exports all three into Archon's environment (`PACK_DIR=/home/atom/dev/archon-workflows`, `TEST_COMMAND=<the target repository's single test command>`, `DESIGN_SLUG=<the design file's name without .md>`). Archon expands `${...}` only in `env`, so `command` and `args` read `PACK_DIR` and `DESIGN_SLUG` from the server's own environment, and the `:?` guards turn an unset `PACK_DIR` or `DESIGN_SLUG` (which Archon expands to `""` with a warning) into a start failure. An unset `TEST_COMMAND` leaves `FENCE_TEST_COMMAND` empty, and `checks.py` refuses to start.

```json
// the two server entries, shared by every config; <FENCE_*> per role below
"files": {
  "command": "sh",
  "args": ["-c", ": \"${PACK_DIR:?PACK_DIR unset}\" \"${DESIGN_SLUG:?DESIGN_SLUG unset}\"; exec uv run --script \"$PACK_DIR/.archon/workflows/feature-pipeline/fence/files.py\""],
  "env": { "PACK_DIR": "${PACK_DIR}", "DESIGN_SLUG": "${DESIGN_SLUG}", "FENCE_READ": "<read>", "FENCE_WRITE": "<write>", "FENCE_DENY": "<deny>", "FENCE_ROUNDS": "<rounds>" }
},
"checks": {
  "command": "sh",
  "args": ["-c", ": \"${PACK_DIR:?PACK_DIR unset}\"; exec uv run --script \"$PACK_DIR/.archon/workflows/feature-pipeline/fence/checks.py\""],
  "env": { "PACK_DIR": "${PACK_DIR}", "FENCE_TEST_COMMAND": "${TEST_COMMAND}" }
}
```

`R` in the table stands for the literal `reviews/${DESIGN_SLUG}`, which Archon expands in `env`. A folder entry may name a single file, such as `R/plans/approved.json`.

| Config file | Node | Servers | `FENCE_READ` | `FENCE_WRITE` | `FENCE_DENY` | `FENCE_ROUNDS` |
|---|---|---|---|---|---|---|
| `plan-review/.archon/feature-pipeline-fence/planner.json` | `plan` | files | `.` | `R/plans` | `R/plans/findings:R/plans/approved.json` | `reviews` |
| `plan-review/.archon/feature-pipeline-fence/prosecutor.json` | `prosecute` | files | `.` | `R/plans/findings:R/plans/approved.json` | `""` | `reviews` |
| `plan-review/.archon/feature-pipeline-fence/specifier.json` | `spec` | files | `.` | `R/specs` | `R/specs/findings:R/specs/approved.json` | `reviews` |
| `plan-review/.archon/feature-pipeline-fence/arbiter.json` | `arbitrate` | files | `R/specs:tests:R/plans/approved.json` | `R/specs/findings:R/specs/approved.json` | `""` | `reviews` |
| `build-loop/.archon/feature-pipeline-fence/test-writer.json` | `tests` | files, checks | `R/specs/approved.json:tests` | `tests` | `""` | `""` |
| `build-loop/.archon/feature-pipeline-fence/implementer.json` | `implement` | files, checks | `.` | `.` | `tests:reviews` | `""` |
| `build-loop/.archon/feature-pipeline-fence/testreview.json` | `testreview` | files | `R/specs/approved.json:tests` | `""` | `""` | `""` |
| `build-loop/.archon/feature-pipeline-fence/codereview.json` | `codereview` | files | `.` | `""` | `""` | `""` |
| `finish/.archon/feature-pipeline-fence/resolver-tests.json` | `resolvetests` | files | `R/specs/approved.json:tests` | `tests` | `""` | `""` |
| `finish/.archon/feature-pipeline-fence/resolver.json` | `resolve` | files | `.` | `.` | `tests:reviews` | `""` |

No other folder is named in any config. `.archon/`, `.claude/` and `.git/` are refused by `files.py` itself and appear in no config. Each `finish` resolver config carries the `FENCE_*` values of the role that writes its folder: `resolver-tests.json` the test writer's, `resolver.json` the implementer's.

Unmeasured, shown by the first live run: whether Claude Code passes `CLAUDE_PROJECT_DIR`, `PATH` and the rest of the environment the test command needs to a stdio server given an `env` block; whether a session resumed from `brief` starts the node's servers; whether an inline sub-agent reaches its node's MCP servers; whether the `examiner` keeps built-in tools its node's `allowed_tools` does not list.

### `.archon/workflows/feature-pipeline/plan-review/`

Each agent returns only its verdict and question; every Plan, Spec and finding is a file under `reviews/`.

```yaml
- id: recall        # bash; reads and writes reviews/$DESIGN_SLUG (no $STATE_DIR, no key)
  # fails when $DESIGN_SLUG is not the slug of the design input
  # reviews = reviews/$DESIGN_SLUG
  # design blob as today (checkout, else design_ref, else "absent")
  # last = newest commit touching $reviews (git log -1, default history
  #        simplification), with its Design, Design-Blob and Planning trailers
  # answer given: write { question: stopped.question, text: answer } to
  #        $reviews/answers/<n>.json; answers = every answers file, in number order
  # approval = the newest approvals file's state when its plan and spec blobs match
  #        the approved files, else none
  # newest = the highest-numbered findings file in plans/findings/ and specs/findings/
  # next: reuse when no resume, last's Design-Blob is this design's blob, last's Planning
  #        is done, `git status --porcelain -- $reviews` is empty and approval is not
  #        rejected; blocked when start's kind already has its approved.json; else rounds
  # start: resume's round when resume is given; else from newest: none -> plan; a plans
  #        file -> spec on pass, plan otherwise; a specs file -> plan on fail with a
  #        blocking finding whose author is plan, spec otherwise; plan whenever last's
  #        Planning is done
  # question: on blocked, names the approved.json that start's kind cannot pass again
  mutates_checkout: true
  output_format: { design, design_blob, reviews, read, from, root, branch, head,
                   next: rounds|reuse|blocked, start: plan|spec, question, answers,
                   approval: approved|rejected|none }
- id: plan          # commands/plan.md; writes the round file $reviews/plans/<n>.json
  allowed_tools: [Agent]
  mcp: .archon/feature-pipeline-fence/planner.json
  agents:
    detective:
      tools: [mcp__files__read_file, mcp__files__list_directory, mcp__files__find_files, mcp__files__grep]
  output_format: { question: string }
- id: cite          # script cite.py: reads the newest round file in $reviews/plans/, resolves
                    # each cite, edits that file in place (<n>.json.tmp, then mv); outputs { unresolved }
- id: prosecute     # commands/prosecute.md, carries $cite.output.unresolved; writes
                    # $reviews/plans/findings/<n>.json for the newest plan round, unresolved cites
                    # as minor findings; on pass,
                    # copy_file($reviews/plans/<n>.json, $reviews/plans/approved.json)
  allowed_tools: []
  mcp: .archon/feature-pipeline-fence/prosecutor.json
  output_format: { verdict: pass|fail|refused|blocked, question: string }
- id: spec          # commands/spec.md; writes the round file $reviews/specs/<n>.json from
                    # $reviews/plans/approved.json (no Plan on the tests-only route)
  allowed_tools: [Agent]
  mcp: .archon/feature-pipeline-fence/specifier.json
  sandbox: # as today
  agents:
    examiner:
      tools: [Bash, Write, Edit, mcp__files__read_file, mcp__files__list_directory, mcp__files__find_files, mcp__files__grep]
  output_format: { question: string }
- id: arbitrate     # commands/arbitrate.md; writes $reviews/specs/findings/<n>.json for the
                    # newest spec round; on pass,
                    # copy_file($reviews/specs/<n>.json, $reviews/specs/approved.json)
  allowed_tools: []
  mcp: .archon/feature-pipeline-fence/arbiter.json
  output_format: { verdict: pass|fail|refused|blocked, question: string }
- id: route         # bash: next from the verdict that ruled this round, as today; reads the
                    # arbiter's findings file with jq for a blocking plan finding; next is
                    # blocked, with a question naming the approved file, when the next round's
                    # kind already has its approved.json
  output_format: { next: plan|spec|done|refused|blocked, resume: plan|spec|null, question: string }
- id: reviews       # bash, when route's next is spec or done:
                    # git add -A -- $reviews; git commit -q -m "reviews: <plan|spec> approved"
                    #   --trailer "Design: <design>" --trailer "Design-Blob: <blob>"
                    #   --trailer "Planning: <spec|done>" -- $reviews
  depends_on: [route]
- id: verdict       # verdict, question, stopped (route's output plus answers, when blocked;
                    # recall's question when recall's next is blocked), recalled, reviews and
                    # approval (recall's), findings (the newest findings file's, [] on reuse)
```

`keep` is removed. `plan`, `cite`, `spec` and `route` lose their Plan and Spec fields; `route`'s `plan`, `spec` and `findings` fields go. Every node in the block drops `mutates_checkout: false` but `track` and `brief`. `rounds` is skipped when recall's `next` is `reuse` or `blocked`.

- Every command in the block carries `$recall.output.reviews` as the design's review folder.
- `commands/brief.md` carries no plan record and no seed Plan or Spec: the Plan and Spec to start from are the newest round files in `plans/` and `specs/` as they stand, the owner's word on them is `$recall.output.approval`, and the owner's answers are `$recall.output.answers`.
- `commands/plan.md` and `commands/spec.md` take a round's number as one above the highest round number in `plans/` and `specs/` together, write a new round file with `write_file` when every round file has its findings file, and otherwise revise the round in progress, the one round file without one. Each returns only `question`; the detective reads through the `files` tools.
- `commands/prosecute.md` and `commands/arbitrate.md` name the `files` tools in place of `Read`, `Grep` and `Glob`, rule on the newest round file of their kind, write the findings file of that number, copy the passed round file to `approved.json` with `copy_file`, and return only `verdict` and `question`. `arbitrate.md` states that the arbiter reads only `specs/`, `tests/` and `plans/approved.json` and holds the design from `brief`.
- `commands/spec.md` reads the Plan from `plans/approved.json` alone and may read source. It writes the Spec's test steps in build order: in the Plan order of the code step each step's `before` names, steps with `before` null last. `commands/arbitrate.md` adds that order to its cross-check, as a `field: order` finding.
- The examiner writes only its scratch copy under `$ARTIFACTS_DIR/.archon/scratch/spec/`.
- `scripts/cite.py` reads the newest round file in `reviews/$DESIGN_SLUG/plans/` under the working directory, edits it in place and prints `{"unresolved": [...]}`; it takes no `INPUTS_PLAN`.

### `.archon/workflows/feature-pipeline/build-loop/`

The `write` node becomes two writers, `tests` for test steps and `implement` for code steps. `review` becomes `testreview`, on test steps, and `codereview`, on every step. The workflow, not a writer, holds each step's check and paths, read from the approved files.

```yaml
# build-loop.yaml (include block)
inputs: {}
returns: result

nodes:
  - id: before        # bash: { status: git status --porcelain -- . ':(exclude)reviews',
                      #         first, reviews: reviews/$DESIGN_SLUG } from the approved files with jq
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
                          # writer reads ''); jq finds that step in $reviews/plans/approved.json or
                          # $reviews/specs/approved.json and runs its `check` with bash -c;
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

- `commands/tests.md` holds no `$` reference and nothing from the lead or any other node, and the node loads no setting sources. The test writer reads the one `reviews/*/specs/approved.json` its fence shows, found with `find_files`, and `tests/`, and takes direction from the Spec alone. It builds the first test step in the Spec's `steps` order that has a line not yet written in its file as the line states, writes a test only from a line carrying file, shared, setup and assertion (a port line as in the preserved test) and a helper only from its `helpers` entry, and returns that step's id. A line it cannot build as written gets a `design_gap` and nothing written. It may call `run_tests` to see its tests fail or pass.
- `commands/implement.md` carries `$before.output.reviews` and `$LOOP_PREV.codereview.output`. The implementer reads the Plan and Spec from `plans/approved.json` and `specs/approved.json` in that folder, builds the step named by `next` (on iteration 1, the Plan's first step), writes the code that serves the Spec lines whose `step` is that step, fixes each finding the review gives it, reverts each stray path it is named for, and returns the step's id. It may call `run_tests`.
- `commands/testreview.md` carries the writer's `step_id`, `check` and `commit` output and `$LOOP_PREV.codereview.output`. The test reviewer reads the one `reviews/*/specs/approved.json` its fence shows and `tests/` alone, checks the tests against their lines, and returns the test step's verdict, findings and fixed list.
- `commands/codereview.md` is today's `review.md`, naming the `files` tools, carrying `before` (its `reviews` folder included), the writer's output, `check`, `commit`, `$testreview.output` (`''` on a code step) and `$LOOP_PREV.codereview.output`, and reading the Plan and Spec from the approved files. On a test step it takes the step's verdict, findings and fixed list from `testreview` and judges no test itself; on every step it keeps the build order: `next`, `kind`, `remaining`, `done`, `stuck`, `design_gaps` and `stray`.
- `commands/write.md` and `commands/review.md` are removed.
- Test steps are built strictly in Spec order. The code reviewer sets `next` to a test step only when every earlier test step in Spec order has passed; once a test step is `stuck` or left unbuilt, no later test step is built this cycle, and no code step whose test step is unbuilt is built.
- A review `fix` on a test step reruns the test writer with no findings; it re-reads the Spec and its tests. A finding with the same cause and basis as one in `fixed` makes the step `stuck`. A stray path under `tests/`, or a `step_id` that differs from `next`, makes a test step `stuck` at once.
- The code reviewer checks each writer's `step_id` against `next` and the code against the lines that cite its step. A path under `reviews/` is never stray. Everything else in the build-loop module of `feature-pipeline-finish-design.md` holds as written there, with `write` read as whichever writer ran and `review` as `codereview`.

### `.archon/workflows/feature-pipeline/finish/`

A sync conflict is fixed by the resolver whose fence writes the conflicted path's folder. Two resolver nodes, `resolve` and `resolvetests`, replace today's one `resolve`, both `context: fresh`, `allowed_tools: []`, with `resolve`'s output format `{ resolved: boolean, reason: string }`. No resolver writes under `reviews/`: every conflicted path there takes the branch's side, so no round file or approved file is rewritten.

```yaml
# finish.yaml, cycle body
- id: sync          # as today, plus two outputs splitting `paths`, one path per line:
                    # tests (under tests/), other (every conflicted path outside tests/ and reviews/);
                    # every conflicted path under reviews/ takes the branch's side
                    # (git checkout --ours --) and is in neither
- id: resolve       # commands/resolve.md, carries $sync.output.other
  depends_on: [sync]
  when: "$sync.output.other != ''"
  allowed_tools: []
  mcp: .archon/feature-pipeline-fence/resolver.json
- id: resolvetests  # test writer as resolver; commands/resolve-tests.md
  depends_on: [sync]
  when: "$sync.output.tests != ''"
  allowed_tools: []
  mcp: .archon/feature-pipeline-fence/resolver-tests.json
  settingSources: []
- id: merge         # as today, but resolved is true only when every resolver that ran
                    # returned resolved: true (a skipped one reads ''), and reason joins
                    # each resolver's reason
  depends_on: [sync, resolvetests, resolve]
  trigger_rule: none_failed_min_one_success
  when: "$sync.output.conflicted == true"
- id: build         # include build-loop, no `with`
```

- `commands/resolve.md` is today's `resolve.md`, listing `$sync.output.other`, naming the `files` tools in place of `Read`, `Edit`, `Grep` and `Glob`, and resolving from the two sides and what its fence reads.
- `commands/resolve-tests.md` holds no `$` reference and nothing from the lead or any other node, and the node loads no setting sources. The resolver finds the conflicted files with the `files` `grep` for marker lines under `tests/`, resolves each block from the two sides and the one `reviews/*/specs/approved.json` its fence shows alone, and returns `resolved` and `reason` as `resolve` does. A block that file does not settle is left.
- `unmerged` is unchanged: a marker left in any path, `.archon/`, `.claude/` and `.git/` included, ends the run through its cancel.
- `planning`'s `carry` names the previous plan-review result as verdict, question and findings.
- `commands/bail.md` carries `$planning.output.reviews` and reads the Plan, the Spec and their decisions from `plans/approved.json` and `specs/approved.json` in that folder.

### `.archon/workflows/feature-pipeline/feature/`

`feature` writes and commits `reviews/` through `plan-review`; the workflow drops `mutates_checkout: false` and its description says so.

```yaml
- id: gate          # as today, when: "$planned.output.approval != 'approved'"; attention names
                    # $planned.output.reviews/plans/approved.json and .../specs/approved.json and
                    # the open decisions in each, and prints neither
- id: approval      # bash: writes reviews/$DESIGN_SLUG/approvals/<n>.json { state, text, plan, spec },
                    # <n> one above the highest in that folder (written to <n>.json.tmp, then mv),
                    # then git commit -q -m "reviews: owner approval" -- that file
```

## Homes

| Concern | Home | Forbidden elsewhere |
|---|---|---|
| An agent's writes to the checkout | the node's fence config, served by `fence/files.py`, with `allowed_tools: []` (`[Agent]` on `plan` and `spec`) | Built-in `Edit`, `Write`, `NotebookEdit` or `Bash` on any node or sub-agent but `spec`'s `examiner`; a fence folder in a prompt, a YAML file or the launcher's environment; a folder in a config that the config table above does not name; a role writing `.archon/`, `.claude/` or `.git/`. |
| An agent's reads of the checkout, on a fenced node | the same config's `FENCE_READ` | Built-in `Read`, `Grep` or `Glob` on a fenced node or its sub-agents. |
| A writer's test runs | `fence/checks.py`'s `run_tests`, on the command in `TEST_COMMAND` | Built-in `Bash` on a writer; a test command in a prompt or config. |
| Locating the fence scripts | `PACK_DIR` in each config's `env`, read by `sh -c` with the `:?` guard | A pack path literal in a config, a YAML file or a prompt; a server started from the checkout. |
| Fence config location | `<workflow>/.archon/feature-pipeline-fence/<role>.json`, named by `mcp: .archon/feature-pipeline-fence/<role>.json` | A config path whose checkout match lies outside `.archon/`; a config file anywhere in the checkout; one config copied into two workflow folders; a `finish` resolver config whose `FENCE_*` differ from the role's row it carries. |
| Review documents | `reviews/<slug>/` in the checkout, one file per round, laid out as the `reviews/` module states | A Plan, Spec or finding in a node output, a node input or a prompt `$` reference; anything under `$STATE_DIR`; a plan record or its key; one file holding two rounds. |
| The design's review folder | `DESIGN_SLUG`, exported by the launcher; `recall`'s `reviews` output in plan-review prompts, `before`'s in build-loop prompts, `verdict`'s outside plan-review; `reviews/${DESIGN_SLUG}` in fence configs | A slug computed anywhere else; a review folder literal in a prompt, a YAML file or a config. |
| Never overwriting a review | `FENCE_ROUNDS=reviews` on the planner, prosecutor, specifier and arbiter configs, `copy_file`'s refusal of an existing `dst`, and bash writing each answers and approvals file once under a new number | An edit to a round file with a higher-numbered one beside it; a deleted, moved or rewritten file under `reviews/` but the newest round's; `cite` editing any round but the newest; a resolver writing under `reviews/`. |
| Hand-off between nodes | agents return a verdict, a question or a step id only; `route` passes `next`, `resume` and `question`; everything else is read from `reviews/<slug>/` | Any other agent output field but a writer's `design_gap` and the build-loop reviewers' outputs; `build-loop` inputs. |
| Approval copy | `copy_file`, once, by the prosecutor to `reviews/<slug>/plans/approved.json` and by the arbiter to `reviews/<slug>/specs/approved.json` | Any other writer of an `approved.json`; an approved file written with `write_file` or `edit_file`; a round of a kind started while that kind's `approved.json` exists. |
| Commits of `reviews/` | `plan-review`'s `reviews` node, one commit of `reviews/<slug>/` per approval with `Design`, `Design-Blob` and `Planning` trailers; `feature`'s `approval` for its own approvals file alone | `reviews/` staged by `build-loop`'s `commit` or any other node; `reviews/` left out of the branch. |
| Reuse and resume | `recall`, from `reviews/<slug>/`, the last `reviews` commit's trailers and the newest round numbers | A round counter, a record or a cache anywhere else; any node deleting under `reviews/`. |
| The owner's answers and approval | `reviews/<slug>/answers/<n>.json`, written by `recall`; `reviews/<slug>/approvals/<n>.json`, written by `feature`'s `approval`; one file per answer, never rewritten | An answer or approval kept anywhere else. |
| Pack code | the "Pack code" row of `feature-pipeline-finish-design.md`, plus `fence/files.py`, `fence/checks.py`, their tests, the ten fence configs, the `mcp:` paths, `plan-review`'s `recall` and `reviews` as stated here, `cite.py` editing the newest plan round, `build-loop`'s `before` with `first` and `reviews`, `sync`'s reviews split, and `feature`'s `approval` | Any other MCP server, script, config or bash job. |
| A step's check and committed paths | the step in `reviews/<slug>/plans/approved.json` or `reviews/<slug>/specs/approved.json`, found with `jq` by the writer's `step_id` in `check` and `commit` | A writer's output carrying a check or paths; `check` running any other command. |
| The test writers' direction | `reviews/<slug>/specs/approved.json`, written only by the arbiter's copy and, for `resolvetests`, as `sync` leaves it | A `$` reference, or anything from the lead or another node, in `commands/tests.md` or `commands/resolve-tests.md`; a setting source on `tests` or `resolvetests`; any file under `reviews/` but that one read by `tests` or `resolvetests`. |
| Which writer runs | `tests`' and `implement`'s `when:`, on `codereview`'s `kind` and, on iteration 1, `before`'s `first` | A writer choosing between test and code steps; a step kind decided anywhere else. |
| A test step's verdict | `testreview`, from `reviews/<slug>/specs/approved.json` and `tests/` | `codereview` judging a test; `testreview` reading code or the Plan. |
| Test-step order | the Spec's `steps` order, written by the specifier and checked by the arbiter | A test writer told which step to build; a test step built out of Spec order. |
| Writes outside a step | `codereview`, from `before` and `commit` status output, which exclude `reviews/` | A hook; a node that reverts on its own; a "did `tests/` change" check after a step; a path under `reviews/` named stray. |
| Sync conflicts under `reviews/` | `sync`, taking the branch's side for every path under `reviews/` | A resolver given a path under `reviews/` or outside its folder; one resolver for every folder; a conflict under `tests/` fixed by any node but `resolvetests`. |
| Tests | `docs/testing.md`, binding every Python suite and workflow fixture this design produces | A test or fixture written to any other rule. |

## Order

1. `architect`: `docs/superpowers/specs/workflow-builder-design.md`: the roster stub's MCP-server line and the "Pack code" row admit `fence/files.py`, `fence/checks.py` and the fence configs as this design places them, pointed at `docs/superpowers/specs/writer-fence-design.md`.
2. `architect`: `docs/superpowers/specs/feature-pipeline-finish-design.md`: the Modules preamble (bash jobs, script files), the plan-review module (the hand-off of the Plan and Spec through files under `reviews/`, `recall`, `route`, `reviews`, `verdict`, `keep` removed, no plan record, `prosecute`, `arbitrate`, `spec` and examiner lines), the build-loop module, the finish module's `sync`, `resolve`, `merge`, `build` and `bail` lines, its sync-conflict paragraph and its `resolved` and `unresolved` fixture lines, the feature module's `gate` and `approval`, and the "Pack code", "Writes outside a step", "Hand-off between nodes" and "Checking the pack" rows, stated as this design holds them.
3. `role-author`: `~/.claude/agents/workflow-builder.md`: `mcp:` paths under `.archon/feature-pipeline-fence/` and the fence config files in each workflow folder admitted; `fence/` left unwritable.
4. `workflow-builder`: `.archon/workflows/feature-pipeline/plan-review/plan-review.yaml`, `.archon/workflows/feature-pipeline/plan-review/scripts/cite.py`, `.archon/workflows/feature-pipeline/plan-review/commands/brief.md`, `.archon/workflows/feature-pipeline/plan-review/commands/plan.md`, `.archon/workflows/feature-pipeline/plan-review/commands/prosecute.md`, `.archon/workflows/feature-pipeline/plan-review/commands/spec.md`, `.archon/workflows/feature-pipeline/plan-review/commands/arbitrate.md`, `.archon/workflows/feature-pipeline/plan-review/.archon/feature-pipeline-fence/planner.json`, `.archon/workflows/feature-pipeline/plan-review/.archon/feature-pipeline-fence/prosecutor.json`, `.archon/workflows/feature-pipeline/plan-review/.archon/feature-pipeline-fence/specifier.json`, `.archon/workflows/feature-pipeline/plan-review/.archon/feature-pipeline-fence/arbiter.json`, `.archon/workflows/feature-pipeline/plan-review/fixtures/*`: `recall`, `route`, `reviews` and `verdict` on `reviews/<slug>/` round files, `keep` removed, the four speakers on their configs with `FENCE_ROUNDS=reviews` returning verdict and question only, `cite.py` editing the newest plan round in place, the Spec's test steps in build order checked by the arbiter; fixtures stubbing the new outputs, with a reused, a resumed and an approved-file-blocked route.
5. `workflow-builder`: `.archon/workflows/feature-pipeline/build-loop/build-loop.yaml`, `.archon/workflows/feature-pipeline/build-loop/commands/tests.md`, `.archon/workflows/feature-pipeline/build-loop/commands/implement.md`, `.archon/workflows/feature-pipeline/build-loop/commands/testreview.md`, `.archon/workflows/feature-pipeline/build-loop/commands/codereview.md`, `.archon/workflows/feature-pipeline/build-loop/commands/review.md` (removed), `.archon/workflows/feature-pipeline/build-loop/commands/write.md` (removed), `.archon/workflows/feature-pipeline/build-loop/.archon/feature-pipeline-fence/test-writer.json`, `.archon/workflows/feature-pipeline/build-loop/.archon/feature-pipeline-fence/implementer.json`, `.archon/workflows/feature-pipeline/build-loop/.archon/feature-pipeline-fence/testreview.json`, `.archon/workflows/feature-pipeline/build-loop/.archon/feature-pipeline-fence/codereview.json`, `.archon/workflows/feature-pipeline/build-loop/fixtures/*.stubs.yaml`: no inputs, `before` with `first`, the two writers, `check` and `commit` reading the step from the approved files, the two reviewers; every fixture stubbing `before`, `tests`, `implement`, `testreview` and `codereview` as it reaches them, with a fixture whose first step is a test step and one whose first step is a code step.
6. `workflow-builder`: `.archon/workflows/feature-pipeline/finish/finish.yaml`, `.archon/workflows/feature-pipeline/finish/commands/resolve.md`, `.archon/workflows/feature-pipeline/finish/commands/resolve-tests.md`, `.archon/workflows/feature-pipeline/finish/commands/bail.md`, `.archon/workflows/feature-pipeline/finish/.archon/feature-pipeline-fence/resolver.json`, `.archon/workflows/feature-pipeline/finish/.archon/feature-pipeline-fence/resolver-tests.json`, `.archon/workflows/feature-pipeline/finish/fixtures/*.stubs.yaml`: `sync`'s two folder outputs and its branch-side `reviews/` paths, the two resolvers on their configs, `merge` over both, `build` with no `with`, `bail` on the approved files; `resolved` stubs a conflict in `tests/` and one in another folder, each resolved by its own resolver; `unresolved` stubs `resolvetests` leaving a conflict; every fixture stubbing plan-review's new outputs.
7. `workflow-builder`: `.archon/workflows/feature-pipeline/feature/feature.yaml`, `.archon/workflows/feature-pipeline/feature/fixtures/*.stubs.yaml`: `gate` naming the approved files and skipping on `approval == 'approved'`, `approval` writing and committing a new `reviews/<slug>/approvals/<n>.json`, the workflow's `mutates_checkout: false` and description; fixtures stubbing plan-review's new outputs.

Each step's done-check is the "Checking the pack" home of `feature-pipeline-finish-design.md`.

## Decisions for the owner

1. **A second approval of the same design.** With one `approved.json` per kind written once, every review that must pass a kind a second time stops planning `blocked` for the owner: a spec round's blocking finding against the Plan (the ordinary plan-spec bounce), an owner rejection at the gate, a design edited after approval, and a later `finish` cycle that replans stuck steps. The design as written holds this.
   - Recommend: the approved copy is per passing round, `plans/approved/<n>.json` and `specs/approved/<n>.json` under `FENCE_ROUNDS`, the highest number in force, each written once by `copy_file`; fence configs name the `approved/` folders. Cost: readers and `check`/`commit` take the newest file in a folder instead of one fixed path.
   - Alternative: keep one `approved.json` per kind. Cost: each case above stops the run for the owner, and clearing it needs a new design name or a hand edit under `reviews/`.
