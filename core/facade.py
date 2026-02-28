"""
Zentrales Interface für den Audit-Workflow.
"""

import os
import shutil
import time

from core.services.generate_report_from_json import create_report
from core.services.pdf_crawler import crawl_site_logic
from core.services.pdf_processor import get_verapdf_version, process_pdf_links
from core.utils.config_loader import load_config
from core.utils.error_utils import log_info
from core.utils.zip_utils import create_repair_zip


class AuditFacade:
    """
    Hauptklasse zur Steuerung des Audit-Ablaufs.
    """

    def __init__(self):
        self.cfg = load_config()
        self.out_dir = self.cfg["active_paths"]["output"]
        self.reports_dir = os.path.join(self.out_dir, "reports")
        self.temp_dir = os.path.join(self.out_dir, "temp_pdfs")
        os.makedirs(self.reports_dir, exist_ok=True)

    def _generate_names(self, url, max_p, depth):
        ts = time.strftime("%Y%m%d-%H%M%S")
        safe = url.replace("https://", "").replace("/", "_")[:25]
        base = f"REPORT_{ts}_{safe}_P{max_p}_D{depth}"
        return ts, safe, base

    def run_full_audit(self, url, max_p, depth, force_ai=False):
        """
        Führt den kompletten Audit durch: Crawl -> Check -> Report.
        """
        ts, safe, base = self._generate_names(url, max_p, depth)
        link_f = os.path.join(self.reports_dir, f"{base}_links.txt")
        json_f = os.path.join(self.reports_dir, f"{base}.json")
        pdf_f = os.path.join(self.reports_dir, f"{base}.pdf")

        # 1. Crawl
        log_info("--- [1/3] Crawl ---")
        crawl_site_logic(url, link_f, max_p, depth, self.cfg["crawler"]["user_agent"])

        # 2. Process & Fix
        log_info("--- [2/3] Process & Fix ---")
        results = process_pdf_links(
            link_f, json_f, self.temp_dir, self.cfg["active_paths"]["verapdf"], force_ai
        )

        # 3. Report
        log_info("--- [3/3] Report ---")
        create_report(
            json_f,
            pdf_f,
            url,
            get_verapdf_version(self.cfg["active_paths"]["verapdf"]),
            os.path.join(os.getcwd(), self.cfg["assets"]["logo_file"]),
            {"max_pages": max_p, "depth": depth},
        )

        # 4. ZIP
        log_info("--- [extra] Zip ---")
        rep_paths = [
            r["repaired_path"]
            for r in results
            if r.get("repaired") and r["repaired_path"]
        ]
        if rep_paths:
            create_repair_zip(
                rep_paths, os.path.join(self.reports_dir, f"IMPROVED_{ts}_{safe}.zip")
            )

        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
        return pdf_f
