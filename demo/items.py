"""The items the demo produces.

Plain dataclasses — Scrapy exports them natively, and web-poet's `to_item()` builds them from a
`FrostPage`'s fields (declared with `Returns[T]`), so every field name here must match a field on the
page object. `field(...)` selector fields and `@web_poet.field` computed methods both become item
fields; `raw_*`/`card_*` helper columns are dropped by `skip_nonitem_fields=True`.

The schema mirrors what a `zyte_common_items.Product` carries for a book, but stays dependency-free
so the demo is easy to run. Swap in a typed item (attrs / pydantic / zyte-common-items) by changing
the `Returns[...]` parameter in `pages.py`; web-poet builds whichever type you bind.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class BookLink:
    """One book as it appears on a catalogue/listing page (an `article.product_pod`).

    Extracted in the *parent* streaming pass via `Many(...)`, so it must stay pure-selector and
    native: `url`/`thumbnail` are the relative paths exactly as written on the page. The navigation
    page object resolves them to absolute URLs in a `@derive` afterwards (see `Navigation.book_urls`).
    """

    url: str | None = None
    title: str | None = None
    price: str | None = None  # normalized amount, e.g. "51.77" (Zyte models price as a string)
    rating: int | None = None
    thumbnail: str | None = None


@dataclass
class Navigation:
    """What a listing page yields the spider: the books on this page, plus where to go next."""

    page_url: str | None = None
    books: list[BookLink] = field(default_factory=list)
    book_urls: list[str] = field(default_factory=list)  # absolute, derived from `books`
    next_href: str | None = None                        # relative, as on the page
    next_page: str | None = None                        # absolute, derived from `next_href`


@dataclass
class Book:
    """A single book's detail page."""

    url: str | None = None
    title: str | None = None
    category: str | None = None
    price: str | None = None       # normalized amount, e.g. "51.77" (Zyte models price as a string)
    currencyRaw: str | None = None  # the symbol as written on the page, e.g. "£"
    currency: str | None = None    # ISO 4217 code, derived from currencyRaw, e.g. "GBP"
    rating: int | None = None
    availability: str | None = None
    in_stock: bool | None = None
    stock: int | None = None
    upc: str | None = None
    description: str | None = None
    image_path: str | None = None  # relative, as written on the page
    image_url: str | None = None   # absolute, derived from `image_path`
