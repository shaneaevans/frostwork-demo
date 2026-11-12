# Validating frostwork-demo against Frostwork main

> **Historical report.** This records a run on 2026-08-05, against Frostwork main at that date and
> Scrapy 2.11 to 2.17. Frostwork has since moved to the [Scrapy organisation](https://github.com/scrapy/frostwork),
> [frostwork#9](https://github.com/scrapy/frostwork/pull/9) was merged, and the demo now runs on
> Scrapy 2.20 with Frostwork 0.2.2 on Python 3.11 and newer. Library findings below describe Frostwork as it
> was then; check its [changelog](https://github.com/scrapy/frostwork/blob/main/CHANGELOG.md) for what changed.
> The repo's [tests](../tests) define the current checks.

**Library under test:** `frostwork` main as of 2026-08-05, including the web-poet integration work
(`788f4d1`).

**Bottom line:** everything works. Across 14 Scrapy wirings, 4 Scrapy versions, 3 Python versions, 15
encoding shapes and a real Chromium render, Frostwork returned **byte-identical values every time**,
with zero errors and zero deprecation warnings. The defects found were in *this repo's* metadata and
benchmark, not in the engine; the library findings below are all about the edges of the web-poet bridge,
not its core.

## What was validated

| Axis | Configurations | Result |
| --- | --- | --- |
| Scrapy wiring (storefront + books) | 14: `ADDONS` vs manual `DOWNLOADER_MIDDLEWARES`/`SPIDER_MIDDLEWARES`/`REQUEST_FINGERPRINTER_CLASS`; HTTP cache on / replay / off; `CONCURRENT_REQUESTS` 1 / 32 / 64; `HttpCompressionMiddleware` removed; robots on/off; `BaseDupeFilter`; feed-indent variants | 0 errors, **0 item divergences** across configs |
| Scrapy version | 2.11.2, 2.13.3, 2.14.0, 2.17.0 (latest) | identical items on every shared URL |
| Python | 3.12.13, 3.13.5, 3.14.4 | identical items; suite green on all three |
| Encoding (`FrostPage` vs Parsel, same `HttpResponse`) | 15: utf-8 (header / meta / BOM / none), cp1252, latin-1, shift_jis, euc-kr, gb18030, utf-16le BOM, utf-16, windows-1251 via `http-equiv`, and a **mislabelled** response (utf-8 bytes, latin-1 header) | **0 divergences** |
| Browser (`FrostBrowserPage` over a rendered DOM) | scrapy-playwright 0.0.48 / Chromium 1.62, 37 products | 0 errors; wire-visible fields byte-identical to the direct path; client-rendered fields present on 37/37 |
| Whole-item parity vs Parsel | 40 × ~555 KB pages, 11 flat selectors + 6 `Many`/`One` (9 sub-selectors) | **0 mismatches**, flat columns *and* every group row |
| Static audit | `frostwork-audit` over the page objects + `--scan` over the repo | 3/3 schemas OK; 53/53 literal selectors supported |

Measured throughput on the storefront (M-series Mac, py3.13, lxml 6.1, release build):

| | Parsel | Frostwork | ratio |
| --- | --- | --- | --- |
| 11 flat selectors | ~12.6 ms/page | ~1.00 ms/page | ~12.7× |
| whole item (+6 `Many`/`One`) | ~20.6 ms/page | ~1.15 ms/page | **~18×** |

The second row is the interesting one: adding the nested collections costs Frostwork **+0.15 ms** and
Parsel **+8 ms**. That is the one-pass claim showing up as a measurement rather than an assertion.

## Library findings

Ordered by what I'd fix first. None of these blocked anything.

### 1. Nothing documents where a `BrowserResponse` comes from — and `AnyResponse` has no base

**Correction to an earlier draft of this report:** `FrostBrowserPage` is *not* unreachable in
production. `scrapy_zyte_api.providers.ZyteApiProvider` (from `scrapy-zyte-api[provider]`, verified on
0.35.0) declares `BrowserResponse` and `BrowserHtml` among its `provided_classes`, so on the Zyte API
stack `FrostBrowserPage` works with **no extra wiring at all** — the addon registers the provider. That
is the production path and it is fine.

What is actually true is narrower, and splits in two.

**(a) Off Zyte API, the user supplies the provider, and the docs don't say so.** `scrapy-poet` alone
provides `HttpResponse`, `HttpRequest`, `PageParams`, `RequestUrl`, `ResponseUrl`, `Stats`,
`HttpClient` — nothing browser-shaped. So with scrapy-playwright (or Splash, or any other renderer)
`FrostBrowserPage` needs a ~10-line provider, which is what `demo/browser.py:BrowserResponseProvider`
in this repo is. Neither fact — "Zyte API gives you this free" nor "anything else needs a provider" —
appears in `docs/PYTHON.md`; the response-types table names the input type and stops. Two sentences and
a link would close it.

**(b) The better gap: `ZyteApiProvider` also provides `AnyResponse`, and Frostwork has no base for
it.** `web_poet.AnyResponse` wraps *either* a `BrowserResponse` or an `HttpResponse`, and it is the type
scrapy-zyte-api steers browser-capable page objects toward, because it lets the framework decide
whether to pay for rendering per request. A page object on `FrostPage` or `FrostBrowserPage` has already
committed to one.

It works today through the documented `frostwork_input()` hook, and stays injectable — verified against
both branches of the union:

```python
@attrs.define
class AnyPage(FrostFields):
    response: AnyResponse

    def frostwork_input(self):
        inner = self.response.response
        if isinstance(inner, BrowserResponse):
            return str(inner.html).encode("utf-8"), "utf-8"
        body = inner.body if isinstance(inner.body, bytes) else bytes(inner.body)
        return body, inner.encoding

    title = field("h1::text")
# over HttpResponse    -> {'title': 'Café Widget'}
# over BrowserResponse -> {'title': 'Café Widget'}
# is_injectable(AnyPage) -> True
```

That is six lines every Zyte API user writing browser-capable page objects will write identically, and
getting the `HttpResponse` branch subtly wrong (passing `.text` instead of `.body`, or dropping
`.encoding`) is exactly the silent-divergence class the library is otherwise rigorous about. A shipped
`FrostAnyPage` — a third row in the response-types table — looks like the right answer; a docs recipe is
the cheap one.

### 2. `.as_node()` with no processor resolvable puts raw HTML in a typed field, silently

```python
class P(FrostPage, zyte_common_items.pages.ProductPage):
    mainImage = field(".gallery-main").as_node()     # zyte declares no mainImage processor
```
→ `item.mainImage` is `str`: `'<div class="gallery-main">\n <img …'`. A raw HTML string in a field typed
`Image`, nothing raised.

`_frostwork_validate_fields` already refuses five ways of getting `.as_node()` wrong, and the mirror
case (processor + bare element + neither declaration) is a class-definition error. This one is the
remaining hole, and its failure mode is exactly the silently-wrong value the no-fallback contract exists
to prevent.

A hard error at class definition would be wrong — the comment at the handoff is right that a *subclass*
can attach the processor, so a base class declaring `.as_node()` with nothing attached yet is legitimate.
The natural home is therefore the **audit**: `check_schema()` / `frostwork-audit` inspect the concrete
class, are already the consolidated CI report, and are the documented place for advisory findings.
Something like `advisory: field 'mainImage' declares .as_node() but no processor resolves for it on this
class — the node has no consumer and the field will carry element source`. Today the audit reports
selectors only and has no notion of processors.

Related, and worth one sentence in the docs rather than code: when a processor *is* attached but
**declines** the node, a `parsel.Selector` object lands in the item. `images_processor` does this — it is
gated on `str`/`Iterable`, not on node types, so `field(".thumb-list").as_node()` yields
`item.images == <Selector …>`. The docs warn about the reverse (a node processor handed a string); the
node-handed-to-a-value-processor direction is the one `.as_node()` itself can cause. Of the 11 zyte
processors, the node-aware ones are `brand`, `breadcrumbs`, `description`, `descriptionHtml`, `gtin`,
`price`, `rating`, `simple_price`; `images` and `metadata` are not. A table of which names want
`.as_node()` would remove the guesswork entirely.

### 3. `frostwork-audit <path>` cannot audit a page-object module in a package

`docs/PYTHON.md:431` advertises `frostwork-audit myproject/pages.py` as the primary form. On any
page-object module that uses a relative import — which is the norm in a Scrapy project — it fails:

```
$ frostwork-audit demo/commerce.py
frostwork-audit: could not import 'demo/commerce.py': attempted relative import with no known parent package
```

`_load_module` loads a path via `spec_from_file_location` with a synthetic top-level name and puts the
file's *own* directory on `sys.path`, so `from .prices import parse_amount` has no parent package to
resolve against. `demo/commerce.py` in this repo is an ordinary web-poet page-object module; it cannot
be audited by the documented invocation.

The dotted form works but needs `PYTHONPATH=.` — the CLI doesn't put the CWD on `sys.path` the way
`python -m` does:

```
$ frostwork-audit demo.commerce          # No module named 'demo'
$ PYTHONPATH=. frostwork-audit demo.commerce
OK  ProductFields  (members 17/128, sib-bits 0/64)
OK  ProductPage    (members 17/128, sib-bits 0/64)
OK  NavigationPage (members 2/128, sib-bits 0/64)
3/3 schema(s) OK
```

Two small fixes: insert `os.getcwd()` into `sys.path`, and when given a path, walk up while
`__init__.py` exists to derive the dotted name and import *that* instead of exec'ing the file. Both
make the advertised command work in the project layout the docs assume.

Also: `frostwork-audit a.py b.py` prints `the schema audit takes ONE module target` and exits 2. Correct
behaviour, but auditing a project's page objects usually means several modules, and `--scan` (which does
take many) answers a different question. Accepting N module targets would be a natural fit.

### 4. Small gate gaps

- **`Many(".card")` with no subfields is accepted** and yields `[{}, {}]` — one empty dict per matched
  container. `One(".card")` yields `{}`. A group with no subfields can't produce anything; given how
  thoroughly the neighbouring declarations are refused, this one looks like an oversight.
- **`field(123)` raises PyO3's bare `TypeError: 'int' object is not an instance of 'str'`** — no field
  name, no mention of Frostwork. Every other error in this library names the field and the fix; this one
  is the odd one out.
- **A malformed XPath is reported as unsupported rather than malformed.** `field("//a[@href")` (missing
  `]`) gives *"outside the supported downward-XPath subset (child/descendant steps, `*`/tag tests,
  attribute predicates, …)"*, which sends the reader looking for a supported alternative instead of the
  typo. Worth distinguishing "did not parse" from "parsed, not supported".

### What was notably good

Worth saying, because it is the bulk of what I exercised:

- **Encoding handling is exactly as advertised.** 15 shapes including UTF-16, BOM-only, meta-only,
  `http-equiv`, and a deliberately mislabelled response — byte-identical to Parsel on all of them. This
  is the contract most likely to break quietly in a crawler, and it doesn't.
- **The error messages are the best part of the library.** Nine of the ten common mistakes I tried
  produced a message that named the field, said what was wrong, and gave the fix — `re_first` on
  `all=True` pointing at `join=`/`.map()`, a subfield `out=` explaining that web-poet only sees the
  group, `field()` on a plain `WebPage` explaining that `to_item()` would silently omit the field.
- **`FrostFields` as a response-agnostic field bundle works exactly as the MRO-merging commit implies.**
  `class ProductFields(FrostFields)` + `ProductPage(ProductFields, FrostPage)` +
  `ProductBrowserPage(ProductFields, FrostBrowserPage)` shares one schema across both response
  contracts, verbatim, with `Returns[...]` and `skip_nonitem_fields` intact. This repo now uses it, and
  it is what makes the direct-vs-browser comparison a real assertion rather than two hand-kept copies.
- **`frost_schema()` is the right introspection hook.** The benchmark, the parity tests and the audit
  all read the schema off the class instead of duplicating selector lists.
- **Nested-collection parity holds at the row level**, not just per column — 40 pages × 6 groups
  compared against Parsel's per-container `.css()`, 0 mismatches.

## Documentation findings

1. **`docs/PYTHON.md`, the processors example, is wrong in its comment.**
   ```python
   images = field("img.hero::attr(src)", all=True)   # a SCALAR terminal: stays a list of str
   ```
   It does not stay a list of str. `images_processor` is attached by name on a
   `zyte_common_items.pages.ProductPage` subclass and converts a `list[str]` into `list[Image]`.
   Measured: `[Image(url='/static/img/3/0.jpg'), …]`. The executed test for that block
   (`tests/test_doc_examples.py:145`) asserts `[Image(url="/i/hero.jpg")]` and its inline comment ("a
   scalar terminal: URL strings, not a node") is correct — so the code is gated and the prose isn't. On
   the one line a Zyte user is most likely to copy, the comment teaches the opposite of what happens.

2. **The response-types table doesn't say where each input comes from** — see library finding 1. A
   reader who picks `FrostBrowserPage` off that table learns the type but not that Zyte API supplies it
   free and everything else needs a provider, nor that `AnyResponse` exists and is what scrapy-zyte-api
   prefers.

3. **Nothing documents which zyte processors want `.as_node()`.** The prose says "most zyte-common-items
   processors want an lxml/parsel node", which is true (8 of 11), but the exceptions are the ones that go
   wrong silently, and `images` is among the most-used fields in the schema.

4. **A small honesty note in `docs/PYTHON.md`'s install block.** It documents
   `maturin develop --release --extras=webpoet`, but the demo's `uv sync` path is what most people will
   use and the release-mode caveat lives only in this repo's README. One line pointing at it would help,
   since a debug build silently makes every benchmark meaningless.

Everything else in `docs/PYTHON.md` matched behaviour when I tried it: the `strict=`/`check` semantics,
the `frost_schema()` shape, the `.map()`/`.re_first()`/processor composition order, the `re_first`-on-a-
list refusal, the `Many`/`One` first-match-by-default rule, and the subtree-local caveat on `.as_node()`.

## Fixed in this repo

Two of these are real bugs a fresh clone would hit.

- **`pyproject.toml`: `scrapy-poet>=0.24` → `>=0.26`.** `scrapy_poet.Addon` (which `demo/settings.py`
  wires the whole integration through) first appears in 0.26.0. On 0.24 or 0.25 **every crawl dies at
  startup**: `NameError: Module 'scrapy_poet' doesn't define any object named 'Addon'`. Reproduced on a
  clean 0.24.0 env.
- **`pyproject.toml`: `scrapy>=2.11` → `>=2.14`.** Scrapy below 2.14 does not cap Twisted, and Twisted
  ≥25.5 dropped `_setAcceptableProtocols`, which those releases import — so a fresh resolve of
  `scrapy==2.11` + current Twisted cannot load a download handler. The demo code itself runs fine on
  2.11.2 with Twisted pinned to 24.11 (verified, items identical), so this is about not advertising an
  uninstallable floor.
- **`demo/settings.py`: dropped `REQUEST_FINGERPRINTER_IMPLEMENTATION = "2.7"`.** Removed from Scrapy
  entirely (no occurrences in 2.17.0); it was a dead setting.
- **`demo/bench.py` now benchmarks the whole item.** It measured only the 11 flat selectors while the
  README claimed "*every* field rides the one scan — including the nested collections". It now times
  both halves via `frostwork.extract_grouped` and asserts parity over every group row. The correction
  *raises* the ratio (13× → 18×), because the collections are where a one-pass engine wins most.
- **README benchmark numbers refreshed** (were ~22 ms / ~0.8 ms / ~28×; measured ~20.6 / ~1.15 / ~18×).
- **New: the browser path.** `demo/browser.py` (provider + `ProductBrowserPage` +
  `NavigationBrowserPage`), `demo/spiders/commerce_browser.py`, `tests/test_browser.py` (6 tests), a
  `browser` optional extra, and a README section. `demo/commerce.py`'s schema moved onto
  `ProductFields(FrostFields)` so both response contracts share it. The storefront's buy box now serves
  `#delivery` empty and hydrates it from `__APP_STATE__`, so the browser path reaches a field the direct
  path provably cannot — and the parity test has something real to compare.

`uv.lock` was refreshed to latest (scrapy 2.17.0, cssselect 1.5.0, lxml 6.1.1, cryptography 50).

## Addendum: can the `str` → UTF-8 step be avoided? (built, measured, mostly no)

`FrostBrowserPage.frostwork_input` did `response.html.encode("utf-8")`, and the `AnyResponse` recipe
above had to do the same. That allocates a second copy of the document per response, so it looked worth
removing: on the demo's 530 KB page `str.encode()` is ~0.14 ms against a ~1.12 ms scan — **12% of the
combined cost**.

Implemented in [frostwork#9](https://github.com/scrapy/frostwork/pull/9): an `Html` input enum at the PyO3
boundary so `bytes` and `str` both cross as-is, the `str` arm borrowing CPython's UTF-8 view via
`PyUnicode_AsUTF8AndSize`.

**The 12% turned out to be irreducible.** Measured on the demo page, cold cache, copy cost subtracted:

| scans of one response | 1 | 2 | 4 |
|---|---|---|---|
| ASCII page | +0.8% | +3.3% | +1.0% |
| non-ASCII page | +2.5% | +5.3% | +9.9% |

The reason: that 0.14 ms is a **UCS-2 → UTF-8 transcode**, which CPython must perform for anyone asking
UTF-8 bytes of a non-ASCII `str` — PyO3 pays it too. Only a compact-ASCII `str` is stored as UTF-8
already, and there the copy being removed is a 7 µs memcpy on a 1050 µs scan. One `—` or `£` anywhere in
the document (true of the demo's own pages) puts you in the second row.

What the borrow does buy is **repeat scans**: CPython caches the UTF-8 on the string, so a second page
object over the same `BrowserResponse` pays nothing, where `.encode()` re-transcodes every time. Hence
the growth to ~10% at four scans.

**It costs `abi3-py39` → `abi3-py310`,** which is approved and now done in the same branch. `&str`
extraction does not exist under the 3.9 limited API — the `FromPyObject` impl is
`#[cfg(any(Py_3_10, not(Py_LIMITED_API)))]` and `PyUnicode_AsUTF8AndSize` is not even declared in
`pyo3-ffi` there. Confirmed by compiling: *`the trait bound &str: FromPyObject is not satisfied`*.

**Take it for the interface, not the speed.** A caller should not have to know the engine wants bytes,
and `.encode()` on the hot path is written once per integration and never revisited. It also closes a
footgun the old signature allowed — passing decoded text with a non-UTF-8 label, which would decode
those bytes as cp1252 and quietly produce mojibake. That is now refused, including on the direct `Plan`
call `frostwork.webpoet` uses.

### The floor bump paid for itself somewhere I did not expect

Dropping 3.9 aligned the core with the `webpoet` extra, which already required 3.10 through web-poet —
the wheel had been supporting an interpreter half the package could not be installed on. The useful
consequence was in CI: the `abi3-floor` job **could not run `pytest` at all** on 3.9, because `parsel`,
`web-poet` and `pytest` each require ≥ 3.10. It ran `tools/abi3_smoke.py` as a stand-in, so the floor
was never covered by the real suite. 3.10 is the first version the pinned toolchain installs on, so that
job now runs the same `pytest tests/` as every other interpreter.

Running it there found a latent bug on the first try:

```
RuntimeError: Error calling __set_name__ on '_FrostField' instance 'name' in 'Wrong'
```

`docs/PYTHON.md` promised that declaring a `field()` on a non-Frostwork base *"raises `TypeError` at
class definition"*. It does — from `_FrostField.__set_name__` — but **CPython before 3.12 re-raises
anything out of `__set_name__` wrapped in `RuntimeError`**
([gh-77757](https://github.com/python/cpython/issues/77757) stopped that in 3.12). So on 3.10 and 3.11
a user catches `RuntimeError`, not `TypeError`, and two tests asserting `pytest.raises(TypeError)`
failed on the floor while passing on the dev interpreter. The message survives on `__cause__`, so the
diagnosis is not lost — the exception *type* is. Fixed by asserting what is true on every supported
version (class creation fails, the message reaches the user somewhere on the chain, and from 3.12 the
`TypeError` arrives unwrapped — that last clause so the helper still catches a 3.12+ regression), and
by documenting the version-dependence with the `except (TypeError, RuntimeError)` a caller needs.

Worth noting for its own sake: this is a bug that existed for as long as the 3.9 floor did, and the
reason nobody saw it is that the job guarding the floor was the one job in CI that could not run the
suite. A stand-in test that cannot fail the way the real one does is worth re-examining whenever the
constraint that forced it goes away.

**Verified on the branch:** library suite **173 passed on 3.10** (extension rebuilt there), **173 on
3.13**, **176 on 3.14**; the dependency-free `abi3_smoke.py` passes on the floor; the new test helper
still goes red on a wrong message and on nothing raised; `str` and `bytes` return equal columns for
`extract`/`extract_grouped`/`Plan` including non-ASCII; the demo's 14 tests pass; the 15-shape encoding
differential still shows **0 divergences**; and a Chromium crawl extracts **22/22** products with the
client-rendered fields present and 0 divergences from the bytes path.

Two commits, open as [frostwork#9](https://github.com/scrapy/frostwork/pull/9):

```
Let the engine own the str→UTF-8 step, instead of making callers pre-encode
Drop Python 3.9, and let the floor job run the suite it never could
```

## Suggested next steps for the library

1. A `FrostAnyPage` base for `web_poet.AnyResponse` (or the recipe for it), plus two sentences on the
   response-types table saying which stack supplies which input.
2. Fix the `images` comment in the processors example.
3. Teach the audit about processors: report `.as_node()` fields with no resolvable processor.
4. Make `frostwork-audit` work on a package-relative module (CWD on `sys.path`; derive the dotted name
   from a path).
5. Refuse a subfield-less `Many`/`One`.
6. A table of which zyte-common-items processors want `.as_node()`.
7. Merge [frostwork#9](https://github.com/scrapy/frostwork/pull/9) (see the addendum): `str` at the
   boundary, `abi3-py310`, the floor job running the real suite, and the `__set_name__` wrapping fix it
   uncovered.
8. While 3.9 is going: consider whether the `typing.Dict`/`List`/`Tuple` imports in `webpoet.py` and
   `page.py` still need to be there. They are 3.9-era spellings; at a 3.10 floor `dict[...]`/`X | None`
   work at runtime. Left alone in #9 so a whole-file retype would not bury the change under a diff.
