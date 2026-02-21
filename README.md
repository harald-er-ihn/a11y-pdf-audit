# 🧩 Automated Accessibility Checks for Downloadable PDFs

![Python](https://img.shields.io/badge/Python-3.12-blue?logo=python)
![Flask](https://img.shields.io/badge/Flask-3.0-green?logo=flask)
![Build Status](https://img.shields.io/badge/Build-Passing-brightgreen)
![Pylint Score](https://img.shields.io/badge/Pylint-9.12%2F10-success)
![Security](https://img.shields.io/badge/Bandit-Secure-success)
![License](https://img.shields.io/badge/License-MIT-lightgrey)

> **a11y PDF Audit** is a modular web application designed to automatically check websites for accessible PDF files. It crawls any given URL, downloads discovered PDFs, validates them using VeraPDF, and generates structured HTML and PDF reports automatically.

---

## 🎯 Purpose and Idea

Ensuring digital accessibility is crucial. This tool automates the tedious process of finding and checking PDF files on websites.

It uses **[VeraPDF](https://verapdf.org/)**, a purpose-built, open-source file-format validator covering all PDF/A and PDF/UA parts and conformance levels, to check for compliance with accessibility standards (PDF/UA-1).

## ⭐ Main Features

*   🔍 **Automatic Validation:** Checks PDF/UA compliance via VeraPDF.
*   🌐 **Recursive Crawler:** Searches websites for downloadable PDFs (configurable depth & limit).
*   📊 **Reporting:** Generates detailed reports in JSON, HTML, and PDF formats (using WeasyPrint).
*   💻 **Web Interface:** Easy-to-use Flask frontend with live logs and report overview.
*   ⚙️ **Modular Architecture:** Built using Facade & Controller patterns for scalability (Docker/Fly.io ready).

---

## 🏗️ Technical Architecture Overview

The project is structured to separate concerns between scanning, processing, and reporting.

| Directory / File | Description |
| :--- | :--- |
| `core/` | Central logic and services |
| `├── services/` | Functional modules (Crawler, PDF Processor, Reporting) |
| `├── facade.py` | Facade pattern controlling the full audit workflow |
| `└── controller.py` | Background thread management & Keep-Alive logic |
| `web_app/` | Flask web interface (Routes & Views) |
| `templates/` | HTML templates for frontend & reports |
| `static/` | CSS, JS, and assets |
| `config/config.json` | Central configuration file |
| `Dockerfile` | Container definition for deployment |

---

## ✅ Quality & Testing

We maintain high code quality standards through automated linting and security checks.

| Tool | Purpose | Status / Result |
| :--- | :--- | :--- |
| **flake8** | Formatting & Style Checking | ✅ No critical issues found. |
| **pylint** | Code Quality / Docstrings | ⭐ Score: > 9.0 / 10 points. |
| **bandit** | Security Analysis | 🔒 No high severity findings. |
| **radon cc** | Cyclomatic Complexity | 🌿 Mainly A-level functions. |

---

## ⚠️ Known Issues / Limitations

**VeraPDF vs. axesCheck (PAC)**
There is a known discrepancy between **VeraPDF** (used by this tool) and **axesCheck/PAC** regarding ISO 14289-1:2014 (PDF/UA-1), specifically rule **7.5 (Tables)**.

*   **VeraPDF** tends to be very strict and may report `FAIL` on tables where the headers cannot be determined *algorithmically* according to its strict interpretation of the standard.
*   **axesCheck** might pass the same file if the logical structure is semantically sufficient for screen readers.
*   *Conclusion:* Use the reports from this tool as a strict technical baseline. A "FAIL" in VeraPDF warrants a manual check, but the document might still be accessible in practice.

---

## 🚀 Deployment (Docker & Fly.io)

The app is designed to run in a containerized environment.

### Local Start
```bash
# Build and run using the helper script
./docker_start.sh
```
### Deploy to Fly.io
```bash
fly deploy
```

**Environment Variables:**
```bash
FLASK_HOST: 0.0.0.0
FLASK_PORT: 8000
FLASK_DEBUG: False
PYTHONPATH: /usr/lib/python3/dist-packages:/usr/local/lib/python3.12/site-packages
```

### ❤️ Support & Donation
This tool is free to use. However, running servers costs money, and developing accessible software takes time and effort.
[![Donate with PayPal](https://img.shields.io/badge/Donate-PayPal-gold.svg)](https://www.paypal.me/hutterharald)

## 🧑🏻‍💻 Author & 📜 License
Developed by Dr. Harald Hutter.
Licensed under the MIT License.
