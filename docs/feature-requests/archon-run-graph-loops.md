## Problem

The Web UI cannot show what a run is doing inside a `loop_group`, or inside an `include` expanded within one. A workflow whose work runs in loops looks like a few static boxes, whatever stage the run has reached.

Observed on Archon CLI v0.13.2 (linux-x64, binary build, commit `b8d01782`) with the 0.13.2 web UI:

- The only graph in the web UI is the workflow builder's. It draws the authored workflow: its inputs are the workflow definition, the node positions and the current selection. It takes no run state, so no node on it shows pending, running, completed, failed, skipped or paused.
- `loop_group`, `include` and `workflow` nodes draw as single opaque boxes. A `loop_group` is labelled with its body size and cap ("10 nodes, ≤4 rounds") and its body nodes are not drawn.
- An `include` inside a `loop_group` body expands into body-local nodes (`workflow-language.md`, "How expansion works"). Every node of the included workflow, nested loops included, therefore sits inside the group's one box.
- The run view's event list does name body nodes, with their group prefix: for example `cycle.planning__rounds.plan`. `archon workflow runs` prints the same, for example `active node(s): cycle, cycle.planning__rounds, cycle.planning__rounds.plan`. The information exists; only the graph does not show it.

Concrete case: a `finish` workflow has six top-level nodes. One is a `loop_group` (`cycle`, at most 4 iterations) whose body holds 10 nodes and two includes. One include is a planning block with its own `loop_group` (`rounds`, at most 24 iterations, 8 body nodes). The other is a build block with its own `loop_group` (`steps`, at most 200 iterations, 4 body nodes). In the graph, all of planning, review rounds and implementation are one box. Which round is running, which step is being built, and where the run paused can be read only by scrolling the event list.

## Why

Repetition in an Archon DAG is expressed only through `loop:` and `loop_group:`. `depends_on` must stay acyclic, so any workflow with review rounds, fix loops or per-item work puts that work inside a loop body. The more a workflow relies on loops, the less of it the graph shows, and the longest-running, most expensive part of a run is the part the owner cannot watch.

## Desired outcome

While a run is in progress, and after it ends, the owner can see each node of the run in a graph with its current state. That includes the nodes inside `loop_group` bodies and inside includes expanded within them, iteration by iteration.

## Acceptance

- [ ] A run's page shows a graph of that run in which every node carries its state (pending, running, completed, failed, skipped, paused), updating live without a reload while the run is in progress.
- [ ] A `loop_group` node in that graph can be opened to show its body nodes, their `depends_on` edges and each node's state in the current iteration, with the iteration number against `max_iterations` (for example "round 3 of 24").
- [ ] An earlier iteration of a `loop_group` can be selected, showing each body node's state and output for that iteration.
- [ ] A `loop_group` nested inside another, directly or through an `include` in the outer body, opens the same way, to the include nesting limit.
- [ ] An `include` node, at the top level or inside a body, can be opened to show its expanded nodes under their namespaced ids (`<includeId>__<nodeId>`).
- [ ] A body node paused at a `wait:` or approval shows as paused at its place in the graph.
- [ ] Existing workflows render this way with no change to their YAML.

## Constraints and related work

- Must remain true: `loop_group`, `include` and `depends_on` semantics are unchanged; the DAG stays acyclic; the builder still edits the authored YAML.
- Scope boundary: viewing runs. Editing loop bodies in the builder is out of scope.
- Solution steering: Hint — each node execution already records `invocation.loopPath`, the enclosing loop groups and iterations (`node-execution.md`), and body events carry their group prefix. The run graph may be buildable from data Archon already records.

## Additional notes

If a run graph with loop drill-in already exists and I have missed it, a pointer to where it lives would close this.
