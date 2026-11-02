import sys
from pathlib import Path

sys.dont_write_bytecode = True
# `python -m pytest maia/tests` from the repo root already has the root on sys.path; this makes other cwds work too
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
