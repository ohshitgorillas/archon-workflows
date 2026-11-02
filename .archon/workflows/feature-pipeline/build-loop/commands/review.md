You are the reviewer. Read-only. Rule on the step just written.

The Plan:
$INPUTS.plan

The Spec:
$INPUTS.spec

Tree state before the loop began (git status --porcelain):
$before.output

This iteration's writer answer:
$write.output

This iteration's section check:
$check.output

This iteration's commit result (committed or not, and the tree state after it):
$commit.output

The previous iteration's review (empty on iteration 1):
$LOOP_PREV.review.output

Check:
- The writer's step_id, paths and check match the step in the Plan or Spec.
- The tests match their Spec lines. The code serves the Spec lines that cite its step.
- The section check is green and the step was committed.
- Stray edits: compare the commit result's tree state with the state before the loop and the steps already done. A path changed outside every committed step is a finding with cause "stray edit"; its fix is to revert that path. The step does not pass while a stray path remains.

Answer:
- verdict pass: no finding. verdict fix: findings by cause, one entry per cause, with fixes_used one more than the previous count for this step. verdict stuck: this step has already used 2 fixes and still fails, or the writer reported a design_gap.
- fixes_used: fixes spent on this step, at most 2. It is 0 when the step passes first time.
- next: after pass or stuck, the id of the next step in build order that is unblocked (empty blocked_by), not done, not stuck, and, for a code step, whose test step is not stuck. After fix, the same step. null when none is left.
- remaining: the count of unblocked steps not yet passed and not stuck, counting a step whose test step is stuck as not buildable this cycle. 0 ends the loop.
- done: the previous done plus this step when it passed.
- stuck: the previous stuck plus this step when it is stuck.
- design_gaps: the previous gaps plus the writer's design_gap, if any.
- stray: paths changed outside every committed step that are still in the tree, only once the step is stuck; otherwise empty.
