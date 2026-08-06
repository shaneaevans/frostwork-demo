"""Render a catalog product into a heavy, Amazon/Walmart-class HTML page.

A tiny DOM builder (`el`/`txt`/`raw`/`cmt`) feeds a set of components — mega-nav, breadcrumbs, image
gallery, buy-box with variant swatches, spec table, prose description, review list, "customers also
bought" recommendation grids, a footer link-farm, inline SVG icons, and a JSON-LD `Product` island.
The component sizing (`SIZE` knob) is calibrated so a product page lands near Zyte's real-world
shape: ~555 KB median, ~1,800–2,400 elements, tree depth ~18, ~11% inline-SVG elements.
"""
from __future__ import annotations

import html as _html
import json
import random

from . import catalog
from .catalog import slug

# Void (self-closing) HTML elements — rendered without a closing tag.
_VOID = {"img", "input", "br", "hr", "meta", "link", "use", "path", "source", "col"}

# How much chrome/content to emit. Bumping this scales page weight & element count together.
SIZE = {
    "rec_grids": 4,        # "customers also bought" style grids
    "cards_per_grid": 20,  # product cards per grid  (cards dominate the element count)
    "reviews_shown": 24,   # visible review blocks
    "desc_paragraphs": 4,  # marketing prose blocks
    "spec_extra": 8,       # extra spec rows beyond the fixed ones
    "footer_cols": 7,      # footer link-farm columns
    "related_rail": 12,    # small "recently viewed" rail cards
    "state_related": 31,   # full product records embedded in the __APP_STATE__ JSON island
}


# --------------------------------------------------------------------------------- tiny DOM builder
def el(tag, *children, cls=None, **attrs):
    """An element node: (tag, attrs, children). `cls=` sets class; attr underscores become hyphens."""
    a = {}
    if cls is not None:
        a["class"] = cls
    for k, v in attrs.items():
        if v is None:
            continue
        a[k.replace("_", "-")] = v
    kids = [c for c in children if c is not None]
    return (tag, a, kids)


def txt(s):
    return ("#text", _html.escape(str(s)), None)


def raw(s):
    return ("#raw", s, None)


def cmt(s):
    return ("#comment", s, None)


def _attrs_str(a):
    out = []
    for k, v in a.items():
        out.append(f' {k}="{_html.escape(str(v), quote=True)}"')
    return "".join(out)


def render(node, depth=0, buf=None, indent="  "):
    """Pretty-print to HTML with indentation — the inter-tag whitespace mirrors real pages."""
    top = buf is None
    if top:
        buf = []
    tag, a, kids = node
    if tag == "#text":
        buf.append(a)
        return
    if tag == "#raw":
        buf.append(a)
        return
    if tag == "#comment":
        buf.append(f"<!-- {a} -->")
        return
    pad = indent * depth
    if tag in _VOID:
        buf.append(f"{pad}<{tag}{_attrs_str(a)}>")
        return
    # Leaf with a single text/raw child stays on one line.
    if len(kids) == 1 and kids[0][0] in ("#text", "#raw"):
        buf.append(f"{pad}<{tag}{_attrs_str(a)}>{kids[0][1]}</{tag}>")
        return
    if not kids:
        buf.append(f"{pad}<{tag}{_attrs_str(a)}></{tag}>")
        return
    buf.append(f"{pad}<{tag}{_attrs_str(a)}>")
    for k in kids:
        render(k, depth + 1, buf, indent)
    buf.append(f"{pad}</{tag}>")
    return "\n".join(buf) if top else None


# ---------------------------------------------------------------- chrome rng (stable across pages)
_chrome_rng = random.Random(catalog.SITE_SEED ^ 0xC0FFEE)


# ----------------------------------------------------------------------------------- SVG components
def svg_icon(rng, n_paths=2, cls="icon"):
    paths = [el("path", d=_path_data(rng), fill="currentColor") for _ in range(n_paths)]
    return el("svg", el("g", *paths), viewBox="0 0 32 32", width="24", height="24",
              cls=cls, aria_hidden="true", role="img")


def _path_data(rng):
    pts = [f"{rng.randint(0, 32)} {rng.randint(0, 32)}" for _ in range(rng.randint(3, 7))]
    return "M" + " L".join(pts) + " Z"


def icon_sprite(rng, n=10):
    syms = [el("symbol", el("path", d=_path_data(rng), fill="currentColor"),
               id=f"i-{i}", viewBox="0 0 32 32") for i in range(n)]
    return el("svg", *syms, style="display:none", aria_hidden="true")


def stars(value, count=None):
    """Visible star rating as spans (kept off SVG so the SVG share stays realistic)."""
    full = int(round(value))
    kids = [el("span", txt("★" if i < full else "☆"),
               cls="star " + ("on" if i < full else "off")) for i in range(5)]
    if count is not None:
        kids.append(el("span", txt(f"({count})"), cls="rating-count"))
    return el("span", *kids, cls="stars", role="img", aria_label=f"{value} out of 5 stars")


