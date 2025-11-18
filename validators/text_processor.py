"""
Text Processor for Multi-Type Column Processing

This module implements TextProcessor class for handling free-form text columns
with UTF-8 encoding, normalization, cleaning, and length validation.
"""

import re
import unicodedata
from typing import Any, Optional, Dict, List
from .base_validator import BaseValidator, ValidationResult


class TextProcessor(BaseValidator):
    """
    Processor for text columns with UTF-8 normalization and cleaning
    
    Handles free-form text columns like:
    - โรคประจำตัว(รายละเอียด)
    - ข้อมูลอื่นๆ  
    - หมายเหตุ
    - ที่มาสื่อออนไลน์
    - อำเภอ, ตำบล, etc.
    
    Features:
    - UTF-8 encoding validation and normalization
    - Thai text cleaning and standardization
    - Length validation and truncation
    - HTML/special character cleaning
    - Whitespace normalization
    """
    
    def __init__(self, column_name: str, validation_config: Optional[Dict] = None):
        """
        Initialize text processor
        
        Args:
            column_name: Name of the column being processed
            validation_config: Configuration with text processing settings
        """
        super().__init__()
        self.column_name = column_name
        self.config = validation_config or {}
        
        # Text processing settings
        self.max_length = self.config.get('max_length', 500)
        self.min_length = self.config.get('min_length', 0)
        self.encoding = self.config.get('encoding', 'utf-8')
        self.normalize_unicode = self.config.get('normalize_unicode', True)
        self.remove_html = self.config.get('remove_html', True)
        self.remove_urls = self.config.get('remove_urls', True)
        self.normalize_whitespace = self.config.get('normalize_whitespace', True)
        self.preserve_thai_chars = self.config.get('preserve_thai_chars', True)
        self.preserve_english_chars = self.config.get('preserve_english_chars', True)
        self.preserve_digits = self.config.get('preserve_digits', True)
        self.allow_special_chars = self.config.get('allow_special_chars', True)
        self.truncate_on_length_exceed = self.config.get('truncate_on_length_exceed', True)
        
        # Custom cleaning patterns
        self.custom_clean_patterns = self.config.get('custom_clean_patterns', {})
        
        # Setup column-specific cleaning rules
        self._setup_column_specific_rules()
    
    def process(self, value: Any) -> ValidationResult:
        """Process text value (required by abstract base class)"""
        return self.validate_and_process(value)
    
    def validate_and_process(self, value: Any) -> ValidationResult:
        """
        Validate and process a text value
        
        Args:
            value: Raw text value to validate and process
            
        Returns:
            ValidationResult with processed text or error information
        """
        # Handle null/empty values
        if self.is_null_or_empty(value):
            return self.create_success_result(
                processed_value=self.handle_null_value(),
                original_value=value,
                processing_notes=['Null text value handled']
            )
        
        try:
            # Convert to string
            str_value = str(value)
            processing_notes = []
            
            # Step 1: Encoding validation and normalization
            encoding_result = self._validate_and_normalize_encoding(str_value)
            if not encoding_result[0]:
                return self.create_failure_result(
                    original_value=value,
                    errors=[f'Encoding error: {encoding_result[1]}']
                )
            
            processed_text = encoding_result[1]
            if encoding_result[2]:
                processing_notes.extend(encoding_result[2])
            
            # Step 2: Unicode normalization
            if self.normalize_unicode:
                normalized_text = self._normalize_unicode(processed_text)
                if normalized_text != processed_text:
                    processing_notes.append('Unicode normalization applied')
                    processed_text = normalized_text
            
            # Step 3: Content cleaning
            cleaned_text = self._clean_text_content(processed_text)
            if cleaned_text != processed_text:
                processing_notes.append('Text cleaning applied')
                processed_text = cleaned_text
            
            # Step 4: Length validation
            length_result = self._validate_and_handle_length(processed_text)
            if not length_result[0]:
                return self.create_failure_result(
                    original_value=value,
                    errors=[length_result[1]]
                )
            
            processed_text = length_result[1]
            if length_result[2]:
                processing_notes.append(length_result[2])
            
            # Step 5: Final validation
            final_validation = self._final_text_validation(processed_text)
            if not final_validation[0]:
                return self.create_failure_result(
                    original_value=value,
                    errors=[final_validation[1]]
                )
            
            return self.create_success_result(
                processed_value=processed_text,
                original_value=value,
                processing_notes=processing_notes
            )
            
        except Exception as e:
            return self.create_failure_result(
                original_value=value,
                errors=[f'Text processing error: {str(e)}']
            )
    
    def _validate_and_normalize_encoding(self, text: str) -> tuple[bool, str, Optional[List[str]]]:
        """
        Validate and normalize text encoding
        
        Args:
            text: Input text to validate and normalize
            
        Returns:
            Tuple of (success, processed_text, processing_notes)
        """
        try:
            # Try to encode/decode with target encoding
            if self.encoding.lower() == 'utf-8':
                # Ensure proper UTF-8 encoding
                encoded = text.encode('utf-8', errors='ignore')
                decoded = encoded.decode('utf-8')
                
                if decoded != text:
                    return True, decoded, ['Invalid UTF-8 characters removed']
                else:
                    return True, text, None
            else:
                # Handle other encodings
                encoded = text.encode(self.encoding, errors='ignore')
                decoded = encoded.decode(self.encoding)
                return True, decoded, [f'Text normalized to {self.encoding}']
                
        except Exception as e:
            return False, f'Encoding validation failed: {str(e)}', None
    
    def _normalize_unicode(self, text: str) -> str:
        """
        Normalize Unicode characters to consistent forms
        
        Args:
            text: Text to normalize
            
        Returns:
            Unicode-normalized text
        """
        # Use NFKC normalization (canonical decomposition, then canonical composition)
        # This handles things like combining characters and ligatures
        normalized = unicodedata.normalize('NFKC', text)
        
        return normalized
    
    def _clean_text_content(self, text: str) -> str:
        """
        Clean text content based on configured rules
        
        Args:
            text: Text to clean
            
        Returns:
            Cleaned text
        """
        cleaned = text
        
        # Remove HTML tags if configured
        if self.remove_html:
            cleaned = self._remove_html_tags(cleaned)
        
        # Remove URLs if configured
        if self.remove_urls:
            cleaned = self._remove_urls(cleaned)
        
        # Apply custom cleaning patterns
        for pattern, replacement in self.custom_clean_patterns.items():
            cleaned = re.sub(pattern, replacement, cleaned)
        
        # Character filtering based on preservation settings
        if not self.allow_special_chars:
            cleaned = self._filter_characters(cleaned)
        
        # Normalize whitespace if configured
        if self.normalize_whitespace:
            cleaned = self._normalize_whitespace(cleaned)
        
        return cleaned
    
    def _remove_html_tags(self, text: str) -> str:
        """
        Remove HTML tags from text
        
        Args:
            text: Text with potential HTML tags
            
        Returns:
            Text with HTML tags removed
        """
        # Remove HTML tags
        html_pattern = re.compile(r'<[^>]+>')
        text_no_html = html_pattern.sub('', text)
        
        # Decode common HTML entities
        html_entities = {
            '&amp;': '&',
            '&lt;': '<',
            '&gt;': '>',
            '&quot;': '"',
            '&#39;': "'",
            '&nbsp;': ' '
        }
        
        for entity, char in html_entities.items():
            text_no_html = text_no_html.replace(entity, char)
        
        return text_no_html
    
    def _remove_urls(self, text: str) -> str:
        """
        Remove URLs from text
        
        Args:
            text: Text with potential URLs
            
        Returns:
            Text with URLs removed
        """
        # Pattern to match various URL formats
        url_pattern = re.compile(
            r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
        )
        
        # Also match www. patterns
        www_pattern = re.compile(r'www\.(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+')
        
        text_no_urls = url_pattern.sub('', text)
        text_no_urls = www_pattern.sub('', text_no_urls)
        
        return text_no_urls
    
    def _filter_characters(self, text: str) -> str:
        """
        Filter characters based on preservation settings
        
        Args:
            text: Text to filter
            
        Returns:
            Filtered text
        """
        allowed_chars = []
        
        for char in text:
            # Check if character should be preserved
            if self._should_preserve_character(char):
                allowed_chars.append(char)
            else:
                # Replace with space to avoid concatenation
                allowed_chars.append(' ')
        
        return ''.join(allowed_chars)
    
    def _should_preserve_character(self, char: str) -> bool:
        """
        Check if a character should be preserved based on settings
        
        Args:
            char: Character to check
            
        Returns:
            True if character should be preserved
        """
        # Always preserve whitespace
        if char.isspace():
            return True
        
        # Check Thai characters (Unicode range for Thai: U+0E00–U+0E7F)
        if self.preserve_thai_chars and '\u0e00' <= char <= '\u0e7f':
            return True
        
        # Check English characters
        if self.preserve_english_chars and char.isascii() and char.isalpha():
            return True
        
        # Check digits
        if self.preserve_digits and char.isdigit():
            return True
        
        # Common punctuation that's usually safe to keep
        safe_punctuation = '.,;:!?()-[]{}"\'\n\r\t'
        if char in safe_punctuation:
            return True
        
        return False
    
    def _normalize_whitespace(self, text: str) -> str:
        """
        Normalize whitespace in text
        
        Args:
            text: Text with potentially irregular whitespace
            
        Returns:
            Text with normalized whitespace
        """
        # Replace multiple whitespace with single space
        normalized = re.sub(r'\s+', ' ', text)
        
        # Strip leading and trailing whitespace
        normalized = normalized.strip()
        
        return normalized
    
    def _validate_and_handle_length(self, text: str) -> tuple[bool, str, Optional[str]]:
        """
        Validate text length and handle length violations
        
        Args:
            text: Text to validate
            
        Returns:
            Tuple of (success, processed_text, processing_note)
        """
        text_length = len(text)
        
        # Check minimum length
        if text_length < self.min_length:
            return False, f'Text too short: {text_length} < {self.min_length}', None
        
        # Check maximum length
        if text_length > self.max_length:
            if self.truncate_on_length_exceed:
                truncated = text[:self.max_length]
                # Try to truncate at word boundary if possible
                if ' ' in truncated:
                    last_space = truncated.rfind(' ')
                    if last_space > self.max_length * 0.8:  # Only if we don't lose too much
                        truncated = truncated[:last_space]
                
                return True, truncated, f'Text truncated from {text_length} to {len(truncated)} characters'
            else:
                return False, f'Text too long: {text_length} > {self.max_length}', None
        
        return True, text, None
    
    def _final_text_validation(self, text: str) -> tuple[bool, Optional[str]]:
        """
        Perform final validation checks on processed text
        
        Args:
            text: Processed text to validate
            
        Returns:
            Tuple of (success, error_message)
        """
        # Check if text became empty after processing (but wasn't originally empty)
        if not text.strip():
            return True, None  # Allow empty text after processing
        
        # Check for any remaining problematic characters
        if self.encoding.lower() == 'utf-8':
            try:
                text.encode('utf-8')
            except UnicodeEncodeError as e:
                return False, f'Final UTF-8 validation failed: {str(e)}'
        
        return True, None
    
    def _setup_column_specific_rules(self) -> None:
        """
        Setup cleaning rules specific to column types
        """
        column_lower = self.column_name.lower()
        
        # URL/media source columns - preserve URLs
        if 'ที่มาสื่อ' in self.column_name or 'source' in column_lower or 'url' in column_lower:
            self.remove_urls = False
            self.max_length = 300
        
        # Medical detail columns - stricter cleaning
        elif 'โรค' in self.column_name or 'อาการ' in self.column_name or 'medical' in column_lower:
            self.max_length = 500
            self.custom_clean_patterns.update({
                r'\d+\.\s*': '',  # Remove numbered list markers
                r'[-•]\s*': ''    # Remove bullet points
            })
        
        # Location columns - shorter length
        elif any(loc in self.column_name for loc in ['อำเภอ', 'ตำบล', 'district', 'subdistrict']):
            self.max_length = 100
        
        # Note/remark columns - longer length allowed
        elif 'หมายเหตุ' in self.column_name or 'ข้อมูลอื่น' in self.column_name or 'remark' in column_lower:
            self.max_length = 1000
        
        # Health region - specific pattern
        elif 'สคร.' in self.column_name:
            self.max_length = 50
            self.custom_clean_patterns.update({
                r'[^\d\sสคร\.]': ''  # Keep only digits, spaces, 'สคร.'
            })