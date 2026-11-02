Status: approved.

## Why

The tree holds no pack code yet. Each concern the pack's pieces share already has one copy or a constraint that decides where its home goes:

1. **Fence paths.** The only fence in the tree is the spike's sandbox block, which uses relative globs (`docs/reference/archon/spike-sandbox-workflow.yaml:12-16`). Those globs do nothing, and only Bash is fenced, so every absolute path the pack fences lives in one module.
2. **Checkout per agent.** A node has no `cwd` of its own. A `workflow:` child with `isolation: worktree` gets a generated path and branch, cut from `origin/<baseBranch>` (`docs/reference/archon/workflow-language.md:101`, `:2094-2116`), so it cannot sit at a fixed path. `--cwd <dir> --no-worktree` runs a whole run in a directory of your choosing (`docs/reference/archon/cli.md:290`), and `--detach --json` is the only form whose output can be parsed (`cli.md:278`, `:302`). One launcher therefore runs every tool-bearing agent as its own run in a fixed worktree.
3. **Test running.** HQPTuner runs pytest in three ways: the gate (`~/dev/hqptuner2/Makefile:82-83`), the ini settings (`~/dev/hqptuner2/pyproject.toml:56-78`, `testpaths` at `:63`, `pythonpath` at `:68`) and mutmut (`pyproject.toml:98`). The pack's red runs, green runs and `run_tests` need one runner with its own ini. It reads `pythonpath` from the tree and loads no repository plugins (`~/dev/gauntlet/docs/design.md:175`, `:202`).
4. **Interface view.** Both the test writer and the Arbiter see signature-only stubs (`~/dev/gauntlet/docs/design.md:198`). They are generated once per plan.
5. **Branches.** `~/dev/hqptuner2` is a worktree of `~/dev/hqptuner` on `v2`, 508 commits ahead of `main`. Promotion to `main` is the owner's call (`~/dev/hqptuner2/CLAUDE.md:60`). The run cuts from `v2` and lands on `v2`.
6. **Changelog.** No agent writes `CHANGELOG.md` (`~/dev/hqptuner2/CLAUDE.md:58`). It is fenced like the protected set.
7. **Verdict shapes.** Archon holds each result shape on the node that produces it (`docs/reference/archon/workflow-language.md:2629-2645`). No module restates a schema.

## Modules

The pack is `hqptuner-feature/` at the repository root. `install.py` copies it to `~/.archon/workflows/hqptuner-feature/`. Shared modules go in `hqptuner-feature/.shared/` (`workflow-language.md:50`). Each workflow is `hqptuner-feature/<workflow>/<workflow>.yaml`, with its own `scripts/`, `commands/` and `fixtures/*.stubs.yaml`, at least one fixture per workflow (`workflow-builder-design.md:124`). Scripts use `runtime: uv`.

**`.shared/fence.py`**: every absolute path, and the read and write roots of each role. Replaces the relative globs at `spike-sandbox-workflow.yaml:15-16`.

```python
REPO = Path("/home/atom/dev/hqptuner2")
BASE_BRANCH = "v2"
RUN_ROOT = Path("/home/atom/.archon/hqptuner-run")
TREES = {"base": RUN_ROOT / "base", "tests": RUN_ROOT / "tests",
         "impl": RUN_ROOT / "impl", "merge": RUN_ROOT / "merge"}
INTERFACE_DIR = ".interface"          # inside the tests tree, outside hqptuner/
PROTECTED = ("conftest.py", "pyproject.toml", "package.json", "Makefile",
             "scripts/pytest_plugins/", "CHANGELOG.md", ".interface/")
Role = Literal["planner", "prosecutor", "spec_writer", "writer", "implementer", "juror", "reviewer"]

@dataclass(frozen=True)
class Fence:
    read: tuple[Path, ...]            # absolute roots Read/Grep/Glob may touch
    write: tuple[Path, ...]           # absolute roots Edit/Write may touch
    deny: tuple[Path, ...]            # absolute roots denied to every tool, inside read roots too

def fence(role: Role) -> Fence: ...
def sandbox_block(role: Role) -> dict: ...   # the YAML `sandbox:` mapping for that role, absolute paths only
```

