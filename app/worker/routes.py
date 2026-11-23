import cv2
import numpy as np
from fastapi import APIRouter, File, HTTPException, Query, Request, Response, UploadFile
from app.worker.processor import process_image

# Define the API router for worker operations with a prefix and tags for documentation.
router = APIRouter(prefix="/worker", tags=["Worker"])

# Define a maximum image size limit for uploads to prevent excessive memory usage.
MAX_IMAGE_BYTES = 15 * 1024 * 1024  # 15 MB limit per upload

# Define the endpoint to retrieve (GET) worker information, including its ID and status.
@router.get("/info")
def get_worker_info(request: Request):
    return {
        "worker_id": request.app.state.worker_id,
        "service": "worker",
        "status": "ready",
    }


# Define the endpoint to process uploaded (POST) images with specified operations.
@router.post("/process")
def process_uploaded_image(
    request: Request,
    file: UploadFile = File(...),
    operation: str = Query(...),
):
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(
            status_code=400,
            detail="Uploaded file must be an image.",
        )

    # Read up to MAX_IMAGE_BYTES + 1 to reject oversized files without loading gigabytes into RAM
    image_bytes = file.file.read(MAX_IMAGE_BYTES + 1)

    if not image_bytes:
        raise HTTPException(
            status_code=400,
            detail="Uploaded image is empty.",
        )

    if len(image_bytes) > MAX_IMAGE_BYTES:
        raise HTTPException(
            status_code=413,
            detail="Image exceeds the 15 MB size limit.",
        )

    image_array = np.frombuffer(image_bytes, dtype=np.uint8)
    image = cv2.imdecode(image_array, cv2.IMREAD_UNCHANGED)

    if image is None:
        raise HTTPException(
            status_code=400,
            detail="Could not decode the uploaded image.",
        )

    try:
        result = process_image(image, operation)
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    success, encoded_image = cv2.imencode(".png", result)

    if not success:
        raise HTTPException(
            status_code=500,
            detail="Could not encode the processed image.",
        )

    return Response(
        content=encoded_image.tobytes(),
        media_type="image/png",
        headers={
            "X-Worker-ID": request.app.state.worker_id,
            "X-Processing-Operation": operation.strip(),
        },
    )