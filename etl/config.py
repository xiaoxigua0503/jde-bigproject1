import logging
import os
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

def setup_logging(log_dir: Path, log_level: str) -> Path:
    """Log to both terminal and a timestamped file."""

    log_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = log_dir / f"youtube_etl_{timestamp}.log"

    logging.basicConfig(
        level=getattr(logging, log_level),
        format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(
                log_file,
                encoding="utf-8",
            ),
        ],
        force=True,
    )

    return log_file

load_dotenv()

YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")

GCP_PROJECT_ID = os.getenv("GCP_PROJECT_ID")
BQ_DATASET_ID = os.getenv("BQ_DATASET_ID")
BQ_TABLE_ID = os.getenv("BQ_TABLE_ID")

YOUTUBE_API_BASE_URL = "https://www.googleapis.com/youtube/v3"

YOUTUBE_CHANNELS_ENDPOINT = (
    f"{YOUTUBE_API_BASE_URL}/channels"
)

YOUTUBE_REQUEST_TIMEOUT = 30

YOUTUBE_BATCH_SIZE = 50

YOUTUBE_PROXY = "http://127.0.0.1:7897"

BQ_LOCATION = "VN"