import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
UPLOAD_FOLDER = BASE_DIR / "uploads"
DB_PATH = BASE_DIR / "app.db"

AI_MODELS_DIR = BASE_DIR / "models"
AI_MODEL_PATH_DEFAULT = AI_MODELS_DIR / "classifier_model.onnx"
AI_MODEL_PATH_FALLBACK = BASE_DIR / "models_ai" / "classifier_model.onnx"


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

    AI_MODEL_PATH = os.getenv("AI_MODEL_PATH", str(AI_MODEL_PATH_DEFAULT))
    AI_MODEL_PATH_FALLBACK = os.getenv("AI_MODEL_PATH_FALLBACK", str(AI_MODEL_PATH_FALLBACK))
    AI_UNSAFE_THRESHOLD = float(os.getenv("AI_UNSAFE_THRESHOLD", "0.5"))
