"""Playwright (Chromium) tylko dla stron w JavaScript. Import leniwy: bez Playwright reszta działa."""
from __future__ import annotations

import json


class Browser:
    def __init__(self):
        self._pw = None
        self._browser = None

    def _ensure(self):
        if self._browser is None:
            from playwright.sync_api import sync_playwright  # noqa: PLC0415
            self._pw = sync_playwright().start()
            self._browser = self._pw.chromium.launch()

    def render(self, url: str, wait_ms: int = 4000, capture_json: bool = False):
        """Zwraca (html, lista_odpowiedzi_json). JSON przydaje się do rozpoznania wewnętrznego API strony."""
        self._ensure()
        page = self._browser.new_page(locale="pl-PL")
        captured: list[dict] = []
        if capture_json:
            def on_response(resp):
                if "json" in (resp.headers.get("content-type") or ""):
                    try:
                        captured.append({"url": resp.url, "body": resp.json()})
                    except Exception:  # noqa: BLE001
                        pass
            page.on("response", on_response)
        try:
            page.goto(url, wait_until="networkidle", timeout=45_000)
        except Exception:  # noqa: BLE001  (networkidle bywa nieosiągalne; bierzemy to, co jest)
            pass
        page.wait_for_timeout(wait_ms)
        html = page.content()
        page.close()
        return html, captured

    def close(self):
        if self._browser:
            self._browser.close()
            self._pw.stop()


def dump_json(captured: list[dict]) -> str:
    return json.dumps(captured, ensure_ascii=False, indent=1)[:2_000_000]
