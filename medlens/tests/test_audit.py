import datetime as dt
import json
import os
import tempfile
import unittest
from pathlib import Path

from medlens.audit import (
    TraceWriter,
    debug_enabled,
    redact_for_log,
    validate_run_id,
)


class AuditTests(unittest.TestCase):
    def test_debug_environment_switch(self):
        self.assertTrue(debug_enabled({"DEBUG": "true"}))
        self.assertTrue(debug_enabled({"DEBUG": "1"}))
        self.assertFalse(debug_enabled({"DEBUG": "false"}))

    def test_run_id_rejects_traversal(self):
        with self.assertRaises(ValueError):
            validate_run_id("../outside")
        self.assertEqual(validate_run_id("run-2026.07_23"), "run-2026.07_23")

    def test_recursive_secret_redaction_and_reasoning_omission(self):
        value = redact_for_log(
            {
                "api_key": "sk-or-v1-abcdefghijklmnop",
                "nested": {"authorization": "Bearer abcdefghijkl"},
                "access_token": "github_pat_abcdefghijklmnopqrstuvwxyz123456",
                "signing_private_key": (
                    "-----BEGIN PRIVATE KEY-----\nsecret-material\n"
                    "-----END PRIVATE KEY-----"
                ),
                "reasoning": "private hidden reasoning",
                "rationale": "Explicit bounded rationale",
            }
        )
        rendered = json.dumps(value)
        self.assertNotIn("abcdefghijklmnop", rendered)
        self.assertNotIn("private hidden reasoning", rendered)
        self.assertNotIn("github_pat_", rendered)
        self.assertNotIn("secret-material", rendered)
        self.assertIn("[REDACTED_SECRET]", rendered)
        self.assertIn("content_omitted", rendered)
        self.assertEqual(value["rationale"], "Explicit bounded rationale")

    def test_normal_trace_rejects_source_payload_key(self):
        with tempfile.TemporaryDirectory() as directory:
            trace = TraceWriter(directory, "trace-test")
            with self.assertRaises(ValueError):
                trace.emit(
                    stage="input",
                    action="bad",
                    status="completed",
                    details={"source_path": "/tmp/report.pdf"},
                )
            trace.close()

    def test_debug_trace_accepts_observable_data_but_redacts_secret(self):
        with tempfile.TemporaryDirectory() as directory:
            trace = TraceWriter(directory, "trace-test", debug=True)
            trace.emit(
                stage="input",
                action="debug",
                status="completed",
                details={
                    "source_path": "/tmp/report.pdf",
                    "rows": [{"value": "9.8"}],
                    "api_key": "sk-secretsecret",
                },
            )
            trace.close()
            rendered = Path(trace.path).read_text(encoding="utf-8")
        self.assertIn("/tmp/report.pdf", rendered)
        self.assertIn("9.8", rendered)
        self.assertNotIn("sk-secretsecret", rendered)
        self.assertIn("[REDACTED_SECRET]", rendered)


if __name__ == "__main__":
    unittest.main()
