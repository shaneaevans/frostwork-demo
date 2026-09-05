# frostwork-demo

Runnable [Frostwork](https://github.com/scrapy/frostwork) examples for **Scrapy developers**:
ordinary callbacks, ItemLoader, web-poet page objects, nested product items, and browser rendering.
Frostwork answers a declared set of selectors in one streaming scan without building a DOM.

Start with the local storefront: it generates its own catalogue, needs no account or external website,
and lets you change selectors against repeatable pages. The Books example also crawls the public
[books.toscrape.com](https://books.toscrape.com/) sandbox.

## Quickstart

Install [uv](https://docs.astral.sh/uv/getting-started/installation/), then:

```bash
git clone https://github.com/shaneaevans/frostwork-demo.git
cd frostwork-demo
uv sync --locked
uv run python -m demo.run
```

This installs a **released Frostwork wheel**, starts the storefront on an available local port,
crawls two listing pages and their products, writes `out/products.json`, and stops the server.
The command fails if the crawl encounters errors or produces no items. Rerunning it replaces the output.
Rust and a Frostwork checkout are only needed for the optional contributor workflow below.

The project supports Python 3.10 and newer; `.python-version` selects 3.13 for the default environment.
To use another interpreter, pass `--python 3.10` to both `uv sync` and `uv run`.

Choose your next example:

| Command | What it teaches |
| --- | --- |
| `uv run python -m demo.run` | Reuse a `frostwork.Page` in ordinary Scrapy callbacks |
| `uv run python -m demo.run --spider commerce_loader` | Send extracted values through ItemLoader processors |
| `uv run python -m demo.run --spider commerce` | Inject web-poet pages and export a complete typed Product |
| `uv run python -m demo.standalone` | Run page objects on saved Books fixtures, without a server |

Use `--pages 1` for a smaller run, `--output out/custom.json` to choose the feed,
and `--stats out/stats.json` to save Scrapy statistics. `--pages` limits listing pages, so each run
finishes all products it discovers within that limit. Output order may vary because downloads are concurrent.

## Ordinary Scrapy callbacks

Read [demo/plain.py](demo/plain.py) for the reusable navigation and product schemas, then
[commerce_plain.py](demo/spiders/commerce_plain.py) for the spider. Its extraction step is:

```python
values = PRODUCT.extract(response.body, encoding=response.encoding)
yield {"url": response.url, **values.to_dict()}
```

Create the schema once and reuse it across responses. `field` selects the first value;
`field_all` preserves every match in document order. Pass the response's encoding alongside its bytes.
Navigation uses the same API to collect product links and follow pagination.

The `commerce_loader` spider in the same file uses `ItemLoader.add_value()` on these extracted values.
It keeps `features` as a list and uses `TakeFirst` for scalar fields. This is a small example of inserting
Frostwork into an existing loader workflow.

Both spiders run with scrapy-poet disabled and export the same small product schema. The full
web-poet example below adds nested fields and typed items. Their shared fields are checked against the
same Parsel reference and deterministic catalogue in the crawl tests.

## web-poet and nested products

[demo/commerce.py](demo/commerce.py) declares a `zyte_common_items.Product` with prices, availability,
features, description, brand, images, breadcrumbs, ratings and additional properties.
`Many` and `One` scope nested fields to their containers in the same scan. `.map()` and `.re_first()`
transform values after extraction; `@web_poet.field` methods handle response URLs and computed fields.

[commerce.py](demo/spiders/commerce.py) uses explicit startup callbacks and asks scrapy-poet to inject
`NavigationPage` and `ProductPage`. [settings.py](demo/settings.py) enables the scrapy-poet addon.

```bash
uv run python -m demo.run --spider commerce --output out/typed-products.json
```

For a site you can also explore in your browser, start the server separately:

```bash
# Terminal 1
uv run python -m demo.site.server
# Terminal 2
uv run scrapy crawl commerce -a max_pages=2 -O out/products.json
```

Open <http://127.0.0.1:8000/>. Use `-a base=http://127.0.0.1:8001` with a server on another port.
The generated pages contain a wide product schema, inline scripts and structured-data islands.
Fields share the scan, but matching, returned values and item construction still have costs.

The public-site example uses typed `Book` and `Navigation` dataclasses, grouped book cards, price parsing,
ratings, and relative URL resolution. Its initial selectors were discovered with Zyte's
`/scrape-analyze-page` workflow; no Zyte service is needed to run the spider.

```bash
uv run scrapy crawl books -s CLOSESPIDER_ITEMCOUNT=40 -O out/books.json
```

This example enables robots.txt handling, a download delay and AutoThrottle. An item-count limit may
overshoot with concurrent requests. HTTP caching is **opt-in** for iteration on this external sandbox:
add `-s HTTPCACHE_ENABLED=1`, and delete `.scrapy/httpcache` when you want fresh responses.
The local runner and its tests always disable caching.

## Browser rendering

```bash
uv sync --locked --extra browser
uv run playwright install chromium
uv run python -m demo.run --spider commerce_browser --pages 1 --output out/browser.json
```

[scrapy-playwright](https://github.com/scrapy-plugins/scrapy-playwright) renders each request, including
the first listing. [BrowserResponseProvider](demo/browser.py) supplies the rendered HTML to
`FrostBrowserPage`; the same `ProductFields` schema supplies the server-visible fields.
The browser builds a DOM for rendering; Frostwork scans its serialized HTML without building another one.

The storefront fills `delivery_window` and `delivery_cost` with JavaScript. These fields must be populated
in the browser feed and are absent from the original response. Tests verify them through an actual Scrapy
browser crawl, alongside parity for the complete server-visible item.

## Unsupported selectors

Python raises `frostwork.UnsupportedSelector` before scanning if a selector is unsupported.
`strict=False` explicitly opts into an empty column. Frostwork never silently falls back to another parser.
Use `Page.check()` to audit your schema and consult the
[compatibility contract](https://github.com/scrapy/frostwork/blob/main/docs/COMPATIBILITY.md).

`python -m demo.standalone` demonstrates both outcomes with `li:last-child > b::text`: this puts a
reverse-position predicate on an ancestor, an unsupported placement. `:contains()` is supported.
The runnable example is tested so expanding support cannot leave its explanation silently stale.

## Tests

```bash
uv run pytest -m "not browser"
# With the browser extra and Chromium installed:
uv run pytest
```

The default suite includes fixture checks, whole-item comparisons against Parsel, actual HTTP crawls
through Scrapy, pagination, feed export, and tests that deliberately break values to prove the gates fail.
HTTP tests start their own loopback server; no external storefront is required. Tests use tldextract's
bundled public-suffix list. Browser-marked tests require the extra and Chromium.

[CI](.github/workflows/ci.yml) covers the declared Scrapy/scrapy-poet floors on Python 3.10,
locked dependencies on Python 3.13 and 3.14, a freshly resolved dependency set, and Chromium on Linux.
The older [manual validation report](docs/VALIDATION-2026-08-05.md) is historical evidence;
the executable tests define the current checks. This demo tests integration, while Frostwork's own
[differential gates](https://github.com/scrapy/frostwork/blob/main/docs/TESTING.md) cover the engine.

## Benchmarks

```bash
uv run python -m demo.bench -n 20 --rounds 7
```

No server is needed. `--base http://127.0.0.1:8000` benchmarks pages fetched from a running storefront.
Generation and downloads are outside the timed work. Every stage must return exactly the same values,
keys, ordering and cardinality as Parsel **before any timing starts**.

The report distinguishes flat raw columns, all raw columns including groups, and complete Product
construction with transforms and conversion to a dictionary. Reusable `Page` schemas compile before
timing. Complete-item timings include async dispatch for both implementations. Engine order alternates
between rounds; results show median milliseconds per page and the observed range.

These are synthetic storefront measurements, not general speed guarantees or end-to-end crawl timings.
Run them on your machine and use Frostwork's
[canonical benchmarks](https://github.com/scrapy/frostwork/blob/main/docs/BENCHMARKS.md)
for comparisons across workloads. Contributor builds should use release-mode native code.

## Working on Frostwork itself

The released installation and lockfile remain the default. For an editable local checkout:

```bash
./setup.sh --local ../frostwork
uv run --no-sync pytest -m "not browser"
uv run --no-sync python -m demo.run
```

This installs the locked dependencies, then replaces Frostwork with the editable checkout. It requires
a Rust toolchain. Use `--no-sync` while developing so uv keeps that override. Python edits are picked up
immediately; rerun the local setup command after Rust changes to rebuild the extension.
Run `uv sync --locked --reinstall-package frostwork` to return to the published wheel.

For the browser extra with a local checkout, use `./setup.sh --local ../frostwork --extra browser`.
The library's [Python guide](https://github.com/scrapy/frostwork/blob/main/docs/PYTHON.md)
explains its API and native build process.