# -------------------------------------------------------------------------------------------- chrome
def mega_nav():
    cols = []
    for dept, subs in catalog.all_departments().items():
        sub_items = []
        for sub, nouns in subs.items():
            links = [el("li", el("a", txt(n), href=f"/c/{slug(dept)}/{slug(sub)}",
                                 cls="nav-sub-link", data_noun=slug(n)), cls="nav-sub-item")
                     for n in nouns]
            sub_items.append(el("div",
                                el("h4", txt(sub), cls="nav-sub-title"),
                                el("ul", *links, cls="nav-sub-list"), cls="nav-sub-col"))
        cols.append(el("li",
                       el("a", txt(dept), href=f"/c/{slug(dept)}", cls="nav-top-link",
                          data_dept=slug(dept)),
                       el("div", *sub_items, cls="nav-flyout"), cls="nav-top-item"))
    return el("nav", el("ul", *cols, cls="nav-menu"), cls="mega-nav", aria_label="Primary")


def site_header():
    r = _chrome_rng
    return el("header",
              el("div",
                 el("a", svg_icon(r, 2, "logo-icon"), el("span", txt("Demporium"), cls="logo-text"),
                    href="/", cls="logo", aria_label="Demporium home"),
                 el("form",
                    el("input", type="search", name="q", placeholder="Search products",
                       cls="search-input", aria_label="Search"),
                    el("button", svg_icon(r, 1, "search-icon"), el("span", txt("Search"), cls="sr-only"),
                       type="submit", cls="search-btn"),
                    cls="search", role="search", action="/search", method="get"),
                 el("div",
                    el("a", svg_icon(r, 1), el("span", txt("Account"), cls="label"),
                       href="/account", cls="header-action"),
                    el("a", svg_icon(r, 1), el("span", txt("Cart"), cls="label"),
                       el("span", txt("0"), cls="cart-count"), href="/cart", cls="header-action"),
                    cls="header-actions"),
                 cls="header-inner container"),
              mega_nav(),
              cls="site-header", id="top")


def breadcrumbs(trail):
    items = []
    for i, name in enumerate(trail):
        if i < len(trail) - 1:
            href = "/" if i == 0 else "/c/" + "/".join(slug(t) for t in trail[1:i + 1])
            items.append(el("li", el("a", txt(name), href=href, cls="breadcrumb-link"),
                            cls="breadcrumb-item"))
        else:
            items.append(el("li", el("a", txt(name), href="#", cls="breadcrumb-link",
                                     aria_current="page"), cls="breadcrumb-item active"))
    return el("nav", el("ol", *items, cls="breadcrumb"), cls="breadcrumbs", aria_label="Breadcrumb")


def site_footer():
    r = _chrome_rng
    cols = []
    titles = ["Shop", "About", "Help", "Account", "Policies", "Sellers", "More"]
    for i in range(SIZE["footer_cols"]):
        links = [el("li", el("a", txt(" ".join(r.choice(catalog.LOREM) for _ in range(r.randint(1, 3))).title(),),
                             href="#", cls="footer-link"), cls="footer-item")
                 for _ in range(r.randint(7, 11))]
        cols.append(el("div",
                       el("h3", txt(titles[i % len(titles)]), cls="footer-title"),
                       el("ul", *links, cls="footer-list"), cls="footer-col"))
    social = el("div", *[el("a", svg_icon(r, 1, "social-icon"), href="#", cls="social",
                            aria_label="Social") for _ in range(4)], cls="footer-social")
    return el("footer",
              el("div", el("div", *cols, cls="footer-cols"), social, cls="footer-inner container"),
              el("div", el("p", txt("© 2026 Demporium. A generative demo site for frostwork."),
                           cls="copyright"), cls="footer-legal"),
              cls="site-footer", id="footer")


# ----------------------------------------------------------------------------- product page pieces
def gallery(p):
    main = el("div",
              el("img", src=p["mainImage"], alt=p["name"], cls="gallery-main-img",
                 width="500", height="500", loading="eager", id="main-image"),
              el("button", svg_icon(_chrome_rng, 1, "zoom-icon"), el("span", txt("Zoom"), cls="sr-only"),
                 type="button", cls="zoom-btn"),
              cls="gallery-main")
    thumbs = [el("li",
                 el("button",
                    el("img", src=img, alt=f"{p['name']} view {i + 1}", width="64", height="64",
                       loading="lazy", cls="thumb-img"),
                    type="button", cls="thumb", data_index=str(i)), cls="thumb-item")
              for i, img in enumerate(p["images"])]
    return el("div", main, el("ul", *thumbs, cls="thumb-list"), cls="gallery", id="product-gallery")


