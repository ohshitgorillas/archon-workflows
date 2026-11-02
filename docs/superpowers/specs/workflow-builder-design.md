Status: approved.

## Why

`workflow-builder` is the one agent that writes Archon workflow folders in `/home/atom/dev/archon-workflows`. The tree holds one pack, `.archon/workflows/feature-pipeline/`. Each concern the role shares with the rest of the repository has a home or a copy:

1. **Host facts.** What Archon v0.13.2 does on Opal, as opposed to what the upstream pages say, lives in `docs/host-facts.md`, with one copy at `.gauntlet/jobs/design/brief.md:25-33`. The facts that break a workflow silently are among them: the sandbox fences Bash only, and relative globs do nothing (`brief.md:28`, `docs/reference/archon/spike-sandbox-workflow.yaml:12-16`); a tier model such as `small` fails until `archon setup` (`brief.md:31`); the Claude sandbox needs `socat`, which is absent (`brief.md:32`).
2. **Pack check.** Its home is the "Checking the pack" row, `docs/superpowers/specs/rebuild-finish-archon-native-design.md:170`, with each step's done-check at `:174`. `validate workflows` takes a workflow name, not a path (`docs/reference/archon/cli.md:1505-1515`), and resolves names from the discovery scopes (`docs/reference/archon/global-workflows.md:14-20`, `:56-60`). A repository's `.archon/workflows/` is a scope from its root; a temporary `ARCHON_HOME` breaks both checks (`docs/host-facts.md:21-25`). `archon workflow test` runs no provider (`cli.md:194-202`) and checks wiring only (`cli.md:436`).
3. **Fixtures.** Fixtures are the only check that runs a workflow's routes without a live run (`cli.md:194-196`).
4. **Who writes workflow folders.** The `feature-pipeline` design gives each workflow folder to `workflow-builder` (`rebuild-finish-archon-native-design.md:176-180`).
5. **Pack layout.** A workflow folder holds exactly one YAML file plus its own `commands/` (`docs/reference/archon/workflow-language.md:48`) and `fixtures/` (`cli.md:196`). The pack's code is Archon nodes; its home is the "Pack code" row, `rebuild-finish-archon-native-design.md:169`. The pack is loaded with `--workflow-source` (`rebuild-finish-archon-native-design.md:168`).

## Modules

