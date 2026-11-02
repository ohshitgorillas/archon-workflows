# Feature request: let `archon workflow test` exercise loops past their first iteration

**Archon version:** CLI v0.13.2, linux-x64

## Problem

`archon workflow test` cannot test any route that needs a loop to run more than once. This hits retry-until-accepted loops hardest, such as plan, review, and plan again.

Two behaviors cause it:

1. **`until_bash` is never run in a dry run.** The loop is assumed complete after the first iteration. The CLI says so itself: `assumed complete after N iteration(s) — 'until_bash' is not executed in a dry run`. This holds even when the fixture sets `exec-code: true`, which already runs `bash:` and `script:` nodes for real. A `loop_group` whose only exit is `until_bash` always ends after iteration 1.
2. **Stubs cannot vary by iteration.** Each node gets one stub, and the stub returns the same output every pass. So even a loop that does re-run cannot be driven through "refused on pass 1, accepted on pass 2".

Neither behavior is documented in `cli.md`, `workflow-language.md` or the loop-nodes guide. We found it in the binary.

## Concrete case

A `loop_group` named `rounds` makes up to four plan attempts. Each attempt is reviewed, and the loop exits through `until_bash` on the review verdict. Fixtures for "accepted on attempt 1, then spec", "refused four times", "refused at spec" and "reopened" all fail:

```
required nodes did not complete: spec, arbitrate
expected node 'verdict' resolved text to contain "\"next\":\"refused\",\"cuts\":4,\"specs\":0"
```

## Requested

- **Under `exec-code: true`, run `until_bash` for real** after each iteration, against that iteration's outputs. Then honor `max_iterations` as a live run does.
- **Allow per-iteration stubs.** For example, a node's stub could be a list consumed one entry per iteration, with the last entry repeating:

  ```yaml
  stubs:
    review:
      - { output: '{"verdict":"refused"}' }
      - { output: '{"verdict":"accepted"}' }
  ```
- **Document the dry-run loop semantics** in `cli.md`: which exit conditions run, which are assumed, and how many iterations are taken.

## Related, smaller

`fixture.resolved-text-contains` accepts one fragment per node: a record of string to string. A list of fragments per node would let one fixture check several non-adjacent facts in a node's text. Today a list fails with `'fixture' block — Invalid input: expected string, received array`.

## Workaround in use

We prove the multi-round routes on a live run, and dry-run fixtures cover only single-pass routes.
