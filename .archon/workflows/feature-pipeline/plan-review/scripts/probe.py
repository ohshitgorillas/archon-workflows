"""Check probe: reads each Plan step's check against the run's root and branch.

Reads the Plan from INPUTS_PLAN, the checkout root from INPUTS_ROOT and the
branch from INPUTS_BRANCH. Runs no check and writes nothing. Files one finding
per hit, targeted at the step, and prints {"findings": [...]} as JSON on stdout:

- a cd or pushd target, or a git -C or make -C directory, that is not an
  existing directory under the root, unless it is a directory prefix of a path
  some step of the same Plan lists;
- git rev-parse --abbrev-ref HEAD, git branch --show-current or
  git symbolic-ref --short HEAD compared by =, == or != with a literal other
  than the run's branch;
- any git checkout, git switch or git worktree.
"""

import json
import os
import pathlib
import re
import shlex
import sys
from typing import NamedTuple

SEPARATORS = {"&&", "||", ";", "|", "&", "(", ")", ";;", "|&"}
REDIRECTS = {">", ">>", "<", "<<", "<<<", ">&", "<&", "&>", "&>>", ">|"}
KEYWORDS = {"if", "then", "else", "elif", "do", "while", "until", "!", "time", "{", "}", "fi", "done"}
COMPARE = {"=", "==", "!="}
BRANCH_READS = (
    ["git", "rev-parse", "--abbrev-ref", "HEAD"],
    ["git", "branch", "--show-current"],
    ["git", "symbolic-ref", "--short", "HEAD"],
)
MOVES = {"checkout", "switch", "worktree"}
SUB = re.compile(r"^__probe_sub_(\d+)__$")


class Hit(NamedTuple):
    """One probe hit in a check: what was found and how to fix it."""

    cause: str
    fix: str


def closing(text: str, start: int) -> int:
    """Return the index of the ) that closes the ( at start, or len(text) when none does."""
    depth = 0
    for j in range(start, len(text)):
        depth += {"(": 1, ")": -1}.get(text[j], 0)
        if depth == 0:
            return j
    return len(text)


def lift(text: str, subs: list[str]) -> str:
    """Replace each $(...) and `...` in text by a placeholder; keep its body in subs."""
    out = []
    i = 0
    while i < len(text):
        if text.startswith("$(", i):
            j = closing(text, i + 1)
            body = text[i + 2 : j]
        elif text[i] == "`":
            j = text.find("`", i + 1)
            j = len(text) if j < 0 else j
            body = text[i + 1 : j]
        else:
            out.append(text[i])
            i += 1
            continue
        subs.append(body)
        out.append(f"__probe_sub_{len(subs) - 1}__")
        i = j + 1
    return "".join(out)


