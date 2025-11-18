#!/usr/bin/env python3
"""
Full Pipeline Runner - รันทั้งระบบอัตโนมัติ
ประกอบด้วย 3 ขั้นตอน:
1. Google Alert Collection (ดึง URLs จาก Gmail)
2. Smart Scraping (Scrape เนื้อหาจาก URLs)
3. LLM Extraction (จำแนกและสกัดข้อมูล)

Usage:
    python full_pipeline.py
    python full_pipeline.py --skip-alert        # ข้าม Google Alert
    python full_pipeline.py --skip-scraping     # ข้าม Smart Scraping
    python full_pipeline.py --truncate-input    # Truncate input_df.csv หลัง pipeline สำเร็จ
    python full_pipeline.py --help
"""

import subprocess
import sys
import argparse
import logging
from pathlib import Path
from datetime import datetime
import shutil
import pandas as pd

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def print_banner():
    """Print welcome banner"""
    banner = """
================================================================
         Thai News Processing - FULL PIPELINE
         Google Alert -> Scraping -> LLM Extraction
================================================================
"""
    print(banner)


def print_step_header(step_num, step_name):
    """Print step header"""
    print("\n" + "="*70)
    print(f"  STEP {step_num}/3: {step_name}")
    print("="*70 + "\n")


def run_command(cmd, description, allow_failure=False, cwd=None):
    """
    Run a command and handle errors

    Args:
        cmd: Command to run (list)
        description: Description of the command
        allow_failure: Allow command to fail without stopping pipeline
        cwd: Working directory for the command

    Returns:
        bool: True if successful, False otherwise
    """
    logger.info(f"Running: {description}")
    logger.debug(f"Command: {' '.join(cmd)}")

    try:
        result = subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            text=True,
            cwd=cwd
        )
        logger.info(f"[OK] {description} - SUCCESS")
        if result.stdout:
            print(result.stdout)
        return True

    except subprocess.CalledProcessError as e:
        logger.error(f"[FAIL] {description} - FAILED")
        logger.error(f"Exit code: {e.returncode}")
        if e.stderr:
            logger.error(f"Error output:\n{e.stderr}")

        if not allow_failure:
            logger.error("Pipeline stopped due to error")
            sys.exit(1)
        return False

    except FileNotFoundError:
        logger.error(f"[FAIL] Command not found: {cmd[0]}")
        if not allow_failure:
            sys.exit(1)
        return False


def step1_google_alert(skip=False):
    """Step 1: Google Alert Collection"""
    if skip:
        logger.info("[SKIP] Skipping Google Alert Collection (--skip-alert)")
        return True

    print_step_header(1, "Google Alert Collection")

    script_dir = Path(__file__).parent
    script_path = script_dir / "google_alert_from_email.py"
    if not script_path.exists():
        logger.warning(f"Google Alert script not found: {script_path}")
        logger.warning("Skipping this step...")
        return True

    cmd = [sys.executable, str(script_path)]
    return run_command(
        cmd,
        "Collecting URLs from Google Alerts (Gmail)",
        allow_failure=True,  # Allow failure if no new alerts
        cwd=str(script_dir)
    )


def step2_smart_scraping(skip=False):
    """Step 2: Smart Scraping"""
    if skip:
        logger.info("[SKIP] Skipping Smart Scraping (--skip-scraping)")
        return True

    print_step_header(2, "Smart Web Scraping")

    script_dir = Path(__file__).parent
    data_dir = script_dir.parent / "data"
    script_path = script_dir / "smart_scraper.py"
    input_file = data_dir / "input_df.csv"
    output_file = data_dir / "prepare_data.csv"

    if not script_path.exists():
        logger.warning(f"Smart Scraper script not found: {script_path}")
        logger.warning("Skipping this step...")
        return True

    if not input_file.exists():
        logger.warning(f"Input file not found: {input_file}")
        logger.warning("Skipping scraping - no URLs to scrape")
        return True

    cmd = [sys.executable, str(script_path), "--input", str(input_file), "--output", str(output_file)]
    return run_command(
        cmd,
        "Scraping content from URLs",
        allow_failure=False,
        cwd=str(script_dir)
    )


def step3_llm_extraction():
    """Step 3: LLM Extraction Pipeline"""
    print_step_header(3, "LLM Extraction Pipeline")

    script_dir = Path(__file__).parent
    script_path = script_dir / "pipeline_runner.py"

    if not script_path.exists():
        logger.error(f"Pipeline runner not found: {script_path}")
        sys.exit(1)

    cmd = [sys.executable, str(script_path)]
    return run_command(
        cmd,
        "Running LLM classification and extraction",
        allow_failure=False,
        cwd=str(script_dir)
    )


