# /// script
# requires-python = ">=3.12"
# ///
"""finish-bootstrap's one script: git, pytest and packcheck runs for the core build.

It imports nothing from the pack's `.shared/`, which does not exist yet. Every input
arrives as an INPUTS_<NAME> env var; the mode picks the check. It prints one JSON
object on stdout and nothing else; subprocess output is captured, never echoed.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

TAIL = 6000
PYTEST = [
    "uv", "run", "--with", "pytest", "--with", "pyyaml", "pytest", "-q",
    "-p", "no:cacheprovider", "--tb=short", "-rA", "--continue-on-collection-errors",
]
RESULT = re.compile(r"^(PASSED|FAILED|ERROR) (\S+)", re.M)


def env(name: str, default: str = "") -> str:
    return os.environ.get("INPUTS_" + name.upper(), default)


def listed(name: str) -> list[str]:
    raw = env(name)
    return json.loads(raw) if raw else []


def tail(text: str) -> str:
    return text if len(text) <= TAIL else "..." + text[-TAIL:]


def run(argv: list[str], cwd: str | Path) -> tuple[int, str]:
    clean = {k: v for k, v in os.environ.items() if k != "SKIP"}
    clean["PYTHONDONTWRITEBYTECODE"] = "1"
    p = subprocess.run(argv, cwd=cwd, env=clean, capture_output=True, text=True)
    return p.returncode, (p.stdout + p.stderr).strip()


def git(tree: str | Path, *args: str) -> tuple[int, str]:
    return run(["git", *args], tree)


def record(event: dict) -> None:
    path = Path(env("records"))
    path.parent.mkdir(parents=True, exist_ok=True)
    event = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "run_id": env("run_id"), **event}
    with path.open("a") as f:
        f.write(json.dumps(event) + "\n")


def progress(state: str, commit: str | None = None) -> None:
    part = env("part")
    record({"event": "progress", "step": part, "item": part, "state": state, "commit": commit})


def chosen(step: str, choice: str, reason: str) -> None:
    record({"event": "chosen", "step": step, "choice": choice, "reason": reason})


def changed(tree: str) -> list[str]:
    _, out = git(tree, "status", "--porcelain", "-uall")
    paths = []
    for ln in out.splitlines():
        p = ln[3:].split(" -> ")[-1].strip().strip('"')
        if p:
            paths.append(p)
    return paths


def outside(paths: list[str], allowed: list[str]) -> list[str]:
    def ok(p: str) -> bool:
        return any(p == a or (a.endswith("/") and p.startswith(a)) for a in allowed)

    return [p for p in paths if not ok(p)]


def pytest(tree: str, targets: list[str]) -> tuple[int, str, dict[str, set[str]]]:
    rc, out = run([*PYTEST, *targets], tree)
    found: dict[str, set[str]] = {"PASSED": set(), "FAILED": set(), "ERROR": set()}
    for kind, ident in RESULT.findall(out):
        found[kind].add(ident)
    return rc, out, found


def baseline_file() -> Path:
    return Path(env("tree")).parent / f"baseline-{env('part')}.txt"


def hash_file() -> Path:
    return Path(env("tree")).parent / f"tests-{env('part')}.sha"


def tests_hash(tree: str, tests: list[str]) -> str:
    h = hashlib.sha256()
    for t in tests:
        p = Path(tree) / t
        h.update(p.read_bytes() if p.is_file() else b"<missing>")
    return h.hexdigest()


def committed(tree: str, part: str) -> bool:
    _, out = git(tree, "log", "--format=%s")
    return any(s.startswith(f"bootstrap({part}):") for s in out.splitlines())


def done(ok: bool, detail: str, **extra: object) -> int:
    print(json.dumps({"ok": ok, "detail": tail(detail), **extra}))
    return 0


def mode_tree() -> int:
    tree, branch = Path(env("tree")), env("branch")
    if tree.exists():
        rc, cur = git(tree, "rev-parse", "--abbrev-ref", "HEAD")
        if rc or cur != branch:
            return done(False, f"{tree} exists and is on {cur!r}, not {branch!r}")
    else:
        tree.parent.mkdir(parents=True, exist_ok=True)
        has, _ = git(env("repo"), "rev-parse", "--verify", "--quiet", branch)
        add = ["worktree", "add", str(tree), branch] if has == 0 else [
            "worktree", "add", "-b", branch, str(tree), env("base")]
        rc, out = git(env("repo"), *add)
        if rc:
            return done(False, out)
    Path(env("records")).parent.mkdir(parents=True, exist_ok=True)
    if not (tree / ".venv").exists():
        rc, out = run(["uv", "sync"], tree)
        if rc:
            return done(False, "uv sync failed: " + out)
    return done(True, f"tree {tree} on {branch}")


def mode_todo() -> int:
    tree, part = env("tree"), env("part")
    pending = not committed(tree, part)
    if pending:
        found: set[str] = set()
        if (Path(tree) / "tests").is_dir():
            found = pytest(tree, ["tests"])[2]["PASSED"]
        baseline_file().write_text("\n".join(sorted(found)))
        progress("started")
    print(json.dumps({"ok": True, "pending": pending, "detail": "pending" if pending else "committed"}))
    return 0


def mode_red() -> int:
    tree, tests = env("tree"), listed("tests")
    stray = outside(changed(tree), tests)
    missing = [t for t in tests if not (Path(tree) / t).is_file()]
    parts, ok = [], True
    if stray:
        ok = False
        parts.append("paths changed outside the test files: " + ", ".join(stray))
    if missing:
        ok = False
        parts.append("test files not written: " + ", ".join(missing))
    if not missing:
        base = set(baseline_file().read_text().split())
        _, out, found = pytest(tree, tests)
        fresh = sorted(found["PASSED"] - base)
        if fresh:
            ok = False
            parts.append("new tests that already pass (they must fail): " + ", ".join(fresh))
        if not (found["FAILED"] or found["ERROR"]):
            ok = False
            parts.append("no test fails or errors; the part's tests must fail first")
        parts.append(out)
    if ok:
        hash_file().write_text(tests_hash(tree, tests))
    if not ok and env("final") == "true":
        progress("failed")
    return done(ok, "\n".join(parts) if parts else "tests are red")


def mode_green() -> int:
    tree, tests = env("tree"), listed("tests")
    base = set(baseline_file().read_text().split())
    _, out, found = pytest(tree, ["tests"])
    problems = []
    regress = sorted(base - found["PASSED"])
    if regress:
        problems.append("tests that passed at the part's start and do not now: " + ", ".join(regress))
    if found["FAILED"] or found["ERROR"]:
        problems.append("failing: " + ", ".join(sorted(found["FAILED"] | found["ERROR"])))
    for t in tests:
        if not any(i.startswith(t + "::") for i in found["PASSED"]):
            problems.append(f"no test in {t} passes")
    rc, pout = run(["uv", "run", "packcheck.py", "feature-pipeline"], tree)
    if rc:
        problems.append(f"packcheck exit {rc}: {pout}")
    return done(not problems, "\n".join([*problems, out]) if problems else "green")


def mode_paths() -> int:
    tree, tests = env("tree"), listed("tests")
    problems = []
    stray = outside(changed(tree), [*tests, *listed("modules")])
    if stray:
        problems.append("paths changed outside this part's tests and modules: " + ", ".join(stray))
    want = hash_file().read_text() if hash_file().is_file() else None
    if want != tests_hash(tree, tests):
        problems.append("the test files changed after the tests were locked red")
    return done(not problems, "\n".join(problems) if problems else "paths ok")


def mode_commit() -> int:
    tree, part = env("tree"), env("part")
    if committed(tree, part):
        return done(True, "already committed")
    if env("checks_ok") != "true" or env("paths_ok") != "true":
        if env("final") == "true":
            progress("failed")
        return done(False, "not committed: the checks or the paths check failed")
    paths = [p for p in [*listed("tests"), *listed("modules")] if (Path(tree) / p).exists()]
    rc, out = git(tree, "add", "--", *paths)
    if rc == 0:
        rc, out = git(tree, "commit", "-m", f"bootstrap({part}): {env('title')}")
    if rc:
        if env("final") == "true":
            progress("failed")
        return done(False, "git commit refused:\n" + out)
    sha = git(tree, "rev-parse", "--short", "HEAD")[1]
    progress("green", sha)
    return done(True, f"committed {sha}")


def conflicts(tree: str) -> list[str]:
    return git(tree, "diff", "--name-only", "--diff-filter=U")[1].split()


def mode_land_check() -> int:
    rc, _ = git(env("repo"), "merge-base", "--is-ancestor", env("base"), env("branch"))
    print(json.dumps({"ok": True, "moved": rc != 0, "detail": "main moved" if rc else "main has not moved"}))
    return 0


def mode_merge_main() -> int:
    tree = env("tree")
    if not (Path(tree) / ".git").exists():
        return done(False, "no tree")
    merging = git(tree, "rev-parse", "-q", "--verify", "MERGE_HEAD")[0] == 0
    out = ""
    if not merging:
        rc, out = git(tree, "merge", "--no-ff", "-m", f"bootstrap: merge {env('base')} into {env('branch')}", env("base"))
    left = conflicts(tree)
    if not merging and rc and not left:
        print(json.dumps({"ok": False, "clean": False, "conflicts": [], "detail": out}))
        return 0
    print(json.dumps({"ok": True, "clean": not left, "conflicts": left, "detail": out}))
    return 0


def mode_merge_finish() -> int:
    tree, files = env("tree"), listed("conflicts")
    stray = outside(changed(tree), files)
    marked = [f for f in files if (Path(tree) / f).is_file()
              and re.search(r"^(<{7}|>{7}) ", (Path(tree) / f).read_text(errors="replace"), re.M)]
    if stray or marked:
        return done(False, f"paths changed outside the conflict list: {stray}; conflict markers left in: {marked}")
    rc, out = git(tree, "add", "--", *files)
    if rc == 0:
        rc, out = git(tree, "commit", "--no-edit")
    if rc:
        return done(False, "merge commit refused:\n" + out)
    chosen("land", f"resolved merge of {env('base')}: {', '.join(files)}",
           "a resolver agent took each conflict; no conflict goes to the owner")
    return done(True, "merge committed")


def mode_retest() -> int:
    tree = env("tree")
    rc, out, found = pytest(tree, ["tests"])
    prc, pout = run(["uv", "run", "packcheck.py", "feature-pipeline"], tree)
    bad = sorted(found["FAILED"] | found["ERROR"])
    ok = rc == 0 and prc == 0 and not bad
    return done(ok, "all parts' tests pass" if ok else f"failing: {bad}\npackcheck exit {prc}: {pout}\n{out}")


def mode_land() -> int:
    repo, tree, base, branch = env("repo"), env("tree"), env("base"), env("branch")
    cur = git(repo, "rev-parse", "--abbrev-ref", "HEAD")[1]
    if cur != base:
        return done(False, f"{repo} is on {cur!r}, not {base!r}")
    files = git(repo, "diff", "--name-only", base, branch)[1].split()
    dirty = {p for p in changed(repo)}
    clash = sorted(dirty & set(files))
    if clash:
        return done(False, "uncommitted changes on main touch landed files: " + ", ".join(clash))
    rc, out = git(repo, "merge", "--ff-only", branch)
    if rc:
        return done(False, "fast-forward refused:\n" + out)
    return done(True, git(repo, "rev-parse", "--short", "HEAD")[1])


def mode_install() -> int:
    argv = ["uv", "run", "install.py", "hqptuner", "--workflows", *env("workflows").split()]
    rc, out = run(argv, env("tree"))
    return done(rc == 0, out or "installed")


MODES = {
    "tree": mode_tree, "todo": mode_todo, "red": mode_red, "green": mode_green,
    "paths": mode_paths, "commit": mode_commit, "land-check": mode_land_check,
    "merge-main": mode_merge_main, "merge-finish": mode_merge_finish,
    "retest": mode_retest, "land": mode_land, "install": mode_install,
}

if __name__ == "__main__":
    sys.exit(MODES[env("mode")]())
