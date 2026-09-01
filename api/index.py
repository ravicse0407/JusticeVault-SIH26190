import sys
import os
from pathlib import Path

# Tell backend to use /tmp for SQLite and vault storage on Vercel
os.environ["VERCEL"] = "1"

# Add backend directory to sys.path so app modules can be imported
root_dir = Path(__file__).resolve().parent.parent
backend_dir = root_dir / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.main import app
from app.core import init_db

# Initialize database schema and seeds on cold start
try:
    init_db()
except Exception as e:
    print("JusticeVault startup init error:", e)
