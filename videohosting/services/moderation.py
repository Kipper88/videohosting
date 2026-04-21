from __future__ import annotations

import asyncio
import os
import tempfile
from pathlib import Path

import nudenet

from videohosting.core.config import Config
from videohosting.services.media import extract_frame, get_video_duration

UNSAFE_DETECTOR_LABELS = {
    "FEMALE_BREAST_EXPOSED",
    "FEMALE_GENITALIA_EXPOSED",
    "MALE_GENITALIA_EXPOSED",
    "ANUS_EXPOSED",
    "BUTTOCKS_EXPOSED",
}

nude_model = None
model_mode = "none"


def _resolve_model_path() -> str | None:
    for candidate in (Config.AI_MODEL_PATH, Config.AI_MODEL_PATH_FALLBACK):
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


def _classify_frame_sync(frame_path: str) -> tuple[bool, float]:
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
            if label in UNSAFE_DETECTOR_LABELS:
                max_score = max(max_score, score)
        return max_score < threshold, max_score

    return True, 0.0


async def moderate_video_content_with_ai(video_path: str, sample_count: int = 5) -> tuple[bool, str | None, float | None, int]:
    if nude_model is None:
        return True, "skipped_no_local_model", 0.0, 0

    duration = await get_video_duration(video_path)
    if not duration or duration <= 0:
        return True, "skipped_no_duration", 0.0, 0

    checked_frames = 0
    max_unsafe_score = 0.0
    timestamps = [max(min(duration * (i + 1) / (sample_count + 1), duration - 0.2), 0.2) for i in range(sample_count)]

    with tempfile.TemporaryDirectory(prefix="vh_moderation_") as tmp_dir:
        for index, ts in enumerate(timestamps, start=1):
            frame_path = str(Path(tmp_dir) / f"frame_{index}.jpg")
            if not await extract_frame(video_path, frame_path, ts):
                continue

            checked_frames += 1
            allowed, unsafe_score = await asyncio.to_thread(_classify_frame_sync, frame_path)
            max_unsafe_score = max(max_unsafe_score, unsafe_score)
            if not allowed:
                return False, "unsafe_video_segment", unsafe_score, checked_frames

    if checked_frames == 0:
        return True, "skipped_no_frames", 0.0, 0

    return True, "safe_video_segments", max_unsafe_score, checked_frames


async def moderate_thumbnail_with_ai(thumb_path: str) -> tuple[bool, str | None, float | None]:
    if nude_model is None:
        return True, "skipped_no_local_model", 0.0

    allowed, unsafe_score = await asyncio.to_thread(_classify_frame_sync, thumb_path)
    return allowed, ("safe" if allowed else "unsafe"), unsafe_score


nude_model = _init_nude_model()
