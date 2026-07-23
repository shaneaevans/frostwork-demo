"""Page objects — the heart of the demo. Frostwork behind web-poet, crawling the real
https://books.toscrape.com sandbox.

`BookPage` and `NavigationPage` are `frostwork.webpoet.FrostPage` subclasses: you declare selectors
with `field(...)` and Frostwork answers **all of them in ONE streaming pass** over the page (no DOM,
no lxml tree). They are genuine web-poet page objects — injectable by scrapy-poet,
`@handle_urls`-registrable, with an async `to_item()`. This is what the Scrapy spider uses.

Two Frostwork idioms show up here:

* **`.map(...)` / `.re_first(...)`.** A `field(...)` gives the raw string/list; a transform (parse the
  amount, map the rating word to an int, pull the currency symbol with a regex) chains right onto it
  and runs in Python on the tiny extracted value — never in the scan. Fields that need the *response*
  (e.g. `urljoin`, `response.url`) or *other* fields are plain `@web_poet.field` methods. `raw_*`
  helper columns aren't item attributes, so `skip_nonitem_fields=True` drops them from the built item.
* **`Many(...)` for the product cards.** `NavigationPage.books` extracts one `BookLink` per
  `article.product_pod`, each sub-field scoped to that card, all in the same streaming pass.

Selectors here were discovered by running the Zyte `/scrape-analyze-page` skill over a real detail
page; `books.toscrape.com` has no JSON-LD, so every field is a plain CSS selector — including
`description`'s `~` sibling combinator, which Frostwork drives natively.
"""
from __future__ import annotations

import re

import web_poet
from web_poet import Returns, handle_urls

from frostwork.webpoet import FrostPage, Many, field

from .items import Book, BookLink, Navigation
from .prices import parse_amount, symbol_to_currency

# --------------------------------------------------------------------------- small pure transforms
# Passed to `.map(...)`; they run in Python on the one extracted value, never in the scan. Price /
# currency parsing lives in `demo.prices` (shared with the storefront page objects).

_RATINGS = {"One": 1, "Two": 2, "Three": 3, "Four": 4, "Five": 5}


def rating_to_int(class_attr: str | None) -> int | None:
    """`star-rating Three` -> 3 (the rating is encoded as a CSS class word)."""
    for word in (class_attr or "").split():
        if word in _RATINGS:
            return _RATINGS[word]
    return None


def first_nonempty(parts: list[str]) -> str | None:
    """The availability `<p>` holds several whitespace text nodes around the real value."""
    return next((p.strip() for p in parts if p and p.strip()), None)


def last(items: list[str]) -> str | None:
    return items[-1] if items else None


# ============================================================================ the book detail page

@handle_urls("books.toscrape.com")
class BookPage(FrostPage, Returns[Book], skip_nonitem_fields=True):
    """A book detail page. Every selector rides ONE streaming pass — including `description`, whose
    `~` sibling combinator Frostwork drives natively. `.map`/`.re_first` transform the extracted
    values in place; the two `@web_poet.field` methods below need the response (`urljoin`, `url`)."""

    title = field(".product_main h1::text")
    description = field("#product_description ~ p::text")            # `~` sibling combinator, native
    image_path = field("#product_gallery img::attr(src)")           # relative, as written on the page

    # "£51.77" -> price "51.77" (Zyte models price as a string) and currencyRaw "£" — both off the
    # SAME node, folded into the same scan; `.re_first` grabs the leading non-digits (the symbol).
    price = field(".product_main p.price_color::text").map(parse_amount)
    currencyRaw = field(".product_main p.price_color::text").re_first(r"^\D+")
    rating = field("p.star-rating::attr(class)").map(rating_to_int)
    category = field("ul.breadcrumb a::text", all=True).map(last)    # last crumb before the title
    availability = field(".product_main p.instock.availability::text", all=True).map(first_nonempty)
    upc = field("table.table-striped td::text").map(str.strip)       # first cell is the UPC

    @web_poet.field
    def currency(self) -> str | None:
        return symbol_to_currency(self.currencyRaw)   # ISO 4217 from the symbol (explicit map)

    @web_poet.field
    def in_stock(self) -> bool:
        return "in stock" in (self.availability or "").lower()

    @web_poet.field
    def stock(self) -> int | None:
        m = re.search(r"(\d+)\s+available", self.availability or "")
        return int(m.group(1)) if m else None

    @web_poet.field
    def url(self) -> str:
        return str(self.response.url)

    @web_poet.field
    def image_url(self) -> str:
        return str(self.response.urljoin(self.image_path or ""))


# ================================================================================ a listing page

@handle_urls("books.toscrape.com")
class NavigationPage(FrostPage, Returns[Navigation], skip_nonitem_fields=True):
    """A catalogue/category listing page: every product card on it + the "next" link.

    `Many(...)` extracts one `BookLink` per `article.product_pod`, each sub-field scoped to that card,
    in the SAME pass that reads `next_href`. `@web_poet.field` methods resolve relative URLs after."""

    books = Many("article.product_pod", item=BookLink,
                 url=field("h3 a::attr(href)"),                       # relative, resolved below
                 title=field("h3 a::attr(title)"),
                 price=field("p.price_color::text").map(parse_amount),
                 rating=field("p.star-rating::attr(class)").map(rating_to_int),
                 thumbnail=field(".image_container img::attr(src)"))
    next_href = field("li.next a::attr(href)")

    @web_poet.field
    def page_url(self) -> str:
        return str(self.response.url)

    @web_poet.field
    def book_urls(self) -> list[str]:
        return [str(self.response.urljoin(b.url)) for b in self.books if b.url]

    @web_poet.field
    def next_page(self) -> str | None:
        return str(self.response.urljoin(self.next_href)) if self.next_href else None
