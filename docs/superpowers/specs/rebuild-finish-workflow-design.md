Status: approved.

## Why

HQPTuner's rebuild-integrate refactor has four steps left: 12a, 12b, 12c and 13 (`hqptuner2/docs/superpowers/specs/rebuild-integrate-design.md:122-129`; every `hqptuner2/` path is under `/home/atom/dev/hqptuner2`). This pack carries them to the end in the worktree `/home/atom/dev/hqptuner2/.claude/worktrees/integrate`, on `rebuild/integrate`, without anyone watching. The loop also builds the pack core it runs on, as its first stages. It halts only on a product choice that has no recommended answer and no basis in the merged code or the approved documents.

What the tree holds for this today, and the copies a new workflow would otherwise make:

- **Gate invocation, 3 forms.** The core target sets `gate = ["make", "check"]` (`hqptuner-archon-workflow-design.md:30`, at HEAD). HQPTuner runs every gate through `scripts/gate.sh` and needs `PYTHONPATH=$(pwd)` in a worktree (`hqptuner2/CLAUDE.md:57`, `:74`). Its queue writes the JS check out by hand (`hqptuner2/docs/queue.md:344`). Each of the three misses something the others hold.
- **Progress record, 2 places, neither complete.** The queue marks only `landed 7` and `landed 11` (`hqptuner2/docs/queue.md:3-4`). It has no section for 12a, 12b, 12c or 13. Its step-12 section is cut as `port` dispatches, which 12a forbids until the baseline is green (`hqptuner2/docs/queue.md:344`, `rebuild-integrate-design.md:122-129`). The baseline log it keeps is under `/tmp` (`hqptuner2/docs/queue.md:344`), which does not survive a reboot.
- **Worktree handling.** The core cuts and removes every tree it uses (`hqptuner-archon-workflow-design.md:55-70`, at HEAD). The integrate worktree holds uncommitted work that 12a must keep (`rebuild-integrate-design.md:122-129`). It also holds an untracked `uv.lock` and an untracked copy of `rebuild-integrate-design.md` that is byte-identical to the copy `v2` tracks. That untracked copy makes a merge of `v2` refuse.
- **Commit rule.** HQPTuner requires `make check` green before every commit (`hqptuner2/CLAUDE.md:56`). The owner's ruling lets a dispatch commit on a red tree when its own section is green. Pre-commit still runs, unbypassed (`hqptuner2/CLAUDE.md:56`). Nothing in either repository defines "section green".
- **Pack core not built.** The only tracked pack file is `feature-pipeline/feature/feature.yaml` with its fixtures. The core modules (`hqptuner-archon-workflow-design.md:19-154`, at HEAD) do not exist yet. The loop builds them in `finish-bootstrap` before any finish stage runs.
- **Shared code stays inside one pack.** `.shared/` is shared within one pack only (`docs/reference/archon/workflow-language.md:50`). So these workflows go in `feature-pipeline/` and build on its core.
- **Sandbox needs `socat`, which is absent.** The sandbox covers Bash only and needs `socat` (`docs/host-facts.md:10`). The core's `install.py` refuses when `socat` is missing (`hqptuner-archon-workflow-design.md:154`, at HEAD). So no writing role in this design gets Bash.
- **Step 13 is not a fast-forward.** `v2` is 2 commits ahead of `rebuild/integrate` (`def39bff`, `d16b9dee`). Both branches touch `.pre-commit-config.yaml`, `CLAUDE.md` and `docs/spec/faceplate.md`. Merging `v2` is a routine step, and a resolver stage takes any conflict.
- **Plan and test review, 2 forms in the core, neither mechanical.** The core reviews a plan with `feature-prosecute` rounds (`hqptuner-archon-workflow-design.md:177`, at HEAD) and a spec with the Arbiter (`:181`), both agent judgments. Nothing checks a cut for gaps, duplicates, cycles, fence breaches or false quotes before writers run.
- **Decision 1 is settled.** A dial that times out with no answer is inconclusive, `address_found: null` (`hqptuner2/docs/superpowers/specs/rebuild-integrate-design.md:131-133`). Backend-fields already serves `null`, so no code change follows from it. Any api.md text that states the value (`:89`) is written as `null`.

## Modules

