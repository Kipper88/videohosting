from __future__ import annotations

import asyncio
from pathlib import Path


async def remove_files(*paths: str) -> None:
    async def _remove(path: str):
        if not path:
            return
        candidate = Path(path)
        if candidate.exists():
            try:
                await asyncio.to_thread(candidate.unlink)
            except OSError:
                pass

    await asyncio.gather(*(_remove(path) for path in paths))