- `writer`: reads `tests/` in the tests tree, `.interface/`, `REPO/docs/spec/testing.md` and the run's request and spec files. Writes `tests/` in the tests tree only. The tests tree's `hqptuner/` is in `deny`.
- `implementer`: reads the impl tree. Writes the impl tree outside `tests/` and `PROTECTED`.
- `planner`, `prosecutor`, `spec_writer`: read the base tree; write nothing.
- `juror`, `reviewer`: read the merge tree; write nothing.
- Every role has `REPO` and the other trees in `deny`.

**`.shared/guard.py`**: the PreToolUse hook for Read, Grep, Glob, Edit and Write. It checks the structured path in the tool input against `fence(role)` and refuses with the reason.

```python
def decide(role: Role, tool: str, tool_input: dict) -> tuple[Literal["allow", "deny"], str]: ...
def main() -> int: ...   # reads the hook payload on stdin and prints the PreToolUse decision
```

**`.shared/trees.py`**: the fixed worktrees and the checks on them.

```python
def cut(name: str, branch: str, start: str) -> Path: ...   # removes any stale worktree at TREES[name], then `git worktree add` it fresh
def head(name: str) -> str: ...
def changed_paths(name: str, since: str) -> list[str]: ...
def diff_gate(name: str, since: str, allowed: Callable[[str], bool]) -> list[str]: ...   # the paths that break the rule; empty means pass
def tests_digest(name: str) -> str: ...                   # git tree hash of tests/
def merge_tests(tests_commit: str) -> str: ...            # merge tree = impl HEAD with tests/ taken from tests_commit; returns the commit
def land(commit: str) -> str: ...                         # `merge --ff-only` into BASE_BRANCH at REPO; refuses a dirty REPO or a REPO not on BASE_BRANCH
def remove_all() -> None: ...
```

**`.shared/stage.py`**: runs a stage workflow as its own Archon run in a fixed tree and returns that run's `returns:` value.

```python
@dataclass(frozen=True)
class StageResult:
    run_id: str
    status: Literal["completed", "failed", "cancelled"]
    value: dict | None            # the stage's returns: value from terminal_record
    reason: str | None

def run_stage(workflow: str, tree: str, inputs: dict[str, str]) -> StageResult: ...
# archon workflow run <workflow> --cwd TREES[tree] --no-worktree --detach --json --input k=v...,
# then `archon workflow wait <id>`, then `archon workflow get <id> --json`
```

**`.shared/harness.py`**: the only test runner the pack uses.

```python
Outcome = Literal["pass", "fail", "error"]

@dataclass(frozen=True)
class TestOutcome:
    test_id: str
    outcome: Outcome
    exc_type: str | None

def run_tests(tree: str, test_ids: list[str] | None = None) -> list[TestOutcome]: ...
# own ini written to RUN_ROOT/pytest.ini (pythonpath read from the tree's pyproject.toml, testpaths = tests),
# `-c <ini> --confcutdir=tests -m "not live and not e2e" -p no:cacheprovider`, PYTEST_DISABLE_PLUGIN_AUTOLOAD=1,
# junit XML parsed to outcomes; prints no traceback and no output
def run_js_tests(tree: str, files: list[str]) -> list[TestOutcome]: ...
```

**`.shared/run_tests_mcp.py`**: a stdio MCP server with one tool, `run_tests(test_ids)`, on the tests tree. It is the writer's only route to running anything against the real source. It calls `harness.run_tests("tests", ids)` or `harness.run_js_tests` and returns `[{test_id, outcome, exc_type}]`.

**`.shared/interface.py`**: builds the interface view and the stubs from the plan.

```python
@dataclass(frozen=True)
class Surface:
    module: str                   # e.g. "hqptuner/engine/foo.py" or "hqptuner/static/x.js"
    names: list[str]              # public names the plan adds or changes

def view(tree: str, surfaces: list[Surface]) -> Path: ...    # .pyi via stubgen, .d.ts via tsc --allowJs --declaration --emitDeclarationOnly,
                                                               # trimmed to `names`, written to <tree>/.interface/
def stub(tree: str, surfaces: list[Surface]) -> list[str]: ...  # adds the new names to the tree with bodies that raise NotImplementedError / throw; returns paths
```