def buy_box(p):
    price_block = [el("span", txt(p["currencyRaw"]), cls="price-symbol"),
                   el("span", txt(p["price"]), cls="price-amount", data_price=p["price"])]
    price = el("div", el("span", *price_block, cls="price price_color", itemprop="price"),
               *( [el("span", txt(f'{p["currencyRaw"]}{p["regularPrice"]}'), cls="price-regular was")]
                  if p["regularPrice"] else [] ),
               cls="price-row")

    swatches = []
    seen = []
    for v in p["variants"]:
        key = v["color"]
        if key in seen:
            continue
        seen.append(key)
        swatches.append(el("button", el("span", txt(v["color"]), cls="swatch-label"),
                           type="button", cls="swatch", data_color=slug(v["color"]),
                           data_sku=v["sku"]))
    color_opts = el("div", el("span", txt("Color:"), cls="opt-label"),
                    el("div", *swatches, cls="swatches"), cls="option color-option")

    sizes = [v["size"] for v in p["variants"] if v["size"]]
    size_opts = None
    if sizes:
        uniq = list(dict.fromkeys(sizes))
        size_btns = [el("button", txt(s), type="button", cls="size-btn", data_size=slug(s)) for s in uniq]
        size_opts = el("div", el("span", txt("Size:"), cls="opt-label"),
                       el("div", *size_btns, cls="sizes"), cls="option size-option")

    avail = "In Stock" if p["availability"] == "InStock" else "Out of Stock"
    availability = el("div",
                      el("span", txt(avail), cls="availability " + ("in-stock" if p["availability"] == "InStock" else "out-of-stock"),
                         data_availability=p["availability"]),
                      *( [el("span", txt(f'{p["stock"]} left'), cls="stock-note")] if p["stock"] else [] ),
                      cls="availability-row")

    return el("div",
              el("h1", txt(p["name"]), cls="product-title", itemprop="name"),
              el("div",
                 el("a", txt(p["brand"]), href=f"/b/{slug(p['brand'])}", cls="brand", itemprop="brand"),
                 el("span", txt("·"), cls="sep"),
                 el("a", stars(p["rating"], p["reviewCount"]), href="#reviews", cls="rating-link"),
                 cls="subtitle"),
              price,
              availability,
              color_opts,
              size_opts,
              el("div",
                 el("label", txt("Qty"), for_="qty", cls="qty-label"),
                 el("input", type="number", id="qty", name="qty", value="1", min="1", max="10", cls="qty-input"),
                 el("button", txt("Add to Cart"), type="button", cls="add-to-cart btn-primary"),
                 el("button", svg_icon(_chrome_rng, 1, "wish-icon"), el("span", txt("Save"), cls="label"),
                    type="button", cls="wishlist"),
                 cls="purchase"),
              el("ul",
                 el("li", txt("Free shipping over $35"), cls="perk"),
                 el("li", txt("30-day returns"), cls="perk"),
                 el("li", txt(f"SKU: {p['sku']}"), cls="perk sku", data_sku=p["sku"]),
                 cls="perks"),
              # Client-rendered: EMPTY in the served bytes, filled by `_HYDRATE_JS` from
              # `__APP_STATE__`. It is the one thing on this page a browser is required for, which is
              # what the FrostBrowserPage path in demo/browser.py exists to show.
              el("div", cls="delivery-estimate", id="delivery", data_hydrate="delivery"),
              cls="buy-box", id="buy-box")


def specs_table(p):
    rows = [el("tr", el("th", txt(k), scope="row", cls="spec-key"),
               el("td", txt(v), cls="spec-val", data_key=slug(k)))
            for k, v in p["specs"].items()]
    return el("section",
              el("h2", txt("Product Information"), cls="section-title"),
              el("table", el("tbody", *rows, cls="specs-body"), cls="specs-table",
                 id="product-specs"),
              cls="specs", id="specifications")


def description_section(p):
    feature_items = [el("li", txt(f), cls="feature-item") for f in p["features"]]
    paras = [el("p", raw(_emphasize(para)), cls="desc-para") for para in p["descriptionHtml"]]
    return el("section",
              el("h2", txt("About this item"), cls="section-title"),
              el("ul", *feature_items, cls="feature-list"),
              el("div", *paras, cls="description", id="product-description", itemprop="description"),
              cls="product-overview", id="overview")


def _emphasize(text):
    # Sprinkle a few inline tags so descriptionHtml is genuinely rich markup, like a CMS block.
    words = text.split()
    out = []
    for i, w in enumerate(words):
        if i and i % 11 == 0:
            out.append(f"<strong>{_html.escape(w)}</strong>")
        elif i and i % 17 == 0:
            out.append(f"<em>{_html.escape(w)}</em>")
        else:
            out.append(_html.escape(w))
    return " ".join(out)


def review_block(rv):
    badge = el("span", txt("Verified Purchase"), cls="verified") if rv["verified"] else None
    return el("article",
              el("div", stars(rv["rating"]),
                 el("span", txt(rv["title"]), cls="review-title"), cls="review-head"),
              el("div",
                 el("span", txt(rv["author"]), cls="review-author"),
                 el("time", txt(rv["date"]), datetime=rv["date"], cls="review-date"),
                 badge, cls="review-meta"),
              el("p", txt(rv["body"]), cls="review-body"),
              cls="review", itemprop="review")


def reviews_section(p):
    shown = p["reviews"][:SIZE["reviews_shown"]]
    blocks = [review_block(rv) for rv in shown]
    summary = el("div",
                 el("span", txt(f'{p["rating"]:.1f}'), cls="rating-big"),
                 stars(p["rating"]),
                 el("span", txt(f'{p["reviewCount"]} global ratings'), cls="rating-total"),
                 cls="reviews-summary")
    return el("section",
              el("h2", txt("Customer Reviews"), cls="section-title"),
              summary,
              el("div", *blocks, cls="review-list"),
              cls="reviews", id="reviews")


def product_card(pid):
    p = catalog.product(pid)
    inner = el("div",
               el("a",
                  el("div",
                     el("img", src=p["mainImage"], alt=p["name"], width="200", height="200",
                        loading="lazy", cls="card-img"),
                     svg_icon(_chrome_rng, 1, "card-badge"), cls="card-media"),
                  href=catalog.product_url(pid), cls="card-link", data_pid=str(pid)),
               el("div",
                  el("h3", el("a", txt(p["name"]), href=catalog.product_url(pid), cls="card-title-link"),
                     cls="card-title"),
                  el("div", stars(p["rating"], p["reviewCount"]), cls="card-rating"),
                  el("div",
                     el("span", txt(p["currencyRaw"]), cls="card-price-symbol"),
                     el("span", txt(p["price"]), cls="card-price-amount"),
                     cls="card-price price_color"),
                  el("div", txt(p["brand"]), cls="card-brand"),
                  cls="card-body"),
               cls="card-inner")
    return el("article", inner, cls="product-card product_pod", data_sku=p["sku"])


