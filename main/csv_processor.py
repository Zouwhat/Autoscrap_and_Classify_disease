"""
CSV Processor for Story 1.1 & 1.2: Read prepare_data.csv and ML Classification

This module handles reading prepare_data.csv and processing content
to update is_news field in input_df.csv based on content validation and ML classification.
"""

import logging
import pandas as pd
from pathlib import Path
from typing import Dict, Optional, Tuple, Union, List, Any
import sys
import os
# File locking - fcntl only available on Unix/Linux
try:
    import fcntl
    FCNTL_AVAILABLE = True
except ImportError:
    FCNTL_AVAILABLE = False
import time
import tempfile
import shutil
from contextlib import contextmanager

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class CSVProcessingError(Exception):
    """Custom exception for CSV processing errors"""
    pass


class CSVProcessor:
    """
    Handles CSV file operations for the news classification pipeline.
    
    Reads prepare_data.csv and updates input_df.csv with is_news field
    based on content validation logic and ML classification.
    """
    
    def __init__(self, prepare_data_path: str = "prepare_data.csv", 
                 input_df_path: str = "input_df.csv", ml_classifier=None, enhanced_classifier=None):
        """
        Initialize CSV processor with file paths and optional classifiers.
        
        Args:
            prepare_data_path: Path to prepare_data.csv file
            input_df_path: Path to input_df.csv file
            ml_classifier: Optional ML classifier instance for classification (legacy)
            enhanced_classifier: Optional enhanced ML+LLM classifier instance
        """
        self.prepare_data_path = Path(prepare_data_path)
        self.input_df_path = Path(input_df_path)
        self.ml_classifier = ml_classifier
        self.enhanced_classifier = enhanced_classifier  # New: Enhanced ML+LLM classifier
        self.stats = {
            'total_rows': 0,
            'empty_content': 0,
            'valid_content': 0,
            'classified_content': 0,
            'low_confidence_predictions': 0,
            'llm_fallback_used': 0,  # New: Track LLM fallback usage
            'llm_fallback_success': 0,  # New: Track LLM fallback success
            'errors': 0
        }
    
    def read_prepare_data(self) -> pd.DataFrame:
        """
        Read prepare_data.csv file with proper error handling.
        
        Returns:
            DataFrame with prepare_data content
            
        Raises:
            CSVProcessingError: If file cannot be read or parsed
        """
        try:
            # Validate file exists and is readable
            if not self.prepare_data_path.exists():
                raise CSVProcessingError(f"File not found: {self.prepare_data_path}")
            
            if not self.prepare_data_path.is_file():
                raise CSVProcessingError(f"Path is not a file: {self.prepare_data_path}")
            
            logger.info(f"Reading prepare_data.csv from: {self.prepare_data_path}")
            
            # Read CSV with proper encoding handling
            try:
                df = pd.read_csv(self.prepare_data_path, encoding='utf-8')
            except UnicodeDecodeError:
                logger.warning("UTF-8 decoding failed, trying with latin-1 encoding")
                df = pd.read_csv(self.prepare_data_path, encoding='latin-1')
            
            # Validate required columns according to data contract
            required_columns = ['url', 'content', 'scrape_status']
            missing_columns = [col for col in required_columns if col not in df.columns]
            
            if missing_columns:
                raise CSVProcessingError(f"Missing required columns: {missing_columns}")
            
            self.stats['total_rows'] = len(df)
            logger.info(f"Successfully read {len(df)} rows from prepare_data.csv")
            
            return df
            
        except pd.errors.EmptyDataError:
            raise CSVProcessingError("CSV file is empty")
        except pd.errors.ParserError as e:
            raise CSVProcessingError(f"CSV parsing error: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error reading prepare_data.csv: {str(e)}")
            raise CSVProcessingError(f"Failed to read prepare_data.csv: {str(e)}")
    
    def read_input_df(self) -> pd.DataFrame:
        """
        Read or create input_df.csv file.
        
        Returns:
            DataFrame with input_df content
        """
        try:
            if self.input_df_path.exists():
                logger.info(f"Reading existing input_df.csv from: {self.input_df_path}")
                df = pd.read_csv(self.input_df_path, encoding='utf-8')
                
                # Validate required columns according to data contract
                required_columns = ['url']
                missing_columns = [col for col in required_columns if col not in df.columns]
                
                if missing_columns:
                    raise CSVProcessingError(f"Missing required columns in input_df.csv: {missing_columns}")
                
                # Ensure optional columns exist
                if 'context' not in df.columns:
                    df['context'] = pd.NA
                if 'is_news' not in df.columns:
                    df['is_news'] = pd.NA
                    
                return df
            else:
                logger.info("input_df.csv not found, will be created during processing")
                # Return empty DataFrame with correct schema
                return pd.DataFrame(columns=['url', 'context', 'is_news'])
                
        except Exception as e:
            logger.error(f"Error reading input_df.csv: {str(e)}")
            # Return empty DataFrame as fallback
            return pd.DataFrame(columns=['url', 'context', 'is_news'])
    
    def validate_content(self, content: str) -> bool:
        """
        Validate if content field contains meaningful data.
        
        Args:
            content: Content string to validate
            
        Returns:
            True if content is valid, False if empty/null
        """
        if pd.isna(content):
            return False
        
        if not isinstance(content, str):
            content = str(content)
        
        # Check if content is empty or just whitespace
        content_stripped = content.strip()
        
        if not content_stripped:
            return False
        
        # Additional validation - content should be meaningful
        if len(content_stripped) < 10:  # Arbitrary minimum length
            return False
        
        return True
    
    def process_content_validation(self, prepare_df: pd.DataFrame, 
                                 input_df: pd.DataFrame) -> pd.DataFrame:
        """
        Process content validation and ML classification to update is_news field.
        
        Args:
            prepare_df: DataFrame from prepare_data.csv
            input_df: DataFrame from input_df.csv
            
        Returns:
            Updated input_df DataFrame with classification results
        """
        logger.info("Starting content validation and classification process")
        
        # Create URL to content mapping from prepare_df
        url_content_map = {}
        for _, row in prepare_df.iterrows():
            url = row['url']
            content = row['content']
            scrape_status = row.get('scrape_status', '')
            
            # Only process successfully scraped content
            if scrape_status == 'ok':
                url_content_map[url] = content
        
        # Create result DataFrame based on prepare_data URLs
        result_rows = []
        
        for url, content in url_content_map.items():
            # Check if URL already exists in input_df
            existing_row = input_df[input_df['url'] == url]
            
            if not existing_row.empty:
                # Update existing row
                row_data = existing_row.iloc[0].to_dict()
            else:
                # Create new row
                row_data = {'url': url, 'context': pd.NA, 'is_news': pd.NA}
            
            # Validate content
            if self.validate_content(content):
                self.stats['valid_content'] += 1
                
                # Perform classification using enhanced classifier (preferred) or legacy ML classifier
                if self.enhanced_classifier and hasattr(self.enhanced_classifier, 'classify'):
                    try:
                        # Use enhanced ML+LLM classifier
                        enhanced_result = self.enhanced_classifier.classify(content)
                        row_data['is_news'] = enhanced_result.prediction
                        
                        # Track enhanced statistics
                        self.stats['classified_content'] += 1
                        
                        if enhanced_result.fallback_triggered:
                            self.stats['llm_fallback_used'] += 1
                            if enhanced_result.method_used == 'llm_fallback' and not enhanced_result.error_details:
                                self.stats['llm_fallback_success'] += 1
                        
                        if enhanced_result.ml_confidence and enhanced_result.ml_confidence < 0.6:
                            self.stats['low_confidence_predictions'] += 1
                        
                        logger.debug(f"Enhanced classification for URL {url[:50]}... -> {enhanced_result.prediction} "
                                   f"(method: {enhanced_result.method_used}, confidence: {enhanced_result.confidence:.3f})")
                        
                    except Exception as e:
                        logger.warning(f"Enhanced classification failed for URL {url[:50]}...: {str(e)}")
                        row_data['is_news'] = pd.NA
                        self.stats['errors'] += 1
                        
                elif self.ml_classifier and hasattr(self.ml_classifier, 'classify'):
                    try:
                        # Fallback to legacy ML classifier
                        classification_result = self.ml_classifier.classify(content)
                        row_data['is_news'] = classification_result['prediction']
                        
                        # Track statistics
                        self.stats['classified_content'] += 1
                        if classification_result.get('needs_llm_fallback', False):
                            self.stats['low_confidence_predictions'] += 1
                        
                        logger.debug(f"ML classification for URL {url[:50]}... -> {classification_result['prediction']} "
                                   f"(confidence: {classification_result['confidence']:.3f})")
                        
                    except Exception as e:
                        logger.warning(f"ML classification failed for URL {url[:50]}...: {str(e)}")
                        row_data['is_news'] = pd.NA
                        self.stats['errors'] += 1
                else:
                    # No classifier available - prepare for classification but don't set is_news
                    logger.debug(f"Valid content found for URL: {url[:50]}... (no classifier)")
                    
            else:
                # Empty content -> set is_news = NA
                row_data['is_news'] = pd.NA
                self.stats['empty_content'] += 1
                logger.debug(f"Empty content detected for URL: {url[:50]}...")
            
            result_rows.append(row_data)
        
        result_df = pd.DataFrame(result_rows)
        
        # Enhanced logging with LLM fallback statistics
        log_msg = (f"Processing completed: {self.stats['valid_content']} valid, "
                  f"{self.stats['empty_content']} empty, "
                  f"{self.stats['classified_content']} classified, "
                  f"{self.stats['low_confidence_predictions']} low confidence")
        
        if self.enhanced_classifier:
            log_msg += (f", LLM fallback: {self.stats['llm_fallback_used']} used, "
                       f"{self.stats['llm_fallback_success']} successful")
        
        logger.info(log_msg)
        
        return result_df
    
    def save_input_df(self, df: pd.DataFrame) -> None:
        """
        Save updated input_df.csv file.
        
        Args:
            df: DataFrame to save
        """
        try:
            # Ensure directory exists
            self.input_df_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Save with UTF-8 encoding
            df.to_csv(self.input_df_path, index=False, encoding='utf-8')
            logger.info(f"Successfully saved {len(df)} rows to {self.input_df_path}")
            
        except Exception as e:
            logger.error(f"Failed to save input_df.csv: {str(e)}")
            raise CSVProcessingError(f"Failed to save input_df.csv: {str(e)}")
    
    def process_from_input_df(self) -> Dict[str, int]:
        """
        Story 1.4: Process classification directly from input_df.csv using enhanced classifier.
        This method reads input_df.csv and classifies content that's already been scraped.
        
        Returns:
            Dictionary with processing statistics
        """
        try:
            logger.info("Starting input_df.csv classification workflow (Story 1.4)")
            
            # Step 1: Read input_df.csv
            input_df = self.read_input_df()
            
            if len(input_df) == 0:
                logger.warning("input_df.csv is empty, no content to classify")
                return self.stats
            
            # Step 2: Load content from prepare_data.csv for classification
            # We need content to classify, so we'll map URLs to content
            content_map = {}
            if self.prepare_data_path.exists():
                try:
                    prepare_df = self.read_prepare_data()
                    for _, row in prepare_df.iterrows():
                        if row.get('scrape_status') == 'ok':
                            content_map[row['url']] = row['content']
                    logger.info(f"Loaded content for {len(content_map)} URLs from prepare_data.csv")
                except Exception as e:
                    logger.warning(f"Could not load prepare_data.csv: {e}")
            
            # Step 3: Process classification using enhanced classifier
            result_rows = []
            
            for _, row in input_df.iterrows():
                url = row['url']
                row_data = row.to_dict()
                
                # Get content for this URL
                content = content_map.get(url)
                
                if content and self.validate_content(content):
                    self.stats['valid_content'] += 1
                    
                    # Skip if already classified with valid value
                    current_is_news = row.get('is_news')
                    if pd.notna(current_is_news) and current_is_news in [0, 1]:
                        logger.debug(f"Skipping already classified URL: {url[:50]}...")
                        result_rows.append(row_data)
                        continue
                    
                    # Perform classification using enhanced classifier
                    if self.enhanced_classifier and hasattr(self.enhanced_classifier, 'classify'):
                        try:
                            enhanced_result = self.enhanced_classifier.classify(content)
                            row_data['is_news'] = enhanced_result.prediction
                            
                            # Track enhanced statistics
                            self.stats['classified_content'] += 1
                            
                            if enhanced_result.fallback_triggered:
                                self.stats['llm_fallback_used'] += 1
                                if enhanced_result.method_used == 'llm_fallback' and not enhanced_result.error_details:
                                    self.stats['llm_fallback_success'] += 1
                            
                            if enhanced_result.ml_confidence and enhanced_result.ml_confidence < 0.6:
                                self.stats['low_confidence_predictions'] += 1
                            
                            logger.debug(f"Enhanced classification for URL {url[:50]}... -> {enhanced_result.prediction} "
                                       f"(method: {enhanced_result.method_used}, confidence: {enhanced_result.confidence:.3f})")
                            
                        except Exception as e:
                            logger.warning(f"Enhanced classification failed for URL {url[:50]}...: {str(e)}")
                            row_data['is_news'] = pd.NA
                            self.stats['errors'] += 1
                            
                    elif self.ml_classifier and hasattr(self.ml_classifier, 'classify'):
                        try:
                            # Fallback to legacy ML classifier
                            classification_result = self.ml_classifier.classify(content)
                            row_data['is_news'] = classification_result['prediction']
                            
                            self.stats['classified_content'] += 1
                            if classification_result.get('needs_llm_fallback', False):
                                self.stats['low_confidence_predictions'] += 1
                            
                            logger.debug(f"ML classification for URL {url[:50]}... -> {classification_result['prediction']} "
                                       f"(confidence: {classification_result['confidence']:.3f})")
                            
                        except Exception as e:
                            logger.warning(f"ML classification failed for URL {url[:50]}...: {str(e)}")
                            row_data['is_news'] = pd.NA
                            self.stats['errors'] += 1
                    else:
                        logger.debug(f"No classifier available for URL: {url[:50]}...")
                        row_data['is_news'] = pd.NA
                else:
                    # No content available or invalid content
                    row_data['is_news'] = pd.NA
                    self.stats['empty_content'] += 1
                    logger.debug(f"No valid content for classification: {url[:50]}...")
                
                result_rows.append(row_data)
            
            # Step 4: Create result DataFrame and save
            result_df = pd.DataFrame(result_rows)
            self.save_input_df(result_df)
            
            # Update total rows processed
            self.stats['total_rows'] = len(input_df)
            
            # Enhanced logging with LLM fallback statistics
            log_msg = (f"Input_df processing completed: {self.stats['valid_content']} valid, "
                      f"{self.stats['empty_content']} empty, "
                      f"{self.stats['classified_content']} classified, "
                      f"{self.stats['low_confidence_predictions']} low confidence")
            
            if self.enhanced_classifier:
                log_msg += (f", LLM fallback: {self.stats['llm_fallback_used']} used, "
                           f"{self.stats['llm_fallback_success']} successful")
            
            logger.info(log_msg)
            logger.info(f"Processing statistics: {self.stats}")
            
            return self.stats
            
        except CSVProcessingError:
            self.stats['errors'] += 1
            raise
        except Exception as e:
            self.stats['errors'] += 1
            logger.error(f"Unexpected error in input_df processing: {str(e)}")
            raise CSVProcessingError(f"Input_df processing failed: {str(e)}")

    def process(self) -> Dict[str, int]:
        """
        Main processing function that orchestrates the entire workflow.
        
        Returns:
            Dictionary with processing statistics
        """
        try:
            logger.info("Starting CSV processing workflow")
            
            # Step 1: Read prepare_data.csv
            prepare_df = self.read_prepare_data()
            
            # Step 2: Read or create input_df.csv
            input_df = self.read_input_df()
            
            # Step 3: Process content validation
            updated_input_df = self.process_content_validation(prepare_df, input_df)
            
            # Step 4: Save updated input_df.csv
            self.save_input_df(updated_input_df)
            
            logger.info("CSV processing completed successfully")
            logger.info(f"Processing statistics: {self.stats}")
            
            return self.stats
            
        except CSVProcessingError:
            self.stats['errors'] += 1
            raise
        except Exception as e:
            self.stats['errors'] += 1
            logger.error(f"Unexpected error in processing: {str(e)}")
            raise CSVProcessingError(f"Processing failed: {str(e)}")


