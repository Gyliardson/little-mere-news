import sys
from pathlib import Path

# Publisher tests load main.py with importlib rather than importing an installed package.
# Keep the service root importable so main.py can resolve its sibling policy module in
# the same way `python Backend-Publisher/main.py` does in production.
SERVICE_ROOT = Path(__file__).resolve().parents[1]
if str(SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVICE_ROOT))
