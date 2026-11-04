import importlib.util
from pathlib import Path

import pytest

SRC = Path(__file__).with_name("files.py")


def load(monkeypatch, root, read="", write="", deny=""):
    if root is None:
        monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)
    else:
        monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(root))
    monkeypatch.setenv("FENCE_READ", read)
    monkeypatch.setenv("FENCE_WRITE", write)
    monkeypatch.setenv("FENCE_DENY", deny)
    spec = importlib.util.spec_from_file_location("fence_files_under_test", SRC)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def put(root, rel, text="x\n"):
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)
    return p


def test_missing_project_dir_fails_startup(monkeypatch, capsys):
    with pytest.raises(SystemExit) as exc:
        load(monkeypatch, None)
    assert exc.value.code != 0
    assert "CLAUDE_PROJECT_DIR" in capsys.readouterr().err


def test_project_dir_not_a_directory_fails_startup(monkeypatch, tmp_path):
    with pytest.raises(SystemExit):
        load(monkeypatch, tmp_path / "nope")


def test_read_allowed_and_numbered(monkeypatch, tmp_path):
    put(tmp_path, "src/a.txt", "one\ntwo\nthree\n")
    f = load(monkeypatch, tmp_path, read="src")
    assert f.read_file("src/a.txt") == "     1\tone\n     2\ttwo\n     3\tthree"
    assert f.read_file("src/a.txt", offset=1, limit=1) == "     2\ttwo"


def test_read_denied(monkeypatch, tmp_path):
    put(tmp_path, "src/a.txt")
    put(tmp_path, "other/b.txt")
    f = load(monkeypatch, tmp_path, read="src")
    with pytest.raises(PermissionError, match="other/b.txt.*FENCE_READ"):
        f.read_file("other/b.txt")


def test_absolute_path_inside_root_allowed(monkeypatch, tmp_path):
    p = put(tmp_path, "src/a.txt", "hi\n")
    f = load(monkeypatch, tmp_path, read="src")
    assert f.read_file(str(p)).endswith("hi")


def test_write_allowed_and_denied(monkeypatch, tmp_path):
    f = load(monkeypatch, tmp_path, read=".", write="out")
    f.write_file("out/a.txt", "hello")
    assert (tmp_path / "out/a.txt").read_text() == "hello"
    with pytest.raises(PermissionError, match="FENCE_WRITE"):
        f.write_file("src/a.txt", "no")
    assert not (tmp_path / "src").exists()


def test_new_nested_file_creates_parents(monkeypatch, tmp_path):
    f = load(monkeypatch, tmp_path, write="out")
    f.write_file("out/a/b/c.txt", "deep")
    assert (tmp_path / "out/a/b/c.txt").read_text() == "deep"


def test_deny_inside_write_root_implementer_case(monkeypatch, tmp_path):
    f = load(
        monkeypatch,
        tmp_path,
        read=".",
        write=".",
        deny="tests:plans/approved:specs/approved:.archon:.claude",
    )
    f.write_file("src/ok.py", "ok")
    f.write_file("plans/draft/p.md", "ok")
    for bad in ("tests/t.py", "plans/approved/p.md", "specs/approved/s.md"):
        with pytest.raises(PermissionError, match="denied folder"):
            f.write_file(bad, "no")


def test_git_always_denied(monkeypatch, tmp_path):
    f = load(monkeypatch, tmp_path, read=".", write=".")
    with pytest.raises(PermissionError, match="denied folder"):
        f.write_file(".git/hooks/pre-commit", "no")
    assert not (tmp_path / ".git").exists()


@pytest.mark.parametrize("bad", [".archon/w.yaml", ".claude/settings.json"])
def test_archon_and_claude_always_denied(monkeypatch, tmp_path, bad):
    f = load(monkeypatch, tmp_path, read=".", write=".")
    with pytest.raises(PermissionError, match="denied folder"):
        f.write_file(bad, "no")
    put(tmp_path, bad)
    with pytest.raises(PermissionError):
        f.edit_file(bad, "x", "y")
    with pytest.raises(PermissionError):
        f.delete_file(bad)


