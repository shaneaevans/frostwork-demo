"""The browser path: the SAME Frostwork schema, fed a rendered DOM instead of the bytes off the wire.

Frostwork ships two response contracts (`docs/PYTHON.md`, "Input"):

* `FrostPage` scans `response.body` — an `HttpResponse`, i.e. what the server actually sent.
* `FrostBrowserPage` scans `response.html` — a `BrowserResponse`, i.e. what a browser made of it.

Nothing else changes: same `field(...)` declarations, same one streaming pass, same columns. This
module binds `demo.commerce.ProductFields` to the browser contract and supplies the one piece
scrapy-poet does *not* ship — a provider that builds `web_poet.BrowserResponse` from a rendered
Scrapy response (scrapy-poet only knows how to build `HttpResponse`).

Run it (needs the `browser` extra — see README):

    uv run python -m demo.site.server                    # terminal 1
    uv run scrapy crawl commerce_browser -s CLOSESPIDER_ITEMCOUNT=10 -O out/browser.json

`delivery_window` / `delivery_cost` are the point of the exercise: the storefront serves
`.buy-box #delivery` **empty** and fills it client-side from `__APP_STATE__` (see
`demo/site/render.py`, `_HYDRATE_JS`). On the direct path they are `None`; on the browser path they
carry values — while every other field stays byte-identical, which `tests/test_browser.py` asserts.
"""
from __future__ import annotations

import web_poet
from scrapy.http import Response
from scrapy_poet import PageObjectInputProvider
from web_poet import BrowserHtml, BrowserResponse, Returns
from zyte_common_items import Product

from frostwork.webpoet import FrostBrowserPage, field

from .commerce import ProductFields


class BrowserResponseProvider(PageObjectInputProvider):
    """Builds web-poet's browser inputs from a Scrapy response that a browser produced.

    Needed here, but NOT on the Zyte API stack: `scrapy_zyte_api.providers.ZyteApiProvider` already
    provides `BrowserResponse`, `BrowserHtml` and `AnyResponse`, so a `FrostBrowserPage` there needs no
    wiring at all. Plain scrapy-poet provides only `HttpResponse` and friends, because it has no way to
    know a given response came from a browser — that is the download handler's business. With
    scrapy-playwright installed and `playwright=True` in the request meta, `response.text` *is* the
    serialised DOM after load, so the conversion is direct.

    Registered through `SCRAPY_POET_PROVIDERS` (see `CommerceBrowserSpider.custom_settings`). Taking
    `response: Response` here is also what tells scrapy-poet the download is needed, so a callback
    using this must NOT annotate its response as `DummyResponse`.
    """

    provided_classes = {BrowserResponse, BrowserHtml}
    name = "browser_response"

    def __call__(self, to_provide, response: Response):
        html = BrowserHtml(response.text)
        built: dict[type, object] = {
            BrowserHtml: html,
            BrowserResponse: BrowserResponse(url=str(response.url), html=html, status=response.status),
        }
        return [built[cls] for cls in to_provide]



# Deliberately NOT `@handle_urls`-registered, unlike everything in `demo/commerce.py`. A rule is
# (url pattern, returned item) and these would claim the same pair as `ProductPage` — so in a process
# that imports both (any crawl does, since the spider module imports this one) the higher priority
# would win every `Product` request, browser response available or not. The spiders name the page
# object they want in the callback signature, which is unambiguous.
class ProductBrowserPage(ProductFields, FrostBrowserPage, Returns[Product], skip_nonitem_fields=True):
    """`ProductFields` over a rendered DOM. The two extra fields below exist ONLY in the DOM — the
    served HTML has an empty `#delivery` container — so they are the direct evidence that the scan
    read the browser's output and not the wire bytes.

    They are not `Product` attributes, and `skip_nonitem_fields=True` drops them from the built item;
    `tests/test_browser.py` and the spider read them off the page object directly."""

    delivery_window = field("#delivery .delivery-window::text")
    delivery_cost = field("#delivery .delivery-cost::text")


class NavigationBrowserPage(FrostBrowserPage):
    """The listing page over the rendered DOM — same selectors as `commerce.NavigationPage`."""

    card_hrefs = field(".product-grid .card-link::attr(href)", all=True)
    next_href = field("a.page-next::attr(href)")

    @web_poet.field
    def page_url(self) -> str:
        return str(self.response.url)

    @web_poet.field
    def product_urls(self) -> list[str]:
        return [str(self.response.urljoin(h)) for h in dict.fromkeys(self.card_hrefs)]

    @web_poet.field
    def next_page(self) -> str | None:
        return str(self.response.urljoin(self.next_href)) if self.next_href else None
