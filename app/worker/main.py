from contextlib import asynccontextmanager
import os
import socket
import cv2
from fastapi import FastAPI
from app.worker.routes import router

# Worker ID is a combination of the node's hostname and the process ID, 
# ensuring uniqueness across distributed systems.
NODE_ID = os.getenv("WORKER_ID", socket.gethostname())
WORKER_ID = f"{NODE_ID}-{os.getpid()}"

# The lifespan context manager is used to manage the startup and shutdown events of the FastAPI application.
@asynccontextmanager
async def lifespan(app: FastAPI):
    cv2.setNumThreads(1)
    print(f"[{WORKER_ID}] Worker started.")

    yield 
    print(f"[{WORKER_ID}] Worker shutting down.")

# The FastAPI application instance is created with metadata and the lifespan context manager.
app = FastAPI(
    title="Distributed Image Processing - Worker",
    description="Worker service for image processing tasks.",
    version="1.0.0",
    lifespan=lifespan
)

# The worker ID is stored in the application state for easy access throughout the application.
app.state.worker_id = WORKER_ID

# The router containing the worker's API endpoints is included in the FastAPI application.
app.include_router(router)

# The health check endpoint provides a simple way to verify that the worker service is running and healthy.
@app.get("/health")
def health_check():
    return {
        "status": "Very well, I'm healthy!",
        "service": "Worker",
        "worker_id": WORKER_ID,
    }
