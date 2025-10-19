"""Module entrypoint for `python -m backend`.

Purpose: Delegate to `backend.server.main` to start the WebSocket server.
"""

from .server import main


if __name__ == "__main__":
    main()
