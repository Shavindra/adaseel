import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from medlens import config, feedback
from medlens.agent import run_review
from medlens.fake import make_fake_completer


REPORT = """Report type: Chemistry panel
| Test | Result | Unit | Reference Range | Flag |
| --- | --- | --- | --- | --- |
| Marker A | 9.8 | mmol/L | 2.0-8.0 | |
| Marker B | 4.0 | mmol/L | 3.0-5.0 | |
"""


class AgentFlowTests(unittest.TestCase):
    def setUp(self):
        feedback.configure(quiet=True)

    def tearDown(self):
        feedback.configure(quiet=False)

    def _write_report(
        self,
        directory: str,
        name: str = "report.txt",
        content: str = REPORT,
    ) -> Path:
        path = Path(directory) / name
        path.write_text(content, encoding="utf-8")
        return path

    def _cfg(self) -> dict:
        return {"agents": config.resolve_agent_runtimes(fake=True)}

    def _run(self, source: Path, directory: str, **kwargs):
        return run_review(
            self._cfg(),
            str(source),
            runs_dir=str(Path(directory) / "runs"),
            structured_completer=make_fake_completer(),
            **kwargs,
        )

    def test_all_roles_emit_typed_outputs_and_five_handoffs(self):
        with tempfile.TemporaryDirectory() as directory, mock.patch.dict(
            os.environ,
            {"DEBUG": "false"},
            clear=False,
        ):
            source = self._write_report(directory)
            result = self._run(source, directory, run_id="full-run")
            manifest = json.loads(Path(result["artifacts"]["manifest"]).read_text())
            outputs = json.loads(Path(result["artifacts"]["agent_outputs"]).read_text())
            invocations = json.loads(
                Path(result["artifacts"]["agent_invocations"]).read_text()
            )
            handoffs = json.loads(Path(result["artifacts"]["handoffs"]).read_text())
            trace_text = Path(result["artifacts"]["trace"]).read_text()
            log_text = Path(result["artifacts"]["log"]).read_text()
            report_text = Path(result["artifacts"]["report"]).read_text()

        self.assertTrue(result["ok"])
        self.assertEqual(manifest["model_usage"], "bounded_multi_agent")
        self.assertEqual(
            list(manifest["agents"]["role_status"]),
            [
                "report_classification",
                "result_extraction",
                "result_flagging",
                "result_validation",
            ],
        )
        self.assertTrue(all(manifest["agents"]["role_status"].values()))
        self.assertEqual(len(invocations["invocations"]), 4)
        self.assertEqual(
            invocations["invocations"][0]["output_contract"],
            "ReportClassificationOutput/v1",
        )
        self.assertEqual(
            invocations["invocations"][3]["output_name"],
            "submit_flagging_assessment",
        )
        self.assertEqual(
            [item["role"] for item in invocations["invocations"]],
            [
                "report_classification",
                "result_extraction",
                "result_validation",
                "result_flagging",
            ],
        )
        self.assertEqual(len(handoffs["handoffs"]), 5)
        self.assertEqual(
            handoffs["handoffs"][-1]["to_role"],
            "deterministic_acceptance",
        )
        self.assertIn("decision", outputs["outputs"]["report_classification"]["output"])
        self.assertIn("results", outputs["outputs"]["result_extraction"]["output"])
        self.assertIn("reviews", outputs["outputs"]["result_validation"]["output"])
        self.assertIn("assessments", outputs["outputs"]["result_flagging"]["output"])
        self.assertEqual(trace_text.count('"action":"agent_invocation_started"'), 4)
        self.assertNotIn(str(source), trace_text)
        self.assertNotIn("9.8", trace_text)
        self.assertIn("## Multi-agent execution", report_text)
        self.assertIn("report_classification/v1", report_text)
        self.assertIn("Structured hand-offs recorded: 5", report_text)
        self.assertIn("run.run_started — started", log_text)
        self.assertIn("report_classification.agent_invocation_started", log_text)
        self.assertIn("configuration.agent_runtime_resolved", log_text)
        self.assertTrue(
            any(item["kind"] == "human_run_log" for item in manifest["artifacts"])
        )
        self.assertIn(
            "api_key_status",
            manifest["agents"]["runtimes"]["report_classification"],
        )

    def test_debug_trace_contains_full_agent_and_tool_io_and_redacts_secrets(self):
        with tempfile.TemporaryDirectory() as directory, mock.patch.dict(
            os.environ,
            {"DEBUG": "true"},
            clear=False,
        ):
            source = self._write_report(directory)
            cfg = self._cfg()
            cfg["agents"]["report_classification"][
                "api_key"
            ] = "sk-or-v1-secretsecretsecret"
            result = run_review(
                cfg,
                str(source),
                runs_dir=str(Path(directory) / "runs"),
                run_id="debug-run",
                structured_completer=make_fake_completer(),
            )
            trace_text = Path(result["artifacts"]["trace"]).read_text()
            log_text = Path(result["artifacts"]["log"]).read_text()
            manifest = json.loads(Path(result["artifacts"]["manifest"]).read_text())

        self.assertIn(str(source), trace_text)
        self.assertIn("Report type: Chemistry panel", trace_text)
        self.assertIn("9.8", trace_text)
        self.assertIn("submit_report_classification", trace_text)
        self.assertNotIn("sk-or-v1-secretsecretsecret", trace_text)
        self.assertIn("[REDACTED_SECRET]", trace_text)
        self.assertNotIn("sk-or-v1-secretsecretsecret", log_text)
        self.assertIn("[REDACTED_SECRET]", log_text)
        self.assertTrue(manifest["debug"]["enabled"])
        self.assertFalse(manifest["debug"]["hidden_reasoning_content_logged"])

    def test_each_role_can_use_a_different_model(self):
        with tempfile.TemporaryDirectory() as directory:
            source = self._write_report(directory)
            cfg = self._cfg()
            for index, (role, runtime) in enumerate(cfg["agents"].items(), 1):
                runtime["model"] = "role-model-%d" % index
                runtime["provider"] = "role-provider-%d" % index
            result = run_review(
                cfg,
                str(source),
                runs_dir=str(Path(directory) / "runs"),
                run_id="role-models",
                write_report=False,
                structured_completer=make_fake_completer(),
            )
            manifest = json.loads(Path(result["artifacts"]["manifest"]).read_text())

        self.assertEqual(
            {item["model"] for item in manifest["agents"]["runtimes"].values()},
            {"role-model-1", "role-model-2", "role-model-3", "role-model-4"},
        )
        self.assertIsNone(result["artifacts"]["report"])

    def test_agent_failure_degrades_but_deterministic_results_remain(self):
        base = make_fake_completer()

        def completer(runtime, messages, schema, output_name):
            if output_name == "submit_result_validation":
                return {"error": "synthetic timeout", "ok": False, "raw": None}
            return base(runtime, messages, schema, output_name)

        with tempfile.TemporaryDirectory() as directory:
            source = self._write_report(directory)
            result = run_review(
                self._cfg(),
                str(source),
                runs_dir=str(Path(directory) / "runs"),
                run_id="degraded-run",
                write_report=False,
                structured_completer=completer,
            )
            manifest = json.loads(Path(result["artifacts"]["manifest"]).read_text())
            flagged = json.loads(Path(result["artifacts"]["flagged_results"]).read_text())

        self.assertTrue(result["ok"])
        self.assertTrue(result["degraded"])
        self.assertEqual(result["status"], "completed_to_flagging_degraded")
        self.assertFalse(manifest["agents"]["role_status"]["result_validation"])
        self.assertEqual(flagged["results"][0]["flag"], "high")
        self.assertTrue(
            any("validation agent" in item for item in manifest["limitations"])
        )

    def test_complete_agent_failure_still_produces_deterministic_bundle(self):
        def failed_completer(runtime, messages, schema, output_name):
            return {
                "error": "synthetic provider unavailable",
                "ok": False,
                "raw": None,
            }

        with tempfile.TemporaryDirectory() as directory:
            source = self._write_report(directory)
            result = run_review(
                self._cfg(),
                str(source),
                runs_dir=str(Path(directory) / "runs"),
                run_id="all-agents-failed",
                write_report=False,
                structured_completer=failed_completer,
            )
            manifest = json.loads(Path(result["artifacts"]["manifest"]).read_text())
            flagged = json.loads(Path(result["artifacts"]["flagged_results"]).read_text())
            handoffs = json.loads(Path(result["artifacts"]["handoffs"]).read_text())

        self.assertTrue(result["ok"])
        self.assertTrue(result["degraded"])
        self.assertFalse(any(manifest["agents"]["role_status"].values()))
        self.assertEqual(flagged["results"][0]["flag"], "high")
        self.assertEqual(len(handoffs["handoffs"]), 5)
        self.assertTrue(
            any(item["status"] == "degraded" for item in handoffs["handoffs"])
        )

    def test_typed_network_timeout_is_readable_and_does_not_crash_pipeline(self):
        base = make_fake_completer()

        def completer(runtime, messages, schema, output_name):
            if output_name == "submit_result_validation":
                return {
                    "error": "Connection timed out.",
                    "error_code": "network_connect_timeout",
                    "error_detail": {
                        "attempts": 3,
                        "code": "network_connect_timeout",
                        "endpoint": {
                            "host": "api.example.invalid",
                            "port": 443,
                            "scheme": "https",
                        },
                        "hint": "Check DNS, internet access, firewall, VPN, or proxy.",
                        "message": "Connection to api.example.invalid:443 timed out.",
                        "retryable": True,
                    },
                    "ok": False,
                    "raw": None,
                }
            return base(runtime, messages, schema, output_name)

        with tempfile.TemporaryDirectory() as directory:
            source = self._write_report(directory)
            result = run_review(
                self._cfg(),
                str(source),
                runs_dir=str(Path(directory) / "runs"),
                run_id="network-timeout",
                write_report=False,
                structured_completer=completer,
            )
            readable = Path(result["artifacts"]["log"]).read_text()
            invocations = json.loads(
                Path(result["artifacts"]["agent_invocations"]).read_text()
            )

        self.assertTrue(result["ok"])
        self.assertTrue(result["degraded"])
        self.assertIn("network_connect_timeout", readable)
        self.assertIn("api.example.invalid", readable)
        self.assertIn("firewall", readable)
        validation = [
            item
            for item in invocations["invocations"]
            if item["role"] == "result_validation"
        ][0]
        self.assertEqual(validation["status"], "transport_error")
        self.assertEqual(
            validation["validation_codes"],
            ["network_connect_timeout"],
        )

    def test_missing_hosted_key_is_preflighted_without_provider_call(self):
        with tempfile.TemporaryDirectory() as directory, mock.patch.dict(
            os.environ,
            {},
            clear=True,
        ):
            source = self._write_report(directory)
            cfg = {
                "agents": config.resolve_agent_runtimes(
                    provider="openrouter",
                    model="qwen",
                )
            }
            completer = mock.Mock(
                side_effect=AssertionError("provider must not be called")
            )
            result = run_review(
                cfg,
                str(source),
                runs_dir=str(Path(directory) / "runs"),
                run_id="missing-key",
                write_report=False,
                structured_completer=completer,
            )
            readable = Path(result["artifacts"]["log"]).read_text()
            invocations = json.loads(
                Path(result["artifacts"]["agent_invocations"]).read_text()
            )

        completer.assert_not_called()
        self.assertTrue(result["degraded"])
        self.assertEqual(
            {item["status"] for item in invocations["invocations"]},
            {"config_error"},
        )
        self.assertIn("agent_api_key_missing", readable)
        self.assertIn("none was found", readable)
        self.assertIn("OPENROUTER_API_KEY", readable)

    def test_agent_flag_mismatch_is_rejected_by_deterministic_reconciliation(self):
        base = make_fake_completer()

        def completer(runtime, messages, schema, output_name):
            result = base(runtime, messages, schema, output_name)
            if output_name == "submit_flagging_assessment" and result.get("ok"):
                result["value"]["assessments"][0]["flag"] = "normal"
            return result

        with tempfile.TemporaryDirectory() as directory:
            source = self._write_report(directory)
            result = run_review(
                self._cfg(),
                str(source),
                runs_dir=str(Path(directory) / "runs"),
                run_id="mismatch-run",
                write_report=False,
                structured_completer=completer,
            )
            flagged = json.loads(Path(result["artifacts"]["flagged_results"]).read_text())

        self.assertEqual(flagged["results"][0]["flag"], "high")
        self.assertEqual(flagged["summary"]["agent_mismatch_count"], 1)
        self.assertEqual(
            flagged["agent_reconciliation"][0]["status"],
            "rejected_category_mismatch",
        )

    def test_agent_can_classify_arbitrary_non_blood_report(self):
        content = """# Specialised saliva hormone assay
| Test | Result | Unit | Reference Range |
| --- | --- | --- | --- |
| Salivary marker | 2.1 | ng/mL | 1.0-3.0 |
"""
        with tempfile.TemporaryDirectory() as directory:
            source = self._write_report(directory, content=content)
            result = self._run(
                source,
                directory,
                run_id="saliva-run",
                write_report=False,
            )

        self.assertEqual(
            result["report_context"]["label"],
            "Specialised saliva hormone assay",
        )
        self.assertEqual(result["report_context"]["source"], "agent")

    def test_user_report_type_remains_authoritative(self):
        with tempfile.TemporaryDirectory() as directory:
            source = self._write_report(directory)
            result = self._run(
                source,
                directory,
                report_type="User-defined environmental assay",
                run_id="typed-run",
                write_report=False,
            )

        self.assertEqual(
            result["report_context"]["label"],
            "User-defined environmental assay",
        )
        self.assertEqual(result["report_context"]["source"], "user")

    def test_explicit_transcript_supports_image_without_ocr(self):
        with tempfile.TemporaryDirectory() as directory:
            image = Path(directory) / "scan.png"
            image.write_bytes(b"not a real image; OCR must not be called")
            transcript = self._write_report(directory, "transcript.txt")
            with mock.patch(
                "medlens.labtools._docling_to_text",
                side_effect=AssertionError("OCR should not run"),
            ):
                result = run_review(
                    self._cfg(),
                    str(image),
                    transcript_path=str(transcript),
                    runs_dir=str(Path(directory) / "runs"),
                    run_id="transcript-run",
                    write_report=False,
                    structured_completer=make_fake_completer(),
                )
            extracted = json.loads(
                Path(result["artifacts"]["extracted_results"]).read_text()
            )

        self.assertTrue(result["ok"])
        self.assertEqual(extracted["engine"], "user-supplied-transcript")

    def test_unrelated_image_never_uses_bundled_sample_transcript(self):
        with tempfile.TemporaryDirectory() as directory:
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
                    self._cfg(),
                    str(image),
                    runs_dir=str(Path(directory) / "runs"),
                    run_id="failed-run",
                    structured_completer=make_fake_completer(),
                )
            manifest = json.loads(Path(result["manifest_path"]).read_text())
            trace = Path(result["trace_path"]).read_text()

        self.assertFalse(result["ok"])
        self.assertEqual(manifest["failure"]["stage"], "canonical_extraction")
        self.assertEqual(manifest["agent_invocation_count"], 0)
        self.assertNotIn("Haemoglobin", trace)

    def test_existing_run_directory_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            source = self._write_report(directory)
            first = self._run(source, directory, run_id="same", write_report=False)
            second = self._run(source, directory, run_id="same", write_report=False)

        self.assertTrue(first["ok"])
        self.assertFalse(second["ok"])
        self.assertEqual(second["error_code"], "run_directory_exists")


if __name__ == "__main__":
    unittest.main()
