Status: approved.

## Why

HQPTuner's rebuild-integrate refactor has four steps left: 12a, 12b, 12c and 13 (`hqptuner2/docs/superpowers/specs/rebuild-integrate-design.md:122-129`; every `hqptuner2/` path is under `/home/atom/dev/hqptuner2`, and the design file is read from the integrate worktree, where it is untracked). This pack carries them to the end unattended in `/home/atom/dev/hqptuner2/.claude/worktrees/integrate` on `rebuild/integrate`, landing on `v2`. It is built from Archon's own nodes. The pack holds no Python module, no `.shared/` code, no MCP server and no install script.

Copies and stand-ins the tree holds today:

- **A Python core standing in for Archon features, 10 modules.** `docs/superpowers/specs/rebuild-finish-workflow-design.md:20-206` proposes `.shared/trees.py`, `record.py`, `stoprule.py`, `harness.py`, `run_tests_mcp.py`, `section.py`, `cutcheck.py`, `fence.py`, `target.py` and `install.py`. Each has a native counterpart: the live checkout through `--no-worktree` (`docs/reference/archon/cli.md:290`, `docs/reference/archon/worktrees.md:24`); a ledger in `archon state` (`workflow-language.md:1416-1508`); a terminal attention `wait` in a loop body (`workflow-language.md:773`, `docs/reference/archon/approval-nodes.md:152-181`); `bash:` nodes for gates, with their output read by the next iteration (`workflow-language.md:559`, `:497-501`); `$node.execution.checkoutStart` for the start commit (`workflow-language.md:1222-1256`); a review agent in the loop for the plan check; `--config` with `env:` for target facts (`cli.md:295`); and `--workflow-source` for loading the pack (`cli.md:284`, `:351-370`). That file is replaced by this one.
- **Gate invocation, 3 forms.** `PYTHONPATH=$(pwd) scripts/gate.sh make check` in a worktree (`hqptuner2/CLAUDE.md:57`, `:74`), the JS check written out by hand (`hqptuner2/docs/queue.md:344`), and the core target's bare `make check` (`rebuild-finish-workflow-design.md:9`).
- **Progress record, none usable.** The queue marks only `landed 7` and `landed 11` (`hqptuner2/docs/queue.md:3-4`), has no section for 12a to 13, and keeps its baseline log under `/tmp` (`:344`).
- **The pack's discovery scope.** The pack sits in this repository's `.archon/workflows/feature-pipeline/`, a discovery scope: `archon workflow test feature-pipeline` run from the repository root finds and passes its fixtures (`docs/host-facts.md:25`). `--workflow-source <path>` reads `<path>/.archon/workflows` (`cli.md:284`).

Archon gaps this design builds around (`docs/host-facts.md:8-10`): the sandbox fences Bash only and refuses to start without `socat`, which is absent, so no agent node gets Bash; Read, Edit and Write are unfenced, so a `bash:` node checks each writer's paths after it runs; there is no per-node `cwd`, so the whole run sits in the integrate worktree; there is no commit node, so commits are `bash:` nodes running `git commit` with pre-commit unbypassed.

Facts of the target: `rebuild/integrate` is 114 commits ahead of `v2` and `v2` is 2 ahead; `v2` is checked out at `/home/atom/dev/hqptuner2`. The integrate worktree's 12a work in progress is committed; its tree holds only the untracked `uv.lock` and an untracked `docs/superpowers/specs/rebuild-integrate-design.md` that `v2` also tracks. `make check` is `lint lint-js test test-js` (`hqptuner2/.claude/worktrees/integrate/Makefile:144`); the JS suite is `node --import ./tests/js/support/vendor-resolve.js --test ...` (`Makefile:135-142`). Pre-commit runs every gate except the JS suite (`hqptuner2/CLAUDE.md:56`). Decision 1 of the rebuild-integrate design is settled as `address_found: null` (`rebuild-integrate-design.md:131-133`).

## Modules

Every workflow folder sits under `.archon/workflows/feature-pipeline/` in this repository and holds its YAML, `commands/` and `fixtures/` (`workflow-language.md:48`). No folder holds `scripts/`. Every agent node names `provider: claude` and a literal model (`docs/host-facts.md:20`). Every agent's `allowed_tools` omits Bash.

**`targets/hqptuner-finish.yaml`**: the one home of target facts, an Archon `--config` layer (`cli.md:295`). Every node reads them as environment variables.

