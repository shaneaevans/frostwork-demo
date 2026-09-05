"""Exercise real Scrapy startup, downloads, injection, pagination and feed export."""
import asyncio
import json
from pathlib import Path
import subprocess
import sys

from itemadapter import ItemAdapter
import pytest

from demo.parsel_reference import product as parsel_product
from demo.site import catalog, render
from demo.site.server import local_storefront

ROOT = Path(__file__).resolve().parents[1]


def run_crawl(tmp_path, spider, base, pages):
    output = tmp_path / f"{spider}.json"
    stats = tmp_path / f"{spider}-stats.json"
    result = subprocess.run(
        [sys.executable, "-m", "demo.crawl", spider, "--base", base, "--pages", str(pages),
         "--output", str(output), "--stats", str(stats)], cwd=ROOT,
        capture_output=True, text=True, timeout=240,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads(stats.read_text())
    assert report["finish_reason"] == "finished"
    assert not report.get("log_count/ERROR"), result.stderr
    assert not report.get("httpcache/hit")
    items = json.loads(output.read_text())
    assert items and len(items) == report["item_scraped_count"]
    return items, report


def expected_items(base, pages):
    expected = {}
    for page in range(1, pages + 1):
        products, _ = catalog.listing(None, None, page)
        for pid in products:
            url = base + catalog.product_url(pid)
            body = render.product_page(pid).replace("{HOST}", base.removeprefix("http://")).encode()
            expected[url] = ItemAdapter(parsel_product(body, url)).asdict()
    return expected


def assert_export(items, expected, *, full):
    urls = [item["url"] for item in items]
    assert len(urls) == len(set(urls)), "duplicate product export"
    assert set(urls) == set(expected), "missing products or pagination"
    keys = ("url", "name", "price", "currency", "availability", "sku", "features")
    for item in items:
        truth = expected[item["url"]]
        assert item == (truth if full else {key: truth[key] for key in keys})


@pytest.mark.parametrize("spider", ["commerce_plain", "commerce_loader", "commerce"])
def test_local_crawl_exports_expected_items_and_follows_pagination(tmp_path, spider):
    with local_storefront() as base:
        items, _ = run_crawl(tmp_path, spider, base, pages=2)
        assert_export(items, expected_items(base, 2), full=spider == "commerce")


@pytest.mark.browser
def test_browser_spider_renders_and_exports_complete_items(tmp_path):
    pytest.importorskip("scrapy_playwright")
    with local_storefront() as base:
        items, stats = run_crawl(tmp_path, "commerce_browser", base, pages=2)
        # Every listing and detail request must use the browser, including the initial request.
        assert stats["playwright/request_count"] >= len(items) + 2
        for item in items:
            delivery = render._delivery(catalog.product(int(item["productId"])))
            assert item.pop("delivery_window") == delivery["window"]
            assert item.pop("delivery_cost") == delivery["cost"]
        assert_export(items, expected_items(base, 2), full=True)


def test_initial_browser_request_has_render_flag_and_explicit_callback():
    from demo.spiders.commerce_browser import CommerceBrowserSpider

    spider = CommerceBrowserSpider()

    async def requests():
        return [request async for request in spider.start()]

    (request,) = asyncio.run(requests())
    assert request.callback == spider.parse
    assert request.meta["playwright"] is True


def test_quickstart_manages_server_and_exports_items(tmp_path):
    output = tmp_path / "quickstart.json"
    result = subprocess.run([sys.executable, "-m", "demo.run", "--pages", "1", "--output", str(output)],
                            cwd=ROOT, capture_output=True, text=True, timeout=240)
    assert result.returncode == 0, result.stdout + result.stderr
    items = json.loads(output.read_text())
    products, _ = catalog.listing(None, None, 1)
    assert len(items) == len(products)
    for item in items:
        pid = int(item["url"].split("/p/")[1].split("/")[0])
        assert item["name"] == catalog.product(pid)["name"]


def test_crawl_command_fails_for_an_empty_feed(tmp_path):
    with local_storefront() as base:
        result = subprocess.run([sys.executable, "-m", "demo.crawl", "commerce_plain", "--base", base + "/missing",
                                 "--output", str(tmp_path / "empty.json")],
                                cwd=ROOT, capture_output=True, text=True, timeout=240)
    assert result.returncode != 0
    assert "produced no items" in result.stderr


def test_export_gate_rejects_lost_products_keys_and_changed_values():
    truth = {"url": "http://example/p/1", "name": "Widget", "price": "1.00"}
    expected = {truth["url"]: truth}
    for broken in ([], [truth, truth], [{"url": truth["url"]}], [{**truth, "price": "2.00"}]):
        with pytest.raises(AssertionError):
            assert_export(broken, expected, full=True)


def test_crawl_command_rejects_partial_output_after_a_callback_error(tmp_path):
    code = '''
import sys
from demo.crawl import crawl
from demo.spiders.commerce_plain import CommercePlainSpider
original = CommercePlainSpider.parse_product
def broken(self, response):
    if "/p/1/" in response.url:
        raise ValueError("deliberate callback regression")
    return list(original(self, response))
CommercePlainSpider.parse_product = broken
crawl(CommercePlainSpider, sys.argv[1], 1, sys.argv[2], sys.argv[3])
'''
    stats = tmp_path / "partial-stats.json"
    with local_storefront() as base:
        result = subprocess.run([sys.executable, "-c", code, base, str(tmp_path / "partial.json"), str(stats)],
                                cwd=ROOT, capture_output=True, text=True, timeout=240)
    assert result.returncode != 0
    assert "deliberate callback regression" in result.stderr
    report = json.loads(stats.read_text())
    assert report["item_scraped_count"] > 0, "this must exercise partial, not empty, output"
    assert report["spider_exceptions/ValueError"] == 1
