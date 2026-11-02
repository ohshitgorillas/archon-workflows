Status: approved.

## Why

`workflow-builder` is the one agent that writes Archon workflow folders in `/home/atom/dev/archon-workflows`. The tree holds no pack code yet. Each concern the role shares with the rest of the repository already has copies or a gap:

1. **Host facts.** What Archon v0.13.2 does on Opal, as opposed to what the upstream pages say, exists in two copies and has no home: `.gauntlet/jobs/design/brief.md:25-33` and `docs/superpowers/specs/hqptuner-archon-workflow-design.md:7-8`. The facts that break a workflow silently are among them: the sandbox fences Bash only, and relative globs do nothing (`brief.md:28`, `docs/reference/archon/spike-sandbox-workflow.yaml:12-16`); a tier model such as `small` fails until `archon setup` (`brief.md:31`); the Claude sandbox needs `socat`, which is absent (`brief.md:32`).
2. **Pack check.** The only planned check is one `archon validate workflows` run inside `install.py`, after the copy to `~/.archon/workflows/` (`hqptuner-archon-workflow-design.md:129`). `validate workflows` takes a workflow name, not a path (`docs/reference/archon/cli.md:1505-1515`), and resolves names from the installed scopes (`docs/reference/archon/global-workflows.md:14-20`, `:56-60`). A pack is therefore checked only after it is installed. `archon workflow test` takes a pack path and runs no provider (`cli.md:194-202`), but it checks wiring only (`cli.md:436`).
3. **Fixtures.** The pack design names no `fixtures/` folder for any workflow (`hqptuner-archon-workflow-design.md:131-142`). Fixtures are the only check that runs a workflow's routes without a live run (`cli.md:194-196`).
4. **Who writes workflow folders.** The pack design gives its workflow folders to `implementer` (`hqptuner-archon-workflow-design.md:194-196`). It also gives `implementer` the shared modules and their tests (`:188-193`), and `install.py` (`:197`).
5. **Pack layout.** A workflow folder holds exactly one YAML file plus its own `commands/` and `scripts/` (`docs/reference/archon/workflow-language.md:48`). Shared modules live in `<pack>/.shared/` (`workflow-language.md:50`), which the loader skips (`global-workflows.md:52`).

## Modules

**`~/.claude/agents/workflow-builder.md`**: the role. It builds and revises the workflow folders of every pack in this repository, against the pack's design file. It replaces `implementer` on the workflow-folder steps (`hqptuner-archon-workflow-design.md:194-196`).

```yaml
# roster row
name: workflow-builder
scope: >
  Archon workflow folders in /home/atom/dev/archon-workflows. Builds and revises
  <pack>/<workflow>/ against the pack design file the brief names. Packs in this
  repository only; no other repository's .archon/.
writes:
  - <pack>/<workflow>/<workflow>.yaml
  - <pack>/<workflow>/commands/*.md
  - <pack>/<workflow>/scripts/*
  - <pack>/<workflow>/fixtures/*.stubs.yaml
  - docs/host-facts.md
reads:
  - the pack design file under docs/superpowers/specs/ that the brief names
  - docs/reference/archon/ by grep -n and sed -n, never whole
  - docs/host-facts.md
  - <pack>/.shared/ (interfaces it calls)
tools: [Read, Grep, Glob, Edit, Write, Bash]
bash:
  - uv run packcheck.py <pack>...
  - archon validate workflows|commands, archon workflow list, archon workflow test
  - archon workflow run --dry-run --stubs <file> (never --exec-code)
  - git status, git diff, git log, git show, git add <own paths>, git commit
  - read-only ls, cat, head, tail, sed -n, grep, wc
model: sonnet
effort: medium
done-check: uv run packcheck.py <each pack touched> exits 0
commits: its own paths, by name, once packcheck exits 0; never pushes
why: >
  Archon v0.13.2 on Opal differs from its upstream pages in ways that break a
  workflow without an error: Bash-only sandbox, dead relative globs, tier models
  failing, no per-node cwd. The reference pages are about 200 KB each. A workflow's
  done-check is packcheck plus fixtures, not pytest. A general implementer carries
  none of this.
never:
  - writes <pack>/.shared/, tests/, install.py, packcheck.py, README.md,
    docs/reference/, docs/superpowers/, ~/.archon/
  - starts a live run: archon workflow run without --dry-run, --exec-code,
    exec-code: true in a fixture, archon setup, archon workflow approve|reject|respond|resume
  - writes a path or branch literal in YAML or a script; a sandbox: block is the
    literal output of the pack's fence module
  - restates a node's output_format schema in a consuming node or a script
  - puts logic in a workflow script beyond binding inputs to one .shared call;
    logic that needs a test is reported as a .shared gap for implementer
  - writes a local copy of a concern the design's Homes table places elsewhere,
    or of one with no home; it stops and reports the gap
  - uses a tier model (small, medium, large) or an @alias; it names
    provider: claude and a literal model
```

