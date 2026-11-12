"""Run the page objects WITHOUT Scrapy — the fastest way to see the integration work, against the
saved books.toscrape.com fixtures.

    uv run python -m demo.standalone

Shows: (1) the `FrostPage` `BookPage` producing a `Book` in one streaming pass; (2) `NavigationPage`
extracting every product card on a listing page (`Many(...)` -> one `BookLink` each, one pass);
(3) the lower-level `frostwork.Page` primitive doing the same book extraction without web-poet; and
(4) Frostwork's no-fallback contract — an unsupported selector raises before scanning (the default) or
returns an empty column (`strict=False`), never a wrong value.
"""
import asyncio
import json
from dataclasses import asdict
from pathlib import Path

from web_poet import HttpResponse

import frostwork
from frostwork import Page

from .pages import BookPage, NavigationPage, parse_amount, rating_to_int

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
BOOK_URL = "https://books.toscrape.com/catalogue/a-light-in-the-attic_1000/index.html"
CATALOGUE_URL = "https://books.toscrape.com/catalogue/category/books_1/index.html"


def _response(name: str, url: str) -> HttpResponse:
    path = FIXTURES / name
    return HttpResponse(url, body=path.read_bytes(), encoding="utf-8")


def _rule(title: str) -> None:
    print("\n" + "=" * 78 + f"\n{title}\n" + "=" * 78)


def main() -> None:
    book_resp = _response("book.html", BOOK_URL)
    catalogue_resp = _response("catalogue.html", CATALOGUE_URL)

    _rule("1. FrostPage BookPage  (frostwork.webpoet) — every field in one streaming pass")
    book = asyncio.run(BookPage(book_resp).to_item())
    print(json.dumps(asdict(book), indent=2, ensure_ascii=False))

    _rule("2. NavigationPage — Many(...) extracts every product card (one BookLink each), one pass")
    nav = asyncio.run(NavigationPage(catalogue_resp).to_item())
    nav_dict = asdict(nav)
    shown = 3
    extra = len(nav.books) - shown
    nav_dict["books"] = nav_dict["books"][:shown] + ([f"... +{extra} more"] if extra > 0 else [])
    nav_dict["book_urls"] = nav_dict["book_urls"][:shown] + ([f"... +{extra} more"] if extra > 0 else [])
    print(json.dumps(nav_dict, indent=2, ensure_ascii=False))

    _rule("3. The frostwork.Page primitive — same one-pass engine, without web-poet")
    page = (Page()
            .field("title", ".product_main h1::text")
            .field("price", ".product_main p.price_color::text", map=parse_amount)
            .field("rating", "p.star-rating::attr(class)", map=rating_to_int)
            .field("description", "#product_description ~ p::text")
            .field_all("breadcrumbs", "ul.breadcrumb a::text"))
    item = page.extract(book_resp.body, encoding="utf-8")   # ONE scan fills every field
    print(json.dumps(item.to_dict(), indent=2, ensure_ascii=False))

    _rule("4. No fallback — an unsupported selector fails fast, or returns an empty column")
    # `li:last-child > b` puts a reverse position on an ancestor, an unsupported placement. There are exactly two outcomes, and neither
    # is a wrong value or a silent reroute to another parser (see the compatibility contract):
    #   * the DEFAULT (strict=True) raises UnsupportedSelector *before* scanning a byte;
    #   * strict=False opts into the engine's permissive empty column.
    selectors = [".product_main h1::text", "li:last-child > b::text"]
    try:
        frostwork.extract(book_resp.body, selectors)
    except frostwork.UnsupportedSelector as exc:
        print(f"strict=True (default) raises before scanning:\n  {exc}\n")
    cols = frostwork.extract(book_resp.body, selectors, strict=False)
    print("strict=False returns an empty column for it:")
    print(json.dumps({"h1::text": cols[0], "li:last-child > b::text (unsupported)": cols[1]}, indent=2))


if __name__ == "__main__":
    main()