**`.shared/request.md`**: the request template. Its sections are Goal, Behaviour (observable, one item per line), Examples, Out of scope and Surfaces touched. The intake session writes `docs/requests/<slug>.md` to it, and `check-request` judges against it.

**`.shared/notice.py`**: writes every message the owner sees.

```python
def plan_gate(plan: str, review: dict) -> str: ...
def spec_gate(spec: str, rulings: dict) -> str: ...
def tests_diff_gate(diff: str, rulings: dict) -> str: ...
def replan_gate(lines: list[str], plan_diff: str, review: dict) -> str: ...
def undetermined_gate(verdicts: dict, outcomes: list[dict]) -> str: ...
def merge_gate(diff_stat: str, gates: dict, findings: list[dict]) -> str: ...
```

**`install.py`** (repository root): calls `packcheck.check` (`workflow-builder-design.md:89`, `:112`) on `hqptuner-feature/` and refuses on any failure, then copies it to `~/.archon/workflows/hqptuner-feature/`. It runs no `archon validate` of its own. It refuses to install when `socat` is missing.

**Workflows.** Each stage workflow pins `worktree.enabled: false`, gives each agent node `provider: claude`, a named model, effort `medium`, `context: fresh`, `sandbox: fence.sandbox_block(role)` as literal YAML, the `guard.py` hook for its role and `allowed_tools`. Its `returns:` names a node with `output_format`.

| Workflow | Runs in | Agent, model | Tools | Returns |
|---|---|---|---|---|
| `hqptuner-feature` | `REPO`, `worktree.enabled: false` | none with tools; `check-request` and `arbiter` are tool-less judge prompts (`allowed_tools: []`) on opus | — | `{outcome, landed_commit, reason}`; `outcome_field: outcome` |
| `hqp-plan` | base tree | planner, opus | Read, Grep, Glob | `{plan, surfaces[], steps[]}` |
| `hqp-prosecute` | base tree | prosecutor, opus | Read, Grep, Glob | `{checks[{id, verdict: PASS\|FAIL\|COULD_NOT_JUDGE, reason}]}` |
| `hqp-spec` | base tree | spec writer, opus | Read, Grep, Glob | `{lines[{id: S<n>, behaviour, start: RED\|GREEN}]}` |
| `hqp-write-tests` | tests tree | test writer, sonnet | Bash, Read, Grep, Glob, Edit, Write, `mcp: run_tests` | `{bindings[{line, test_ids[]}]}` |
| `hqp-implement` | impl tree | implementer, sonnet | Bash, Read, Grep, Glob, Edit, Write | `{status: complete\|blocked, reason}` |
| `hqp-judge-red` | merge tree | juror, opus | Read, Grep, Glob | `{verdicts[{test_id, line, side: build_wrong\|tests_wrong\|spec_wrong\|undetermined, reason}]}` |
| `hqp-review` | merge tree | diff reviewer, sonnet; sees the diff and the request only | Read, Grep, Glob | `{findings[{path, line, severity: blocking\|note, text}]}` |

Every node in `hqptuner-feature` and every read-only stage node has `mutates_checkout: false`.

**`hqptuner-feature` nodes**, in DAG order. Input: `request`, a path under `REPO/docs/requests/`.

