Status: proposed.

# feature-pipeline: the writer fence

## Why

Every agent that writes the checkout writes it with built-in tools, bounded by its prompt alone. Five copies of write permission sit in the pack:

- `build-loop/build-loop.yaml`: one `write` node, `allowed_tools: [Read, Grep, Glob, Edit, Write, Bash]`, builds test steps and code steps alike, so the agent that writes a code step can also write its tests.
- `build-loop/build-loop.yaml`: `check` runs `$write.output.check` with `bash -c`, and `commit` stages `$write.output.paths`; the writer chooses the command the workflow runs and the paths it commits.
- `finish/finish.yaml`: `resolve` holds built-in `Edit` over the whole checkout.
- `plan-review/plan-review.yaml`: `prosecute` and `arbitrate` hold built-in `Read`, `Grep` and `Glob` over the whole checkout.
- `plan-review/plan-review.yaml`: `spec`'s `examiner` holds `Bash`, `Write` and `Edit`, kept out of the checkout by its prompt and the node's `sandbox:`.

Three rules forbid the fence itself: the roster stub and the "Pack code" row of `docs/superpowers/specs/workflow-builder-design.md` forbid an MCP server; the "Pack code" row of `docs/superpowers/specs/feature-pipeline-finish-design.md` forbids an MCP server and any script but `plan-review/scripts/cite.py`; its "Writes outside a step" row forbids a fence script, and its "Hand-off between nodes" row forbids a file one node writes for another.

## Modules

### `.archon/workflows/feature-pipeline/fence/` (built)

Two stdio MCP servers, run by `uv run --script`, each started by Claude Code once per node from that node's config file. Both resolve every path against `CLAUDE_PROJECT_DIR`, which Claude Code sets to the run's checkout, and ignore the client's roots. Nothing in this design changes them.

```text
files.py   env: CLAUDE_PROJECT_DIR (required), FENCE_READ, FENCE_WRITE, FENCE_DENY
           (colon-separated folders relative to the root; "." is the whole root)
           writes under .archon, .claude and .git are always refused
           tools: read_file(path, offset=0, limit=2000), list_directory(path="."),
                  find_files(pattern, path="."), grep(regex, path=".", glob=None),
                  write_file(path, content), edit_file(path, old, new, replace_all=False),
                  delete_file(path)
checks.py  env: CLAUDE_PROJECT_DIR, FENCE_TEST_COMMAND (required), FENCE_TEST_TIMEOUT (default 900)
           tools: run_tests() -> "exit=<n> timed_out=<bool> seconds=<n>" and the output tail
```

Replaces built-in `Read`, `Grep`, `Glob`, `Edit`, `Write` and `Bash` on every node below.

### Fence configs: `.archon/workflows/feature-pipeline/<workflow>/.archon/feature-pipeline-fence/<role>.json`

One MCP config file per fenced role, in the folder of the workflow that declares the node. A node names it as `mcp: .archon/feature-pipeline-fence/<role>.json` with `allowed_tools: []`, so the node runs on `mcp__files__*` and `mcp__checks__*` only. Archon looks the path up in the checkout first, then in the declaring workflow's folder; the checkout match it could find is `<checkout>/.archon/feature-pipeline-fence/<role>.json`, under `.archon/`, which `files.py` refuses to every role.

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
| `plan-review/.archon/feature-pipeline-fence/prosecutor.json` | `prosecute` | files | `.` | `plans/approved` | `""` |
| `plan-review/.archon/feature-pipeline-fence/arbiter.json` | `arbitrate` | files | `specs:tests:plans/approved` | `specs/approved` | `""` |
| `build-loop/.archon/feature-pipeline-fence/test-writer.json` | `tests` | files, checks | `specs/approved:tests` | `tests` | `""` |
| `build-loop/.archon/feature-pipeline-fence/implementer.json` | `implement` | files, checks | `.` | `.` | `tests:plans/approved:specs/approved` |
| `finish/.archon/feature-pipeline-fence/resolver-tests.json` | `resolvetests` | files | `specs/approved:tests` | `tests` | `""` |
| `finish/.archon/feature-pipeline-fence/resolver-plans.json` | `resolveplans` | files | `.` | `plans/approved` | `""` |
| `finish/.archon/feature-pipeline-fence/resolver-specs.json` | `resolvespecs` | files | `specs:tests:plans/approved` | `specs/approved` | `""` |
| `finish/.archon/feature-pipeline-fence/resolver.json` | `resolve` | files | `.` | `.` | `tests:plans/approved:specs/approved` |

