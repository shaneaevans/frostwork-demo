"""Fixture tests for the Frostwork-backed page objects.

Run against the saved books.toscrape.com pages — no network — exercising the real async web-poet
`to_item()` path that scrapy-poet uses in the spider.

    uv run pytest
"""
import asyncio
from pathlib import Path

from web_poet import HttpResponse

from demo.items import Book, Navigation
from demo.pages import BookPage, NavigationPage

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
BOOK_URL = "https://books.toscrape.com/catalogue/a-light-in-the-attic_1000/index.html"
CATALOGUE_URL = "https://books.toscrape.com/catalogue/category/books_1/index.html"


def _response(name: str, url: str) -> HttpResponse:
    return HttpResponse(url, body=(FIXTURES / name).read_bytes(), encoding="utf-8")


def _to_item(page):
    return asyncio.run(page.to_item())


def test_book_page_fields():
    book = _to_item(BookPage(_response("book.html", BOOK_URL)))
    assert isinstance(book, Book)
    assert book.title == "A Light in the Attic"
    assert book.category == "Poetry"
    assert book.price == "51.77"        # normalized string amount (via price-parser)
    assert book.currencyRaw == "£"      # the symbol as written on the page (via .re_first)
    assert book.currency == "GBP"       # ISO 4217, derived from currencyRaw
    assert book.rating == 3
    assert book.availability == "In stock (22 available)"
    assert book.in_stock is True
    assert book.stock == 22
    assert book.upc == "a897fe39b1053632"
    assert book.url == BOOK_URL
    # image_path is relative as on the page; image_url is resolved against the response.
    assert book.image_path.startswith("../../media/")
    assert book.image_url == (
        "https://books.toscrape.com/media/cache/fe/72/fe72f0532301ec28892ae79a629a293c.jpg"
    )
    # `description` uses a `~` sibling combinator — native, byte-for-byte with Parsel.
    assert book.description.startswith("It's hard to imagine a world without A Light in the Attic.")


def test_book_page_is_one_streaming_pass(monkeypatch):
    """Every selector field shares a single compiled-plan extract_grouped call — cost tracks the page,
    not the field count (computed/response fields add no extra scan)."""
    calls = {"n": 0}
    real_plan = BookPage._frostwork_plan

    class CountingPlan:
        def extract_grouped(self, *a, **k):
            calls["n"] += 1
            return real_plan.extract_grouped(*a, **k)

    monkeypatch.setattr(BookPage, "_frostwork_plan", CountingPlan())

    book = _to_item(BookPage(_response("book.html", BOOK_URL)))
    assert book.title == "A Light in the Attic"
    assert calls["n"] == 1


def test_navigation_page_lists_books():
    nav = _to_item(NavigationPage(_response("catalogue.html", CATALOGUE_URL)))
    assert isinstance(nav, Navigation)
    assert len(nav.books) == 20
    first = nav.books[0]
    assert first.title == "A Light in the Attic"
    assert first.price == "51.77"
    assert first.rating == 3
    # The parallel-column cards keep relative hrefs; the page resolves them to absolute book_urls.
    assert first.url.endswith("a-light-in-the-attic_1000/index.html")
    assert nav.book_urls[0] == BOOK_URL
    assert nav.next_page == (
        "https://books.toscrape.com/catalogue/category/books_1/page-2.html"
    )
