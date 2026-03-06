import os
import subprocess
import tempfile
from pathlib import Path

import nudenet
from flask import current_app

from config import Config


nude_model = None
model_mode = "none"


def _resolve_model_path() -> str | None:
    candidates = [Config.AI_MODEL_PATH, Config.AI_MODEL_PATH_FALLBACK]
    for candidate in candidates:
        if candidate and os.path.exists(candidate):
            return candidate
    return None


def _init_nude_model():
    global model_mode

    model_path = _resolve_model_path()

    classifier_cls = getattr(nudenet, "NudeClassifier", None)
    if classifier_cls:
        try:
            if model_path:
                model_mode = "classifier"
                return classifier_cls(model_path=model_path)
            model_mode = "classifier"
            return classifier_cls()
        except Exception:
            pass

    detector_cls = getattr(nudenet, "NudeDetector", None)
    if detector_cls:
        try:
            if model_path:
                model_mode = "detector"
                return detector_cls(model_path=model_path)
            model_mode = "detector"
            return detector_cls()
        except Exception:
            pass

    model_mode = "none"
    return None


try:
    nude_model = _init_nude_model()
except Exception:
    nude_model = None
    model_mode = "none"


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
    if nude_model is None:
        return True, 0.0

    threshold = Config.AI_UNSAFE_THRESHOLD

    if model_mode == "classifier":
        result = nude_model.classify(frame_path)
        data = result.get(frame_path, {})
        unsafe_score = float(data.get("unsafe", 0.0))
        return unsafe_score < threshold, unsafe_score

    if model_mode == "detector":
        detections = nude_model.detect(frame_path) or []
        max_score = 0.0
        for detection in detections:
            score = float(detection.get("score", 0.0))
            max_score = max(max_score, score)
        return max_score < threshold, max_score

    return True, 0.0


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
    if nude_model is None:
        return True, "skipped_no_local_model", 0.0, 0

    duration = get_video_duration(video_path)
    if not duration or duration <= 0:
        return True, "skipped_no_duration", 0.0, 0

    checked_frames = 0
    max_unsafe_score = 0.0
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
    if nude_model is None:
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
