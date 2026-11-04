"""Pomocnicze: pobranie strony (HTTP albo przeglądarka), zapis surowych danych w trybie --probe."""
from __future__ import annotations

import re

from bs4 import BeautifulSoup

from monitor.core.browser import dump_json


def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:80]


def get_page(url: str, cfg: dict, ctx, tag: str) -> str:
    if cfg.get("render") == "browser":
        if ctx.browser is None:
            raise RuntimeError("źródło wymaga przeglądarki (uruchom z Playwright)")
        html, captured = ctx.browser.render(url, capture_json=ctx.probe_dir is not None)
        if ctx.probe_dir and captured:
            (ctx.probe_dir / f"{slug(tag)}.json").write_text(dump_json(captured), encoding="utf-8")
    else:
        html = ctx.http.get_text(url, delay=cfg.get("delay_ms", 400) / 1000)
    if ctx.probe_dir:
        (ctx.probe_dir / f"{slug(tag)}.html").write_text(html, encoding="utf-8")
    return html


def page_text(html: str, limit: int = 6000) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for t in soup(["script", "style", "noscript", "nav", "header", "footer", "svg"]):
        t.decompose()
    return re.sub(r"\s+", " ", soup.get_text(" ")).strip()[:limit]
