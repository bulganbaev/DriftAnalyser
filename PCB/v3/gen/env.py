import os, subprocess

APP = "/Applications/KiCad/KiCad.app/Contents"
KICAD_CLI = f"{APP}/MacOS/kicad-cli"
KICAD_PY = f"{APP}/Frameworks/Python.framework/Versions/Current/bin/python3"
SYMBOL_DIR = f"{APP}/SharedSupport/symbols"
FOOTPRINT_DIR = f"{APP}/SharedSupport/footprints"
DEMO_DIR = os.path.expanduser("~/Library/Application Support/kicad/demos")
PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CUSTOM_SYM = os.path.join(PROJECT_DIR, "lib", "da3.kicad_sym")
CUSTOM_FP = os.path.join(PROJECT_DIR, "lib", "da3.pretty")
PROJECT_NAME = "driftanalyser-v3"

def run_cli(*args, check=False):
    return subprocess.run([KICAD_CLI, *args], capture_output=True, text=True, check=check)
