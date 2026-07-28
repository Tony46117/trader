"""
╔══════════════════════════════════════════════════════════╗
║          TRADER v2 — Entry Point                        ║
╠══════════════════════════════════════════════════════════╣
║  Run:  python app.py  (or  python3 app.py)              ║
║  Then open http://localhost:5000                        ║
╚══════════════════════════════════════════════════════════╝
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import and run the server
from server import main

if __name__ == "__main__":
    main()
