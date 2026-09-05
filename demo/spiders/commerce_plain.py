"""Start here: standard Scrapy callbacks using a reusable frostwork.Page.

Run `python -m demo.run`, or add `--spider commerce_loader` for ItemLoader.
"""
import scrapy
from itemloaders import ItemLoader
from itemloaders.processors import Identity, TakeFirst

from demo.plain import NAVIGATION, PRODUCT


class CommercePlainSpider(scrapy.Spider):
    name = "commerce_plain"
    custom_settings = {
        "ADDONS": {},  # This example uses only Scrapy and frostwork.Page.
        "DOWNLOAD_DELAY": 0,
        "AUTOTHROTTLE_ENABLED": False,
        "HTTPCACHE_ENABLED": False,
    }

    def __init__(self, base="http://127.0.0.1:8000", max_pages=None, **kwargs):
        super().__init__(**kwargs)
        self.base = base.rstrip("/")
        self.max_pages = int(max_pages) if max_pages is not None else None
        if self.max_pages is not None and self.max_pages < 1:
            raise ValueError("max_pages must be positive")

    async def start(self):
        yield scrapy.Request(f"{self.base}/c", callback=self.parse)

    def parse(self, response, page_number=1):
        navigation = NAVIGATION.extract(response.body, encoding=response.encoding)
        for href in dict.fromkeys(navigation.value("links")):
            yield response.follow(href, callback=self.parse_product)
        if navigation.value("next") and (self.max_pages is None or page_number < self.max_pages):
            yield response.follow(navigation.value("next"), callback=self.parse,
                                  cb_kwargs={"page_number": page_number + 1})

    def parse_product(self, response):
        values = PRODUCT.extract(response.body, encoding=response.encoding)
        yield self.build_item(response, values)

    def build_item(self, response, values):
        return {"url": response.url, **values.to_dict()}


class ProductLoader(ItemLoader):
    default_output_processor = TakeFirst()
    features_out = Identity()


class CommerceLoaderSpider(CommercePlainSpider):
    """Feed extracted values into existing ItemLoader processors with add_value()."""
    name = "commerce_loader"

    def build_item(self, response, values):
        loader = ProductLoader(item={})
        loader.add_value("url", response.url)
        for name, value in values.to_dict().items():
            loader.add_value(name, value)
        return loader.load_item()
