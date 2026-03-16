"""
NEXUS = HumanTwin
Backend entry point — FastAPI + uvicorn
Mirrors MiroFish's run.py pattern
"""
import uvicorn
from app import create_app
from app.config import settings

app = create_app()

if __name__ == "__main__":
    uvicorn.run(
        "run:app",
        host=settings.BACKEND_HOST,
        port=settings.BACKEND_PORT,
        reload=True,
        log_level="info",
    )
