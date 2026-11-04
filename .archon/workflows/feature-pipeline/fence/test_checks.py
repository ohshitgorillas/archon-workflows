import asyncio
import importlib.util
import os
import re
import signal
import subprocess
from pathlib import Path

import pytest

CHECKS = Path(__file__).with_name("checks.py")


def load(monkeypatch, root, command, timeout=None):
    if root is None:
        monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)
    else:
        monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(root))
    monkeypatch.setenv("FENCE_TEST_COMMAND", command)
    if timeout is None:
        monkeypatch.delenv("FENCE_TEST_TIMEOUT", raising=False)
    else:
        monkeypatch.setenv("FENCE_TEST_TIMEOUT", timeout)
    spec = importlib.util.spec_from_file_location("checks_under_test", CHECKS)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run(monkeypatch, root, command, timeout=None, clock=None):
    module = load(monkeypatch, root, command, timeout)
    if clock is None:
        return asyncio.run(module.run_tests())
    return asyncio.run(module.run_tests_with(clock(module)))


async def readable(fd):
    loop = asyncio.get_running_loop()
    ready = loop.create_future()
    loop.add_reader(fd, lambda: ready.done() or ready.set_result(None))
    try:
        await ready
    finally:
        loop.remove_reader(fd)


def virtual_clock(module, ready_fd=None):
    """A clock whose sleep advances its own reading and returns at once.

    With ready_fd, a sleep first waits until the command has written its
    ready line, so no deadline fires before the command reached its steady state.
    """
    elapsed = 0.0

    def monotonic():
        return elapsed

    async def sleep(seconds):
        nonlocal elapsed
        if ready_fd is not None:
            await readable(ready_fd)
        elapsed += seconds

    return module.Clock(monotonic=monotonic, sleep=sleep)


def dead(pid):
    """True once pid has exited or holds a pending SIGKILL, which it cannot escape.

    ps lists nothing for a pid that is gone; -L reports the thread's own pending
    mask, where the kernel queues SIGKILL for a process that a fatal signal hit.
    """
    ps = subprocess.run(
        ["ps", "-L", "-o", "stat=,pending=", "-p", str(pid)],
        capture_output=True, text=True, check=False,
    )
    rows = ps.stdout.split()
    if not rows:
        return True
    state, pending = rows[0], int(rows[1], 16)
    return state[0] in "ZX" or bool(pending & (1 << (signal.SIGKILL - 1)))


# Prints the shell's pid and a background child's pid, signals readiness on
# the ready fifo once both exist, then waits on a short foreground job, so the
# command ends by itself if no timeout fires.
BACKGROUNDED = "sleep 30 & echo $$ $!; sleep 3 & echo > ready; wait $!"


def run_past_timeout(monkeypatch, tmp_path, command):
    """Run command on a virtual clock past a production-sized timeout.

    Returns the header fields plus whether the background child is dead, then
    kills whatever is left of the process group.
    """
    os.mkfifo(tmp_path / "ready")
    fd = os.open(tmp_path / "ready", os.O_RDWR | os.O_NONBLOCK)
    try:
        result = run(
            monkeypatch, tmp_path, command, "900",
            clock=lambda module: virtual_clock(module, fd),
        )
    finally:
        os.close(fd)
    shell, child = (int(pid) for pid in body(result).split())
    evidence = {**header(result), "child_dead": dead(child)}
    try:
        os.killpg(shell, signal.SIGKILL)
    except ProcessLookupError:
        pass
    return evidence


def header(result):
    return dict(field.split("=", 1) for field in result.partition("\n")[0].split())


def body(result):
    return result.partition("\n")[2]


def startup_exit(monkeypatch, tmp_path, root="dir", command="true", timeout=None):
    (tmp_path / "f.txt").write_text("x")
    target = {
        "dir": tmp_path,
        "unset": None,
        "missing": tmp_path / "nope",
        "file": tmp_path / "f.txt",
    }
    with pytest.raises(SystemExit) as exc:
        load(monkeypatch, target[root], command, timeout)
    return exc.value.code


