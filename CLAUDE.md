# archon-workflows — agent conduct

**1. No scaffolding.** Use Archon's features directly, always. No scaffolding in any language (Python, Bash, shell one-liners or otherwise) without the owner's approval.
**2. A missing Archon feature is the owner's problem.** Stop and report the gap; the owner files a feature request or decides how to deal with it (a patch script, or a different route altogether).
**3. Token waste is a defect.** An approach, fix, node or rule that spends tokens on work the sequence does not need is a defect, however correct the rest of the file.
**4. A stop on a non-issue is a defect.** An approach, fix, node, gate or check that lets the sequence stop over a technicality or a non-issue is a defect, however correct the rest of the file.
**5. One such defect condemns the whole file.** The owner removes that file from the drive and from git history, whatever else it holds. Write every file so that no rule of kind 3 or 4 lives in it.
**6. Tests follow `docs/testing.md`.** Read it before writing or changing any test or workflow fixture.
