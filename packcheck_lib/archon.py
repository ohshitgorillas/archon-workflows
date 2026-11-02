"""The temporary Archon home packcheck runs in, and the archon runs inside it."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# What json.loads hands back, and the object form archon prints with --json.
type Json = None | bool | int | float | str | list[Json] | dict[str, Json]
type JsonObject = dict[str, Json]

# subprocess.run, or a stand-in with its signature (the seam tests fake at).
Runner = Callable[..., subprocess.CompletedProcess[str]]


@dataclass(frozen=True)
class ArchonRun:
    """One archon run that printed a JSON object."""

    rc: int  # exit code
    data: JsonObject  # the JSON object on stdout
    err: str  # stderr, stripped


class ArchonNotRun(Exception):
    """archon could not be started or did not finish; `check` names the check
    the run belonged to."""

    def __init__(self, check: str, message: str) -> None:
        super().__init__(message)
        self.check = check


class ArchonNoJson(Exception):
    """archon ran but printed no JSON object."""


def copy_provider_receipts(home: Path) -> None:
    """Copy the host's provider receipts (plugins/installed/**/receipt.json of kind
    provider) into the temp home. The receipts alone register the providers for
    validate; nothing in the temp home links back to the host, so no run can write it.
    Host workflow packs (plugins/packs/) and their receipts are not copied, so they
    cannot load beside the pack under check."""
    host = Path(os.environ.get("ARCHON_HOME") or Path.home() / ".archon") / "plugins"
    installed = host / "installed"
    if not installed.is_dir():
        return
    for receipt in installed.rglob("receipt.json"):
        try:
            data = json.loads(receipt.read_text())
        except (OSError, ValueError):
            continue
        if not isinstance(data, dict):
            continue
        manifest = data.get("manifest")
        if not isinstance(manifest, dict) or manifest.get("kind") != "provider":
            continue
        dest = home / "plugins" / receipt.relative_to(host)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(receipt, dest)


def temp_home(pack: Path, tmp: Path) -> tuple[Path, dict[str, str]]:
    """Copy `pack` to <tmp>/home/workflows/<pack name>/ with the provider receipts;
    return the copy and the environment that points ARCHON_HOME at <tmp>/home."""
    home = tmp / "home"
    dest = home / "workflows" / pack.name
    shutil.copytree(pack, dest)
    copy_provider_receipts(home)
    return dest, {**os.environ, "ARCHON_HOME": str(home)}


def run_archon(
    args: list[str], env: dict[str, str], run: Runner, check: str, what: str
) -> ArchonRun:
    """Run `archon <args>` from the repository root; return the run. Raises ArchonNotRun when it cannot run, ArchonNoJson
    when it prints no JSON object; `what` names the command in either message."""
    try:
        proc = run(
            ["archon", *args],
            cwd=REPO_ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=300,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as e:
        raise ArchonNotRun(check, f"archon {what} failed to run: {e}") from e
    err = proc.stderr.strip()
    no_json = f"no JSON from archon {what} (exit {proc.returncode}): {err[:200]}"
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        raise ArchonNoJson(no_json) from e
    if not isinstance(data, dict):
        raise ArchonNoJson(no_json)
    return ArchonRun(proc.returncode, data, err)
