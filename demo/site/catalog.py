"""The catalog — a deterministic, generative data model of a "typical product".

Each product is built from a seed (`SITE_SEED` xor the product id), so the whole site is a closed,
reproducible world: the same id always yields the same product, listing pages page through real ids,
and "related products" link to ids that actually exist.

The field set and value distributions follow the **Zyte Common Product Schema**
(`zyte_common_items.Product`): `name`, `brand`, `price`/`regularPrice`/`currency`, `availability`,
`sku`/`mpn`/`gtin`/`productId`, `breadcrumbs`, `mainImage`/`images`, `aggregateRating`, `features`,
`additionalProperties`, `variants`, `description`/`descriptionHtml`. `render.py` reads this dict and
lays it into JSON-LD + visible HTML; the crawler's page object extracts the same fields back out.
"""
from __future__ import annotations

import hashlib
import random

SITE_SEED = 1742  # change to reshuffle the whole catalog
CATALOG_SIZE = 1000  # number of distinct products the site serves

# --------------------------------------------------------------------------------------- vocabulary
BRANDS = [
    "Aelo", "Northpeak", "Vanta", "Kestrel", "Lumora", "Brightfield", "Oakhaus", "Meridian",
    "Cobalt", "Solace", "Driftwood", "Ironclad", "Pulsewave", "Verda", "Quill & Co", "Halcyon",
    "Summit", "Tidalwave", "Emberly", "Nordkit", "Voltaic", "Cascade", "Pinnacle", "Auralite",
    "Strato", "Fernweh", "Glacier", "Hearthstone", "Wayfarer", "Zephyr",
]
ADJECTIVES = [
    "Premium", "Ultra", "Compact", "Wireless", "Ergonomic", "Insulated", "Stainless", "Organic",
    "Heavy-Duty", "Lightweight", "Adjustable", "Rechargeable", "Smart", "Pro", "Classic", "Deluxe",
    "Portable", "All-Weather", "Travel", "Professional", "Eco", "Magnetic", "Foldable", "Quiet",
]
MATERIALS = ["aluminum", "stainless steel", "bamboo", "recycled plastic", "tempered glass",
             "anodized alloy", "silicone", "oak", "carbon fiber", "ceramic", "merino wool", "leather"]
COLORS = ["Black", "Slate Gray", "Midnight Blue", "Forest Green", "Sand", "Crimson", "White",
          "Rose Gold", "Graphite", "Teal", "Burgundy", "Ivory"]
SIZES = ["XS", "S", "M", "L", "XL", "XXL"]

# A small category tree: each leaf carries a product-noun pool so names read in-category.
CATEGORIES = {
    "Electronics": {
        "Headphones": ["Headphones", "Earbuds", "Headset"],
        "Speakers": ["Speaker", "Soundbar", "Subwoofer"],
        "Wearables": ["Smartwatch", "Fitness Tracker", "Smart Ring"],
        "Accessories": ["Charger", "Power Bank", "Cable", "Adapter"],
    },
    "Home & Kitchen": {
        "Cookware": ["Skillet", "Saucepan", "Dutch Oven", "Stockpot"],
        "Appliances": ["Blender", "Kettle", "Toaster", "Air Fryer"],
        "Storage": ["Container Set", "Organizer", "Shelf", "Bin"],
        "Drinkware": ["Tumbler", "Water Bottle", "Mug", "Carafe"],
    },
    "Outdoor": {
        "Camping": ["Tent", "Sleeping Bag", "Camp Stove", "Lantern"],
        "Hiking": ["Backpack", "Trekking Poles", "Daypack", "Hydration Pack"],
        "Apparel": ["Jacket", "Fleece", "Rain Shell", "Vest"],
    },
    "Office": {
        "Furniture": ["Desk", "Office Chair", "Monitor Stand", "Bookcase"],
        "Supplies": ["Notebook", "Pen Set", "Desk Organizer", "Whiteboard"],
    },
    "Fitness": {
        "Equipment": ["Dumbbell Set", "Kettlebell", "Resistance Bands", "Yoga Mat"],
        "Recovery": ["Massage Gun", "Foam Roller", "Compression Sleeve"],
    },
}

# A lorem pool with a commerce-y flavour for prose / reviews.
LOREM = (
    "engineered precision comfort durable everyday lightweight balance grip premium tested travel "
    "design quality material finish performance reliable versatile compact storage capacity battery "
    "charge wireless seamless intuitive control texture surface coating resistant warranty support "
    "value crafted refined modern minimal sturdy stable smooth quiet efficient powerful trusted"
).split()

