#!/usr/bin/env bash
set -euo pipefail

python -m medlens review \
  --input examples/reports/urinalysis.txt \
  --no-report \
  --no-pick \
  --runs-dir runs \
  "$@"
