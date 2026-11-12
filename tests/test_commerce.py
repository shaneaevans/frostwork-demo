"""Offline tests for the generative storefront + its Frostwork Product page object.

Everything is rendered in-process from the deterministic catalog (no server, no network, no stored
fixtures), then extracted with the page object and checked back against the catalog truth.

    uv run pytest
"""
import asyncio

from web_poet import HttpResponse
from zyte_common_items import Product

from demo.commerce import ProductPage
from demo.site import catalog, render

PID = 1


def _response(pid=PID):
    html = render.product_page(pid).replace("{HOST}", "testserver")
    url = f"http://testserver{catalog.product_url(pid)}"
    return HttpResponse(url, body=html.encode("utf-8"), encoding="utf-8")


def _to_item(page):
    return asyncio.run(page.to_item())


def test_page_shape_matches_zyte_targets():
    """The generated product page should sit near Zyte's real-world corpus shape."""
    from parsel import Selector
    html = render.product_page(PID)
    size_kb = len(html.encode()) / 1024
    elements = len(Selector(html).xpath("//*"))
    assert 400 < size_kb < 900, size_kb            # ~555 KB median
    assert 1500 < elements < 3000, elements        # ~1,800-2,400 target
    assert "application/ld+json" in html           # structured-data island
    assert 'id="__APP_STATE__"' in html            # data island that carries the weight


def test_product_extraction_matches_catalog():
    truth = catalog.product(PID)
    product = _to_item(ProductPage(response=_response()))
    assert isinstance(product, Product)
    assert product.name == truth["name"]
    assert product.brand.name == truth["brand"]
    assert product.price == truth["price"]
    assert product.currency == "USD"
    assert product.availability == truth["availability"]
    assert product.sku == truth["sku"]
    assert product.mpn == truth["mpn"]
    assert product.color == truth["color"]
    assert product.productId == truth["productId"]
    assert product.mainImage.url == truth["mainImage"]
    assert product.aggregateRating.ratingValue == truth["rating"]
    assert product.aggregateRating.reviewCount == truth["reviewCount"]
    assert [b.name for b in product.breadcrumbs] == truth["breadcrumbs"]
    assert len(product.additionalProperties) == len(truth["specs"])
    assert product.features == truth["features"]


def test_full_schema_is_one_streaming_pass(monkeypatch):
    """The whole wide Product — scalars + nested Brand/Image/Rating/Breadcrumb/AdditionalProperty via
    Many/One — comes from ONE compiled-plan extract_grouped call (no DOM, no per-field re-parse)."""
    calls = {"n": 0}
    real_plan = ProductPage._frostwork_plan

    class CountingPlan:
        def extract_grouped(self, *a, **k):
            calls["n"] += 1
            return real_plan.extract_grouped(*a, **k)

    monkeypatch.setattr(ProductPage, "_frostwork_plan", CountingPlan())

    product = _to_item(ProductPage(response=_response()))
    assert product.name == catalog.product(PID)["name"]
    assert calls["n"] == 1


def test_matches_parsel():
    """Frostwork's one pass returns byte-identical columns to Parsel's per-selector queries."""
    import frostwork
    from parsel import Selector

    body = _response().body
    selectors = list(ProductPage.frost_schema()["fields"].values())
    frost = frostwork.extract(body, selectors, "utf-8")
    sel = Selector(body=body, encoding="utf-8")
    parsel_cols = [sel.css(q).getall() for q in selectors]
    assert frost == parsel_cols
