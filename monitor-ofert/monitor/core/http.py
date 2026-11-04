"""Grzeczne pobieranie stron: User-Agent przeglądarki, opóźnienie, timeout, rozpoznawanie kodowania."""
from __future__ import annotations

import re
import time

import httpx

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36")


def decode(content: bytes, header_charset: str | None = None) -> str:
    """UTF-8 / ISO-8859-2 / Windows-1250: nagłówek, potem <meta charset>, potem próba UTF-8."""
    candidates = []
    if header_charset:
        candidates.append(header_charset)
    m = re.search(rb'<meta[^>]+charset=["\']?([\w-]+)', content[:4096], re.I)
    if m:
        candidates.append(m.group(1).decode("ascii", "ignore"))
    candidates += ["utf-8", "windows-1250"]
    for enc in candidates:
        try:
            return content.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
    return content.decode("utf-8", "replace")


class Http:
    def __init__(self, timeout: float = 30, delay_ms: int = 400):
        self.delay = delay_ms / 1000
        self._last = 0.0
        self.client = httpx.Client(
            timeout=timeout, follow_redirects=True,
            headers={"User-Agent": UA, "Accept-Language": "pl-PL,pl;q=0.9"},
        )

    def _wait(self, delay: float | None):
        d = self.delay if delay is None else delay
        sleep = self._last + d - time.monotonic()
        if sleep > 0:
            time.sleep(sleep)
        self._last = time.monotonic()

    def get(self, url: str, delay: float | None = None, **kw) -> httpx.Response:
        self._wait(delay)
        r = self.client.get(url, **kw)
        r.raise_for_status()
        return r

    def get_text(self, url: str, delay: float | None = None, **kw) -> str:
        r = self.get(url, delay, **kw)
        return decode(r.content, r.charset_encoding)

    def close(self):
        self.client.close()