```yaml
env:
  HQP_MAIN: /home/atom/dev/hqptuner2                 # checkout holding v2
  HQP_BRANCH: rebuild/integrate
  HQP_LAND: v2
  HQP_DESIGN: docs/superpowers/specs/rebuild-integrate-design.md
  HQP_GATE_FULL: make check
  HQP_GATE_SECTION: node --import ./tests/js/support/vendor-resolve.js --test
  HQP_NEVER_COMMIT: "uv.lock CHANGELOG.md"           # pathspecs never staged
  HQP_LEDGER: rebuild-finish/hqptuner                # archon state document
```

**`finish-gate/`**: the one gate invocation, an `include:` block (`workflow-language.md:96`). It always exits 0 and prints `gate.sh`'s own `exit=<rc> log=<path>` line, so a red gate feeds the next node instead of failing the run.

```yaml
name: finish-gate
inputs:
  files: { type: string, default: "" }   # space-separated test files; empty runs HQP_GATE_FULL
nodes:
  - id: run
    bash: |
      # one line: CLAUDE_SCRATCH=$ARTIFACTS_DIR PYTHONPATH=$PWD scripts/gate.sh
      #   ${files:+$HQP_GATE_SECTION $files} or $HQP_GATE_FULL; then `|| true`
```

**`finish-commit/`**: the one commit, an `include:` block. It stages only the given paths minus `HQP_NEVER_COMMIT` and runs `git commit`, so pre-commit runs. It fails the node on a pre-commit failure.

```yaml
name: finish-commit
inputs:
  paths:   { type: string }   # space-separated
  message: { type: string }
nodes:
  - id: commit
    bash: |
      # git add -- $paths ':!'<each HQP_NEVER_COMMIT> && git commit -m "$message"
      # prints the new HEAD; then appends {event: landed, message, commit} to HQP_LEDGER
```

**`finish-item/`**: one plan item to a commit, the `fan_out` child (`workflow-language.md:2237-2300`). It runs one writer in a loop until its section is green, its fence is clean and its audit has no findings.

```yaml
name: finish-item
inputs:
  id:      { type: string }
  route:   { type: string }   # repair | fixture | red_then_build | contract | port
  paths:   { type: string }   # space-separated files the item may write
  tests:   { type: string }   # space-separated test files that make its section
  spec:    { type: string }   # what to change, with the claims it keeps and their quotes
  message: { type: string }   # commit message
returns:
  status:  { type: string }   # landed | baseline_red | blocked
  commit:  { type: string }
  ask:     { type: string }   # a product question a writer met, else ""
nodes:
  - id: pre          # include finish-gate, files: tests; route port only
  - id: hold         # bash; route port with pre red: return status baseline_red, run nothing else
  - id: red          # loop_group, route red_then_build only, until the section is red on an
                     #   assertion (`ERR_ASSERTION` in the gate log), never on an import or syntax error
    body: [write-red (sonnet, Read Grep Glob Edit Write), fence, check]
  - id: pin          # bash, route red_then_build: records `git hash-object` of tests
  - id: work         # loop_group, max_iterations 4, until: check `exit=0`, fence empty, audit 0
    body:
      - write        # sonnet, Read Grep Glob Edit Write; mode = route; reads $LOOP_PREV.check,
                     #   $LOOP_PREV.fence and $LOOP_PREV.audit; status blocked + ask on a product question
      - fence        # bash: `git status --porcelain -- . ':!<each path>' ':!<each HQP_NEVER_COMMIT>'`
                     #   against the dirty manifest of $write.execution.checkoutStart; for
                     #   red_then_build also fails on any change to the pinned test hashes
      - check        # include finish-gate, files: tests
      - audit        # opus, Read Grep Glob, fresh: {count, findings[{path, line,
                     #   kind: skip|relaxed_assertion|compat_reader|claim_changed|copy|exemption, text}]}
  - id: land         # include finish-commit, paths, message; when work ended green
```

Writer modes: `repair` changes test machinery and keeps every claim and assertion; `fixture` writes one shared fixture or builder the plan lists before its users; `red_then_build` writes the failing test in `red`, then fixes the production defect in `work` with the test held; `contract` changes a claim only as the spec's quotes establish; `port` moves one site set onto the approved interface after `pre` is green.

**`finish/`**: the job. It runs in the integrate worktree, merges `v2` in first, loops 12a, 12b and 12c until `make check` is green with no retired shape left, then fast-forwards `v2` with no pause before `land`, a production fix under `hqptuner/static/` included (`hqptuner2/CLAUDE.md:37`).

