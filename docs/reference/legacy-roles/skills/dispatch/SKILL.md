---
name: dispatch
description: How agents are dispatched on Opal (Gauntlet roles, Relay and Foreman queues, HQPTuner leads) - the roster, sizing and cutting of steps, the divvyer and recut, overloaded briefs, short reports, retiring heavy sessions, how a brief is written, design approvals and structure-first design. Use before dispatching or resuming any agent, writing or checking a brief, acting as or running a lead, cutting a queue, or starting multi-piece work that needs a design.
---

# Dispatching agents

`~/dev/CLAUDE.md` keeps one line each for 7.1, 7.1f and 7.1g, whose full rules are here, and holds 7.2 to 7.6 itself. The roster of roles is in `roster.md` beside this file.

## Who dispatches whom

- **A pasted lead prompt makes that session the lead.** A session whose prompt opens "You are a lead" does the lead's work itself and dispatches only workers; it never hands the prompt on to another `lead`.
- **Leads take a section; single agents take one step.** A `lead` may carry a section of several steps through development, dispatching each step to a fresh agent, until the section is done. Any agent doing the work itself gets one step per dispatch and one per resume: one done-check, at most one commit, then ping and stop. Never write "then continue" or a list of later steps into such a brief or reply; the next step is a fresh reply after this one lands. Before sending any brief, check it against 7.1f; if it fails, cut it.
- **The divvyer cuts every design.** Straight after the owner's own words approve a design, the divvyer cuts it into the queue in the same chained job (`~/.local/bin/design-chain`); there is no second architect pass, and neither the architect nor the dispatcher sizes a section. A section the divvyer cut is sent as cut: it sized it, and its cut is final. Work that has to run in sequence is cut as a sequence along its natural lines, never chopped to fit an arbitrary rule such as a file count.
- **Role files live in one place.** Every agent role file on this host lives in `~/.claude/agents/` (a plain directory here, not a symlink; Guild is not on this host) and is written or edited only there. No repository or worktree keeps a `.claude/agents/` copy: a repo copy overrides the shared file in Claude Code. A line that holds for one repository is worded for it inside the shared file ("in Gauntlet, ...; in Relay, ...").
- **"main"** in any agent's rules means the repository's default branch, whatever it is named (`git symbolic-ref --short HEAD` in the main checkout; Workboard's is `master`).

## Tokens, resume and reports

- **Watch tokens.** Prefer a fresh agent with a short brief over resuming a long session; a session past about 100k tokens of context is retired at its next safe point and its next step goes to a fresh one. The context-watch hook enforces the threshold.
- **Resume a stopped agent.** When a lead or worker stops early, crashes or gets heavy, the fresh agent's brief names the stopped session (`resume <session id>`) and carries the stopped agent's final report pasted in; the fresh agent starts from that report and recalls from Terminus with `~/.claude/skills/terminus/scripts/recall-session <session id>` (the `terminus` skill covers the rest) only when no report came. Git commits and the queue stay the record of what is finished; no agent writes a progress document.
- **Short reports.** Every worker ends with a fixed short report of about ten lines: DONE or STOPPED, the files changed, `git diff --stat`, the done-check command and its result line, and its CHOSEN choices. A lead reads that report and re-runs the done-check; it never reads the full diff and never holds full reviews. The blind reviewers (`diff-reviewer`, `test-reviewer`) read the full diff and return findings only. A lead recalls a worker's session with `recall-session <agent id>` only when a short report looks wrong.
- **Handoff before retiring.** Every agent writes its handoff report before it retires, however far past 100k; no limit excuses ending without it.
- **A retire is a diagnosis.** A heavy stop with work in the tree resumes as before. A heavy stop with no edits is never re-handed as it stands: run `~/.local/bin/retire-reads <id>`, which prints a `READS` line first. `FILE-SPLIT <paths>` is a file-split finding sent to `hitman` for those files before the step is re-dispatched. `SPREAD` means the brief is rewritten to excerpts and `path:line` pointers, or, for a divvyer-cut dispatch, sent to the divvyer's `recut` with the output pasted into the kept report. `EDITED` while `git status` and the commits are unchanged since the dispatch means the edits never landed: treat it as no edits and act on the `READS` line.
- **Reading load is measured before dispatch.** A dispatch's load is the tokens (bytes/4) of every file it must read whole, the design included when the brief hands it whole. The load plus the role's p90 peak from `uv run --project ~/dev/relay relay stats` must stay under 100k; over it, excerpt, cut or split before dispatch.
- **Model and effort (7.4).** Set them in the Agent tool's `model` and `effort` fields, not in the brief. A role file that pins both counts as set; override it only when the step differs (a lead follows its role file). Every other type (`Explore`, `Plan`) gets both on every call. Never fork bulk work: a fork ignores both fields and runs at its parent's.

## Writing a brief (7.1)

**7.1 A brief never restates what the agent already holds.** A brief says whatever the task needs. Three kinds of line are defects in any brief: a line that names, cites, quotes, summarizes or points to a `CLAUDE.md`, hook, budget or rule (every `CLAUDE.md` above the working directory loads into the agent on its own, a fork inherits the whole context, and a hook enforces without being mentioned); a line telling the agent to read something before it starts; and a line restricting a tool the agent type already lacks (a read-only task goes to an agent type without write tools). A ceiling above the 3.3 default, or a command set narrower than the agent type enforces, is task content and is stated.

**7.1a A brief to anything but an agent type the Agent tool lists is imperatives only.** Two to five sentences, each an order: an imperative verb, an object named by path, symbol or commit, and where it applies, a check that says done. A sentence that states rather than orders is struck before the brief is sent. If it cannot be rewritten as an order, delete it.

**7.1b A dispatch brief is cut to the work.** A brief commissioning an agent type the Agent tool lists runs as long or as short as the task demands, and carries whatever serves the agent: prose, tables, lists, examples, excerpts, the goal and why it matters, what is known or ruled out, constraints, the shape of answer wanted, what counts as done. 7.1 still holds, and every line earns its place. A conclusion the agent is meant to reach is left for it to reach.

**7.1c A dispatch is one step, not a shift.** Size each dispatch so the agent finishes it in a fresh context with room left to debug its own work. A brief that holds several steps is a plan, not a step: cut it into steps along the work's natural lines (a design's steps are cut by the divvyer, never by the dispatcher), dispatch them in sequence, and give each brief only its step plus whatever earlier steps returned that it needs. A new step goes to a fresh agent; 7.5 covers follow-ups on the step an agent already holds.

