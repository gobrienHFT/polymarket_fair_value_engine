from __future__ import annotations

from dataclasses import dataclass
from time import monotonic
from typing import Generic, TypeVar

T = TypeVar("T")


@dataclass
class _CacheItem(Generic[T]):
    value: T
    expires_at: float


class TTLCache(Generic[T]):
    def __init__(self, ttl_seconds: float) -> None:
        self.ttl_seconds = ttl_seconds
        self._items: dict[str, _CacheItem[T]] = {}

    def get(self, key: str) -> T | None:
        item = self._items.get(key)
        if item is None:
            return None
        if monotonic() >= item.expires_at:
            self._items.pop(key, None)
            return None
        return item.value

    def set(self, key: str, value: T) -> None:
        self._items[key] = _CacheItem(value=value, expires_at=monotonic() + self.ttl_seconds)

