# Agent roster

Every repository on this host uses the same agents, and needs no roster of its own to use them. Role files live in `~/.claude/agents/`.

| Agent | Writes | Red test |
|---|---|---|
| `architect` | `docs/superpowers/specs/<topic>-design.md` | none |
| `divvyer` | the queue at its brief's path | none |
| `lead` | nothing; dispatches, re-runs done-checks, commits | — |
| `test-reader` | `quotes.md` in the test chain's handoff directory; first of the test chain (`sonnet`, low) | — |
| `test-speccer` | `spec.md` in the handoff directory; second of the test chain (`opus`, medium) | — |
| `test-writer` | test files, typed from a `spec.md`; last of the test chain (`sonnet`, medium) | — |
| `builder` | the paths its Order step lists, test files excepted; also a `stub` piece, the step's Modules signatures raise-only, before its red test | `test-writer`; none for `stub` |
| `diff-reviewer`, `test-reviewer` | nothing | — |
| `mutant-hunter` | test files | — |
| `spiker` | the scratchpad | — |
| `assayer` | nothing; judges one failure in a section | — |
| `juror` | nothing; Foreman's judge of one step or group check | — |
| `researcher` | nothing; maps one Relay queue section as `path:line` pointers | — |
| `reader` | nothing; dispatched only by `researcher` | — |
| `role-author` | one role prompt under `~/.claude/agents/`, or a Gauntlet role or skill | none |
| `workflow-builder` | Archon workflow folders `.archon/workflows/<pack>/<workflow>/` in `archon-workflows`; commits its own paths once `archon validate workflows <name>` per workflow and `archon workflow test .archon/workflows/<pack>` exit 0, from the repository root (`sonnet`, medium) | none; its fixtures and Archon's own checks |

- `general-purpose` and `claude` are denied in `~/.claude/settings.json`. A throwaway experiment, in any repository or none, goes to `spiker`.
- A change confined to `docs/` or `CLAUDE.md` takes no red test.
- A repository's `CLAUDE.md` may name extra specialists that take over part of `builder`'s writes (Gauntlet's `core-builder`, `seamstress`, `gatesmith`) and nothing else; every other role is this table's.
- This host also keeps 14 agents of its own with no row above: `abuser-reviewer`, `backend`, `backend-reviewer`, `brief-writer`, `calibrator`, `eq-assistant`, `frontend`, `frontend-reviewer`, `hooksmith` (`~/dev/CLAUDE.md` 2.3), `memoizer`, `modeler`, `pedant-reviewer`, `ratchet`, `user-reviewer`.
