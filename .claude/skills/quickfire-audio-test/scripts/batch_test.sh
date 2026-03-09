#!/usr/bin/env bash
# Batch test script for processing entire class
# Usage: ./batch_test.sh <batch-id> [student1,student2,...]

set -e

BATCH_ID="$1"
STUDENTS="$2"

if [ -z "$BATCH_ID" ]; then
    echo "Usage: $0 <batch-id> [student1,student2,...]"
    echo ""
    echo "Examples:"
    echo "  $0 TestClass88888_2026-01-05                    # Process all students"
    echo "  $0 TestClass88888_2026-01-05 Qihang,Oscar       # Process specific students"
    echo ""
    echo "Available batches:"
    ls -1 archive/ | head -5
    exit 1
fi

echo "════════════════════════════════════════════════════════════"
echo "  Quickfire Batch Audio Test"
echo "════════════════════════════════════════════════════════════"
echo "  Batch: $BATCH_ID"
echo "  Mode: Batch API (50% cost savings)"
echo "  Model: gemini-3-pro-preview"

if [ -n "$STUDENTS" ]; then
    echo "  Students: $STUDENTS"
else
    echo "  Students: All in batch"
fi

echo "════════════════════════════════════════════════════════════"
echo ""

# Check batch directory exists
if [ ! -d "archive/$BATCH_ID" ]; then
    echo "❌ Error: Batch directory not found: archive/$BATCH_ID"
    echo ""
    echo "Available batches:"
    ls -1 archive/ | head -10
    exit 1
fi

# Count students
STUDENT_COUNT=$(ls -1 "archive/$BATCH_ID/" | grep -v "^_" | grep -v "metadata.json" | wc -l | tr -d ' ')
echo "✅ Batch directory found: $STUDENT_COUNT students"
echo ""

# Run batch test
echo "Submitting batch job..."
echo ""

if [ -n "$STUDENTS" ]; then
    uv run python scripts/main.py \
        --archive-batch "$BATCH_ID" \
        --student "$STUDENTS" \
        --batch-audio
else
    uv run python scripts/main.py \
        --archive-batch "$BATCH_ID" \
        --batch-audio
fi

# Find latest batch run
BATCH_RUN_DIR=$(find "archive/$BATCH_ID/_batch_runs" -type d -name "*.audio" | sort -r | head -1)

if [ -n "$BATCH_RUN_DIR" ]; then
    echo ""
    echo "════════════════════════════════════════════════════════════"
    echo "  Batch Results"
    echo "════════════════════════════════════════════════════════════"
    echo ""

    # Show summary
    if [ -f "$BATCH_RUN_DIR/batch_report.json" ]; then
        echo "  Report: $BATCH_RUN_DIR/batch_report.json"
        echo ""

        # Extract summary stats
        python3 <<EOF
import json
with open('$BATCH_RUN_DIR/batch_report.json', 'r') as f:
    data = json.load(f)
    summary = data.get('summary', {})
    print(f"  Total students: {summary.get('total_students', 'N/A')}")
    print(f"  Success: {summary.get('success', 'N/A')}")
    print(f"  Failed: {summary.get('failed', 'N/A')}")
    print()

    grades = summary.get('grade_distribution', {})
    print(f"  Grade distribution:")
    print(f"    A: {grades.get('A', 0)}")
    print(f"    B: {grades.get('B', 0)}")
    print(f"    C: {grades.get('C', 0)}")
    print()

    tokens = data.get('token_usage', {}).get('total', {})
    print(f"  Token usage:")
    print(f"    Total: {tokens.get('total_tokens', 0):,}")
EOF

        echo ""
        echo "  Student reports: $BATCH_RUN_DIR/students/"
        echo ""
    fi
fi

echo "════════════════════════════════════════════════════════════"
