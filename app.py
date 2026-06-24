"""
LCA_TYRE Streamlit entry point.

Run:
    streamlit run app.py

or:
    python -m streamlit run app.py
"""

from pathlib import Path
import runpy
import sys

ROOT = Path(__file__).resolve().parent
ENGINE_PATH = ROOT / "engine" / "opentyre_lca"

# Make local engine importable
sys.path.insert(0, str(ENGINE_PATH))

# Run the main dashboard script
runpy.run_path(str(ROOT / "web" / "streamlit_app.py"), run_name="__main__")
