"""Benchmark reusable extraction and complete Product construction against Parsel.

    python -m demo.bench -n 20 --rounds 7

By default pages are generated locally. --base fetches them from an already-running storefront.
Generation/downloads and schema compilation are outside the timing. Exact values, order, keys and
cardinality must agree before ANY timing starts. Results describe this synthetic workload only.
"""
from __future__ import annotations

import argparse
import asyncio
import gc
from importlib.metadata import version
import platform
import statistics
import time
import urllib.request

import attrs
from frostwork import Page
from parsel import Selector
from web_poet import HttpResponse

from demo.commerce import ProductPage
from demo.parsel_reference import product as parsel_product
from demo.site import catalog, render

SCHEMA = ProductPage.frost_schema()


def column_page(grouped):
    page = Page()
    for name, selector in SCHEMA["fields"].items():
        page.field_all(name, selector)
    if grouped:
        for name, (container, subfields) in SCHEMA["groups"].items():
            page.many(name, container, {key: (selector, "all") for key, selector in subfields.items()})
    return page


FLAT_PAGE = column_page(False)
FULL_PAGE = column_page(True)


def _corpus(base, n):
    records = []
    for pid in range(1, n + 1):
        url = (base or "http://benchmark.local").rstrip("/") + catalog.product_url(pid)
        if base:
            with urllib.request.urlopen(url, timeout=30) as response:
                body = response.read()
        else:
            body = render.product_page(pid).replace("{HOST}", "benchmark.local").encode("utf-8")
        records.append((body, url))
    return records


def _frostwork_flat(record):
    return FLAT_PAGE.extract(record[0], encoding="utf-8").to_dict()


def _frostwork_all(record):
    return FULL_PAGE.extract(record[0], encoding="utf-8").to_dict()


def _parsel_columns(record, grouped):
    sel = Selector(body=record[0], encoding="utf-8")
    values = {name: sel.css(query).getall() for name, query in SCHEMA["fields"].items()}
    if grouped:
        for name, (container, subs) in SCHEMA["groups"].items():
            values[name] = [{key: node.css(query).getall() for key, query in subs.items()}
                            for node in sel.css(container)]
    return values


def _parsel_flat(record):
    return _parsel_columns(record, False)


def _parsel_all(record):
    return _parsel_columns(record, True)


async def _frostwork_item(record):
    body, url = record
    return attrs.asdict(await ProductPage(response=HttpResponse(url, body=body, encoding="utf-8")).to_item())


async def _parsel_item(record):
    return attrs.asdict(parsel_product(*record))


def assert_parity(cases, corpus):
    """One equality standard for all stages, before timing any stage."""
    for label, frost, parsel in cases:
        for record in corpus:
            actual, expected = frost(record), parsel(record)
            if actual != expected:
                keys = sorted(key for key in actual.keys() | expected.keys()
                              if key not in actual or key not in expected or actual[key] != expected[key])
                raise ValueError(f"Parity failed: {label}, {record[1]}, fields={keys}")
            if not actual or not any(actual.values()):
                raise ValueError(f"Empty benchmark workload: {label}, {record[1]}")


def _elapsed(fn, corpus):
    started = time.perf_counter()
    for record in corpus:
        fn(record)
    return (time.perf_counter() - started) * 1000 / len(corpus)


def _measure(frost, parsel, corpus, rounds):
    timings = [[], []]
    enabled = gc.isenabled()
    gc.disable()
    try:
        for repeat in range(rounds):
            # Alternate the engine order so one is not always timed on a colder machine.
            for index in ((0, 1) if repeat % 2 == 0 else (1, 0)):
                timings[index].append(_elapsed((frost, parsel)[index], corpus))
    finally:
        if enabled:
            gc.enable()
    return timings


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", help="fetch from this storefront instead of generating in-process")
    parser.add_argument("-n", type=int, default=20)
    parser.add_argument("--rounds", type=int, default=7)
    args = parser.parse_args(argv)
    if not 1 <= args.n <= catalog.CATALOG_SIZE or args.rounds < 1:
        parser.error(f"-n must be 1..{catalog.CATALOG_SIZE}; --rounds must be positive")
    corpus = _corpus(args.base, args.n)
    loop = asyncio.new_event_loop()
    try:
        cases = [
            ("Flat raw columns", _frostwork_flat, _parsel_flat),
            ("Whole-schema raw columns, including groups", _frostwork_all, _parsel_all),
            ("Complete Product -> dict (transforms, groups and async dispatch included)",
             lambda record: loop.run_until_complete(_frostwork_item(record)),
             lambda record: loop.run_until_complete(_parsel_item(record))),
        ]
        # This also warms the reusable plans, keeping compilation outside every timed stage.
        assert_parity(cases, corpus)
        print(f"Exact parity passed for every page at every stage. Python {platform.python_version()}, "
              f"Frostwork {version('frostwork')}, Parsel {version('parsel')}, lxml {version('lxml')}.")
        print(f"{len(corpus)} synthetic pages; median {statistics.median(len(body) for body, _ in corpus) / 1024:.0f} KiB. "
              f"{args.rounds} alternating rounds; medians in ms/page, observed min..max in brackets.")
        for label, frost, parsel in cases:
            results = _measure(frost, parsel, corpus, args.rounds)
            print(f"\n{label}")
            for name, samples in zip(("Frostwork", "Parsel"), results):
                print(f"  {name}: {statistics.median(samples):.3f} [{min(samples):.3f}..{max(samples):.3f}]")
            print(f"  Parsel/Frostwork median ratio: {statistics.median(results[1]) / statistics.median(results[0]):.2f}x")
    finally:
        loop.close()


if __name__ == "__main__":
    main()
