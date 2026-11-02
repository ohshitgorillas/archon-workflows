Status: approved.

## Why

The tree holds no pack code. Each concern the pack's pieces share has one copy or a constraint that sets its home:

1. **Target facts.** The pack is generic; HQPTuner is its first target. The target's facts are its checkout and base branch (`~/dev/hqptuner2` on `v2`; promotion is the owner's, `~/dev/hqptuner2/CLAUDE.md:60`), the files no agent writes (`CHANGELOG.md`, `~/dev/hqptuner2/CLAUDE.md:58`; the pytest config, `~/dev/hqptuner2/pyproject.toml:56-78`), its testing policy, its gate (`~/dev/hqptuner2/Makefile:141`), its pytest marks (`~/dev/hqptuner2/pyproject.toml:98`) and its JS test command (`~/dev/hqptuner2/Makefile:132-139`). They sit in one target file in this repository: none in the pack's code, none in the target.
2. **Fence paths.** The spike's sandbox block uses relative globs (`docs/reference/archon/spike-sandbox-workflow.yaml:12-16`), which do nothing, and the sandbox fences Bash only. Every fence path is absolute and comes from one module.
3. **Checkout per agent.** A node has no `cwd`. A `workflow:` child with `isolation: worktree` gets a generated path and branch cut from `origin/<baseBranch>` (`docs/reference/archon/workflow-language.md:101`, `:2094-2116`). `--cwd <dir> --no-worktree` runs a whole run in a chosen directory (`docs/reference/archon/cli.md:290`), and only `--detach --json` output parses (`cli.md:278`, `:302`). One launcher runs each tool-bearing agent as its own run in a fixed worktree.
4. **Test running.** HQPTuner runs pytest three ways: the gate (`~/dev/hqptuner2/Makefile:82-83`), the ini (`~/dev/hqptuner2/pyproject.toml:56-78`) and mutmut (`pyproject.toml:98`). The pack runs tests through one runner with its own ini and no repository plugins (`~/dev/gauntlet/docs/design.md:175`, `:202`).
5. **Interface view.** The test writer and the Arbiter see signature-only stubs (`~/dev/gauntlet/docs/design.md:198`), generated once per plan.
6. **Gate text.** A wait node's attention message takes runtime references (`docs/reference/archon/approval-nodes.md:92`). Each gate node holds its own message.
7. **Result shapes.** The node that produces a result holds its shape (`docs/reference/archon/workflow-language.md:2629-2645`).

## Modules

The pack is `feature-pipeline/` at the repository root. Shared modules sit in `feature-pipeline/.shared/` (`workflow-language.md:50`). Each workflow is `feature-pipeline/<workflow>/<workflow>.yaml` with its own `scripts/`, `commands/` and at least one `fixtures/*.stubs.yaml` (`workflow-builder-design.md:124`). Scripts use `runtime: uv`. Each target is `targets/<name>.toml` at the repository root. One target is installed at a time, and runs are serial.

**`targets/hqptuner.toml`**: HQPTuner's facts, the only place they appear.

```toml
repo = "/home/atom/dev/hqptuner2"
base_branch = "v2"
source = "hqptuner"
tests = "tests"
requests = "docs/requests"
testing_policy = "docs/spec/testing.md"
protected = ["conftest.py", "pyproject.toml", "package.json", "Makefile",
             "scripts/pytest_plugins/", "CHANGELOG.md"]
gate = ["make", "check"]
pytest_marks = "not live and not e2e"
js_test = ["node", "--import", "./tests/js/support/vendor-resolve.js", "--test"]
```

**`.shared/target.py`**: the one reader of a target file.

```python
@dataclass(frozen=True)
class Target:
    name: str                     # the target file's stem
    repo: Path
    base_branch: str
    source: str                   # source package dir, relative to repo
    tests: str
    requests: str
    testing_policy: str
    protected: tuple[str, ...]
    gate: tuple[str, ...]         # argv, run in a tree's root
    pytest_marks: str
    js_test: tuple[str, ...]      # argv prefix for JS test files; empty means the target has none

def load(path: Path | None = None) -> Target: ...   # default: the installed pack's .shared/target.toml
```

**`.shared/trees.py`**: the run's fixed worktrees and the git work on them. Phase 1 builds `cut`, `head`, `commit` and `remove_all`; phase 2 adds `changed_paths`, `diff_gate`, `tests_digest` and `merge_tests`; phase 3 adds `land`.