def product_grid(pids, title, cls="rec-grid"):
    cards = [product_card(pid) for pid in pids]
    return el("section",
              el("h2", txt(title), cls="section-title"),
              el("div", *cards, cls=cls), cls="recommendations", data_count=str(len(cards)))


def recommendations(p):
    related = p["related"]
    grids = []
    titles = ["Customers also bought", "More from " + p["brand"], "Frequently viewed together",
              "Similar items", "Sponsored products", "You might also like"]
    n = SIZE["cards_per_grid"]
    for g in range(SIZE["rec_grids"]):
        chunk = related[g * n:(g + 1) * n]
        if not chunk:
            break
        grids.append(product_grid(chunk, titles[g % len(titles)]))
    return el("div", *grids, cls="rec-section")


def viewed_rail(p):
    pids = p["related"][-SIZE["related_rail"]:]
    cards = [product_card(pid) for pid in pids]
    return el("section",
              el("h2", txt("Recently viewed"), cls="section-title"),
              el("div", *cards, cls="rail"), cls="recently-viewed")


# --------------------------------------------------------------------------------------- JSON-LD
def ld_json_product(p):
    offer = {
        "@type": "Offer", "url": catalog.product_url(int(p["productId"])),
        "price": p["price"], "priceCurrency": p["currency"],
        "availability": f'https://schema.org/{p["availability"]}',
        "itemCondition": "https://schema.org/NewCondition",
    }
    if p["regularPrice"]:
        offer["priceSpecification"] = {"@type": "PriceSpecification", "price": p["regularPrice"],
                                       "priceCurrency": p["currency"]}
    obj = {
        "@context": "https://schema.org/", "@type": "Product",
        "name": p["name"], "sku": p["sku"], "mpn": p["mpn"],
        "gtin13": p["gtin"][0]["value"],
        "brand": {"@type": "Brand", "name": p["brand"]},
        "description": p["description"],
        "image": p["images"], "color": p["color"], "category": "/".join(p["breadcrumbs"][1:-1]),
        "offers": offer,
        "aggregateRating": {"@type": "AggregateRating", "ratingValue": p["rating"],
                            "reviewCount": p["reviewCount"], "bestRating": 5, "worstRating": 1},
        "review": [{"@type": "Review",
                    "author": {"@type": "Person", "name": rv["author"]},
                    "datePublished": rv["date"], "name": rv["title"], "reviewBody": rv["body"],
                    "reviewRating": {"@type": "Rating", "ratingValue": rv["rating"], "bestRating": 5}}
                   for rv in p["reviews"]],
        "additionalProperty": [{"@type": "PropertyValue", "name": k, "value": v}
                               for k, v in p["specs"].items()],
    }
    breadcrumb_ld = {
        "@context": "https://schema.org/", "@type": "BreadcrumbList",
        "itemListElement": [{"@type": "ListItem", "position": i + 1, "name": name}
                            for i, name in enumerate(p["breadcrumbs"])],
    }
    return [el("script", raw(json.dumps(obj)), type="application/ld+json"),
            el("script", raw(json.dumps(breadcrumb_ld)), type="application/ld+json")]


