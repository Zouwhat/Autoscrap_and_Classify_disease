"""
Numeric Validators for Multi-Type Column Processing

This module implements IntegerValidator and FloatValidator classes
for processing numeric columns with range validation, clamping,
and outlier filtering according to business rules.
"""

import re
from typing import Any, Optional, Union, List, Dict
from .base_validator import NumericBaseValidator, ValidationResult


class IntegerValidator(NumericBaseValidator):
    """
    Validator for integer columns with range validation and clamping
    
    Handles columns like ที่, ปี, อายุ(ปี) with specific business rules
    including age clamping (0-120 years) and year validation.
    """
    
    def __init__(self, column_name: str, validation_config: Optional[Dict] = None):
        """
        Initialize integer validator
        
        Args:
            column_name: Name of the column being validated
            validation_config: Configuration with min_value, max_value, clamp_to_range
        """
        super().__init__()
        self.column_name = column_name
        self.config = validation_config or {}
        
        # Set default clamping for age columns
        if 'อายุ' in column_name:
            self.min_value = self.min_value or 0
            self.max_value = self.max_value or 120
            self.clamp_to_range = True
    
    def process(self, value: Any) -> ValidationResult:
        """Process integer value (required by abstract base class)"""
        return self.validate_and_process(value)
    
    def validate_and_process(self, value: Any) -> ValidationResult:
        """
        Validate and process an integer value
        
        Args:
            value: Raw value to validate and process
            
        Returns:
            ValidationResult with processed integer or error information
        """
        # Handle null/empty values
        if self.is_null_or_empty(value):
            if self.allow_null:
                return self.create_success_result(
                    processed_value=self.handle_null_value(),
                    original_value=value,
                    processing_notes=['Null value handled']
                )
            else:
                return self.create_failure_result(
                    original_value=value,
                    errors=['Null value not allowed for this column']
                )
        
        try:
            # Convert to string and clean
            str_value = str(value).strip()
            
            # Handle Thai/English text that might contain numbers
            if self._contains_numeric_text(str_value):
                str_value = self._extract_number_from_text(str_value)
            
            # Try direct integer conversion
            try:
                int_value = int(float(str_value))  # Handle cases like "41.0"
            except (ValueError, TypeError):
                return self.create_failure_result(
                    original_value=value,
                    errors=[f'Cannot convert to integer: {str_value}']
                )
            
            # Check and apply range validation
            is_valid, range_message = self.check_numeric_range(int_value)
            
            processing_notes = []
            if range_message:
                processing_notes.append(range_message)
            
            # Apply clamping if enabled
            if self.clamp_to_range:
                clamped_value = int(self.clamp_value(int_value))
                if clamped_value != int_value:
                    processing_notes.append(f'Value clamped from {int_value} to {clamped_value}')
                    int_value = clamped_value
            elif not is_valid:
                return self.create_failure_result(
                    original_value=value,
                    errors=[range_message]
                )
            
            # Format as string for CSV output
            processed_value = str(int_value)
            
            return self.create_success_result(
                processed_value=processed_value,
                original_value=value,
                processing_notes=processing_notes
            )
            
        except Exception as e:
            return self.create_failure_result(
                original_value=value,
                errors=[f'Integer processing error: {str(e)}']
            )
    
    def _contains_numeric_text(self, text: str) -> bool:
        """
        Check if text contains Thai or English numeric descriptions
        
        Args:
            text: Text to check
            
        Returns:
            True if text contains numeric indicators
        """
        # Thai number words
        thai_numbers = ['หนึ่ง', 'สอง', 'สาม', 'สี่', 'ห้า', 'หก', 'เจ็ด', 'แปด', 'เก้า', 'สิบ']
        text_lower = text.lower()
        
        return any(thai_num in text for thai_num in thai_numbers) or \
               any(eng_num in text_lower for eng_num in ['one', 'two', 'three', 'four', 'five'])
    
    def _extract_number_from_text(self, text: str) -> str:
        """
        Extract numeric value from text that contains number descriptions
        
        Args:
            text: Text containing number descriptions
            
        Returns:
            Extracted numeric string or original text if no extraction possible
        """
        # Look for digits in the text first
        digits = re.findall(r'\d+', text)
        if digits:
            return digits[0]  # Return first found digit sequence
        
        # Thai number mapping (basic implementation)
        thai_to_int = {
            'หนึ่ง': '1', 'สอง': '2', 'สาม': '3', 'สี่': '4', 'ห้า': '5',
            'หก': '6', 'เจ็ด': '7', 'แปด': '8', 'เก้า': '9', 'สิบ': '10'
        }
        
        for thai, digit in thai_to_int.items():
            if thai in text:
                return digit
        
        return text  # Return original if no extraction possible


