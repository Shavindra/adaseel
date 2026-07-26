import tempfile
import unittest
from pathlib import Path
from unittest import mock

from typer.testing import CliRunner

from medlens.cli import app


class CliDiagnosticsTests(unittest.TestCase):
    def setUp(self):
        self.runner = CliRunner()

    def test_verbose_shows_safe_resolved_configuration(self):
        fake_result = {
            "degraded": False,
            "ok": True,
            "run_dir": "runs/test",
            "status": "completed_to_flagging",
        }
        with tempfile.TemporaryDirectory() as directory, mock.patch.dict(
            "os.environ",
            {},
            clear=True,
        ), mock.patch("medlens.cli.run_review", return_value=fake_result) as run, mock.patch(
            "medlens.feedback._console",
            None,
        ), mock.patch(
            "medlens.cli._setup_logging",
        ):
            source = Path(directory) / "report.txt"
            source.write_text("Report type: Example", encoding="utf-8")
            result = self.runner.invoke(
                app,
                [
                    "review",
                    "--input",
                    str(source),
                    "--provider",
                    "openrouter",
                    "--model",
                    "qwen",
                    "--api-key",
                    "test-secret-key-material",
                    "--no-pick",
                    "--verbose",
                    "--retries",
                    "1",
                    "--connect-timeout",
                    "3",
                    "--read-timeout",
                    "17",
                ],
            )

        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("api_key=present", result.output)
        self.assertIn("endpoint=https://openrouter.ai/api/v1", result.output)
        self.assertIn("connect_timeout=3s", result.output)
        self.assertIn("read_timeout=17s", result.output)
        self.assertIn(
            '"api_key_source": "global:explicit_argument"',
            result.output,
        )
        self.assertNotIn("test-secret-key-material", result.output)
        runtime = run.call_args.args[0]["agents"]["report_classification"]
        self.assertEqual(runtime["api_key"], "test-secret-key-material")
        self.assertEqual(runtime["retries"], 1)

    def test_degraded_run_returns_distinct_exit_code(self):
        fake_result = {
            "degraded": True,
            "degraded_roles": ["result_validation"],
            "ok": True,
            "run_dir": "runs/test",
            "status": "completed_to_flagging_degraded",
        }
        with tempfile.TemporaryDirectory() as directory, mock.patch.dict(
            "os.environ",
            {},
            clear=True,
        ), mock.patch("medlens.cli.run_review", return_value=fake_result), mock.patch(
            "medlens.feedback._console",
            None,
        ), mock.patch(
            "medlens.cli._setup_logging",
        ):
            source = Path(directory) / "report.txt"
            source.write_text("Report type: Example", encoding="utf-8")
            result = self.runner.invoke(
                app,
                [
                    "review",
                    "--input",
                    str(source),
                    "--provider",
                    "ollama",
                    "--model",
                    "qwen",
                    "--no-pick",
                    "--quiet",
                ],
            )

        self.assertEqual(result.exit_code, 2)
        self.assertIn('"degraded": true', result.output)

    def test_review_help_describes_verbose_and_readable_log(self):
        result = self.runner.invoke(app, ["review", "--help"])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("--verbose", result.output)
        self.assertIn("configuration/key", result.output)
        self.assertIn("provenance", result.output)
        self.assertIn("run.log", result.output)
        self.assertIn("events.jsonl", result.output)


if __name__ == "__main__":
    unittest.main()
