import os
import subprocess
import tempfile
from pathlib import Path

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


def _extract_frame(video_path: str, frame_path: str, timestamp: float) -> bool:
    try:
        result = subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-ss",
                f"{timestamp:.3f}",
                "-i",
                video_path,
                "-vframes",
                "1",
                frame_path,
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        return result.returncode == 0 and os.path.exists(frame_path)
    except Exception:
        return False


def _classify_frame(frame_path: str) -> tuple[bool, float]:
    if nude_classifier is None:
        return True, 0.0

    result = nude_classifier.classify(frame_path)
    data = result.get(frame_path, {})
    unsafe_score = float(data.get("unsafe", 0.0))
    return unsafe_score < 0.5, unsafe_score


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


def moderate_video_content_with_ai(
    video_path: str,
    sample_count: int = 5,
) -> tuple[bool, str | None, float | None, int]:
    """
    Модерация по нескольким участкам видео.
    Возвращает: allowed, label, max_score, checked_frames.
    """
    if nude_classifier is None:
        return True, "skipped_no_local_model", 0.0, 0

    duration = get_video_duration(video_path)
    if not duration or duration <= 0:
        return True, "skipped_no_duration", 0.0, 0

    checked_frames = 0
    max_unsafe_score = 0.0

    # Проверяем равномерно по ролику, избегая самых краёв.
    timestamps = []
    for i in range(sample_count):
        ratio = (i + 1) / (sample_count + 1)
        timestamps.append(max(min(duration * ratio, duration - 0.2), 0.2))

    with tempfile.TemporaryDirectory(prefix="vh_moderation_") as tmp_dir:
        for index, ts in enumerate(timestamps, start=1):
            frame_path = str(Path(tmp_dir) / f"frame_{index}.jpg")
            if not _extract_frame(video_path, frame_path, ts):
                continue

            checked_frames += 1
            try:
                allowed, unsafe_score = _classify_frame(frame_path)
            except Exception:
                try:
                    current_app.logger.exception("Ошибка AI-модерации кадра")
                except RuntimeError:
                    pass
                continue

            max_unsafe_score = max(max_unsafe_score, unsafe_score)
            if not allowed:
                return False, "unsafe_video_segment", unsafe_score, checked_frames

    if checked_frames == 0:
        return True, "skipped_no_frames", 0.0, 0

    return True, "safe_video_segments", max_unsafe_score, checked_frames


def moderate_thumbnail_with_ai(thumb_path: str) -> tuple[bool, str | None, float | None]:
    if nude_classifier is None:
        return True, "skipped_no_local_model", 0.0

    try:
        allowed, unsafe_score = _classify_frame(thumb_path)
        label = "safe" if allowed else "unsafe"
        return allowed, label, unsafe_score
    except Exception:
        try:
            current_app.logger.exception("Ошибка во время модерации превью")
        except RuntimeError:
            pass
        return True, "moderation_error", 0.0
