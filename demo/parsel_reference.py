"""Independent Parsel implementation of the Product item, used by tests and benchmarks.

Keep this explicit: checking whole items catches missing keys and broken processors as well as
selector differences. The shared helpers below only transform already-extracted strings.
"""
import re

from parsel import Selector
from zyte_common_items import AdditionalProperty, AggregateRating, Brand, Breadcrumb, Image, Product

from demo.prices import parse_amount, symbol_to_currency


def product(body, url):
    sel = Selector(body=body, encoding="utf-8")
    css = lambda query: sel.css(query).get()
    rating = css(".reviews-summary .rating-big::text")
    reviews = css(".reviews-summary .rating-total::text")
    count = re.search(r"[\d,]+", reviews or "")
    identifier = re.search(r"/p/(\d+)", url)
    return Product(
        url=url,
        productId=identifier.group(1) if identifier else None,
        canonicalUrl=css('link[rel="canonical"]::attr(href)'),
        name=css("h1.product-title::text"),
        price=css(".product-main .price .price-amount::text"),
        regularPrice=parse_amount(css(".product-main .price-regular::text")),
        currencyRaw=css(".product-main .price-symbol::text"),
        currency=symbol_to_currency(css(".product-main .price-symbol::text")),
        availability=css(".product-main .availability::attr(data-availability)"),
        sku=css(".perks .sku::attr(data-sku)"),
        mpn=css('.specs-table td[data-key="model"]::text'),
        color=css('.specs-table td[data-key="color"]::text'),
        features=sel.css(".feature-list .feature-item::text").getall(),
        description=" ".join(t.strip() for t in sel.css("#product-description ::text").getall() if t.strip()) or None,
        brand=next((Brand(name=node.css(".brand::text").get()) for node in sel.css(".subtitle")), None),
        mainImage=next((Image(url=node.css("img::attr(src)").get()) for node in sel.css(".gallery-main")), None),
        images=[Image(url=node.css("img::attr(src)").get()) for node in sel.css(".thumb-list .thumb-item")],
        breadcrumbs=[Breadcrumb(name=node.css("a::text").get(), url=node.css("a::attr(href)").get())
                     for node in sel.css(".breadcrumb .breadcrumb-item")],
        aggregateRating=(AggregateRating(ratingValue=float(rating) if rating else None,
                                         reviewCount=int(count.group().replace(",", "")) if count else None)
                         if sel.css(".reviews-summary") else None),
        additionalProperties=[AdditionalProperty(name=node.css("th::text").get(), value=node.css("td::text").get())
                              for node in sel.css(".specs-table tbody tr")],
    )
