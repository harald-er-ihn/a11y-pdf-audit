"""
Service zur Generierung von PDF-Reports aus JSON-Daten via WeasyPrint.
Optimiert für PDF/UA-1 Konformität (axesCheck & VeraPDF Strict).
"""

import html
import json
import os
from datetime import datetime

import pikepdf
import weasyprint
from weasyprint import HTML

from core.utils.config_loader import load_config
from core.utils.error_utils import log_error, log_info, setup_logging


def _build_improved_section(results):
    """Baut die Tabelle für erfolgreich verbesserte Dateien."""
    improved = [r for r in results if r.get("repaired")]
    if not improved:
        return ""

    rows = ""
    for r in improved:
        status_after = r.get("status_after", "FAIL")
        color = "green" if status_after == "PASS" else "red"
        rows += f"<tr><td>{html.escape(r['filename'])}</td><td style='color:{color}'>{status_after}</td></tr>"

    return f"""
    <div style='page-break-before: always;'></div>
    <h2>Improved PDF Files (AI Reconstruction Success)</h2>
    <table class='report-table'><thead><tr><th>File</th><th>New Status</th></tr></thead>
    <tbody>{rows}</tbody></table>
    """


def _get_report_style():
    """Liefert das CSS."""
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
        .header-container {
            margin-bottom: 30px; border-bottom: 2px solid #005A9C;
            padding-bottom: 10px; overflow: hidden;
        }
        .header-logo-wrapper { float: left; width: 25%; }
        .header-logo-img { width: 100%; height: auto; max-width: 3.5cm; }
        .header-text-wrapper {
            float: right; width: 70%; text-align: right; padding-top: 10px;
        }
        h1 { font-size: 22pt; margin: 0; color: #005A9C; font-weight: bold; }
        h2 {
            font-size: 14pt; margin-top: 24pt; margin-bottom: 10pt;
            color: #111; border-bottom: 1px solid #777; page-break-after: avoid;
        }
        .summary-box {
            background-color: #f2f2f2; padding: 15px;
            border-left: 5px solid #005A9C; margin-bottom: 20px; color: #111;
        }
        .status-pass { color: #006600; font-weight: bold; }
        .status-fail { color: #CC0000; font-weight: bold; }
        .status-error { color: #A0522D; font-weight: bold; }
        .meta-info {
            font-size: 10pt; color: #333; margin-top: 2px; display: block;
        }
        .verapdf-info {
            background: #eee; padding: 10px; font-family: monospace;
            font-size: 9pt; white-space: pre-wrap;
            border-radius: 4px; color: #111;
        }
        a { color: #004085; text-decoration: underline; }
        ul { padding-left: 1.5em; list-style-type: none; }
        li { margin-bottom: 8pt; }
        .tech-table {
            width: 100%; border-collapse: collapse;
            font-size: 10pt; margin-bottom: 10pt;
        }
        .tech-table td { padding: 4px; border-bottom: 1px solid #ccc; }
        /* PDF/UA-konforme Listenstruktur */
        Lbl::before { content: "• "; color: #005A9C; font-weight: bold; }
        LBody { display: inline; }
    """


def _get_about_section(cfg_gen):
    """Liefert den About-Text mit absoluten URLs aus Config für das PDF."""
    base = cfg_gen.get("base_url", "https://a11y-pdf-audit.fly.dev")
    return f"""
    <h2>Automated Accessibility Checks for Downloadable PDFs</h2>
    <p>Learn more about the technical architecture, features, and motivation behind the PDF A11y Auditor tool.</p>
    <h3>Technical Architecture Overview</h3>
    <ul>
    <li><a href="{base}/about#PurposeIdea" target="_blank">Purpose and Idea︎</a></li>
    <li><a href="{base}/about#GermanFederalMonitoringAgencyForAccessibilityInInformationTechnology" target="_blank">
    German Federal Monitoring Agency for Accessibility in Information Technology︎</a></li>
    <li><a href="{base}/about#MainFeatures" target="_blank">Main Features</a></li>
    <li><a href="{base}/about#LimitationsIssues" target="_blank">Limitations and Issues</a></li>
    <li><a href="{base}/about#Performance" target="_blank">Performance︎</a></li>
    <li><a href="{base}/about#QualityTesting" target="_blank">Quality and Testing</a></li>
    </ul>
    <h3>Development & License</h3>
    <p>Developed by {cfg_gen.get("author", "Unknown")}. License: MIT License.<br>
    <a href="{base}/">{base}/</a></p>
    """


def _build_summary(stats, total, base_url, config_info):
    """Baut den Zusammenfassungs-HTML-Block."""
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
        f'<li><span class="status-error">ERRORS: {stats["ERROR"]}</span>'
        f"</li></ul></div>"
    )


def _build_file_list(results):
    """Erzeugt die Liste der Dateien als HTML."""
    items = []

    for entry in results:
        status = entry.get("status", "UNKNOWN")
        status_strict = entry.get("status_strict", "UNKNOWN")

        cls_sr = "status-pass" if status == "PASS" else "status-fail"
        if status == "ERROR":
            cls_sr = "status-error"

        cls_strict = "status-pass" if status_strict == "PASS" else "status-fail"
        if status_strict == "ERROR":
            cls_strict = "status-error"

        fname = html.escape(entry.get("filename", "unknown"))
        details = html.escape(entry.get("details", ""))
        url = html.escape(entry.get("url", ""))
        author = html.escape(entry.get("author", "Unknown"))
        date = html.escape(entry.get("date", "Unknown"))

        # URL escapen, aber doppelte Anführungszeichen im HTML verwenden!
        item_html = (
            "<li style='margin-bottom: 12pt;'>"
            f"<Lbl></Lbl>"
            "<LBody style='display: inline-block; vertical-align: top; width: 90%;'>"
            f'<strong><a href="{url}">{fname}</a></strong><br>'
            f"<span style='font-size:0.9em;'>"
            f"ScreenReader: <span class='{cls_sr}'>[{status}]</span> | "
            f"Strict ISO: <span class='{cls_strict}'>[{status_strict}]</span>"
            f"</span>"
            f"<div class='{cls_sr}' style='font-size:0.9em; margin-top: 2px;'>{details}</div>"
            f"<div class='meta-info'>Author: {author} | Date:{date}</div>"
            "</LBody>"
            "</li>"
        )

        items.append(item_html)

    if not items:
        return "<p>No PDFs found.</p>"
    return "<ul>" + "".join(items) + "</ul>"


def generate_html_content(results, v_version, base_url, logo_path, info):
    # Setup Variablen
    footer = '<div class="footer">© 2026 Dr. Harald Hutter - PDF A11y Auditor</div>'
    stats = {"PASS": 0, "FAIL": 0, "ERROR": 0}
    for r in results:
        stats[r.get("status", "ERROR")] += 1

    from core.services.generate_report_from_json import (_build_file_list,
                                                         _build_summary,
                                                         _get_report_style)

    return f"""
    <html><head><style>{_get_report_style()}</style></head>
    <body>
        {footer}
        <img src='file://{logo_path}' style='width:150px;'>
        <h1>Accessibility Audit Report</h1>
        {_build_summary(stats, len(results), base_url, info)}
        <h2>Original Scan Results</h2>
        {_build_file_list(results)}
        {_build_improved_section(results)}
    </body></html>
    """


def _apply_pdf_metadata(pdf_path):
    """Setzt Metadaten aus config/config.json ins fertige PDF."""
    try:
        cfg = load_config()
        meta_cfg = cfg.get("pdf_metadata", {})

        with pikepdf.open(pdf_path, allow_overwriting_input=True) as pdf:
            pdf.docinfo["/Title"] = str(meta_cfg.get("Title", "")).strip()
            pdf.docinfo["/Author"] = str(meta_cfg.get("Author", "")).strip()
            pdf.docinfo["/Subject"] = str(meta_cfg.get("Subject", "")).strip()

            keywords = meta_cfg.get("Keywords")
            if isinstance(keywords, list):
                pdf.docinfo["/Keywords"] = ", ".join(map(str, keywords))
            elif isinstance(keywords, str):
                pdf.docinfo["/Keywords"] = keywords

            # Creator
            gen = cfg.get("general", {})
            name = gen.get("app_name", "a11y-pdf-audit")
            ver = gen.get("version", "1.0")

            creator_val = f"{name} Toolset v{ver}"
            pdf.docinfo["/Creator"] = creator_val

            v_str = getattr(weasyprint, "__version__", "unknown")
            producer_val = (
                str(meta_cfg.get("Producer", "")).strip() or f"WeasyPrint {v_str}"
            )
            pdf.docinfo["/Producer"] = producer_val

            lang_val = meta_cfg.get("Lang")
            if isinstance(lang_val, list):
                lang_val = lang_val[0]

            if isinstance(lang_val, str) and lang_val:
                root_dict = pdf.trailer["/Root"]
                root_dict["/Lang"] = lang_val
                pdf.trailer["/Root"] = root_dict

            pdf.save(pdf_path)
        return True

    except Exception as err:  # pylint: disable=broad-exception-caught
        log_error(f"⚠️ Fehler beim Setzen der Metadaten: {err}")
        return False


def create_report(  # pylint: disable=too-many-arguments
    json_file, output_pdf, base_url, verapdf_version, logo_path, config_info
):
    """Erstellt das PDF."""
    if not os.path.exists(json_file):
        log_error(f"❌ JSON-Datei fehlt: {json_file}")
        return False
    try:
        with open(json_file, "r", encoding="utf-8") as f:
            results = json.load(f)
    except Exception as err:  # pylint: disable=broad-exception-caught
        log_error(f"❌ Fehler beim Lesen des JSONs ({json_file}): {err}")
        return False

    html_str = generate_html_content(
        results, verapdf_version, base_url, logo_path, config_info
    )

    try:
        os.makedirs(os.path.dirname(output_pdf), exist_ok=True)
        # PDF/UA-1
        HTML(string=html_str, base_url=os.getcwd()).write_pdf(
            target=output_pdf, pdf_variant="pdf/ua-1", pdf_version="1.7", zoom=1
        )
        _apply_pdf_metadata(output_pdf)
        return True
    except Exception as err:  # pylint: disable=broad-exception-caught
        log_error(f"⚠️ Haupt-PDF-Erstellung fehlgeschlagen: {err}")
        try:
            # Fallback
            HTML(string=html_str, base_url=os.getcwd()).write_pdf(target=output_pdf)
            _apply_pdf_metadata(output_pdf)
            return True
        except Exception as err2:  # pylint: disable=broad-exception-caught
            log_error(f"❌ Fallback fehlgeschlagen: {err2}")
            return False


# In generate_report_from_json.py die Funktion _build_improved_list hinzufügen:


def _build_improved_file_list(results):
    """Baut die Liste der verbesserten Dateien für das Ende des Reports."""
    improved_items = [r for r in results if r.get("repaired")]

    if not improved_items:
        return "<p>No files were improved during this run.</p>"

    html = "<ul>"
    for entry in improved_items:
        fname = html.escape(entry.get("filename", "unknown"))
        st_before = entry.get("status", "FAIL")
        st_after = entry.get("status_after", "UNKNOWN")

        # Farbauswahl für den Vorher/Nachher Vergleich
        cls_after = "status-pass" if st_after == "PASS" else "status-fail"

        html += f"""
        <li style='margin-bottom: 10pt;'>
            <Lbl></Lbl>
            <LBody>
                <strong>{fname}</strong><br>
                <span style='font-size: 0.9em;'>
                    Improvement Result: 
                    <span class='status-fail'>[{st_before}]</span> ➔ 
                    <span class='{cls_after}'>[{st_after}]</span>
                </span>
            </LBody>
        </li>
        """
    html += "</ul>"
    return html


def main_test():
    """Testfunktion für lokale Ausführung."""
    setup_logging(log_dir="output")
    log_info("✅ Modul geladen – Testlauf gestartet")
    cfg = load_config()

    j_file = "output/reports/test.json"
    o_pdf = "output/reports/test.pdf"
    b_url = cfg["general"]["base_url"]

    # Dummy string to test without running actual java process
    v_ver = f"veraPDF (Test Mode) via {cfg['general']['app_name']}"
    l_path = cfg["assets"]["logo_file"]
    c_info = {"max_pages": 10000, "depth": 10}


if __name__ == "__main__":
    main_test()