def main():
    """Main function for command line usage"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Process prepare_data.csv for content validation and classification')
    parser.add_argument('--prepare-data', default='prepare_data.csv', 
                       help='Path to prepare_data.csv file')
    parser.add_argument('--input-df', default='input_df.csv',
                       help='Path to input_df.csv file')
    parser.add_argument('--model-path', type=str,
                       help='Path to trained ML model for classification')
    parser.add_argument('--train-model', action='store_true',
                       help='Train new ML model using prepare_data.csv')
    parser.add_argument('--model-type', choices=['nb', 'lr'], default='nb',
                       help='Model type for training: nb (Naive Bayes) or lr (Logistic Regression)')
    parser.add_argument('--use-enhanced', action='store_true',
                       help='Use enhanced ML+LLM classifier with fallback logic')
    parser.add_argument('--disable-llm', action='store_true',
                       help='Disable LLM fallback (ML only mode for enhanced classifier)')
    parser.add_argument('--input-df-mode', action='store_true',
                       help='Process classification directly from input_df.csv (Story 1.4)')
    parser.add_argument('--batch-size', type=int, default=50,
                       help='Batch size for processing large datasets (Story 1.4)')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Enable verbose logging')
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    try:
        # Initialize ML classifier if requested
        ml_classifier = None
        if args.model_path or args.train_model:
            try:
                # Import ML classifier (avoid import if not needed)
                from ml_classifier import MLNewsClassifier
                
                ml_classifier = MLNewsClassifier(model_type=args.model_type)
                
                if args.train_model:
                    # Train new model
                    logger.info("Training new ML model...")
                    prepare_df = pd.read_csv(args.prepare_data)
                    texts, labels = ml_classifier.prepare_training_data(prepare_df)
                    metrics = ml_classifier.train(texts, labels)
                    
                    print(f"[TRAIN] Model training completed!")
                    print(f"   Accuracy: {metrics['accuracy']:.3f}")
                    print(f"   Cross-validation: {metrics['cv_accuracy_mean']:.3f} ± {metrics['cv_accuracy_std']:.3f}")
                    
                    if metrics['accuracy'] >= 0.70:
                        print("   [OK] Accuracy requirement (>=70%) met!")
                    else:
                        print("   [FAIL] Accuracy requirement (>=70%) not met!")
                    
                    # Auto-save trained model
                    model_path = ml_classifier.save_model()
                    print(f"   [SAVE] Model saved to: {model_path}")
                    
                elif args.model_path:
                    # Load existing model
                    logger.info(f"Loading ML model from: {args.model_path}")
                    ml_classifier.load_model(args.model_path)
                    print(f"[OK] ML model loaded successfully!")
                    
            except ImportError as e:
                logger.error(f"Failed to import ML classifier: {e}")
                print("[ERROR] ML classifier not available. Install required dependencies.")
                ml_classifier = None
            except Exception as e:
                logger.error(f"ML classifier initialization failed: {e}")
                print(f"[ERROR] ML classifier error: {e}")
                ml_classifier = None
        
        # Initialize enhanced classifier if requested
        enhanced_classifier = None
        if args.use_enhanced:
            try:
                # Import enhanced classifier (avoid import if not needed)
                from llm_classifier import EnhancedNewsClassifier
                
                logger.info("Initializing enhanced ML+LLM classifier...")
                enhanced_classifier = EnhancedNewsClassifier(
                    ml_classifier=ml_classifier,
                    use_llm_fallback=not args.disable_llm
                )
                
                print(f"[OK] Enhanced classifier initialized!")
                print(f"   ML classifier: {'Available' if ml_classifier else 'Not available'}")
                print(f"   LLM fallback: {'Enabled' if not args.disable_llm else 'Disabled'}")
                
                # Check health status
                health = enhanced_classifier.get_health_status()
                print(f"   System health: ML={health['ml_classifier_healthy']}, "
                      f"LLM={'Healthy' if health.get('llm_providers_healthy') else 'Unhealthy'}")
                
            except ImportError as e:
                logger.error(f"Failed to import enhanced classifier: {e}")
                print("[ERROR] Enhanced classifier not available. Install required dependencies.")
                enhanced_classifier = None
            except Exception as e:
                logger.error(f"Enhanced classifier initialization failed: {e}")
                print(f"[ERROR] Enhanced classifier error: {e}")
                enhanced_classifier = None
        
        # Initialize processor with classifiers (enhanced takes precedence)
        processor = CSVProcessor(args.prepare_data, args.input_df, ml_classifier, enhanced_classifier)
        
        # Choose processing mode based on arguments
        if args.input_df_mode:
            print(f"[RUN] Running Story 1.4 mode: Processing classification from input_df.csv")
            stats = processor.process_from_input_df()
        else:
            print(f"[RUN] Running standard mode: Processing from prepare_data.csv")
            stats = processor.process()
        
        print(f"[OK] Processing completed successfully!")
        print(f"[STATS] Statistics:")
        for key, value in stats.items():
            print(f"   {key}: {value}")
        
        return 0
        
    except CSVProcessingError as e:
        print(f"[ERROR] Processing failed: {e}")
        return 1
    except Exception as e:
        print(f"[FATAL] Unexpected error: {e}")
        return 2


class CSVUpdater:
    """
    Enhanced CSV processor for Story 1.4: Update input_df.csv with classification results.
    
    Handles updating the is_news field in input_df.csv after ML baseline and LLM fallback 
    classification is complete, with atomic operations, file locking, and batch processing.
    """
    
    def __init__(self, input_df_path: str = "input_df.csv", enhanced_classifier=None, batch_size: int = 50, prepare_data_path: str = "prepare_data.csv"):
        """
        Initialize CSV updater with enhanced capabilities.
        
        Args:
            input_df_path: Path to input_df.csv file
            enhanced_classifier: Enhanced ML+LLM classifier instance from Story 1.3
            batch_size: Number of rows to process in each batch for memory efficiency
            prepare_data_path: Path to prepare_data.csv file for content retrieval
        """
        self.input_df_path = Path(input_df_path)
        self.prepare_data_path = Path(prepare_data_path)
        self.enhanced_classifier = enhanced_classifier
        self.batch_size = batch_size
        self.stats = {
            'total_processed': 0,
            'successfully_updated': 0,
            'classification_errors': 0,
            'skipped_items': 0,
            'batches_processed': 0,
            'file_lock_retries': 0,
            'llm_fallback_used': 0,
            'llm_fallback_success': 0
        }
    
    @contextmanager
    def _file_lock(self, file_path: Path, timeout: int = 30):
        """
        Context manager for file locking to prevent concurrent access.
        
        Args:
            file_path: Path to file to lock
            timeout: Maximum seconds to wait for lock
        """
        lock_file = file_path.with_suffix(file_path.suffix + '.lock')
        lock_acquired = False
        start_time = time.time()
        
        while not lock_acquired and (time.time() - start_time) < timeout:
            try:
                # Create lock file atomically
                fd = os.open(str(lock_file), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                lock_acquired = True
                logger.debug(f"Acquired file lock: {lock_file}")
            except FileExistsError:
                # Lock file exists, wait and retry
                time.sleep(0.1)
                self.stats['file_lock_retries'] += 1
                
        if not lock_acquired:
            raise CSVProcessingError(f"Could not acquire file lock after {timeout} seconds: {file_path}")
        
        try:
            yield fd
        finally:
            try:
                os.close(fd)
                lock_file.unlink(missing_ok=True)
                logger.debug(f"Released file lock: {lock_file}")
            except Exception as e:
                logger.warning(f"Error releasing file lock {lock_file}: {e}")
    
    def _load_prepare_data_content_map(self) -> Dict[str, str]:
        """
        Load prepare_data.csv and create a URL -> content mapping for classification.
        
        Returns:
            Dictionary mapping URL to content for classification
        """
        content_map = {}
        
        if not self.prepare_data_path.exists():
            logger.warning(f"prepare_data.csv not found at {self.prepare_data_path}. Will use input_df context field if available.")
            return content_map
            
        try:
            logger.info(f"Loading content from prepare_data.csv: {self.prepare_data_path}")
            
            # Try UTF-8 first, fall back to latin-1
            try:
                prepare_df = pd.read_csv(self.prepare_data_path, encoding='utf-8')
            except UnicodeDecodeError:
                logger.warning("UTF-8 decoding failed for prepare_data.csv, trying latin-1")
                prepare_df = pd.read_csv(self.prepare_data_path, encoding='latin-1')
            
            # Validate required columns
            required_columns = ['url', 'content']
            missing_columns = [col for col in required_columns if col not in prepare_df.columns]
            if missing_columns:
                logger.error(f"Missing required columns in prepare_data.csv: {missing_columns}")
                return content_map
            
            # Create URL -> content mapping (only for rows with content)
            for _, row in prepare_df.iterrows():
                url = row['url']
                content = row['content']
                
                # Only add if content is not null/empty and scrape_status is successful
                if pd.notna(content) and str(content).strip():
                    # Check scrape_status if it exists
                    scrape_status = row.get('scrape_status', 'ok')
                    if scrape_status in ['ok', 'success']:
                        content_map[url] = str(content).strip()
                    else:
                        logger.debug(f"Skipping URL with failed scrape_status: {url[:50]}... (status: {scrape_status})")
                else:
                    logger.debug(f"Skipping URL with empty content: {url[:50]}...")
            
            logger.info(f"Loaded content for {len(content_map)} URLs from prepare_data.csv")
            
        except Exception as e:
            logger.error(f"Error loading prepare_data.csv: {str(e)}")
            
        return content_map
    
    def _get_content_for_classification(self, url: str, row_context: str, content_map: Dict[str, str]) -> Optional[str]:
        """
        Get content for classification from available sources.
        
        Priority:
        1. Content from prepare_data.csv (if available)
        2. Context field from input_df (if available and non-empty)
        3. None (will be marked as NA)
        
        Args:
            url: URL to get content for
            row_context: Context field from input_df row
            content_map: URL -> content mapping from prepare_data.csv
            
        Returns:
            Content string for classification, or None if no content available
        """
        # Priority 1: Content from prepare_data.csv
        if url in content_map:
            content = content_map[url]
            logger.debug(f"Using content from prepare_data.csv for URL: {url[:50]}...")
            return content
        
        # Priority 2: Context field from input_df
        if pd.notna(row_context) and str(row_context).strip():
            content = str(row_context).strip()
            logger.debug(f"Using context field from input_df for URL: {url[:50]}...")
            return content
            
        # No content available
        logger.debug(f"No content available for classification: {url[:50]}...")
        return None
    
    def read_input_df_safe(self) -> pd.DataFrame:
        """
        Safely read input_df.csv with file locking and validation.
        
        Returns:
            DataFrame with input_df content or empty DataFrame with correct schema
            
        Raises:
            CSVProcessingError: If file cannot be read or has invalid structure
        """
        try:
            if not self.input_df_path.exists():
                logger.info("input_df.csv not found, creating empty DataFrame")
                return pd.DataFrame(columns=['url', 'context', 'is_news'])
            
            with self._file_lock(self.input_df_path):
                logger.info(f"Reading input_df.csv from: {self.input_df_path}")
                
                try:
                    df = pd.read_csv(self.input_df_path, encoding='utf-8')
                except UnicodeDecodeError:
                    logger.warning("UTF-8 decoding failed, trying with latin-1 encoding")
                    df = pd.read_csv(self.input_df_path, encoding='latin-1')
                
                # Validate required columns according to data contract
                required_columns = ['url']
                missing_columns = [col for col in required_columns if col not in df.columns]
                
                if missing_columns:
                    raise CSVProcessingError(f"Missing required columns in input_df.csv: {missing_columns}")
                
                # Ensure optional columns exist with proper types
                if 'context' not in df.columns:
                    df['context'] = pd.NA
                if 'is_news' not in df.columns:
                    df['is_news'] = pd.NA
                    
                # Validate is_news column values
                invalid_values = df[~df['is_news'].isin([0, 1, pd.NA]) & pd.notna(df['is_news'])]
                if len(invalid_values) > 0:
                    logger.warning(f"Found {len(invalid_values)} rows with invalid is_news values")
                
                logger.info(f"Successfully read {len(df)} rows from input_df.csv")
                return df
                
        except Exception as e:
            logger.error(f"Error reading input_df.csv: {str(e)}")
            raise CSVProcessingError(f"Failed to read input_df.csv: {str(e)}")
    
    def update_classification_results(self, df: pd.DataFrame, batch_size: Optional[int] = None) -> pd.DataFrame:
        """
        Update is_news field with classification results using enhanced classifier.
        
        Args:
            df: Input DataFrame to update
            batch_size: Override default batch size for processing
            
        Returns:
            Updated DataFrame with classification results
        """
        if not self.enhanced_classifier:
            logger.warning("No enhanced classifier provided, skipping classification updates")
            return df
            
        batch_size = batch_size or self.batch_size
        total_rows = len(df)
        result_df = df.copy()
        
        logger.info(f"Starting batch classification update for {total_rows} rows (batch_size={batch_size})")
        
        # Load content mapping from prepare_data.csv
        content_map = self._load_prepare_data_content_map()
        
        for batch_start in range(0, total_rows, batch_size):
            batch_end = min(batch_start + batch_size, total_rows)
            batch_df = df.iloc[batch_start:batch_end].copy()
            
            logger.info(f"Processing batch {batch_start//batch_size + 1}: rows {batch_start+1}-{batch_end}")
            
            for idx in range(len(batch_df)):
                global_idx = batch_start + idx
                row = batch_df.iloc[idx]
                url = row['url']
                
                # Skip if already classified (has valid is_news value)
                current_is_news = row.get('is_news')
                if pd.notna(current_is_news) and current_is_news in [0, 1]:
                    logger.debug(f"Skipping already classified URL: {url[:50]}...")
                    self.stats['skipped_items'] += 1
                    continue
                
                try:
                    # Get content for classification (from prepare_data.csv or input_df.context)
                    row_context = row.get('context', '')
                    content = self._get_content_for_classification(url, row_context, content_map)
                    
                    if content is None:
                        # No content available - mark as NA
                        logger.debug(f"No content available for classification: {url[:50]}...")
                        result_df.loc[result_df.index[global_idx], 'is_news'] = pd.NA
                        self.stats['skipped_items'] += 1
                        continue
                    
                    # Perform actual classification using enhanced classifier
                    logger.debug(f"Classifying content for URL: {url[:50]}... (content length: {len(content)})")
                    classification_result = self.enhanced_classifier.classify(content)
                    
                    # Update classification result (0 or 1)
                    is_news_result = 1 if classification_result.prediction else 0
                    result_df.loc[result_df.index[global_idx], 'is_news'] = is_news_result
                    
                    # Update statistics
                    self.stats['successfully_updated'] += 1
                    if hasattr(classification_result, 'method_used'):
                        if 'llm' in classification_result.method_used.lower():
                            self.stats['llm_fallback_used'] += 1
                            if classification_result.prediction is not None:
                                self.stats['llm_fallback_success'] += 1
                    
                    logger.debug(f"Classification result for {url[:50]}...: {is_news_result} "
                               f"(method: {getattr(classification_result, 'method_used', 'N/A')}, "
                               f"confidence: {getattr(classification_result, 'confidence', 'N/A'):.3f})")
                    
                except Exception as e:
                    logger.error(f"Classification failed for URL {url[:50]}...: {str(e)}")
                    result_df.loc[result_df.index[global_idx], 'is_news'] = pd.NA
                    self.stats['classification_errors'] += 1
            
            self.stats['batches_processed'] += 1
            self.stats['total_processed'] += len(batch_df)
            
            # Progress reporting
            progress = (batch_end / total_rows) * 100
            logger.info(f"Batch {self.stats['batches_processed']} completed. Progress: {progress:.1f}%")
        
        logger.info(f"Classification update completed. Processed: {self.stats['total_processed']}, "
                   f"Errors: {self.stats['classification_errors']}, Skipped: {self.stats['skipped_items']}")
        
        return result_df
    
    def save_input_df_atomic(self, df: pd.DataFrame) -> None:
        """
        Atomically save updated input_df.csv with proper error handling.
        
        Args:
            df: DataFrame to save
            
        Raises:
            CSVProcessingError: If save operation fails
        """
        try:
            # Ensure directory exists
            self.input_df_path.parent.mkdir(parents=True, exist_ok=True)
            
            with self._file_lock(self.input_df_path):
                # Create temporary file for atomic write
                with tempfile.NamedTemporaryFile(
                    mode='w', 
                    suffix='.tmp',
                    dir=self.input_df_path.parent,
                    delete=False,
                    encoding='utf-8'
                ) as temp_file:
                    temp_path = Path(temp_file.name)
                
                try:
                    # Write to temporary file
                    df.to_csv(temp_path, index=False, encoding='utf-8')
                    
                    # Verify written file
                    verification_df = pd.read_csv(temp_path, encoding='utf-8')
                    if len(verification_df) != len(df):
                        raise CSVProcessingError("Written file verification failed: row count mismatch")
                    
                    # Atomic move to final location
                    if self.input_df_path.exists():
                        backup_path = self.input_df_path.with_suffix('.csv.bak')
                        shutil.copy2(self.input_df_path, backup_path)
                        logger.debug(f"Created backup: {backup_path}")
                    
                    shutil.move(str(temp_path), str(self.input_df_path))
                    self.stats['successfully_updated'] = len(df)
                    
                    logger.info(f"Successfully saved {len(df)} rows to {self.input_df_path}")
                    
                except Exception as e:
                    # Cleanup temporary file on error
                    temp_path.unlink(missing_ok=True)
                    raise e
                    
        except Exception as e:
            logger.error(f"Failed to save input_df.csv: {str(e)}")
            raise CSVProcessingError(f"Failed to save input_df.csv: {str(e)}")
    
    def update_from_classification_results(self, classification_results: List[Dict[str, Any]]) -> Dict[str, int]:
        """
        Update input_df.csv from a list of classification results.
        
        Args:
            classification_results: List of dicts with 'url', 'is_news', 'confidence', etc.
            
        Returns:
            Dictionary with update statistics
        """
        try:
            logger.info(f"Starting CSV update process with {len(classification_results)} classification results")
            
            # Read current input_df
            df = self.read_input_df_safe()
            
            # Create URL to classification mapping
            url_classification_map = {result['url']: result for result in classification_results}
            
            # Update DataFrame
            updated_count = 0
            for idx, row in df.iterrows():
                url = row['url']
                if url in url_classification_map:
                    classification = url_classification_map[url]
                    df.loc[idx, 'is_news'] = classification.get('is_news', pd.NA)
                    updated_count += 1
                    
                    # Track enhanced classifier statistics
                    if 'fallback_triggered' in classification and classification['fallback_triggered']:
                        self.stats['llm_fallback_used'] += 1
                        if classification.get('method_used') == 'llm_fallback' and not classification.get('error_details'):
                            self.stats['llm_fallback_success'] += 1
            
            # Save updated DataFrame atomically
            self.save_input_df_atomic(df)
            
            self.stats['successfully_updated'] = updated_count
            logger.info(f"CSV update completed: {updated_count} records updated")
            
            return self.stats
            
        except Exception as e:
            logger.error(f"CSV update process failed: {str(e)}")
            self.stats['classification_errors'] += 1
            raise CSVProcessingError(f"CSV update process failed: {str(e)}")
    
    def process_large_dataset_batch(self, batch_size: Optional[int] = None, memory_limit_mb: int = 512) -> Dict[str, int]:
        """
        Process large datasets with memory-efficient batch processing.
        
        Args:
            batch_size: Override default batch size
            memory_limit_mb: Memory limit in MB for processing
            
        Returns:
            Dictionary with processing statistics
        """
        try:
            import psutil
            import gc
            
            batch_size = batch_size or self.batch_size
            logger.info(f"Starting large dataset batch processing (batch_size={batch_size}, memory_limit={memory_limit_mb}MB)")
            
            # Read input_df in chunks to determine total size
            total_rows = 0
            if self.input_df_path.exists():
                with open(self.input_df_path, 'r', encoding='utf-8') as f:
                    total_rows = sum(1 for _ in f) - 1  # Exclude header
                    
            logger.info(f"Processing {total_rows} total rows")
            
            if total_rows == 0:
                logger.warning("No data to process")
                return self.stats
            
            # Adjust batch size for very large datasets
            if total_rows > 1000:
                batch_size = min(batch_size, 100)  # Smaller batches for large datasets
                logger.info(f"Large dataset detected, reducing batch size to {batch_size}")
            
            processed_rows = 0
            
            # Process in chunks using pandas chunksize
            for chunk_df in pd.read_csv(self.input_df_path, chunksize=batch_size, encoding='utf-8'):
                # Check memory usage
                memory_usage_mb = psutil.Process().memory_info().rss / 1024 / 1024
                if memory_usage_mb > memory_limit_mb:
                    logger.warning(f"Memory usage ({memory_usage_mb:.1f}MB) exceeds limit ({memory_limit_mb}MB), forcing garbage collection")
                    gc.collect()
                    
                    # Check again after GC
                    memory_usage_mb = psutil.Process().memory_info().rss / 1024 / 1024
                    if memory_usage_mb > memory_limit_mb * 1.2:  # 20% tolerance
                        raise CSVProcessingError(f"Memory usage ({memory_usage_mb:.1f}MB) still exceeds limit after garbage collection")
                
                # Process this chunk
                logger.info(f"Processing chunk: rows {processed_rows + 1} to {processed_rows + len(chunk_df)}")
                
                # Simulate classification processing for this chunk
                # In real implementation, this would call the enhanced classifier
                for idx, row in chunk_df.iterrows():
                    url = row.get('url', '')
                    current_is_news = row.get('is_news')
                    
                    # Skip if already classified
                    if pd.notna(current_is_news) and current_is_news in [0, 1]:
                        self.stats['skipped_items'] += 1
                        continue
                    
                    # Here we would normally classify content
                    # For now, just mark as processed
                    self.stats['total_processed'] += 1
                
                processed_rows += len(chunk_df)
                self.stats['batches_processed'] += 1
                
                # Progress reporting
                progress = (processed_rows / total_rows) * 100
                logger.info(f"Batch {self.stats['batches_processed']} completed. Progress: {progress:.1f}% "
                           f"(Memory: {memory_usage_mb:.1f}MB)")
                
                # Force garbage collection every 10 batches
                if self.stats['batches_processed'] % 10 == 0:
                    gc.collect()
            
            logger.info(f"Large dataset processing completed. Total batches: {self.stats['batches_processed']}")
            return self.stats
            
        except ImportError:
            logger.warning("psutil not available, falling back to basic batch processing")
            return self.update_classification_results(self.read_input_df_safe(), batch_size)
        except Exception as e:
            logger.error(f"Large dataset batch processing failed: {str(e)}")
            raise CSVProcessingError(f"Large dataset batch processing failed: {str(e)}")
    
    def validate_csv_integrity(self, df: pd.DataFrame) -> bool:
        """
        Validate CSV data integrity before and after operations.
        
        Args:
            df: DataFrame to validate
            
        Returns:
            True if validation passes, False otherwise
        """
        try:
            # Check required columns
            required_columns = ['url']
            if not all(col in df.columns for col in required_columns):
                logger.error("Missing required columns in DataFrame")
                return False
            
            # Check for duplicate URLs
            duplicate_urls = df['url'].duplicated().sum()
            if duplicate_urls > 0:
                logger.warning(f"Found {duplicate_urls} duplicate URLs in DataFrame")
            
            # Check is_news column values
            if 'is_news' in df.columns:
                invalid_values = df[~df['is_news'].isin([0, 1, pd.NA]) & pd.notna(df['is_news'])]
                if len(invalid_values) > 0:
                    logger.error(f"Found {len(invalid_values)} invalid is_news values")
                    return False
            
            # Check for empty URLs
            empty_urls = df['url'].isna().sum() + (df['url'] == '').sum()
            if empty_urls > 0:
                logger.error(f"Found {empty_urls} empty URLs in DataFrame")
                return False
            
            logger.debug(f"CSV integrity validation passed for {len(df)} rows")
            return True
            
        except Exception as e:
            logger.error(f"CSV integrity validation failed: {str(e)}")
            return False
    
    def get_update_statistics(self) -> Dict[str, int]:
        """Get current update statistics."""
        return self.stats.copy()


if __name__ == "__main__":
    sys.exit(main())