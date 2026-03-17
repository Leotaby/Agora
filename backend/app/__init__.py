from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


def create_app() -> FastAPI:
    app = FastAPI(
        title="AGORA — Banking Stability Simulator",
        description="Agent-based banking contagion through interbank networks",
        version="0.1.0",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    from app.api import router, banking_router
    app.include_router(router, prefix="/api")
    app.include_router(banking_router, prefix="/api")

    return app
