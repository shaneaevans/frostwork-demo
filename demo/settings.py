"""Scrapy settings. The only frostwork-specific thing here is *nothing* — the integration is
purely through web-poet, which scrapy-poet wires in. frostwork is the extraction backend inside
the page objects, invisible to Scrapy itself."""

BOT_NAME = "demo"
SPIDER_MODULES = ["demo.spiders"]
NEWSPIDER_MODULE = "demo.spiders"

# scrapy-poet: the Addon registers the InjectionMiddleware + the providers that build web-poet inputs
# (notably the HttpResponse, from the ordinary Scrapy download) and inject the page objects into the
# spider callbacks. No Zyte API addon — books.toscrape.com is a static sandbox we fetch over plain HTTP.
ADDONS = {"scrapy_poet.Addon": 300}

# Where scrapy-poet looks for @handle_urls-registered page objects.
SCRAPY_POET_DISCOVER = ["demo.pages", "demo.commerce"]

# scrapy-poet's to_item() is async, so use the asyncio reactor.
TWISTED_REACTOR = "twisted.internet.asyncioreactor.AsyncioSelectorReactor"

# Be a well-behaved guest on the sandbox.
ROBOTSTXT_OBEY = True
CONCURRENT_REQUESTS_PER_DOMAIN = 4
DOWNLOAD_DELAY = 0.25
AUTOTHROTTLE_ENABLED = True
USER_AGENT = "frostwork-demo (+https://github.com/shaneaevans/frostwork)"

TELNETCONSOLE_ENABLED = False
LOG_LEVEL = "INFO"
REQUEST_FINGERPRINTER_IMPLEMENTATION = "2.7"
FEED_EXPORT_ENCODING = "utf-8"

# Developer cache — store every response on disk so re-running the spider replays from disk instead
# of re-fetching books.toscrape.com. The Dummy policy caches and serves everything regardless of
# cache headers (ideal for iterating on page objects). Cache lives in .scrapy/httpcache (gitignored);
# delete it to force a fresh fetch.
HTTPCACHE_ENABLED = True
HTTPCACHE_POLICY = "scrapy.extensions.httpcache.DummyPolicy"
HTTPCACHE_STORAGE = "scrapy.extensions.httpcache.FilesystemCacheStorage"
HTTPCACHE_DIR = "httpcache"
HTTPCACHE_EXPIRATION_SECS = 0  # 0 = entries never expire
HTTPCACHE_IGNORE_HTTP_CODES = []
