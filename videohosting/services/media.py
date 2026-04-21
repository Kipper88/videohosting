from __future__ import annotations

import asyncio
import os


async def get_video_duration(video_path: str) -> float | None:
    process = await asyncio.create_subprocess_exec(
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        video_path,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
    )
    stdout, _ = await process.communicate()
    if process.returncode != 0:
        return None

    out = stdout.decode().strip()
    return float(out) if out else None


async def extract_frame(video_path: str, frame_path: str, timestamp: float) -> bool:
    process = await asyncio.create_subprocess_exec(
        "ffmpeg",
        "-y",
        "-ss",
        f"{timestamp:.3f}",
        "-i",
        video_path,
        "-vframes",
        "1",
        frame_path,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )
    await process.communicate()
    return process.returncode == 0 and os.path.exists(frame_path)


async def generate_thumbnail(video_path: str, thumb_path: str) -> bool:
    duration = await get_video_duration(video_path)
    timestamp = str(max(min(duration / 2, duration - 0.5), 0.5)) if duration else "1.0"

    process = await asyncio.create_subprocess_exec(
        "ffmpeg",
        "-y",
        "-ss",
        timestamp,
        "-i",
        video_path,
        "-vframes",
        "1",
        thumb_path,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )
    await process.communicate()
    return process.returncode == 0 and os.path.exists(thumb_path)
