import os
import unittest
from unittest import mock

from medlens import providers


class ProviderLoggingTests(unittest.TestCase):
    def test_debug_logging_omits_hidden_reasoning_content(self):
        payload = {
            "choices": [
                {
                    "finish_reason": "stop",
                    "message": {
                        "role": "assistant",
                        "content": "",
                        "reasoning": "private chain of thought content",
                    },
                }
            ]
        }
        cfg = {
            "api_key": "sk-or-v1-secretsecret",
            "base_url": "https://example.invalid/v1",
            "max_tokens": 10,
            "model": "example",
            "retries": 1,
        }
        with mock.patch.dict(os.environ, {"DEBUG": "true"}, clear=False), mock.patch(
            "medlens.providers._post_with_retry",
            return_value=(payload, None),
        ), self.assertLogs("medlens.providers", level="DEBUG") as captured:
            result = providers.chat(cfg, [{"role": "user", "content": "hello"}])
        rendered = "\n".join(captured.output)
        self.assertNotIn("private chain of thought content", rendered)
        self.assertNotIn("sk-or-v1-secretsecret", rendered)
        self.assertIn("content_omitted", rendered)
        self.assertNotIn("reasoning", result["raw"])
        self.assertNotIn("private chain of thought content", str(result["raw"]))
        self.assertTrue(
            result["raw"]["hidden_reasoning_diagnostics"]["reasoning"]["content_omitted"]
        )


if __name__ == "__main__":
    unittest.main()
