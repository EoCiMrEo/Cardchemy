"""Command-line entry point for durable transactional email delivery."""

import asyncio
import logging
import signal

from app.config import get_settings
from app.database import verify_database_revision
from app.workers.email import EmailWorker


async def run_email_worker() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    settings = get_settings()
    settings.require_email_delivery_config()
    await verify_database_revision()
    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for signal_name in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(signal_name, stop_event.set)
        except NotImplementedError:
            signal.signal(signal_name, lambda *_: loop.call_soon_threadsafe(stop_event.set))
    await EmailWorker(settings=settings).run(stop_event)


if __name__ == "__main__":
    asyncio.run(run_email_worker())