No other folder is named in any config. `.archon/`, `.claude/` and `.git/` are refused by `files.py` itself and appear in no config. Each `finish` resolver config carries the `FENCE_*` values of the role that writes its folder: `resolver-tests.json` the test writer's, `resolver-plans.json` the prosecutor's, `resolver-specs.json` the arbiter's, `resolver.json` the implementer's.

Whether Claude Code passes `CLAUDE_PROJECT_DIR`, `PATH` and the rest of the environment the test command needs to a stdio server given an `env` block, and whether a session resumed from `brief` starts the node's servers, are unmeasured; the first live run shows both.

### `.archon/workflows/feature-pipeline/build-loop/`

The `write` node becomes two writers, `tests` for test steps and `implement` for code steps. The workflow, not a writer, holds each step's check and paths.

```yaml
# build-loop.yaml (include block)
inputs:
  plan: object
  spec: object
returns: result

nodes:
  - id: publish       # bash: writes $INPUTS.spec to specs/approved/spec.json (mkdir -p, write
                      # spec.json.tmp, mv over spec.json); outputs First
  - id: before        # bash: git status --porcelain, after publish
    depends_on: [publish]
  - id: steps
    depends_on: [before]
    loop_group:
      max_iterations: 200
      until_bash: |
        r=$review.output.remaining; [ "$r" = 0 ]
      nodes:
        - id: tests       # test writer: sonnet, medium; commands/tests.md; context: fresh
          when: "$LOOP_PREV.review.output.kind == 'test' || $LOOP_PREV.review.output == '' && $publish.output.first == 'test'"
          allowed_tools: []
          mcp: .archon/feature-pipeline-fence/test-writer.json
          settingSources: []
          output_format: Built
        - id: implement   # implementer: sonnet, medium; commands/implement.md; context: fresh
          when: "$LOOP_PREV.review.output.kind == 'code' || $LOOP_PREV.review.output == '' && $publish.output.first == 'code'"
          allowed_tools: []
          mcp: .archon/feature-pipeline-fence/implementer.json
          output_format: Built
        - id: check       # bash: step id is $tests.output.step_id$implement.output.step_id (the skipped
                          # writer reads ''); runs that step's `check` from $INPUTS.plan or $INPUTS.spec
                          # with bash -c; always exits 0; outputs status green|red and the output tail
          depends_on: [tests, implement]
          trigger_rule: none_failed_min_one_success
        - id: commit      # bash, when check is green: git add and git commit of that step's `paths`
                          # from $INPUTS.plan or $INPUTS.spec; then outputs git status --porcelain
          depends_on: [check]
          trigger_rule: all_done
        - id: review      # opus, medium, read-only built-in tools; commands/review.md
          depends_on: [commit]
          output_format: Review
  - id: result        # collector: the last iteration's Review
    depends_on: [steps]
```

```yaml
# First (output_format of publish)
first: test | code | none   # test: a Spec step's `before` is the Plan's first step, or the Plan has
                            # no steps and the Spec has one; code: the Plan has a first step and no
                            # Spec step precedes it; none: neither has a step

# Built (output_format of tests and implement)
step_id: string
design_gap: string | null

# Review (output_format of review): as in feature-pipeline-finish-design.md, plus
kind: test | code | null    # the kind of the step in `next`; null when next is null
```

