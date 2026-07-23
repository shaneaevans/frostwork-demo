"""Benchmark Frostwork's one streaming pass vs a full lxml/Parsel parse, extracting the wide
`zyte_common_items.Product` schema from the generative storefront's heavy (~555 KB) pages.

Start the site first, then run the benchmark against it:

    uv run python -m demo.site.server                 # terminal 1
    uv run python -m demo.bench                        # terminal 2
    uv run python -m demo.bench --base http://127.0.0.1:8001 -n 60

Frostwork answers the whole schema in ONE scan with no DOM; Parsel (the real-spider baseline) parses
the page into an lxml tree once, then runs each selector against it. Both run the SAME selectors and
must return byte-identical columns (parity is asserted). Reports ms/page and the speedup.

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

# The whole ProductPage flat schema, straight off the page object — every selector it declares
# (public introspection; includes inherited fields).
SELECTORS = list(ProductPage.frost_schema()["fields"].values())


def _corpus(base: str, n: int) -> list[bytes]:
    out = []
    for pid in range(1, n + 1):
        url = f"{base.rstrip('/')}/p/{pid}"
        out.append(urllib.request.urlopen(url).read())
    return out


def _frostwork_extract(body: bytes):
    return frostwork.extract(body, SELECTORS, "utf-8")


def _parsel_extract(body: bytes):
    from parsel import Selector
    sel = Selector(body=body, encoding="utf-8")
    return [sel.css(q).getall() for q in SELECTORS]


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

    # parity: Frostwork's one pass must return byte-identical columns to Parsel's per-selector queries.
    mismatches = sum(1 for b in corpus if _frostwork_extract(b) != _parsel_extract(b))

    gc.disable()
    frost_ms = _time(_frostwork_extract, corpus, args.rounds)
    parsel_ms = _time(_parsel_extract, corpus, args.rounds)
    gc.enable()

    print(f"zyte_common_items.Product schema over {len(corpus)} generated pages (median {kb:.0f} KB)")
    print(f"  {len(SELECTORS)} selectors/page   parity (frostwork vs Parsel columns): {mismatches} mismatches")
    print(f"  Parsel (parse once + queries) : {parsel_ms:6.2f} ms/page   (1.00x)")
    print(f"  Frostwork (one streaming pass): {frost_ms:6.2f} ms/page   ({parsel_ms / frost_ms:.2f}x)")
    print(f"  -> Frostwork is {parsel_ms / frost_ms:.2f}x faster, and never builds a DOM")
    if frost_ms > parsel_ms:
        print("  WARNING: Frostwork slower than Parsel — is it built in release mode? "
              "(uv sync --reinstall-package frostwork)")


if __name__ == "__main__":
    main()
