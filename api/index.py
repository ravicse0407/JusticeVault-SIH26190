import sys
import os
from pathlib import Path

# Force Vercel / serverless environment mode
os.environ["VERCEL"] = "1"

root_dir = Path(__file__).resolve().parent.parent
backend_dir = root_dir / "backend"

for p in [str(root_dir), str(backend_dir), str(backend_dir / "app")]:
    if p not in sys.path:
        sys.path.insert(0, p)

from app.main import app