```python
RUN_ROOT = Path("/home/atom/.archon/feature-run")
TREES = {"base": RUN_ROOT / "base", "tests": RUN_ROOT / "tests",
         "impl": RUN_ROOT / "impl", "merge": RUN_ROOT / "merge"}

def cut(name: str, branch: str, start: str) -> Path: ...   # removes any stale worktree at TREES[name], then `git -C <repo> worktree add` it fresh
def head(name: str) -> str: ...
def commit(name: str, paths: list[str], message: str) -> str: ...
def remove_all() -> None: ...
def changed_paths(name: str, since: str) -> list[str]: ...
def diff_gate(name: str, since: str, allowed: Callable[[str], bool]) -> list[str]: ...   # the paths that break the rule; empty means pass
def tests_digest(name: str) -> str: ...                   # git tree hash of the target's tests dir
def merge_tests(tests_commit: str) -> str: ...            # merge tree = impl HEAD with the tests dir from tests_commit; returns the commit
def land(commit: str) -> str: ...                         # `merge --ff-only` into base_branch at repo; refuses a dirty repo or one not on base_branch
```

**`.shared/fence.py`** (phase 2): the read, write and deny roots of the two writing roles, built from `target.load()` and `trees.TREES`. Replaces the relative globs at `spike-sandbox-workflow.yaml:15-16`.

```python
Role = Literal["writer", "implementer"]
ROLE_OF: dict[str, Role] = {"feature-write-tests": "writer", "feature-implement": "implementer"}

@dataclass(frozen=True)
class Fence:
    read: tuple[Path, ...]            # absolute roots Read/Grep/Glob may touch
    write: tuple[Path, ...]           # absolute roots Edit/Write may touch
    deny: tuple[Path, ...]            # absolute roots denied to every tool, inside read roots too

def protected() -> tuple[str, ...]: ...      # target.protected plus interface.INTERFACE_DIR
def fence(role: Role) -> Fence: ...
def sandbox_block(role: Role) -> dict: ...   # the `sandbox:` mapping for that role, absolute paths only
```

- `writer`: reads the tests tree's tests dir, `.interface/` and testing policy; the request and the spec reach it as stage inputs. Writes the tests tree's tests dir only. The tests tree's source dir is in `deny`.
- `implementer`: reads the impl tree. Writes the impl tree outside the tests dir and `protected()`.
- Both have the target repo and the other trees in `deny`.
- The read-only roles (planner, prosecutor, spec writer, juror, reviewer) hold Read, Grep and Glob only, in their own tree, and carry no fence.

**`.shared/guard.py`** (phase 2): the PreToolUse hook for Read, Grep, Glob, Edit and Write on the writing roles. It checks the structured path in the tool input against `fence(role)` and refuses with the reason.

```python
def decide(role: Role, tool: str, tool_input: dict) -> tuple[Literal["allow", "deny"], str]: ...
def main() -> int: ...   # reads the hook payload on stdin and prints the PreToolUse decision
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

**`.shared/harness.py`** (phase 2): the only test runner the pack uses.

```python
Outcome = Literal["pass", "fail", "error"]

@dataclass(frozen=True)
class TestOutcome:
    test_id: str
    outcome: Outcome
    exc_type: str | None

def run_tests(tree: str, test_ids: list[str] | None = None) -> list[TestOutcome]: ...
# own ini written to RUN_ROOT/pytest.ini (pythonpath read from the tree's pyproject.toml, testpaths = target.tests),
# `-c <ini> --confcutdir=<target.tests> -m <target.pytest_marks> -p no:cacheprovider`, PYTEST_DISABLE_PLUGIN_AUTOLOAD=1,
# junit XML parsed to outcomes; prints no traceback and no output
def run_js_tests(tree: str, files: list[str]) -> list[TestOutcome]: ...   # target.js_test + files, in the tree's root
```

**`.shared/run_tests_mcp.py`** (phase 2), with **`.shared/run_tests.mcp.json`**: a stdio MCP server with one tool, `run_tests(test_ids)`, on the tests tree. It is the writer's only route to running anything against the real source. It calls `harness.run_tests("tests", ids)` or `harness.run_js_tests` and returns `[{test_id, outcome, exc_type}]`.

**`.shared/interface.py`**: builds the interface view and the stubs from the plan.

```python
INTERFACE_DIR = ".interface"      # inside the tests tree, outside the source dir

@dataclass(frozen=True)
class Surface:
    module: str                   # e.g. "hqptuner/engine/foo.py" or "hqptuner/static/x.js"
    names: list[str]              # public names the plan adds or changes

