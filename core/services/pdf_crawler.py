"""
Service zum Crawlen von Webseiten nach PDF-Dateien.
Strikt auf eine Domain beschränkt (keine Subdomains).
"""

import re
import time
from collections import deque
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from core.utils.error_utils import log_error, log_info, log_warning


def is_exact_domain(url, allowed_netloc):
    """
    Prüft, ob die URL exakt zur erlaubten Domain gehört (keine Subdomains).
    """
    try:
        netloc = urlparse(url).netloc
        # Wenn netloc leer ist, ist es relativ -> intern -> okay
        if not netloc:
            return True
        # Exakter Vergleich (mit und ohne www Toleranz)
        return (
            netloc == allowed_netloc
            or netloc == allowed_netloc.replace("www.", "")
            or allowed_netloc == netloc.replace("www.", "")
        )
    except ValueError:
        return False


def _fetch_sitemap(start_url):
    """
    Versucht, die sitemap.xml zu finden und PDF-Links daraus zu extrahieren.
    """
    pdf_links = set()
    parsed_start = urlparse(start_url)
    sitemap_urls = [
        f"{parsed_start.scheme}://{parsed_start.netloc}/sitemap.xml",
        f"{parsed_start.scheme}://{parsed_start.netloc}/sitemap_index.xml",
    ]

    headers = {"User-Agent": "a11y-pdf-audit-bot"}

    for sm_url in sitemap_urls:
        try:
            resp = requests.get(sm_url, headers=headers, timeout=10)
            if resp.status_code == 200:
                log_info(f"🗺️ Sitemap gefunden: {sm_url}")
                locs = re.findall(r"<loc>(.*?)</loc>", resp.text)
                for loc in locs:
                    if loc.lower().endswith(".pdf"):
                        pdf_links.add(loc)
        except Exception:
            pass

    if pdf_links:
        log_info(f"🗺️ {len(pdf_links)} PDFs direkt aus Sitemap extrahiert.")

    return list(pdf_links)


def _extract_links_from_html(content, current_url):
    """Parst HTML und gibt absolute Links zurück."""
    soup = BeautifulSoup(content, "html.parser")
    found = []
    for link in soup.find_all("a", href=True):
        href = link["href"].strip()
        if href.startswith(("#", "javascript:", "mailto:", "tel:")):
            continue
        found.append(urljoin(current_url, href))
    return found


def crawl_site_logic(
    start_url, output_file, max_pages=50, max_depth=1, user_agent="Bot"
):
    """
    Hauptfunktion des Crawlers.
    """
    import os

    os.makedirs(os.path.dirname(output_file), exist_ok=True)

    # Wir nutzen strict netloc für die Begrenzung
    allowed_netloc = urlparse(start_url).netloc
    log_info(f"Crawler Scope: Nur {allowed_netloc} (keine anderen Subdomains)")

    all_pdfs = set()
    queue = deque([(start_url, 0)])
    visited = {start_url}
    pages_scanned = 0

    session = requests.Session()
    headers = {"User-Agent": user_agent}

    # 1. Sitemap Check
    sitemap_pdfs = _fetch_sitemap(start_url)
    for pdf in sitemap_pdfs:
        all_pdfs.add(pdf)

    with open(output_file, "w", encoding="utf-8") as f_out:
        f_out.write(f"# Crawl Results for {start_url}\n\n")

        for pdf in sitemap_pdfs:
            f_out.write(pdf + "\n")

        # 2. Regulärer Crawl
        while queue and pages_scanned < max_pages:
            url, depth = queue.popleft()

            if pages_scanned % 10 == 0 or depth == 0:
                log_info(f"[{pages_scanned+1}/{max_pages}] Scan (T{depth}): {url}")

            try:
                # HEAD Check
                try:
                    head = session.head(
                        url, headers=headers, timeout=5, allow_redirects=True
                    )
                    if "text/html" not in head.headers.get("Content-Type", "").lower():
                        pages_scanned += 1
                        continue
                except Exception:
                    pass

                response = session.get(url, headers=headers, timeout=10)
                links = _extract_links_from_html(response.content, url)

                for full_url in links:
                    # PDF gefunden?
                    if full_url.lower().endswith(".pdf"):
                        if full_url not in all_pdfs:
                            all_pdfs.add(full_url)
                            log_info(
                                f"📄 PDF: {os.path.basename(urlparse(full_url).path)}"
                            )
                            f_out.write(full_url + "\n")
                            f_out.flush()

                    # Weiter crawlen?
                    elif depth < max_depth:
                        # STRIKTER CHECK: Nur exakte Domain
                        if is_exact_domain(full_url, allowed_netloc):
                            if full_url not in visited:
                                if not any(
                                    full_url.lower().endswith(ext)
                                    for ext in [".jpg", ".png", ".zip", ".mp4"]
                                ):
                                    visited.add(full_url)
                                    queue.append((full_url, depth + 1))

            except Exception as e:
                log_warning(f"Fehler bei {url}: {e}")

            pages_scanned += 1
            time.sleep(0.2)

    log_info(f"[-] Crawler fertig. Total PDFs: {len(all_pdfs)}")
    return list(all_pdfs)
