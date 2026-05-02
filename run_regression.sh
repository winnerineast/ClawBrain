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
    echo "[ENV] Sanitizing .env for regression (hiding platform prefixes)..."
    mv .env .env.bak
    # Create a sanitized .env with only generic keys to allow test-level overrides
    grep -vE "^(LINUX_|DARWIN_)" .env.bak > .env || true
    # Ensure original .env is restored
    trap "mv .env.bak .env" EXIT
fi
ps aux | grep -E "uvicorn|pytest" | grep -v grep | awk '{print $2}' | xargs kill -9 || true
sleep 1

PYTHONPATH=. python3 tests/prepare_env.py

# 2. Execute Tests
# We disable room detection to prevent background task interference
# We disable cognitive judge for DETERMINISTIC regression results (did we find it?)
# but the upstream LLM is still LIVE for generation.
COMMON_ENV="CLAWBRAIN_DISABLE_ROOM_DETECTION=true CLAWBRAIN_DISABLE_COGNITIVE_JUDGE=true PYTHONPATH=."

if [ $# -eq 0 ]; then
    echo "Running full LIVE regression suite..."
    eval $COMMON_ENV venv/bin/pytest -s \
        tests/test_p*.py \
        tests/test_chromadb_semantic_recall.py \
        tests/test_issue_*.py
else
    echo "Running selective LIVE tests: $@"
    eval $COMMON_ENV venv/bin/pytest -s "$@"
fi

echo ""
echo "✅ All regression tests passed successfully!"
