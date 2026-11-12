"""A real Scrapy spider that crawls https://books.toscrape.com and lets scrapy-poet inject the
frostwork-backed page objects into the callbacks.

    uv run scrapy crawl books -O out/books.json
    # polite by default; cap a demo run with, e.g.:
    uv run scrapy crawl books -s CLOSESPIDER_ITEMCOUNT=40 -O out/books.json

Flow: start on the "Books" catalogue page -> `NavigationPage` extracts every product card and the
"next" link in one pass -> follow each book to `BookPage` (the one-pass detail extraction) -> follow
pagination back into `parse`.

The crawl is plain Scrapy HTTP — no Zyte API needed for this static sandbox. scrapy-poet's default
provider builds the web-poet `HttpResponse` from the ordinary download, and frostwork is the
extraction backend inside the page objects, invisible to Scrapy itself.
"""
import scrapy
from scrapy_poet import DummyResponse

from demo.pages import BookPage, NavigationPage


class BooksSpider(scrapy.Spider):
    name = "books"

    # The "Books" category lists the whole catalogue (1000 books across 50 pages).
    start_urls = ["https://books.toscrape.com/catalogue/category/books_1/index.html"]

    async def start(self):
        for url in self.start_urls:
            yield scrapy.Request(url, callback=self.parse)

    async def parse(self, response: DummyResponse, nav: NavigationPage):
        # `nav: NavigationPage` is the injection point — scrapy-poet builds it from the response.
        # `DummyResponse` says this callback only needs the page object, not the raw response body.
        navigation = await nav.to_item()

        for url in navigation.book_urls:
            yield scrapy.Request(url, callback=self.parse_book)

        if navigation.next_page:
            yield scrapy.Request(navigation.next_page, callback=self.parse)

    async def parse_book(self, response: DummyResponse, page: BookPage):
        # `page.to_item()` runs every Book field in one streaming pass over the detail page.
        yield await page.to_item()
