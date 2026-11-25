
import os
from pathlib import Path


# Project directories
BASE_DIR = Path(__file__).resolve().parents[2]

DATA_DIR = BASE_DIR / "data"
INPUT_DIR = DATA_DIR / "inputs"
OUTPUT_DIR = DATA_DIR / "outputs"
DATABASE_DIR = DATA_DIR / "database"

DATABASE_PATH = DATABASE_DIR / "jobs.db"


# Coordinator configuration
COORDINATOR_HOST = os.getenv("COORDINATOR_HOST", "0.0.0.0")
COORDINATOR_PORT = int(os.getenv("COORDINATOR_PORT", "8000"))

COORDINATOR_URL = os.getenv(
    "COORDINATOR_URL", "http://127.0.0.1:8000"
)


# Worker configuration
WORKER_URLS = [
    url.strip().rstrip("/")
    for url in os.getenv(
        "WORKER_URLS", "http://127.0.0.1:8001"
    ).split(",")
    if url.strip()
]

WORKER_TIMEOUT = float(os.getenv("WORKER_TIMEOUT", "30"))


def initialize_directories():
    for directory in (INPUT_DIR, OUTPUT_DIR, DATABASE_DIR):
        directory.mkdir(parents=True, exist_ok=True)
