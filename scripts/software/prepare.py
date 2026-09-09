"""Create isolated software-rendering analysis inputs from verified firmware."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'guest'))
from diagnostics import sysroot

root = Path('/software')
target = root / 'sysroot'
if not target.exists():
    sysroot('cmu150-eu-74.00.324A', root).rename(target)
print(target)
