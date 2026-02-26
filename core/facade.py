import os
import shutil
import time

from core.services.generate_report_from_json import create_report
from core.services.pdf_crawler import crawl_site_logic
from core.services.pdf_processor import get_verapdf_version, process_pdf_links
from core.utils.config_loader import load_config
from core.utils.error_utils import log_error, log_info
from core.utils.zip_utils import create_repair_zip


class AuditFacade:
    def __init__(self):
        self.config = load_config()
        self.output_dir = self.config["active_paths"]["output"]
        self.verapdf_path = self.config["active_paths"]["verapdf"]
        self.project_root = os.getcwd()
        self.logo_path = os.path.join(
            self.project_root, self.config["assets"]["logo_file"]
        )
        self.reports_dir = os.path.join(self.output_dir, "reports")
        self.temp_pdf_dir = os.path.join(self.output_dir, "temp_pdfs")
        os.makedirs(self.reports_dir, exist_ok=True)

    def run_full_audit(self, url, max_pages, depth, force_ai=False):
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        safe_name = (
            url.replace("https://", "").replace("http://", "").replace("/", "_")[:30]
        )
        report_base_name = (
            f"REPORT_{timestamp}_{safe_name}_MaxPages{max_pages}_CrawlDepth{depth}"
        )

        link_file = os.path.join(self.reports_dir, f"{report_base_name}_links.txt")
        json_file = os.path.join(self.reports_dir, f"{report_base_name}.json")
        pdf_report = os.path.join(self.reports_dir, f"{report_base_name}.pdf")

        log_info(f"--- [1/3] Crawling {url} ---")
        crawl_site_logic(
            url, link_file, max_pages, depth, self.config["crawler"]["user_agent"]
        )

        log_info("--- [2/3] Processing & Improving PDFs ---")
        results = process_pdf_links(
            link_file,
            json_file,
            self.temp_pdf_dir,
            self.verapdf_path,
            force_ai=force_ai,
        )

        log_info("--- [3/3] Generating Report ---")
        create_report(
            json_file,
            pdf_report,
            url,
            get_verapdf_version(self.verapdf_path),
            self.logo_path,
            {"max_pages": max_pages, "depth": depth},
        )

        log_info("--- [4/4] Finalizing Repair-Package ---")
        repaired_paths = [
            r["repaired_path"]
            for r in results
            if r.get("repaired") and r["repaired_path"]
        ]
        if repaired_paths:
            zip_filename = f"IMPROVED_PACK_{timestamp}_{safe_name}.zip"
            zip_path = os.path.join(self.reports_dir, zip_filename)
            if create_repair_zip(repaired_paths, zip_path):
                log_info(f"✅ ZIP erstellt: {zip_filename}")

        if os.path.exists(self.temp_pdf_dir):
            shutil.rmtree(self.temp_pdf_dir)
        return pdf_report
