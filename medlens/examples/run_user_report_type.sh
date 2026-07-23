#!/usr/bin/env bash
set -euo pipefail

python -m medlens review \
  --input examples/reports/urinalysis.txt \
  --report-type "Urinalysis" \
  --runs-dir runs
