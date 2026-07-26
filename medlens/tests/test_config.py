import unittest
from unittest import mock

from medlens import config
from medlens.agents import public_runtime


class AgentRuntimeConfigTests(unittest.TestCase):
    def test_openrouter_shorthands_resolve_to_current_tool_capable_models(self):
        with mock.patch.dict(
            "os.environ",
            {"OPENROUTER_API_KEY": "test-key"},
            clear=True,
        ):
            nemotron = config.resolve_agent_runtimes(
                provider="openrouter",
                model="nemotron",
            )["report_classification"]
            qwen = config.resolve_agent_runtimes(
                provider="openrouter",
                model="qwen",
            )["report_classification"]
        self.assertEqual(
            nemotron["model"],
            "nvidia/nemotron-3-nano-30b-a3b:free",
        )
        self.assertEqual(
            qwen["model"],
            "qwen/qwen3-next-80b-a3b-instruct",
        )
        self.assertTrue(nemotron["model"].endswith(":free"))
        self.assertFalse(qwen["model"].endswith(":free"))

    def test_per_agent_provider_and_model_overrides_are_independent(self):
        with mock.patch.dict(
            "os.environ",
            {
                "OPENROUTER_API_KEY": "openrouter-key",
                "GROQ_API_KEY": "groq-key",
            },
            clear=False,
        ):
            runtimes = config.resolve_agent_runtimes(
                provider="ollama",
                model="qwen",
                agent_providers={"result_validation": "groq"},
                agent_models={
                    "result_extraction": "custom-extractor",
                    "result_validation": "qwen",
                },
            )
        self.assertEqual(runtimes["report_classification"]["provider"], "ollama")
        self.assertEqual(runtimes["report_classification"]["model"], "qwen3.5")
        self.assertEqual(runtimes["result_extraction"]["model"], "custom-extractor")
        self.assertEqual(runtimes["result_validation"]["provider"], "groq")
        self.assertEqual(runtimes["result_validation"]["model"], "qwen/qwen3-32b")
        self.assertEqual(runtimes["result_validation"]["api_key"], "groq-key")
        self.assertEqual(runtimes["result_flagging"]["provider"], "ollama")

    def test_fake_runtime_has_one_profile_per_role(self):
        runtimes = config.resolve_agent_runtimes(fake=True)
        self.assertEqual(len(runtimes), 4)
        self.assertTrue(all(runtime["fake"] for runtime in runtimes.values()))
        self.assertEqual(len({item["model"] for item in runtimes.values()}), 4)
        self.assertTrue(
            all(runtime["api_key_required"] is False for runtime in runtimes.values())
        )

    def test_hosted_key_presence_and_source_are_explicit_without_key_value(self):
        with mock.patch.dict(
            "os.environ",
            {"OPENROUTER_API_KEY": "test-key-material"},
            clear=True,
        ):
            runtime = config.resolve_agent_runtimes(
                provider="openrouter",
                model="qwen",
            )["result_extraction"]
        self.assertTrue(runtime["api_key_present"])
        self.assertTrue(runtime["api_key_required"])
        self.assertEqual(
            runtime["configuration_sources"]["api_key_source"],
            "global:environment:OPENROUTER_API_KEY",
        )
        self.assertEqual(config.validate_runtime(runtime), [])
        self.assertNotIn(
            "test-key-material",
            str(runtime["configuration_sources"]),
        )
        public = public_runtime(runtime)
        self.assertTrue(public["api_key_status"]["present"])
        self.assertEqual(
            public["api_key_status"]["source"],
            "global:environment:OPENROUTER_API_KEY",
        )
        self.assertNotIn("test-key-material", str(public))

    def test_missing_hosted_key_fails_preflight_without_network(self):
        with mock.patch.dict("os.environ", {}, clear=True):
            runtime = config.resolve_agent_runtimes(
                provider="groq",
                model="qwen",
            )["result_flagging"]
        failures = config.validate_runtime(runtime)
        self.assertEqual([item["code"] for item in failures], ["agent_api_key_missing"])
        self.assertFalse(runtime["api_key_present"])
        self.assertEqual(
            runtime["configuration_sources"]["api_key_source"],
            "global:not_configured",
        )

    def test_safe_base_url_removes_credentials_query_and_fragment(self):
        self.assertEqual(
            config.safe_base_url(
                "https://user:secret@example.invalid:8443/v1?token=secret#fragment"
            ),
            "https://example.invalid:8443/v1",
        )


if __name__ == "__main__":
    unittest.main()
