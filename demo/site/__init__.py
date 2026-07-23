"""A local, generative e-commerce website for the frostwork demo.

`catalog.py` is the deterministic data model — a "typical product" shaped like the **Zyte Common
Product Schema**, with field distributions and a page *shape* (size, element count, tree depth, SVG
share) modeled on Zyte's real-world e-commerce corpus (see the table in the README). `render.py`
turns a product into a heavy, Amazon/Walmart-class HTML page; `server.py` serves it.

Nothing is stored on disk and nothing hits the network: every page is generated on the fly from a
seed, so the whole site is reproducible and the crawler has an endless supply of realistic pages.
"""
