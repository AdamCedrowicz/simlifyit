"""Źródła ofert. Każde źródło: fetch(cfg, ctx) -> list[Offer]. Typ źródła wybiera pole `type` w YAML."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class Ctx:
    http: object
    browser: object | None
    probe_dir: Path | None = None


def get_fetcher(kind: str):
    from monitor.sources import listing, otodom  # noqa: PLC0415
    return {"listing": listing.fetch, "otodom": otodom.fetch}[kind]
