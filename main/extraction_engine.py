"""
Extraction Engine for Epic1_3 Pipeline
Config-driven extraction engine with incremental processing support
"""

import pandas as pd
import logging
import json
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
import shutil

from config_loader import ConfigLoader
from llm_client import LLMClient, LLMResponse

logger = logging.getLogger(__name__)


class ExtractionEngine:
    """
    Main extraction engine with incremental processing

    Features:
    - Load and deduplicate data
    - Classify news (relevant/irrelevant)
    - Extract information using LLM
    - Validate extracted data
    - Merge and output results
    """

    def __init__(self, config: ConfigLoader):
        """
        Initialize extraction engine

        Args:
            config: ConfigLoader instance
        """
        self.config = config
        self.llm_client = LLMClient(config.get_llm_config())

        # Paths
        paths = config.get_data_paths()
        self.input_file = Path(paths['input_file'])
        self.base_file = Path(paths['base_file'])
        self.output_filled_file = Path(paths['output_filled_file'])
        self.output_heat_data_file = Path(paths['output_heat_data_file'])

        # Processing config
        self.batch_size = config.get_batch_size()
        self.skip_processed = config.should_skip_processed_records()

        # Stats
        self.stats = {
            'total_input': 0,
            'already_processed': 0,
            'new_records': 0,
            'classified_relevant': 0,
            'classified_irrelevant': 0,
            'extraction_success': 0,
            'extraction_failed': 0,
            'processing_time_ms': 0
        }

        logger.info(f"[OK] Extraction engine initialized")
        logger.info(f"   LLM: {self.llm_client}")
        logger.info(f"   Batch size: {self.batch_size}")
        logger.info(f"   Skip processed: {self.skip_processed}")

    def load_data(self) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        Load input data and base database

        Returns:
            Tuple of (input_df, base_df)
        """
        logger.info(f"[LOAD] Loading data...")

        # Load input file
        if not self.input_file.exists():
            raise FileNotFoundError(f"Input file not found: {self.input_file}")

        input_df = pd.read_csv(self.input_file, encoding='utf-8')
        logger.info(f"   [OK] Input: {len(input_df)} records from {self.input_file.name}")

        # Load base file if exists
        if self.base_file.exists():
            base_df = pd.read_csv(self.base_file, encoding='utf-8')
            logger.info(f"   [OK] Base: {len(base_df)} records from {self.base_file.name}")
        else:
            # Create empty base with same structure
            base_df = pd.DataFrame()
            logger.info(f"   [WARN] Base file not found, will create new: {self.base_file.name}")

        self.stats['total_input'] = len(input_df)

        return input_df, base_df

    def deduplicate(self, input_df: pd.DataFrame, base_df: pd.DataFrame) -> pd.DataFrame:
        """
        Remove duplicates based on URL

        Args:
            input_df: Input dataframe
            base_df: Base database dataframe

        Returns:
            Dataframe with only new records
        """
        if not self.skip_processed or base_df.empty:
            logger.info(f"[SKIP] No deduplication (skip_processed={self.skip_processed})")
            self.stats['new_records'] = len(input_df)
            return input_df

        logger.info(f"[DEDUP] Deduplicating...")

        # Check if URL column exists
        url_col = 'url' if 'url' in input_df.columns else 'ที่มาสื่อออนไลน์'

        if url_col not in input_df.columns:
            logger.warning(f"   [WARN] URL column not found, cannot deduplicate")
            self.stats['new_records'] = len(input_df)
            return input_df

        # Get existing URLs from base
        if url_col in base_df.columns:
            existing_urls = set(base_df[url_col].dropna().unique())
            logger.info(f"   [INFO] Base has {len(existing_urls)} unique URLs")

            # Filter new records
            new_df = input_df[~input_df[url_col].isin(existing_urls)].copy()

            self.stats['already_processed'] = len(input_df) - len(new_df)
            self.stats['new_records'] = len(new_df)

            logger.info(f"   [OK] Found {len(new_df)} new records (skipped {self.stats['already_processed']} existing)")

            return new_df
        else:
            logger.warning(f"   [WARN] URL column not in base, cannot deduplicate")
            self.stats['new_records'] = len(input_df)
            return input_df

    def classify_batch(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Classify records using LLM

        Args:
            df: Dataframe to classify

        Returns:
            Dataframe with 'is_relevant' column added
        """
        logger.info(f"[CLASSIFY] Classifying {len(df)} records...")

        # Get classification prompt
        class_prompt = self.config.get_classification_prompt()
        system_message = class_prompt['system_message']
        user_template = class_prompt['user_template']

        # Classify each record
        results = []
        total = len(df)

        for i, (idx, row) in enumerate(df.iterrows(), 1):
            content = row.get('content', '')

            if pd.isna(content) or len(str(content).strip()) < 10:
                # Skip empty content
                results.append(0)
                logger.debug(f"   Skipped {idx}: empty content")
                continue

            # Format prompt
            user_message = user_template.format(content=content)

            # Call LLM
            prediction, response = self.llm_client.classify(system_message, user_message)

            results.append(prediction)

            if prediction == 1:
                self.stats['classified_relevant'] += 1
                logger.debug(f"   [OK] {idx}: relevant ({response.response_time_ms}ms)")
            else:
                self.stats['classified_irrelevant'] += 1
                logger.debug(f"   [ERROR] {idx}: irrelevant ({response.response_time_ms}ms)")

            # Progress logging every 10 records
            if i % 10 == 0 or i == total:
                logger.info(f"   Progress: {i}/{total} classified ({i*100//total}%)")

        # Add results to dataframe
        df['is_relevant'] = results

        logger.info(f"   [OK] Classification done: {self.stats['classified_relevant']} relevant, "
                   f"{self.stats['classified_irrelevant']} irrelevant")

        return df

    def generate_extraction_prompt(self) -> Tuple[str, str]:
        """
        Generate extraction prompt from enabled columns

        Returns:
            Tuple of (fields_description, example_json)
        """
        enabled_cols = self.config.get_enabled_columns()

        # Build fields description
        fields_list = []
        example_dict = {}

        for col in enabled_cols:
            name = col['name']
            hint = col.get('extraction_hint', '')

            if hint:
                fields_list.append(f"- {hint}")

            # Generate example value based on data type
            data_type = col.get('data_type', 'text')
            if data_type == 'integer':
                example_dict[name] = 45
            elif data_type == 'float':
                example_dict[name] = 37.5
            elif data_type == 'boolean':
                example_dict[name] = 1
            elif data_type == 'date':
                example_dict[name] = "15/03/2024"
            elif data_type == 'time':
                example_dict[name] = "14:30"
            else:
                example_dict[name] = "ตัวอย่าง"

        fields_description = "\n".join(fields_list)
        example_json = json.dumps(example_dict, ensure_ascii=False, indent=2)

        return fields_description, example_json

    def extract_batch(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Extract information from relevant records using LLM

        Args:
            df: Dataframe with 'is_relevant' column

        Returns:
            Dataframe with extracted columns added
        """
        # Filter relevant records
        relevant_df = df[df['is_relevant'] == 1].copy()

        if len(relevant_df) == 0:
            logger.info(f"[SKIP] No relevant records to extract")
            return df

        logger.info(f"[EXTRACT] Extracting information from {len(relevant_df)} relevant records...")

        # Get extraction prompt
        extract_prompt = self.config.get_extraction_prompt()
        system_message = extract_prompt['system_message']
        user_template = extract_prompt['user_template']

        # Generate fields description
        fields_description, example_json = self.generate_extraction_prompt()

        # Get enabled columns
        enabled_cols = self.config.get_enabled_columns()
        column_names = [col['name'] for col in enabled_cols]

        # Extract each record
        for idx, row in relevant_df.iterrows():
            content = row.get('content', '')

            if pd.isna(content):
                logger.warning(f"   [WARN] Skipped {idx}: empty content")
                self.stats['extraction_failed'] += 1
                continue

            # Format prompt
            user_message = user_template.format(
                fields_description=fields_description,
                content=content,
                example_json=example_json
            )

            # Call LLM
            extracted_data, response = self.llm_client.extract_json(system_message, user_message)

            if extracted_data:
                # Add extracted data to dataframe
                for col_name in column_names:
                    value = extracted_data.get(col_name, None)

                    # Convert list/dict to JSON string to avoid pandas error
                    if isinstance(value, (list, dict)):
                        value = json.dumps(value, ensure_ascii=False)

                    df.at[idx, col_name] = value

                self.stats['extraction_success'] += 1
                logger.debug(f"   [OK] {idx}: extracted {len(extracted_data)} fields ({response.response_time_ms}ms)")
            else:
                self.stats['extraction_failed'] += 1
                logger.warning(f"   [ERROR] {idx}: extraction failed - {response.error}")

        logger.info(f"   [OK] Extraction done: {self.stats['extraction_success']} success, "
                   f"{self.stats['extraction_failed']} failed")

        return df

    def validate_and_normalize(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Validate and normalize extracted data

        Args:
            df: Dataframe with extracted data

        Returns:
            Dataframe with validated and normalized data
        """
        logger.info(f"[VALIDATE] Validating and normalizing data...")

        # TODO: Integrate with existing validators
        # For now, just do basic type conversion

        enabled_cols = self.config.get_enabled_columns()

        for col in enabled_cols:
            col_name = col['name']

            if col_name not in df.columns:
                continue

            data_type = col.get('data_type', 'text')

            try:
                if data_type == 'integer':
                    df[col_name] = pd.to_numeric(df[col_name], errors='coerce').astype('Int64')
                elif data_type == 'float':
                    df[col_name] = pd.to_numeric(df[col_name], errors='coerce')
                elif data_type == 'boolean':
                    # Convert to 1/0/NaN
                    df[col_name] = df[col_name].apply(lambda x: 1 if x in [1, '1', True, 'มี'] else (0 if x in [0, '0', False, 'ไม่มี'] else None))
            except Exception as e:
                logger.warning(f"   [WARN] Validation error for {col_name}: {e}")

        logger.info(f"   [OK] Validation complete")

        return df

    def merge_and_output(self, processed_df: pd.DataFrame, base_df: pd.DataFrame):
        """
        Merge processed data with base and output results

        Args:
            processed_df: Newly processed dataframe
            base_df: Existing base dataframe
        """
        logger.info(f"[SAVE] Merging and outputting results...")

        # Add metadata columns
        processed_df['processing_status'] = processed_df['is_relevant'].apply(
            lambda x: 'extracted' if x == 1 else 'irrelevant'
        )
        processed_df['extracted_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # Output 1: prepare_data_filled.csv (all processed records)
        processed_df.to_csv(self.output_filled_file, index=False, encoding='utf-8')
        logger.info(f"   [OK] Saved {len(processed_df)} records to {self.output_filled_file.name}")

        # Output 2: heat_data.csv (only relevant records)
        relevant_df = processed_df[processed_df['is_relevant'] == 1].copy()
        relevant_df.to_csv(self.output_heat_data_file, index=False, encoding='utf-8')
        logger.info(f"   [OK] Saved {len(relevant_df)} relevant records to {self.output_heat_data_file.name}")

        # Output 3: Update base_heat_map.csv
        if self.config.is_base_database_enabled():
            # Backup existing base if needed
            if self.base_file.exists():
                backup_dir = Path(self.config.get_backup_dir())
                backup_dir.mkdir(parents=True, exist_ok=True)

                backup_file = backup_dir / f"base_heat_map_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
                shutil.copy2(self.base_file, backup_file)
                logger.info(f"   [BACKUP] Backup created: {backup_file.name}")

            # Merge with base
            if not base_df.empty:
                merged_df = pd.concat([base_df, processed_df], ignore_index=True)
            else:
                merged_df = processed_df

            # Save updated base
            merged_df.to_csv(self.base_file, index=False, encoding='utf-8')
            logger.info(f"   [OK] Updated base: {len(merged_df)} total records in {self.base_file.name}")

        logger.info(f"[SAVE] All outputs saved successfully")

    def run(self):
        """Run the complete extraction pipeline"""
        start_time = datetime.now()

        logger.info("[START] Starting extraction pipeline...")
        logger.info("="*60)

        try:
            # Step 1: Load data
            input_df, base_df = self.load_data()

            # Step 2: Deduplicate
            new_df = self.deduplicate(input_df, base_df)

            if len(new_df) == 0:
                logger.info("[OK] No new records to process!")
                return

            # Step 3: Classify
            classified_df = self.classify_batch(new_df)

            # Step 4: Extract
            extracted_df = self.extract_batch(classified_df)

            # Step 5: Validate
            validated_df = self.validate_and_normalize(extracted_df)

            # Step 6: Merge and output
            self.merge_and_output(validated_df, base_df)

            # Calculate total time
            end_time = datetime.now()
            total_time = (end_time - start_time).total_seconds()
            self.stats['processing_time_ms'] = int(total_time * 1000)

            # Print summary
            self.print_summary()

            logger.info("="*60)
            logger.info("[OK] Extraction pipeline completed successfully!")

        except Exception as e:
            logger.error(f"[ERROR] Extraction pipeline failed: {e}")
            import traceback
            traceback.print_exc()
            raise

    def print_summary(self):
        """Print processing summary"""
        logger.info("\n" + "="*60)
        logger.info("[SUMMARY] PROCESSING SUMMARY")
        logger.info("="*60)
        logger.info(f"Input:")
        logger.info(f"  Total records: {self.stats['total_input']}")
        logger.info(f"  Already processed: {self.stats['already_processed']}")
        logger.info(f"  New records: {self.stats['new_records']}")
        logger.info(f"\nClassification:")
        logger.info(f"  Relevant: {self.stats['classified_relevant']}")
        logger.info(f"  Irrelevant: {self.stats['classified_irrelevant']}")
        logger.info(f"\nExtraction:")
        logger.info(f"  Success: {self.stats['extraction_success']}")
        logger.info(f"  Failed: {self.stats['extraction_failed']}")
        logger.info(f"\nPerformance:")
        logger.info(f"  Total time: {self.stats['processing_time_ms'] / 1000:.2f}s")
        logger.info("="*60 + "\n")


# Example usage
if __name__ == "__main__":
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    try:
        # Load config
        from config_loader import load_config

        config = load_config("config.json")

        # Create engine
        engine = ExtractionEngine(config)

        # Run pipeline
        engine.run()

    except Exception as e:
        logger.error(f"[ERROR] Pipeline failed: {e}")
        import traceback
        traceback.print_exc()
