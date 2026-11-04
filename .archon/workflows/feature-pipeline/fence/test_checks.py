import asyncio
import importlib.util
import os
import re
import time
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


def run(monkeypatch, root, command, timeout=None):
    module = load(monkeypatch, root, command, timeout)
    return asyncio.run(module.run_tests())


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


def test_timeout_kills_group(monkeypatch, tmp_path):
    start = time.monotonic()
    result = run(monkeypatch, tmp_path, "echo $$; sleep 30 & sleep 30", "1")
    assert time.monotonic() - start < 9
    assert " timed_out=true " in result.partition("\n")[0]
    pgid = int(result.splitlines()[1])
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        try:
            os.killpg(pgid, 0)
        except ProcessLookupError:
            return
        time.sleep(0.1)
    pytest.fail("process group still alive")


@pytest.mark.parametrize(("env", "name"), BAD_STARTUPS)
def test_startup_exits_nonzero_on_bad_environment(monkeypatch, tmp_path, env, name):
    assert startup_exit(monkeypatch, tmp_path, **env) in range(1, 256)


@pytest.mark.parametrize(("env", "name"), BAD_STARTUPS)
def test_startup_error_names_offending_variable(monkeypatch, tmp_path, capsys, env, name):
    startup_exit(monkeypatch, tmp_path, **env)
    assert name in capsys.readouterr().err
