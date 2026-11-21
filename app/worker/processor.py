# This module provides image-processing functions using OpenCV and NumPy. 
# It includes operations such as grayscale conversion, Gaussian blur, thresholding, and edge detection. 
# Each function validates the input image and parameters before processing.

from collections.abc import Callable
import cv2
import numpy as np

# Ensure the input is a valid, non-empty NumPy image array.
def _validate_image(image: np.ndarray) -> None:          
    if not isinstance(image, np.ndarray) or image.size == 0:
        raise ValueError("Input must be a non-empty image array.")

# Convert a BGR/BGRA image to grayscale (returns as-is if already grayscale)
def convert_to_grayscale(image: np.ndarray) -> np.ndarray:
    _validate_image(image)

    if image.ndim == 2:                                                              
        return image
    if image.shape[2] == 4:
        return cv2.cvtColor(image, cv2.COLOR_BGRA2GRAY)

    return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

# Apply Gaussian blur to reduce image noise.
def apply_gaussian_blur(image: np.ndarray, kernel_size: int = 5) -> np.ndarray:
    _validate_image(image)

    if (
        isinstance(kernel_size, bool)
        or not isinstance(kernel_size, int)
        or kernel_size <= 0
        or kernel_size % 2 == 0
    ):
        raise ValueError("Kernel size must be a positive odd integer.")

    return cv2.GaussianBlur(image, (kernel_size, kernel_size), 0)


# Convert an image to binary black and white.
def apply_threshold(
    image: np.ndarray,
    threshold_value: int = 127,
    max_value: int = 255,
) -> np.ndarray:
    gray = convert_to_grayscale(image)
    _, result = cv2.threshold(gray, threshold_value, max_value, cv2.THRESH_BINARY)
    return result

# Detect edges in an image using the Canny edge detection algorithm.
def detect_edges(
    image: np.ndarray,
    threshold1: int = 100,
    threshold2: int = 200,
) -> np.ndarray:
    gray = convert_to_grayscale(image)
    return cv2.Canny(gray, threshold1, threshold2)

# Mapping of operation names to their corresponding processing functions.
OPERATIONS: dict[str, Callable[..., np.ndarray]] = {
    "grayscale": convert_to_grayscale,
    "blur": apply_gaussian_blur,
    "threshold": apply_threshold,
    "canny": detect_edges,
}

# Execute the requested image-processing operation based on the provided operation name and parameters.
def process_image(
    image: np.ndarray,
    operation: str,
    **params,
) -> np.ndarray:
    _validate_image(image)

    op_key = operation.strip().lower() if isinstance(operation, str) else ""
    if op_key not in OPERATIONS:
        supported = ", ".join(OPERATIONS.keys())
        raise ValueError(
            f"Unsupported operation: {operation!r}. Supported operations: {supported}"
        )

    return OPERATIONS[op_key](image, **params)