BAD_TIMEOUTS = ["abc", "0", "-5", "1.5", ""]
BAD_STARTUPS = [
    pytest.param({"root": "unset"}, "CLAUDE_PROJECT_DIR", id="root-unset"),
    pytest.param({"root": "missing"}, "CLAUDE_PROJECT_DIR", id="root-missing"),
    pytest.param({"root": "file"}, "CLAUDE_PROJECT_DIR", id="root-file"),
    pytest.param({"command": "  "}, "FENCE_TEST_COMMAND", id="command-blank"),
] + [
    pytest.param({"timeout": bad}, "FENCE_TEST_TIMEOUT", id=f"timeout-{bad!r}")
    for bad in BAD_TIMEOUTS
]


@pytest.mark.parametrize(("command", "code"), [("true", "0"), ("exit 7", "7")])
def test_reports_command_exit_code(monkeypatch, tmp_path, command, code):
    assert header(run(monkeypatch, tmp_path, command))["exit"] == code


def test_finished_run_reports_not_timed_out(monkeypatch, tmp_path):
    assert header(run(monkeypatch, tmp_path, "true"))["timed_out"] == "false"


@pytest.mark.parametrize("command", ["echo hello", "echo hello >&2"], ids=["stdout", "stderr"])
def test_returns_command_output(monkeypatch, tmp_path, command):
    assert body(run(monkeypatch, tmp_path, command)) == "hello"


def test_runs_in_root(monkeypatch, tmp_path):
    assert body(run(monkeypatch, tmp_path, "pwd")) == os.path.realpath(tmp_path)


def test_long_output_keeps_last_200_lines(monkeypatch, tmp_path):
    lines = body(run(monkeypatch, tmp_path, "seq 1 1000")).splitlines()
    assert [n for n in lines if n.isdigit()] == [str(i) for i in range(801, 1001)]


def test_long_output_reports_cut_line_count(monkeypatch, tmp_path):
    first = body(run(monkeypatch, tmp_path, "seq 1 1000")).splitlines()[0]
    assert re.findall(r"\d+", first) == ["800"]


def test_long_output_keeps_last_20000_chars(monkeypatch, tmp_path):
    result = run(monkeypatch, tmp_path, "head -c 50000 /dev/zero | tr '\\0' x")
    assert body(result) == "x" * 20000


def test_run_past_its_timeout_reports_timed_out(monkeypatch, tmp_path):
    result = run(monkeypatch, tmp_path, "sleep 3", "900", clock=virtual_clock)
    assert header(result)["timed_out"] == "true"


def test_timeout_kills_background_child_of_the_group(monkeypatch, tmp_path):
    assert run_past_timeout(monkeypatch, tmp_path, BACKGROUNDED)["child_dead"]


def test_timeout_sends_sigterm_before_sigkill(monkeypatch, tmp_path):
    assert run_past_timeout(monkeypatch, tmp_path, BACKGROUNDED)["exit"] == str(-signal.SIGTERM)


def test_timeout_escalates_to_sigkill_when_sigterm_is_ignored(monkeypatch, tmp_path):
    command = "trap '' TERM; " + BACKGROUNDED
    assert run_past_timeout(monkeypatch, tmp_path, command)["exit"] == str(-signal.SIGKILL)


@pytest.mark.parametrize(("env", "name"), BAD_STARTUPS)
def test_startup_exits_nonzero_on_bad_environment(monkeypatch, tmp_path, env, name):
    assert startup_exit(monkeypatch, tmp_path, **env) in range(1, 256)


@pytest.mark.parametrize(("env", "name"), BAD_STARTUPS)
def test_startup_error_names_offending_variable(monkeypatch, tmp_path, capsys, env, name):
    startup_exit(monkeypatch, tmp_path, **env)
    assert name in capsys.readouterr().err
