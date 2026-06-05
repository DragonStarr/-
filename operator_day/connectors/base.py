from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from operator_day.domain import Platform, ProductSnapshot, ReviewSnapshot


@dataclass(frozen=True)
class ConnectorHealth:
    platform: Platform
    mode: str
    capabilities: dict[str, str]
    limitations: tuple[str, ...] = ()


class MarketplaceClient(ABC):
    platform: Platform

    @abstractmethod
    async def validate_capabilities(self) -> ConnectorHealth:
        """Return connector health, available read/write scopes and live limitations."""

    @abstractmethod
    async def list_products(self) -> list[ProductSnapshot]:
        """Return normalized product snapshots from the marketplace."""

    @abstractmethod
    async def list_reviews(self) -> list[ReviewSnapshot]:
        """Return normalized pending reviews/questions."""

    @abstractmethod
    async def send_review_answer(self, review_id: str, answer: str) -> dict[str, str]:
        """Send or emulate a review answer. Real clients must be idempotent."""
