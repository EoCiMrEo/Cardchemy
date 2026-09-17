"""Database-readiness probe for non-HTTP application containers."""

import argparse
import asyncio
import sys
import urllib.request

from app.database import check_database_readiness, close_database
from app.config import get_settings
from app.services.operations import check_local_worker_health


async def run_healthcheck() -> None:
    try:
        await check_database_readiness()
    finally:
        await close_database()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check application readiness")
    parser.add_argument(
        "--url",
        help="Probe an HTTP readiness URL instead of connecting to the database directly",
    )
    parser.add_argument("--worker-kind", choices=["generation", "email"], help="Also require this container's worker loop to be fresh")
    arguments = parser.parse_args(argv)
    try:
        if arguments.url:
            with urllib.request.urlopen(arguments.url, timeout=5) as response:
                if response.status != 200:
                    return 1
        else:
            if arguments.worker_kind:
                check_local_worker_health(arguments.worker_kind, get_settings().worker_health_stale_seconds)
            asyncio.run(run_healthcheck())
    except Exception:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
