import sys
import os
from pathlib import Path

# Set environment
os.environ["VERCEL"] = "1"

root_dir = Path(__file__).resolve().parent.parent
backend_dir = root_dir / "backend"

for p in [str(root_dir), str(backend_dir)]:
    if p not in sys.path:
        sys.path.insert(0, p)

try:
    from app.main import app
    try:
        from mangum import Mangum
        handler = Mangum(app)
    except Exception:
        handler = app
except Exception as err:
    from fastapi import FastAPI
    from fastapi.responses import JSONResponse
    app = FastAPI()
    
    @app.get("/{full_path:path}")
    def fallback(full_path: str):
        return JSONResponse({"status": "ERROR", "message": f"Serverless init failed: {err}"}, status_code=500)
    
    handler = app