All paths are under `feature-pipeline/` unless they start at the repository root. Each module below extends a core module or adds a new one. Every concern in the core's Homes table (`hqptuner-archon-workflow-design.md:213-227`, at HEAD) still holds.

**`targets/hqptuner.toml`** (extended): adds the gate wrapper, the worktree environment, the owner-only paths, the never-commit paths and one queue run. Its values:

```toml
gate_wrap = ["scripts/gate.sh"]
worktree_env = { PYTHONPATH = "{tree}" }          # {tree} is the tree's root, filled by target.py
owner_only = []                                   # the changelog and user-facing text paths of hqptuner2/CLAUDE.md:10, :58
never_commit = ["uv.lock"]

[queue_run.rebuild-finish]
design = "docs/superpowers/specs/rebuild-integrate-design.md"
queue = "docs/queue.md"
queue_section = "s4.2kc"
worktree = "/home/atom/dev/hqptuner2/.claude/worktrees/integrate"
branch = "rebuild/integrate"
steps = ["12a", "12b", "12c", "13"]
settled = { "1" = "a dial that times out with no answer is inconclusive: address_found is null" }   # decisions settled outside the design file, passed to every stage
```

**`.shared/target.py`** (extended): reads the new keys. The wrapper and the environment are applied here, so no caller builds a gate command.

```python
@dataclass(frozen=True)
class QueueRun:
    name: str
    design: Path            # relative to the repo
    queue: Path
    queue_section: str
    worktree: Path
    branch: str
    steps: tuple[str, ...]
    settled: dict[str, str]

# Target gains:
#   gate_wrap: tuple[str, ...]; worktree_env: dict[str, str]
#   owner_only: tuple[str, ...]; never_commit: tuple[str, ...]
#   queue_runs: dict[str, QueueRun]
def wrapped(t: Target, argv: list[str], tree_root: Path) -> tuple[list[str], dict[str, str]]: ...
# gate_wrap + argv, and os.environ updated with worktree_env filled for tree_root
```

**`.shared/trees.py`** (extended): adds an adopted tree, `queue`, which is never cut or removed. It also adds the run record root, merge-in, the untracked-copy clear and a commit that refuses instead of bypassing.

```python
RECORDS = RUN_ROOT / "records"

class CommitRefused(Exception):
    output: str             # the pre-commit or git output, verbatim
    hook: str | None        # the failing hook id, parsed from the output

def adopt(name: str, run: str) -> Path: ...
# binds TREES[name] to target.queue_runs[run].worktree; refuses when that worktree is
# missing or not on the run's branch; remove_all() and cut() never touch an adopted tree
def status(name: str) -> list[str]: ...                   # `git status --short` lines
def merge_in(name: str, branch: str) -> MergeResult: ...  # `git merge --no-ff <branch>`; leaves conflicts in place
@dataclass(frozen=True)
class MergeResult:
    commit: str | None      # None while conflicts remain
    conflicts: list[str]
def finish_merge(name: str, message: str) -> str: ...     # commits a resolved merge; same refusals as commit()
def clear_untracked_copy(name: str, path: str, ref: str) -> bool: ...
# deletes the untracked file only when its bytes equal `<ref>:<path>`; False and no change otherwise
@contextmanager
def with_reverted(name: str, paths: list[str], ref: str) -> Iterator[None]: ...
# writes each path's bytes at `<ref>:<path>` into the tree (deleting a path absent at ref), yields,
# then puts back the exact bytes each path held before, on exit and on any exception
# commit() (core signature kept): never passes --no-verify and never sets SKIP; refuses any
# target.never_commit path; raises CommitRefused when a hook or git refuses
```

**`.shared/harness.py`** (extended): JS tests and the whole gate run through `target.wrapped`. Every log is kept under `trees.RECORDS`.

```python
def run_js_tests(tree: str, files: list[str]) -> list[TestOutcome]: ...   # now via target.wrapped
@dataclass(frozen=True)
class GateResult:
    exit_code: int
    log: Path               # under trees.RECORDS/<run_id>/
    outside: bool           # exit 126 or 127: the gate could not run
def run_gate(tree: str, run_id: str, argv: list[str] | None = None) -> GateResult: ...
# argv defaults to target.gate; any other argv is a queue-section check read from the target
```

