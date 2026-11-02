# Archon host facts (Opal, v0.13.2)

Each fact names the run or command that showed it.

## Spike facts (runs d1fb9a11, d995f962, 32f05577; `.gauntlet/jobs/design/brief.md:25-33`)

- `/usr/local/bin/archon` is v0.13.2, Claude provider only; the codex binary is absent.
- The `sandbox:` block covers Bash and its children only, with absolute paths. Read, Edit, Write, Grep and Glob pass through it; under `denyWrite` the Edit tool still appended to `tests/`. Relative globs and `allowRead` globs do nothing (`docs/reference/archon/spike-sandbox-workflow.yaml:12-16`).
- Per-node, Claude only: `allowed_tools`, `hooks`, `sandbox`, `output_format`, `context: fresh`. `mutates_checkout: false` fails a node after the fact. No per-node `cwd`, no path allow-list.
- `socat` is not installed; the Claude sandbox refuses to start without it. Install is the owner's.
- `~/.archon/` has no `workflows/` dir.

## Rules from the design (`docs/superpowers/specs/hqptuner-archon-workflow-design.md:7-8`)

- Every fence path is absolute and comes from one module; relative globs do nothing and the sandbox fences Bash only.
- Target facts live in one target file in this repository, never in a pack's code.

## Observed building `feature-pipeline`

- `model: small` fails with "No default provider". Shown by the spike; use `provider: claude` with a literal model.
- `archon validate workflows --json` under a temp `ARCHON_HOME` with no provider receipt fails with "Provider 'claude' is not installed. Add it with: archon provider add claude". Shown by `uv run packcheck.py feature-pipeline`.
- `archon workflow test` finds fixtures only for workflows in a discovery scope: `archon workflow test feature-pipeline` from `/home/atom/dev/archon-workflows` printed "No fixtures found ... No workflow in any discovery scope declares fixtures." The repository's own tree is not a scope. A scratch git repo with the pack copied to `.archon/workflows/feature-pipeline/`, run from that repo, found and passed all 7 fixtures (`7 passed, 0 failed`).
- With a temp `ARCHON_HOME` holding `workflows/feature-pipeline/`, `archon workflow test feature-pipeline` printed "no discovered workflow matches (feature)" and "Provider 'claude' is not installed" for the same reason as the validate failure.
- Nodes skipped by `when:` need no stub in a fixture: `plan-round-2`, `spec-refused` and the other route fixtures pass with stubs only for the reached nodes.
