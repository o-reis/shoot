import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
GENERATED = SRC / "network" / "generated"

for p in (str(ROOT), str(SRC), str(GENERATED)):
    if p not in sys.path:
        sys.path.insert(0, p)
