import os
import subprocess

import nudenet
from flask import current_app


NUDE_CLASSIFIER_CLS = getattr(nudenet, "NudeClassifier", None)

try:
    nude_classifier = NUDE_CLASSIFIER_CLS() if NUDE_CLASSIFIER_CLS else None
except Exception:
    nude_classifier = None


def allowed_file(filename: str) -> bool:
    allowed_extensions = {"mp4", "webm", "ogg", "mov"}
    return "." in filename and filename.rsplit(".", 1)[1].lower() in allowed_extensions


def get_video_duration(video_path: str) -> float | None:
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
        return float(result.stdout.strip())
    except Exception:
        return None


def generate_thumbnail(video_path: str, thumb_path: str) -> bool:
    try:
        duration = get_video_duration(video_path)
        timestamp = str(max(min(duration / 2, duration - 0.5), 0.5)) if duration else "1.0"

        result = subprocess.run(
            ["ffmpeg", "-y", "-ss", timestamp, "-i", video_path, "-vframes", "1", thumb_path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        return result.returncode == 0 and os.path.exists(thumb_path)
    except Exception:
        return False


def moderate_thumbnail_with_ai(thumb_path: str) -> tuple[bool, str | None, float | None]:
    if nude_classifier is None:
        return True, "skipped_no_local_model", 0.0

    try:
        result = nude_classifier.classify(thumb_path)
        data = result.get(thumb_path, {})
        unsafe_score = float(data.get("unsafe", 0.0))
        safe_score = float(data.get("safe", 0.0))

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
