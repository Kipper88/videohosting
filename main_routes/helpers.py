from __future__ import annotations

import asyncio
import os


async def remove_files(*paths: str) -> None:
    async def _remove(path: str):
        if path and os.path.exists(path):
            try:
                os.remove(path)
            except OSError:
                pass

    await asyncio.gather(*[_remove(path) for path in paths])
