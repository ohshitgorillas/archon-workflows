"""Citation resolver: checks each cite's line against its quote and corrects it.

Reads the Plan from INPUTS_PLAN, files from the working directory (the run's
checkout). Writes nothing. Prints the Resolved object as JSON on stdout.
"""

import json
import os
import pathlib
import sys
from typing import NamedTuple, TypedDict


class Cite(TypedDict):
    """A citation: repository-relative path, 1-based line, the line's text."""

    path: str
    line: int
    quote: str


class Resolution(NamedTuple):
    """A cite with its line resolved, and the reason it is unresolved or None."""

    cite: Cite
    reason: str | None


def resolve(cite: Cite, root: pathlib.Path) -> Resolution:
    """Return (cite with line resolved, reason or None)."""
    quote = str(cite.get("quote", "")).strip()
    if not quote:
        return Resolution(cite, "empty quote")
    root = root.resolve()
    path = (root / str(cite.get("path", ""))).resolve()
    if not path.is_relative_to(root):
        return Resolution(cite, "outside checkout")
    if not path.is_file():
        return Resolution(cite, "no such file")
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    line = cite.get("line")
    if isinstance(line, int) and 1 <= line <= len(lines) and quote in lines[line - 1].strip():
        return Resolution(cite, None)
    candidates = [i for i, text in enumerate(lines, 1) if quote in text.strip()]
    if not candidates:
        return Resolution(cite, "quote not found")
    cited = line if isinstance(line, int) else 0
    best = min(abs(c - cited) for c in candidates)
    nearest = [c for c in candidates if abs(c - cited) == best]
    if len(nearest) > 1:
        return Resolution(cite, f"quote ambiguous: lines {nearest[0]}, {nearest[1]}")
    return Resolution(Cite(**{**cite, "line": nearest[0]}), None)


def main() -> int:
    plan = json.loads(os.environ["INPUTS_PLAN"])
    root = pathlib.Path.cwd()
    unresolved = []
    for step in plan.get("steps", []):
        resolved = []
        for cite in step.get("cites") or []:
            fixed, reason = resolve(cite, root)
            resolved.append(fixed)
            if reason:
                unresolved.append(
                    {
                        "step": step.get("id", ""),
                        "path": cite.get("path", ""),
                        "line": cite.get("line", 0),
                        "quote": cite.get("quote", ""),
                        "reason": reason,
                    }
                )
        if "cites" in step:
            step["cites"] = resolved
    print(json.dumps({"plan": plan, "unresolved": unresolved}, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
