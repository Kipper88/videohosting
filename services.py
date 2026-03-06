import os
import subprocess
import tempfile
from pathlib import Path

import nudenet

from config import Config


nude_model = None
model_mode = "none"

UNSAFE_DETECTOR_LABELS = {
    "FEMALE_BREAST_EXPOSED",
    "FEMALE_GENITALIA_EXPOSED",
    "MALE_GENITALIA_EXPOSED",
    "ANUS_EXPOSED",
    "BUTTOCKS_EXPOSED",
}


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
        model_mode = "classifier"
        return classifier_cls(model_path=model_path) if model_path else classifier_cls()

    detector_cls = getattr(nudenet, "NudeDetector", None)
    if detector_cls:
        model_mode = "detector"
        return detector_cls(model_path=model_path) if model_path else detector_cls()

    model_mode = "none"
    return None


nude_model = _init_nude_model()


def allowed_file(filename: str) -> bool:
    allowed_extensions = {"mp4", "webm", "ogg", "mov"}
    return "." in filename and filename.rsplit(".", 1)[1].lower() in allowed_extensions


def get_video_duration(video_path: str) -> float | None:
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

    out = result.stdout.strip()
    return float(out) if out else None


def _extract_frame(video_path: str, frame_path: str, timestamp: float) -> bool:
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
            label = str(detection.get("class", "")).upper()

            # Для NudeDetector учитываем только действительно небезопасные классы,
            # иначе безопасные детекции (например лицо) могут отклонять любой ролик.
            if label in UNSAFE_DETECTOR_LABELS:
                max_score = max(max_score, score)

        return max_score < threshold, max_score

    return True, 0.0


def generate_thumbnail(video_path: str, thumb_path: str) -> bool:
    duration = get_video_duration(video_path)
    timestamp = str(max(min(duration / 2, duration - 0.5), 0.5)) if duration else "1.0"

    result = subprocess.run(
        ["ffmpeg", "-y", "-ss", timestamp, "-i", video_path, "-vframes", "1", thumb_path],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return result.returncode == 0 and os.path.exists(thumb_path)


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
            allowed, unsafe_score = _classify_frame(frame_path)
            max_unsafe_score = max(max_unsafe_score, unsafe_score)
            if not allowed:
                return False, "unsafe_video_segment", unsafe_score, checked_frames

    if checked_frames == 0:
        return True, "skipped_no_frames", 0.0, 0

    return True, "safe_video_segments", max_unsafe_score, checked_frames


def moderate_thumbnail_with_ai(thumb_path: str) -> tuple[bool, str | None, float | None]:
    if nude_model is None:
        return True, "skipped_no_local_model", 0.0

    allowed, unsafe_score = _classify_frame(thumb_path)
    label = "safe" if allowed else "unsafe"
    return allowed, label, unsafe_score


def allowed_image_file(filename: str) -> bool:
    allowed_extensions = {"jpg", "jpeg", "png", "webp"}
    return "." in filename and filename.rsplit(".", 1)[1].lower() in allowed_extensions
