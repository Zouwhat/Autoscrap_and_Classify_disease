"""
Config Loader for Epic1_3 Pipeline
โหลดและจัดการ configuration จาก config.json
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any
import os

logger = logging.getLogger(__name__)


class ConfigLoadError(Exception):
    """Exception raised when config loading fails"""
    pass


class ConfigLoader:
    """
    โหลดและจัดการ configuration จาก config.json

    Features:
    - Load and validate config file
    - Apply bulk operations (enable/disable column groups)
    - Provide helper methods for accessing config
    - Handle path resolution
    """

    def __init__(self, config_path: str = "config.json"):
        """
        Initialize ConfigLoader

        Args:
            config_path: Path to config.json file
        """
        self.config_path = Path(config_path)
        self.config = None
        self._load_config()
        self._apply_bulk_operations()
        self._validate_config()

    def _load_config(self):
        """Load config from JSON file"""
        if not self.config_path.exists():
            raise ConfigLoadError(f"Config file not found: {self.config_path}")

        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                self.config = json.load(f)
            logger.info(f"[OK] Config loaded from {self.config_path}")
        except json.JSONDecodeError as e:
            raise ConfigLoadError(f"Invalid JSON in config file: {e}")
        except Exception as e:
            raise ConfigLoadError(f"Failed to load config: {e}")

    def _apply_bulk_operations(self):
        """Apply bulk enable/disable operations to column groups"""
        if not self.config:
            return

        bulk_ops = self.config.get('columns', {}).get('bulk_operations', {})
        groups = self.config.get('columns', {}).get('column_groups', {})
        schema = self.config.get('columns', {}).get('schema', [])

        # Map group names to bulk operation keys
        group_mappings = {
            'location': 'enable_all_location',
            'medical': 'enable_all_medical',
            'temperature': 'enable_all_temperature',
            'datetime': 'enable_all_datetime',
            'basic_info': 'enable_all_basic_info'
        }

        # Apply bulk operations
        for group_name, bulk_key in group_mappings.items():
            if bulk_key in bulk_ops:
                enabled = bulk_ops[bulk_key]
                column_names = groups.get(group_name, [])

                # Update schema
                for col in schema:
                    if col['name'] in column_names:
                        col['enabled'] = enabled
                        logger.debug(f"Bulk operation: {col['name']} -> enabled={enabled}")

        logger.info("[OK] Bulk operations applied")

    def _validate_config(self):
        """Validate config structure and required fields"""
        if not self.config:
            raise ConfigLoadError("Config is empty")

        # Check required top-level keys
        required_keys = ['llm_provider', 'data_paths', 'llm_settings', 'columns', 'prompts']
        missing_keys = [key for key in required_keys if key not in self.config]

        if missing_keys:
            raise ConfigLoadError(f"Missing required config keys: {missing_keys}")

        # Validate LLM provider
        llm_provider = self.config['llm_provider']
        if llm_provider not in self.config['llm_settings']:
            raise ConfigLoadError(f"LLM provider '{llm_provider}' not found in llm_settings")

        # Validate data paths
        required_paths = ['input_file', 'base_file', 'output_filled_file', 'output_heat_data_file']
        data_paths = self.config['data_paths']
        missing_paths = [key for key in required_paths if key not in data_paths]

        if missing_paths:
            raise ConfigLoadError(f"Missing required data paths: {missing_paths}")

        # Check if input file exists (base file can be created)
        input_file = Path(data_paths['input_file'])
        if not input_file.exists():
            logger.warning(f"[WARN] Input file not found: {input_file}")

        logger.info("[OK] Config validation passed")

    def get_llm_config(self) -> Dict[str, Any]:
        """
        Get LLM configuration for selected provider

        Returns:
            Dict containing LLM settings
        """
        provider = self.config['llm_provider']
        llm_settings = self.config['llm_settings'][provider].copy()
        llm_settings['provider'] = provider
        return llm_settings

    def get_data_paths(self) -> Dict[str, str]:
        """
        Get all data file paths

        Returns:
            Dict with keys: input_file, base_file, output_filled_file, output_heat_data_file
        """
        return self.config['data_paths'].copy()

    def get_processing_config(self) -> Dict[str, Any]:
        """
        Get processing configuration

        Returns:
            Dict containing processing settings
        """
        return self.config['processing'].copy()

    def get_enabled_columns(self) -> List[Dict[str, Any]]:
        """
        Get list of enabled columns for extraction

        Returns:
            List of column definitions with enabled=True
        """
        schema = self.config['columns']['schema']
        enabled = [col for col in schema if col.get('enabled', False)]
        logger.info(f"[OK] Found {len(enabled)} enabled columns out of {len(schema)} total")
        return enabled

    def get_all_columns(self) -> List[Dict[str, Any]]:
        """
        Get all columns (enabled and disabled)

        Returns:
            List of all column definitions
        """
        return self.config['columns']['schema']

    def get_column_by_name(self, column_name: str) -> Optional[Dict[str, Any]]:
        """
        Get column definition by name

        Args:
            column_name: Name of the column

        Returns:
            Column definition dict or None if not found
        """
        schema = self.config['columns']['schema']
        for col in schema:
            if col['name'] == column_name:
                return col
        return None

    def get_prompts(self) -> Dict[str, Any]:
        """
        Get prompt templates

        Returns:
            Dict with classification and extraction prompts
        """
        return self.config['prompts'].copy()

    def get_classification_prompt(self) -> Dict[str, str]:
        """Get classification prompt template"""
        return self.config['prompts']['classification'].copy()

    def get_extraction_prompt(self) -> Dict[str, str]:
        """Get extraction prompt template"""
        return self.config['prompts']['extraction'].copy()

    def get_advanced_config(self, section: str) -> Dict[str, Any]:
        """
        Get advanced configuration section

        Args:
            section: Section name (e.g., 'base_database', 'processing_details', 'validation')

        Returns:
            Configuration dict for the section
        """
        return self.config.get('advanced', {}).get(section, {}).copy()

    def get_validation_rules(self) -> Dict[str, Any]:
        """Get column validation rules"""
        return self.config.get('advanced', {}).get('column_validation_rules', {}).copy()

    def is_base_database_enabled(self) -> bool:
        """Check if base database (incremental processing) is enabled"""
        return self.config.get('advanced', {}).get('base_database', {}).get('enabled', True)

    def get_backup_dir(self) -> str:
        """Get backup directory path"""
        return self.config.get('advanced', {}).get('base_database', {}).get('backup_dir', 'backups')

    def should_skip_processed_records(self) -> bool:
        """Check if processed records should be skipped (incremental mode)"""
        return self.config.get('processing', {}).get('skip_processed_records', True)

    def get_batch_size(self) -> int:
        """Get processing batch size"""
        return self.config.get('processing', {}).get('batch_size', 20)

    def reload(self):
        """Reload configuration from file"""
        logger.info("Reloading configuration...")
        self._load_config()
        self._apply_bulk_operations()
        self._validate_config()
        logger.info("[OK] Configuration reloaded")

    def __repr__(self):
        """String representation"""
        provider = self.config.get('llm_provider', 'unknown')
        mode = self.config.get('processing', {}).get('mode', 'unknown')
        enabled_cols = len(self.get_enabled_columns())
        return f"ConfigLoader(provider={provider}, mode={mode}, enabled_columns={enabled_cols})"


def load_config(config_path: str = "config.json") -> ConfigLoader:
    """
    Convenience function to load config

    Args:
        config_path: Path to config.json file

    Returns:
        ConfigLoader instance
    """
    return ConfigLoader(config_path)


# Example usage
if __name__ == "__main__":
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    try:
        # Load config
        config = load_config("config.json")

        print("\n" + "="*60)
        print("📋 CONFIG LOADER TEST")
        print("="*60)

        # Print config info
        print(f"\n{config}")

        # LLM config
        llm_config = config.get_llm_config()
        print(f"\n[LLM] LLM Provider: {llm_config['provider']}")
        print(f"   Model: {llm_config['model']}")
        print(f"   Temperature: {llm_config['temperature']}")

        # Data paths
        paths = config.get_data_paths()
        print(f"\n[DATA] Data Paths:")
        for key, path in paths.items():
            exists = "[OK]" if Path(path).exists() else "[ERROR]"
            print(f"   {exists} {key}: {path}")

        # Processing config
        proc_config = config.get_processing_config()
        print(f"\n[PROC] Processing:")
        print(f"   Mode: {proc_config['mode']}")
        print(f"   Batch size: {proc_config['batch_size']}")
        print(f"   Skip processed: {proc_config['skip_processed_records']}")

        # Enabled columns
        enabled_cols = config.get_enabled_columns()
        print(f"\n[COLS] Enabled Columns ({len(enabled_cols)}):")
        for col in enabled_cols[:10]:  # Show first 10
            print(f"   - {col['name']} ({col['data_type']})")
        if len(enabled_cols) > 10:
            print(f"   ... and {len(enabled_cols) - 10} more")

        # Prompts
        class_prompt = config.get_classification_prompt()
        print(f"\n[PROMPT] Classification Prompt Length: {len(class_prompt['user_template'])} chars")

        extract_prompt = config.get_extraction_prompt()
        print(f"[PROMPT] Extraction Prompt Length: {len(extract_prompt['user_template'])} chars")

        # Validation rules
        val_rules = config.get_validation_rules()
        print(f"\n[OK] Validation Rules:")
        print(f"   Provinces: {len(val_rules.get('provinces', []))}")
        print(f"   Regions: {len(val_rules.get('regions', []))}")
        print(f"   Genders: {val_rules.get('genders', [])}")

        print("\n" + "="*60)
        print("[OK] Config loader test completed successfully!")
        print("="*60 + "\n")

    except ConfigLoadError as e:
        print(f"\n[ERROR] Config load error: {e}\n")
    except Exception as e:
        print(f"\n[ERROR] Unexpected error: {e}\n")
        import traceback
        traceback.print_exc()
