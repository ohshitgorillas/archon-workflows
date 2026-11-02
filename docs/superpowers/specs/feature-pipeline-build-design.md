Status: proposed.

## Why

Phase 1 of `feature-pipeline` is `.archon/workflows/feature-pipeline/feature/feature.yaml`: planner, prosecutor, plan gate, spec writer, Arbiter, spec gate, reading the run's working directory in place and writing nothing. It ends at `spec-rejected` with an approved spec and no code. Phases 2 and 3 build, check and land the code, using Archon's own nodes and no scripts, libraries or wrappers. What they share, and the copies or gaps already present:

1. **Base commit.** Phase 1 reads the checkout in place, so what it read is that checkout's `HEAD` at run start; no node records it. A writing child run with `isolation: worktree` is cut from `origin/<baseBranch>`, not from the parent's checkout, with the base resolved from repo config or the remote's HEAD. In `~/dev/hqptuner2` local `v2` is 46 commits ahead of `origin/v2` (`git rev-list --count origin/v2..v2`). See Archon gap 1.
2. **Target facts.** Phase 1 needs none. Phases 2 and 3 need the target's test paths, how to run one test, its gate and its protected paths. No copy exists yet; none may be a literal in the pack. Provisioning a fresh checkout is Archon's `worktree.postCreate` in the target's `.archon/config.yaml`; `~/dev/hqptuner2` has no `.archon/` and no setup target.
3. **Write fences.** The sandbox fences Bash only; Edit and Write pass through it; it cannot start without `socat`, which is absent; there is no per-node path allow-list. See Archon gap 2.
4. **Round loops.** Two copies of loop, verdict and cancel in `feature.yaml`, one for the plan and one for the spec. Phases 2 and 3 add two more. Each loop's gate reads its inner nodes' outputs, which an `include:` block hides; the shape stays inline per loop, each with its own schema.
5. **Approval gates.** Two copies of wait plus cancel-on-reject in `feature.yaml`, the plan gate and the spec gate, the form Archon documents. Phase 3 adds the merge gate in the same form.
6. **Test discipline.** The first target requires new tests to fail against pre-change code, never edited to pass, with a red after implementation going back to the owner, and commits that pass the target's hooks with no bypass.
7. **Cleanup.** A child worktree is not removed when the child ends and nothing merges it back.

## Modules

**`.archon/workflows/feature-pipeline/feature/feature.yaml`**: the parent run. Keeps phase 1 as built; adds the target inputs, a `base` node, the `build` child launch, the cancels on a failed build, the merge gate and the land. Runs in the target checkout with `worktree.enabled: false`; its agents never write.

```yaml
inputs:
  request:   { required: true }   # as built
  tests:     { required: true, description: JSON array of repo-relative test path prefixes. }
  test_cmds: { required: true, description: >-
      JSON object, file suffix -> argv array; "{file}" and "{name}" in an element are
      replaced with one test's file and name. Run with no shell. }
  gate:      { required: true, description: Shell command; exit 0 is green. }
  protected: { required: true, description: JSON array of repo-relative paths no agent writes. }

nodes:
  - id: base            # phase 2; bash, no depends_on
    # prints {"sha": <git rev-parse HEAD>, "branch": <git branch --show-current>}
    output_format: { sha: string, branch: string }

  # read-request .. spec-rejected: unchanged

  - id: build           # phase 2
    depends_on: [spec-gate, spec-rejected, base]
    trigger_rule: none_failed_min_one_success
    workflow: feature-build
    isolation: worktree
    with: { request, plan: $plan-loop.output, spec: $spec-loop.output,
            spec_note: $spec-gate.output.text, tests, test_cmds, gate, protected }

  - id: tests-refused   # phase 2; cancel when $build.output.verdict == 'TESTS_REFUSED'
  - id: build-red       # phase 2; cancel when $build.output.verdict == 'RED'
    # both messages carry $build.output.report and $build.output.branch (kept for inspection)

  - id: merge-gate      # phase 3; wait, form: approval, when verdict == 'GREEN'
    # attention: branch, head, $build.output.diffstat, $build.output.review
  - id: merge-rejected  # phase 3; cancel on reject, message names the kept branch
  - id: land            # phase 3; bash, mutates_checkout: true
    # refuses unless `git branch --show-current` == $base.output.branch,
    # then `git merge --ff-only $build.output.head`; a moved branch, a head that
    # does not descend from the checkout, or a conflicting local change fails the
    # node and leaves the build branch.
  - id: cleanup         # phase 3; bash: archon complete $build.output.branch
```

**`.archon/workflows/feature-pipeline/feature-build/feature-build.yaml`**: the child run. Writes tests, then code, in its own worktree; runs the tests and the gate; returns a verdict. It never cancels: the parent owns every stop. New folder, holding only its YAML and `fixtures/`.

