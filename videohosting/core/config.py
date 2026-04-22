import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
UPLOAD_FOLDER = BASE_DIR / "uploads"
DB_PATH = BASE_DIR / "app.db"

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key")

    SQLALCHEMY_DATABASE_URI = f"sqlite:///{DB_PATH}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = str(UPLOAD_FOLDER)

    VIDEO_STORAGE = os.getenv("VIDEO_STORAGE", "local")

    S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME")
    S3_REGION = os.getenv("S3_REGION")
    S3_ENDPOINT_URL = os.getenv("S3_ENDPOINT_URL")
    S3_BASE_URL = os.getenv("S3_BASE_URL")

    MANUAL_MODERATION = os.getenv("MANUAL_MODERATION", "true").lower() in {"1", "true", "yes", "on"}
