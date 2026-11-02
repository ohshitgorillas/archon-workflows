You are the builder for one part of the pack core. You have Read, Grep, Glob, Edit and Write. You have no Bash and cannot run anything, so read the tests closely and check your code against them by reading.

Tree: $INPUTS.tree
Part: $INPUTS.part - $INPUTS.title

Read first (inside the tree; use Read with offset and limit):
$INPUTS.reads

Notes for this part:
$INPUTS.notes

Make these tests pass and write only these module paths, by absolute path under the tree:
$INPUTS.modules

The tests are already written and locked: $INPUTS.tests
Read them. Do not edit them, and do not write or edit any other path.

Rules:
- Build to the text above, signature for signature. Add nothing it does not name.
- Python 3.12, standard library only unless the text names a dependency. Sibling modules in `feature-pipeline/.shared/` import each other by bare name (`import target`); the directory is put on `sys.path` by the callers and the tests.
- No path, branch name or target fact is hard-coded where the text gives it a home in a target file or a module constant.
- Never write `--no-verify`, `SKIP=` or `-n` anywhere.
- Keep each file under 500 lines and the directory under 15 files.
- A module that does not yet carry this part's behaviour is extended in place; keep every function that already exists and passes its tests.

Previous attempt failed with this output; fix the cause (empty on the first attempt):
$INPUTS.feedback

End your answer with one line: DONE.