```yaml
name: finish
worktree: { enabled: false }
nodes:
  - id: ledger       # bash: `archon state put $HQP_LEDGER --if-revision 0 '[]'`, an existing document kept
  - id: merge-v2     # loop_group, max_iterations 4, until no unmerged path and MERGE_HEAD gone
    body:
      - merge        # bash: removes the untracked HQP_DESIGN copy only when `git show $HQP_LAND:$HQP_DESIGN`
                     #   is byte-identical; `git merge --no-edit $HQP_LAND` with conflicts left in place;
                     #   prints the unmerged paths
      - resolve      # opus, Read Grep Glob Edit Write; when unmerged paths exist; edits only conflict hunks
      - seal         # include finish-commit with the unmerged paths, when a merge is in progress
  - id: rebuild      # loop_group, max_iterations 12, until plan phase == done and gate `exit=0`
    body:
      - gate         # include finish-gate, files "" (full make check); the 12a reproduction and 12c check
      - read-ledger  # bash: `archon state get $HQP_LEDGER`
      - plan         # opus, Read Grep Glob; reads HQP_DESIGN steps 12a and 12b, the gate log, the ledger,
                     #   $LOOP_PREV.review, $LOOP_PREV.items, $LOOP_PREV.ask; returns
                     #   {phase: recover|port|done, items[finish-item inputs], ask_open: bool,
                     #    ask_question, ask_recommend, ask_alternative, ask_basis}
      - review       # opus, Read Grep Glob, fresh; sees HQP_DESIGN, the gate log and the plan only;
                     #   {clean: bool, findings[{item, kind: defect_as_stale|unsupported_claim|
                     #    overlapping_tests|gap|duplicate|order|fence|false_quote, text}]}
      - chosen       # bash, when ask_recommend != '': appends {event: chosen, question, recommend,
                     #   alternative, basis} to HQP_LEDGER
      - items        # workflow: finish-item, fan_out over $plan.output.items, max_parallel 1, join fails on
                     #   any failed child; when review clean, phase != done and ask_open false
      - ask          # wait, attention, sole terminal sink, trigger_rule all_done; when ask_open true;
                     #   its message is the question, the recommendation, the alternative and the basis
  - id: land         # bash: refuses unless `git -C $HQP_MAIN status --porcelain` is empty; then
                     #   `git -C $HQP_MAIN merge --ff-only $HQP_BRANCH`; appends {event: landed-v2} to HQP_LEDGER
```

`plan` rules: phase `recover` while the gate is red, with items routed per 12a; phase `port` once it is green and retired shapes remain, one item per site set, per 12b; phase `done` only when the gate is green and no retired shape remains. Shared-helper items come before their callers in `items` order. A child's `baseline_red` or `blocked` returns to `plan` on the next iteration through `$LOOP_PREV.items`. `ask_open` is true only for a product choice with no recommendation and no basis in the merged code or approved documents; any other question is settled with `ask_recommend` and recorded by `chosen`. A user-facing text change, a gate exemption or a `CHANGELOG.md` entry is always `ask_open` (`hqptuner2/CLAUDE.md:10-11`, `:58`).

Launch, by the owner or a lead on the owner's word (`docs/superpowers/specs/workflow-builder-design.md:126`):

```bash
archon workflow run finish \
  --workflow-source /home/atom/dev/archon-workflows \
  --cwd /home/atom/dev/hqptuner2/.claude/worktrees/integrate --no-worktree \
  --config /home/atom/dev/archon-workflows/targets/hqptuner-finish.yaml
```

Restart is `archon workflow resume <run-id>`, which skips completed nodes (`workflow-language.md:955-1007`).

After a run ends on `land`, the lead who launched it runs `/task-check` on the landed `v2` and hands the owner its URL. The owner first sees the result there, already on `v2`.

**`feature/`**: moves to `.archon/workflows/feature-pipeline/feature/`. Its plan rounds become one `loop_group` (`plan`, `prosecute`, until the prosecution is clean, `max_iterations: 2`) and its spec rounds another (`spec`, `arbiter`), each reading the last round through `$LOOP_PREV`. Its routes and fixtures keep their outcomes.

## Homes

