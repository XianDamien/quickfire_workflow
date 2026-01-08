#!/bin/bash
# Batch Monitoring Script for Zoe61330_2025-12-15
# Purpose: Monitor status of audio batch processing

# Color codes
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Environment Setup
export GEMINI_API_KEY=***GOOGLE_API_KEY_REDACTED***
export HTTPS_PROXY=http://127.0.0.1:7890

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Batch Status Monitor${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Function to check batch status
check_batch() {
    local batch_name=$1
    echo -e "${YELLOW}Checking: $batch_name${NC}"
    uv run python scripts/gemini_batch_audio.py status --batch-name "$batch_name" 2>&1
    echo ""
}

# Check both batches
check_batch "audio-Zoe61330_2025-12-15-r1"
check_batch "audio-Zoe61330_2025-12-15-r2"

# List all batches
echo -e "${BLUE}All Batches:${NC}"
uv run python scripts/gemini_batch_audio.py list
echo ""

# Instructions
echo -e "${YELLOW}To download completed batches:${NC}"
echo "  uv run python scripts/gemini_batch_audio.py download --batch-name audio-Zoe61330_2025-12-15-r1"
echo "  uv run python scripts/gemini_batch_audio.py download --batch-name audio-Zoe61330_2025-12-15-r2"
echo ""
echo -e "${YELLOW}To run this monitor in a loop (every 60s):${NC}"
echo "  watch -n 60 ./monitor_batches.sh"