def truncate_input_csv(backup=True):
    """
    Truncate input_df.csv หลังจาก pipeline สำเร็จ
    เพื่อป้องกันไม่ให้ขั้นตอนต่อไปอ่านข้อมูลเก่าซ้ำ

    Args:
        backup: สำรอง input_df.csv ก่อน truncate (default: True)

    Returns:
        bool: True if successful, False otherwise
    """
    logger.info("Truncating input_df.csv...")

    script_dir = Path(__file__).parent
    data_dir = script_dir.parent / "data"
    input_df_path = data_dir / "input_df.csv"

    if not input_df_path.exists():
        logger.warning(f"input_df.csv not found at {input_df_path}")
        return True  # ไม่มีไฟล์ก็ถือว่าสำเร็จ

    try:
        # สำรองไฟล์ก่อน truncate
        if backup:
            backup_dir = data_dir / "backups"
            backup_dir.mkdir(exist_ok=True)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = backup_dir / f"input_df_backup_{timestamp}.csv"

            shutil.copy2(input_df_path, backup_path)
            logger.info(f"✓ Backed up to: {backup_path.name}")

        # อ่านไฟล์เพื่อดูจำนวนแถว
        df = pd.read_csv(input_df_path)
        row_count = len(df)
        logger.info(f"✓ Found {row_count} URLs in input_df.csv")

        # Truncate โดยสร้างไฟล์ว่างใหม่
        empty_df = pd.DataFrame(columns=['url', 'context', 'is_news'])
        empty_df.to_csv(input_df_path, index=False)

        logger.info(f"✓ Truncated input_df.csv (removed {row_count} URLs)")
        logger.info("✓ input_df.csv is now empty and ready for next run")

        return True

    except Exception as e:
        logger.error(f"✗ Failed to truncate input_df.csv: {e}")
        return False


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='Full Thai News Processing Pipeline',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run full pipeline (all 3 steps)
  python full_pipeline.py

  # Run pipeline and truncate input_df.csv after completion
  python full_pipeline.py --truncate-input

  # Skip Google Alert collection (use existing input_df.csv)
  python full_pipeline.py --skip-alert

  # Skip both Alert and Scraping (use existing prepare_data.csv)
  python full_pipeline.py --skip-alert --skip-scraping

  # Only run LLM extraction
  python full_pipeline.py --skip-alert --skip-scraping

  # Run with truncation but keep input (for debugging)
  python full_pipeline.py --truncate-input --keep-input

Steps:
  1. Google Alert Collection  -> input_df.csv
  2. Smart Scraping          -> prepare_data.csv
  3. LLM Extraction          -> heat_data.csv
  4. (Optional) Truncate input_df.csv (with --truncate-input)
        """
    )

    parser.add_argument(
        '--skip-alert',
        action='store_true',
        help='Skip Google Alert collection (use existing input_df.csv)'
    )

    parser.add_argument(
        '--skip-scraping',
        action='store_true',
        help='Skip Smart Scraping (use existing prepare_data.csv)'
    )

    parser.add_argument(
        '--truncate-input',
        action='store_true',
        help='Truncate input_df.csv after successful pipeline completion'
    )

    parser.add_argument(
        '--keep-input',
        action='store_true',
        help='Keep input_df.csv (do not truncate even with --truncate-input)'
    )

    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose (DEBUG) logging'
    )

    args = parser.parse_args()

    # Set verbose logging
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Start pipeline
    start_time = datetime.now()
    print_banner()
    logger.info(f"Starting Full Pipeline at {start_time.strftime('%Y-%m-%d %H:%M:%S')}")

    try:
        # Step 1: Google Alert
        step1_google_alert(skip=args.skip_alert)

        # Step 2: Smart Scraping
        step2_smart_scraping(skip=args.skip_scraping)

        # Step 3: LLM Extraction
        step3_llm_extraction()

        # Step 4 (Optional): Truncate input_df.csv
        if args.truncate_input and not args.keep_input:
            print("\n" + "="*70)
            print("  CLEANUP: Truncating input_df.csv")
            print("="*70 + "\n")
            truncate_input_csv(backup=True)
        elif args.keep_input:
            logger.info("[SKIP] Keeping input_df.csv (--keep-input)")

        # Success
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        print("\n" + "="*70)
        print("  [OK] PIPELINE COMPLETED SUCCESSFULLY")
        print("="*70)
        logger.info(f"Total Duration: {duration:.2f}s ({duration/60:.2f} min)")
        logger.info(f"Output: heat_data.csv")
        if args.truncate_input and not args.keep_input:
            logger.info(f"Note: input_df.csv has been truncated (backup saved)")
        print()

        return 0

    except KeyboardInterrupt:
        logger.warning("\n\nPipeline interrupted by user (Ctrl+C)")
        return 130

    except Exception as e:
        logger.error(f"\n\nPipeline failed with error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