**`.shared/run_tests_mcp.py`** (extended): gains `--tree <name>`, which defaults to `tests`. The finish stages start it with `--tree queue`.

**`.shared/fence.py`** (extended): adds three roles. None of them has Bash, so `sandbox_block` writes nothing for them.

```python
# ROLE_OF gains:
#   "repairer": write target.tests in TREES["queue"]
#   "coder":    write target.source in TREES["queue"], excluding target.tests
#   "resolver": write TREES["queue"] minus target.protected; a diff_gate against the conflict list follows each run
```

**`install.py`** (extended): gains `--workflows <name>...`. It installs `.shared/` plus only the named workflows. It refuses on a missing `socat` only when a named workflow has a fenced role with Bash.

**`.shared/record.py`** (new): the run record, one JSON line per event in `trees.RECORDS/<run_id>.jsonl`. It is the only progress record for a run. `docs/queue.md` is read, never written.

```python
def chosen(run_id: str, step: str, choice: str, reason: str) -> None: ...
def progress(run_id: str, step: str, item: str, state: Literal["started", "green", "parked", "failed"], commit: str | None = None) -> None: ...
def park(run_id: str, step: str, item: str, ask: "stoprule.Ask") -> None: ...
def read(run_id: str) -> list[dict]: ...
```

**`.shared/stoprule.py`** (new): pure functions. They decide whether a stage's question halts the run. Every stage answer that raises a question carries an `Ask`. Stages are told to recommend whenever the approved documents, the queue run's `settled` table or the merged code give a basis.

```python
@dataclass(frozen=True)
class Ask:
    question: str
    product: bool           # what the product does for its user; False for every technical choice
    recommend: str | None   # the step the stage would take
    basis: list[str]        # path:line quotes from the approved documents, settled entries or merged code that back recommend
    merge_conflict: bool    # raised while resolving a merge

@dataclass(frozen=True)
class Halt:
    ask: Ask

@dataclass(frozen=True)
class Chosen:
    choice: str
    reason: str

def settle(ask: Ask) -> Halt | Chosen: ...
# Halt only when product is set, merge_conflict is not, recommend is None and basis is empty:
# a product choice with no recommended answer and no basis in the merged code or the approved documents.
# Every other ask returns Chosen: recommend, or the stage's obvious step, and the driver logs it as CHOSEN.
# A technical ask with no recommend goes back to its stage once for one; the second time it is a fault.
def owner_text(changed: list[str], owner_only: tuple[str, ...]) -> list[str]: ...   # the changed paths that only the owner may write
```

A change to an `owner_text` path stands only with a `basis` quote for its exact text, from the approved documents or the merged code. Without a basis, the stage must raise an `Ask` with `product` set and `recommend` unset. The exception is a merge resolution, which is always taken.

**`.shared/section.py`** (new): defines "section green" for each commit. All of it is pure except `snapshot`.

```python
@dataclass(frozen=True)
class Snapshot:
    commit: str
    js: dict[str, Outcome]          # every JS test file -> outcome
    py: dict[str, Outcome] | None   # every offline pytest id, when the dispatch touches Python

def snapshot(tree: str, python: bool) -> Snapshot: ...      # harness.run_js_tests on all files, harness.run_tests when python
def green(before: Snapshot, after: Snapshot, named: list[TestOutcome]) -> list[str]: ...
# the breaches: each named test not passing, and each file or id that passed in before and does not pass in after; empty = green
def red_on_assertion(named: list[TestOutcome]) -> list[str]: ...
# the breaches: each named test whose outcome is not "fail", or whose exc_type is an import, module-resolution
# or syntax error; empty = a valid red test
def reverts_red(tree: str, tests: list[str], production: list[str], start: str) -> list[str]: ...
# inside trees.with_reverted(tree, production, start): harness.run_js_tests on tests;
# the breaches: each test that does not fail there; empty = the production change is what makes the tests pass
```

A commit by a finish workflow happens only when `section.green` is empty and `trees.commit` returns. The rest of the tree may be red. The cost of a whole-suite snapshot per dispatch is unmeasured.

**`.shared/cutcheck.py`** (new): pure functions over the whole plan at once. The plan is the parsed outputs of `finish-plan`, `finish-audit` mode `sites` and `finish-adjudicate`, as dicts in those nodes' `output_format` shapes; no schema is restated here. Each function returns its breaches; empty = pass.

