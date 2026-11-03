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
- Build order is the Plan's step order, with each Spec test step placed directly before the Plan code step its `before` names; test steps whose `before` is null (test-only work) come after every Plan step, in Spec order.
- A step is unblocked when every entry of its blocked_by is cleared. A decision id is never cleared this cycle (the owner's answer is pending). A step id is cleared once that step is in done (built with its check green); a step id that is stuck, or not yet done, leaves the dependent step unbuilt.
- next: after pass or stuck, the id of the next step in build order that is unblocked, not done, not stuck, and, for a code step, whose test step is not stuck. After fix, the same step. null when none is left.
- remaining: the count of steps not yet passed and not stuck that are unblocked or can still be unblocked this cycle (every blocked_by entry is a step id that is done or can itself still be built this cycle), counting a step whose test step is stuck, or that waits on a stuck step, as not buildable this cycle. 0 ends the loop.
- done: the previous done plus this step when it passed.
- stuck: the previous stuck plus this step when it is stuck.
- design_gaps: the previous gaps plus the writer's design_gap, if any.
- stray: paths changed outside every committed step that are still in the tree, only once the step is stuck; otherwise empty.
