# 🌐 Thai News Processing Pipeline
**Automated news collection, scraping, classification, and data extraction system using LLM technology**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)

A comprehensive system for collecting and processing Thai health crisis news from Google Alerts, combining web scraping with LLM-powered classification and data extraction.

---

## 📋 Table of Contents
- [Installation & Setup](#-installation--setup)
- [File Structure](#-file-structure)
- [Quick Start Commands](#-quick-start-commands)
- [Testing & Validation](#-testing--validation)
- [Workflow Examples](#-workflow-examples)
- [Output Files](#-output-files)
- [Troubleshooting](#-troubleshooting)
- [Configuration](#-configuration)
- [Features](#-features)

---

## 🚀 Installation & Setup

### Step 1: Install Python Requirements

Install **basic** dependencies (required for all steps):

```bash
pip install pandas requests beautifulsoup4 python-dotenv
```

Install **additional** dependencies for web scraping (Step 2):

```bash
pip install tqdm playwright trafilatura lxml
```

**Install all dependencies at once:**

```bash
pip install pandas requests beautifulsoup4 python-dotenv tqdm playwright trafilatura lxml
```

| Package | Purpose | Required |
|---------|---------|----------|
| **pandas** | Data processing | ✓ Yes |
| **requests** | HTTP requests | ✓ Yes |
| **beautifulsoup4** | HTML parsing | ✓ Yes |
| **python-dotenv** | Environment variables | ✓ Yes |
| **tqdm** | Progress bars | ✓ For scraping |
| **playwright** | Browser automation | ✓ For scraping |
| **trafilatura** | Article extraction | ✓ For scraping |
| **lxml** | Advanced HTML parsing | ✓ For scraping |

### Step 2: Configure API Keys

Create a `.env` file in the main directory:

```env
TYPHOON_API_KEY=your_typhoon_api_key_here
```

Or configure `google_pass.gitignore` for Gmail integration:

```json
{
  "email": "your-email@gmail.com",
  "app_password": "your-app-password"
}
```

### Step 3: Configure Pipeline Settings

Edit `config.json` to customize:
- **LLM Provider**: `typhoon` or `ollama`
- **Data Paths**: Input/output file locations
- **Extraction Columns**: Which fields to extract
- **Processing Mode**: `incremental` or `full`

---

## 📦 File Structure

### Core Pipeline Scripts
```
main/
├── full_pipeline.py              # 🎯 Main entry point / orchestrator
├── pipeline_runner.py            # LLM extraction runner
├── extraction_engine.py          # Classification & extraction logic
├── google_alert_from_email.py    # 📧 Gmail URL fetcher
├── smart_scraper.py              # 🌐 Smart incremental scraper
├── news_scraper_1.2.py           # 📰 Web content scraper (Playwright)
├── csv_processor.py              # CSV utilities
├── llm_client.py                 # LLM API wrapper (Typhoon)
├── config_loader.py              # Configuration handler
└── .env                          # Environment variables (API keys)
```

### Testing & Validation
```
├── test_pipeline_integration.py   # Integration tests
├── validate_pipeline.py           # Data validation tool
└── run_tests.bat                  # Test runner (Windows)
```

### Data Files
```
data/
├── input_df.csv                  # URLs from Google Alerts
├── prepare_data.csv              # Scraped content
├── heat_data.csv                 # Final output (relevant news)
└── base_heat_map.csv             # Cumulative dedup database
```

### Configuration & Documentation
```
├── config.json                   # Pipeline settings
├── README.md                     # Main guide
├── SETUP_GUIDE.md                # Installation guide
├── USAGE_GUIDE.md                # Usage examples
└── COMMANDS.txt                  # Command reference
```

---

## ⚡ Quick Start Commands

### A. Run Full Pipeline (All Steps)

```bash
cd main
python full_pipeline.py
```

**What it does:**
1. Fetch URLs from Google Alerts (Gmail)
2. Scrape web page content
3. Classify news relevance using LLM
4. Extract structured data
5. Output: `heat_data.csv`

### B. Run with Input Truncation (Recommended for Production)

```bash
cd main
python full_pipeline.py --truncate-input
```

Same as above, plus:
- ✓ Truncates `input_df.csv` after completion
- ✓ Prevents duplicate processing in next run
- ✓ Creates automatic backup before truncating

### C. Skip Google Alerts (Use Existing Data)

```bash
cd main
python full_pipeline.py --skip-alert
```

Uses existing `input_df.csv` without fetching from Gmail

### D. Skip Scraping (LLM Only)

```bash
cd main
python full_pipeline.py --skip-alert --skip-scraping
```

Only runs LLM extraction on existing `prepare_data.csv`

### E. Verbose Mode (Detailed Logging)

```bash
cd main
python full_pipeline.py --verbose
```

---

## 🧪 Testing & Validation

### Option 1: Using Batch Script (Windows)

**Quick Test** (1 minute - Config & files only):
```batch
run_tests.bat quick
```

**Test Specific Component:**
```batch
run_tests.bat google          # Google Alert Fetch
run_tests.bat scraping        # Web Scraping
run_tests.bat classification  # LLM Classification
run_tests.bat validate        # Data Validation
```

**Full Pipeline Test** (15-30 minutes):
```batch
run_tests.bat full
```

**Comprehensive Test** (30-60 minutes):
```batch
run_tests.bat all
```

### Option 2: Using Python Scripts

**Integration Tests:**
```bash
python test_pipeline_integration.py --test-google-alert
python test_pipeline_integration.py --test-scraping
python test_pipeline_integration.py --test-classification
python test_pipeline_integration.py --test-deduplication
python test_pipeline_integration.py --test-truncation
python test_pipeline_integration.py --test-full-pipeline
python test_pipeline_integration.py --test-all
```

**Data Validation:**
```bash
python validate_pipeline.py --check-all
python validate_pipeline.py --check-input
python validate_pipeline.py --check-prepare
python validate_pipeline.py --check-heat
python validate_pipeline.py --check-consistency
python validate_pipeline.py --check-config
```

---

## 📚 Workflow Examples

### Example 1: First Time Setup & Test

1. **Install dependencies:**
   ```bash
   pip install pandas requests beautifulsoup4 python-dotenv
   ```

2. **Configure:**
   - Edit `config.json`
   - Create `.env` with API keys
   - Update `google_pass.gitignore` with Gmail credentials

3. **Validate setup:**
   ```bash
   run_tests.bat quick
   ```

4. **Test full pipeline:**
   ```bash
   run_tests.bat full
   ```

5. **Check results:**
   ```bash
   run_tests.bat validate
   ```

### Example 2: Daily Processing Run

1. **Run pipeline with truncation:**
   ```bash
   python full_pipeline.py --truncate-input
   ```

2. **Check results:**
   ```bash
   python validate_pipeline.py --check-all
   ```

3. **Review output:** Check `heat_data.csv` for relevant news

### Example 3: Troubleshooting

1. **Test Google Alerts connection:**
   ```bash
   python google_alert_from_email.py
   ```

2. **Test scraping:**
   ```bash
   python smart_scraper.py --input input_df.csv --output prepare_data.csv
   ```

3. **Test LLM classification:**
   ```bash
   python pipeline_runner.py --verbose
   ```

4. **Validate data integrity:**
   ```bash
   python validate_pipeline.py --check-all
   ```

---

## 📊 Output Files

After running the pipeline, you'll get:

| File | Description |
|------|-------------|
| **heat_data.csv** | Final output - Relevant news only with extracted data |
| **prepare_data_filled.csv** | All processed records with classification results |
| **base_heat_map.csv** | Cumulative database for deduplication |
| **test_report.json** | Test execution results |
| **validation_report.json** | Data validation results |

### heat_data.csv Columns
- `url` - News article URL
- `content` - Article text
- `is_relevant` - Classification result (0/1)
- `death_count` - Number of deaths
- `injured_count` - Number of injuries
- `location_province` - Province affected
- `incident_date` - Date of incident
- `death_cause` - Cause of death
- ... and more fields based on configuration

---

## 🐛 Troubleshooting

### Problem: Python not found

**Solution:**
```bash
# Make sure Python is installed and in PATH
python --version
```

### Problem: Module not found error

**Solution:**
```bash
pip install pandas requests beautifulsoup4 python-dotenv
```

### Problem: Google Alert fetch fails

**Solution:**
1. Check `google_pass.gitignore` has correct credentials
2. Enable "App Password" in Gmail settings
3. Verify Gmail account is accessible

### Problem: LLM API error

**Solution:**
1. Check API key in `.env` file
2. Verify API key is valid
3. Or use Ollama with local LLM in `config.json`

### Problem: Scraping timeout

**Solution:**
1. Check internet connection
2. Some URLs may be blocked or slow
3. Increase timeout in `config.json`

### Problem: Tests take too long

**Solution:**
1. Run smaller tests first (quick, google, scraping)
2. Use `--skip-alert --skip-scraping` to skip network requests
3. Run tests at off-peak hours

---

## ⚙️ Configuration (config.json)

### Key Settings

| Setting | Value | Purpose |
|---------|-------|---------|
| `llm_provider` | `typhoon` / `ollama` | Which LLM to use |
| `mode` | `incremental` / `full` | Processing mode |
| `skip_processed_records` | `true` / `false` | Skip already processed |
| `batch_size` | `20` | LLM processing batch size |
| `enable_all_location` | `true` / `false` | Extract location fields |
| `enable_all_medical` | `true` / `false` | Extract medical fields |
| `enable_all_temperature` | `true` / `false` | Extract temperature fields |

For detailed configuration options, see **SETUP_GUIDE.md**

---

## ✨ Features

- ✅ **Automated Collection** - Google Alerts from Gmail
- ✅ **Smart Scraping** - Incremental web scraping
- ✅ **LLM Classification** - News relevance detection
- ✅ **Data Extraction** - Death counts, locations, dates, causes
- ✅ **Deduplication** - Prevent duplicate processing
- ✅ **Input Truncation** - Automatic cleanup after processing
- ✅ **Testing Suite** - Comprehensive test coverage
- ✅ **Data Validation** - Integrity checking
- ✅ **Backup Management** - Automatic backups
- ✅ **Thai Support** - Multi-language text processing

---

## 📖 Additional Resources

For more detailed information, see:

- **README.txt** - Quick reference guide
- **SETUP_GUIDE.md** - Detailed installation steps
- **USAGE_GUIDE.md** - Usage examples and advanced topics
- **COMMANDS.txt** - Complete command reference
- **FILES_USAGE_SUMMARY.md** - File dependency information
- **DEPENDENCY_CHECK_REPORT.txt** - Package and file dependency validation

---

## 🆘 Questions or Issues?

1. Check the documentation files listed above
2. Review test output in `test_report.json`
3. Check validation results in `validation_report.json`

---

## ⚡ Quick Reference Card

```bash
# Install dependencies
pip install pandas requests beautifulsoup4 python-dotenv

# Run pipeline with truncation (PRODUCTION)
python full_pipeline.py --truncate-input

# Quick test (1 minute)
run_tests.bat quick

# Full test (15-30 minutes)
run_tests.bat full

# Validate all data
python validate_pipeline.py --check-all

# View help
python full_pipeline.py --help
```

---

## 📝 Version Info

| Item | Value |
|------|-------|
| **Version** | 1.1 |
| **Created** | 2025-01-17 |
| **Updated** | 2025-11-19 (Added news_scraper_1.2.py & dependencies) |
| **License** | MIT |
| **Python** | 3.8+ (Tested with 3.11.9) |
| **Status** | ✅ Production Ready |

---

**Department of Disease Control (Thailand)** - Public Health Surveillance System