def tokens(text: str) -> list[str]:
    """Split a shell command into words and operators; raise ValueError when it does not parse."""
    lexer = shlex.shlex(text.replace("\n", " ; "), posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    return list(lexer)


def commands(words: list[str]) -> list[list[str]]:
    """Split a token list into simple commands, keeping ( and ) as their own entries."""
    out: list[list[str]] = []
    current: list[str] = []
    skip = False
    for word in words:
        if skip:
            skip = False
            continue
        if word in SEPARATORS:
            if current:
                out.append(current)
            current = []
            if word in ("(", ")"):
                out.append([word])
            continue
        if word in REDIRECTS:
            skip = True
            continue
        if not current and (word in KEYWORDS or re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", word)):
            continue
        current.append(word)
    if current:
        out.append(current)
    return out


def branch_read(body: str) -> str | None:
    """Return the branch-reading command in body, or None when body is not one."""
    words = [w for w in body.split() if w not in ("-q", "--quiet")]
    for read in BRANCH_READS:
        if words == read:
            return " ".join(read)
    return None


def git_args(command: list[str]) -> tuple[list[str], list[str]]:
    """Return (-C directories, remaining words) of a git command after its global options."""
    dirs = []
    i = 1
    while i < len(command):
        word = command[i]
        if word == "-C" and i + 1 < len(command):
            dirs.append(command[i + 1])
            i += 2
        elif word == "-c" and i + 1 < len(command):
            i += 2
        elif word.startswith("-"):
            i += 1
        else:
            break
    return dirs, command[i:]


def make_dirs(command: list[str]) -> list[str]:
    """Return every -C or --directory directory of a make command."""
    dirs = []
    for i, word in enumerate(command[1:], 1):
        if word == "-C" and i + 1 < len(command):
            dirs.append(command[i + 1])
        elif word.startswith("-C") and len(word) > 2:
            dirs.append(word[2:])
        elif word.startswith("--directory="):
            dirs.append(word.split("=", 1)[1])
    return dirs


class Probe:
    """Reads one Plan's checks against a checkout root and branch."""

    def __init__(self, root: pathlib.Path, branch: str, listed: list[str]):
        self.root = root.resolve()
        self.branch = branch
        self.prefixes = set()
        for path in listed:
            for parent in pathlib.PurePosixPath(path).parents:
                if str(parent) != ".":
                    self.prefixes.add(str(parent))

    def directory(self, cwd: pathlib.Path, target: str, how: str) -> tuple[pathlib.Path, Hit | None]:
        """Resolve a directory target from cwd; return it and a hit when it is not under the root."""
        if "$" in target or target == "-":
            return cwd, None
        place = pathlib.Path(os.path.normpath(cwd / target))
        if place == self.root:
            return place, None
        if place.is_relative_to(self.root) and (place.is_dir() or str(place.relative_to(self.root)) in self.prefixes):
            return place, None
        return place, Hit(
            f"{how} {target}: {place} is not an existing directory under the checkout root {self.root}, "
            "and no step of this Plan lists a path inside it",
            "run the check from the checkout root, naming paths relative to it; never cd into another checkout",
        )

    def read(self, text: str, cwd: pathlib.Path | None = None) -> list[Hit]:
        """Return every hit in one check, or in a command substitution run from cwd."""
        cwd = cwd or self.root
        subs: list[str] = []
        hits: list[Hit] = []
        words: list[str] = []
        try:
            words = tokens(lift(text, subs))
        except ValueError as error:
            hits.append(
                Hit(
                    f"the check does not parse as shell ({error}), so bash -c fails on it at build",
                    "close every quote and bracket in the check",
                )
            )
        for i, word in enumerate(words):
            match = SUB.match(word)
            if not match:
                continue
            read = branch_read(subs[int(match.group(1))])
            if read is None:
                continue
            for op_at, other_at in ((i + 1, i + 2), (i - 1, i - 2)):
                if 0 <= op_at < len(words) and 0 <= other_at < len(words) and words[op_at] in COMPARE:
                    other = words[other_at]
                    if "$" in other or SUB.match(other) or other in SEPARATORS or other in ("[", "[[", "test"):
                        continue
                    if other != self.branch:
                        hits.append(
                            Hit(
                                f"the check compares `{read}` {words[op_at]} `{other}`, but the branch of this run is "
                                f"`{self.branch}`; every check runs on that branch, so the comparison never holds as meant",
                                "assert nothing about the branch, or assert the branch of this run",
                            )
                        )
        stack: list[pathlib.Path] = []
        pushed: list[pathlib.Path] = []
        for command in commands(words):
            if command == ["("]:
                stack.append(cwd)
                continue
            if command == [")"]:
                cwd = stack.pop() if stack else cwd
                continue
            for word in command:
                for index in re.findall(r"__probe_sub_(\d+)__", word):
                    hits.extend(self.read(subs[int(index)], cwd))
            name = command[0]
            if name in ("cd", "pushd"):
                args = [w for w in command[1:] if not w.startswith("-") or w == "-"]
                if args:
                    if name == "pushd":
                        pushed.append(cwd)
                    cwd, hit = self.directory(cwd, args[0], name)
                    if hit:
                        hits.append(hit)
            elif name == "popd":
                cwd = pushed.pop() if pushed else cwd
            elif name == "git":
                dirs, rest = git_args(command)
                for target in dirs:
                    _, hit = self.directory(cwd, target, "git -C")
                    if hit:
                        hits.append(hit)
                if rest and rest[0] in MOVES:
                    hits.append(
                        Hit(
                            f"the check runs `git {rest[0]}`; a check never changes the branch or a worktree",
                            f"drop `git {rest[0]}` and check the checkout of this run as it stands",
                        )
                    )
            elif name == "make":
                for target in make_dirs(command):
                    _, hit = self.directory(cwd, target, "make -C")
                    if hit:
                        hits.append(hit)
        return hits


def main() -> int:
    plan = json.loads(os.environ["INPUTS_PLAN"])
    root = pathlib.Path(os.environ["INPUTS_ROOT"])
    branch = os.environ["INPUTS_BRANCH"]
    steps = plan.get("steps") or []
    listed = [path for step in steps for path in step.get("paths") or []]
    probe = Probe(root, branch, listed)
    findings = []
    for step in steps:
        for hit in probe.read(str(step.get("check", ""))):
            findings.append(
                {
                    "author": "plan",
                    "target": step.get("id", ""),
                    "cause": f"check `{step.get('check', '')}`: {hit.cause}",
                    "fix": hit.fix,
                    "severity": "blocking",
                    "design_it_in": False,
                }
            )
    print(json.dumps({"findings": findings}, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
