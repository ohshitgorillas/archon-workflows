import asyncio
import importlib.util
import os
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


def test_passing(monkeypatch, tmp_path):
    result = run(monkeypatch, tmp_path, "echo hello")
    first, _, rest = result.partition("\n")
    assert first.startswith("exit=0 timed_out=false seconds=")
    assert rest == "hello"


def test_failing_exit_code(monkeypatch, tmp_path):
    result = run(monkeypatch, tmp_path, "echo bad; exit 7")
    assert result.startswith("exit=7 timed_out=false")
    assert "bad" in result


def test_runs_in_root(monkeypatch, tmp_path):
    result = run(monkeypatch, tmp_path, "pwd")
    assert result.splitlines()[1] == os.path.realpath(tmp_path)


def test_stderr_captured(monkeypatch, tmp_path):
    result = run(monkeypatch, tmp_path, "echo oops >&2")
    assert "oops" in result


def test_long_output_cut_to_tail(monkeypatch, tmp_path):
    result = run(monkeypatch, tmp_path, "seq 1 1000")
    lines = result.splitlines()
    assert lines[1] == "[... 800 earlier lines cut]"
    assert lines[2] == "801"
    assert lines[-1] == "1000"
    assert len(lines) == 2 + 200


def test_long_output_cut_by_chars(monkeypatch, tmp_path):
    result = run(monkeypatch, tmp_path, "for i in 1 2 3 4 5; do head -c 10000 /dev/zero | tr '\\0' x; echo; done")
    body = result.partition("\n")[2]
    assert "earlier lines cut]" in body
    assert len(body.partition("\n")[2]) <= 20000


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


def test_missing_project_dir(monkeypatch):
    with pytest.raises(SystemExit) as exc:
        load(monkeypatch, None, "true")
    assert exc.value.code != 0


def test_empty_command(monkeypatch, tmp_path, capsys):
    with pytest.raises(SystemExit) as exc:
        load(monkeypatch, tmp_path, "  ")
    assert exc.value.code != 0
    assert "FENCE_TEST_COMMAND" in capsys.readouterr().err


@pytest.mark.parametrize("bad", ["abc", "0", "-5", "1.5", ""])
def test_bad_timeout(monkeypatch, tmp_path, capsys, bad):
    with pytest.raises(SystemExit) as exc:
        load(monkeypatch, tmp_path, "true", bad)
    assert exc.value.code != 0
    assert "FENCE_TEST_TIMEOUT" in capsys.readouterr().err