REVIEW_OPENERS = [
    "Exactly what I needed.", "Exceeded my expectations.", "Solid build, great value.",
    "Works as described.", "Would buy again.", "A little pricey but worth it.",
    "Better than the brand I had before.", "Does the job perfectly.", "Impressed by the quality.",
    "Comfortable and well made.",
]
FIRST_NAMES = ["Alex", "Sam", "Jordan", "Taylor", "Casey", "Morgan", "Riley", "Jamie", "Quinn",
               "Avery", "Devon", "Harper", "Reese", "Skyler", "Drew", "Noor", "Mateo", "Priya"]


def _rng(pid: int) -> random.Random:
    return random.Random(SITE_SEED ^ (pid * 0x9E3779B1))


def _words(rng: random.Random, lo: int, hi: int) -> str:
    return " ".join(rng.choice(LOREM) for _ in range(rng.randint(lo, hi)))


def _sentence(rng: random.Random) -> str:
    return _words(rng, 8, 18).capitalize() + "."


def _paragraph(rng: random.Random, lo: int = 3, hi: int = 6) -> str:
    return " ".join(_sentence(rng) for _ in range(rng.randint(lo, hi)))


def _ean13(rng: random.Random) -> str:
    digits = [rng.randint(0, 9) for _ in range(12)]
    check = (10 - sum((3 if i % 2 else 1) * d for i, d in enumerate(digits)) % 10) % 10
    return "".join(map(str, digits + [check]))


def _category_path(rng: random.Random) -> tuple[str, str, list[str]]:
    dept = rng.choice(list(CATEGORIES))
    sub = rng.choice(list(CATEGORIES[dept]))
    noun = rng.choice(CATEGORIES[dept][sub])
    return noun, sub, ["Home", dept, sub]


def slug(text: str) -> str:
    out = "".join(c.lower() if c.isalnum() else "-" for c in text)
    while "--" in out:
        out = out.replace("--", "-")
    return out.strip("-")


def category_slug(name: str) -> str:
    return slug(name)


def all_departments() -> dict[str, dict[str, list[str]]]:
    return CATEGORIES


