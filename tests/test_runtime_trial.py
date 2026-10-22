"""Disposable trial artifact checks; telemetry comparison remains a separate gate."""
from pathlib import Path
import json
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from check_runtime_trial import inspect_trial


class RuntimeTrialTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.trial = Path(self.temporary.name) / "trial"
        self.trial.mkdir()
        self.result = self.trial / "result.json"
        self.result.write_text(json.dumps({"exit": 0}), encoding="utf-8")
        for name in ("game.log", "r1.log"):
            (self.trial / name).write_text("normal diagnostic output\n", encoding="utf-8")

    def verdict(self, expected):
        report = inspect_trial(self.trial)
        self.assertEqual(report["status"], expected, report)
        self.assertIsInstance(report["errors"], list)
        if expected == "failed":
            self.assertTrue(report["errors"], report)
        else:
            self.assertEqual(report["errors"], [])
        return report

    def test_clean_artifacts_without_trace_pass_this_gate(self):
        self.assertFalse((self.trial / "fight.txt").exists())
        self.verdict("passed")

    def test_zero_exit_fatal_in_either_log(self):
        diagnostics = (
            "r1: HOLD FATAL: resume ownership was lost",
            "r1: fatal: copy-worker completion wait failed",
            "r1: RING RESTORE FATAL: commit failed",
            "FATAL EXCEPTION: access violation",
            "r1: hold fatal: watchdog release",
            "HOLD RELEASE FAILED: resume thread failed",
            "Unhandled exception: access violation",
        )
        for name in ("game.log", "r1.log"):
            for diagnostic in diagnostics:
                with self.subTest(log=name, diagnostic=diagnostic):
                    path = self.trial / name
                    path.write_text("normal start\n" + diagnostic + "\n", encoding="utf-8")
                    self.verdict("failed")
                    path.write_text("normal diagnostic output\n", encoding="utf-8")

    def test_late_fatal_after_apparent_success_is_failure(self):
        (self.trial / "r1.log").write_text(
            "capture complete\nrestore observers PASS\n" + "progress\n" * 4096 +
            "r1: HOLD FATAL: failed to resume thread\n", encoding="utf-8")
        self.verdict("failed")

    def test_hold_refused_is_not_fatal(self):
        for name in ("game.log", "r1.log"):
            (self.trial / name).write_text(
                "r1: HOLD REFUSED: thread was busy\nr1: capture refused: resource unavailable\nnonfatal diagnostic\n",
                encoding="utf-8")
        self.verdict("passed")

    def test_nonzero_exit(self):
        for code in (1, -1, 3221225477):
            with self.subTest(exit=code):
                self.result.write_text(json.dumps({"exit": code}), encoding="utf-8")
                self.verdict("failed")

    def test_missing_artifacts(self):
        for name in ("result.json", "game.log", "r1.log"):
            with self.subTest(artifact=name):
                path = self.trial / name
                original = path.read_bytes()
                path.unlink()
                self.verdict("failed")
                path.write_bytes(original)

    def test_empty_artifacts(self):
        for name in ("result.json", "game.log", "r1.log"):
            with self.subTest(artifact=name):
                path = self.trial / name
                original = path.read_bytes()
                path.write_bytes(b"")
                self.verdict("failed")
                path.write_bytes(original)

    def test_whitespace_and_invalid_utf8_logs(self):
        for name in ("game.log", "r1.log"):
            for contents in (b" \r\n\t", b"normal\n\xff\xfe"):
                with self.subTest(artifact=name, contents=contents):
                    path = self.trial / name
                    original = path.read_bytes()
                    path.write_bytes(contents)
                    self.verdict("failed")
                    path.write_bytes(original)

    def test_result_utf8_bom(self):
        self.result.write_text(json.dumps({"exit": 0}), encoding="utf-8-sig")
        self.verdict("passed")

    def test_invalid_result(self):
        for contents in ("{bad json", "[]", "null", '"result"', "{}", '{"exit": null}',
                         '{"exit": "0"}', '{"exit": false}', '{"exit": 0.0}'):
            with self.subTest(contents=contents):
                self.result.write_text(contents, encoding="utf-8")
                self.verdict("failed")

    def test_missing_trial_directory(self):
        report = inspect_trial(self.trial / "missing")
        self.assertEqual(report["status"], "failed", report)
        self.assertTrue(report["errors"])

    def test_cli_exit_and_machine_readable_report(self):
        output = Path(self.temporary.name) / "report.json"
        for fatal in (False, True):
            with self.subTest(fatal=fatal):
                if fatal:
                    (self.trial / "r1.log").write_text("r1: HOLD FATAL: failure\n", encoding="utf-8")
                result = subprocess.run(
                    [sys.executable, str(ROOT / "tools/check_runtime_trial.py"),
                     str(self.trial), "--output", str(output)],
                    capture_output=True, text=True, timeout=15)
                self.assertEqual(result.returncode, 1 if fatal else 0, result.stdout + result.stderr)
                report = json.loads(output.read_text(encoding="utf-8"))
                self.assertEqual(report["status"], "failed" if fatal else "passed", report)
                self.assertEqual(bool(report["errors"]), fatal)

    def test_cli_without_output(self):
        result = subprocess.run(
            [sys.executable, str(ROOT / "tools/check_runtime_trial.py"), str(self.trial)],
            capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
