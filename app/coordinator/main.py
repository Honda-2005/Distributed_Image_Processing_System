
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.common.config import initialize_directories
from app.coordinator.routes import router


@asynccontextmanager
async def lifespan(app: FastAPI):
    initialize_directories()

    print("[COORDINATOR] Service started.")

    yield

    print("[COORDINATOR] Service shutting down.")


app = FastAPI(
    title="Distributed Image Processing - Coordinator",
    description=(
        "Central coordinator responsible for job submission, "
        "lifecycle management and distributed processing."
    ),
    version="1.0.0",
    lifespan=lifespan,
)


app.include_router(router)


@app.get("/")
def root():
    return {
        "service": "coordinator",
        "version": "1.0.0",
        "status": "running",
        "documentation": "/docs",
    }


@app.get("/health")
def health_check():
    return {
        "service": "coordinator",
        "status": "healthy",
    }