```yaml
name: feature-build
description: >-
  Child of feature; not for a standalone run. Needs a git-repo codebase run via the CLI.
provider: claude
model: claude-opus-5-5
effort: medium
inputs: { request, plan, spec, spec_note, tests, test_cmds, gate, protected }
returns: result

nodes:
  - id: start           # bash: prints {"sha": <git rev-parse HEAD>}, the commit Archon cut

  - id: tests-loop      # loop_group, max_iterations: 2, until tests-check verdict PASS
    nodes:
      - id: write-tests
        context: fresh
        allowed_tools: [Read, Grep, Glob, Edit, Write]
        # sees request, plan, spec, spec_note, the tests prefixes, $LOOP_PREV.tests-check.output;
        # told to write only under the tests prefixes; every spec line gets at least one test
        output_format:
          tests: [{ line: string, file: string, name: string }]
      - id: tests-check  # bash
        # 1. every spec line id appears in write-tests.output.tests
        # 2. runs each test by its suffix's argv from test_cmds:
        #    a RED line's tests exit nonzero, a GREEN line's tests exit 0
        output_format:
          verdict: PASS | FAIL
          results: [{ line: string, file: string, name: string, expected: RED | GREEN, exit: integer }]

  - id: impl-loop       # loop_group, max_iterations: 2, until impl-check verdict GREEN; after a PASS
    nodes:
      - id: implement
        context: fresh
        allowed_tools: [Read, Grep, Glob, Edit, Write]
        # sees request, plan, spec, spec_note, the test list, protected, $LOOP_PREV.impl-check.output;
        # told never to touch a test path or a protected path
      - id: impl-check   # bash: runs "$INPUTS_GATE" > $ARTIFACTS_DIR/gate-<iteration>.log 2>&1
        output_format:
          verdict: GREEN | RED
          exit: integer
          log: string        # path
          tail: string       # last 200 lines of the log

  - id: commit          # phase 3; bash, only on GREEN:
    # git add -A; git commit -m "feature: <request basename without extension>"
    # the target's commit hooks run; a hook failure fails the node
  - id: diff            # phase 3; bash: git diff --stat and git diff <start sha>..HEAD
  - id: review          # phase 3; agent, context: fresh, allowed_tools: [Read, Grep, Glob]
    # judges the diff against request, plan, spec and protected
    output_format:
      verdict: PASS | FAIL
      findings: [{ path: string, finding: string }]

  - id: result          # bash; the one terminal node
    output_format:
      verdict: GREEN | RED | TESTS_REFUSED
      branch: string     # git branch --show-current
      head: string       # git rev-parse HEAD
      report: string     # last tests-check or impl-check output
      diffstat: string   # "" before phase 3 and off GREEN
      review: string     # "" before phase 3 and off GREEN
```

## Homes

| Concern | Home | Forbidden elsewhere |
|---|---|---|
| Target facts | the five `feature` inputs, passed to `feature-build` by `with:` | A test path, command, gate or protected path as a literal in YAML or prompt. |
| Checkout provisioning | the target's `.archon/config.yaml` `worktree.postCreate` | A setup node or setup input in the pack. |
| Writable checkout | the `build` node's `isolation: worktree` | Any write by any node of `feature`, except `land`. A base worktree, a tests worktree, or any other checkout cut by the pack. |
| Bite proof | `tests-check` step 2, before any implementation | Tests written after `implement` starts. |
| Stops and cancels | `feature` cancel nodes | A `cancel:` node in `feature-build`. |
| Owner approvals | `plan-gate`, `spec-gate`, `merge-gate` | Any other wait node. |
| Landing | `feature` node `land` | A push, a PR, a merge or reset in the target checkout by any other node. |
| Scaffolding | none | A `scripts/` or `commands/` file, a `.shared/` module, an install, check or wrapper script, in any workflow of the pack. A workaround for an Archon gap below. |
| Struck items | nowhere | A request judge, base worktree, tests worktree, stubs or interface view in any workflow of the pack. |
| Workflow checks | `archon validate workflows <name>` and `archon workflow test feature-pipeline` from the repository root | Any other done-check for a workflow folder. |

Unmeasured, settled by the first live run: whether `isolation: worktree` under `worktree.enabled: false` cuts a child as under `--no-worktree`; whether the child's cut needs a reachable remote; whether `archon complete` runs from inside a run; the `test_cmds` and `worktree.postCreate` values for `~/dev/hqptuner2`.

## Archon gaps

1. **No isolated child on a local commit.** `isolation: worktree` cuts from `origin/<baseBranch>` resolved by config or the remote's HEAD, and parent `--base`/`--from` do not reach the child. Phase 1 read local `HEAD`; in `~/dev/hqptuner2` that is 46 commits past `origin/v2`. Until this is closed the build runs on a tree phase 1 did not read, and `land` refuses because the build head does not descend from the checked-out branch.
2. **No write fence for Edit and Write.** The sandbox fences Bash only, needs the absent `socat`, and no node takes a path allow-list. Nothing in Archon stops `write-tests` writing outside the tests prefixes, or `implement` editing a test or a protected path; the prompts say so and `review` reads the diff, nothing enforces it.

## Order

1. **Phase 2.** `feature`: the four target inputs beyond `request`, `base`, `build`, `tests-refused`, `build-red`; phase-1 fixtures updated for `base`; fixtures for build green, build red and tests refused. `feature-build`: `start` to `impl-loop` and `result`, with fixtures for green in round 1, green in round 2, tests refused and red after two rounds. Paths: `.archon/workflows/feature-pipeline/feature/feature.yaml`, `.archon/workflows/feature-pipeline/feature/fixtures/*.stubs.yaml`, `.archon/workflows/feature-pipeline/feature-build/feature-build.yaml`, `.archon/workflows/feature-pipeline/feature-build/fixtures/*.stubs.yaml` | `workflow-builder`
2. **Phase 3.** `feature-build`: `commit`, `diff`, `review`, and `diffstat` and `review` in `result`; fixtures for a commit hook failure and both review verdicts. `feature`: `merge-gate`, `merge-rejected`, `land`, `cleanup`; fixtures for landed, rejected and land refused. Same paths as step 1 | `workflow-builder`

## Decisions for the owner

1. **What happens after you approve the merge.** Recommend: `land` fast-forwards your checked-out branch in the target checkout to the build head, refusing if the branch moved or a local change conflicts, then removes the build worktree and branch. Cost: the run writes your live checkout, once, ff-only. Alternative: the run ends at your approval with the branch named; you merge it by hand. Cost: one manual merge per feature, and build branches stay until you remove them.
