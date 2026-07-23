"""Shared price + currency parsing for the demo's page objects.

Two different jobs, two different tools:

* The **amount** -> ``parse_amount``, backed by Zyte's own `price-parser`_. It is robust to
  thousands separators and comma-decimal locales (``"$1,019.00"`` -> ``"1019.00"``,
  ``"€1.299,95"`` -> ``"1299.95"``), where a naive ``[\\d.]+`` regex silently mangles the number
  (``"$1,019.00"`` -> ``"1"``). Reach for it when the amount is embedded in a string with a
  symbol or separators; an already-isolated clean number needs no parsing.
* The **currency code** -> ``symbol_to_currency``, a small explicit symbol->ISO map. No library
  does this step for you: a bare ``"$"`` is ambiguous (USD/CAD/AUD/...), so resolving it is
  site/locale context. This mirrors the Zyte Common Product Schema split — ``currencyRaw`` is the
  symbol as written on the page, ``currency`` is the ISO 4217 code derived from it.

.. _price-parser: https://github.com/scrapinghub/price-parser
"""
from __future__ import annotations

from price_parser import Price

# Symbol -> ISO 4217. Small and explicit on purpose (see the module docstring): the mapping is
# site/locale context, which is why neither price-parser nor zyte-parsers resolves it for you.
SYMBOL_TO_CURRENCY = {"£": "GBP", "$": "USD", "€": "EUR"}


def symbol_to_currency(symbol: str | None) -> str | None:
    """A currency symbol as written on the page (``"£"``) -> its ISO 4217 code (``"GBP"``)."""
    return SYMBOL_TO_CURRENCY.get((symbol or "").strip())


def parse_amount(text: str | None) -> str | None:
    """The price amount as a normalized string — the Zyte schema's ``price`` is a string, e.g.
    ``"10500.99"`` — or ``None`` when there is no amount to parse."""
    if not text:
        return None
    amount = Price.fromstring(text).amount
    return str(amount) if amount is not None else None
