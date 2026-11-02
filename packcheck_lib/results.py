"""What archon's JSON output says about the pack under check."""

from __future__ import annotations

from pathlib import Path

from packcheck_lib.archon import JsonObject
from packcheck_lib.failure import Failure
from packcheck_lib.layout import fixtures


def unique_names(labels: dict[str, list[str]]) -> tuple[dict[str, str], list[Failure]]:
    """The label of each name declared once, and a validate failure for every label
    sharing its name with another."""
    by_name = {n: ls[0] for n, ls in labels.items() if len(ls) == 1}
    clashes = [
        Failure(label, "validate", f"workflow name {name!r} is not unique")
        for name, ls in labels.items()
        if len(ls) > 1
        for label in ls
    ]
    return by_name, clashes


def _issue_failures(label: str, name: str, rs: list[dict]) -> list[Failure]:
    """The failures of the validate results naming one workflow of the pack."""
    if not rs:
        return [
            Failure(
                label, "validate", f"workflow {name!r} not found by archon validate"
            )
        ]
    if len(rs) > 1:
        # The name is also declared outside the pack (bundled or repo scope);
        # the results cannot be told apart, so none is attributed to the pack.
        return [
            Failure(
                label,
                "validate",
                f"workflow name {name!r} is also declared outside the pack",
            )
        ]
    r = rs[0]
    if not isinstance(r.get("issues"), list):
        return [Failure(label, "validate", "result has no issues list")]
    # Every issue fails, warnings included: Archon reports an unknown key it
    # drops (a misspelled `sandbox:`, say) only as a warning.
    issues = [i for i in r["issues"] if isinstance(i, dict)]
    out = []
    for i in issues:
        node = i.get("nodeId")
        where = f"node {node}: " if node else ""
        level = i.get("level") or "issue"
        out.append(Failure(label, "validate", f"{where}{level}: {i.get('message')}"))
    if r.get("valid") is not True and not issues:
        out.append(Failure(label, "validate", "reported invalid"))
    return out


def validate_failures(
    pack: str, by_name: dict[str, str], rc: int, data: JsonObject, err: str
) -> list[Failure]:
    """Failures from `archon validate workflows --json` exiting `rc` with `data`
    on stdout and `err` on stderr."""
    if not isinstance(data.get("results"), list):
        return [
            Failure(
                pack,
                "validate",
                f"no JSON from archon validate (exit {rc}): {err[:200]}",
            )
        ]
    results: dict[str, list[dict]] = {}
    for r in data["results"]:
        if isinstance(r, dict) and r.get("workflowName") in by_name:
            results.setdefault(r["workflowName"], []).append(r)
    out: list[Failure] = []
    for name, label in by_name.items():
        out.extend(_issue_failures(label, name, results.get(name, [])))
    # Workflows outside the pack (bundled, repo scope) may be invalid and set
    # the exit code; only an exit nothing else explains is the pack's failure.
    outside_invalid = any(
        isinstance(r, dict)
        and r.get("workflowName") not in by_name
        and r.get("valid") is not True
        for r in data["results"]
    )
    if rc != 0 and not out and not outside_invalid:
        out.append(
            Failure(
                pack,
                "validate",
                f"archon validate exited {rc} with no failure attributed",
            )
        )
    return out


def _unreported(pack: str, folders: list[Path], results: list) -> list[Failure]:
    """Every declared fixture must appear in the results: exit 0 with no results is
    also what Archon reports when it found no fixtures at all."""
    reported = {
        Path(r["fixture"]).parts[-3:]
        for r in results
        if isinstance(r, dict) and isinstance(r.get("fixture"), str)
    }
    return [
        Failure(
            f"{pack}/{f.name}",
            "fixture",
            f"{fx.name}: not in archon workflow test results",
        )
        for f in folders
        for fx in fixtures(f)
        if (f.name, "fixtures", fx.name) not in reported
    ]


def workflow_test_failures(
    pack: str, by_name: dict[str, str], folders: list[Path], rc: int, data: JsonObject
) -> list[Failure]:
    """Failures from `archon workflow test <pack> --json` exiting `rc` with `data`."""
    out: list[Failure] = []
    if rc != 0:
        out.append(Failure(pack, "fixture", f"archon workflow test exited {rc}"))
    if data.get("ok") is False:
        out.append(Failure(pack, "fixture", str(data.get("error"))))
    failed = data.get("failed")
    if isinstance(failed, bool) or not isinstance(failed, (int, type(None))):
        out.append(Failure(pack, "fixture", f"bad failed count: {failed!r}"))
    elif failed:
        out.append(Failure(pack, "fixture", f"{failed} fixture(s) failed"))
    results = data.get("results")
    if not isinstance(results, list):
        out.append(Failure(pack, "fixture", "no results in workflow test output"))
        results = []
    for r in results:
        if isinstance(r, dict) and not r.get("pass"):
            reason = r.get("failureReason") or "failed"
            label = by_name.get(r.get("workflow"), pack)
            out.append(Failure(label, "fixture", f"{r.get('fixture')}: {reason}"))
    out.extend(Failure(pack, "fixture", str(e)) for e in data.get("errors") or [])
    return out + _unreported(pack, folders, results)
