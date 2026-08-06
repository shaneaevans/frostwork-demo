"""Crawl the storefront through a real browser (scrapy-playwright) and extract with Frostwork.

Identical in shape to `demo/spiders/commerce.py`. The only differences are configuration — the
playwright download handlers, and the `BrowserResponseProvider` that turns the rendered response into
web-poet's `BrowserResponse` — plus the page objects, which are `FrostBrowserPage` subclasses over
the same `ProductFields` schema.

    uv sync --extra browser && uv run playwright install chromium   # once
    uv run python -m demo.site.server                               # terminal 1
    uv run scrapy crawl commerce_browser -s CLOSESPIDER_ITEMCOUNT=10 -O out/browser.json

Note the callbacks take a real `scrapy.http.Response`, not `DummyResponse`: `BrowserResponseProvider`
needs the downloaded (rendered) response to build its inputs from.
"""
import attrs
import scrapy

from demo.browser import BrowserResponseProvider, NavigationBrowserPage, ProductBrowserPage


class CommerceBrowserSpider(scrapy.Spider):
    name = "commerce_browser"

    custom_settings = {
        # --- scrapy-playwright: render every request in Chromium ---
        "DOWNLOAD_HANDLERS": {
            "http": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
            "https": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
        },
        "PLAYWRIGHT_BROWSER_TYPE": "chromium",
        "PLAYWRIGHT_LAUNCH_OPTIONS": {"headless": True},
        # The pages carry a large JSON island and a lot of inline script; give the load room.
        "PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT": 60_000,
        # --- scrapy-poet: our BrowserResponse provider, alongside the built-in ones ---
        "SCRAPY_POET_PROVIDERS": {BrowserResponseProvider: 500},
        # A browser is expensive; don't also cache its output (the storefront is local and free).
        "HTTPCACHE_ENABLED": False,
        "DOWNLOAD_DELAY": 0,
        "AUTOTHROTTLE_ENABLED": False,
        "CONCURRENT_REQUESTS": 8,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 8,
    }

    def __init__(self, base="http://127.0.0.1:8000", *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.base = base.rstrip("/")
        self.start_urls = [f"{self.base}/c"]

    def start_requests(self):
        for url in self.start_urls:
            yield scrapy.Request(url, meta={"playwright": True})

    async def parse(self, response: scrapy.http.Response, nav: NavigationBrowserPage):
        navigation = await nav.to_item()

        for url in navigation["product_urls"]:
            yield scrapy.Request(url, callback=self.parse_product, meta={"playwright": True})

        if navigation["next_page"]:
            yield scrapy.Request(navigation["next_page"], callback=self.parse,
                                 meta={"playwright": True})

    async def parse_product(self, response: scrapy.http.Response, page: ProductBrowserPage):
        item = await page.to_item()
        # The two client-rendered columns are not Product attributes, so read them off the page
        # object: they are what proves the scan ran over the browser's DOM.
        yield {**attrs.asdict(item),
               "delivery_window": page.delivery_window,
               "delivery_cost": page.delivery_cost}
