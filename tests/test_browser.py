"""The browser path: `FrostBrowserPage` over a rendered DOM, checked against `FrostPage` over bytes.

Two layers, because they fail differently:

* **Offline (always runs).** The DOM is simulated — the storefront's own `_HYDRATE_JS` is applied in
  Python — so the *response contract* is exercised with no browser: same `ProductFields`, one input
  `HttpResponse`, the other `BrowserResponse`, and every wire-visible column must match.
* **Real browser (requires the `browser` extra).** Playwright renders the page directly, and the client-rendered columns must come out non-empty. This is
  what catches a `BrowserResponse` the demo builds wrongly, which the simulation cannot.

    uv run pytest -m "not browser"                     # offline layer only
    uv sync --extra browser && uv run playwright install chromium
    uv run pytest                                     # both layers
"""
from __future__ import annotations

import asyncio

import attrs
import pytest
from web_poet import BrowserHtml, BrowserResponse, HttpResponse

from demo.browser import ProductBrowserPage
from demo.commerce import ProductPage
from demo.site import catalog, render

PID = 7
HOST = "testserver"


def _html(pid=PID):
    return render.product_page(pid).replace("{HOST}", HOST)


def _url(pid=PID):
    return f"http://{HOST}{catalog.product_url(pid)}"


def _hydrated(html: str, pid=PID) -> str:
    """What a browser would leave in the DOM: `render._HYDRATE_JS` applied by hand.

    Deliberately hand-applied rather than mocked out — the assertion below is that Frostwork reads
    whatever the browser put there, so the fixture has to actually differ from the served bytes."""
    d = render._delivery(catalog.product(pid))
    filled = (
        f'<div class="delivery-estimate" id="delivery" data-hydrate="delivery" data-hydrated="1">'
        f'<span class="delivery-window">{d["window"]}</span>'
        f'<span class="delivery-cost" data-free="{str(d["free"]).lower()}">{d["cost"]}</span></div>'
    )
    served = '<div class="delivery-estimate" id="delivery" data-hydrate="delivery"></div>'
    assert served in html, "the storefront no longer serves #delivery empty"
    return html.replace(served, filled)


def _item(page):
    return attrs.asdict(asyncio.run(page.to_item()))


# ------------------------------------------------------------------ offline: the response contract

def test_served_html_leaves_the_client_rendered_block_empty():
    """The premise of the whole exercise: these two columns are unreachable without a browser."""
    direct = ProductPage(response=HttpResponse(_url(), body=_html().encode(), encoding="utf-8"))
    unrendered = ProductBrowserPage(response=BrowserResponse(url=_url(), html=BrowserHtml(_html())))
    assert unrendered.delivery_window is None
    assert unrendered.delivery_cost is None
    assert "delivery_window" not in ProductPage.frost_schema()["fields"]
    assert direct.name == catalog.product(PID)["name"]      # the rest of the page still extracts


def test_browser_dom_yields_the_client_rendered_columns():
    truth = render._delivery(catalog.product(PID))
    page = ProductBrowserPage(response=BrowserResponse(url=_url(), html=BrowserHtml(_hydrated(_html()))))
    assert page.delivery_window == truth["window"]
    assert page.delivery_cost == truth["cost"]


def test_both_response_contracts_agree_on_every_wire_visible_field():
    """One `ProductFields` schema, two inputs (`HttpResponse` bytes vs a `BrowserResponse` DOM
    snapshot): the fields the server actually sent must come out identical."""
    direct = _item(ProductPage(response=HttpResponse(_url(), body=_html().encode(), encoding="utf-8")))
    browser = _item(ProductBrowserPage(
        response=BrowserResponse(url=_url(), html=BrowserHtml(_hydrated(_html())))))
    assert direct == browser