class FloatValidator(NumericBaseValidator):
    """
    Validator for float columns with range validation and outlier filtering
    
    Handles temperature columns like อุณหภูมิ สวล.(C°), อุณหภูมิร่างกาย(C°)
    with specific temperature range validation and outlier detection.
    """
    
    def __init__(self, column_name: str, validation_config: Optional[Dict] = None):
        """
        Initialize float validator
        
        Args:
            column_name: Name of the column being validated
            validation_config: Configuration with min_value, max_value, precision, etc.
        """
        super().__init__()
        self.column_name = column_name
        self.config = validation_config or {}
        
        # Set default temperature ranges
        if 'อุณหภูมิ' in column_name:
            if 'สวล' in column_name or 'สิ่งแวดล้อม' in column_name:
                # Environmental temperature range
                self.min_value = self.min_value or -10.0
                self.max_value = self.max_value or 60.0
            elif 'ร่างกาย' in column_name or 'body' in column_name.lower():
                # Body temperature range
                self.min_value = self.min_value or 30.0
                self.max_value = self.max_value or 45.0
        
        # Precision settings
        self.decimal_places = self.config.get('decimal_places', 1)
        self.outlier_detection = self.config.get('outlier_detection', True)
        self.outlier_threshold_std = self.config.get('outlier_threshold_std', 3.0)
    
    def process(self, value: Any) -> ValidationResult:
        """Process float value (required by abstract base class)"""
        return self.validate_and_process(value)
    
    def validate_and_process(self, value: Any) -> ValidationResult:
        """
        Validate and process a float value
        
        Args:
            value: Raw value to validate and process
            
        Returns:
            ValidationResult with processed float or error information
        """
        # Handle null/empty values
        if self.is_null_or_empty(value):
            if self.allow_null:
                return self.create_success_result(
                    processed_value=self.handle_null_value(),
                    original_value=value,
                    processing_notes=['Null value handled']
                )
            else:
                return self.create_failure_result(
                    original_value=value,
                    errors=['Null value not allowed for this column']
                )
        
        try:
            # Convert to string and clean
            str_value = str(value).strip()
            
            # Handle temperature unit indicators
            str_value = self._clean_temperature_value(str_value)
            
            # Try float conversion
            try:
                float_value = float(str_value)
            except (ValueError, TypeError):
                return self.create_failure_result(
                    original_value=value,
                    errors=[f'Cannot convert to float: {str_value}']
                )
            
            # Check for NaN or infinite values
            if not self._is_valid_float(float_value):
                return self.create_failure_result(
                    original_value=value,
                    errors=['Invalid float value (NaN or infinite)']
                )
            
            # Check and apply range validation
            is_valid, range_message = self.check_numeric_range(float_value)
            
            processing_notes = []
            if range_message:
                processing_notes.append(range_message)
            
            # Apply clamping if enabled
            if self.clamp_to_range:
                clamped_value = self.clamp_value(float_value)
                if clamped_value != float_value:
                    processing_notes.append(f'Value clamped from {float_value} to {clamped_value}')
                    float_value = clamped_value
            elif not is_valid:
                return self.create_failure_result(
                    original_value=value,
                    errors=[range_message]
                )
            
            # Check for outliers (if enabled)
            if self.outlier_detection and self._is_outlier(float_value):
                processing_notes.append(f'Potential outlier detected: {float_value}')
            
            # Format with appropriate precision
            if self.decimal_places == 0:
                processed_value = str(int(round(float_value)))
            else:
                processed_value = f"{float_value:.{self.decimal_places}f}"
            
            return self.create_success_result(
                processed_value=processed_value,
                original_value=value,
                processing_notes=processing_notes
            )
            
        except Exception as e:
            return self.create_failure_result(
                original_value=value,
                errors=[f'Float processing error: {str(e)}']
            )
    
    def _clean_temperature_value(self, value_str: str) -> str:
        """
        Clean temperature value by removing unit indicators
        
        Args:
            value_str: Raw string value
            
        Returns:
            Cleaned numeric string
        """
        # Remove common temperature unit indicators
        units_to_remove = ['°C', '°F', 'C°', 'F°', 'องศา', 'เซลเซียส', 'ฟาเรนไฮต์', '度']
        
        cleaned = value_str
        for unit in units_to_remove:
            cleaned = cleaned.replace(unit, '')
        
        # Remove extra whitespace
        cleaned = cleaned.strip()
        
        # Handle decimal separators
        cleaned = cleaned.replace(',', '.')  # Handle comma as decimal separator
        
        return cleaned
    
    def _is_valid_float(self, float_value: float) -> bool:
        """
        Check if float value is valid (not NaN or infinite)
        
        Args:
            float_value: Float value to check
            
        Returns:
            True if valid float
        """
        import math
        return not (math.isnan(float_value) or math.isinf(float_value))
    
    def _is_outlier(self, float_value: float) -> bool:
        """
        Simple outlier detection based on range thresholds
        
        Args:
            float_value: Float value to check
            
        Returns:
            True if value appears to be an outlier
        """
        # For temperature columns, use domain-specific outlier detection
        if 'อุณหภูมิ' in self.column_name:
            if 'สวล' in self.column_name or 'สิ่งแวดล้อม' in self.column_name:
                # Environmental temperature outliers
                return float_value < -20 or float_value > 70
            elif 'ร่างกาย' in self.column_name:
                # Body temperature outliers  
                return float_value < 25 or float_value > 50
        
        # Generic outlier detection
        if self.min_value is not None and self.max_value is not None:
            range_size = self.max_value - self.min_value
            outlier_threshold = range_size * 0.1  # 10% beyond range
            return (float_value < self.min_value - outlier_threshold or 
                   float_value > self.max_value + outlier_threshold)
        
        return False