**7.1d No clock on a dispatch.** Owner ruling, 26 Oct: no agent, `lead` or worker, has a wall-clock cap or deadline, and no timer is started at dispatch. An agent runs until its step is done; sizing is the judgment of whoever cuts the step. A step too big for one worker that cannot be cut goes to a `lead`.

**7.1e A test brief states the behavior, never the test.** A brief to any agent that writes a test, `test-writer` or a specialist that writes its own, gives the behavior wanted in the owner's words and nothing that designs the test: no unit to target beyond the null stub the step names, no assertion, no input, no expected value beyond what the owner's or the design's behavior words themselves state. An agent handed one reports it and does not follow it.

**7.1f An overloaded brief is refused, not ground through.** Every dispatched agent, `lead` or worker, checks its brief before any work and refuses it when any of these holds: more than one done-check or more than one commit (a `lead` handed a section is exempt, and checks each step's brief instead); work it expects to outgrow a fresh context; more than about a page of brief, or more than five files in scope (resolving a merge's conflicts and a reviewer's one read of a step's diff are exempt from the file count; the other tests still apply); a mandated heavy run (full suite, mutation run, whole-tree gate) that alone would fill most of its context; or a ruling it needs and does not have.

- A refusal returns at once with no edits made: a first line `OVERLOADED: <the test failed, with its numbers>`, then a proposed split into steps that each pass this check, each with its done-check.
- An agent that finds partway that its step is bigger than its brief said stops at the next safe point and reports what is done, and what remains as a proposed split in the same shape, rather than push on.
- A `lead` refuses the same way for a step it was about to dispatch and cannot cut itself. The dispatcher runs this check on its own brief before sending it.
- A refusal or overrun, a worker's or a `lead`'s, goes straight to the divvyer's `recut`, never to the owner: the divvyer re-cuts it, weighing the proposed split, and its cut is dispatched again to fresh agents whose briefs name the stopped session. A recut brief to the divvyer is built with `~/.local/bin/recut-brief` and passed as printed, with no line added.
- Only the owner, in their own words, orders an agent to take an oversized step anyway. A refusal is not a failure and is not counted against the agent.

Under `RELAY_RUN=1` none of this refuses: the agent takes the step, notes `CHOSEN`, and stops only at a safe point with its report.

**7.1g A divvyer-cut brief runs as cut.** The size tests of 7.1f (every test but the missing ruling) apply only to a brief the divvyer did not cut. A section or dispatch the divvyer cut is run with no size check and no `OVERLOADED:` refusal; one that finds itself bigger than cut, or its session heavy, stops at the next safe point and reports what is done and what is left, proposing no split. Under `RELAY_RUN=1` none of this refuses: the agent takes the step, notes `CHOSEN`, and stops only at a safe point with its report.

## Designs and approvals

- **The owner's words approve a design.** A design is approved only by the owner's own words approving that design; an architect's `rulings` pass sets `Status: approved` only on those words, and the divvyer cuts it after that. Asking the owner to approve a proposed design is legitimate. The owner is not asked to settle technical internals of their own tooling (Gauntlet, Relay, Void, the Workboard, the design and dispatch scripts), such as failure handling, locks, retries, resume or lint strictness: the architect designs its recommendation in and asks nothing. The owner can overrule any such choice at any time.

## 7a. Structure first

**7a.1 Design before details.** Work with more than one piece (modules, gates, endpoints or roles that share concerns) starts with a design step naming the shared core: its modules, their public interfaces as stubs, and the one place each shared concern lives (output, errors and exit codes, config, process running, cleanup, test helpers). The owner's own words approve it, before any piece is built, and the divvyer cuts it after that.

**7a.2 Pieces build on the core.** Each piece adds only what is its own; a piece that needs what the core lacks stops and reports it rather than writing its own copy. Extending the core is a design change.

**7a.3 Big things first.** The structure lands and is green before edge cases and polish; a detail never goes in ahead of the structure it hangs on.

**7a.4 Copies are findings.** The same logic in two places is fixed by moving it into the core, not by patching both copies; reviewers check each diff against the approved design as well as the spec.

**7a.5 Fix causes, not lines.** A fix names the underlying cause and fixes every instance of it in scope (`~/dev/CLAUDE.md` 10.2).
