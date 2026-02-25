"""
Fassade für den Audit-Prozess.
Kapselt die Aufrufe der verschiedenen Services.
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


class AuditFacade:  # pylint: disable=too-few-public-methods
    """
    Hauptklasse zur Steuerung des Audit-Ablaufs.
    """

    def __init__(self):
        self.config = load_config()
        self.output_dir = self.config["active_paths"]["output"]
        self.verapdf_path = self.config["active_paths"]["verapdf"]

        # Logo-Pfad auflösen
        self.project_root = os.getcwd()
        self.logo_path = os.path.join(
            self.project_root, self.config["assets"]["logo_file"]
        )

        self.reports_dir = os.path.join(self.output_dir, "reports")
        self.temp_pdf_dir = os.path.join(self.output_dir, "temp_pdfs")

        os.makedirs(self.reports_dir, exist_ok=True)

    def run_full_audit(self, url, max_pages, depth):
        """
        Führt den kompletten Audit durch: Crawl -> Check -> Report.
        """
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        safe_name = (
            url.replace("https://", "").replace("http://", "").replace("/", "_")[:30]
        )

        # Name Requirements: REPORT_Timestamp_URL_MaxPages_CrawlDepth.pdf
        report_base_name = (
            f"REPORT_{timestamp}_{safe_name}_" f"MaxPages{max_pages}_CrawlDepth{depth}"
        )

        link_file = os.path.join(self.reports_dir, f"{report_base_name}_links.txt")
        json_file = os.path.join(self.reports_dir, f"{report_base_name}.json")
        pdf_report = os.path.join(self.reports_dir, f"{report_base_name}.pdf")

        log_info(f"--- [1/3] Crawling {url} ---")
        crawl_site_logic(
            start_url=url,
            output_file=link_file,
            max_pages=max_pages,
            max_depth=depth,
            user_agent=self.config["crawler"]["user_agent"],
        )

        log_info("--- [2/3] Processing PDFs ---")
        # WICHTIG: Das Ergebnis der Funktion in der Variable 'results' speichern!
        results = process_pdf_links(
            link_list_file=link_file,
            output_json=json_file,
            temp_dir=self.temp_pdf_dir,
            verapdf_path=self.verapdf_path,
        )
        # In run_full_audit am Ende ergänzen:
        log_info("--- [4/4] Finalizing Repair-Package ---")
        repaired_files = [r["repaired_path"] for r in results if r.get("repaired")]

        if repaired_files:
            zip_name = f"FIX_PACK_{timestamp}_{safe_name}.zip"
            zip_path = os.path.join(self.reports_dir, zip_name)
            create_repair_zip(repaired_files, zip_path)
            log_info(f"✅ ZIP-Paket erstellt: {zip_name}")
        else:
            log_info("ℹ️ Keine Reparaturen notwendig, kein ZIP erstellt.")

        # Cleanup temp_pdfs
        if os.path.exists(self.temp_pdf_dir):
            shutil.rmtree(self.temp_pdf_dir)

        log_info("--- [3/3] Generating Report ---")
        version = get_verapdf_version(self.verapdf_path)

        # Config Info for the Report Header
        config_info = {"max_pages": max_pages, "depth": depth}

        create_report(
            json_file=json_file,
            output_pdf=pdf_report,
            base_url=url,
            verapdf_version=version,
            logo_path=self.logo_path,
            config_info=config_info,
        )

        log_info(f"--- Fertig: {pdf_report} ---")
        return pdf_report
