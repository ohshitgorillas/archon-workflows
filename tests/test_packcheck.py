import contextlib
import io
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import packcheck

GOOD = """name: {name}
description: proof
nodes:
  - id: echo
    bash: 'echo "{{\\"word\\": \\"ok\\"}}"'
    output_format:
      type: object
      properties: {{word: {{type: string}}}}
      required: [word]
      additionalProperties: false
"""
STUB = "fixture: {expect: completed, reached: [echo]}\necho: {word: ok}\n"
STUB_BAD = "fixture: {expect: failed, fail-node: echo}\necho: {word: ok}\n"
# echo stubbed with a value that breaks its output_format, so the node fails as expected
STUB_FAILS_AS_EXPECTED = "fixture: {expect: failed, fail-node: echo}\necho: {word: 5}\n"


def snapshot(p: Path):
    """The root itself and everything under it, each with st_mtime_ns."""
    if not p.exists():
        return None
    return [(str(x), x.stat().st_mtime_ns) for x in [p, *sorted(p.rglob("*"))]]


def recording(homes, then=subprocess.run):
    """A runner recording each archon run's ARCHON_HOME (and whether it exists
    then) before handing the run to `then`."""

    def run(args, *a, **kw):
        home = Path(kw["env"]["ARCHON_HOME"])
        homes.append((home, home.is_dir()))
        return then(args, *a, **kw)

    return run


def faked_workflow_test(payload):
    """A runner: `workflow test` prints payload; other commands run for real."""
    real = subprocess.run

    def run(args, *a, **kw):
        if list(args[1:3]) == ["workflow", "test"]:
            return subprocess.CompletedProcess(args, 0, stdout=payload, stderr="")
        return real(args, *a, **kw)

    return run


class PackCheckTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="pc-test-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def make(self, yaml=None, fixture=STUB, extra=(), name="tp"):
        pack = self.tmp / name
        shutil.rmtree(pack, True)
        wf = pack / "wf1"
        (wf / "fixtures").mkdir(parents=True)
        (wf / "wf1.yaml").write_text(
            yaml if yaml is not None else GOOD.format(name="wf1")
        )
        if fixture is not None:
            (wf / "fixtures" / "ok.stubs.yaml").write_text(fixture)
        for rel, text in dict(extra).items():
            (pack / rel).parent.mkdir(parents=True, exist_ok=True)
            (pack / rel).write_text(text)
        return pack

    def checks(self, pack):
        return {f.check for f in packcheck.check(pack)}

    def failures(self, pack, check, run=subprocess.run):
        return [
            (f.workflow, f.check, f.message)
            for f in packcheck.check(pack, run=run)
            if f.check == check
        ]

    def test_clean_pack_without_shared_install_or_targets(self):
        pack = self.make()
        self.assertEqual(packcheck.check(pack), [])
        self.assertEqual(packcheck.main([str(pack)]), 0)

    def test_pack_with_shared_dir_passes(self):
        pack = self.make(extra={".shared/helper.py": "x = 1\n"})
        self.assertEqual(packcheck.check(pack), [])

    def test_no_fixture(self):
        got = self.failures(self.make(fixture=None), "no-fixture")
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0][:2], ("tp/wf1", "no-fixture"))
        self.assertTrue(got[0][2].strip())

    def test_failing_fixture(self):
        got = self.failures(self.make(fixture=STUB_BAD), "fixture")
        self.assertTrue(got)
        self.assertIn(got[0][:2], (("tp", "fixture"), ("tp/wf1", "fixture")))
        self.assertTrue(got[0][2].strip())

    def test_fixture_failing_as_expected_passes(self):
        pack = self.make(fixture=STUB_FAILS_AS_EXPECTED)
        self.assertEqual(packcheck.check(pack), [])

    def test_exec_code(self):
        self.assertExecCode(self.make(fixture=STUB + "exec-code: true\n"))

    def assertExecCode(self, pack):
        got = self.failures(pack, "exec-code")
        self.assertTrue(got)
        self.assertEqual(got[0][:2], ("tp/wf1", "exec-code"))
        self.assertTrue(got[0][2].strip())

    def test_exec_code_truthy_spellings(self):
        for case, fx in (
            ("capital", STUB + "exec-code: True\n"),
            (
                "whole-document flow",
                "{exec-code: true, fixture: {expect: completed}}\n",
            ),
        ):
            with self.subTest(case=case):
                self.assertExecCode(self.make(fixture=fx))

    def test_exec_code_pack_never_runs_its_bash(self):
        marker = self.tmp / "bash-ran"
        y = GOOD.format(name="wf1").replace("bash: '", f"bash: 'touch {marker} && ", 1)
        pack = self.make(yaml=y, fixture=STUB + "exec-code: true\n")
        got = self.checks(pack)
        self.assertIn("exec-code", got)
        self.assertFalse(marker.exists())

    def test_tier_and_alias_models(self):
        for model in ("small", "medium", "large", "'@reviewer'"):
            node = (
                GOOD.format(name="wf1")
                + f"  - id: say\n    prompt: hi\n    model: {model}\n    depends_on: [echo]\n"
            )
            wf = f"model: {model}\n" + GOOD.format(name="wf1")
            for level, y in (("node", node), ("workflow", wf)):
                with self.subTest(model=model, level=level):
                    got = self.failures(self.make(yaml=y), "tier-model")
                    self.assertEqual(len(got), 1)
                    self.assertEqual(got[0][:2], ("tp/wf1", "tier-model"))
                    self.assertIn(model.strip("'"), got[0][2])

    def test_list_valued_models(self):
        lst = "['@reviewer', medium]"
        node = (
            GOOD.format(name="wf1")
            + f"  - id: say\n    prompt: hi\n    model: {lst}\n    depends_on: [echo]\n"
        )
        wf = f"model: {lst}\n" + GOOD.format(name="wf1")
        for level, y in (("node", node), ("workflow", wf)):
            with self.subTest(level=level):
                got = self.failures(self.make(yaml=y), "tier-model")
                self.assertTrue(got)
                self.assertTrue(all(g[:2] == ("tp/wf1", "tier-model") for g in got))
                text = "\n".join(m for _, _, m in got)
                self.assertIn("@reviewer", text)
                self.assertIn("medium", text)

    def test_literal_model_with_provider_passes(self):
        y = "provider: claude\nmodel: claude-sonnet-4-5\n" + GOOD.format(name="wf1")
        self.assertEqual(packcheck.check(self.make(yaml=y)), [])

    def test_relative_fence(self):
        y = GOOD.format(name="wf1").replace(
            "    output_format:",
            "    sandbox:\n      enabled: true\n      filesystem:\n"
            "        denyRead: ['zz-one/**']\n        denyWrite:\n"
            "          - /abs-ok\n          - zz-two\n    output_format:",
            1,
        )
        got = self.failures(self.make(yaml=y), "relative-fence")
        self.assertEqual(len(got), 2)
        self.assertTrue(all(w == "tp/wf1" for w, _, _ in got))
        for path in ("zz-one/**", "zz-two"):
            self.assertEqual(sum(path in m for _, _, m in got), 1, path)
        self.assertFalse(any("abs-ok" in m for _, _, m in got))

    def test_relative_fence_workflow_level_and_flow_style(self):
        good = GOOD.format(name="wf1")
        cases = {
            "workflow-block": "sandbox:\n  filesystem:\n    denyRead: ['zz-wb/**']\n"
            + good,
            "workflow-flow": "sandbox: {filesystem: {denyRead: ['zz-wf/**']}}\n" + good,
            "node-flow": good.replace(
                "    output_format:",
                "    sandbox: {filesystem: {allowWrite: [zz-nf]}}\n    output_format:",
                1,
            ),
        }
        wants = {
            "workflow-block": "zz-wb/**",
            "workflow-flow": "zz-wf/**",
            "node-flow": "zz-nf",
        }
        for case, y in cases.items():
            with self.subTest(case=case):
                got = self.failures(self.make(yaml=y), "relative-fence")
                self.assertEqual(len(got), 1)
                self.assertIn(wants[case], got[0][2])

    def test_absolute_fence_ok(self):
        y = GOOD.format(name="wf1").replace(
            "    output_format:",
            "    sandbox:\n      enabled: true\n      filesystem:\n        denyRead: ['/srv/x']\n    output_format:",
            1,
        )
        self.assertNotIn("relative-fence", self.checks(self.make(yaml=y)))

    def test_validate_failure(self):
        y = (
            GOOD.format(name="wf1")
            + "  - id: bad\n    prompt: hi\n    depends_on: [nope]\n    provider: claude\n    model: claude-sonnet-4-5\n"
        )
        got = self.failures(self.make(yaml=y), "validate")
        self.assertTrue(any(w == "tp/wf1" and "nope" in m for w, _, m in got), got)

    def test_validate_warning_for_misspelled_key(self):
        y = GOOD.format(name="wf1").replace(
            "    output_format:",
            "    sandox:\n      enabled: true\n    output_format:",
            1,
        )
        got = self.failures(self.make(yaml=y), "validate")
        self.assertTrue(any(w == "tp/wf1" and "sandox" in m for w, _, m in got), got)

    def test_pack_level_yaml_scanned_and_attributed(self):
        y = GOOD.format(name="top").replace(
            "    output_format:",
            "    sandbox:\n      filesystem:\n        denyRead: [zz-top]\n    output_format:",
            1,
        )
        pack = self.make(extra={"top.yaml": y})
        got = self.failures(pack, "relative-fence")
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0][:2], ("tp/top", "relative-fence"))
        self.assertIn("zz-top", got[0][2])

    def test_workflow_test_failed_count_is_fixture_failure(self):
        payload = '{"ok": true, "failed": 1, "results": []}'
        got = self.failures(self.make(), "fixture", faked_workflow_test(payload))
        self.assertTrue(got)
        self.assertIn(got[0][:2], (("tp", "fixture"), ("tp/wf1", "fixture")))
        self.assertTrue(got[0][2].strip())

    def test_workflow_test_without_results_is_fixture_failure(self):
        payload = '{"ok": true, "failed": 0}'
        got = self.failures(self.make(), "fixture", faked_workflow_test(payload))
        self.assertTrue(got)
        self.assertIn(got[0][:2], (("tp", "fixture"), ("tp/wf1", "fixture")))
        self.assertTrue(got[0][2].strip())

    def test_workflow_test_with_no_fixtures_found_is_fixture_failure(self):
        payload = '{"results": [], "passed": 0, "failed": 0, "errors": []}'
        got = self.failures(self.make(), "fixture", faked_workflow_test(payload))
        self.assertTrue(got)
        self.assertIn(got[0][:2], (("tp", "fixture"), ("tp/wf1", "fixture")))
        self.assertTrue(any("ok.stubs.yaml" in m for _, _, m in got), got)

    def run_main(self, *packs):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = packcheck.main([str(p) for p in packs])
        return rc, out.getvalue()

    def assertNoFixtureLine(self, out):
        shaped = [
            line
            for line in out.splitlines()
            if re.match(r"^[^\s:/]+(/[^\s:]+)?: [a-z-]+: \S", line)
        ]
        self.assertEqual(len(shaped), 1, out)
        self.assertTrue(shaped[0].startswith("tp/wf1: no-fixture: "))
        self.assertTrue(shaped[0][len("tp/wf1: no-fixture: ") :].strip())

    def test_main_exit_1_and_line_format(self):
        rc, out = self.run_main(self.make(fixture=None))
        self.assertEqual(rc, 1)
        self.assertNoFixtureLine(out)

    def test_main_clean_and_failing_packs(self):
        good = self.make(name="good")
        bad = self.make(name="tp", fixture=None)
        rc, out = self.run_main(good, bad)
        self.assertEqual(rc, 1)
        self.assertNoFixtureLine(out)

    def test_home_untouched(self):
        home = Path.home() / ".archon"
        before = snapshot(home)
        packcheck.check(self.make())
        self.assertEqual(snapshot(home), before)

    def assert_tmp_gone(self, homes):
        self.assertTrue(homes)
        for home, existed in homes:
            self.assertTrue(existed, home)
            self.assertFalse(home.parent.exists(), home.parent)

    def test_tmp_removed_on_every_exit(self):
        clean = self.make(name="clean")
        failing = self.make(name="tp", fixture=STUB_BAD)
        for case, pack in (("clean", clean), ("failing", failing)):
            with self.subTest(case=case):
                homes = []
                packcheck.check(pack, run=recording(homes))
                self.assert_tmp_gone(homes)

        def boom(args, *a, **kw):
            raise RuntimeError("boom")

        homes = []
        try:
            result = packcheck.check(clean, run=recording(homes, then=boom))
        except RuntimeError:
            pass
        else:
            self.assertTrue(result)
        self.assert_tmp_gone(homes)


if __name__ == "__main__":
    unittest.main()
