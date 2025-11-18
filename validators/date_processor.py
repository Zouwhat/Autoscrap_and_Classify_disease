"""
Date Processor for Multi-Type Column Processing

This module implements DateProcessor class for handling Thai date formats,
Buddhist/Gregorian calendar conversion, and ISO format standardization.
Includes month name extraction for derived fields.
"""

import re
from datetime import datetime, date
from typing import Any, Optional, Dict, Tuple
from .base_validator import BaseValidator, ValidationResult


class DateProcessor(BaseValidator):
    """
    Processor for date columns with Thai date format parsing and ISO conversion
    
    Handles ว/ด/ป เสียชีวิต column with support for:
    - Thai date formats (M/D/YYYY, DD/MM/YYYY, etc.)
    - Buddhist to Gregorian year conversion
    - ISO format output (YYYY-MM-DD)  
    - Thai month name extraction
    """
    
    # Thai month names mapping
    THAI_MONTHS = {
        1: 'มกราคม', 2: 'กุมภาพันธ์', 3: 'มีนาคม', 4: 'เมษายน',
        5: 'พฤษภาคม', 6: 'มิถุนายน', 7: 'กรกฎาคม', 8: 'สิงหาคม',
        9: 'กันยายน', 10: 'ตุลาคม', 11: 'พฤศจิกายน', 12: 'ธันวาคม'
    }
    
    # Reverse mapping for parsing Thai month names
    THAI_MONTH_NAMES_TO_NUM = {v: k for k, v in THAI_MONTHS.items()}
    
    # Additional Thai month abbreviations and variations
    THAI_MONTH_VARIATIONS = {
        'ม.ค.': 1, 'มค': 1, 'Jan': 1, 'January': 1,
        'ก.พ.': 2, 'กพ': 2, 'Feb': 2, 'February': 2,
        'มี.ค.': 3, 'มีค': 3, 'Mar': 3, 'March': 3,
        'เม.ย.': 4, 'เมย': 4, 'Apr': 4, 'April': 4,
        'พ.ค.': 5, 'พค': 5, 'May': 5,
        'มิ.ย.': 6, 'มิย': 6, 'Jun': 6, 'June': 6,
        'ก.ค.': 7, 'กค': 7, 'Jul': 7, 'July': 7,
        'ส.ค.': 8, 'สค': 8, 'Aug': 8, 'August': 8,
        'ก.ย.': 9, 'กย': 9, 'Sep': 9, 'September': 9,
        'ต.ค.': 10, 'ตค': 10, 'Oct': 10, 'October': 10,
        'พ.ย.': 11, 'พย': 11, 'Nov': 11, 'November': 11,
        'ธ.ค.': 12, 'ธค': 12, 'Dec': 12, 'December': 12
    }
    
    def __init__(self, column_name: str, validation_config: Optional[Dict] = None):
        """
        Initialize date processor
        
        Args:
            column_name: Name of the column being processed
            validation_config: Configuration with date format settings
        """
        super().__init__()
        self.column_name = column_name
        self.config = validation_config or {}
        
        # Date validation settings
        self.min_year = self.config.get('min_year', 2020)
        self.max_year = self.config.get('max_year', 2030)
        self.buddhist_era_cutoff = self.config.get('buddhist_era_cutoff', 2100)  # Years above this are Buddhist
        self.allow_future_dates = self.config.get('allow_future_dates', False)
        self.output_format = self.config.get('output_format', 'iso')  # 'iso' for YYYY-MM-DD
        
        # Supported input formats (order matters for parsing attempts)
        self.input_formats = [
            '%m/%d/%Y',    # 3/20/2561
            '%d/%m/%Y',    # 20/3/2561  
            '%Y/%m/%d',    # 2561/3/20
            '%m-%d-%Y',    # 3-20-2561
            '%d-%m-%Y',    # 20-3-2561
            '%Y-%m-%d',    # 2561-3-20
            '%m/%d/%y',    # 3/20/61
            '%d/%m/%y',    # 20/3/61
        ]
    
    def process(self, value: Any) -> ValidationResult:
        """Process date value (required by abstract base class)"""
        return self.validate_and_process(value)
    
    def validate_and_process(self, value: Any) -> ValidationResult:
        """
        Validate and process a date value
        
        Args:
            value: Raw date value to validate and process
            
        Returns:
            ValidationResult with processed ISO date or error information
        """
        # Handle null/empty values
        if self.is_null_or_empty(value):
            return self.create_success_result(
                processed_value=self.handle_null_value(),
                original_value=value,
                processing_notes=['Null date value handled']
            )
        
        try:
            # Convert to string and clean
            str_value = str(value).strip()
            
            # Try parsing with different strategies
            parse_result = self._parse_date_string(str_value)
            
            if not parse_result[0]:  # Parsing failed
                return self.create_failure_result(
                    original_value=value,
                    errors=[f'Unable to parse date: {str_value}', parse_result[2]]
                )
            
            parsed_date, processing_notes = parse_result[1], [parse_result[2]]
            
            # Validate date range
            if not self._is_valid_date_range(parsed_date):
                return self.create_failure_result(
                    original_value=value,
                    errors=[f'Date {parsed_date} outside valid range ({self.min_year}-{self.max_year})']
                )
            
            # Check future date constraint
            if not self.allow_future_dates and parsed_date > date.today():
                return self.create_failure_result(
                    original_value=value,
                    errors=[f'Future date not allowed: {parsed_date}']
                )
            
            # Format output
            if self.output_format == 'iso':
                processed_value = parsed_date.strftime('%Y-%m-%d')
            else:
                processed_value = str(parsed_date)
            
            return self.create_success_result(
                processed_value=processed_value,
                original_value=value,
                processing_notes=processing_notes
            )
            
        except Exception as e:
            return self.create_failure_result(
                original_value=value,
                errors=[f'Date processing error: {str(e)}']
            )
    
    def extract_thai_month_name(self, date_value: Any) -> Optional[str]:
        """
        Extract Thai month name from processed date
        
        Args:
            date_value: Date value (string or date object)
            
        Returns:
            Thai month name or None if extraction fails
        """
        try:
            if isinstance(date_value, str):
                # Try to parse ISO format first
                if re.match(r'\d{4}-\d{2}-\d{2}', date_value):
                    parsed_date = datetime.strptime(date_value, '%Y-%m-%d').date()
                else:
                    parse_result = self._parse_date_string(date_value)
                    if not parse_result[0]:
                        return None
                    parsed_date = parse_result[1]
            elif isinstance(date_value, date):
                parsed_date = date_value
            else:
                return None
            
            month_num = parsed_date.month
            return self.THAI_MONTHS.get(month_num)
            
        except Exception:
            return None
    
    def _parse_date_string(self, date_str: str) -> Tuple[bool, Optional[date], str]:
        """
        Parse date string using various format attempts
        
        Args:
            date_str: Date string to parse
            
        Returns:
            Tuple of (success, parsed_date, processing_note)
        """
        # Clean the date string
        cleaned_date = self._clean_date_string(date_str)
        
        # Try parsing with Thai month names first
        thai_month_result = self._parse_thai_month_format(cleaned_date)
        if thai_month_result[0]:
            return thai_month_result
        
        # Try parsing with standard date formats
        for fmt in self.input_formats:
            try:
                parsed_datetime = datetime.strptime(cleaned_date, fmt)
                parsed_date = parsed_datetime.date()
                
                # Convert Buddhist year to Gregorian if needed
                if parsed_date.year > self.buddhist_era_cutoff:
                    gregorian_year = parsed_date.year - 543
                    parsed_date = parsed_date.replace(year=gregorian_year)
                    note = f"Parsed {fmt}, converted Buddhist year {parsed_date.year + 543} to Gregorian {gregorian_year}"
                else:
                    note = f"Parsed with format {fmt}"
                
                return True, parsed_date, note
                
            except ValueError:
                continue
        
        # Try alternative parsing strategies
        alternative_result = self._parse_alternative_formats(cleaned_date)
        if alternative_result[0]:
            return alternative_result
        
        return False, None, f"No matching date format found for: {cleaned_date}"
    
    def _clean_date_string(self, date_str: str) -> str:
        """
        Clean and normalize date string for parsing
        
        Args:
            date_str: Raw date string
            
        Returns:
            Cleaned date string
        """
        # Remove common prefixes and suffixes
        cleaned = date_str.strip()
        
        # Remove Thai date indicators
        cleaned = re.sub(r'(วันที่|ว/ด/ป|เมื่อ)', '', cleaned)
        
        # Replace Thai numerals with Arabic numerals (basic implementation)
        thai_to_arabic = {
            '๐': '0', '๑': '1', '๒': '2', '๓': '3', '๔': '4',
            '๕': '5', '๖': '6', '๗': '7', '๘': '8', '๙': '9'
        }
        
        for thai_num, arabic_num in thai_to_arabic.items():
            cleaned = cleaned.replace(thai_num, arabic_num)
        
        # Normalize separators
        cleaned = re.sub(r'[.\s]+', '/', cleaned)
        cleaned = re.sub(r'[,]+', '/', cleaned)
        
        # Clean extra whitespace
        cleaned = ' '.join(cleaned.split())
        
        return cleaned.strip()
    
    def _parse_thai_month_format(self, date_str: str) -> Tuple[bool, Optional[date], str]:
        """
        Parse dates with Thai month names
        
        Args:
            date_str: Date string with potential Thai month names
            
        Returns:
            Tuple of (success, parsed_date, processing_note)
        """
        # Look for Thai month names in the string
        month_found = None
        month_name = None
        
        # Check full Thai month names
        for thai_month, month_num in self.THAI_MONTH_NAMES_TO_NUM.items():
            if thai_month in date_str:
                month_found = month_num
                month_name = thai_month
                break
        
        # Check abbreviations and variations
        if month_found is None:
            for abbrev, month_num in self.THAI_MONTH_VARIATIONS.items():
                if abbrev.lower() in date_str.lower():
                    month_found = month_num
                    month_name = abbrev
                    break
        
        if month_found is None:
            return False, None, "No Thai month name found"
        
        # Extract day and year from remaining text
        remaining_text = date_str.replace(month_name, '').strip()
        
        # Look for day and year patterns
        numbers = re.findall(r'\d+', remaining_text)
        
        if len(numbers) < 2:
            return False, None, f"Insufficient date components with month {month_name}"
        
        try:
            # Assume first number is day, second is year
            day = int(numbers[0])
            year = int(numbers[1])
            
            # Convert Buddhist year if needed
            if year > self.buddhist_era_cutoff:
                year = year - 543
            
            parsed_date = date(year, month_found, day)
            
            return True, parsed_date, f"Parsed Thai month format with {month_name}"
            
        except (ValueError, TypeError):
            return False, None, f"Invalid date components: day={numbers[0]}, month={month_name}, year={numbers[1]}"
    
    def _parse_alternative_formats(self, date_str: str) -> Tuple[bool, Optional[date], str]:
        """
        Try alternative parsing strategies for edge cases
        
        Args:
            date_str: Date string to parse
            
        Returns:
            Tuple of (success, parsed_date, processing_note)
        """
        # Try to extract numbers and make reasonable assumptions
        numbers = re.findall(r'\d+', date_str)
        
        if len(numbers) == 3:
            # Three numbers: try different combinations
            combinations = [
                (int(numbers[0]), int(numbers[1]), int(numbers[2])),  # M/D/Y
                (int(numbers[1]), int(numbers[0]), int(numbers[2])),  # D/M/Y
                (int(numbers[2]), int(numbers[1]), int(numbers[0]))   # Y/M/D
            ]
            
            for month, day, year in combinations:
                try:
                    # Convert Buddhist year if needed
                    if year > self.buddhist_era_cutoff:
                        year = year - 543
                    elif year < 100:  # Two-digit year
                        year = year + 2000 if year < 50 else year + 1900
                    
                    if 1 <= month <= 12 and 1 <= day <= 31:
                        parsed_date = date(year, month, day)
                        return True, parsed_date, f"Alternative parsing: {month}/{day}/{year}"
                        
                except ValueError:
                    continue
        
        return False, None, "All alternative parsing strategies failed"
    
    def _is_valid_date_range(self, date_obj: date) -> bool:
        """
        Check if date is within valid range
        
        Args:
            date_obj: Date object to validate
            
        Returns:
            True if date is within valid range
        """
        return self.min_year <= date_obj.year <= self.max_year