# --------------------------------------------------------------------------------------- head/style
_INLINE_CSS = """
:root{--fg:#0f1111;--muted:#565959;--line:#e3e6e6;--bg:#f3f4f4;--accent:#0a7d62;
  --price:#b12704;--star:#de7921;--header:#131921;--nav:#232f3e;--cta:#ffd814;--cta-line:#e3b800}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--fg);line-height:1.5;
  font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Arial,sans-serif;font-size:15px}
a{color:inherit}
img{max-width:100%}
.container{max-width:1280px;margin:0 auto;padding:0 16px}
.sr-only{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0,0,0,0)}
.section-title{font-size:18px;font-weight:700;margin:0 0 16px;padding-bottom:8px;border-bottom:1px solid var(--line)}

/* header + search */
.site-header{background:var(--header);color:#fff;position:sticky;top:0;z-index:50}
.header-inner{display:flex;gap:20px;align-items:center;padding:10px 16px}
.logo{display:flex;align-items:center;gap:8px;color:#fff;text-decoration:none;font-weight:800;font-size:21px}
.logo-icon{color:var(--accent)}
.logo-text{letter-spacing:-.5px}
.search{flex:1;display:flex;max-width:680px}
.search-input{flex:1;border:0;padding:11px 14px;border-radius:8px 0 0 8px;font-size:15px;color:#111}
.search-btn{border:0;background:var(--accent);color:#fff;padding:0 18px;border-radius:0 8px 8px 0;cursor:pointer;display:flex;align-items:center}
.header-actions{display:flex;gap:18px}
.header-action{color:#fff;text-decoration:none;display:flex;align-items:center;gap:6px;font-size:13px}
.cart-count{background:var(--accent);border-radius:999px;min-width:18px;height:18px;display:inline-flex;align-items:center;justify-content:center;font-size:11px;font-weight:700}

/* mega nav */
.mega-nav{background:var(--nav)}
.nav-menu{display:flex;gap:2px;list-style:none;margin:0 auto;padding:0 8px;max-width:1280px}
.nav-top-item{position:relative}
.nav-top-link{display:block;color:#fff;text-decoration:none;padding:11px 14px;font-size:14px;font-weight:600}
.nav-top-item:hover .nav-top-link{background:rgba(255,255,255,.12)}
.nav-flyout{display:none;position:absolute;top:100%;left:0;background:#fff;color:var(--fg);
  box-shadow:0 12px 28px rgba(0,0,0,.2);padding:20px 24px;gap:32px;border-radius:0 0 10px 10px;min-width:560px;z-index:60}
.nav-top-item:hover .nav-flyout{display:flex}
.nav-sub-title{font-size:12px;margin:0 0 8px;color:var(--muted);text-transform:uppercase;letter-spacing:.5px}
.nav-sub-list{list-style:none;margin:0;padding:0}
.nav-sub-link{color:var(--fg);text-decoration:none;font-size:14px;line-height:2;display:block}
.nav-sub-link:hover{color:var(--accent);text-decoration:underline}

/* breadcrumbs */
.breadcrumbs{padding:14px 0 6px}
.breadcrumb{display:flex;flex-wrap:wrap;align-items:center;gap:6px;list-style:none;margin:0;padding:0;font-size:13px;color:var(--muted)}
.breadcrumb-item+.breadcrumb-item::before{content:"\\203a";margin-right:6px;color:#9aa0a6}
.breadcrumb-link{color:var(--accent);text-decoration:none}
.breadcrumb-link:hover{text-decoration:underline}
.breadcrumb-item.active .breadcrumb-link{color:var(--muted);pointer-events:none;text-decoration:none}

/* product page */
.product-main{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,400px);gap:32px;
  background:#fff;padding:24px;border-radius:12px;border:1px solid var(--line)}
.product-detail-col{display:grid;gap:0}
.product-overview,.specs,.reviews,.recommendations,.recently-viewed{
  background:#fff;border:1px solid var(--line);border-radius:12px;padding:24px;margin-top:20px}
.gallery{display:flex;gap:12px}
.thumb-list{order:-1;display:flex;flex-direction:column;gap:8px;list-style:none;margin:0;padding:0}
.thumb{width:58px;height:58px;border:1px solid var(--line);border-radius:8px;background:#fff;padding:0;cursor:pointer;overflow:hidden}
.thumb:hover{border-color:var(--accent)}
.thumb-img{width:100%;height:100%;object-fit:cover;display:block}
.gallery-main{position:relative;flex:1;border:1px solid var(--line);border-radius:10px;overflow:hidden;background:#fff}
.gallery-main-img{width:100%;display:block;aspect-ratio:1/1;object-fit:cover}
.zoom-btn{position:absolute;bottom:10px;right:10px;background:rgba(255,255,255,.9);border:1px solid var(--line);border-radius:999px;padding:6px;cursor:pointer}
.product-title{font-size:24px;font-weight:600;margin:0 0 8px;line-height:1.25}
.subtitle{display:flex;align-items:center;gap:8px;font-size:14px;margin-bottom:10px}
.brand{color:var(--accent);text-decoration:none;font-weight:600}
.sep{color:#ccc}
.rating-link{text-decoration:none}
.stars{color:var(--star);font-size:15px;letter-spacing:1px;white-space:nowrap}
.star.off{color:#cfcfcf}
.rating-count{color:var(--accent);font-size:13px;margin-left:6px}
.price-row{margin:14px 0;border-top:1px solid var(--line);padding-top:14px}
.price{font-size:30px;color:var(--price);font-weight:600;line-height:1}
.price-symbol{font-size:15px;vertical-align:9px;margin-right:1px}
.price-regular{color:var(--muted);text-decoration:line-through;font-size:15px;margin-left:10px}
.availability-row{margin:10px 0}
.availability{font-weight:600}.availability.in-stock{color:#067d62}.availability.out-of-stock{color:var(--price)}
.stock-note{color:var(--muted);font-size:13px;margin-left:8px;font-weight:400}
.option{margin:14px 0}
.opt-label{display:block;font-size:13px;color:var(--muted);margin-bottom:6px;font-weight:600}
.swatches,.sizes{display:flex;gap:8px;flex-wrap:wrap}
.swatch,.size-btn{border:1px solid #ccc;border-radius:8px;background:#fff;padding:7px 12px;cursor:pointer;font-size:13px}
.swatch:hover,.size-btn:hover{border-color:var(--accent);box-shadow:0 0 0 1px var(--accent)}
.purchase{display:flex;align-items:center;gap:10px;margin:18px 0}
.qty-label{font-size:13px;color:var(--muted)}
.qty-input{width:58px;padding:9px;border:1px solid #ccc;border-radius:8px}
.btn-primary,.add-to-cart{background:var(--cta);border:1px solid var(--cta-line);border-radius:999px;padding:11px 22px;font-weight:600;cursor:pointer;font-size:14px;color:#0f1111}
.add-to-cart:hover{filter:brightness(.97)}
.wishlist{background:#fff;border:1px solid #ccc;border-radius:999px;padding:10px 16px;cursor:pointer;display:flex;gap:6px;align-items:center;font-size:14px}
.perks{list-style:none;margin:16px 0 0;padding:14px 0 0;border-top:1px solid var(--line);font-size:13px;color:var(--muted);display:flex;flex-direction:column;gap:5px}
/* client-rendered (see _HYDRATE_JS): empty in the served HTML, so :empty keeps it invisible */
.delivery-estimate:empty{display:none}
.delivery-estimate{margin-top:12px;padding:10px 12px;border:1px solid var(--line);border-radius:8px;display:flex;gap:10px;align-items:baseline;font-size:13px}
.delivery-window{font-weight:600}
.delivery-cost{color:var(--muted)}

/* overview / specs / reviews */
.feature-list{margin:0 0 16px;padding-left:20px}
.feature-item{margin:5px 0}
.description{color:#333}.desc-para{margin:0 0 12px}
.specs-table{width:100%;border-collapse:collapse;font-size:14px}
.specs-table th{text-align:left;color:var(--muted);font-weight:500;width:32%;padding:10px 12px;vertical-align:top}
.specs-table td{padding:10px 12px}
.specs-table tr:nth-child(odd){background:#f7f8f8}
.reviews-summary{display:flex;align-items:center;gap:14px;margin-bottom:18px}
.rating-big{font-size:34px;font-weight:700;line-height:1}
.rating-total{color:var(--muted);font-size:14px}
.review-list{display:grid;gap:18px}
.review{border-top:1px solid var(--line);padding-top:16px}
.review:first-child{border-top:0;padding-top:0}
.review-head{display:flex;align-items:center;gap:10px}
.review-title{font-weight:600}
.review-meta{display:flex;gap:10px;font-size:12px;color:var(--muted);margin:5px 0}
.verified{color:#067d62;font-weight:600}
.review-body{font-size:14px;color:#333;margin:6px 0 0}

/* product cards + grids */
.rec-grid,.product-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(185px,1fr));gap:16px}
.rail{display:flex;gap:16px;overflow-x:auto;padding-bottom:6px}
.rail .product-card{min-width:190px}
.product-card{background:#fff;border:1px solid var(--line);border-radius:12px;overflow:hidden;transition:box-shadow .15s ease,transform .15s ease}
.product-card:hover{box-shadow:0 8px 22px rgba(0,0,0,.12);transform:translateY(-3px)}
.card-inner{display:flex;flex-direction:column;height:100%}
.card-link{display:block;position:relative}
.card-media{aspect-ratio:1/1;background:#eef0f0;overflow:hidden}
.card-img{width:100%;height:100%;object-fit:cover;display:block}
.card-badge{position:absolute;top:8px;left:8px;background:var(--accent);color:#fff;border-radius:999px;padding:4px}
.card-body{padding:12px;display:flex;flex-direction:column;gap:5px;flex:1}
.card-title{font-size:14px;margin:0;font-weight:500;line-height:1.3}
.card-title-link{color:var(--fg);text-decoration:none;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.card-title-link:hover{color:var(--accent)}
.card-rating .stars{font-size:12px}
.card-price{color:var(--price);font-weight:700;font-size:17px;margin-top:auto}
.card-price-symbol{font-size:11px;vertical-align:4px}
.card-brand{font-size:12px;color:var(--muted)}

/* listing */
.listing-head{padding:6px 0 16px}
.listing-title{font-size:22px;margin:0}
.result-count{color:var(--muted);margin:4px 0 0}
.listing-body{display:grid;grid-template-columns:220px 1fr;gap:24px;align-items:start}
.filters{background:#fff;border:1px solid var(--line);border-radius:12px;padding:18px;position:sticky;top:96px}
.filters-title{font-size:15px;margin:0 0 10px}
.filter-list{list-style:none;margin:0;padding:0}
.filter-link{color:var(--accent);text-decoration:none;font-size:14px;line-height:2.1}
.filter-link:hover{text-decoration:underline}
.listing-results .product-grid{background:#fff;border:1px solid var(--line);border-radius:12px;padding:18px}
.pagination{display:flex;gap:14px;align-items:center;justify-content:center;padding:22px;font-size:14px}
.page-prev,.page-next{color:var(--accent);text-decoration:none;font-weight:600}
.page-info{color:var(--muted)}

/* home hero */
.hero{background:linear-gradient(120deg,var(--nav),var(--accent));color:#fff;border-radius:16px;padding:52px 40px;margin:18px 0 26px}
.hero-title{font-size:36px;margin:0 0 8px}
.hero-sub{font-size:17px;opacity:.92;margin:0 0 20px}
.hero-cta{display:inline-block;text-decoration:none}

/* footer */
.site-footer{background:var(--header);color:#dfe3e6;margin-top:36px}
.footer-inner{padding:36px 16px;max-width:1280px;margin:0 auto}
.footer-cols{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:26px}
.footer-title{font-size:14px;color:#fff;margin:0 0 12px}
.footer-list{list-style:none;margin:0;padding:0}
.footer-link{color:#aab2b8;text-decoration:none;font-size:13px;line-height:2.1}
.footer-link:hover{color:#fff;text-decoration:underline}
.footer-social{display:flex;gap:14px;margin-top:20px}
.social{color:#fff}
.footer-legal{border-top:1px solid #3a4553;padding:18px 16px;text-align:center}
.copyright{margin:0;font-size:12px;color:#8b969d}

@media(max-width:900px){.product-main{grid-template-columns:1fr}.listing-body{grid-template-columns:1fr}.filters{position:static}}
"""