def test_browser_page_is_one_streaming_pass(monkeypatch):
    """Including the client-rendered columns — the browser base changes the input, not the engine."""
    calls = {"n": 0}
    real = ProductBrowserPage._frostwork_plan

    class CountingPlan:
        def extract_grouped(self, *a, **k):
            calls["n"] += 1
            return real.extract_grouped(*a, **k)

    monkeypatch.setattr(ProductBrowserPage, "_frostwork_plan", CountingPlan())
    page = ProductBrowserPage(response=BrowserResponse(url=_url(), html=BrowserHtml(_hydrated(_html()))))
    assert asyncio.run(page.to_item()).name == catalog.product(PID)["name"]
    assert page.delivery_window
    assert calls["n"] == 1


# ------------------------------------------------------------------ the scrapy-poet provider itself

def test_provider_builds_both_browser_inputs_from_a_scrapy_response():
    """`BrowserResponseProvider` is the piece scrapy-poet does not ship, so it gets its own test."""
    from scrapy.http import HtmlResponse, Request

    from demo.browser import BrowserResponseProvider

    rendered = _hydrated(_html())
    scrapy_response = HtmlResponse(url=_url(), body=rendered.encode(), encoding="utf-8",
                                   request=Request(_url()), status=200)
    provider = BrowserResponseProvider(None)

    (resp,) = provider([BrowserResponse], scrapy_response)
    assert isinstance(resp, BrowserResponse)
    assert str(resp.url) == _url()
    assert resp.status == 200
    assert 'data-hydrated="1"' in str(resp.html)

    (html,) = provider([BrowserHtml], scrapy_response)
    assert isinstance(html, BrowserHtml)

    # Order follows `to_provide`, since the injector zips the two together.
    both = provider([BrowserHtml, BrowserResponse], scrapy_response)
    assert [type(x) for x in both] == [BrowserHtml, BrowserResponse]

    # …and the page object built from it sees the client-rendered columns.
    page = ProductBrowserPage(response=resp)
    assert page.delivery_window == render._delivery(catalog.product(PID))["window"]


# ------------------------------------------------------- real browser: needs the `browser` extra

@pytest.mark.browser
def test_real_chromium_render_reaches_frostwork():
    """Render the page in Chromium and scan its actual DOM.

    The offline layer above hand-applies `_HYDRATE_JS`; this asserts a real browser agrees — that the
    selectors match what Chromium actually built, and that `render._delivery` is not just checking the
    fixture against itself. The scrapy-playwright wiring on top of this is covered by
    `tests/test_crawls.py` with a real browser spider and exported items."""
    pytest.importorskip("playwright", reason="needs `uv sync --extra browser`")
    import threading

    from playwright.sync_api import sync_playwright

    from demo.site.server import make_server

    httpd = make_server(port=0)
    port = httpd.server_address[1]
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            try:
                bpage = browser.new_page()
                bpage.goto(f"http://127.0.0.1:{port}{catalog.product_url(PID)}", wait_until="load")
                dom = bpage.content()
                url = bpage.url
            finally:
                browser.close()
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=5)

    truth = render._delivery(catalog.product(PID))
    page = ProductBrowserPage(response=BrowserResponse(url=url, html=BrowserHtml(dom)))
    assert page.delivery_window == truth["window"]
    assert page.delivery_cost == truth["cost"]
    # Chromium's serialisation differs from ours (attribute order, injected tags), so the wire-visible
    # columns are checked for VALUE equality with the direct path, on the same rendered document.
    direct = _item(ProductPage(response=HttpResponse(_url(), body=_html().encode(), encoding="utf-8")))
    browser_item = _item(page)
    assert browser_item["name"] == direct["name"]
    assert browser_item["price"] == direct["price"]
    assert browser_item["sku"] == direct["sku"]
    assert browser_item["breadcrumbs"] == direct["breadcrumbs"]
    assert browser_item["additionalProperties"] == direct["additionalProperties"]
    assert len(browser_item["images"]) == len(direct["images"])
