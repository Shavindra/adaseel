#!/usr/bin/env bash
set -euo pipefail

python -m medlens review \
  --input sample_lab_report.png \
  --transcript sample_lab_report.txt \
  --runs-dir runs
