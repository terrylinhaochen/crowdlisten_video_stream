#!/usr/bin/env bash
set -euo pipefail

BASE="/Users/terry/Desktop/crowdlisten_files/crowdlisten_marketing/content_gen/token_experiment_zh_cards"
MODE="${1:-fulltext}"

case "$MODE" in
  fulltext)
    python3 "$BASE/generate_v3_fulltext.py"
    echo "Output: $BASE/v3_fulltext"
    ;;
  paragraph-gap)
    # v4 generated as paragraph-gap version
    # keep this entrypoint stable for OpenClaw orchestration
    python3 "$BASE/generate_v3_fulltext.py"
    echo "Then use paragraph-gap variant script if present."
    echo "Current best readable output: $BASE/v4_fulltext_paragraph_gap"
    ;;
  *)
    echo "Usage: $0 [fulltext|paragraph-gap]"
    exit 1
    ;;
esac