def view(tree: str, surfaces: list[Surface]) -> Path: ...    # .pyi via stubgen, .d.ts via tsc --allowJs --declaration --emitDeclarationOnly,
                                                               # trimmed to `names`, written to <tree>/INTERFACE_DIR/
def stub(tree: str, surfaces: list[Surface]) -> list[str]: ...  # adds the new names to the tree with bodies that raise NotImplementedError / throw; returns paths
```

**`.shared/request.md`**: the request template. Its sections are Goal, Behaviour (observable, one item per line), Examples, Out of scope and Surfaces touched. The intake session writes `<repo>/<requests>/<slug>.md` to it, and `check-request` judges against it.

**`install.py`** (repository root): `uv run install.py <target>`. It copies `feature-pipeline/` to a temporary directory, writes `targets/<target>.toml` there as `.shared/target.toml`, and writes into every agent node of each workflow in `fence.ROLE_OF` the `sandbox:` block `fence.sandbox_block(role)`. It runs `packcheck.check` (`workflow-builder-design.md:89`, `:112`) on that copy and refuses on any failure, then replaces `~/.archon/workflows/feature-pipeline/` with it. It runs no `archon validate` of its own and refuses when `socat` is missing. Phase 1 builds it without the sandbox step; phase 2 adds the step.

**Workflows.** Each stage workflow pins `worktree.enabled: false` and gives each agent node `provider: claude`, a named model, effort `medium`, `context: fresh` and `allowed_tools`. The writing stages' agent nodes also carry the `guard.py` hook for their role. No source YAML holds a `sandbox:` block. Each `returns:` names a node with `output_format`.

| Workflow | Phase | Runs in | Agent, model | Tools | Returns |
|---|---|---|---|---|---|
| `feature` | 1 to 3 | the target repo, `worktree.enabled: false` | none with tools; `check-request` and `arbiter` are tool-less judge prompts (`allowed_tools: []`) on opus | none | `{outcome, landed_commit, reason}`; `outcome_field: outcome` |
| `feature-plan` | 1 | base tree | planner, opus | Read, Grep, Glob | `{plan, surfaces[], steps[]}` |
| `feature-prosecute` | 1 | base tree | prosecutor, opus | Read, Grep, Glob | `{checks[{id, verdict: PASS\|FAIL\|COULD_NOT_JUDGE, reason}]}` |
| `feature-spec` | 1 | base tree | spec writer, opus | Read, Grep, Glob | `{lines[{id: S<n>, behaviour, start: RED\|GREEN}]}` |
| `feature-write-tests` | 2 | tests tree | test writer, sonnet | Bash, Read, Grep, Glob, Edit, Write, `mcp: run_tests` | `{bindings[{line, test_ids[]}]}` |
| `feature-implement` | 2 | impl tree | implementer, sonnet | Bash, Read, Grep, Glob, Edit, Write | `{status: complete\|blocked, reason}` |
| `feature-judge-red` | 3 | merge tree | juror, opus | Read, Grep, Glob | `{verdicts[{test_id, line, side: build_wrong\|tests_wrong\|spec_wrong\|undetermined, reason}]}` |
| `feature-review` | 3 | merge tree | diff reviewer, sonnet; sees the diff and the request only | Read, Grep, Glob | `{findings[{path, line, severity: blocking\|note, text}]}` |

Every node in `feature` and every read-only stage node has `mutates_checkout: false`.

**`feature` nodes**, in DAG order. Input: `request`, a path under `<repo>/<requests>/`. Each `wait` node's `attention` message is written in that node, from runtime references to the nodes it reports on.

Phase 1, through the owner's approval of the test spec:

1. `check-request`: a script binds the request text and `request.md`, and a judge returns `{complete, gaps[]}`. `cancel` with the gaps when incomplete.
2. `cut-base`: `trees.cut("base", "archon/feature-<slug>-base", target.base_branch)`.
3. `plan-1`, `prosecute-1`, then `plan-2` and `prosecute-2` with `when:` any check from round 1 is not `PASS`. If round 2 still fails, `cancel` with the failing checks. These are script nodes calling `run_stage`.
4. `plan-gate`: `wait`, `form: approval`, showing the plan and the last review. `reject` cancels the run, with the owner's text as the reason.
5. `interface`: `trees.cut("tests", …)`, `interface.stub("tests", surfaces)`, `interface.view("tests", surfaces)`, then `trees.commit` of the stubs and the view on the tests branch.
6. `spec`: `run_stage("feature-spec", "base", …)`.
7. `arbiter`: a judge with no tools. A script binds its prompt, which holds only the request, the spec, the interface view and the target's testing policy. It returns `{rulings[{line, verdict: ACCEPT\|REJECT, reason}]}`. On any `REJECT`, `spec` and `arbiter` run once more with the rulings. Any `REJECT` after that cancels the run.
8. `spec-gate`: `wait`, `form: approval`, showing the spec and the rulings. `reject` cancels the run, with the owner's text as the reason.

Phase 2, through the first `merge-run`:

9. `cut-impl`: `trees.cut("impl", "archon/feature-<slug>", target.base_branch)`.
10. `write-tests` and `implement` run in one layer.
    - `write-tests`: `run_stage("feature-write-tests", "tests", …)`, then `trees.diff_gate("tests", stubs_commit, under the tests dir and not in fence.protected())`. Every bound test must be `fail` or `error` on the stubs under `harness.run_tests("tests")`, except lines marked `GREEN`. The script commits the tests dir with `trees.commit` as the locked commit.
    - `implement`: `run_stage("feature-implement", "impl", …)`, then `trees.diff_gate("impl", base, not under the tests dir and not in fence.protected())`. Any breach fails the node.
11. `merge-run`: `trees.merge_tests(locked)`, then `harness.run_tests("merge")`. Green goes to node 15.

Phase 3, through `merge-gate`:

12. `juror`: `run_stage("feature-judge-red", "merge", …)` on the failing ids. Every failing id has exactly one verdict.
13. One repair, chosen by the juror's verdicts. A run with any `undetermined` verdict, or with verdicts of more than one side, goes to node 14.
    - `build_wrong`: `implement` runs once more, silently, with the failing ids, followed by its diff gate and `merge-run`.
    - `tests_wrong`: `write-tests` runs once more on the named tests. The Arbiter re-rules only the spec lines bound to the changed tests. Then `tests-diff-gate` (`wait`, `form: approval`, showing the diff and the rulings), a new locked commit, and `merge-run`.
    - `spec_wrong`: the affected lines are replanned with `feature-plan`. `feature-prosecute` re-reviews only those lines. Then `replan-gate` (`wait`, `form: approval`, showing the replanned lines and the review), `feature-spec` and the Arbiter for those lines, `write-tests` and `implement` for those lines, and `merge-run`.
    - A red `merge-run` after the repair goes to node 14.
14. `undetermined-gate`: `wait`, `form: select`, giving both sides with the verdicts and outcomes. The options are `build-wrong`, `tests-wrong`, `spec-wrong` and `abandon`, and the owner's answer may carry a note. Picking a side runs that side's repair from node 13 once, with the note. A red `merge-run` after that pass, or `abandon`, cancels the run with both sides in the reason.
15. `verify`: `trees.tests_digest("merge")` equals the digest of the last locked commit, `target.gate` passes in the merge tree, and `feature-review` runs. Blocking findings appear on the merge gate and trigger no repair.
16. `merge-gate`: `wait`, `form: approval`, showing the diff stat, the gate result and the findings. On approve, `trees.land(merge_commit)`, then `trees.remove_all()`. On reject, the run is cancelled and the trees stay for inspection.

**Phase ends.**

- Phases 1 and 2 end in a script node `phase-end`, which `returns:` names while it exists. It returns `{outcome: "phase_end", landed_commit: null, reason}`, the reason naming the last node reached; after phase 2 that is `merge-run`, green or red, with the failing ids.
- `phase-end` removes no tree; the next run's `trees.cut` clears them.
- Phase 2 moves `phase-end` behind `merge-run`, both green and red. Phase 3 deletes `phase-end` and points `returns:` at the final node.
- Each phase keeps every earlier fixture passing, rewriting the reached-node list of each fixture that reached `phase-end`, and adds fixtures for its own routes.

## Homes

| Concern | Home | Forbidden elsewhere |
|---|---|---|
| Target facts: repo, base branch, source and tests dirs, requests dir, testing policy, protected set, gate, pytest marks, JS test command | `targets/<name>.toml`, read only through `.shared/target.py` | Any target fact in `feature-pipeline/` scripts, YAML, commands or prompts. Any pack file in the target repository. |
| Run paths `RUN_ROOT` and `TREES` | `.shared/trees.py` | Path literals in any other script or YAML. |
| Writing roles' fence roots | `.shared/fence.py` | A `sandbox:` block in source YAML. Any `sandbox:` block not written by `install.py` from `sandbox_block(role)`. |
| Tool path checks | `.shared/guard.py` | Any other PreToolUse hook. Any per-node path logic. |
| Worktree lifecycle, commits, diff gates, tests lock, landing | `.shared/trees.py` | `git worktree`, `git commit`, `git merge` or `git diff` run from any other script or YAML `bash:`. |
| Running an agent with tools | `.shared/stage.py` and the stage workflows | A tool-bearing agent node in `feature`. Any other `archon workflow run`. `isolation: worktree`. |
| Running tests | `.shared/harness.py` (used by `run_tests_mcp.py`) | Any other pytest or node test invocation by the pack. Use of the target's pytest plugins or ini. |
| Interface view and stubs | `.shared/interface.py` | Stubs or views written by an agent. |
| Request completeness | `.shared/request.md` | A second list of required sections. |
| Owner-facing text | each `wait` node's own `attention` message | A message module. Gate text built in a script. |
| Verdict and result shapes | The producing node's `output_format` | Any schema restated in Python or in a consuming node. |
| Gates | `target.gate` in the merge tree | Any narrowed gate. `IDLE_GATE=off`. |
| Installed pack | `install.py` | Any other copy into `~/.archon/workflows/`. |

## Order

The order is the three phases, each built by its own fresh `workflow-builder`. Phase 1 starts once `packcheck.py` exists (`workflow-builder-design.md:132`). Within a phase, each part starts once the part before it is committed. A test file in a part goes to `test-writer` as that part's red test. Each stage workflow folder holds its YAML file, `commands/` and `fixtures/`. A phase ends when the owner, or a lead on the owner's word, runs `install.py hqptuner` and a live run of the installed pack on a real request reaches `phase-end`; the next phase starts after that run.

1. **Phase 1, through `spec-gate`, before any test or code writing.**
   1. `targets/hqptuner.toml`, `feature-pipeline/.shared/target.py` | `builder`; `tests/test_target.py` | `test-writer`
   2. `feature-pipeline/.shared/trees.py` with `RUN_ROOT`, `TREES`, `cut`, `head`, `commit` and `remove_all` | `builder`; `tests/test_trees.py` | `test-writer`
   3. `feature-pipeline/.shared/stage.py` | `builder`; `tests/test_stage.py` | `test-writer`
   4. `feature-pipeline/.shared/interface.py` | `builder`; `tests/test_interface.py` | `test-writer`
   5. `feature-pipeline/.shared/request.md` | `builder`
   6. `install.py` without the sandbox step | `builder`; `tests/test_install.py` | `test-writer`
   7. `feature-pipeline/feature-plan/`, `feature-pipeline/feature-prosecute/`, `feature-pipeline/feature-spec/`, and `feature-pipeline/feature/feature.yaml` nodes 1 to 8 with `phase-end`, with their `scripts/` and `fixtures/` | a fresh `workflow-builder`
2. **Phase 2, through the first `merge-run`.**
   1. `feature-pipeline/.shared/fence.py`, `feature-pipeline/.shared/guard.py` | `builder`; `tests/test_fence.py`, `tests/test_guard.py` | `test-writer`
   2. `feature-pipeline/.shared/trees.py`: `changed_paths`, `diff_gate`, `tests_digest`, `merge_tests` | `builder`; `tests/test_trees.py` | `test-writer`
   3. `feature-pipeline/.shared/harness.py`, `feature-pipeline/.shared/run_tests_mcp.py`, `feature-pipeline/.shared/run_tests.mcp.json` | `builder`; `tests/test_harness.py` | `test-writer`
   4. `install.py`: the sandbox step | `builder`; `tests/test_install.py` | `test-writer`
   5. `feature-pipeline/feature-write-tests/`, `feature-pipeline/feature-implement/`, and nodes 9 to 11 in `feature-pipeline/feature/`, `phase-end` moved behind `merge-run` | a fresh `workflow-builder`
3. **Phase 3, through `merge-gate`.**
   1. `feature-pipeline/.shared/trees.py`: `land` | `builder`; `tests/test_trees.py` | `test-writer`
   2. `feature-pipeline/feature-judge-red/`, `feature-pipeline/feature-review/`, and nodes 12 to 16 in `feature-pipeline/feature/`, `phase-end` removed | a fresh `workflow-builder`
   3. `README.md` | `builder`
