#!/usr/bin/env bash
set -euo pipefail

python -m medlens review \
  --input examples/reports/renal_profile.csv \
  --runs-dir runs
