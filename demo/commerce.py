"""Frostwork page objects for the generative storefront (`demo.site`).

These extract the **Zyte Common Product Schema** (`zyte_common_items.Product`) from the heavy,
~555 KB product pages — the whole wide item, including the nested `Brand`, `Image`,
`AggregateRating`, `Breadcrumb`, and `AdditionalProperty` types — in a SINGLE streaming pass over
the page (no DOM built). This is the case Frostwork is built for: a big page, a wide schema, and the
cost stays one scan regardless of how many fields you add.

The nested collections use Frostwork's `Many`/`One`: for every element matching the container, each
sub-field is extracted **scoped to that container** (descendant-or-self) in the same pass, then built
into the matching zyte type via `item=`. `.map`/`.re_first` transform sub-values in place. Scalar
fields are plain `field(...)`; `url`/`productId`/`currency` need the response or another field, so
they're `@web_poet.field` methods.
"""
from __future__ import annotations

import re

import web_poet
from web_poet import Returns, handle_urls
from zyte_common_items import (
    AdditionalProperty, AggregateRating, Brand, Breadcrumb, Image, Product,
)

from frostwork.webpoet import FrostPage, Many, One, field

from .prices import parse_amount, symbol_to_currency


def _join_text(parts: list[str]) -> str | None:
    """Collapse a subtree's text nodes into one clean string (drop whitespace-only nodes)."""
    return " ".join(t.strip() for t in parts if t and t.strip()) or None


def _int(text: str | None) -> int | None:
    return int(text.replace(",", "")) if text else None


@handle_urls("127.0.0.1")
class ProductPage(FrostPage, Returns[Product], skip_nonitem_fields=True):
    # --- scalar Product fields (selector, with an in-Python transform where needed) ---
    canonicalUrl = field('link[rel="canonical"]::attr(href)')
    name = field("h1.product-title::text")
    # The amount is already isolated in its own element (Zyte models price as a string) — take it
    # as-is. regularPrice is a "$199.00" blob, so price-parser pulls the amount out.
    price = field(".product-main .price .price-amount::text")
    regularPrice = field(".product-main .price-regular::text").map(parse_amount)
    currencyRaw = field(".product-main .price-symbol::text")
    availability = field(".product-main .availability::attr(data-availability)")
    sku = field(".perks .sku::attr(data-sku)")
    mpn = field('.specs-table td[data-key="model"]::text')
    color = field('.specs-table td[data-key="color"]::text')
    features = field(".feature-list .feature-item::text", all=True)
    description = field("#product-description ::text", all=True).map(_join_text)

    # --- nested zyte types via Many/One: each sub-field is scoped to its container, one pass ---
    brand = One(".subtitle", item=Brand, name=field(".brand::text"))
    mainImage = One(".gallery-main", item=Image, url=field("img::attr(src)"))
    images = Many(".thumb-list .thumb-item", item=Image, url=field("img::attr(src)"))
    breadcrumbs = Many(".breadcrumb .breadcrumb-item", item=Breadcrumb,
                       name=field("a::text"), url=field("a::attr(href)"))
    aggregateRating = One(".reviews-summary", item=AggregateRating,
                          ratingValue=field(".rating-big::text").map(lambda s: float(s) if s else None),
                          reviewCount=field(".rating-total::text").re_first(r"[\d,]+").map(_int))
    additionalProperties = Many(".specs-table tbody tr", item=AdditionalProperty,
                                 name=field("th::text"), value=field("td::text"))

    # --- composite fields from the response / other fields ---
    @web_poet.field
    def url(self) -> str:
        return str(self.response.url)

    @web_poet.field
    def productId(self) -> str | None:
        m = re.search(r"/p/(\d+)", str(self.response.url))
        return m.group(1) if m else None

    @web_poet.field
    def currency(self) -> str | None:
        return symbol_to_currency(self.currencyRaw)


@handle_urls("127.0.0.1")
class NavigationPage(FrostPage):
    """A listing/category page: the product links on it + the link to the next page. Returns a plain
    dict (navigation isn't a zyte-common-items type, just what the spider needs to keep crawling)."""

    card_hrefs = field(".product-grid .card-link::attr(href)", all=True)
    next_href = field("a.page-next::attr(href)")

    @web_poet.field
    def page_url(self) -> str:
        return str(self.response.url)

    @web_poet.field
    def product_urls(self) -> list[str]:
        # resolve the (deduped) card hrefs against the listing URL — runs after the one pass.
        return [str(self.response.urljoin(h)) for h in dict.fromkeys(self.card_hrefs)]

    @web_poet.field
    def next_page(self) -> str | None:
        return str(self.response.urljoin(self.next_href)) if self.next_href else None
