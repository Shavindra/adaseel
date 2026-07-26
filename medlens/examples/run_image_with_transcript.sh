#!/usr/bin/env bash
set -euo pipefail

python -m medlens review \
  --input examples/reports/sample_lab_report.png \
  --transcript examples/reports/sample_lab_report.txt \
  --no-pick \
  --runs-dir runs \
  "$@"
