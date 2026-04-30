#!/usr/bin/env bash
# Generated from design/test_sanitization.md v1.0

set -e

echo "🚀 Starting ClawBrain Regression Suite"
echo "========================================"

# 0. Activate Virtual Environment (Rule 11)
source venv/bin/activate

# 0.5 Purge Test Data (Strict Isolation)
rm -rf tests/data/*
mkdir -p tests/data

# 1. Sanitize Environment (Rule 10: Deterministic Integrity)
echo "[CLEANUP] Reaping orphaned server and test processes..."
if [ -f .env ]; then
    echo "[ENV] Loading configuration from .env..."
    set -a
    source .env
    set +a
fi
ps aux | grep -E "uvicorn|pytest" | grep -v grep | awk '{print $2}' | xargs kill -9 || true
sleep 1

PYTHONPATH=. python3 tests/prepare_env.py

# 2. Execute Tests
# We disable room detection to prevent background task interference during unit/integration tests
# Support selective test execution via arguments
if [ $# -eq 0 ]; then
    echo "Running full regression suite..."
    CLAWBRAIN_DISABLE_ROOM_DETECTION=true CLAWBRAIN_DISABLE_COGNITIVE_JUDGE=true PYTHONPATH=. venv/bin/pytest -s \
        tests/test_p*.py \
        tests/test_chromadb_semantic_recall.py \
        tests/test_issue_*.py
else
    echo "Running selective tests: $@"
    CLAWBRAIN_DISABLE_ROOM_DETECTION=true CLAWBRAIN_DISABLE_COGNITIVE_JUDGE=true PYTHONPATH=. venv/bin/pytest -s "$@"
fi

echo ""
echo "✅ All regression tests passed successfully!"