def placeholder_svg(pid: int, index: int = 0) -> str:
    """A deterministic SVG product-image placeholder (gradient tile + brand) served for the catalog's
    `/static/img/...` URLs — so the storefront looks real without shipping any binary assets."""
    p = catalog.product(pid)
    hue = (pid * 47 + index * 17) % 360
    c1 = f"hsl({hue} 52% 60%)"
    c2 = f"hsl({(hue + 42) % 360} 58% 42%)"
    initial = _html.escape((p["brand"][:1] or "?").upper())
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 400" width="400" height="400" '
        f'role="img" aria-label="{_html.escape(p["name"])}">'
        f'<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1">'
        f'<stop offset="0" stop-color="{c1}"/><stop offset="1" stop-color="{c2}"/></linearGradient></defs>'
        '<rect width="400" height="400" fill="url(#g)"/>'
        '<circle cx="200" cy="160" r="96" fill="rgba(255,255,255,.16)"/>'
        f'<text x="200" y="196" font-family="system-ui,Arial,sans-serif" font-size="104" '
        f'font-weight="700" fill="#fff" text-anchor="middle">{initial}</text>'
        f'<text x="200" y="300" font-family="system-ui,Arial,sans-serif" font-size="28" '
        f'font-weight="600" fill="#fff" text-anchor="middle">{_html.escape(p["brand"])}</text>'
        f'<text x="200" y="336" font-family="system-ui,Arial,sans-serif" font-size="18" '
        f'fill="rgba(255,255,255,.85)" text-anchor="middle">{_html.escape(p["noun"])}</text>'
        '</svg>'
    )

