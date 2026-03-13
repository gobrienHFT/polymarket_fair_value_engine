from __future__ import annotations

import logging


LOGGER = logging.getLogger(__name__)


class ClobWsClient:
    """Future websocket adapter scaffold.

    The engine currently uses polling REST snapshots for deterministic paper trading.
    """

    def connect(self) -> None:
        LOGGER.info("CLOB websocket scaffold is not implemented yet")

