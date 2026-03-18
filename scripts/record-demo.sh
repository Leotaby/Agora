#!/bin/bash
# Record a demo GIF of the AGORA 3D visualizer for the README.
#
# Prerequisites:
#   brew install ffmpeg
#
# Usage:
#   1. Start the backend:  cd ~/Downloads/nexus/backend && uv run python run.py
#   2. Build & launch the visualizer in another terminal
#   3. Run this script:    ./scripts/record-demo.sh
#   4. A 20-second screen recording will start — interact with the visualizer
#      (advance rounds with SPACE, rotate with mouse, let ECB intervention play)
#   5. The script converts the recording to a GIF and prints the path.

set -euo pipefail
cd "$(dirname "$0")/.."

DOCS_DIR="docs"
RAW_MOV="$DOCS_DIR/agora-raw.mov"
GIF_OUT="$DOCS_DIR/agora-demo.gif"

mkdir -p "$DOCS_DIR"

# Check for ffmpeg
if ! command -v ffmpeg &>/dev/null; then
    echo "ERROR: ffmpeg not found. Install with: brew install ffmpeg"
    exit 1
fi

echo "Recording will start in 3 seconds — switch to the AGORA visualizer window."
echo "Recording lasts 20 seconds. Use SPACE to advance rounds, drag to rotate."
sleep 3

# Record 20 seconds of the screen (macOS will prompt for the window/area)
screencapture -v -V 20 "$RAW_MOV"

echo "Recording saved to $RAW_MOV"
echo "Converting to GIF..."

# Convert to high-quality GIF with palette optimization
ffmpeg -y -i "$RAW_MOV" \
    -vf "fps=12,scale=900:-1:flags=lanczos,split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse" \
    -loop 0 "$GIF_OUT"

echo "GIF saved to $GIF_OUT"
echo ""
echo "To add to README and commit:"
echo "  git add docs/agora-demo.gif README.md"
echo '  git commit -m "docs: add 3D visualization demo GIF"'
echo "  git push origin main"
