#!/bin/bash
# ── TRADER v2 — Setup Script ──────────────────────────────────
set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${CYAN}"
echo "╔══════════════════════════════════════════════════════════╗"
echo "║          TRADER v2 — Setup & Launch                    ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# ── 1. Python environment ──
PYTHON="${HOME}/python312-dev/bin/python3.12"
if [ ! -f "$PYTHON" ]; then
    echo -e "${YELLOW}Creating python3.12 virtual environment...${NC}"
    python3.12 -m venv "${HOME}/python312-dev"
fi

PIP="${HOME}/python312-dev/bin/pip3.12"
echo -e "${GREEN}✅ $($PYTHON --version)${NC}"

# ── 2. Install deps ──
$PIP install --upgrade pip setuptools wheel --quiet
$PIP install -r requirements.txt --quiet
echo -e "${GREEN}✅ Dependencies installed${NC}"

# ── 3. Compile C++ (if possible) ──
if command -v g++ &>/dev/null && [ -f /usr/include/python3.12/Python.h ]; then
    echo -e "${YELLOW}Compiling C++ indicators...${NC}"
    cd engine/cpp_indicator
    make -f Makefile PYTHON=$PYTHON 2>&1 || echo -e "${YELLOW}⚠️  C++ compilation optional — falling back to pure Python${NC}"
    cd ../..
fi

echo -e "\n${GREEN}"
echo "╔══════════════════════════════════════════════════════════╗"
echo "║          ✅ Ready!                                      ║"
echo "╠══════════════════════════════════════════════════════════╣"
echo "║  Run: ~/python312-dev/bin/python3.12 server.py           ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo -e "${NC}"
