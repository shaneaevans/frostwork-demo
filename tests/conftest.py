"""The fixture suite uses tldextract's bundled suffix list, with no background HTTP fetch."""
import tldextract

# Configure before @handle_urls decorators run during test collection. The crawls below run in
# fresh processes against loopback; none depend on an up-to-date public-suffix database.
tldextract.tldextract.TLD_EXTRACTOR = tldextract.TLDExtract(cache_dir=None, suffix_list_urls=())
