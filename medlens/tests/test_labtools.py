import unittest

from medlens import labtools


class LabToolsTests(unittest.TestCase):
    def test_markdown_parser_and_document_report_type(self):
        text = """Report type: Urinalysis

| Test | Result | Unit | Reference Range | Flag |
| --- | --- | --- | --- | --- |
| pH | 6.0 | | 4.5-8.0 | |
| Protein | Negative | | Negative | |
"""
        rows = labtools.parse_lab_text(text)
        context = labtools.determine_report_type(text, rows)
        self.assertEqual(len(rows), 2)
        self.assertEqual(context["label"], "Urinalysis")
        self.assertEqual(context["source"], "document")

    def test_csv_parser_with_leading_metadata(self):
        text = """Report type: Renal profile
Test,Result,Unit,Reference Range,Flag
Sodium,141,mmol/L,135-145,
Potassium,5.8,mmol/L,3.5-5.1,H
"""
        rows = labtools.parse_lab_text(text)
        self.assertEqual([row["test_name"] for row in rows], ["Sodium", "Potassium"])

    def test_user_report_type_wins_without_fixed_taxonomy(self):
        rows = [{"test_name": "Custom marker", "value": "1", "reference_range": "0-2"}]
        context = labtools.determine_report_type(
            "No report label",
            rows,
            specified_type="Specialised metabolic assay",
        )
        self.assertEqual(context["label"], "Specialised metabolic assay")
        self.assertEqual(context["source"], "user")

    def test_arbitrary_markdown_heading_can_declare_report_type(self):
        text = """# Specialised cytokine assay

| Test | Result | Reference Range |
| --- | --- | --- |
| Marker | 1.2 | 0.5-2.0 |
"""
        rows = labtools.parse_lab_text(text)
        context = labtools.determine_report_type(text, rows)
        self.assertEqual(context["label"], "Specialised cytokine assay")
        self.assertEqual(context["source"], "document")

    def test_unknown_report_type_is_not_guessed(self):
        rows = [{"test_name": "Novel marker", "value": "1", "reference_range": "0-2"}]
        context = labtools.determine_report_type("Results", rows)
        self.assertEqual(context["source"], "unknown")
        self.assertEqual(context["reason_code"], "report_type_not_determined")

    def test_flagging_is_generic_and_fail_closed(self):
        rows = [
            {"result_id": "R0001", "test_name": "A", "value": "4", "reference_range": "5-10"},
            {"result_id": "R0002", "test_name": "B", "value": "11", "reference_range": "5-10"},
            {"result_id": "R0003", "test_name": "C", "value": "7", "reference_range": "5-10"},
            {"result_id": "R0004", "test_name": "D", "value": "7", "reference_range": "<=7"},
            {"result_id": "R0005", "test_name": "E", "value": "Negative", "reference_range": "Negative"},
            {"result_id": "R0006", "test_name": "F", "value": "7", "reference_range": ""},
        ]
        assessed, abnormal = labtools.flag_results(rows)
        self.assertEqual(
            [row["flag"] for row in assessed],
            [
                "low",
                "high",
                "normal",
                "normal",
                "cannot_assess — qualitative result unsupported",
                "cannot_assess — no range provided",
            ],
        )
        self.assertEqual([row["result_id"] for row in abnormal], ["R0001", "R0002"])
        self.assertEqual(assessed[0]["flag_reason_code"], "value_below_interval")
        self.assertEqual(assessed[4]["assessment_method"], "not_assessed")

    def test_report_provided_flag_does_not_control_calculation(self):
        assessed, abnormal = labtools.flag_results(
            [
                {
                    "test_name": "Marker",
                    "value": "5",
                    "reference_range": "1-10",
                    "flag_from_report": "H",
                }
            ]
        )
        self.assertEqual(assessed[0]["flag"], "normal")
        self.assertEqual(abnormal, [])


if __name__ == "__main__":
    unittest.main()