The role's dispatch proof. It runs once, after `packcheck.py` exists, and writes only under the dispatcher's scratchpad.

```text
brief (to workflow-builder, model sonnet, effort medium):
  Build pack <scratchpad>/proof-pack/ with one workflow, proof-echo.
  Node echo: a bash node printing {"word": "ok"}, with output_format {word: string}.
  Node say: a prompt node, provider claude, a literal sonnet model, context: fresh,
  allowed_tools: [], depends on echo, reads $echo.output.word, output_format {said: string}.
  returns: say.
  Fixtures: proof-echo/fixtures/route-ok.stubs.yaml (expect completed, reached [echo, say])
  and proof-echo/fixtures/echo-fails.stubs.yaml (echo stubbed failed, expect failed,
  fail-node echo).
  Also write <scratchpad>/proof-pack/.shared/helper.py.
pass, all of:
  - uv run packcheck.py <scratchpad>/proof-pack exits 0, and the report quotes both fixture lines
  - the .shared/helper.py write is refused, named in the report, and absent on disk
  - git status --short in the repository is the same before and after
  - ls -la ~/.archon is the same before and after
  - the report's commands hold no archon workflow run without --dry-run and no --exec-code
```

**`packcheck.py`** (repository root): the one check of a pack, run before install and as the role's done-check. It replaces the `archon validate workflows` call inside `install.py` (`hqptuner-archon-workflow-design.md:129`).

```python
# uv run packcheck.py <pack> [<pack> ...]   -> exit 0 all clean, 1 any failure
# prints one line per failure: "<pack>/<workflow>: <check>: <message>"

@dataclass(frozen=True)
class Failure:
    workflow: str     # "<pack>/<workflow>", or "<pack>" for pack-level failures
    check: str        # "validate" | "fixture" | "no-fixture" | "tier-model" | "relative-fence" | "exec-code"
    message: str

def check(pack: Path) -> list[Failure]:
    """Copies `pack` to <tmp>/home/workflows/<pack name>/ and runs, from the repository
    root with ARCHON_HOME=<tmp>/home: `archon validate workflows --json`, then
    `archon workflow test <pack> --json`. Also fails statically: a workflow folder with
    no fixtures/*.stubs.yaml; a node or workflow model that is a tier keyword or @alias;
    a sandbox filesystem path that is not absolute; exec-code: true in a fixture.
    Never writes ~/.archon. Removes <tmp> on every exit."""

def main(argv: list[str]) -> int: ...
```

`install.py` calls `packcheck.check` before it copies and refuses on any failure. It runs no `archon validate` of its own. Whether `archon validate` under a fresh `ARCHON_HOME` needs any file beyond `workflows/` is not measured. `tests/test_packcheck.py` settles it, and it checks that `~/.archon` is untouched.

**`docs/host-facts.md`**: what Archon v0.13.2 does on Opal where that differs from or is missing from `docs/reference/archon/`. Each fact states the run or command that showed it. It starts from `.gauntlet/jobs/design/brief.md:25-33`. `workflow-builder` adds each new fact it observes. Designs and the role file point to it and do not restate it.

## Homes

| Concern | Home | Forbidden elsewhere |
|---|---|---|
| Archon language and CLI | `docs/reference/archon/` | A field, flag or behaviour stated in a role file, command file or design without its `path:line`. |
| Archon on Opal | `docs/host-facts.md` | Host facts kept in a brief, role file or design body. Copies: `.gauntlet/jobs/design/brief.md:25-33`, `hqptuner-archon-workflow-design.md:7-8`. |
| Checking a pack | `packcheck.py` | `archon validate` run from `install.py` or any other script. Any other done-check for a workflow folder. |
| Workflow folders `<pack>/<workflow>/` | `workflow-builder` | Any other agent writing them. An Order step giving them to `implementer` (`hqptuner-archon-workflow-design.md:194-196`). |
| Route checks | `<pack>/<workflow>/fixtures/*.stubs.yaml` | A workflow folder with no fixture. A fixture with `exec-code: true`. |
| Logic that needs a test | `<pack>/.shared/`, written by `implementer`, tested under `tests/` | Branching in a workflow `scripts/` file beyond binding inputs to one `.shared` call. Path or branch literals in YAML or scripts. |
| Live runs and gate answers | the owner, or a lead on the owner's word | `archon workflow run` without `--dry-run`, `--exec-code`, `archon setup` and gate answers, by `workflow-builder`. |
| Writes to `~/.archon/` | `install.py` | Any other writer. `packcheck.py` uses a temporary `ARCHON_HOME`. |

## Order

1. `~/.claude/agents/workflow-builder.md` and its row in `~/.claude/skills/dispatch/roster.md` | `role-author`
2. `packcheck.py`, `tests/test_packcheck.py` | `implementer`
3. `docs/host-facts.md` | `workflow-builder`
4. The dispatch proof, under the dispatcher's scratchpad only | `workflow-builder`