def test_dotdot_escape_refused(monkeypatch, tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    (tmp_path / "secret.txt").write_text("s")
    f = load(monkeypatch, root, read=".", write=".")
    with pytest.raises(PermissionError, match="outside"):
        f.read_file("../secret.txt")
    with pytest.raises(PermissionError, match="outside"):
        f.write_file("../new.txt", "no")
    with pytest.raises(PermissionError, match="outside"):
        f.write_file("a/../../new.txt", "no")
    assert not (tmp_path / "new.txt").exists()


def test_symlink_out_refused(monkeypatch, tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "s.txt").write_text("s")
    (root / "link").symlink_to(outside)
    (root / "flink").symlink_to(outside / "s.txt")
    f = load(monkeypatch, root, read=".", write=".")
    with pytest.raises(PermissionError, match="outside"):
        f.read_file("link/s.txt")
    with pytest.raises(PermissionError, match="outside"):
        f.read_file("flink")
    with pytest.raises(PermissionError, match="outside"):
        f.write_file("link/new.txt", "no")
    with pytest.raises(PermissionError, match="outside"):
        f.write_file("flink", "no")
    assert (outside / "s.txt").read_text() == "s"
    assert not (outside / "new.txt").exists()


def test_component_match_not_prefix(monkeypatch, tmp_path):
    put(tmp_path, "tests2/x.txt")
    put(tmp_path, "tests/x.txt")
    f = load(monkeypatch, tmp_path, read="tests", write="tests")
    assert f.read_file("tests/x.txt")
    with pytest.raises(PermissionError):
        f.read_file("tests2/x.txt")
    with pytest.raises(PermissionError):
        f.write_file("tests2/y.txt", "no")
    g = load(monkeypatch, tmp_path, read=".", write=".", deny="tests")
    g.write_file("tests2/y.txt", "ok")
    with pytest.raises(PermissionError):
        g.write_file("tests/y.txt", "no")


def test_empty_env_means_none(monkeypatch, tmp_path):
    put(tmp_path, "a.txt")
    f = load(monkeypatch, tmp_path)
    with pytest.raises(PermissionError):
        f.read_file("a.txt")
    with pytest.raises(PermissionError):
        f.write_file("a.txt", "no")


def test_edit_file(monkeypatch, tmp_path):
    put(tmp_path, "src/a.txt", "alpha beta\nbeta\n")
    f = load(monkeypatch, tmp_path, read="src", write="src")
    with pytest.raises(ValueError, match="not unique"):
        f.edit_file("src/a.txt", "beta", "gamma")
    with pytest.raises(ValueError, match="not found"):
        f.edit_file("src/a.txt", "zeta", "gamma")
    f.edit_file("src/a.txt", "alpha", "ALPHA")
    assert (tmp_path / "src/a.txt").read_text() == "ALPHA beta\nbeta\n"
    f.edit_file("src/a.txt", "beta", "gamma", replace_all=True)
    assert (tmp_path / "src/a.txt").read_text() == "ALPHA gamma\ngamma\n"


def test_edit_needs_read_and_write(monkeypatch, tmp_path):
    put(tmp_path, "src/a.txt", "abc")
    f = load(monkeypatch, tmp_path, read="", write="src")
    with pytest.raises(PermissionError, match="FENCE_READ"):
        f.edit_file("src/a.txt", "a", "b")
    g = load(monkeypatch, tmp_path, read="src", write="")
    with pytest.raises(PermissionError, match="FENCE_WRITE"):
        g.edit_file("src/a.txt", "a", "b")


def test_delete_file(monkeypatch, tmp_path):
    put(tmp_path, "out/a.txt")
    (tmp_path / "out/d").mkdir()
    f = load(monkeypatch, tmp_path, write="out")
    with pytest.raises(ValueError, match="not a file"):
        f.delete_file("out/d")
    f.delete_file("out/a.txt")
    assert not (tmp_path / "out/a.txt").exists()


def test_list_directory_hides_unreadable(monkeypatch, tmp_path):
    put(tmp_path, "tests/t.py")
    put(tmp_path, "tests/sub/u.py")
    put(tmp_path, "src/a.py")
    put(tmp_path, "top.txt")
    f = load(monkeypatch, tmp_path, read="tests")
    assert f.list_directory(".").splitlines() == ["tests/"]
    assert f.list_directory("tests").splitlines() == ["sub/", "t.py"]
    with pytest.raises(PermissionError):
        f.list_directory("src")
    g = load(monkeypatch, tmp_path, read="tests/sub")
    assert g.list_directory(".").splitlines() == ["tests/"]
    assert g.list_directory("tests").splitlines() == ["sub/"]


def test_list_directory_dirs_have_slash(monkeypatch, tmp_path):
    put(tmp_path, "d/f.txt")
    put(tmp_path, "g.txt")
    f = load(monkeypatch, tmp_path, read=".")
    assert f.list_directory().splitlines() == ["d/", "g.txt"]


def test_find_files_hides_unreadable(monkeypatch, tmp_path):
    put(tmp_path, "tests/t.py")
    put(tmp_path, "tests2/t.py")
    put(tmp_path, "src/a.py")
    f = load(monkeypatch, tmp_path, read="tests")
    assert f.find_files("**/*.py").splitlines() == ["tests/t.py"]
    assert f.find_files("../*").strip() == ""


def test_find_files_cap(monkeypatch, tmp_path):
    for i in range(520):
        put(tmp_path, f"d/{i:04}.txt")
    f = load(monkeypatch, tmp_path, read=".")
    assert len(f.find_files("d/*.txt").splitlines()) == 500


def test_grep_hides_unreadable_and_skips_binary_and_git(monkeypatch, tmp_path):
    put(tmp_path, "tests/t.py", "needle one\nplain\n")
    put(tmp_path, "tests/.git/c", "needle git\n")
    (tmp_path / "tests/bin.dat").write_bytes(b"needle\0\1\2")
    put(tmp_path, "src/a.py", "needle secret\n")
    put(tmp_path, "tests2/b.py", "needle other\n")
    f = load(monkeypatch, tmp_path, read="tests")
    assert f.grep("needle").splitlines() == ["tests/t.py:1:needle one"]
    assert f.grep("needle", glob="*.dat") == ""
    with pytest.raises(PermissionError):
        f.grep("needle", path="src")


def test_grep_cap(monkeypatch, tmp_path):
    put(tmp_path, "big.txt", "hit\n" * 600)
    f = load(monkeypatch, tmp_path, read=".")
    assert len(f.grep("hit").splitlines()) == 500
