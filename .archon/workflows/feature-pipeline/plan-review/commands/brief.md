You are the brief for one planning call. Four roles continue from this session, each on its own branch: the planner, the prosecutor, the specifier and the arbiter. This turn only reads, so that each of them holds what follows without reading it again.

Read the design file below once, in full, with Read. Read nothing else: not the checkout, not any path the design names.

Design: $recall.output.read
Design source: $recall.output.from

The run's checkout: $recall.output.root, on branch $recall.output.branch at commit $recall.output.head.
Branch the caller lands on, empty when it does not land: $INPUTS.land_branch
Checkout holding that branch, empty when it does not land: $INPUTS.land_checkout

Design steps still to build; each one is a unit key:
$INPUTS.scope

Tail of the latest full-check output:
$INPUTS.survey

Prior cycle (last plan and spec, open steps, design gaps, stuck steps, stray edits, owner answers, last findings and refusal findings):
$INPUTS.carry

The plan record for this design and scope, `null` when there is none. When there is one, its `plan` is the Plan to start from, its `spec` the Spec to start from, and its `approval` the owner's word on them:
$recall.output.record

The stopped call this one resumes, `null` when it resumes none. When there is one, its `plan` is the Plan to start from, its `spec` the Spec, its `resume` the round it stopped in, and its `question` the question it stopped on:
$recall.output.seed

The owner's answer to that question, empty when there is none:
$INPUTS.answer

Every answer the owner has given for this design and scope:
$recall.output.answers

The standard every role works to:

- A round fails only when the Plan or Spec would build the wrong thing, break something, skip something the design asks for, add work nobody asked for, run steps in an order that cannot work, or use a check that cannot pass or would not prove the step did its job. Everything else is minor, never costs a round, and is corrected by the build-loop writer.
- Work the sequence does not need is a defect. Letting the sequence stop over a technicality or a non-issue is a defect.
- An owner's answer above settles its question. No role asks it again.

Return `{ "ok": true }` once you have read the design.
