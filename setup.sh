#!/bin/bash
# setup.sh — Local environment setup
# Run once after cloning the repo: bash setup.sh

set -e

echo ""
echo "═══════════════════════════════════════════════════"
echo "  🖥  YouTube Automation — Local Setup"
echo "═══════════════════════════════════════════════════"
echo ""

# ── Check Python version ────────────────────────────────────────────────────
PY_VER=$(python3 --version 2>&1 | awk '{print $2}')
echo "✔  Python: $PY_VER"
python3 -c "import sys; assert sys.version_info >= (3,10), 'Python 3.10+ required'" || {
    echo "❌  Python 3.10+ is required. Install from python.org"
    exit 1
}

# ── Check ffmpeg ────────────────────────────────────────────────────────────
if ! command -v ffmpeg &> /dev/null; then
    echo "⚠️   ffmpeg not found — installing…"
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        sudo apt-get install -y ffmpeg
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        brew install ffmpeg
    else
        echo "❌  Please install ffmpeg manually: https://ffmpeg.org/download.html"
        exit 1
    fi
fi
echo "✔  ffmpeg: $(ffmpeg -version 2>&1 | head -1 | awk '{print $3}')"

# ── Install Python packages ─────────────────────────────────────────────────
echo ""
echo "📦  Installing Python dependencies…"
pip install -r requirements.txt -q
echo "✔  Dependencies installed"

# ── Create .env from example ────────────────────────────────────────────────
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo ""
    echo "📝  Created .env — fill in your API keys:"
    echo "    • ANTHROPIC_API_KEY  → console.anthropic.com"
    echo "    • YouTube creds      → run: python auth_setup.py"
else
    echo "✔  .env already exists"
fi

# ── Create output directory ─────────────────────────────────────────────────
mkdir -p output
echo "✔  output/ directory ready"

echo ""
echo "═══════════════════════════════════════════════════"
echo "  ✅  Setup complete!"
echo ""
echo "  Next steps:"
echo "  1. Edit .env → add your ANTHROPIC_API_KEY"
echo "  2. Run: python auth_setup.py  (get YouTube token)"
echo "  3. Run: python pipeline.py    (test the pipeline)"
echo "  4. Push to GitHub + add Secrets → auto-runs daily"
echo "═══════════════════════════════════════════════════"
echo ""
