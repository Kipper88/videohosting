import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
DB_PATH = os.path.join(BASE_DIR, "app.db")

AI_MODELS_DIR = os.path.join(BASE_DIR, "models")
AI_MODEL_PATH_DEFAULT = os.path.join(AI_MODELS_DIR, "classifier_model.onnx")
AI_MODEL_PATH_FALLBACK = os.path.join(BASE_DIR, "models_ai", "classifier_model.onnx")


class Config:
    # Безопасный секрет берём из окружения, но оставляем дев-значение по умолчанию
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key")

    SQLALCHEMY_DATABASE_URI = f"sqlite:///{DB_PATH}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = UPLOAD_FOLDER

    # Хранилище видео: local или s3
    VIDEO_STORAGE = os.getenv("VIDEO_STORAGE", "local")  # "local" или "s3"

    # Настройки S3 (для масштабируемого хранилища)
    S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME")
    S3_REGION = os.getenv("S3_REGION")
    S3_ENDPOINT_URL = os.getenv("S3_ENDPOINT_URL")  # опционально (minio и т.п.)
    S3_BASE_URL = os.getenv("S3_BASE_URL")  # если есть CDN/CloudFront, иначе можно не задавать

    # AI-модерация
    AI_MODEL_PATH = os.getenv("AI_MODEL_PATH", AI_MODEL_PATH_DEFAULT)
    AI_MODEL_PATH_FALLBACK = os.getenv("AI_MODEL_PATH_FALLBACK", AI_MODEL_PATH_FALLBACK)
    AI_UNSAFE_THRESHOLD = float(os.getenv("AI_UNSAFE_THRESHOLD", "0.5"))

