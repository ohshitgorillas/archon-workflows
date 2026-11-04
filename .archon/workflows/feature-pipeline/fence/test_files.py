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


def startup_exit(monkeypatch, tmp_path, root):
    put(tmp_path, "f.txt")
    target = {"unset": None, "missing": tmp_path / "nope", "file": tmp_path / "f.txt"}
    with pytest.raises(SystemExit) as exc:
        load(monkeypatch, target[root])
    return exc.value.code


def numbered(text):
    return [(int(n), line) for n, line in (row.split("\t", 1) for row in text.splitlines())]


@pytest.mark.parametrize("root", ["unset", "missing", "file"])
def test_startup_exits_nonzero_without_project_directory(monkeypatch, tmp_path, root):
    assert startup_exit(monkeypatch, tmp_path, root) in range(1, 256)


def test_startup_error_names_project_dir_variable(monkeypatch, tmp_path, capsys):
    startup_exit(monkeypatch, tmp_path, "unset")
    assert "CLAUDE_PROJECT_DIR" in capsys.readouterr().err


def test_read_numbers_every_line(monkeypatch, tmp_path):
    put(tmp_path, "src/a.txt", "one\ntwo\nthree\n")
    f = load(monkeypatch, tmp_path, read="src")
    assert numbered(f.read_file("src/a.txt")) == [(1, "one"), (2, "two"), (3, "three")]


def test_read_offset_and_limit_select_numbered_lines(monkeypatch, tmp_path):
    put(tmp_path, "src/a.txt", "one\ntwo\nthree\n")
    f = load(monkeypatch, tmp_path, read="src")
    assert numbered(f.read_file("src/a.txt", offset=1, limit=1)) == [(2, "two")]


def test_read_absolute_path_inside_root(monkeypatch, tmp_path):
    p = put(tmp_path, "src/a.txt", "hi\n")
    f = load(monkeypatch, tmp_path, read="src")
    assert numbered(f.read_file(str(p))) == [(1, "hi")]


def test_read_outside_read_folders_refused(monkeypatch, tmp_path):
    put(tmp_path, "other/b.txt")
    f = load(monkeypatch, tmp_path, read="src")
    with pytest.raises(PermissionError, match="FENCE_READ"):
        f.read_file("other/b.txt")


@pytest.mark.parametrize(
    ("call", "refused"),
    [
        (lambda f: f.read_file("a.txt"), "FENCE_READ"),
        (lambda f: f.write_file("a.txt", "no"), "FENCE_WRITE"),
    ],
    ids=["read", "write"],
)
def test_empty_fence_variables_allow_nothing(monkeypatch, tmp_path, call, refused):
    put(tmp_path, "a.txt")
    f = load(monkeypatch, tmp_path)
    with pytest.raises(PermissionError, match=refused):
        call(f)


def test_write_creates_missing_parent_folders(monkeypatch, tmp_path):
    f = load(monkeypatch, tmp_path, write="out")
    f.write_file("out/a/b/c.txt", "deep")
    assert (tmp_path / "out/a/b/c.txt").read_text() == "deep"


def test_write_outside_write_folders_refused(monkeypatch, tmp_path):
    f = load(monkeypatch, tmp_path, read=".", write="out")
    with pytest.raises(PermissionError, match="FENCE_WRITE"):
        f.write_file("src/a.txt", "no")


@pytest.mark.parametrize(
    ("call", "refused"),
    [
        (lambda f: f.read_file("tests2/x.txt"), "FENCE_READ"),
        (lambda f: f.write_file("tests2/y.txt", "no"), "FENCE_WRITE"),
    ],
    ids=["read", "write"],
)
def test_fence_folder_does_not_cover_sibling_with_prefix_name(
    monkeypatch, tmp_path, call, refused
):
    put(tmp_path, "tests2/x.txt")
    f = load(monkeypatch, tmp_path, read="tests", write="tests")
    with pytest.raises(PermissionError, match=refused):
        call(f)


@pytest.mark.parametrize(
    "bad", ["tests/t.py", "plans/approved/p.md", "specs/approved/s.md"]
)
def test_write_refused_inside_denied_folder(monkeypatch, tmp_path, bad):
    f = load(
        monkeypatch,
        tmp_path,
        read=".",
        write=".",
        deny="tests:plans/approved:specs/approved",
    )
    with pytest.raises(PermissionError):
        f.write_file(bad, "no")


def test_deny_does_not_cover_sibling_with_prefix_name(monkeypatch, tmp_path):
    f = load(monkeypatch, tmp_path, read=".", write=".", deny="tests")
    f.write_file("tests2/y.txt", "ok")
    assert (tmp_path / "tests2/y.txt").read_text() == "ok"


@pytest.mark.parametrize(
    "bad", [".git/hooks/pre-commit", ".archon/w.yaml", ".claude/settings.json"]
)
def test_write_refused_in_always_denied_folder(monkeypatch, tmp_path, bad):
    f = load(monkeypatch, tmp_path, read=".", write=".")
    with pytest.raises(PermissionError):
        f.write_file(bad, "no")


