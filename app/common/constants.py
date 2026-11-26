
from enum import Enum


class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ImageOperation(str, Enum):
    GRAYSCALE = "grayscale"
    BLUR = "blur"
    THRESHOLD = "threshold"
    CANNY = "canny"


MAX_IMAGE_BYTES = 15 * 1024 * 1024
