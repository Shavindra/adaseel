import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from medlens.agent import run_review


REPORT = """Report type: Chemistry panel
| Test | Result | Unit | Reference Range | Flag |
| --- | --- | --- | --- | --- |
| Marker A | 9.8 | mmol/L | 2.0-8.0 | |
| Marker B | 4.0 | mmol/L | 3.0-5.0 | |
"""


class AgentFlowTests(unittest.TestCase):
    def _write_report(self, directory: str, name: str = "report.txt") -> Path:
        path = Path(directory) / name
        path.write_text(REPORT, encoding="utf-8")
        return path

    def test_completed_run_writes_required_bundle_and_detailed_trace(self):
        with tempfile.TemporaryDirectory() as directory, mock.patch.dict(
            os.environ, {"DEBUG": "false"}, clear=False
        ):
            source = self._write_report(directory)
            result = run_review(
                {},
                str(source),
                runs_dir=str(Path(directory) / "runs"),
                run_id="normal-run",
            )
            self.assertTrue(result["ok"])
            for path in result["artifacts"].values():
                if path:
                    self.assertTrue(Path(path).is_file(), path)
            manifest = json.loads(Path(result["artifacts"]["manifest"]).read_text())
            trace_text = Path(result["artifacts"]["trace"]).read_text()
            events = [json.loads(line) for line in trace_text.splitlines()]

        self.assertEqual(manifest["status"], "completed_to_flagging")
        self.assertEqual(manifest["model_usage"], "none")
        self.assertEqual(manifest["report_context"]["label"], "Chemistry panel")
        self.assertIn("extract", manifest["completed_stages"])
        self.assertIn("flag", manifest["completed_stages"])
        self.assertEqual(
            len([event for event in events if event["action"] == "result_assessed"]),
            2,
        )
        assessment = next(event for event in events if event["action"] == "result_assessed")
        self.assertIn("rationale", assessment["details"])
        self.assertIn("alternatives_considered", assessment["details"])
        self.assertIn("assumptions", assessment["details"])
        self.assertIn("uncertainties", assessment["details"])
        self.assertIn("stage_started", [event["action"] for event in events])
        self.assertIn("stage_completed", [event["action"] for event in events])
        self.assertNotIn(str(source), trace_text)
        self.assertNotIn("9.8", trace_text)
        self.assertNotIn("Report type: Chemistry panel", trace_text)

    def test_debug_trace_contains_full_observable_io_and_redacts_secrets(self):
        with tempfile.TemporaryDirectory() as directory, mock.patch.dict(
            os.environ, {"DEBUG": "true"}, clear=False
        ):
            source = self._write_report(directory)
            result = run_review(
                {"api_key": "sk-or-v1-secretsecretsecret"},
                str(source),
                runs_dir=str(Path(directory) / "runs"),
                run_id="debug-run",
            )
            trace_text = Path(result["artifacts"]["trace"]).read_text()
            manifest = json.loads(Path(result["artifacts"]["manifest"]).read_text())
            report_text = Path(result["artifacts"]["report"]).read_text()

        self.assertIn(str(source), trace_text)
        self.assertIn("Report type: Chemistry panel", trace_text)
        self.assertIn("9.8", trace_text)
        self.assertNotIn("sk-or-v1-secretsecretsecret", trace_text)
        self.assertIn("[REDACTED_SECRET]", trace_text)
        self.assertTrue(manifest["debug"]["enabled"])
        self.assertFalse(manifest["debug"]["hidden_reasoning_content_logged"])
        self.assertIn("DEBUG=true trace includes full observable", report_text)

    def test_explicit_transcript_supports_image_without_ocr(self):
        with tempfile.TemporaryDirectory() as directory, mock.patch.dict(
            os.environ, {"DEBUG": "false"}, clear=False
        ):
            image = Path(directory) / "scan.png"
            image.write_bytes(b"not a real image; OCR must not be called")
            transcript = self._write_report(directory, "transcript.txt")
            with mock.patch(
                "medlens.labtools._docling_to_text",
                side_effect=AssertionError("OCR should not run"),
            ):
                result = run_review(
                    {},
                    str(image),
                    transcript_path=str(transcript),
                    runs_dir=str(Path(directory) / "runs"),
                    run_id="transcript-run",
                    write_report=False,
                )
            extracted = json.loads(Path(result["artifacts"]["extracted_results"]).read_text())

        self.assertTrue(result["ok"])
        self.assertEqual(extracted["engine"], "user-supplied-transcript")
        self.assertIsNone(result["artifacts"]["report"])

    def test_unrelated_image_never_uses_bundled_sample_transcript(self):
        with tempfile.TemporaryDirectory() as directory, mock.patch.dict(
            os.environ, {"DEBUG": "false"}, clear=False
        ):
            image = Path(directory) / "unrelated.png"
            image.write_bytes(b"not an image")
            with mock.patch(
                "medlens.labtools._docling_to_text",
                side_effect=RuntimeError("docling unavailable"),
            ), mock.patch(
                "medlens.labtools._surya_to_text",
                side_effect=RuntimeError("surya unavailable"),
            ):
                result = run_review(
                    {},
                    str(image),
                    runs_dir=str(Path(directory) / "runs"),
                    run_id="failed-run",
                )
            manifest = json.loads(Path(result["manifest_path"]).read_text())
            trace = Path(result["trace_path"]).read_text()

        self.assertFalse(result["ok"])
        self.assertEqual(manifest["status"], "failed")
        self.assertEqual(manifest["failure"]["stage"], "extract")
        self.assertNotIn("Haemoglobin", trace)

    def test_debug_failure_trace_includes_exception_stack(self):
        with tempfile.TemporaryDirectory() as directory, mock.patch.dict(
            os.environ, {"DEBUG": "true"}, clear=False
        ):
            image = Path(directory) / "failed-scan.png"
            image.write_bytes(b"not an image")
            with mock.patch(
                "medlens.labtools._docling_to_text",
                side_effect=RuntimeError("docling diagnostic"),
            ), mock.patch(
                "medlens.labtools._surya_to_text",
                side_effect=RuntimeError("surya diagnostic"),
            ):
                result = run_review(
                    {},
                    str(image),
                    runs_dir=str(Path(directory) / "runs"),
                    run_id="debug-failed-run",
                )
            trace = Path(result["trace_path"]).read_text()

        self.assertFalse(result["ok"])
        self.assertIn("exception_traceback", trace)
        self.assertIn("RuntimeError: docling diagnostic", trace)
        self.assertIn("RuntimeError: surya diagnostic", trace)

    def test_user_report_type_overrides_document_label(self):
        with tempfile.TemporaryDirectory() as directory, mock.patch.dict(
            os.environ, {"DEBUG": "false"}, clear=False
        ):
            source = self._write_report(directory)
            result = run_review(
                {},
                str(source),
                report_type="User-defined assay",
                runs_dir=str(Path(directory) / "runs"),
                run_id="typed-run",
                write_report=False,
            )
        self.assertEqual(result["report_context"]["label"], "User-defined assay")
        self.assertEqual(result["report_context"]["source"], "user")

    def test_existing_run_directory_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as directory, mock.patch.dict(
            os.environ, {"DEBUG": "false"}, clear=False
        ):
            source = self._write_report(directory)
            runs = Path(directory) / "runs"
            first = run_review({}, str(source), runs_dir=str(runs), run_id="same")
            second = run_review({}, str(source), runs_dir=str(runs), run_id="same")
        self.assertTrue(first["ok"])
        self.assertFalse(second["ok"])
        self.assertEqual(second["error_code"], "run_directory_exists")


if __name__ == "__main__":
    unittest.main()
