#!/usr/bin/env bash
# Generated from design/test_sanitization.md v1.2
# Mandate: Objective Reality. Run until SUCCESS or 3 CONSECUTIVE FAILURES.

FAIL_COUNT=0
MAX_FAILS=3
ROUND=1

echo "🚀 Starting Ultimate PageIndex Verification Loop..."
echo "===================================================="

while true; do
    echo "📍 ROUND $ROUND (Consecutive Fails: $FAIL_COUNT)"
    
    # Run pytest. We don't clean pageindex/ cache so it resumes work.
    PYTHONPATH=. venv/bin/pytest -v -s tests/test_p66_pageindex.py
    EXIT_CODE=$?

    if [ $EXIT_CODE -eq 0 ]; then
        echo "✅ SUCCESS! PageIndex perfectly integrated after $ROUND rounds."
        exit 0
    else
        FAIL_COUNT=$((FAIL_COUNT + 1))
        echo "❌ Round $ROUND failed."
        
        if [ $FAIL_COUNT -ge $MAX_FAILS ]; then
            echo "🚨 CRITICAL FAILURE: 3 consecutive failures reached. Halting."
            exit 1
        fi
    fi
    
    ROUND=$((ROUND + 1))
    echo "⏳ Cooling down for 5s before next attempt..."
    sleep 5
done
