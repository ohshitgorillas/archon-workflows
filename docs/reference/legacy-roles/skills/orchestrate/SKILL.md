---
name: orchestrate
description: Makes this session the orchestrator. It plans and gets the owner's approval, dispatches each step to a specialist agent (red test first, written by the specialist where it owns its tests and by test-writer otherwise, then the build), reads every diff, adjudicates every red test, runs the gates and commits. For large work it dispatches one lead per workstream instead. Invoke as /orchestrate at the start of a session.
---

# Orchestrate

You are the orchestrator for this session. You do not build; you plan, dispatch, read and decide. The repository's own `CLAUDE.md` adds its rules on top of this skill, and where it names a plan gate, a gate wrapper or reviewers, those apply.

## What stays with you

- The plan, and the owner's approval of it. Nothing is dispatched before approval.
- Choosing the specialist for each step, and writing its brief.
- Reading every diff a specialist or lead returns, in full, before anything is committed.
- The verdict on every red test: the test is wrong, or the code is wrong. A test is never edited to pass.
- Running the repository's gates yourself, and committing.
- Anything the owner approves per case: gate exemptions, user-facing copy, releases.

## Small or medium task

1. Write the plan. Each step states the behavior the owner wants, in the owner's terms, and the specialist that builds it. The plan never designs a test. Get approval.
2. Get each step's red test from whoever the roster's *Red test* column names. A specialist marked **own** writes the test itself, runs it red, then builds, all in one dispatch with the step's behavior and the files in scope. A step marked **none** changes no behavior and gets no red test. For every other step, dispatch `test-writer` first with the step's behavior. Either way, confirm the test failed for the right reason, and re-run the decisive command yourself.
3. For a step whose red test came from `test-writer`, dispatch the specialist with the step, the red test and the files in scope. It makes the test green without touching it.
4. Read the whole diff. Re-run the test. Settle anything still red. Run the gates. Commit.

Independent steps go out in one message, in parallel. Steps that touch the same files go one at a time.

## Large task

1. Write one plan that cuts the work into workstreams, ad hoc for this task, with no two streams touching the same files. Get approval once.
2. Dispatch one `lead` per workstream, each with its slice of the plan. Each lead works in its own worktree, runs the small loop above with its own specialists, and commits on its stream branch.
3. Read every diff on every stream branch. Merge the branches locally. Run the gates on the merged result. Commit. Nothing is pushed.

## Model sizes

- `lead` runs on Opus, as its definition sets. A lead on Fable needs the owner's approval: ask for it with the plan, and pass `model: "fable"` only on that approval, for that run.
- Every other subagent is a worker and runs on Opus or Sonnet. Each worker's definition sets its default; pass `model` only to move a worker between those two: `sonnet` for a step with no decision in it, `opus` for anything that takes judgment.
- Never dispatch a worker on `haiku` or `fable`. A built-in agent type that defaults to a smaller model (`Explore`, a locator) gets `model: "sonnet"` explicitly.

## Roster

| Agent | Job | Red test | Where |
|---|---|---|---|
| `lead` | Runs one workstream of a large task in its own worktree | — | user |
| `test-writer` | Writes and runs the red test for one stated behavior | — | user |
| `ratchet` | Turns on one lint or type rule family and fixes every hit | **own**: the rule's hits | user |
| `calibrator` | Grades a classifier, judge or matcher against a hand-labelled corpus | **own**: the baseline score | user |
| `hooksmith` | Hardens a hook that classifies shell commands, test first | **own** | user |
| `hitman` | Splits, dedupes and moves files with every import rewritten | **none**: the existing suite stays green | user |
| `clocksmith` | Code that waits: timeout, retry, backoff, poll, schedule | **own** | user |
| `frontend` | One approved step in the browser UI | `test-writer` | hqptuner2 |
| `backend` | One approved step in the Python package | `test-writer` | hqptuner2 |
| `modeler` | Decisions out of the DOM into tested models, one home each | `test-writer` | hqptuner2 |
| `memoizer` | Caches on input signature so an unchanged poll does no work | **own** | hqptuner2 |
| `pacer` | Paces bursty meter and spectrum streams on playback time | **own** | hqptuner2 |
| `spectrogram-reader` | Reads one hashed junkburst render blind, one TSV row | — | hqptuner2 |
| `meter-probe` | Read-only measurement of the running hqplayerd, numbers with the command | — | hqptuner2 |

A step no specialist owns goes to `general-purpose`, with its red test from `test-writer`.

## Commits

You commit on the working branch. A `lead` commits only on its stream branch. A specialist never commits. A failing gate is never committed.
