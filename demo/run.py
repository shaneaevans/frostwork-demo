"""Start a local storefront, crawl it, export JSON, and stop the server."""
import argparse
from pathlib import Path
import subprocess
import sys

from demo.crawl import positive_int
from demo.site.server import local_storefront


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spider", choices=["commerce_plain", "commerce_loader", "commerce", "commerce_browser"],
                        default="commerce_plain")
    parser.add_argument("--pages", type=positive_int, default=2, help="listing pages to crawl")
    parser.add_argument("--output", type=Path, default=Path("out/products.json"))
    parser.add_argument("--stats", type=Path)
    args = parser.parse_args()
    with local_storefront() as base:
        command = [sys.executable, "-m", "demo.crawl", args.spider, "--base", base,
                   "--pages", str(args.pages), "--output", str(args.output)]
        if args.stats:
            command.extend(["--stats", str(args.stats)])
        subprocess.run(command, check=True)


if __name__ == "__main__":
    main()
