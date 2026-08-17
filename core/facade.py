"""Zentrales Interface für den Audit-Workflow."""

import os
import shutil
import time

from core.services.generate_report_from_json import create_report
from core.services.pdf_crawler import crawl_site_logic
from core.services.pdf_processor import get_verapdf_version, process_pdf_links
from core.utils.config_loader import load_config
from core.utils.error_utils import log_info


class AuditFacade:
    """
    Hauptklasse zur Steuerung des Audit-Ablaufs.
    Hält Pfade aus der Konfiguration bereit.
    """

    # pylint: disable=too-few-public-methods

    def __init__(self):
        self.cfg = load_config()
        self.out_dir = self.cfg["active_paths"]["output"]
        self.reports_dir = os.path.join(self.out_dir, "reports")
        self.temp_dir = os.path.join(self.out_dir, "temp_pdfs")
        os.makedirs(self.reports_dir, exist_ok=True)

    def run_full_audit(self, url, max_p, depth):
        """Führt den kompletten Audit durch: Crawl -> Check -> Report."""
        ts = time.strftime("%Y%m%d-%H%M%S")
        safe = url.replace("https://", "").replace("/", "_")[:25]
        base = f"REPORT_{ts}_{safe}_P{max_p}_D{depth}"

        link_f = os.path.join(self.reports_dir, f"{base}_links.txt")
        json_f = os.path.join(self.reports_dir, f"{base}.json")
        pdf_f = os.path.join(self.reports_dir, f"{base}.pdf")

        log_info(f"--- [1/3] Crawl gestartet: {url} ---")
        crawl_site_logic(
            url,
            link_f,
            max_p,
            depth,
            self.cfg["crawler"]["user_agent"],
            self.cfg["crawler"]["timeout"],
        )

        log_info("--- [2/3] Check gestartet ---")
        process_pdf_links(
            link_f, json_f, self.temp_dir, self.cfg["active_paths"]["verapdf"]
        )

        log_info("---[3/3] Generiere PDF-Report ---")
        create_report(
            json_f,
            pdf_f,
            url,
            get_verapdf_version(self.cfg["active_paths"]["verapdf"]),
            os.path.join(os.getcwd(), self.cfg["assets"]["logo_file"]),
            {"max_pages": max_p, "depth": depth},
        )

        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

        return pdf_f
