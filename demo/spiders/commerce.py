"""Crawl the local generative storefront (`demo.site`) and extract `zyte_common_items.Product`.

Start the site in one terminal:

    uv run python -m demo.site.server            # http://127.0.0.1:8000

…then crawl it in another:

    uv run scrapy crawl commerce -s CLOSESPIDER_ITEMCOUNT=50 -O out/products.json
    # point at a different host/port with: -a base=http://127.0.0.1:8001

Flow: start on the all-products listing -> `NavigationPage` yields product links + the next page in
one pass -> follow each product to `ProductPage` (the ~555 KB page, extracted in one streaming pass)
-> follow pagination back into `parse`.
"""
import scrapy
from scrapy_poet import DummyResponse

from demo.commerce import NavigationPage, ProductPage


class CommerceSpider(scrapy.Spider):
    name = "commerce"

    # The target is a local server — no need to be polite. Crawl flat out so the wall-clock reflects
    # the framework + extraction cost, not deliberate throttling.
    custom_settings = {
        "DOWNLOAD_DELAY": 0,
        "AUTOTHROTTLE_ENABLED": False,
        "CONCURRENT_REQUESTS": 32,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 32,
    }

    def __init__(self, base="http://127.0.0.1:8000", *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.base = base.rstrip("/")
        self.start_urls = [f"{self.base}/c"]

    async def parse(self, response: DummyResponse, nav: NavigationPage):
        # `nav: NavigationPage` is the injection point — scrapy-poet builds it from the response.
        # `DummyResponse` says this callback only needs the page object, not the raw response body.
        navigation = await nav.to_item()

        for url in navigation["product_urls"]:
            yield scrapy.Request(url, callback=self.parse_product)

        if navigation["next_page"]:
            yield scrapy.Request(navigation["next_page"], callback=self.parse)

    async def parse_product(self, response: DummyResponse, page: ProductPage):
        # `page.to_item()` runs the whole wide Product extraction in one streaming pass.
        yield await page.to_item()
