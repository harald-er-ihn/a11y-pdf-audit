"""
Service zum Crawlen von Webseiten nach PDF-Dateien.
Strikt auf eine Domain beschränkt (keine Subdomains).
"""

import os
import re
import time
from collections import deque
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from core.utils.error_utils import log_info, log_warning


class CrawlContext:  # pylint: disable=too-few-public-methods
    """Hält den Zustand des Crawlers, um lokale Variablen zu reduzieren."""

    def __init__(self, start_url, output_file, config):
        self.queue = deque([(start_url, 0)])
        self.visited = {start_url}
        self.all_pdfs = set()
        self.pages_scanned = 0
        self.file_handle = open(output_file, "w", encoding="utf-8")
        self.config = config
        self.session = requests.Session()

    def close(self):
        """Schließt Datei-Handles."""
        if self.file_handle:
            self.file_handle.close()


def is_exact_domain(url, allowed_netloc):
    """Versucht, die eingegebene URL valide zu machen."""
    try:
        netloc = urlparse(url).netloc.lower()
        if not netloc:
            return True
        return netloc.replace("www.", "") == allowed_netloc.lower().replace("www.", "")
    except ValueError:
        return False


def _fetch_sitemap(start_url):
    """Versucht, die sitemap.xml zu finden."""
    pdf_links = set()
    parsed = urlparse(start_url)
    sitemaps = [
        f"{parsed.scheme}://{parsed.netloc}/sitemap.xml",
        f"{parsed.scheme}://{parsed.netloc}/sitemap_index.xml",
    ]

    headers = {"User-Agent": "a11y-pdf-audit-bot"}

    for sm_url in sitemaps:
        try:
            resp = requests.get(sm_url, headers=headers, timeout=10)
            if resp.status_code == 200:
                log_info(f"🗺️ Sitemap gefunden: {sm_url}")
                locs = re.findall(r"<loc>(.*?)</loc>", resp.text)
                for loc in locs:
                    if loc.lower().endswith(".pdf"):
                        pdf_links.add(loc)
        except Exception:  # pylint: disable=broad-exception-caught
            pass

    if pdf_links:
        log_info(f"🗺️ {len(pdf_links)} PDFs direkt aus Sitemap extrahiert.")

    return list(pdf_links)


def _extract_links(content, current_url):
    """Parst HTML und gibt absolute Links zurück."""
    soup = BeautifulSoup(content, "html.parser")
    found = []
    for link in soup.find_all("a", href=True):
        href = link["href"].strip()
        if href.startswith(("#", "javascript:", "mailto:", "tel:")):
            continue
        found.append(urljoin(current_url, href))
    return found


def _process_links(links, ctx, depth):
    """Verarbeitet extrahierte Links einer Seite."""
    for full_url in links:
        if full_url.lower().endswith(".pdf"):
            if full_url not in ctx.all_pdfs:
                ctx.all_pdfs.add(full_url)
                fname = os.path.basename(urlparse(full_url).path)
                log_info(f"📄 PDF: {fname}")
                ctx.file_handle.write(full_url + "\n")
                ctx.file_handle.flush()

        elif depth < ctx.config["max_depth"]:
            is_valid_domain = is_exact_domain(full_url, ctx.config["allowed_netloc"])
            is_media = any(
                full_url.lower().endswith(x) for x in [".jpg", ".png", ".zip", ".mp4"]
            )

            if is_valid_domain and full_url not in ctx.visited and not is_media:
                ctx.visited.add(full_url)
                ctx.queue.append((full_url, depth + 1))


def crawl_site_logic(
    start_url, output_file, max_pages=50, max_depth=1, user_agent="Bot"
):
    """Hauptfunktion des Crawlers."""
    allowed_netloc = urlparse(start_url).netloc.lower()
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    allowed_netloc = urlparse(start_url).netloc.lower()  # Hier einmal klein machen
    log_info(f"Crawler Scope: Nur {allowed_netloc}")

    config = {
        "max_depth": max_depth,
        "allowed_netloc": allowed_netloc,
        "user_agent": user_agent,
    }

    ctx = CrawlContext(start_url, output_file, config)

    try:
        # Sitemap Check
        sitemap_pdfs = _fetch_sitemap(start_url)
        ctx.all_pdfs.update(sitemap_pdfs)
        ctx.file_handle.write(f"# Crawl Results for {start_url}\n\n")
        for pdf in sitemap_pdfs:
            ctx.file_handle.write(pdf + "\n")

        # BFS Crawl
        while ctx.queue and ctx.pages_scanned < max_pages:
            url, depth = ctx.queue.popleft()

            if ctx.pages_scanned % 10 == 0 or depth == 0:
                log_info(f"[{ctx.pages_scanned+1}/{max_pages}] T{depth}: {url}")

            try:
                # HEAD Request
                try:
                    head = ctx.session.head(
                        url, headers={"User-Agent": user_agent}, timeout=5
                    )
                    ctype = head.headers.get("Content-Type", "").lower()
                    if "text/html" not in ctype:
                        ctx.pages_scanned += 1
                        continue
                except Exception:  # pylint: disable=broad-exception-caught
                    pass

                # GET Request
                resp = ctx.session.get(
                    url, headers={"User-Agent": user_agent}, timeout=10
                )
                links = _extract_links(resp.content, url)
                _process_links(links, ctx, depth)

            except Exception as err:  # pylint: disable=broad-exception-caught
                log_warning(f"Fehler bei {url}: {err}")

            ctx.pages_scanned += 1
            time.sleep(0.2)

    finally:
        ctx.close()

    log_info(f"[-] Crawler fertig. Total PDFs: {len(ctx.all_pdfs)}")
    return list(ctx.all_pdfs)