- `commands/tests.md` holds no `$` reference and nothing from the lead or any other node, and the node loads no setting sources. The test writer reads `specs/approved/spec.json` and `tests/` and takes direction from the Spec alone. It builds the first test step in the Spec's `steps` order that has a line not yet written in its file as the line states, writes a test only from a line carrying file, shared, setup and assertion (a port line as in the preserved test) and a helper only from its `helpers` entry, and returns that step's id. A line it cannot build as written gets a `design_gap` and nothing written. It may call `run_tests` to see its tests fail or pass.
- `commands/implement.md` carries the Plan, the Spec and `$LOOP_PREV.review.output`. The implementer builds the step named by `next` (on iteration 1, the Plan's first step), writes the code that serves the Spec lines whose `step` is that step, fixes each finding the review gives it, reverts each stray path it is named for, and returns the step's id. It may call `run_tests`.
- `commands/write.md` is removed.
- Test steps are built strictly in Spec order. The reviewer sets `next` to a test step only when every earlier test step in Spec order has passed; once a test step is `stuck` or left unbuilt, no later test step is built this cycle, and no code step whose test step is unbuilt is built.
- A review `fix` on a test step reruns the test writer with no findings; it re-reads the Spec and its tests. A finding with the same cause and basis as one in `fixed` makes the step `stuck`. A stray path under `tests/`, or a `step_id` that differs from `next`, makes a test step `stuck` at once.
- The reviewer checks each writer's `step_id` against `next`, the tests against their lines and the code against the lines that cite its step. Everything else in the build-loop module of `feature-pipeline-finish-design.md` holds as written there, with `write` read as whichever writer ran.

### `.archon/workflows/feature-pipeline/plan-review/`

```yaml
- id: prosecute     # unchanged but for its tools
  allowed_tools: []
  mcp: .archon/feature-pipeline-fence/prosecutor.json
- id: arbitrate     # unchanged but for its tools
  allowed_tools: []
  mcp: .archon/feature-pipeline-fence/arbiter.json
```

- `commands/prosecute.md` and `commands/arbitrate.md` name the `files` tools in place of `Read`, `Grep` and `Glob`. `arbitrate.md` states that the arbiter reads only `specs/`, `tests/` and `plans/approved/` and holds the design from `brief`.
- `commands/spec.md` writes the Spec's test steps in build order: in the Plan order of the code step each step's `before` names, steps with `before` null last. `commands/arbitrate.md` adds that order to its cross-check, as a `field: order` finding.
- `spec` and its `examiner` keep their tools and `sandbox:`; the examiner writes only its scratch copy under `$ARTIFACTS_DIR/.archon/scratch/spec/`.

### `.archon/workflows/feature-pipeline/finish/`

A sync conflict is fixed by the resolver whose fence writes the conflicted path's folder. Four resolver nodes replace the one `resolve`, all `context: fresh`, `allowed_tools: []`, with `resolve`'s output format `{ resolved: boolean, reason: string }`.

```yaml
# finish.yaml, cycle body
- id: sync          # as today, plus four outputs splitting `paths`, one path per line:
                    # tests (under tests/), plans (under plans/approved/),
                    # specs (under specs/approved/), other (every other conflicted path)
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
  depends_on: [resolvetests, resolveplans, resolvespecs, resolve]
  trigger_rule: none_failed_min_one_success
```

- `commands/resolve.md`, `commands/resolve-plans.md` and `commands/resolve-specs.md` are today's `resolve.md`, each listing its own `$sync.output.<folder>` paths, naming the `files` tools in place of `Read`, `Edit`, `Grep` and `Glob`, and resolving from the two sides and what its fence reads.
- `commands/resolve-tests.md` holds no `$` reference and nothing from the lead or any other node, and the node loads no setting sources. The resolver finds the conflicted files with the `files` `grep` for marker lines under `tests/`, resolves each block from the two sides and `specs/approved/` alone, and returns `resolved` and `reason` as `resolve` does. A block `specs/approved/` does not settle is left.
- `resolvetests` runs after `resolvespecs`, so it reads `specs/approved/` with its conflicts resolved.
- `unmerged` is unchanged: a marker left in any path, `.archon/`, `.claude/` and `.git/` included, ends the run through its cancel.

## Homes

| Concern | Home | Forbidden elsewhere |
|---|---|---|
| An agent's writes to the checkout | the node's fence config, served by `fence/files.py`, with `allowed_tools: []` | Built-in `Edit`, `Write`, `NotebookEdit` or `Bash` on any node but `spec`'s `examiner`; a fence folder in a prompt, a YAML file or the launcher's environment; a folder in a config that the config table above does not name; a role writing `.archon/`, `.claude/` or `.git/`. |
| An agent's reads of the checkout, on a fenced node | the same config's `FENCE_READ` | Built-in `Read`, `Grep` or `Glob` on a fenced node. |
| A writer's test runs | `fence/checks.py`'s `run_tests`, on the command in `TEST_COMMAND` | Built-in `Bash` on a writer; a test command in a prompt or config. |
| Locating the fence scripts | `PACK_DIR` in each config's `env`, read by `sh -c` with the `:?` guard | A pack path literal in a config, a YAML file or a prompt; a server started from the checkout. |
| Fence config location | `<workflow>/.archon/feature-pipeline-fence/<role>.json`, named by `mcp: .archon/feature-pipeline-fence/<role>.json` | A config path whose checkout match lies outside `.archon/`; a config file anywhere in the checkout; one config copied into two workflow folders; a `finish` resolver config whose `FENCE_*` differ from the role's row it carries. |
| Who fixes a sync conflict | the `finish` resolver whose fence writes the path's folder, picked by `sync`'s `tests`, `plans`, `specs` and `other` outputs | A resolver given a path outside its folder; one resolver for every folder; a conflict under `tests/` fixed by any node but `resolvetests`. |
| Pack code | the "Pack code" row of `feature-pipeline-finish-design.md`, plus `fence/files.py`, `fence/checks.py`, their tests, the eight fence configs, the `mcp:` paths and `build-loop`'s `publish` | Any other MCP server, script, config or bash job. |
| A step's check and committed paths | the step in `$INPUTS.plan` or `$INPUTS.spec`, looked up by the writer's `step_id` in `check` and `commit` | A writer's output carrying a check or paths; `check` running any other command. |
| The test writers' direction | `specs/approved/`: for `tests`, its `spec.json`, written only by `publish` from `$INPUTS.spec`; for `resolvetests`, the folder as `resolvespecs` leaves it | A `$` reference, or anything from the lead or another node, in `commands/tests.md` or `commands/resolve-tests.md`; a setting source on `tests` or `resolvetests`; any file in `specs/approved/` but `spec.json` read by `tests`. |
| Which writer runs | `tests`' and `implement`'s `when:`, on `review`'s `kind` and, on iteration 1, `publish`'s `first` | A writer choosing between test and code steps; a step kind decided anywhere else. |
| Test-step order | the Spec's `steps` order, written by the specifier and checked by the arbiter | A test writer told which step to build; a test step built out of Spec order. |
| Hand-off between nodes | as in `feature-pipeline-finish-design.md`, plus `specs/approved/spec.json` from `publish` to `tests` | Any other file written by one node for another in the same run. |
| Writes outside a step | `build-loop`'s reviewer, from `before` and `commit` status output, beside the fence | A hook; a node that reverts on its own; a "did `tests/` change" check after a step. |

## Order

1. `architect`: `docs/superpowers/specs/workflow-builder-design.md`: the roster stub's MCP-server line and the "Pack code" row admit `fence/files.py`, `fence/checks.py` and the fence configs as this design places them, pointed at `docs/superpowers/specs/writer-fence-design.md`.
2. `architect`: `docs/superpowers/specs/feature-pipeline-finish-design.md`: the Modules preamble (bash jobs, the bash stub list with `publish`, script files), the build-loop module, the `prosecute`, `arbitrate`, `spec` and examiner lines of the plan-review module, the finish module's `sync`, `resolve` and `merge` lines, its sync-conflict paragraph and its `resolved` and `unresolved` fixture lines, and the "Pack code", "Writes outside a step", "Hand-off between nodes" and "Checking the pack" rows, stated as this design holds them.
3. `role-author`: `~/.claude/agents/workflow-builder.md`: `mcp:` paths under `.archon/feature-pipeline-fence/` and the fence config files in each workflow folder admitted; `fence/` left unwritable.
4. `workflow-builder`: `.archon/workflows/feature-pipeline/build-loop/build-loop.yaml`, `.archon/workflows/feature-pipeline/build-loop/commands/tests.md`, `.archon/workflows/feature-pipeline/build-loop/commands/implement.md`, `.archon/workflows/feature-pipeline/build-loop/commands/review.md`, `.archon/workflows/feature-pipeline/build-loop/commands/write.md` (removed), `.archon/workflows/feature-pipeline/build-loop/.archon/feature-pipeline-fence/test-writer.json`, `.archon/workflows/feature-pipeline/build-loop/.archon/feature-pipeline-fence/implementer.json`, `.archon/workflows/feature-pipeline/build-loop/fixtures/*.stubs.yaml`, `.archon/workflows/feature-pipeline/finish/fixtures/*.stubs.yaml`: `publish`, the two writers, `check` and `commit` reading the step from the inputs, `review`'s `kind`; every fixture stubbing `publish`, `tests` and `implement` as it reaches them, with a fixture whose first step is a test step and one whose first step is a code step.
5. `workflow-builder`: `.archon/workflows/feature-pipeline/plan-review/plan-review.yaml`, `.archon/workflows/feature-pipeline/plan-review/commands/prosecute.md`, `.archon/workflows/feature-pipeline/plan-review/commands/arbitrate.md`, `.archon/workflows/feature-pipeline/plan-review/commands/spec.md`, `.archon/workflows/feature-pipeline/plan-review/.archon/feature-pipeline-fence/prosecutor.json`, `.archon/workflows/feature-pipeline/plan-review/.archon/feature-pipeline-fence/arbiter.json`: `prosecute` and `arbitrate` on their configs; the Spec's test steps in build order, checked by the arbiter.
6. `workflow-builder`: `.archon/workflows/feature-pipeline/finish/finish.yaml`, `.archon/workflows/feature-pipeline/finish/commands/resolve.md`, `.archon/workflows/feature-pipeline/finish/commands/resolve-plans.md`, `.archon/workflows/feature-pipeline/finish/commands/resolve-specs.md`, `.archon/workflows/feature-pipeline/finish/commands/resolve-tests.md`, `.archon/workflows/feature-pipeline/finish/.archon/feature-pipeline-fence/resolver.json`, `.archon/workflows/feature-pipeline/finish/.archon/feature-pipeline-fence/resolver-plans.json`, `.archon/workflows/feature-pipeline/finish/.archon/feature-pipeline-fence/resolver-specs.json`, `.archon/workflows/feature-pipeline/finish/.archon/feature-pipeline-fence/resolver-tests.json`, `.archon/workflows/feature-pipeline/finish/fixtures/resolved.stubs.yaml`, `.archon/workflows/feature-pipeline/finish/fixtures/unresolved.stubs.yaml`: `sync`'s folder outputs, the four resolvers on their configs, `merge` over all four; `resolved` stubs a conflict in `tests/` and one in another folder, each resolved by its own resolver; `unresolved` stubs `resolvetests` leaving a conflict.

Each step's done-check is the "Checking the pack" home of `feature-pipeline-finish-design.md`.
