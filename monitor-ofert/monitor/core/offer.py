"""Ujednolicony format oferty zwracany przez każde źródło."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass
class Offer:
    source: str
    url: str
    title: str
    category: str = ""            # np. grunty, garaze
    location: str = ""            # tekst: miejscowość, gmina, powiat
    lat: float | None = None
    lon: float | None = None
    area_m2: float | None = None
    price: float | None = None
    start_price: float | None = None   # cena wywołania
    estimate: float | None = None      # suma oszacowania / wartość z operatu
    auction_date: str = ""             # YYYY-MM-DD
    signature: str = ""                # sygnatura (Km, GKm, numer obwieszczenia)
    description: str = ""
    extra: dict = field(default_factory=dict)  # wyniki analizy (flagi, ULDK, ocena)

    @property
    def key(self) -> str:
        return f"{self.source}|{self.url}"

    @property
    def text(self) -> str:
        return f"{self.title}\n{self.location}\n{self.description}"

    @property
    def effective_price(self) -> float | None:
        return self.start_price if self.start_price is not None else self.price

    def to_dict(self) -> dict:
        return asdict(self)
