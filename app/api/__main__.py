from __future__ import annotations

import sys


def main() -> int:
    try:
        import uvicorn
    except ImportError:
        print(
            'HTTP API requires extra "api". Install with: pip install -e ".[api]" or pip install -e ".[all]"',
            file=sys.stderr,
        )
        return 1

    from app.config.settings import Settings
    from app.log_setup import setup_logging

    settings = Settings()
    setup_logging(settings.log_level)
    uvicorn.run(
        "app.api.app:app",
        host=settings.api_host,
        port=settings.api_port,
        workers=1,
        timeout_keep_alive=300,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
