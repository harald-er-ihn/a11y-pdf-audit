"""
Service zum Crawlen von Webseiten nach PDF-Dateien.
Strikt auf eine Domain beschränkt.
"""

import os
import re
import time
from collections import deque
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from core.utils.error_utils import log_info, log_warning


class CrawlContext:
    """Hält den Zustand des Crawlers und verwaltet Ressourcen."""

    def __init__(self, start_url, output_file, config):
        self.queue = deque([(start_url, 0)])
        self.visited = {start_url}
        self.all_pdfs = set()
        self.pages_scanned = 0
        self.config = config
        self.session = requests.Session()
        # Öffne die Datei im Append-Modus
        # pylint: disable=consider-using-with
        self.file_handle = open(output_file, "a", encoding="utf-8")

    def log_pdf(self, url):
        """Speichert eine gefundene PDF-URL."""
        if url not in self.all_pdfs:
            self.all_pdfs.add(url)
            self.file_handle.write(url + "\n")
            self.file_handle.flush()
            return True
        return False

    def close(self):
        """Schließt Datei-Handles und Sessions."""
        if self.file_handle:
            self.file_handle.close()
        if self.session:
            self.session.close()


def is_exact_domain(url, allowed_netloc):
    """Prüft, ob die URL zur erlaubten Domain gehört."""
    try:
        netloc = urlparse(url).netloc.lower()
        if not netloc:
            return True
        return netloc.replace("www.", "") == allowed_netloc.replace("www.", "")
    except ValueError:
        return False


def _fetch_sitemap(start_url):
    """Versucht, PDFs aus der Sitemap zu extrahieren."""
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
        except requests.RequestException:
            pass

    if pdf_links:
        log_info(f"🗺️ {len(pdf_links)} PDFs aus Sitemap extrahiert.")
    return list(pdf_links)


def _extract_links(content, current_url):
    """Extrahiert alle validen Links aus HTML Content."""
    soup = BeautifulSoup(content, "html.parser")
    found = []
    for link in soup.find_all("a", href=True):
        href = link["href"].strip()
        if href.startswith(("#", "javascript:", "mailto:", "tel:")):
            continue
        found.append(urljoin(current_url, href))
    return found


def _process_links(links, ctx, depth):
    """Filtert und verarbeitet gefundene Links."""
    for full_url in links:
        if full_url.lower().endswith(".pdf"):
            if ctx.log_pdf(full_url):
                fname = os.path.basename(urlparse(full_url).path)
                log_info(f"📄 PDF: {fname}")

        elif depth < ctx.config["max_depth"]:
            is_valid = is_exact_domain(full_url, ctx.config["allowed_netloc"])
            is_media = any(
                full_url.lower().endswith(x) for x in [".jpg", ".png", ".zip"]
            )

            if is_valid and full_url not in ctx.visited and not is_media:
                ctx.visited.add(full_url)
                ctx.queue.append((full_url, depth + 1))


def crawl_site_logic(
    start_url, output_file, max_pages=50, max_depth=1, user_agent="Bot"
):
    """
    Hauptfunktion des Crawlers.
    """
    allowed_netloc = urlparse(start_url).netloc.lower()

    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    log_info(f"Crawler Scope: Nur {allowed_netloc}")

    config = {
        "max_depth": max_depth,
        "allowed_netloc": allowed_netloc,
        "user_agent": user_agent,
    }

    ctx = CrawlContext(start_url, output_file, config)

    try:
        # Sitemap Check
        for pdf in _fetch_sitemap(start_url):
            ctx.log_pdf(pdf)

        ctx.file_handle.write(f"# Crawl Results for {start_url}\n\n")

        # BFS Crawl
        while ctx.queue and ctx.pages_scanned < max_pages:
            url, depth = ctx.queue.popleft()

            if ctx.pages_scanned % 10 == 0 or depth == 0:
                log_info(f"[{ctx.pages_scanned+1}/{max_pages}] T{depth}: {url}")

            try:
                resp = ctx.session.get(
                    url, headers={"User-Agent": user_agent}, timeout=10
                )
                if "text/html" in resp.headers.get("Content-Type", "").lower():
                    links = _extract_links(resp.content, url)
                    _process_links(links, ctx, depth)
            except requests.RequestException as err:
                log_warning(f"Fehler bei {url}: {err}")

            ctx.pages_scanned += 1
            time.sleep(0.2)

    finally:
        ctx.close()

    log_info(f"[-] Crawler fertig. Total PDFs: {len(ctx.all_pdfs)}")
    return list(ctx.all_pdfs)
