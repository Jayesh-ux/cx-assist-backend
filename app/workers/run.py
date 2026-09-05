"""Standalone background worker entrypoint (used by the `worker` compose service).
Consumes the Redis job queue and retries failures, separate from the API process."""
from __future__ import annotations

import asyncio

from app.workers.jobs import worker_loop


async def main() -> None:
    stop_event = asyncio.Event()
    print("CX Assist worker started")
    try:
        await worker_loop(stop_event)
    except asyncio.CancelledError:
        pass
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    asyncio.run(main())