from fastapi import FastAPI
from app.worker.routes import router

app = FastAPI(
    title="Distributed Image Processing - Worker",
    description="Worker service for image processing tasks",
    version="1.0.0"
)

app.include_router(router)


@app.get("/health")
def health_check():
    """Check whether the worker service is running."""
    return {"status": "healthy"}