```python
def coverage(plan: dict, failing: list[str], sites: list[dict]) -> list[str]: ...
# each failing baseline file in exactly one item; each retired-shape site in exactly one port;
# each item whose route writes a test in exactly one spec; gaps and duplicates both breach
def order(plan: dict) -> list[str]: ...
# the graph from helper_of, consumers, specs[].helpers and port depends_on has no cycle,
# and each helper item comes before every user in order
def paths(plan: dict, fences: dict[str, tuple[str, ...]]) -> list[str]: ...
# fences: role -> absolute globs, from fence.ROLE_OF; each item's and port's paths sit inside the fence
# of the role its route writes with; two items or ports with no order path between them share no file
def quotes(plan: dict, lines: Callable[[str], list[str] | None], settled: dict[str, str]) -> list[str]: ...
# every quotes[], claims[].quotes[] and basis entry is `<path>:<line>[-<line>] <text>` or `settled:<n> <text>`;
# its text matches those lines, or that settled entry, word for word with whitespace collapsed;
# every claim with changed set carries at least one quote; lines(path) returns None for a missing file
def overlap(plan: dict) -> list[str]: ...
# no test file in two specs; no claim text in two specs; every helper a spec uses is a helper item;
# a fixture or builder named by two or more specs is a helper item, never written inside a spec's own file
def check(plan: dict, failing: list[str], sites: list[dict], fences: dict[str, tuple[str, ...]],
          lines: Callable[[str], list[str] | None], settled: dict[str, str]) -> list[str]: ...
# all five, concatenated
```

The driver binds `lines` to the `queue` tree's working files and to the queue run's design file.

**Stage workflows** (`feature-pipeline/<name>/`, each with its YAML, `commands/` and `fixtures/`). All of them run in the `queue` tree. Each one that may ask returns `asks[]` in the `Ask` shape.

| Workflow | Agent, model | Tools | Returns |
|---|---|---|---|
| `finish-plan` | planner, opus | Read, Grep, Glob | `{baseline_files[], check, ports[{id, sites[], baseline_files[], paths[], depends_on[]}], asks[]}`, read from the queue run's design steps 12a and 12b and its queue section |
| `finish-adjudicate` | step-12 lead, opus | Read, Grep, Glob | `{items[{id, test_file, test_id, cause: stale_test\|production_defect\|helper\|contract_mismatch, helper_of, consumers[], route: repair\|red_then_build\|contract\|fixture, paths[], spec, quotes[]}], specs[{id, test_file, items[], claims[{text, changed, quotes[]}], helpers[]}], order[], asks[]}`; every test spec for the whole plan, written together: one spec per test file, its claims, and the helper items it builds on; a fixture or builder two specs need is its own item, cause `helper` and route `fixture`; helpers come before their users in `order` |
| `finish-review` | reviewer, opus | Read, Grep, Glob | `{findings[{item, kind: defect_as_stale\|unsupported_claim\|overlapping_tests\|single_use_structure\|gap, text, quotes[]}]}`; its prompt holds only the queue run's design file, the 12a gate log and the plan, with no `asks` and no record lines; it hunts above all a production defect filed as a stale test |
| `finish-repair` | repairer, sonnet | Read, Grep, Glob, Edit, Write, `mcp: run_tests` | `{status: complete\|blocked, files[], asks[]}`; writes only what its item's spec states, using the spec's helper items; mode `fixture` writes one shared fixture or builder that specs list in `helpers[]`, and nothing else; mode `repair` keeps the test's claims; mode `red` writes a failing test from the spec; mode `contract` changes a claim only as its spec's quotes establish |
| `finish-build` | coder, sonnet | Read, Grep, Glob, Edit, Write, `mcp: run_tests` | `{status, files[], asks[]}`; fixes a production defect against its red test |
| `finish-port` | coder, sonnet | Read, Grep, Glob, Edit, Write, `mcp: run_tests` | `{status, files[], asks[]}`; ports one site set to its new shape |
| `finish-audit` | auditor, opus | Read, Grep, Glob | mode `diff`: `{findings[{path, line, kind: skip\|relaxed_assertion\|compat_reader\|claim_changed, text}]}`; mode `sites`: `{sites[{path, line, shape}]}` of retired shapes left |
| `finish-resolve` | resolver, opus | Read, Grep, Glob, Edit, Write | `{resolved[], asks[]}`; resolves only the merge's conflict hunks |
| `finish` | none with tools; tool-less judges only | none | `{outcome: landed\|halted\|fault, landed_commit, record}`; `outcome_field: outcome` |

