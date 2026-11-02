## Problem

`archon workflow test` cannot exercise any route that needs a loop to run more than once. Workflow authors with retry or review loops have no way to prove those routes before a live run. A typical case is "plan, review, refused, plan again, accepted".

Observed on Archon CLI v0.13.2 (linux-x64):

- A loop whose exit is `until_bash` always ends after iteration 1 in a dry run. This holds even when the fixture sets `exec-code: true`. The CLI reports `assumed complete after N iteration(s) — 'until_bash' is not executed in a dry run`.
- A node's stub returns the same output on every iteration. So a fixture cannot describe "refused on pass 1, accepted on pass 2", even for a loop that does re-run.
- Neither behavior is documented in `cli.md`, `workflow-language.md` or the loop-nodes guide.

Concrete case: a `loop_group` named `rounds` makes up to four plan attempts. Each attempt is reviewed, and the loop exits through `until_bash` on the review's verdict. Every fixture that needs a second round fails, with one of these:

```
required nodes did not complete: spec, arbitrate
expected node 'verdict' resolved text to contain "\"next\":\"refused\",\"cuts\":4,\"specs\":0"
```

## Why

Loops are where workflow logic is most likely to be wrong: exit conditions, iteration caps and state carried between rounds. Today a dry run cannot test them, so the only proof is a live run, which is slow, costs model calls and is hard to repeat. We have dropped four planned fixtures from one workflow pack because of this.

## Desired outcome

A dry run can drive a loop through several iterations. The fixture controls what each iteration's nodes return, and the loop exits by the same condition it would use live.

## Acceptance

- [ ] A fixture can make a `loop_group` with an `until_bash` exit run N > 1 iterations and then exit, with the exit decided by the loop's own condition.
- [ ] A fixture can give a node a different output on each iteration of a loop.
- [ ] A loop that never meets its exit condition in a dry run stops at `max_iterations` and reports it, the same way a live run does.
- [ ] `cli.md` documents how loops behave in a dry run: which exit conditions are evaluated, which are assumed, and how iterations are counted.

## Constraints and related work

- Must remain true: existing fixtures with one stub per node keep working unchanged.
- Scope boundary: dry-run (`archon workflow test`) behavior only. Live runs are unchanged.
- Solution steering: Hint — evaluate `until_bash` for real when `exec-code: true` is set, since `bash:` and `script:` nodes already run then. Hint — a stub given as a list could be consumed one entry per iteration, with the last entry repeating.

## Additional notes

A related, smaller limit: `fixture.resolved-text-contains` accepts one fragment per node. A list fails with `'fixture' block — Invalid input: expected string, received array`. Allowing a list would let one fixture check several non-adjacent facts in a node's text. It could be filed separately.

Workaround in use: multi-round routes are proved on the first live run, and dry-run fixtures cover only single-pass routes.
