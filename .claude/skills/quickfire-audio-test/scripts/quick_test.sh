#!/usr/bin/env bash
# Quick test script for single student with audio annotation
# Usage: ./quick_test.sh <batch-id> <student-name>

set -e

BATCH_ID="$1"
STUDENT="$2"

if [ -z "$BATCH_ID" ] || [ -z "$STUDENT" ]; then
    echo "Usage: $0 <batch-id> <student-name>"
    echo ""
    echo "Example:"
    echo "  $0 TestClass88888_2026-01-05 Qihang"
    echo ""
    echo "Available batches:"
    ls -1 archive/ | head -5
    exit 1
fi

echo "════════════════════════════════════════════════════════════"
echo "  Quickfire Audio Test - Single Student"
echo "════════════════════════════════════════════════════════════"
echo "  Batch: $BATCH_ID"
echo "  Student: $STUDENT"
echo "  Model: gemini-3-pro-preview (audio mode)"
echo "════════════════════════════════════════════════════════════"
echo ""

# Check audio file exists
AUDIO_FILE="archive/$BATCH_ID/$STUDENT/1_input_audio.mp3"
if [ ! -f "$AUDIO_FILE" ]; then
    echo "❌ Error: Audio file not found: $AUDIO_FILE"
    echo ""
    echo "Available students in $BATCH_ID:"
    ls -1 "archive/$BATCH_ID/" | grep -v "^_" | grep -v "metadata.json" | head -10
    exit 1
fi

echo "✅ Audio file found: $AUDIO_FILE"
echo ""

# Run test
echo "Running audio annotation test..."
echo ""
uv run python scripts/main.py \
    --archive-batch "$BATCH_ID" \
    --student "$STUDENT" \
    --annotator gemini-audio

# Find latest result
RESULT_DIR=$(find "archive/$BATCH_ID/$STUDENT/runs/gemini-3-pro-preview" -type d -name "[0-9]*" | sort -r | head -1)

if [ -n "$RESULT_DIR" ]; then
    echo ""
    echo "════════════════════════════════════════════════════════════"
    echo "  Results"
    echo "════════════════════════════════════════════════════════════"
    echo ""

    # Show grade
    if [ -f "$RESULT_DIR/4_llm_annotation.json" ]; then
        GRADE=$(cat "$RESULT_DIR/4_llm_annotation.json" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('final_grade_suggestion', 'N/A'))")
        ERRORS=$(cat "$RESULT_DIR/4_llm_annotation.json" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('mistake_count', {}).get('errors', 'N/A'))")

        echo "  Grade: $GRADE"
        echo "  Errors: $ERRORS"
        echo ""
        echo "  Annotation file: $RESULT_DIR/4_llm_annotation.json"
        echo "  Prompt log: $RESULT_DIR/prompt_log.txt"
        echo ""
    fi
fi

echo "════════════════════════════════════════════════════════════"
