"""
Service zur Generierung von PDF-Reports aus JSON-Daten via WeasyPrint.
Optimiert für PDF/UA-1 Konformität (axesCheck & VeraPDF Strict).
"""

import html
import json
import os
from datetime import datetime

from weasyprint import HTML


def _get_report_style():
    """
    Liefert das CSS für den PDF-Bericht.
    Layout ohne Tabellen für den Header!
    """
    return """
        @page {
            size: A4;
            margin: 2.5cm;
            margin-bottom: 2cm;
            @bottom-center {
                content: counter(page);
                font-family: sans-serif;
                font-size: 10pt;
                color: #222;
            }
        }

        body { 
            font-family: sans-serif; 
            font-size: 11pt; 
            color: #000; 
            line-height: 1.5;
        }
        
        /* HEADER LAYOUT: Flexbox/Flow statt Tabelle für Barrierefreiheit */
        .header-container {
            margin-bottom: 30px;
            border-bottom: 2px solid #005A9C;
            padding-bottom: 10px;
            overflow: hidden; /* Clearfix */
        }
        
        .header-logo-wrapper {
            float: left;
            width: 25%;
        }
        
        .header-logo-img {
            width: 100%;
            height: auto;
            max-width: 3.5cm;
        }
        
        .header-text-wrapper {
            float: right;
            width: 70%;
            text-align: right;
            padding-top: 10px;
        }

        h1 { 
            font-size: 22pt; 
            margin: 0;
            color: #005A9C; 
            font-weight: bold;
        }
        
        h2 { 
            font-size: 14pt; 
            margin-top: 24pt; 
            margin-bottom: 10pt;
            color: #111; 
            border-bottom: 1px solid #777;
            page-break-after: avoid;
        }
        
        h3 {
            font-size: 12pt;
            margin-top: 16pt;
            margin-bottom: 6pt;
            color: #222;
            font-weight: bold;
        }
        
        .summary-box { 
            background-color: #f2f2f2;
            padding: 15px; 
            border-left: 5px solid #005A9C;
            margin-bottom: 20px; 
            color: #111;
        }
        
        .status-pass { color: #006600; font-weight: bold; }
        .status-fail { color: #CC0000; font-weight: bold; }
        .status-error { color: #A0522D; font-weight: bold; }
        
        .meta-info { 
            font-size: 10pt; 
            color: #333; 
            margin-top: 2px; 
            display: block; 
        }
        
        .verapdf-info { 
            background: #eee; 
            padding: 10px; 
            font-family: monospace; 
            font-size: 9pt; 
            white-space: pre-wrap; 
            border-radius: 4px;
            color: #111;
        }
        
        a { color: #004085; text-decoration: underline; }
        ul { padding-left: 1.5em; }
        li { margin-bottom: 8pt; }
        
        .tech-table {
            width: 100%;
            border-collapse: collapse;
            font-size: 10pt;
            margin-bottom: 10pt;
        }
        .tech-table td {
            padding: 4px;
            border-bottom: 1px solid #ccc;
        }
    """


def _get_about_section():
    return """
    <h2>Automated Accessibility Checks for Downloadable PDFs</h2>
    
    <h3>Purpose and Idea</h3>
    <p>
        The a11y PDF Audit is a modular web application designed to automatically check websites for accessible PDF files.
        It crawls any given URL, downloads discovered PDFs, validates them using VeraPDF,
        and generates structured HTML and PDF reports automatically.
    </p>


    <h3>Development & License</h3>
    <p>
    Developed by Dr. Harald Hutter – Licensed under MIT License.
    <a href="https://a11y-pdf-audit.fly.dev/">https://a11y-pdf-audit.fly.dev/</a>
    </p>
    """


def _build_summary_html(stats, total, base_url, config_info):
    date_str = datetime.now().strftime("%Y-%m-%d")
    return (
        f'<div class="summary-box">'
        f"<p><strong>URL:</strong> {html.escape(base_url)}</p>"
        f"<p><strong>Date:</strong> {date_str}</p>"
        f'<p><strong>Max. Pages:</strong> {config_info["max_pages"]}<br>'
        f'<strong>Crawl Depth:</strong> {config_info["depth"]}</p>'
        f'<hr style="border: 0; border-top: 1px solid #555; margin: 10px 0;">'
        f"<ul>"
        f"<li><strong>Total Files:</strong> {total}</li>"
        f'<li><span class="status-pass">PASS: {stats["PASS"]}</span></li>'
        f'<li><span class="status-fail">FAIL: {stats["FAIL"]}</span></li>'
        f'<li><span class="status-error">ERRORS: {stats["ERROR"]}</span></li>'
        f"</ul>"
        f"</div>"
    )


