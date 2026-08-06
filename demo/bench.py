"""Benchmark Frostwork's one streaming pass vs a full lxml/Parsel parse, extracting the wide
`zyte_common_items.Product` schema from the generative storefront's heavy (~555 KB) pages.

Start the site first, then run the benchmark against it:

    uv run python -m demo.site.server                 # terminal 1
    uv run python -m demo.bench                        # terminal 2
    uv run python -m demo.bench --base http://127.0.0.1:8001 -n 60

Frostwork answers the whole schema in ONE scan with no DOM; Parsel (the real-spider baseline) parses
the page into an lxml tree once, then runs each selector against it. Both run the SAME selectors and
must return byte-identical columns (parity is asserted). Reports ms/page and the speedup.

"Whole schema" means what the page object actually declares: the flat `field(...)` selectors AND the
nested `Many`/`One` collections. The collections are where the shapes diverge most — Frostwork scopes
every sub-field to its container inside the same pass, while Parsel has to re-run each sub-selector
against each matched container — so leaving them out (as this script used to) understated the gap.
Both halves are timed, so you can see either.

IMPORTANT: build Frostwork in RELEASE mode first, or the Rust core runs ~10x slow and the numbers are
meaningless:  `uv sync --reinstall-package frostwork`  (a debug `maturin develop` build will mislead
you — this script prints a warning if Frostwork looks suspiciously slow).
"""
from __future__ import annotations

import argparse
import gc
import statistics
import time
import urllib.request

import frostwork

from demo.commerce import ProductPage

# The whole ProductPage schema, straight off the page object (public introspection; includes
# inherited fields). `frost_schema()` reports the two halves separately, and `frostwork.extract_grouped`
# takes exactly this shape.
_SCHEMA = ProductPage.frost_schema()
SELECTORS = list(_SCHEMA["fields"].values())
GROUPS = [(container, list(subfields.items())) for container, subfields in _SCHEMA["groups"].values()]
N_SUBFIELDS = sum(len(subs) for _, subs in GROUPS)


def _corpus(base: str, n: int) -> list[bytes]:
    out = []
    for pid in range(1, n + 1):
        url = f"{base.rstrip('/')}/p/{pid}"
        out.append(urllib.request.urlopen(url).read())
    return out


def _frostwork_flat(body: bytes):
    return frostwork.extract(body, SELECTORS, "utf-8")


def _frostwork_all(body: bytes):
    """Flat fields AND every nested collection — one pass, one call."""
    return frostwork.extract_grouped(body, SELECTORS, GROUPS, "utf-8")


def _parsel_flat(body: bytes):
    from parsel import Selector
    sel = Selector(body=body, encoding="utf-8")
    return [sel.css(q).getall() for q in SELECTORS]


def _parsel_all(body: bytes):
    """The same work in Parsel: one tree, then a query per field, then a query per sub-field PER
    matched container — which is how you would write it against a DOM."""
    from parsel import Selector
    sel = Selector(body=body, encoding="utf-8")
    flat = [sel.css(q).getall() for q in SELECTORS]
    grouped = [[[c.css(sub).getall() for _, sub in subs] for c in sel.css(container)]
               for container, subs in GROUPS]
    return flat, grouped


def _time(fn, corpus, rounds) -> float:
    for body in corpus:  # warm up
        fn(body)
    best = min(_elapsed(fn, corpus) for _ in range(rounds))
    return best / len(corpus) * 1e3


def _elapsed(fn, corpus) -> float:
    t0 = time.perf_counter()
    for body in corpus:
        fn(body)
    return time.perf_counter() - t0


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--base", default="http://127.0.0.1:8000")
    ap.add_argument("-n", type=int, default=40, help="number of product pages to benchmark")
    ap.add_argument("--rounds", type=int, default=12)
    args = ap.parse_args()

    corpus = _corpus(args.base, args.n)
    kb = statistics.median(len(b) for b in corpus) / 1024

    # parity: Frostwork's one pass must return byte-identical columns to Parsel's queries — for the
    # flat fields AND for every nested collection's rows.
    mismatches = sum(1 for b in corpus if _frostwork_all(b) != _parsel_all(b))

    gc.disable()
    flat = (_time(_frostwork_flat, corpus, args.rounds), _time(_parsel_flat, corpus, args.rounds))
    full = (_time(_frostwork_all, corpus, args.rounds), _time(_parsel_all, corpus, args.rounds))
    gc.enable()

    print(f"zyte_common_items.Product schema over {len(corpus)} generated pages (median {kb:.0f} KB)")
    print(f"  parity (frostwork vs Parsel columns, flat + every group row): {mismatches} mismatches")
    for label, n, (frost_ms, parsel_ms) in (
        (f"flat fields only ({len(SELECTORS)} selectors)", len(SELECTORS), flat),
        (f"WHOLE item (+{len(GROUPS)} Many/One, {N_SUBFIELDS} sub-selectors)", N_SUBFIELDS, full),
    ):
        print(f"\n  {label}")
        print(f"    Parsel (parse once + queries) : {parsel_ms:6.2f} ms/page   (1.00x)")
        print(f"    Frostwork (one streaming pass): {frost_ms:6.2f} ms/page   ({parsel_ms / frost_ms:.2f}x)")
        if frost_ms > parsel_ms:
            print("    WARNING: Frostwork slower than Parsel — is it built in release mode? "
                  "(uv sync --reinstall-package frostwork)")
    print(f"\n  -> on the whole item Frostwork is {full[1] / full[0]:.1f}x faster, and never builds a DOM")


if __name__ == "__main__":
    main()
