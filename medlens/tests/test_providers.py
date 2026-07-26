import os
import unittest
from unittest import mock

from medlens import providers


class ProviderLoggingTests(unittest.TestCase):
    def test_connect_timeout_is_classified_retried_and_emitted(self):
        events = []
        with mock.patch(
            "medlens.providers.requests.post",
            side_effect=providers.requests.exceptions.ConnectTimeout(
                "HTTPSConnectionPool(host='example.invalid', port=443): timed out"
            ),
        ) as request, mock.patch("medlens.providers.time.sleep") as sleep, mock.patch.object(
            providers.log,
            "warning",
        ), mock.patch.object(providers.log, "error"):
            data, error = providers._post_with_retry(
                "https://example.invalid/v1/chat/completions",
                {"Authorization": "Bearer secret"},
                {"model": "example"},
                attempts=2,
                connect_timeout=3,
                read_timeout=11,
                on_event=events.append,
            )
        self.assertIsNone(data)
        self.assertEqual(error["code"], "network_connect_timeout")
        self.assertEqual(error["endpoint"]["port"], 443)
        self.assertEqual(error["attempts"], 2)
        self.assertIn("firewall", error["hint"])
        self.assertEqual(request.call_count, 2)
        self.assertEqual(sleep.call_count, 1)
        self.assertEqual(
            request.call_args.kwargs["timeout"],
            (3, 11),
        )
        self.assertEqual(
            [item["action"] for item in events],
            [
                "provider_request_attempt_started",
                "provider_request_retry_scheduled",
                "provider_request_attempt_started",
                "provider_request_failed",
            ],
        )

    def test_tls_error_is_not_retried(self):
        with mock.patch(
            "medlens.providers.requests.post",
            side_effect=providers.requests.exceptions.SSLError("certificate failed"),
        ) as request, mock.patch("medlens.providers.time.sleep") as sleep, mock.patch.object(
            providers.log,
            "error",
        ):
            _, error = providers._post_with_retry(
                "https://example.invalid/v1/chat/completions",
                {},
                {},
                attempts=3,
            )
        self.assertEqual(error["code"], "network_tls_error")
        self.assertFalse(error["retryable"])
        self.assertEqual(request.call_count, 1)
        sleep.assert_not_called()

    def test_http_authentication_error_has_actionable_code(self):
        response = mock.Mock()
        response.ok = False
        response.status_code = 401
        response.text = '{"error":{"message":"invalid key"}}'
        with mock.patch(
            "medlens.providers.requests.post",
            return_value=response,
        ), mock.patch.object(providers.log, "error"):
            _, error = providers._post_with_retry(
                "https://example.invalid/v1/chat/completions",
                {},
                {},
                attempts=3,
            )
        self.assertEqual(error["code"], "provider_authentication_failed")
        self.assertFalse(error["retryable"])
        self.assertIn("API key", error["message"])

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

    def test_complete_structured_requires_one_exact_output_tool(self):
        payload = {
            "choices": [
                {
                    "finish_reason": "tool_calls",
                    "message": {
                        "role": "assistant",
                        "content": "",
                        "tool_calls": [
                            {
                                "id": "call_1",
                                "type": "function",
                                "function": {
                                    "name": "submit_expected",
                                    "arguments": '{"value":"ok"}',
                                },
                            }
                        ],
                    },
                }
            ]
        }
        cfg = {
            "api_key": "",
            "base_url": "https://example.invalid/v1",
            "model": "example",
            "retries": 1,
        }
        schema = {
            "type": "object",
            "additionalProperties": False,
            "required": ["value"],
            "properties": {"value": {"type": "string"}},
        }
        with mock.patch(
            "medlens.providers._post_with_retry",
            return_value=(payload, None),
        ):
            result = providers.complete_structured(
                cfg,
                [{"role": "user", "content": "{}"}],
                schema,
                "submit_expected",
            )
        self.assertTrue(result["ok"])
        self.assertEqual(result["value"], {"value": "ok"})

    def test_complete_structured_rejects_wrong_output_tool(self):
        payload = {
            "choices": [
                {
                    "finish_reason": "tool_calls",
                    "message": {
                        "role": "assistant",
                        "content": "",
                        "tool_calls": [
                            {
                                "id": "call_1",
                                "type": "function",
                                "function": {
                                    "name": "wrong_tool",
                                    "arguments": "{}",
                                },
                            }
                        ],
                    },
                }
            ]
        }
        cfg = {
            "api_key": "",
            "base_url": "https://example.invalid/v1",
            "model": "example",
            "retries": 1,
        }
        with mock.patch(
            "medlens.providers._post_with_retry",
            return_value=(payload, None),
        ):
            result = providers.complete_structured(
                cfg,
                [{"role": "user", "content": "{}"}],
                {"type": "object"},
                "submit_expected",
            )
        self.assertFalse(result["ok"])
        self.assertEqual(result["error_code"], "structured_output_wrong_name")

    def test_complete_structured_rejects_json_embedded_in_content(self):
        payload = {
            "choices": [
                {
                    "finish_reason": "stop",
                    "message": {
                        "role": "assistant",
                        "content": (
                            '{"name":"submit_expected",'
                            '"arguments":{"value":"not-a-tool-call"}}'
                        ),
                    },
                }
            ]
        }
        cfg = {
            "api_key": "",
            "base_url": "https://example.invalid/v1",
            "model": "example",
            "retries": 1,
        }
        with mock.patch(
            "medlens.providers._post_with_retry",
            return_value=(payload, None),
        ):
            result = providers.complete_structured(
                cfg,
                [{"role": "user", "content": "{}"}],
                {"type": "object"},
                "submit_expected",
            )
        self.assertFalse(result["ok"])
        self.assertEqual(
            result["error_code"],
            "structured_output_transport_missing",
        )


if __name__ == "__main__":
    unittest.main()
