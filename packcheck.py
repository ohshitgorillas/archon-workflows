#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = ["pyyaml>=6"]
# ///
"""packcheck: the one check of an Archon workflow pack.

uv run packcheck.py <pack> [<pack> ...]   -> exit 0 all clean, 1 any failure
Prints one line per failure: "<pack>/<workflow>: <check>: <message>".

The checks live in packcheck_lib/: layout (where workflows and fixtures sit),
static (checks made without Archon), archon (the temp home and the archon runs)
and results (what archon's JSON says). This file runs them and reports.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from packcheck_lib import results
from packcheck_lib.archon import (
    ArchonNoJson,
    ArchonNotRun,
    Runner,
    run_archon,
    temp_home,
)
from packcheck_lib.failure import Failure
from packcheck_lib.layout import (
    fixtures,
    labels_by_name,
    pack_paths,
    parse,
    workflow_folders,
)
from packcheck_lib.static import static_failures

__all__ = ["Failure", "check", "main"]


def _dynamic(
    pack: Path,
    folders: list[Path],
    by_name: dict[str, str],
    tmp: Path,
    run: Runner,
    run_fixtures: bool,
    out: list[Failure],
) -> None:
    """Append the archon runs' failures to `out` as each run finishes, so a later
    run that cannot start keeps the earlier failures. `run_fixtures` False skips
    `archon workflow test` (a fixture asked for exec-code)."""
    dest, env = temp_home(pack, tmp)
    try:
        done = run_archon(
            ["validate", "workflows", "--json"], env, run, "validate", "validate"
        )
    except ArchonNoJson as e:
        out.append(Failure(pack.name, "validate", str(e)))
    else:
        out.extend(
            results.validate_failures(pack.name, by_name, done.rc, done.data, done.err)
        )
    if not run_fixtures or not any(fixtures(f) for f in folders):
        return
    try:
        done = run_archon(
            ["workflow", "test", str(dest), "--json"],
            env,
            run,
            "fixture",
            "workflow test",
        )
    except ArchonNoJson as e:
        out.append(Failure(pack.name, "fixture", str(e)))
    else:
        out.extend(
            results.workflow_test_failures(
                pack.name, by_name, folders, done.rc, done.data
            )
        )


def check(pack: Path, *, run: Runner = subprocess.run) -> list[Failure]:
    """Copies `pack` to <tmp>/home/workflows/<pack name>/ and runs, from the repository
    root with ARCHON_HOME=<tmp>/home: `archon validate workflows --json`, then
    `archon workflow test <pack> --json` (skipped when a fixture has exec-code). Also
    fails statically: a workflow folder with no fixtures/*.stubs.yaml; a node or
    workflow model that is a tier keyword or @alias; a sandbox filesystem path that
    is not absolute; exec-code: true in a fixture. Never writes ~/.archon. Removes
    <tmp> on every exit. `run` runs each archon command (subprocess.run's
    signature); a test hands in a stand-in."""
    pack = Path(pack).resolve()
    if not pack.is_dir():
        return [Failure(str(pack.name), "validate", f"not a directory: {pack}")]
    folders = workflow_folders(pack)
    if not folders:
        return [
            Failure(
                pack.name,
                "validate",
                "no workflow folder (a subfolder holding a YAML file)",
            )
        ]
    parsed = parse(pack_paths(pack, folders))
    failures = static_failures(pack, folders, parsed)
    # A fixture asking for exec-code is never handed to `archon workflow test`: that
    # would run its bash and script nodes for real.
    safe = not any(f.check == "exec-code" for f in failures)
    by_name, clashes = results.unique_names(labels_by_name(pack, folders, parsed))
    failures.extend(clashes)
    tmp = Path(tempfile.mkdtemp(prefix="packcheck-"))
    try:
        _dynamic(pack, folders, by_name, tmp, run, safe, failures)
    except ArchonNotRun as e:
        failures.append(Failure(pack.name, e.check, str(e)))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return failures


def main(argv: list[str]) -> int:
    if not argv:
        print("usage: packcheck.py <pack> [<pack> ...]", file=sys.stderr)
        return 2
    bad = 0
    for arg in argv:
        for f in check(Path(arg)):
            bad += 1
            print(f"{f.workflow}: {f.check}: {f.message}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