**`finish-bootstrap/finish-bootstrap.yaml`**: the loop's first stages, and its only part that exists before the loop runs. It has to exist because every other finish workflow imports `.shared/` and is installed by `install.py`, and neither exists until the loop builds them. It holds no logic beyond the nodes below. It builds the pack core and this design's extensions in this repository, installs the pack, and starts `finish`. It runs before `.shared/` exists, so it uses only Archon's own `bash:` and agent nodes. Until `install.py` exists, it is the one home for `git`, `pytest` and `packcheck` runs.

- **Launch.** The loop is started by copying `feature-pipeline/finish-bootstrap/` to `~/.archon/workflows/feature-pipeline/finish-bootstrap/` and running `archon workflow run finish-bootstrap`. This is the only copy into `~/.archon/workflows/` that `install.py` does not make. The bootstrap's own install later replaces it.
- **Tree.** A `bash:` node adds the worktree `/home/atom/.archon/finish-bootstrap/tree` on branch `finish/core`, cut from `main`. A restarted run reuses it.
- **Specs.** Before any part, a spec agent node (opus; Read, Grep, Glob) returns the test specs of every part at once: per part, its test files and its claims, each claim with the design `path:line` it rests on; and the shared fixtures, each with one file under `tests/` and built by the first part that uses it. A reviewer agent node (opus; Read, Grep, Glob) then gets only the two design files and the specs. It returns findings of overlapping tests, structure built for one claim, and claims the designs do not state. Findings go back to the spec node, with 2 attempts. After that, the run ends as `fault`.
- **Parts.** One part per core step, built to the core design's text, in its order: `hqptuner-archon-workflow-design.md:234-236`, `:239`, `:242-245`, `:248`, at HEAD. The core's live-run gate between phases holds for its workflow steps, not for these modules. Then this design's extensions follow, one part each, in this order:
  1. `targets/hqptuner.toml` and `target.py`: the new keys and `wrapped`.
  2. `trees.py`: `RECORDS`, `CommitRefused`, `adopt`, `status`, `merge_in`, `finish_merge`, `clear_untracked_copy`, `with_reverted`, and the `commit` refusals.
  3. `harness.py` and `run_tests_mcp.py`: `run_js_tests` through `wrapped`, `run_gate`, and `--tree`.
  4. `fence.py` and `install.py`: the three roles and `--workflows`.
  5. `record.py`.
  6. `stoprule.py`.
  7. `section.py`, with `red_on_assertion` and `reverts_red`.
  8. `cutcheck.py`.

  Each part names its module paths and its test files under `tests/`.
- **Per part, in this order:**
  1. A test-writer agent node (sonnet; Read, Grep, Glob, Edit, Write) writes the part's test files and any shared fixture the specs assign to the part, from the specs only.
  2. A `bash:` node requires those tests to fail. Where the part's modules exist at its start, each failure is a failed assertion, not a collection, import or syntax error.
  3. A builder agent node (sonnet; same tools) writes the part's module paths.
  4. A `bash:` node requires four things. The part's tests pass under `uv run pytest`. No test in `tests/` that passed at the part's start fails. `uv run packcheck.py feature-pipeline` exits 0. With the part's module paths put back to the part's start commit, the part's tests fail; the builder's bytes are then restored.
  5. A `bash:` node checks that each agent changed only its own paths.
  6. A `bash:` node commits those paths by name. Pre-commit runs unbypassed.

  A failing check feeds its output back to the node that wrote the files, with 2 attempts per node. After that, the run ends as `fault`. No agent node has Bash.
