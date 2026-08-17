# 🧩 Automated Accessibility Checks for Downloadable PDFs

![Python](https://img.shields.io/badge/Python-3.12-blue?logo=python)
![Flask](https://img.shields.io/badge/Flask-3.0-green?logo=flask)
![Build Status](https://img.shields.io/badge/Build-Passing-brightgreen)
![Pylint Score](https://img.shields.io/badge/Pylint-10%2F10-success)
![Security](https://img.shields.io/badge/Bandit-Secure-success)
![License](https://img.shields.io/badge/License-MIT-lightgrey)

> **a11y PDF Audit** is a modular web application designed to automatically check websites for accessible PDF files. 
It crawls any given URL, downloads discovered PDFs, validates them using VeraPDF, and generates structured PDF reports automatically.

---
> **Projektstatus:** Abgeschlossen / archiviert.  
> Dieses Repository wird derzeit nicht mehr aktiv weiterentwickelt.
---
## 🎯 Purpose and Idea

Ensuring digital accessibility is crucial. This tool automates the tedious process of finding and checking PDF files on websites.

It uses **[VeraPDF](https://verapdf.org/)**, a purpose-built, open-source file-format validator covering all PDF/A and PDF/UA parts and conformance levels, 
to check for compliance with accessibility standards (PDF/UA-1).

## ⭐ Main Features (v1.3.0)

*   🔍 **Dual-Audit System:** Validates PDFs simultaneously against the strict ISO PDF/UA-1 standard AND our custom, pragmatic **ScreenReadable** profile.
*   🌐 **Recursive Crawler:** Searches websites for downloadable PDFs (configurable depth & limit) with smart error handling.
*   📊 **Reporting:** Generates detailed reports in PDF formats (using WeasyPrint).
*   🧹 **Auto-Cleanup:** Automatically deletes reports older than 14 days to preserve server storage.
*   💯 **Perfect Performance:** Achieves 100/100 in Google PageSpeed Insights (Performance, Accessibility, Best Practices, SEO).

---

## 🏗️ Technical Architecture Overview

The project uses a modern Producer/Consumer pattern to separate fast web serving from heavy AI processing.

| Directory / File | Description |
| :--- | :--- |
| `core/services/` | Functional modules (Crawler, PDF Processor, Reporting) |
| `core/facade.py` | Facade pattern controlling the full audit workflow |
| `core/controller.py` | Controller pattern controlling background processes |
| `web_app/` | Flask web interface (Routes & Views acting as the Job Producer) |
| `templates/` | HTML templates for frontend & reports |
| `config/config.json` | Central configuration file |
| `Dockerfile`| Enabling this application to run consistently across different computing environments |

---

## ✅ Quality & Testing

We maintain high code quality standards through automated linting and security checks.

| Tool | Purpose | Status / Result |
| :--- | :--- | :--- |
| **flake8** | Formatting & Style Checking | ✅ No critical issues found. |
| **pylint** | Code Quality / Docstrings | ⭐ Score: > 9.5 / 10 points. |
| **bandit** | Security Analysis | 🔒 No high severity findings. |
| **radon cc** | Cyclomatic Complexity | 🌿 Mainly A-level functions. |

---

## 🟡 Known Issues / Limitations

**VeraPDF vs. axesCheck (PAC)**
There is a known discrepancy between **VeraPDF** (used by this tool) and **axesCheck/PAC** regarding ISO 14289-1:2014 (PDF/UA-1), specifically rule **7.5 (Tables)**.

*   **VeraPDF** tends to be very strict and may report `FAIL` on tables where the headers cannot be determined *algorithmically*.
*   **Solution:** We provide the **ScreenReadable Profile** alongside the strict check to bridge this gap.

---

## 🚀 Deployment (Docker Compose)

The app is designed to run in a fully containerized environment.

### Local Start
```bash
# Formats code, tests it, and boots the docker-compose stack
./secure_startup.sh
```
## ❤️ Support & Donation
This tool is free to use. However, running servers costs money, and developing accessible software takes time and effort.
[![Donate with PayPal](https://img.shields.io/badge/Donate-PayPal-gold.svg)](https://www.paypal.me/hutterharald)

## 🧑🏻‍💻 Author & 📜 License
Developed by Dr. Harald Hutter.
Licensed under the MIT License.

VeraPDF is open source software dual licensed under MPL v2+ and GPL v3+ 
- see [Licenses](https://a11y-pdf-audit.fly.dev/licenses) for details. 