def product(pid: int) -> dict:
    """Build the full product record for `pid` (1..CATALOG_SIZE), deterministically."""
    pid = (pid - 1) % CATALOG_SIZE + 1
    rng = _rng(pid)

    noun, sub, trail = _category_path(rng)
    brand = rng.choice(BRANDS)
    adj = rng.choice(ADJECTIVES)
    adj2 = rng.choice(ADJECTIVES)
    color = rng.choice(COLORS)
    material = rng.choice(MATERIALS)
    name = f"{brand} {adj} {noun}"
    if rng.random() < 0.5:
        name = f"{brand} {adj} {adj2} {noun}"
    model = f"{rng.choice('ABCDEFGHJKLMNPQRSTUVWXYZ')}{rng.randint(100, 999)}"

    # Price: lognormal-ish, snapped to a .99/.95 ending. Median lands around $35.
    base = round(2.0 ** rng.uniform(2.3, 11.0), 2)  # ~$5 .. ~$2000
    price = max(3.99, round(base) - 0.01)
    discounted = rng.random() < 0.45
    regular = round(price * rng.uniform(1.1, 1.6), 2) if discounted else None
    in_stock = rng.random() < 0.9
    stock = rng.randint(1, 240) if in_stock else 0

    rating = round(rng.uniform(3.2, 5.0), 1)
    review_count = int(2 ** rng.uniform(2, 12))  # ~4 .. ~4000

    n_images = rng.randint(4, 8)
    images = [f"/static/img/{pid}/{i}.jpg" for i in range(n_images)]

    n_features = rng.randint(4, 7)
    features = [
        f"{rng.choice(ADJECTIVES)} {material} {rng.choice(['body', 'frame', 'shell', 'build', 'finish'])}",
        f"{_words(rng, 3, 6).capitalize()}",
        f"Up to {rng.randint(6, 48)} hours {rng.choice(['battery', 'runtime', 'use'])}"
        if "Electronics" in trail else f"Holds up to {rng.randint(1, 64)} {rng.choice(['liters', 'items', 'cups'])}",
        f"Backed by a {rng.choice([1, 2, 3, 5, 10])}-year warranty",
    ] + [_words(rng, 3, 7).capitalize() for _ in range(n_features - 4)]

    # additionalProperties — the spec table (name/value pairs).
    specs = {
        "Brand": brand, "Model": model, "Color": color, "Material": material.title(),
        "Weight": f"{round(rng.uniform(0.1, 12.0), 1)} kg",
        "Dimensions": f"{rng.randint(5, 60)} x {rng.randint(5, 60)} x {rng.randint(2, 40)} cm",
        "Country of Origin": rng.choice(["China", "Vietnam", "Germany", "USA", "Japan", "Mexico"]),
        "Warranty": f"{rng.choice([1, 2, 3, 5, 10])} years",
        "Item Weight": f"{round(rng.uniform(0.1, 12.0), 1)} kg",
        "Shipping Weight": f"{round(rng.uniform(0.2, 14.0), 1)} kg",
    }
    for _ in range(rng.randint(4, 9)):
        specs[_words(rng, 1, 2).title()] = _words(rng, 1, 3).title()

    # Variants — color x size combos that share the base price.
    variant_colors = rng.sample(COLORS, k=rng.randint(2, 5))
    variant_sizes = rng.sample(SIZES, k=rng.randint(1, 4)) if rng.random() < 0.6 else [None]
    variants = []
    for c in variant_colors:
        for s in variant_sizes:
            vp = max(3.99, round(price + rng.uniform(-5, 15), 2))
            variants.append({"color": c, "size": s, "price": f"{vp:.2f}",
                             "sku": f"{model}-{slug(c)}" + (f"-{s}" if s else "")})

    # Reviews — feed both JSON-LD and the visible review list.
    n_reviews = min(review_count, rng.randint(8, 30))
    reviews = []
    for _ in range(n_reviews):
        reviews.append({
            "author": f"{rng.choice(FIRST_NAMES)} {rng.choice('ABCDEFGHJKLMNPRSTW')}.",
            "rating": rng.randint(max(1, round(rating) - 2), 5),
            "title": rng.choice(REVIEW_OPENERS),
            "body": _paragraph(rng, 2, 4),
            "date": f"20{rng.randint(20, 25)}-{rng.randint(1, 12):02d}-{rng.randint(1, 28):02d}",
            "verified": rng.random() < 0.8,
        })

    description = _paragraph(rng, 4, 7)
    desc_html_paras = [_paragraph(rng, 3, 6) for _ in range(rng.randint(2, 4))]

    # Related products — deterministic neighbours that exist in the catalog.
    related = [((pid * 7 + k * 53) % CATALOG_SIZE) + 1 for k in range(1, 41)]
    related = [r for r in related if r != pid]

    return {
        "productId": str(pid),
        "sku": f"{slug(brand)[:4].upper()}-{model}",
        "mpn": model,
        "gtin": [{"type": "ean13", "value": _ean13(rng)}],
        "name": name,
        "brand": brand,
        "price": f"{price:.2f}",
        "regularPrice": f"{regular:.2f}" if regular else None,
        "currency": "USD",
        "currencyRaw": "$",
        "availability": "InStock" if in_stock else "OutOfStock",
        "stock": stock,
        "color": color,
        "size": variant_sizes[0] if variant_sizes and variant_sizes[0] else None,
        "rating": rating,
        "reviewCount": review_count,
        "category": sub,
        "department": trail[1],
        "breadcrumbs": trail + [name],
        "noun": noun,
        "mainImage": images[0],
        "images": images,
        "features": features,
        "specs": specs,
        "variants": variants,
        "reviews": reviews,
        "description": description,
        "descriptionHtml": desc_html_paras,
        "related": related,
    }


def listing(department: str | None, subcategory: str | None, page: int, per_page: int = 24):
    """Return (product_ids, total) for a category/department listing page (1-based page)."""
    ids = []
    for pid in range(1, CATALOG_SIZE + 1):
        p = product(pid)
        if department and slug(p["department"]) != slug(department):
            continue
        if subcategory and slug(p["category"]) != slug(subcategory):
            continue
        ids.append(pid)
    total = len(ids)
    start = (page - 1) * per_page
    return ids[start:start + per_page], total


def product_url(pid: int) -> str:
    p = product(pid)
    return f"/p/{pid}/{slug(p['name'])}"
