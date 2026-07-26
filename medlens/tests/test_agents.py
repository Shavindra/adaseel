import json
import tempfile
import unittest
from pathlib import Path

from medlens import config
from medlens.agents import AgentCoordinator
from medlens.audit import TraceWriter
from medlens.contracts import AGENT_ROLES, OUTPUT_SCHEMAS, schema_for_role
from medlens.fake import make_fake_completer
from medlens.skills.registry import load_skill


class AgentContractTests(unittest.TestCase):
    def test_every_role_has_versioned_skill_and_closed_output_schema(self):
        for role in AGENT_ROLES:
            skill = load_skill(role)
            schema, output_name, contract_name = schema_for_role(role)
            self.assertEqual(skill["role"], role)
            self.assertTrue(skill["skill_id"].endswith("/v1"))
            self.assertTrue(skill["sha256"])
            self.assertEqual(skill["metadata"]["output_name"], output_name)
            self.assertEqual(skill["metadata"]["output_contract"], contract_name)
            self.assertFalse(schema["additionalProperties"])
            self.assertIn(contract_name, OUTPUT_SCHEMAS)

    def test_invalid_output_gets_one_correction_with_parent_invocation(self):
        calls = {"count": 0}
        valid = {
            "decision": {
                "evidence": ["Report type: Chemistry panel"],
                "report_type": "Chemistry panel",
                "source": "document_evidence",
            },
            "journal": {
                "alternatives_considered": ["unresolved"],
                "assumptions": [],
                "rationale": "The document labels the report.",
                "uncertainties": [],
            },
        }

        def completer(runtime, messages, schema, output_name):
            calls["count"] += 1
            value = {"bad": "shape"} if calls["count"] == 1 else valid
            return {"ok": True, "raw": None, "value": value}

        with tempfile.TemporaryDirectory() as directory:
            trace = TraceWriter(directory, "agent-test")
            coordinator = AgentCoordinator(
                {"agents": config.resolve_agent_runtimes(fake=True)},
                trace,
                structured_completer=completer,
            )
            result = coordinator.invoke(
                "report_classification",
                {
                    "source_text": "Report type: Chemistry panel",
                    "user_report_type": None,
                },
                source_text="Report type: Chemistry panel",
            )
            trace.close()
            events = [
                json.loads(line)
                for line in Path(trace.path).read_text().splitlines()
            ]

        self.assertTrue(result["ok"])
        self.assertEqual(calls["count"], 2)
        self.assertEqual(len(result["invocations"]), 2)
        self.assertEqual(result["invocations"][0]["status"], "invalid_output")
        self.assertEqual(
            result["invocations"][1]["parent_invocation_id"],
            result["invocations"][0]["invocation_id"],
        )
        self.assertEqual(
            len([event for event in events if event["action"] == "agent_invocation_started"]),
            2,
        )

    def test_result_id_coverage_is_exact(self):
        base = make_fake_completer()

        def incomplete(runtime, messages, schema, output_name):
            result = base(runtime, messages, schema, output_name)
            if output_name == "submit_result_validation":
                result["value"]["reviews"] = result["value"]["reviews"][:-1]
            return result

        canonical = [
            {
                "flag_from_report": "",
                "reference_range": "1-3",
                "result_id": "R0001",
                "test_name": "A",
                "unit": "",
                "value": "2",
            },
            {
                "flag_from_report": "",
                "reference_range": "1-3",
                "result_id": "R0002",
                "test_name": "B",
                "unit": "",
                "value": "2",
            },
        ]
        comparison = [
            {
                "agent_row_index": index,
                "differing_fields": [],
                "result_id": row["result_id"],
                "status": "exact_match",
            }
            for index, row in enumerate(canonical)
        ]
        extraction = [
            {
                "reference_range": row["reference_range"],
                "reported_flag": "",
                "test_name": row["test_name"],
                "unit": "",
                "value": row["value"],
            }
            for row in canonical
        ]
        with tempfile.TemporaryDirectory() as directory:
            trace = TraceWriter(directory, "coverage-test")
            coordinator = AgentCoordinator(
                {"agents": config.resolve_agent_runtimes(fake=True)},
                trace,
                structured_completer=incomplete,
            )
            result = coordinator.invoke(
                "result_validation",
                {
                    "agent_extraction": extraction,
                    "canonical_results": canonical,
                    "comparison": comparison,
                },
                result_ids=["R0001", "R0002"],
            )
            trace.close()

        self.assertFalse(result["ok"])
        self.assertEqual(len(result["invocations"]), 2)
        self.assertIn(
            "reviews_result_id_coverage_mismatch",
            result["errors"],
        )

    def test_classification_cannot_invent_a_user_override(self):
        invalid = {
            "decision": {
                "evidence": [],
                "report_type": "Invented user type",
                "source": "user_supplied",
            },
            "journal": {
                "alternatives_considered": ["unresolved"],
                "assumptions": [],
                "rationale": "Incorrectly attributed to the user.",
                "uncertainties": [],
            },
        }

        def completer(runtime, messages, schema, output_name):
            return {"ok": True, "raw": None, "value": invalid}

        with tempfile.TemporaryDirectory() as directory:
            trace = TraceWriter(directory, "classification-test")
            coordinator = AgentCoordinator(
                {"agents": config.resolve_agent_runtimes(fake=True)},
                trace,
                structured_completer=completer,
            )
            result = coordinator.invoke(
                "report_classification",
                {
                    "source_text": "Results without a label",
                    "user_report_type": None,
                },
                source_text="Results without a label",
            )
            trace.close()

        self.assertFalse(result["ok"])
        self.assertIn(
            "classification_user_source_without_override",
            result["errors"],
        )


if __name__ == "__main__":
    unittest.main()
