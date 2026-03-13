from __future__ import annotations

from typing import Any

from polymarket_fair_value_engine.config import AuthConfig, EndpointConfig
from polymarket_fair_value_engine.types import OrderSide, QuoteIntent

try:
    from py_clob_client.client import ClobClient
    from py_clob_client.clob_types import OrderArgs
    from py_clob_client.order_builder.constants import BUY, SELL
except Exception:  # pragma: no cover - optional dependency
    ClobClient = None
    OrderArgs = None
    BUY = None
    SELL = None


class PolymarketLiveExecutor:
    def __init__(self, endpoints: EndpointConfig, auth: AuthConfig) -> None:
        self.endpoints = endpoints
        self.auth = auth
        self.client = self._build_client()

    def _build_client(self) -> Any:
        if ClobClient is None:
            raise RuntimeError("py-clob-client is required for live execution.")
        if not self.auth.private_key:
            raise RuntimeError("POLY_PRIVATE_KEY is required for live execution.")

        client = ClobClient(
            host=self.endpoints.clob_url,
            key=self.auth.private_key,
            chain_id=self.endpoints.chain_id,
            signature_type=self.auth.signature_type,
            funder=self.auth.funder or None,
        )
        if self.auth.api_key and self.auth.api_secret and self.auth.api_passphrase:
            client.set_api_creds(
                {
                    "key": self.auth.api_key,
                    "secret": self.auth.api_secret,
                    "passphrase": self.auth.api_passphrase,
                }
            )
        else:
            creds = client.derive_api_key()
            client.set_api_creds(creds)
        return client

    def place_order(self, quote: QuoteIntent) -> dict[str, Any]:
        if OrderArgs is None or BUY is None or SELL is None:
            raise RuntimeError("py-clob-client order helpers are unavailable.")
        side = BUY if quote.side is OrderSide.BUY else SELL
        order = OrderArgs(price=quote.price, size=quote.size, side=side, token_id=quote.token_id)
        signed = self.client.create_order(order)
        response = self.client.post_order(signed, order_type="GTC")
        return response if isinstance(response, dict) else {"response": str(response)}

    def cancel_all(self) -> Any:
        if hasattr(self.client, "cancel_all"):
            return self.client.cancel_all()
        raise RuntimeError("The installed py-clob-client does not expose cancel_all().")

