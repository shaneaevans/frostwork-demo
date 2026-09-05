"""Reusable schemas for an ordinary Scrapy callback; no page-object injection needed."""
from frostwork import Page

from demo.prices import symbol_to_currency


NAVIGATION = (Page()
              .field_all("links", ".product-grid .card-link::attr(href)")
              .field("next", "a.page-next::attr(href)"))

# Declare once and reuse across responses. field_all keeps every feature in order.
PRODUCT = (Page()
           .field("name", "h1.product-title::text")
           .field("price", ".product-main .price .price-amount::text")
           .field("currency", ".product-main .price-symbol::text", map=symbol_to_currency)
           .field("availability", ".product-main .availability::attr(data-availability)")
           .field("sku", ".perks .sku::attr(data-sku)")
           .field_all("features", ".feature-list .feature-item::text"))