- **Record.** The bootstrap writes `CHOSEN` and progress lines to `/home/atom/.archon/feature-run/records/bootstrap.jsonl`, in `record.py`'s shape. That path is `trees.RECORDS`.
- **Install.** Once every part is committed, `uv run install.py hqptuner --workflows finish finish-plan finish-adjudicate finish-review finish-audit finish-repair finish-build finish-port finish-resolve` runs from the tree.
- **Land.** If `main` has not moved, `finish/core` lands on `main` with `--ff-only`, and only when `main`'s uncommitted changes touch none of the landed files. If `main` has moved, `main` is merged into `finish/core`. A resolver agent node (opus) takes any conflict and logs it as `CHOSEN`. Every part's tests run again, then the fast-forward follows. Nothing is pushed.
- **Start.** The last node starts `finish` through `stage.run_stage`.

**`finish/finish.yaml`**: the driver. It runs in the target repo with `worktree.enabled: false`. Its nodes, in order:

1. **adopt**: `trees.adopt("queue", "rebuild-finish")`. Records `trees.status("queue")`. Keeps every uncommitted change.
2. **plan**: `finish-plan`. Then `harness.run_gate("queue", run_id, check)` on `baseline_files`; the exact file list and the durable log go to the record. Then `finish-audit` mode `sites` for every retired-shape site.
3. **adjudicate**: `finish-adjudicate` on the failing files, the log, the sites and the ports. It returns the items and every test spec together. With no failing file, it returns no items and no specs.
4. **plan review**, over the whole set, before any writer runs:
   - `cutcheck.check` on the plan. Any breach goes back to node 3 with the breaches.
   - Then `finish-review`. Any finding goes back to node 3 with the findings.
   - Node 3 gets 2 returns. After that, the run ends as `fault`.
   - Every later pass of node 3 that adds or re-routes items is followed by this node, over the whole set, before the next writer runs.
5. **12a repair loop**, in `order`:
   - A `fixture`, `repair` or `contract` item goes to `finish-repair` in that mode.
   - A `red_then_build` item goes to `finish-repair` mode `red`, then `section.red_on_assertion` on its test, then `finish-build`, then `section.reverts_red` with the build's production files and the item's start commit. A breach goes back to the stage that wrote the files.
   - Before each commit: `finish-audit` mode `diff`, with any finding sent back to the stage; then `section.green`; then `trees.commit`.
   - A `contract` item whose quotes do not settle the contract carries an `Ask`. It is parked only when `stoprule.settle` returns `Halt`, and its dependants are parked with it.
   - Exit: every retained baseline file, plus the `consumers` of every repaired helper, run together through `harness.run_js_tests` with zero failures. `uv.lock` stays uncommitted.
6. **12b port loop**: `finish-port` for each port in `ports`, each starting by running its `baseline_files`. A failing baseline goes back to node 3 as new items. A port that depends on a parked item is parked. Each commit goes through the same gate as node 5. Exit: `finish-audit` mode `sites` returns no sites.
7. **asks**: if any item is parked, a `wait` node shows every parked `Ask` in one `attention` message, with its quotes and recommendation. After the owner answers, the driver resumes at the earliest parked step.
8. **12c**: `harness.run_gate("queue", run_id)`, the whole `target.gate`, writing nothing. A red gate sends its failing files back to node 3.
9. **13 merge**:
   - `trees.clear_untracked_copy("queue", <design>, "v2")`.
   - `trees.merge_in("queue", "v2")`. On conflicts: `finish-resolve`, then `trees.diff_gate` against the conflict list, then `trees.finish_merge`. Every resolution is taken and written with `record.chosen`. No conflict reaches the owner.
   - Then `harness.run_gate` at that exact commit. Red goes back to node 3.
10. **land**: `trees.land(trees.head("queue"))` fast-forwards `v2`. Nothing is pushed.

Rules the driver applies at every node:

- **Asks.** Every stage `Ask` goes through `stoprule.settle`. A `Chosen` is written with `record.chosen` and taken. A `Halt` parks its item, and the run goes on with independent items.
- **Owner-only paths.** A changed path that `stoprule.owner_text` returns, outside node 9, goes back to its stage once for a `basis` quote. With no basis, it becomes an `Ask` with `product` set and `recommend` unset.
- **Refused commits.** On `trees.CommitRefused`, the driver checks whether the hook's failure already existed at the dispatch's start commit and lies outside its files. If so, the failure goes to node 3 as a new item. If not, it goes back to the same stage.
- **Loop cap.** Each item gets 2 attempts per stage. Then `finish-adjudicate` re-routes it once. Then the run ends with `outcome: fault` and the record, without asking a question.
- **Outside causes.** A `GateResult.outside`, or a `run_stage` status `failed` with no answer, ends the run as `fault`.
- **Restart.** Each step starts by running its exit check, and a green step is skipped. So a restarted run resumes from git and the record alone.

