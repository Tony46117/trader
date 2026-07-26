#!/bin/bash
# ── Trading Signal Framework — Setup & Launch Script ─────────────
set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${CYAN}"
echo "╔══════════════════════════════════════════════════════════╗"
echo "║       TRADING SIGNAL FRAMEWORK — Setup & Launch        ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# ── 1. Check Python environment ──
PYTHON="${HOME}/python312-dev/bin/python3.12"
if [ ! -f "$PYTHON" ]; then
    echo -e "${YELLOW}⚠️  python312-dev environment not found, creating...${NC}"
    python3.12 -m venv "${HOME}/python312-dev"
    PYTHON="${HOME}/python312-dev/bin/python3.12"
fi

PIP="${HOME}/python312-dev/bin/pip3.12"
echo -e "${GREEN}✅ Using Python: $($PYTHON --version)${NC}"

# ── 2. Install dependencies ──
echo -e "\n${YELLOW}📦 Installing Python dependencies...${NC}"
$PIP install --upgrade pip setuptools wheel
$PIP install -r requirements.txt

# ── 3. Install additional packages needed ──
echo -e "\n${YELLOW}📦 Installing additional packages...${NC}"
$PIP install pybind11 yfinance TA-Lib ccxt gunicorn requests beautifulsoup4 flask-cors

# ── 4. Compile C++ indicator module ──
echo -e "\n${YELLOW}⚡ Compiling C++ accelerated indicators...${NC}"
cd engine/cpp_indicator

# Check if pybind11 is available
$PYTHON -c "import pybind11; print(pybind11.get_include())" 2>/dev/null || {
    echo -e "${RED}❌ pybind11 not found, installing...${NC}"
    $PIP install pybind11
}

# Build the module
make -f Makefile PYTHON=$PYTHON 2>&1 || {
    echo -e "${YELLOW}⚠️  C++ compilation failed, falling back to pure Python${NC}"
    echo -e "${YELLOW}   Install build tools: sudo apt-get install g++ python3-dev${NC}"
}

cd ../..

# ── 5. Copy news data if available ──
echo -e "\n${YELLOW}📊 Checking news data files...${NC}"
if [ ! -d "data/news" ]; then
    mkdir -p data/news
fi

# Copy forex factory CSV files from common locations
for file in "${HOME}/Desktop/forex_factory_"*.csv "${HOME}/Documents/forex_factory_"*.csv; do
    if [ -f "$file" ]; then
        cp "$file" data/news/
        echo -e "${GREEN}  ✅ Copied: $(basename $file)${NC}"
    fi
done

# ── 6. Launch ──
echo -e "\n${GREEN}"
echo "╔══════════════════════════════════════════════════════════╗"
echo "║          ✅ Setup Complete!                             ║"
echo "╠══════════════════════════════════════════════════════════╣"
echo "║  Run: gunicorn app:app --bind 0.0.0.0:5000             ║"
echo "║  Or:  python app.py                                    ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo -e "${NC}"