def generate_html_content(results, verapdf_version, base_url, logo_path, config_info):
    stats = {
        "PASS": sum(1 for r in results if r["status"] == "PASS"),
        "FAIL": sum(1 for r in results if r["status"] == "FAIL"),
        "ERROR": sum(1 for r in results if r["status"] == "ERROR"),
    }
    total = len(results)

    css = _get_report_style()
    summary = _build_summary_html(stats, total, base_url, config_info)
    about = _get_about_section()

    # Logo Setup
    logo_img = ""
    if logo_path and os.path.exists(logo_path):
        abs_path = os.path.abspath(logo_path)
        alt_text = "Accessibility Matters Logo - Colorful paint splashes"
        logo_img = (
            f'<img src="file://{abs_path}" alt="{alt_text}" class="header-logo-img">'
        )

    # Neues Header-Layout ohne Tabelle
    header_html = f"""
    <div class="header-container">
        <div class="header-logo-wrapper">
            {logo_img}
        </div>
        <div class="header-text-wrapper">
            <h1>Audit Report</h1>
        </div>
    </div>
    """

    verapdf_block = (
        f'<div class="verapdf-info"><h3>VeraPDF Info</h3>'
        f"{html.escape(verapdf_version)}</div>"
        "<p style='font-size:0.9em; margin-top:5px;'>The veraPDF validation engine implements the PDF/A and PDF/UA specification. "
        "See <a href='https://docs.verapdf.org/validation/'>Matterhorn protocol</a> for details.</p>"
    )

    file_items = []
    for entry in results:
        status = entry.get("status", "UNKNOWN")
        cls = "status-pass" if status == "PASS" else "status-fail"
        if status == "ERROR":
            cls = "status-error"

        fname = html.escape(entry.get("filename", "unknown"))
        details = html.escape(entry.get("details", ""))
        safe_url = html.escape(entry.get("url", ""))
        author = html.escape(entry.get("author", "Unknown"))
        date = html.escape(entry.get("date", "Unknown"))

        item = (
            f"<li>"
            f'<strong><a href="{safe_url}">{fname}</a></strong> '
            f'<span class="{cls}">[{status}]</span><br>'
            f'<span class="{cls}" style="font-size: 0.9em;">{details}</span><br>'
            f'<span class="meta-info">Author: {author} | Date: {date}</span>'
            f"</li>"
        )
        file_items.append(item)

    file_list = (
        "<ul>" + "".join(file_items) + "</ul>"
        if file_items
        else "<p>No PDFs found.</p>"
    )

    footer_html = (
        '<div class="footer-element">'
        "<p>© Dr. Harald Hutter 2026 – https://a11y-pdf-audit.fly.dev/ – License: MIT License</p>"
        "</div>"
    )

    return (
        f'<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">'
        f"<title>Audit Report</title><style>{css}</style></head><body>"
        f"{footer_html}"
        f"{header_html}"
        f"{summary}"
        f"{about}"
        f"<h2>Validation Details</h2>"
        f"{verapdf_block}"
        f"<h2>Detailed Results</h2>{file_list}</body></html>"
    )


def create_report(
    json_file, output_pdf, base_url, verapdf_version, logo_path, config_info
):
    if not os.path.exists(json_file):
        return False
    try:
        with open(json_file, "r", encoding="utf-8") as f:
            results = json.load(f)
    except Exception:
        return False

    html_str = generate_html_content(
        results, verapdf_version, base_url, logo_path, config_info
    )

    try:
        os.makedirs(os.path.dirname(output_pdf), exist_ok=True)
        HTML(string=html_str, base_url=os.getcwd()).write_pdf(
            target=output_pdf, pdf_variant="pdf/ua-1", pdf_version="1.7", zoom=1
        )
        return True
    except Exception:
        # Fallback
        try:
            HTML(string=html_str, base_url=os.getcwd()).write_pdf(target=output_pdf)
            return True
        except Exception:
            return False
