"""
Service zur Generierung von PDF-Reports aus JSON-Daten via WeasyPrint.
Optimiert für PDF/UA-1 Konformität.
"""

import html as html_tool
import json
import os
from datetime import datetime

import pikepdf
import weasyprint
from weasyprint import HTML

from core.utils.config_loader import load_config
from core.utils.error_utils import log_error, log_info


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
        Lbl::before { content: "• "; color: #005A9C; font-weight: bold; }
    """


def _build_improved_section(results):
    """Baut die Tabelle für erfolgreich verbesserte Dateien."""
    improved = [r for r in results if r.get("repaired")]
    if not improved:
        return ""

    rows = ""
    for r in improved:
        status_after = r.get("status_after", "FAIL")
        color = "green" if status_after == "PASS" else "red"
        esc_name = html_tool.escape(r["filename"])
        rows += (
            f"<tr><td>{esc_name}</td>"
            f"<td style='color:{color}'>{status_after}</td></tr>"
        )

    return f"""
    <div style='page-break-before: always;'></div>
    <h2>Improved PDF Files (AI Reconstruction Success)</h2>
    <table class='report-table'><thead><tr><th>File</th><th>New Status</th></tr></thead>
    <tbody>{rows}</tbody></table>
    """


def _build_summary(stats, total, base_url, config_info):
    """Baut den Zusammenfassungs-HTML-Block."""
    date_str = datetime.now().strftime("%Y-%m-%d")
    esc_url = html_tool.escape(base_url)

    return (
        f'<div class="summary-box">'
        f"<p><strong>URL:</strong> {esc_url}</p>"
        f"<p><strong>Date:</strong> {date_str}</p>"
        f'<p><strong>Max. Pages:</strong> {config_info["max_pages"]}<br>'
        f'<strong>Crawl Depth:</strong> {config_info["depth"]}</p>'
        f"<ul><li><strong>Total Files:</strong> {total}</li>"
        f'<li><span class="status-pass">PASS: {stats["PASS"]}</span></li>'
        f'<li><span class="status-fail">FAIL: {stats["FAIL"]}</span></li>'
        f'<li><span class="status-error">ERRORS: {stats["ERROR"]}</span></li>'
        f"</ul></div>"
    )


def _build_file_list(results):
    """Erzeugt die Liste der Dateien als HTML."""
    items = []
    for entry in results:
        status = entry.get("status", "UNKNOWN")
        status_strict = entry.get("status_strict", "UNKNOWN")
        cls_sr = "status-pass" if status == "PASS" else "status-fail"
        cls_strict = "status-pass" if status_strict == "PASS" else "status-fail"

        fname = html_tool.escape(entry.get("filename", "unknown"))
        details = html_tool.escape(entry.get("details", ""))
        url = html_tool.escape(entry.get("url", ""))

        item_html = (
            f"<li><strong><a href='{url}'>{fname}</a></strong><br>"
            f"ScreenReader: <span class='{cls_sr}'>[{status}]</span> | "
            f"Strict ISO: <span class='{cls_strict}'>[{status_strict}]</span>"
            f"<div class='{cls_sr}' style='font-size:0.9em;'>{details}</div></li>"
        )
        items.append(item_html)

    return "<ul>" + "".join(items) + "</ul>" if items else "<p>No PDFs found.</p>"


def generate_html_content(results, _v_version, base_url, logo_path, info):
    """Erstellt den kompletten HTML-String für WeasyPrint."""
    stats = {"PASS": 0, "FAIL": 0, "ERROR": 0}
    for r in results:
        stats[r.get("status", "ERROR")] += 1

    footer = '<div class="footer">© 2026 Dr. Harald Hutter</div>'

    return f"""
    <html lang="en"><head><style>{_get_report_style()}</style></head>
    <body>
        {footer}
        <img src='file://{logo_path}' style='width:150px;' alt='Logo'>
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
        meta = cfg.get("pdf_metadata", {})
        with pikepdf.open(pdf_path, allow_overwriting_input=True) as pdf:
            pdf.docinfo["/Title"] = "Audit Report"
            pdf.docinfo["/Author"] = str(meta.get("Author", "Dr. Harald Hutter"))
            v_str = getattr(weasyprint, "__version__", "unknown")
            pdf.docinfo["/Producer"] = f"WeasyPrint {v_str}"
            pdf.save(pdf_path)
        return True
    except Exception as err:  # pylint: disable=broad-exception-caught
        log_error(f"⚠️ Metadaten-Fehler: {err}")
        return False


def create_report(
    json_file, output_pdf, base_url, verapdf_version, logo_path, config_info
):
    """Hauptfunktion zur Erstellung des PDF-Berichts."""
    if not os.path.exists(json_file):
        return False
    try:
        with open(json_file, "r", encoding="utf-8") as f:
            results = json.load(f)
        html_content = generate_html_content(
            results, verapdf_version, base_url, logo_path, config_info
        )
        os.makedirs(os.path.dirname(output_pdf), exist_ok=True)
        HTML(string=html_content, base_url=os.getcwd()).write_pdf(
            target=output_pdf, pdf_variant="pdf/ua-1"
        )
        _apply_pdf_metadata(output_pdf)
        return True
    except Exception as err:  # pylint: disable=broad-exception-caught
        log_error(f"❌ Report-Fehler: {err}")
        return False


def main_test():
    """Testfunktion für lokale Ausführung."""
    log_info("Testlauf gestartet")
    # Pylint Fix: Variablen im Test nutzen oder löschen
    test_json = "output/reports/test.json"
    if os.path.exists(test_json):
        log_info(f"JSON gefunden: {test_json}")


if __name__ == "__main__":
    main_test()
