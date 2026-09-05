"""Run a finite demo crawl and fail on startup, callback, download or empty-feed errors."""
import argparse
import json
from pathlib import Path

from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings


def crawl(spider, base, pages, output, stats_path=None):
    output = Path(output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    settings = get_project_settings()
    settings.set("FEEDS", {str(output): {"format": "json", "overwrite": True}}, priority="cmdline")
    settings.set("HTTPCACHE_ENABLED", False, priority="cmdline")
    settings.set("DOWNLOAD_TIMEOUT", 30, priority="cmdline")
    settings.set("CLOSESPIDER_TIMEOUT", 180, priority="cmdline")
    process = CrawlerProcess(settings)
    crawler = process.create_crawler(spider)
    failures = []
    process.crawl(crawler, base=base, max_pages=pages).addErrback(failures.append)
    process.start()
    stats = crawler.stats.get_stats() if crawler.stats else {}
    if stats_path:
        path = Path(stats_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(stats, indent=2, default=str), encoding="utf-8")
    errors = stats.get("log_count/ERROR", 0) or stats.get("httperror/response_ignored_count", 0) or any(
        value for key, value in stats.items()
        if key.startswith(("spider_exceptions/", "downloader/exception_type_count/"))
    )
    if failures or errors or stats.get("finish_reason") != "finished" or not stats.get("item_scraped_count"):
        raise RuntimeError(f"Crawl failed or produced no items: {failures or stats}")
    items = json.loads(output.read_text(encoding="utf-8"))
    if len(items) != stats["item_scraped_count"]:
        raise RuntimeError("Exported item count differs from the crawl statistics")
    return len(items)


def positive_int(value):
    value = int(value)
    if value < 1:
        raise argparse.ArgumentTypeError("must be positive")
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("spider", choices=["commerce_plain", "commerce_loader", "commerce", "commerce_browser"])
    parser.add_argument("--base", required=True)
    parser.add_argument("--pages", type=positive_int, default=2)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--stats", type=Path)
    args = parser.parse_args()
    count = crawl(args.spider, args.base, args.pages, args.output, args.stats)
    print(f"Exported {count} items to {args.output.resolve()}")


if __name__ == "__main__":
    main()