1. `check-request`: a script binds the request text and `request.md`, and a judge returns `{complete, gaps[]}`. `cancel` with the gaps when incomplete.
2. `cut-base`: `trees.cut("base", "archon/hqp-<slug>-base", BASE_BRANCH)`.
3. `plan-1`, `prosecute-1`, then `plan-2` and `prosecute-2` with `when:` any check from round 1 is not `PASS`. If round 2 still fails, `cancel` with the failing checks. These are script nodes calling `run_stage`.
4. `plan-gate`: `wait`, `form: approval`, message from `notice.plan_gate`. `reject` cancels the run, with the owner's text as the reason.
5. `interface`: `trees.cut("tests", …)`, `interface.stub("tests", surfaces)`, `interface.view("tests", surfaces)`, then commit the stubs on the tests branch.
6. `spec`: `run_stage("hqp-spec", "base", …)`.
7. `arbiter`: a judge with no tools. Its prompt holds only the request, the spec, the interface view and `REPO/docs/spec/testing.md`. It returns `{rulings[{line, verdict: ACCEPT\|REJECT, reason}]}`. On any `REJECT`, `spec` and `arbiter` run once more with the rulings. Any `REJECT` after that cancels the run.
8. `spec-gate`: `wait`, `form: approval`.
9. `cut-impl`: `trees.cut("impl", "archon/hqp-<slug>", BASE_BRANCH)`.
10. `write-tests` and `implement` run in one layer.
    - `write-tests`: `run_stage("hqp-write-tests", "tests", …)`, then `trees.diff_gate("tests", stubs_commit, under tests/ and not PROTECTED)`. Every bound test must be `fail` or `error` on the stubs under `harness.run_tests("tests")`, except lines marked `GREEN`. The script commits `tests/` as the locked commit.
    - `implement`: `run_stage("hqp-implement", "impl", …)`, then `trees.diff_gate("impl", base, not under tests/ and not PROTECTED)`. Any breach fails the node.
11. `merge-run`: `trees.merge_tests(locked)`, then `harness.run_tests("merge")`. Green goes to node 15.
12. `juror`: `run_stage("hqp-judge-red", "merge", …)` on the failing ids. Every failing id has exactly one verdict.
13. One repair, chosen by the juror's verdicts. A run with any `undetermined` verdict, or with verdicts of more than one side, goes to node 14.
    - `build_wrong`: `implement` runs once more, silently, with the failing ids, followed by its diff gate and `merge-run`.
    - `tests_wrong`: `write-tests` runs once more on the named tests. The Arbiter re-rules only the spec lines bound to the changed tests. Then `tests-diff-gate` (`wait`, `form: approval`), a new locked commit, and `merge-run`.
    - `spec_wrong`: the affected lines are replanned with `hqp-plan`. `hqp-prosecute` re-reviews only those lines. Then `replan-gate` (`wait`, `form: approval`), `hqp-spec` and the Arbiter for those lines, `write-tests` and `implement` for those lines, and `merge-run`.
    - A red `merge-run` after the repair goes to node 14.
14. `undetermined-gate`: `wait`, `form: select`, message from `notice.undetermined_gate` giving both sides. The options are `build-wrong`, `tests-wrong`, `spec-wrong` and `abandon`, and the owner's answer may carry a note. Picking a side runs that side's repair from node 13 once, with the note. A red `merge-run` after that pass, or `abandon`, cancels the run with both sides recorded in the reason.
15. `verify`: `trees.tests_digest("merge")` equals the digest of the last locked commit, `make check` passes in the merge tree, and `hqp-review` runs. Blocking findings appear on the merge gate. They do not trigger a repair.
16. `merge-gate`: `wait`, `form: approval`, message from `notice.merge_gate`. On approve, `trees.land(merge_commit)`, then `trees.remove_all()`. On reject, the run is cancelled and the trees stay for inspection.

**Phases.** `hqptuner-feature.yaml` is built in three phases. Phase 1 holds nodes 1 to 8 and ends after `spec-gate`, before any test or code writing. Phase 2 holds nodes 9 to 11. Phase 3 holds nodes 12 to 16.

- Phases 1 and 2 end in a script node `phase-end`, which `returns:` names while it exists. It returns `{outcome: "phase_end", landed_commit: null, reason}`, the reason naming the last node reached; after phase 2 that is `merge-run`, green or red, with the failing ids.
- `phase-end` removes no tree; the next run's `trees.cut` clears them.
- Phase 2 moves `phase-end` behind `merge-run`, both green and red. Phase 3 deletes `phase-end` and points `returns:` at the final node.
- Each phase keeps every earlier fixture passing, rewriting the reached-node list of each fixture that reached `phase-end`, and adds fixtures for its own routes.

## Homes

