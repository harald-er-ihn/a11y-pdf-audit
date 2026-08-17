"""
Service zur Generierung von PDF-Reports aus JSON-Daten via WeasyPrint.
Optimiert für PDF/UA-1 Konformität durch native HTML-Metadaten.
"""

import html as html_tool
import json
import os
from datetime import datetime

import weasyprint
from weasyprint import HTML

from core.utils.config_loader import load_config
from core.utils.error_utils import log_error


def _get_report_style():
    """Liefert das CSS für den PDF-Report."""
    return """
        @page {
            size: A4; margin: 2.5cm; margin-bottom: 2cm;
            @bottom-center {
                content: counter(page); font-family: sans-serif;
                font-size: 10pt; color: #222;
            }
        }
        body {
            font-family: sans-serif; font-size: 11pt;
            color: #000; line-height: 1.5;
        }
        .summary-box {
            background-color: #f2f2f2; padding: 15px;
            border-left: 5px solid #005A9C; margin-bottom: 20px; color: #111;
        }
        .status-pass { color: #006600; font-weight: bold; }
        .status-fail { color: #CC0000; font-weight: bold; }
        .status-error { color: #A0522D; font-weight: bold; }
        .report-table { width: 100%; border-collapse: collapse; margin-top: 1rem; }
        .report-table th, .report-table td {
            padding: 0.75rem; border: 1px solid #ddd; text-align: left;
        }
        a {
            color: #005A9C;
            text-decoration: underline;
        }
        .toc-list {
            list-style-type: none;
            padding-left: 0;
            line-height: 1.8;
        }
        .toc-list a {
            text-decoration: none;
        }
        Lbl::before { content: "• "; color: #005A9C; font-weight: bold; }
    """


def _build_summary(stats, total, base_url, config_info):
    """Baut den Zusammenfassungs-HTML-Block."""
    date_str = datetime.now().strftime("%Y-%m-%d")
    esc_url = html_tool.escape(base_url)
    err_count = stats.get("ERROR", 0) + stats.get("UNKNOWN", 0)

    return (
        f'<div class="summary-box">'
        f"<p><strong>URL:</strong> {esc_url}</p>"
        f"<p><strong>Date:</strong> {date_str}</p>"
        f'<p><strong>Max. Pages:</strong> {config_info.get("max_pages", "N/A")}<br>'
        f'<strong>Crawl Depth:</strong> {config_info.get("depth", "N/A")}</p>'
        f"<hr style='border: 0; border-top: 1px solid #ccc; margin: 15px 0;'>"
        f"<ul><li><strong>Total Files:</strong> {total}</li>"
        f'<li><span class="status-pass">PASS: {stats.get("PASS", 0)}</span></li>'
        f'<li><span class="status-fail">FAIL: {stats.get("FAIL", 0)}</span></li>'
        f'<li><span class="status-error">ERRORS: {err_count}</span></li>'
        f"</ul></div>"
    )


def _build_file_list(results):
    """Erzeugt die Liste der Dateien als HTML inkl. Autor, Datum und Links."""
    items = []
    for entry in results:
        status = entry.get("status", "UNKNOWN")
        status_strict = entry.get("status_strict", "UNKNOWN")
        cls_sr = "status-pass" if status == "PASS" else "status-fail"
        cls_strict = "status-pass" if status_strict == "PASS" else "status-fail"

        fname = html_tool.escape(entry.get("filename", "unknown"))
        details = html_tool.escape(entry.get("details", ""))
        url = html_tool.escape(entry.get("url", ""))
        author = html_tool.escape(entry.get("author", "Unknown"))
        date_val = html_tool.escape(entry.get("date", "Unknown"))

        item_html = (
            f"<li><strong style='font-size:1.1em;'>• <a href='{url}' target='_blank' "
            f"rel='noopener noreferrer' style='color:#005A9C; text-decoration:underline;'>"
            f"{fname}</a></strong><br>"
            f"ScreenReader: <span class='{cls_sr}'>[{status}]</span> | "
            f"Strict ISO: <span class='{cls_strict}'>[{status_strict}]</span>"
            f"<div class='{cls_sr}' style='font-size:0.9em; font-family:monospace; "
            f"margin-top:4px;'>{details}</div>"
            f"<div style='font-size:0.9em; color:#555;'>Author: {author} | "
            f"Date: {date_val}</div><br></li>"
        )
        items.append(item_html)

    return (
        "<ul style='list-style-type: none; padding-left: 0;'>"
        + "".join(items)
        + "</ul>"
        if items
        else "<p>No PDFs found.</p>"
    )


