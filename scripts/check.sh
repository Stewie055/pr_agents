#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

.venv/bin/ruff check src tests
.venv/bin/python -m pytest

cd "$ROOT_DIR/frontend"
npm run typecheck
npm test
npm run build