| Concern | Home | Forbidden elsewhere |
|---|---|---|
| Target facts: paths, branches, gate argv, never-commit paths, ledger name | `targets/hqptuner-finish.yaml` | A path, branch, gate argv or ledger name in any workflow YAML or command. |
| Gate runs and their logs | `finish-gate`, logging under `$ARTIFACTS_DIR` | Any other `make check`, `scripts/gate.sh`, `node --test` or `pytest`. A log under `/tmp`. A gate piped into `head`, `tail` or `grep`. |
| Commits | `finish-commit` | `git commit` or `git add` in any other node. `--no-verify`, `SKIP=` or `-n` anywhere. Staging a `HQP_NEVER_COMMIT` path. |
| Merge of `v2` and landing on `v2` | `finish` nodes `merge-v2` and `land` | `git merge`, `git rm`, `rm`, `git checkout`, `git restore`, `git stash`, `git reset` or `git worktree` in any other node. A landing other than `--ff-only`. |
| Progress and `CHOSEN` records | the `archon state` document `HQP_LEDGER` | Progress written to `docs/queue.md` or any repository file. A second ledger. |
| Whether a question halts | `plan`'s `ask_open`, answered by the `ask` wait | Any other `wait` node or message to the owner. A `wait` before `land`. A writer, reviewer or auditor halting the run. A merge conflict sent to the owner. |
| The cut of 12a and 12b | `plan`, checked by `review` each iteration | Items, specs or routes written by any other node. A writer run while `review` is not clean. |
| Section green | `finish-item` `work` ending with `check` `exit=0` on the item's tests | A commit of an item whose section is not green. Any other before-and-after comparison. |
| Writer fence | `finish-item` `fence` | A writer accepted with a changed path outside its `paths`. |
| Red tests and their hold | `finish-item` `red` and `pin` | A red test accepted on anything but an assertion failure. A test edited during its build. |
| Test-change legitimacy | `finish-item` `audit` | A skip, a relaxed assertion, a compatibility reader, a changed claim without quotes, a copy change or an exemption in any commit. |
| Repeated rounds | `loop_group` | A round, part or item written out node by node. A workflow YAML generated by a script. |
| Loading the pack | `--workflow-source` on this repository | Any copy into `~/.archon/workflows/`. An install script. |
| Pack code | Archon nodes in `.archon/workflows/feature-pipeline/<workflow>/` | `.shared/`, `scripts/`, an MCP server or a Python module in the pack. |
| Checking the pack | Archon's own checks from the repository root: `archon validate workflows <name>` for each workflow a step writes (`cli.md:1505-1512`) and `archon workflow test feature-pipeline` (`cli.md:194-201`, `docs/host-facts.md:25`) | `packcheck.py`, a checker script or any other done-check. Bare `archon validate workflows`, which validates every workflow Archon discovers, this pack's and others' (`cli.md:1510`). A check run under a temporary `ARCHON_HOME` or from another directory. |

## Order

Each step's done-check runs from the repository root: `archon validate workflows <name>` exits 0 printing `0 with errors` for each workflow named on the step, and `archon workflow test feature-pipeline` exits 0 printing `0 failed`.

1. `feature-pipeline/feature/` moved to `.archon/workflows/feature-pipeline/feature/`, its rounds folded into `loop_group`s; `feature-pipeline/finish-bootstrap/` deleted | `workflow-builder` | done-check: `archon validate workflows feature`; `archon workflow test feature-pipeline`
2. `targets/hqptuner-finish.yaml`; `docs/superpowers/specs/rebuild-finish-workflow-design.md` deleted | `builder` | done-check: `archon validate workflows feature`; `archon workflow test feature-pipeline`
3. `.archon/workflows/feature-pipeline/finish-gate/`, `.archon/workflows/feature-pipeline/finish-commit/` | `workflow-builder` | done-check: `archon validate workflows finish-gate`; `archon validate workflows finish-commit`; `archon workflow test feature-pipeline`
4. `.archon/workflows/feature-pipeline/finish-item/` | `workflow-builder` | done-check: `archon validate workflows finish-item`; `archon workflow test feature-pipeline`
5. `.archon/workflows/feature-pipeline/finish/` | `workflow-builder` | done-check: `archon validate workflows finish`; `archon workflow test feature-pipeline`

Step 2 writes no workflow; whether an Archon check loads a `--config` layer outside a run is unmeasured, so `targets/hqptuner-finish.yaml` is first loaded by the launch (`cli.md:295`).

Fixtures settle what the reference leaves unmeasured: that `fan_out` accepts `$plan.output.items`, that a terminal `wait` skipped by `when:` lets the group's `until_bash` decide, and that an `include:` block's `$INPUTS` reach its `bash:` node. Whether a pre-commit hook fails a commit on a tree whose JS suite is red is unmeasured; pre-commit omits the JS suite (`hqptuner2/CLAUDE.md:56`).
