
import mimetypes
from pathlib import Path

import httpx

from app.common.config import WORKER_TIMEOUT
from app.common.constants import ImageOperation


class WorkerClient:

    def __init__(self, worker_url: str):
        self.worker_url = worker_url.rstrip("/")

    def health_check(self) -> dict:
        response = httpx.get(
            f"{self.worker_url}/health",
            timeout=WORKER_TIMEOUT,
        )

        response.raise_for_status()
        return response.json()

    def process_image(
        self,
        input_path: Path,
        operation: ImageOperation,
    ) -> tuple[bytes, str]:

        content_type = (
            mimetypes.guess_type(input_path.name)[0]
            or "image/octet-stream"
        )

        with input_path.open("rb") as image_file:

            response = httpx.post(
                f"{self.worker_url}/worker/process",
                params={"operation": operation.value},
                files={
                    "file": (
                        input_path.name,
                        image_file,
                        content_type,
                    )
                },
                timeout=WORKER_TIMEOUT,
            )

        response.raise_for_status()

        if not response.content.startswith(b"\x89PNG\r\n\x1a\n"):
            raise ValueError("Worker returned an invalid PNG result.")

        worker_id = response.headers.get("X-Worker-ID")

        if not worker_id:
            raise ValueError("Worker identification is missing.")

        return response.content, worker_id
