#!/usr/bin/env python3
"""
Thai News Processing Pipeline Runner (New Config-Driven Version)
รันระบบ extraction pipeline แบบใหม่ที่ใช้ config.json

Usage:
    python pipeline_runner.py
    python pipeline_runner.py --config custom_config.json
    python pipeline_runner.py --help
"""

import logging
import argparse
import sys
from pathlib import Path
from datetime import datetime

# Load environment variables from .env file
from dotenv import load_dotenv

# Load .env from the same directory as this script
env_path = Path(__file__).parent / '.env'
load_dotenv(dotenv_path=env_path)  # Load .env file before importing other modules

# Import pipeline components
from config_loader import ConfigLoader, load_config
from extraction_engine import ExtractionEngine

# Create logs directory if not exists
Path('logs').mkdir(parents=True, exist_ok=True)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/pipeline.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def setup_logging(config: ConfigLoader):
    """
    Setup logging based on config

    Args:
        config: ConfigLoader instance
    """
    log_config = config.get_advanced_config('logging')

    # Create logs directory if needed
    log_file = Path(log_config.get('filename', 'logs/pipeline.log'))
    log_file.parent.mkdir(parents=True, exist_ok=True)

    # Set log level
    level_str = log_config.get('level', 'INFO')
    level = getattr(logging, level_str, logging.INFO)

    # Update logging configuration
    logging.getLogger().setLevel(level)

    logger.info(f"[OK] Logging configured: level={level_str}, file={log_file}")


def print_banner():
    """Print welcome banner"""
    banner = """
================================================================
    Thai News Processing Pipeline v2.0
    Config-Driven Extraction Engine

    Powered by: Ollama Qwen3 / Typhoon 12B
================================================================
"""
    print(banner)


def print_config_summary(config: ConfigLoader):
    """
    Print configuration summary

    Args:
        config: ConfigLoader instance
    """
    logger.info("\n" + "="*60)
    logger.info("CONFIGURATION SUMMARY")
    logger.info("="*60)

    # LLM config
    llm_config = config.get_llm_config()
    logger.info(f"LLM Provider:")
    logger.info(f"  Provider: {llm_config['provider']}")
    logger.info(f"  Model: {llm_config['model']}")
    logger.info(f"  Temperature: {llm_config['temperature']}")
    logger.info(f"  Max Tokens: {llm_config['max_tokens']}")

    # Data paths
    paths = config.get_data_paths()
    logger.info(f"\nData Paths:")
    logger.info(f"  Input: {paths['input_file']}")
    logger.info(f"  Base: {paths['base_file']}")
    logger.info(f"  Output (filled): {paths['output_filled_file']}")
    logger.info(f"  Output (heat_data): {paths['output_heat_data_file']}")

    # Processing config
    proc_config = config.get_processing_config()
    logger.info(f"\nProcessing:")
    logger.info(f"  Mode: {proc_config['mode']}")
    logger.info(f"  Batch size: {proc_config['batch_size']}")
    logger.info(f"  Skip processed: {proc_config['skip_processed_records']}")

    # Enabled columns
    enabled_cols = config.get_enabled_columns()
    logger.info(f"\nEnabled Columns: {len(enabled_cols)}")

    logger.info("="*60 + "\n")


def run_pipeline(config_path: str = "config.json"):
    """
    Run the complete extraction pipeline

    Args:
        config_path: Path to config.json file
    """
    start_time = datetime.now()

    try:
        # Print banner
        print_banner()

        logger.info(f"[START] Starting pipeline with config: {config_path}")

        # Load configuration
        logger.info("[LOAD] Loading configuration...")
        config = load_config(config_path)
        logger.info(f"[OK] Configuration loaded: {config}")

        # Setup logging
        setup_logging(config)

        # Print configuration summary
        print_config_summary(config)

        # Create extraction engine
        logger.info("[INIT] Initializing extraction engine...")
        engine = ExtractionEngine(config)
        logger.info("[OK] Extraction engine initialized")

        # Run pipeline
        logger.info("\n" + "="*60)
        logger.info("[START] STARTING EXTRACTION PIPELINE")
        logger.info("="*60 + "\n")

        engine.run()

        # Calculate total time
        end_time = datetime.now()
        duration = end_time - start_time
        total_seconds = duration.total_seconds()

        # Print final summary
        logger.info("\n" + "="*60)
        logger.info("[SUCCESS] PIPELINE COMPLETED SUCCESSFULLY")
        logger.info("="*60)
        logger.info(f"Start Time: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"End Time: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"Total Duration: {total_seconds:.2f}s ({total_seconds/60:.2f} min)")
        logger.info("="*60 + "\n")

        return 0

    except FileNotFoundError as e:
        logger.error(f"\n[ERROR] File not found: {e}")
        logger.error("Please check that all required files exist:")
        logger.error("  - config.json")
        logger.error("  - Input data file (specified in config)")
        return 1

    except Exception as e:
        logger.error(f"\n[ERROR] Pipeline failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description='Thai News Processing Pipeline v2.0 (Config-Driven)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run with default config.json
  python pipeline_runner.py

  # Run with custom config file
  python pipeline_runner.py --config my_config.json

  # Show config information only (dry run)
  python pipeline_runner.py --dry-run

Configuration:
  Edit config.json to change:
  - LLM provider (typhoon or ollama)
  - Data file paths (input, base, output)
  - Processing mode (incremental or full)
  - Enabled/disabled columns
  - And more...

For more information, see README.md
        """
    )

    parser.add_argument(
        '--config',
        default='config.json',
        help='Path to configuration file (default: config.json)'
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Load and validate config without running pipeline'
    )

    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose (DEBUG) logging'
    )

    args = parser.parse_args()

    # Set verbose logging if requested
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.debug("Verbose logging enabled")

    # Dry run - just validate config
    if args.dry_run:
        try:
            print_banner()
            logger.info(f"[DRY-RUN] Validating config from {args.config}")

            config = load_config(args.config)
            logger.info(f"[OK] Configuration valid: {config}")

            print_config_summary(config)

            logger.info("[OK] Dry run completed - config is valid!")
            return 0

        except Exception as e:
            logger.error(f"[ERROR] Config validation failed: {e}")
            return 1

    # Run full pipeline
    exit_code = run_pipeline(args.config)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