# A chunk of minified-looking inline JS — real storefronts ship a lot of it inline in the document.
_INLINE_JS = (
    "(function(){var s=window.__APP_STATE__||{};function q(x){return document.querySelector(x)}"
    "function fmt(n){return '$'+Number(n).toFixed(2)}var cart=[];function add(id){cart.push(id);"
    "var c=q('.cart-count');if(c)c.textContent=String(cart.length)}document.addEventListener('click',"
    "function(e){var t=e.target.closest('[data-pid]');if(t){/* track */}});window.addToCart=add;"
    "var io=window.IntersectionObserver?new IntersectionObserver(function(es){es.forEach(function(x){"
    "if(x.isIntersecting){var i=x.target;if(i.dataset&&i.dataset.src){i.src=i.dataset.src}}})}):null;"
    "if(io){document.querySelectorAll('img[loading=lazy]').forEach(function(i){io.observe(i)})}"
    "function gallery(){var t=document.querySelectorAll('.thumb');var m=q('#main-image');"
    "t.forEach(function(b){b.addEventListener('click',function(){var im=b.querySelector('img');"
    "if(im&&m){m.src=im.src}})})}gallery();})();"
) * 3


# Hydration: the ONLY thing on the page whose markup a browser has to produce. Kept separate from
# `_INLINE_JS` because that string is repeated (`* 3`) for weight and this must run exactly once.
# Written into `.buy-box > #delivery`, which is served empty — see `buy_box()`.
_HYDRATE_JS = (
    "(function(){var s=window.__APP_STATE__||{},d=document.getElementById('delivery');"
    "if(!d||!s.delivery)return;var w=document.createElement('span');w.className='delivery-window';"
    "w.textContent=s.delivery.window;var c=document.createElement('span');"
    "c.className='delivery-cost';c.textContent=s.delivery.cost;c.setAttribute('data-free',"
    "String(s.delivery.free));d.appendChild(w);d.appendChild(c);"
    "d.setAttribute('data-hydrated','1')})();"
)


def _delivery(p):
    """The client-rendered delivery promise. Derived from the product record (no randomness), so the
    browser path has a value the direct path can be checked against."""
    days = 2 if p["stock"] > 100 else 5 if p["stock"] else 14
    free = float(p["price"]) >= 35
    return {"window": f"Arrives in {days}–{days + 2} days",
            "cost": "Free delivery" if free else "$4.99 delivery", "free": free}


def _app_state(p):
    """A big inline JSON state island — the single most realistic way to add page weight, mirroring
    the data blobs (Next.js / Redux / app-state) that dominate real storefront HTML."""
    def card_record(rec):
        return {"id": rec["productId"], "name": rec["name"], "brand": rec["brand"],
                "price": rec["price"], "currency": rec["currency"], "rating": rec["rating"],
                "reviewCount": rec["reviewCount"], "image": rec["mainImage"],
                "url": catalog.product_url(int(rec["productId"])), "sku": rec["sku"],
                "breadcrumbs": rec["breadcrumbs"]}
    related_full = [catalog.product(r) for r in p["related"][:SIZE["state_related"]]]
    return {
        "product": p,
        "delivery": _delivery(p),                 # rendered into the DOM by `_HYDRATE_JS`, never by us
        "recommendations": [card_record(r) for r in related_full],
        "relatedDetail": related_full,            # full records (carry their own reviews -> weight)
        "config": {"currency": "USD", "locale": "en-US", "freeShippingThreshold": 35,
                   "features": {"reviews": True, "qa": True, "wishlist": True, "compare": True},
                   "experiments": {f"exp_{i}": bool(i % 2) for i in range(24)}},
        "i18n": {k: " ".join(catalog.LOREM[:6]) for k in
                 ["addToCart", "buyNow", "outOfStock", "inStock", "freeShipping", "returns",
                  "writeReview", "seeAll", "sponsored", "verifiedPurchase"]},
    }


def data_islands(p):
    return [
        el("script", raw(json.dumps(_app_state(p))), type="application/json", id="__APP_STATE__"),
        el("script", raw("window.__APP_STATE__=JSON.parse(document.getElementById('__APP_STATE__').textContent);")),
        el("script", raw(_INLINE_JS)),
        el("script", raw(_HYDRATE_JS)),
    ]


