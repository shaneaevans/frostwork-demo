"""A tiny, dependency-free HTTP server for the generative storefront.

    uv run python -m demo.site.server            # serve on http://127.0.0.1:8000
    uv run python -m demo.site.server --port 8001 --seed 42

Routes (everything is generated on the fly, deterministic per seed):

    GET /                       home page (department rails)
    GET /c                      all-products listing
    GET /c/<dept>[/<sub>]       category listing  (?page=N)
    GET /p/<id>[/<slug>]        product detail page  (the heavy, ~555 KB page)
    GET /robots.txt             permissive
    GET /static/*               tiny stubs (so a browser doesn't 404 on css/js)

Rendered pages are cached by key (deterministic), then the `{HOST}` placeholder in canonical/OG URLs
is filled per request — so repeat hits during a crawl or benchmark are fast and stable.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from functools import lru_cache
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from urllib.parse import urlparse, parse_qs

from . import catalog, render


@lru_cache(maxsize=4096)
def _product_html(pid: int) -> str:
    return render.product_page(pid)


@lru_cache(maxsize=512)
def _listing_html(dept, sub, page) -> str:
    return render.listing_page(dept, sub, page)


@lru_cache(maxsize=1)
def _home_html() -> str:
    return render.home_page()


_STATIC = {
    "app.css": ("text/css", b"/* generated demo stylesheet stub */\n"),
    "app.js": ("application/javascript", b"/* generated demo script stub */\n"),
    "favicon.ico": ("image/x-icon", b""),
}


class Handler(BaseHTTPRequestHandler):
    server_version = "DemporiumDemo/1.0"
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):  # quiet by default
        pass

    def _send(self, body: bytes, status=200, ctype="text/html; charset=utf-8"):
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _send_html(self, html: str, status=200):
        host = self.headers.get("Host", f"{self.server.server_address[0]}:{self.server.server_address[1]}")
        self._send(html.replace("{HOST}", host).encode("utf-8"), status=status)

    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        u = urlparse(self.path)
        parts = [p for p in u.path.split("/") if p]
        qs = parse_qs(u.query)
        page = int(qs.get("page", ["1"])[0] or 1)

        try:
            if not parts:
                return self._send_html(_home_html())
            if parts[0] == "robots.txt":
                return self._send(b"User-agent: *\nAllow: /\n", ctype="text/plain")
            if parts[0] == "static":
                # /static/img/<pid>/<n>.<ext> -> a generated SVG product-image placeholder.
                if len(parts) >= 4 and parts[1] == "img" and parts[2].isdigit():
                    idx_str = parts[3].split(".")[0]
                    idx = int(idx_str) if idx_str.isdigit() else 0
                    svg = render.placeholder_svg(int(parts[2]), idx)
                    return self._send(svg.encode("utf-8"), ctype="image/svg+xml")
                if parts[-1] == "app.css":
                    return self._send(render._INLINE_CSS.encode("utf-8"), ctype="text/css")
                ctype, body = _STATIC.get(parts[-1], ("application/octet-stream", b""))
                return self._send(body, ctype=ctype)
            if parts[0] == "p" and len(parts) >= 2 and parts[1].isdigit():
                return self._send_html(_product_html(int(parts[1])))
            if parts[0] == "c":
                dept = parts[1] if len(parts) >= 2 else None
                sub = parts[2] if len(parts) >= 3 else None
                return self._send_html(_listing_html(dept, sub, page))
        except Exception as e:  # never 500 silently during a crawl
            return self._send(f"error: {e}".encode(), status=500, ctype="text/plain")
        return self._send(b"Not Found", status=404, ctype="text/plain")


def make_server(host="127.0.0.1", port=8000) -> ThreadingHTTPServer:
    return ThreadingHTTPServer((host, port), Handler)


@contextmanager
def local_storefront():
    """Use an available loopback port and always release the server on exit."""
    httpd = make_server(port=0)
    thread = Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{httpd.server_port}"
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=5)


def main():
    ap = argparse.ArgumentParser(description="Serve the generative Demporium storefront.")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--seed", type=int, default=None, help="override the catalog seed")
    args = ap.parse_args()

    if args.seed is not None:
        catalog.SITE_SEED = args.seed
        render._chrome_rng.seed(args.seed ^ 0xC0FFEE)
        _product_html.cache_clear(); _listing_html.cache_clear(); _home_html.cache_clear()

    httpd = make_server(args.host, args.port)
    print(f"Demporium serving {catalog.CATALOG_SIZE} products on http://{args.host}:{args.port}  "
          f"(seed={catalog.SITE_SEED})\n  home: http://{args.host}:{args.port}/\n"
          f"  all:  http://{args.host}:{args.port}/c\n  product: http://{args.host}:{args.port}/p/1\n"
          f"Ctrl-C to stop.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstopping.")
        httpd.shutdown()


if __name__ == "__main__":
    main()