@pytest.mark.parametrize(
    "call",
    [
        lambda f: f.edit_file(".archon/w.yaml", "x", "y"),
        lambda f: f.delete_file(".archon/w.yaml"),
        lambda f: f.copy_file("a.txt", ".archon/w.yaml"),
    ],
    ids=["edit", "delete", "copy"],
)
def test_writing_tools_refused_in_always_denied_folder(monkeypatch, tmp_path, call):
    put(tmp_path, "a.txt")
    put(tmp_path, ".archon/w.yaml")
    f = load(monkeypatch, tmp_path, read=".", write=".")
    with pytest.raises(PermissionError):
        call(f)


@pytest.mark.parametrize(
    "call",
    [
        lambda f: f.read_file("../secret.txt"),
        lambda f: f.write_file("../new.txt", "no"),
        lambda f: f.write_file("a/../../new.txt", "no"),
    ],
    ids=["read", "write", "write-nested"],
)
def test_dotdot_escape_refused(monkeypatch, tmp_path, call):
    root = tmp_path / "root"
    root.mkdir()
    (tmp_path / "secret.txt").write_text("s")
    f = load(monkeypatch, root, read=".", write=".")
    with pytest.raises(PermissionError):
        call(f)


@pytest.mark.parametrize(
    "call",
    [
        lambda f: f.read_file("link/s.txt"),
        lambda f: f.read_file("flink"),
        lambda f: f.write_file("link/new.txt", "no"),
        lambda f: f.write_file("flink", "no"),
    ],
    ids=["read-via-dir", "read-via-file", "write-via-dir", "write-via-file"],
)
def test_symlink_out_of_root_refused(monkeypatch, tmp_path, call):
    root = tmp_path / "root"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "s.txt").write_text("s")
    (root / "link").symlink_to(outside)
    (root / "flink").symlink_to(outside / "s.txt")
    f = load(monkeypatch, root, read=".", write=".")
    with pytest.raises(PermissionError):
        call(f)


def test_edit_replaces_single_occurrence(monkeypatch, tmp_path):
    put(tmp_path, "src/a.txt", "alpha beta\nbeta\n")
    f = load(monkeypatch, tmp_path, read="src", write="src")
    f.edit_file("src/a.txt", "alpha", "ALPHA")
    assert (tmp_path / "src/a.txt").read_text() == "ALPHA beta\nbeta\n"


def test_edit_replace_all_replaces_every_occurrence(monkeypatch, tmp_path):
    put(tmp_path, "src/a.txt", "alpha beta\nbeta\n")
    f = load(monkeypatch, tmp_path, read="src", write="src")
    f.edit_file("src/a.txt", "beta", "gamma", replace_all=True)
    assert (tmp_path / "src/a.txt").read_text() == "alpha gamma\ngamma\n"


@pytest.mark.parametrize("old", ["beta", "zeta"], ids=["ambiguous", "missing"])
def test_edit_refuses_old_text_not_found_exactly_once(monkeypatch, tmp_path, old):
    put(tmp_path, "src/a.txt", "alpha beta\nbeta\n")
    f = load(monkeypatch, tmp_path, read="src", write="src")
    with pytest.raises(ValueError):
        f.edit_file("src/a.txt", old, "gamma")


@pytest.mark.parametrize(
    ("read", "write", "refused"),
    [("", "src", "FENCE_READ"), ("src", "", "FENCE_WRITE")],
)
def test_edit_needs_read_and_write(monkeypatch, tmp_path, read, write, refused):
    put(tmp_path, "src/a.txt", "abc")
    f = load(monkeypatch, tmp_path, read=read, write=write)
    with pytest.raises(PermissionError, match=refused):
        f.edit_file("src/a.txt", "a", "b")


def test_copy_creates_missing_destination_folders(monkeypatch, tmp_path):
    put(tmp_path, "plans/plan.json", "first\n")
    f = load(monkeypatch, tmp_path, read="plans", write="plans/approved")
    f.copy_file("plans/plan.json", "plans/approved/round/plan.json")
    assert (tmp_path / "plans/approved/round/plan.json").read_text() == "first\n"


def test_copy_overwrites_existing_destination(monkeypatch, tmp_path):
    put(tmp_path, "plans/plan.json", "second\n")
    put(tmp_path, "plans/approved/plan.json", "first\n")
    f = load(monkeypatch, tmp_path, read="plans", write="plans/approved")
    f.copy_file("plans/plan.json", "plans/approved/plan.json")
    assert (tmp_path / "plans/approved/plan.json").read_text() == "second\n"


@pytest.mark.parametrize(
    ("read", "write", "refused"),
    [("out", "out", "FENCE_READ"), ("src", "", "FENCE_WRITE")],
)
def test_copy_refuses_unreadable_source_or_unwritable_destination(
    monkeypatch, tmp_path, read, write, refused
):
    put(tmp_path, "src/a.txt")
    f = load(monkeypatch, tmp_path, read=read, write=write)
    with pytest.raises(PermissionError, match=refused):
        f.copy_file("src/a.txt", "out/a.txt")