def _head(title, description, canonical, extra=()):
    metas = [
        el("meta", charset="utf-8"),
        el("meta", name="viewport", content="width=device-width, initial-scale=1"),
        el("meta", name="description", content=description),
        el("meta", name="robots", content="index,follow"),
        el("meta", property="og:type", content="product"),
        el("meta", property="og:title", content=title),
        el("meta", property="og:description", content=description),
        el("meta", property="og:site_name", content="Demporium"),
        el("meta", name="twitter:card", content="summary_large_image"),
        el("meta", name="theme-color", content="#0a7"),
    ]
    links = [
        el("link", rel="canonical", href=canonical),
        el("link", rel="preconnect", href="/static"),
        el("link", rel="icon", href="/static/favicon.ico"),
        el("link", rel="stylesheet", href="/static/app.css"),
        el("link", rel="preload", href="/static/app.js", as_="script"),
    ]
    return el("head",
              el("title", txt(title)),
              *metas, *links, *extra,
              el("style", raw(_INLINE_CSS)),
              cls=None)


def _document(head, body_children, body_cls="page"):
    doc = el("html",
             head,
             el("body", *body_children, cls=body_cls, id="default"),
             lang="en")
    return "<!DOCTYPE html>\n" + render(doc)


# ----------------------------------------------------------------------------------- page assembly
def product_page(pid):
    p = catalog.product(pid)
    title = f'{p["name"]} | Demporium'
    desc = p["description"][:155]
    canonical = f'http://{{HOST}}{catalog.product_url(pid)}'
    head = _head(title, desc, canonical, extra=ld_json_product(p))
    # A few nested layout wrappers — mirrors the wrapper-div depth of real storefront markup.
    content = el("div",
                 el("div", gallery(p), buy_box(p), cls="product-main", id="product",
                    itemscope="", itemtype="https://schema.org/Product"),
                 el("div",
                    description_section(p),
                    specs_table(p),
                    reviews_section(p), cls="product-detail-col"),
                 cls="product-layout")
    main = el("main",
              breadcrumbs(p["breadcrumbs"]),
              el("div", el("div", content, cls="page-grid"), cls="page-inner"),
              recommendations(p),
              viewed_rail(p),
              cls="container product-page")
    body = [
        cmt("Demporium product page — generated for the frostwork demo"),
        site_header(),
        main,
        site_footer(),
        *data_islands(p),
        cmt("end product page"),
    ]
    return _document(head, body, body_cls="page product")


def listing_page(department=None, subcategory=None, page=1):
    ids, total = catalog.listing(department, subcategory, page)
    per_page = 24
    pages = max(1, (total + per_page - 1) // per_page)
    crumbs = ["Home"]
    if department:
        crumbs.append(department.replace("-", " ").title())
    if subcategory:
        crumbs.append(subcategory.replace("-", " ").title())
    title = " / ".join(crumbs) + " | Demporium"
    base = "/c/" + "/".join(x for x in [department, subcategory] if x) if (department or subcategory) else "/c"

    cards = [product_card(pid) for pid in ids]
    pager = []
    if page > 1:
        pager.append(el("a", txt("Previous"), href=f"{base}?page={page-1}", cls="page-prev", rel="prev"))
    pager.append(el("span", txt(f"Page {page} of {pages}"), cls="page-info"))
    if page < pages:
        pager.append(el("a", txt("Next"), href=f"{base}?page={page+1}", cls="page-next", rel="next"))

    filters = el("aside",
                 el("h2", txt("Filters"), cls="filters-title"),
                 el("ul", *[el("li", el("a", txt(b), href="#", cls="filter-link"), cls="filter-item")
                            for b in catalog.BRANDS[:12]], cls="filter-list"),
                 cls="filters", id="filters")
    main = el("main",
              breadcrumbs(crumbs),
              el("div",
                 el("h1", txt(" / ".join(crumbs[1:]) or "All products"), cls="listing-title"),
                 el("p", txt(f"{total} results"), cls="result-count"), cls="listing-head"),
              el("div", filters,
                 el("div",
                    el("div", *cards, cls="product-grid"),
                    el("nav", *pager, cls="pagination", aria_label="Pagination"),
                    cls="listing-results"),
                 cls="listing-body"),
              cls="container listing-page")
    head = _head(title, f"Browse {total} products.", f"http://{{HOST}}{base}?page={page}")
    return _document(head, [site_header(), main, site_footer()], body_cls="page listing")


def home_page():
    blocks = []
    pid = 1
    for dept, subs in catalog.all_departments().items():
        ids = list(range(pid, pid + SIZE["cards_per_grid"]))
        pid += SIZE["cards_per_grid"]
        blocks.append(product_grid(ids, dept))
    hero = el("section",
              el("div", el("h1", txt("Everything, generated."), cls="hero-title"),
                 el("p", txt("A synthetic storefront for the frostwork demo."), cls="hero-sub"),
                 el("a", txt("Shop all"), href="/c", cls="hero-cta btn-primary"), cls="hero-inner"),
              cls="hero")
    main = el("main", hero, *blocks, cls="container home-page")
    head = _head("Demporium — generative storefront", "A synthetic storefront for the frostwork demo.",
                 "http://{HOST}/")
    return _document(head, [site_header(), main, site_footer()], body_cls="page home")