| Concern | Home | Forbidden elsewhere |
|---|---|---|
| Absolute paths, base branch, protected set, role roots | `.shared/fence.py` | Path or branch literals in any script. YAML `sandbox:` blocks must equal `sandbox_block(role)`, and `tests/test_fence_sync.py` checks this. |
| Tool path checks | `.shared/guard.py` | Any other PreToolUse hook. Any per-node path logic. |
| Worktree lifecycle, diff gates, tests lock, landing | `.shared/trees.py` | `git worktree`, `git merge` or `git diff` run from any other script or YAML `bash:`. |
| Running an agent with tools | `.shared/stage.py` and the stage workflows | A tool-bearing agent node in `hqptuner-feature`. Any other `archon workflow run`. `isolation: worktree`. |
| Running tests | `.shared/harness.py` (used by `run_tests_mcp.py`) | Any other pytest or node test invocation by the pack. Use of the repository's pytest plugins or ini. |
| Interface view and stubs | `.shared/interface.py` | Stubs or views written by an agent. |
| Request completeness | `.shared/request.md` | A second list of required sections. |
| Owner-facing text | `.shared/notice.py` | `wait.attention` text written anywhere but from `notice.py` output. |
| Verdict and result shapes | The producing node's `output_format` | Any schema restated in Python or in a consuming node. |
| Gates | `make check` in the merge tree | Any narrowed gate. `IDLE_GATE=off`. |

## Order

Each step starts once the step before it is committed. Steps 7 to 10 start once `packcheck.py` exists (`workflow-builder-design.md:132`). A test file in a step goes to `test-writer` as that step's red test. Each stage workflow folder holds its YAML file, `commands/` and `fixtures/`.

1. `hqptuner-feature/.shared/fence.py`, `hqptuner-feature/.shared/guard.py` | `builder`; `tests/test_fence.py`, `tests/test_guard.py` | `test-writer`
2. `hqptuner-feature/.shared/trees.py` | `builder`; `tests/test_trees.py` | `test-writer`
3. `hqptuner-feature/.shared/harness.py`, `hqptuner-feature/.shared/run_tests_mcp.py`, `hqptuner-feature/.shared/run_tests.mcp.json` | `builder`; `tests/test_harness.py` | `test-writer`
4. `hqptuner-feature/.shared/interface.py` | `builder`; `tests/test_interface.py` | `test-writer`
5. `hqptuner-feature/.shared/stage.py` | `builder`; `tests/test_stage.py` | `test-writer`
6. `hqptuner-feature/.shared/request.md`, `hqptuner-feature/.shared/notice.py` | `builder`; `tests/test_notice.py` | `test-writer`
7. `tests/test_fence_sync.py`, checking every `hqptuner-feature/*/*.yaml` present | `test-writer`
8. `install.py` | `builder`; `tests/test_install.py` | `test-writer`
9. Phase 1, through `spec-gate`: `hqptuner-feature/hqp-plan/`, `hqptuner-feature/hqp-prosecute/`, `hqptuner-feature/hqp-spec/`, and `hqptuner-feature/hqptuner-feature/hqptuner-feature.yaml` nodes 1 to 8 with `phase-end`, with their `scripts/` and `fixtures/` | a fresh `workflow-builder`
10. Phase 2, through the first `merge-run`: `hqptuner-feature/hqp-write-tests/`, `hqptuner-feature/hqp-implement/`, and nodes 9 to 11 in `hqptuner-feature/hqptuner-feature/` | a fresh `workflow-builder`
11. Phase 3, through `merge-gate`: `hqptuner-feature/hqp-judge-red/`, `hqptuner-feature/hqp-review/`, and nodes 12 to 16 in `hqptuner-feature/hqptuner-feature/`, `phase-end` removed | a fresh `workflow-builder`
12. `README.md` | `builder`

## Decisions for the owner

1. **Whether each phase waits for a live run.** Recommended: the next phase's `workflow-builder` is dispatched only after you, or a lead on your word, run the installed pack on a real request through the previous phase's `phase-end`. Alternative: each phase starts once the previous one is committed with `packcheck.py` green, and the first live run comes after phase 3. Cost of the recommendation: your time on two live runs, each through the plan and spec gates, and their agent cost (not measured); the build waits on them. Cost of the alternative: faults only a live run shows (real agent output, sandbox and hook behaviour) surface after all three phases are built.