**`~/.claude/agents/workflow-builder.md`**: the role. It builds and revises the workflow folders of every pack in this repository, against the pack's design file. It replaces `implementer` on the workflow-folder steps.

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
  - <pack>/<workflow>/fixtures/*.stubs.yaml
  - docs/host-facts.md
reads:
  - the pack design file under docs/superpowers/specs/ that the brief names
  - docs/reference/archon/ by grep -n and sed -n, never whole
  - docs/host-facts.md
tools: [Read, Grep, Glob, Edit, Write, Bash]
bash:
  - archon validate workflows|commands, archon workflow list, archon workflow test
  - archon workflow run --dry-run --stubs <file> (never --exec-code)
  - git status, git diff, git log, git show, git add <own paths>, git commit
  - read-only ls, cat, head, tail, sed -n, grep, wc
model: sonnet
effort: medium
done-check: the done-check the pack design's Order step names, exits 0
commits: its own paths, by name, once the done-check exits 0; never pushes
why: >
  Archon v0.13.2 on Opal differs from its upstream pages in ways that break a
  workflow without an error: Bash-only sandbox, dead relative globs, tier models
  failing, no per-node cwd. The reference pages are about 200 KB each. A workflow's
  done-check is Archon's own validate and fixture test, not pytest. A general
  implementer carries none of this.
never:
  - writes <pack>/.shared/, <pack>/<workflow>/scripts/, tests/, a Python module
    or script, an install script, README.md, docs/reference/, docs/superpowers/,
    ~/.archon/
  - writes a checker script or runs any done-check other than the pack design's
  - starts a live run: archon workflow run without --dry-run, --exec-code,
    exec-code: true in a fixture, archon setup, archon workflow approve|reject|respond|resume
  - writes a path or branch literal in YAML; paths come from Archon variables
    (docs/reference/archon/workflow-language.md:2986) or the run's inputs
  - writes a sandbox: block; the Claude sandbox refuses to start without socat,
    which is absent (docs/host-facts.md:10)
  - restates a node's output_format schema in a consuming node
  - works around a feature Archon lacks with a script, module, MCP server or
    patch; it stops and reports the missing feature to the owner
  - writes a local copy of a concern the design's Homes table places elsewhere,
    or of one with no home; it stops and reports the gap
  - uses a tier model (small, medium, large) or an @alias; it names
    provider: claude and a literal model
```

The role's dispatch proof. It runs once, after the role file and its roster row exist, and writes only under the dispatcher's scratchpad. The dispatcher first runs `git init <scratchpad>/proof-repo`, so the pack sits in a discovery scope (`docs/host-facts.md:25`).

```text
brief (to workflow-builder, model sonnet, effort medium):
  Build pack <scratchpad>/proof-repo/.archon/workflows/proof-pack/ with one workflow, proof-echo.
  Node echo: a bash node printing {"word": "ok"}, with output_format {word: string}.
  Node say: a prompt node, provider claude, a literal sonnet model, context: fresh,
  allowed_tools: [], depends on echo, reads $echo.output.word, output_format {said: string}.
  returns: say.
  Fixtures: proof-echo/fixtures/route-ok.stubs.yaml (expect completed, reached [echo, say])
  and proof-echo/fixtures/echo-fails.stubs.yaml (echo stubbed failed, expect failed,
  fail-node echo).
  Also write <scratchpad>/proof-repo/.archon/workflows/proof-pack/.shared/helper.py.
pass, all of:
  - the done-check of rebuild-finish-archon-native-design.md:174, run from
    <scratchpad>/proof-repo for workflow proof-echo and pack proof-pack, exits 0,
    and the report quotes both fixture lines
  - the .shared/helper.py write is refused, named in the report, and absent on disk
  - git status --short in the repository is the same before and after
  - ls -la ~/.archon is the same before and after
  - the report's commands hold no archon workflow run without --dry-run and no --exec-code
```

**`docs/host-facts.md`**: what Archon v0.13.2 does on Opal where that differs from or is missing from `docs/reference/archon/`. Each fact states the run or command that showed it. It starts from `.gauntlet/jobs/design/brief.md:25-33`. `workflow-builder` adds each new fact it observes. Designs and the role file point to it and do not restate it.

## Homes

| Concern | Home | Forbidden elsewhere |
|---|---|---|
| Archon language and CLI | `docs/reference/archon/` | A field, flag or behaviour stated in a role file, command file or design without its `path:line`. |
| Archon on Opal | `docs/host-facts.md` | Host facts kept in a brief, role file or design body. Copy: `.gauntlet/jobs/design/brief.md:25-33`. |
| Checking a pack | the "Checking the pack" row, `rebuild-finish-archon-native-design.md:170`, and the done-check at `:174` | A checker script. Any other done-check for a workflow folder. The check's commands restated in a role file or design. |
| Workflow folders `<pack>/<workflow>/` | `workflow-builder` | Any other agent writing them. An Order step giving them to another agent. |
| Route checks | `<pack>/<workflow>/fixtures/*.stubs.yaml` | A workflow folder with no fixture. A fixture with `exec-code: true`. |
| Pack code | the "Pack code" row, `rebuild-finish-archon-native-design.md:169`: Archon nodes | `.shared/`, `scripts/`, a Python module or script, an MCP server or a patch, in a pack or beside it. Path or branch literals in YAML. |
| A feature Archon lacks | the owner | A workaround built by any agent. The agent stops and reports the missing feature to the owner. |
| Live runs and gate answers | the owner, or a lead on the owner's word | `archon workflow run` without `--dry-run`, `--exec-code`, `archon setup` and gate answers, by `workflow-builder`. |
| Loading a pack | the "Loading the pack" row, `rebuild-finish-archon-native-design.md:168`: `--workflow-source` on this repository | Any write to `~/.archon/`. An install script. |

## Order

1. `~/.claude/agents/workflow-builder.md` and its row in `~/.claude/skills/dispatch/roster.md` | `role-author`
2. `docs/host-facts.md` | `workflow-builder`
3. The dispatch proof, under `<scratchpad>/proof-repo/` only | `workflow-builder`
