"""Command-line entry point for durable Subject Ask AI answers."""

import asyncio
import logging
import signal

from app.observability import configure_logging


async def run_answer_worker() -> None:
    configure_logging()
    from app.config import get_settings
    settings = get_settings()
    configure_logging(settings.log_level)
    from app.database import close_database, verify_database_revision
    from app.workers.rag_answer import RagAnswerWorker
    try:
        settings.require_rag_answer_worker_config()
        await verify_database_revision()
        stop_event = asyncio.Event()
        loop = asyncio.get_running_loop()
        for signal_name in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(signal_name, stop_event.set)
            except NotImplementedError:
                signal.signal(signal_name, lambda *_: loop.call_soon_threadsafe(stop_event.set))
        await RagAnswerWorker(settings=settings).run(stop_event)
    finally:
        await close_database()


if __name__ == "__main__":
    try:
        asyncio.run(run_answer_worker())
    except Exception:
        logging.getLogger(__name__).critical("process_failed", extra={"kind": "answer"})
        raise SystemExit(1) from None
