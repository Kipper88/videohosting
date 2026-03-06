import os
import subprocess
from datetime import datetime

import onnxruntime
from flask import current_app
from nudenet import NudeClassifier

from config import BASE_DIR


MODEL_FILE_PATH = os.path.join(BASE_DIR, "models_ai", "classifier_model.onnx")


class MyNudeClassifier(NudeClassifier):
    def __init__(self, custom_model_path: str):
        # Библиотека по умолчанию лезет в ~/.NudeNet, мы принудительно используем наш путь
        if not os.path.exists(custom_model_path):
            raise FileNotFoundError(f"Файл модели не найден по пути: {custom_model_path}")

        # Напрямую инициализируем сессию ONNX вашим файлом
        self.nsfw_model = onnxruntime.InferenceSession(custom_model_path)


try:
    nude_classifier: MyNudeClassifier | None = MyNudeClassifier(MODEL_FILE_PATH)
except Exception as e:
    # Если модель не загрузилась (битый .onnx и т.п.) — логируем и отключаем модерацию
    try:
        current_app.logger.error("Ошибка загрузки NudeClassifier: %s", e)
    except RuntimeError:
        # current_app может быть недоступен на этапе импорта
        print(f"[NudeClassifier] Ошибка загрузки: {e}")
    nude_classifier = None


def allowed_file(filename: str) -> bool:
    allowed_extensions = {"mp4", "webm", "ogg", "mov"}
    return "." in filename and filename.rsplit(".", 1)[1].lower() in allowed_extensions


def get_video_duration(video_path: str) -> float | None:
    """Получить длительность видео в секундах через ffprobe."""
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                video_path,
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            return None
        duration_str = result.stdout.strip()
        return float(duration_str)
    except Exception:
        return None


def generate_thumbnail(video_path: str, thumb_path: str) -> bool:
    """
    Сгенерировать превью (кадр видео) с помощью ffmpeg.
    Берём кадр из середины ролика; если не получается — с 1-й секунды.
    """
    try:
        duration = get_video_duration(video_path)
        if duration and duration > 0 and duration != float("inf"):
            midpoint = max(min(duration / 2, duration - 0.5), 0.5)
            timestamp = str(midpoint)
        else:
            timestamp = "1.0"

        result = subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-ss",
                timestamp,
                "-i",
                video_path,
                "-vframes",
                "1",
                thumb_path,
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        return result.returncode == 0 and os.path.exists(thumb_path)
    except Exception:
        return False


def moderate_thumbnail_with_ai(thumb_path: str) -> tuple[bool, str | None, float | None]:
    """
    Проверить превью через локальную модель NudeNet.
    Возвращает (allowed, label, score), где score — вероятность небезопасного контента.

    Если модель не загрузилась или что-то идёт не так — не блокируем загрузку.
    """
    if nude_classifier is None:
        try:
            current_app.logger.info("Модерация пропущена: нет загруженной модели NudeNet")
        except RuntimeError:
            pass
        return True, "skipped_no_local_model", 0.0

    try:
        result = nude_classifier.classify(thumb_path)
        data = result.get(thumb_path, {})
        unsafe_score = float(data.get("unsafe", 0.0))
        safe_score = float(data.get("safe", 0.0))

        # Порог можно настроить (0.5 — достаточно строгий)
        allowed = unsafe_score < 0.5
        label = "unsafe" if not allowed else "safe"
        score = unsafe_score if not allowed else safe_score
        return allowed, label, score
    except Exception:
        try:
            current_app.logger.exception("Ошибка во время модерации превью")
        except RuntimeError:
            pass
        return True, "moderation_error", 0.0