## Homes

| Concern | Home | Forbidden elsewhere |
|---|---|---|
| Gate wrapper, worktree `PYTHONPATH`, queue-run facts, owner-only and never-commit paths | `targets/hqptuner.toml`, read through `.shared/target.py`; applied by `target.wrapped` | `scripts/gate.sh`, `PYTHONPATH`, a worktree path or a branch name in any workflow YAML, command or script. A gate argv built anywhere else. |
| Adopted `queue` tree, merge-in, untracked-copy clear, commits | `.shared/trees.py` | `git merge`, `git commit`, `git rm`, `rm`, `git checkout`, `git restore`, `git stash` or `git worktree` run from any other script or YAML. `--no-verify`, `SKIP=` or `-n` anywhere. Committing a `never_commit` path. |
| Gate runs and their logs | `harness.run_gate` | Any other `make check`, `scripts/gate.sh` or node invocation. A log under `/tmp`. |
| Run progress and `CHOSEN` lines | `.shared/record.py`, under `trees.RECORDS` | Writes to `docs/queue.md` or any other repository file to record progress. A second record format. |
| Whether a question halts | `stoprule.settle` | A `wait` node, a `blocked` status or a halt that `settle` did not return. A stage prompt that leaves `recommend` unset when the documents, `settled` or the merged code give a basis. A merge conflict sent to the owner. |
| Decisions settled outside the design file | `settled` in the queue run of `targets/hqptuner.toml` | Re-asking a settled decision. Its value restated in a prompt or script. |
| Building the core before the pack is installed | `finish-bootstrap` | `git`, `pytest` or `packcheck` run by any other workflow before `install.py` exists. Any other copy into `~/.archon/workflows/` than its one launch copy. |
| Section green | `section.green` | A commit by a finish workflow without an empty `green` result. Any other before-and-after comparison. |
| Mechanical plan check: coverage, order, paths, quotes, test overlap | `.shared/cutcheck.py` | A second gap, duplicate, cycle, fence or quote check. A writer stage run while `cutcheck.check` has breaches for the current plan. |
| Adversarial plan review | `finish-review`, once per plan pass, over the whole set | A review per item. Planner reasoning, `asks` or record lines in its prompt. A writer stage run while it has findings for the current plan. |
| Test specs | `specs[]` of `finish-adjudicate`, written with the items; in the bootstrap, its spec node | A test spec written per item or by a writer stage. A test file, claim or fixture outside the specs. A fixture or builder two specs need written anywhere but its `helper` item. |
| Red and revert checks | `section.red_on_assertion`, `section.reverts_red` | A red test accepted on `error` or an import, module-resolution or syntax failure. A build accepted without the revert check. |
| Test-change legitimacy | `finish-audit` mode `diff` | A skip, a relaxed assertion, a compatibility reader, or a changed claim without quotes, in any commit. |
| Owner-facing text | the `asks` `wait` node's `attention` message | Any other message to the owner. |

## Order

Each step starts once the step before it is committed. `packcheck.py` is each step's done-check (`docs/superpowers/specs/workflow-builder-design.md:89`). The `.shared/` modules, `targets/` and `install.py` are not Order steps. `finish-bootstrap` writes them when the loop runs.

1. `feature-pipeline/finish-bootstrap/` | a fresh `workflow-builder`
2. `feature-pipeline/finish-plan/`, `feature-pipeline/finish-adjudicate/`, `feature-pipeline/finish-review/`, `feature-pipeline/finish-audit/` | a fresh `workflow-builder`
3. `feature-pipeline/finish-repair/`, `feature-pipeline/finish-build/`, `feature-pipeline/finish-port/`, `feature-pipeline/finish-resolve/` | a fresh `workflow-builder`
4. `feature-pipeline/finish/` | a fresh `workflow-builder`

Steps 2 to 4 reference `.shared/` scripts that exist only after the bootstrap runs. Whether `packcheck.py` resolves those references is unmeasured.

After step 4, the loop is started once with the launch copy and run described under `finish-bootstrap`. Everything after that runs unattended.