def test_copy_refuses_directory_source(monkeypatch, tmp_path):
    (tmp_path / "src/d").mkdir(parents=True)
    f = load(monkeypatch, tmp_path, read="src", write="out")
    with pytest.raises(ValueError):
        f.copy_file("src/d", "out/d")


def test_delete_removes_file(monkeypatch, tmp_path):
    put(tmp_path, "out/a.txt")
    f = load(monkeypatch, tmp_path, write="out")
    f.delete_file("out/a.txt")
    assert not (tmp_path / "out/a.txt").exists()


def test_delete_refuses_directory(monkeypatch, tmp_path):
    (tmp_path / "out/d").mkdir(parents=True)
    f = load(monkeypatch, tmp_path, write="out")
    with pytest.raises(ValueError):
        f.delete_file("out/d")


def test_list_root_shows_only_path_to_readable_folder(monkeypatch, tmp_path):
    put(tmp_path, "tests/t.py")
    put(tmp_path, "src/a.py")
    put(tmp_path, "top.txt")
    f = load(monkeypatch, tmp_path, read="tests")
    assert f.list_directory(".").splitlines() == ["tests/"]


def test_list_readable_folder_marks_subfolders_with_slash(monkeypatch, tmp_path):
    put(tmp_path, "tests/t.py")
    put(tmp_path, "tests/sub/u.py")
    f = load(monkeypatch, tmp_path, read="tests")
    assert sorted(f.list_directory("tests").splitlines()) == ["sub/", "t.py"]


def test_list_parent_of_readable_folder_hides_unreadable_files(monkeypatch, tmp_path):
    put(tmp_path, "tests/t.py")
    put(tmp_path, "tests/sub/u.py")
    f = load(monkeypatch, tmp_path, read="tests/sub")
    assert f.list_directory("tests").splitlines() == ["sub/"]


def test_list_unreadable_folder_refused(monkeypatch, tmp_path):
    put(tmp_path, "src/a.py")
    f = load(monkeypatch, tmp_path, read="tests")
    with pytest.raises(PermissionError, match="FENCE_READ"):
        f.list_directory("src")


def test_find_returns_only_readable_matches(monkeypatch, tmp_path):
    put(tmp_path, "tests/t.py")
    put(tmp_path, "tests2/t.py")
    put(tmp_path, "src/a.py")
    f = load(monkeypatch, tmp_path, read="tests")
    assert f.find_files("**/*.py").splitlines() == ["tests/t.py"]


def test_find_drops_matches_resolving_outside_root(monkeypatch, tmp_path):
    root = tmp_path / "root"
    put(root, "sub/in.txt")
    put(tmp_path, "outside/s.txt")
    (root / "link").symlink_to(tmp_path / "outside")
    f = load(monkeypatch, root, read=".")
    assert f.find_files("*/*.txt").splitlines() == ["sub/in.txt"]


def test_find_stops_at_500_results(monkeypatch, tmp_path):
    for i in range(501):
        put(tmp_path, f"d/{i:04}.txt")
    f = load(monkeypatch, tmp_path, read=".")
    assert len(f.find_files("d/*.txt").splitlines()) == 500


@pytest.mark.parametrize(
    ("decoy", "data"),
    [
        ("src/a.py", b"needle secret\n"),
        ("tests2/b.py", b"needle other\n"),
        ("tests/.git/c", b"needle git\n"),
        ("tests/bin.dat", b"needle\0\1\2"),
    ],
    ids=["unreadable", "prefix-sibling", "git", "binary"],
)
def test_grep_hits_only_readable_text_outside_git(monkeypatch, tmp_path, decoy, data):
    put(tmp_path, "tests/t.py", "needle one\nplain\n")
    (tmp_path / decoy).parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / decoy).write_bytes(data)
    f = load(monkeypatch, tmp_path, read="tests")
    assert f.grep("needle").splitlines() == ["tests/t.py:1:needle one"]


def test_grep_glob_filters_file_names(monkeypatch, tmp_path):
    put(tmp_path, "tests/t.py", "needle one\n")
    put(tmp_path, "tests/u.txt", "needle two\n")
    f = load(monkeypatch, tmp_path, read="tests")
    assert f.grep("needle", glob="*.txt").splitlines() == ["tests/u.txt:1:needle two"]


def test_grep_unreadable_path_refused(monkeypatch, tmp_path):
    put(tmp_path, "src/a.py", "needle\n")
    f = load(monkeypatch, tmp_path, read="tests")
    with pytest.raises(PermissionError, match="FENCE_READ"):
        f.grep("needle", path="src")


def test_grep_stops_at_500_hits(monkeypatch, tmp_path):
    put(tmp_path, "big.txt", "hit\n" * 501)
    f = load(monkeypatch, tmp_path, read=".")
    assert len(f.grep("hit").splitlines()) == 500
