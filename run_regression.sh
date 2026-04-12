#!/usr/bin/env bash
# Generated from design/test_sanitization.md v1.0

set -e

echo "🚀 Starting ClawBrain Regression Suite"
echo "========================================"

# 1. Sanitize Environment
PYTHONPATH=. python3 tests/prepare_env.py

# 2. Execute Tests
# We disable room detection to prevent background task interference during unit/integration tests
# Support selective test execution via arguments
if [ $# -eq 0 ]; then
    echo "Running full regression suite..."
    CLAWBRAIN_DISABLE_ROOM_DETECTION=true PYTHONPATH=. venv/bin/pytest -s \
        tests/test_p*.py \
        tests/test_chromadb_semantic_recall.py \
        tests/test_issue_*.py
else
    echo "Running selective tests: $@"
    CLAWBRAIN_DISABLE_ROOM_DETECTION=true PYTHONPATH=. venv/bin/pytest -s "$@"
fi

echo ""
echo "✅ All regression tests passed successfully!"