# pylint: disable=too-many-locals
def generate_html_content(results, _v_version, base_url, logo_path, info):
    """Erstellt den kompletten HTML-String für WeasyPrint inkl. nativer Metadaten."""
    stats = {"PASS": 0, "FAIL": 0, "ERROR": 0}
    for result in results:
        st = result.get("status", "ERROR")
        stats[st] = stats.get(st, 0) + 1

    footer = '<div class="footer">© 2026 Dr. Harald Hutter</div>'

    cfg = load_config()
    meta = cfg.get("pdf_metadata", {})

    title = html_tool.escape(meta.get("Title") or "Accessibility Audit Report")
    author = html_tool.escape(meta.get("Author", "Dr. Harald Hutter"))
    subject = html_tool.escape(meta.get("Subject", "Accessibility Audit Results"))

    keywords_list = meta.get("Keywords", [])
    if isinstance(keywords_list, str):
        keywords_list = [keywords_list]
    keywords = html_tool.escape(", ".join(keywords_list))

    v_str = getattr(weasyprint, "__version__", "unknown")
    producer = html_tool.escape(meta.get("Producer") or f"WeasyPrint {v_str}")

    lang_raw = meta.get("Lang", ["en-US"])
    language = lang_raw[0] if isinstance(lang_raw, list) else lang_raw

    verapdf_safe = html_tool.escape(_v_version)

    # Umgebrochene URL-Strings zur Vermeidung der "Line too long" Fehlermeldung
    url_about = "https://a11y-pdf-audit.fly.dev/about"
    link_bfit = f"{url_about}#GermanFederalMonitoringAgencyForAccessibilityInInformationTechnology"

    return f"""<!DOCTYPE html>
    <html lang="{language}">
    <head>
        <meta charset="UTF-8">
        <title>{title}</title>
        <meta name="author" content="{author}">
        <meta name="description" content="{subject}">
        <meta name="keywords" content="{keywords}">
        <meta name="generator" content="{producer}">
        <style>{_get_report_style()}</style>
    </head>
    <body>
        {footer}
        <img src='file://{logo_path}' style='width:150px;' alt='Logo'>
        <h1 style="color: #005A9C; margin-bottom:0;">Accessibility Audit Report</h1>
        <p style="margin-top:0; color:#555;">
            {datetime.now().strftime("%Y-%m-%d")} — via a11y-pdf-audit
        </p>

        {_build_summary(stats, len(results), base_url, info)}

        <h2>Automated Accessibility Checks for Downloadable PDFs</h2>
        <p>Learn more about the technical architecture and features.</p>
        <ul class="toc-list">
            <li><a href="{url_about}">Technical Architecture Overview</a></li>
            <li><a href="{url_about}#PurposeIdea">Purpose and Idea</a></li>
            <li><a href="{link_bfit}">German Federal Monitoring Agency</a></li>
            <li><a href="{url_about}#MainFeatures">Main Features</a></li>
            <li><a href="{url_about}#LimitationsIssues">Limitations and Issues</a></li>
            <li><a href="{url_about}#QualityTesting">Quality and Testing</a></li>
        </ul>

        <h2>Development &amp; License</h2>
        <p>Developed by Dr. Harald Hutter. License: MIT License.<br>
        <a href="https://a11y-pdf-audit.fly.dev/">https://a11y-pdf-audit.fly.dev/</a></p>

        <h2>Validation Details</h2>
        <div class="summary-box" style="font-family: monospace; font-size: 0.9em; 
             white-space: pre-wrap; line-height: 1.4;">VeraPDF Version: {verapdf_safe}
Built: Tue Jul 15 16:59:00 CEST 2025
Developed and released by the veraPDF Consortium.
Funded by the PREFORMA project.
Released under the GNU General Public License v3
and the Mozilla Public License v2 or later.</div>

        <h2>Detailed Results</h2>
        {_build_file_list(results)}
    </body>
    </html>
    """


# pylint: disable=too-many-arguments
def create_report(
    json_file, output_pdf, base_url, verapdf_version, logo_path, config_info
):
    """Hauptfunktion zur Erstellung des PDF-Berichts."""
    if not os.path.exists(json_file):
        return False
    try:
        with open(json_file, "r", encoding="utf-8") as f:
            results = json.load(f)

        sort_order = {"PASS": 1, "FAIL": 2, "ERROR": 3}
        results.sort(key=lambda x: sort_order.get(str(x.get("status", "")).upper(), 4))

        html_content = generate_html_content(
            results, verapdf_version, base_url, logo_path, config_info
        )
        os.makedirs(os.path.dirname(output_pdf), exist_ok=True)

        HTML(string=html_content, base_url=os.getcwd()).write_pdf(
            target=output_pdf, pdf_variant="pdf/ua-1"
        )
        return True
    except Exception as err:  # pylint: disable=broad-exception-caught
        log_error(f"❌ Report-Fehler: {err}")
        return False
