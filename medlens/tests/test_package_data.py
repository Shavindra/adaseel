import importlib.resources
import importlib.util
import subprocess
import sys
import tempfile
import unittest
import venv
import zipfile
from pathlib import Path


class PackageDataTests(unittest.TestCase):
    def test_bundled_transcript_is_loadable(self):
        sample = (
            importlib.resources.files("medlens")
            .joinpath("resources")
            .joinpath("sample_lab_report.txt")
        )
        self.assertIn("SYNTHETIC SAMPLE", sample.read_text(encoding="utf-8"))

    @unittest.skipUnless(importlib.util.find_spec("build"), "build extra is not installed")
    def test_wheel_contains_bundled_transcript_and_agent_skills(self):
        project = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as directory:
            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "build",
                    "--wheel",
                    "--no-isolation",
                    "--outdir",
                    directory,
                ],
                cwd=project,
                check=True,
                capture_output=True,
                text=True,
            )
            wheel = next(Path(directory).glob("*.whl"))
            with zipfile.ZipFile(wheel) as archive:
                names = archive.namelist()
            environment = Path(directory) / "venv"
            venv.EnvBuilder(with_pip=True).create(environment)
            python = environment / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
            subprocess.run(
                [
                    str(python),
                    "-m",
                    "pip",
                    "install",
                    "--no-deps",
                    str(wheel),
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            installed = subprocess.run(
                [
                    str(python),
                    "-c",
                    (
                        "import importlib.resources as r; "
                        "p=r.files('medlens').joinpath('resources/sample_lab_report.txt'); "
                        "assert 'SYNTHETIC SAMPLE' in p.read_text(encoding='utf-8'); "
                        "from medlens.skills.registry import load_skill; "
                        "assert load_skill('result_flagging')['skill_id']=='result_flagging/v1'"
                    ),
                ],
                check=True,
                capture_output=True,
                text=True,
            )
        self.assertIn("medlens/resources/sample_lab_report.txt", names)
        self.assertIn("medlens/fake.py", names)
        self.assertIn("medlens/picker.py", names)
        self.assertIn(
            "medlens/skills/report_classification/v1/skill.json",
            names,
        )
        self.assertIn(
            "medlens/skills/result_flagging/v1/system.md",
            names,
        )
        self.assertEqual(installed.returncode, 0)


if __name__ == "__main__":
    unittest.main()
