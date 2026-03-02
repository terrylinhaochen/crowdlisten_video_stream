#!/usr/bin/env bash
set -euo pipefail

BASE="/Users/terry/Desktop/crowdlisten_files/crowdlisten_marketing"
SCRIPTS="$BASE/scripts"
CARDS="$BASE/content_gen/token_experiment_zh_cards"

usage() {
  cat <<USAGE
Usage: $0 <command> [args]

Commands:
  check
      Validate environment + key files for long-form and video flows.

  content --input <file> [--platforms blog,linkedin,newsletter,thread] [--version vX]
      Run long-form -> multi-channel content generation.

  cards [fulltext|paragraph-gap]
      Run Chinese card generation workflow (OpenClaw-first scripts).

  analyze-video <video_path> [--clips N] [--model gemini-2.0-flash]
      Run meme moment detection on a source video.

  render-reels
      Run reels render batch from scripts/render_reels.py config.

  studio-start
      Start Studio GUI backend/frontend.
USAGE
}

check_cmd() {
  echo "== Flow Check =="
  command -v python3 >/dev/null || { echo "Missing python3"; exit 1; }

  test -f "$SCRIPTS/content_gen.py" || { echo "Missing scripts/content_gen.py"; exit 1; }
  test -f "$SCRIPTS/analyze_video.py" || { echo "Missing scripts/analyze_video.py"; exit 1; }
  test -f "$SCRIPTS/render_reels.py" || { echo "Missing scripts/render_reels.py"; exit 1; }

  test -f "$CARDS/generate_v2.py" || echo "WARN: cards generate_v2.py missing"
  test -f "$CARDS/generate_v3_fulltext.py" || echo "WARN: cards generate_v3_fulltext.py missing"

  test -d "$BASE/studio/backend" || { echo "Missing studio/backend"; exit 1; }
  test -f "$BASE/studio/backend/main.py" || { echo "Missing studio/backend/main.py"; exit 1; }

  if [ -d "$BASE/marketing_clips" ]; then
    echo "marketing_clips present"
  else
    echo "WARN: marketing_clips missing"
  fi

  echo "-- CLI smoke --"
  python3 "$SCRIPTS/content_gen.py" --help >/dev/null && echo "content_gen.py OK"
  python3 "$SCRIPTS/analyze_video.py" --help >/dev/null && echo "analyze_video.py OK"
  echo "render_reels.py is batch-config driven (no --help); script present ✅"

  echo "== Check complete =="
}

content_cmd() {
  local input=""
  local platforms="blog,linkedin,newsletter,thread"
  local version=""

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --input) input="$2"; shift 2 ;;
      --platforms) platforms="$2"; shift 2 ;;
      --version) version="$2"; shift 2 ;;
      *) echo "Unknown arg: $1"; exit 1 ;;
    esac
  done

  [[ -n "$input" ]] || { echo "--input required"; exit 1; }

  cmd=(python3 "$SCRIPTS/content_gen.py" --input "$input" --platforms "$platforms" --style every)
  if [[ -n "$version" ]]; then cmd+=(--version "$version"); fi

  "${cmd[@]}"
}

cards_cmd() {
  local mode="${1:-fulltext}"
  case "$mode" in
    fulltext)
      python3 "$CARDS/generate_v3_fulltext.py"
      echo "Output: $CARDS/v3_fulltext"
      ;;
    paragraph-gap)
      # Current paragraph-gap output is already generated as v4_fulltext_paragraph_gap.
      # Keep command stable for OpenClaw orchestration.
      if [ -d "$CARDS/v4_fulltext_paragraph_gap" ]; then
        echo "Output: $CARDS/v4_fulltext_paragraph_gap"
      else
        echo "paragraph-gap output missing; run fulltext first or create dedicated v4 script."
        exit 1
      fi
      ;;
    *)
      echo "cards mode must be fulltext|paragraph-gap"
      exit 1
      ;;
  esac
}

analyze_video_cmd() {
  [[ $# -ge 1 ]] || { echo "video path required"; exit 1; }
  local video="$1"; shift
  python3 "$SCRIPTS/analyze_video.py" "$video" "$@"
}

render_reels_cmd() {
  python3 "$SCRIPTS/render_reels.py"
}

studio_start_cmd() {
  (cd "$BASE/studio" && ./start.sh)
}

main() {
  [[ $# -ge 1 ]] || { usage; exit 1; }
  local cmd="$1"; shift
  case "$cmd" in
    check) check_cmd "$@" ;;
    content) content_cmd "$@" ;;
    cards) cards_cmd "$@" ;;
    analyze-video) analyze_video_cmd "$@" ;;
    render-reels) render_reels_cmd "$@" ;;
    studio-start) studio_start_cmd "$@" ;;
    *) usage; exit 1 ;;
  esac
}

main "$@"
