"""
Time Processor for validating and processing time-related columns
"""

from typing import Any, Optional
from datetime import time, datetime
import re
from .base_validator import ValidationResult


class TimeProcessor:
    """Process and validate time columns"""
    
    def __init__(self, column_name: str = None, validation_config: dict = None):
        self.column_name = column_name
        self.config = validation_config or {}
        self.time_patterns = [
            r'(\d{1,2}):(\d{2})(?::(\d{2}))?',  # HH:MM or HH:MM:SS
            r'(\d{1,2})\.(\d{2})',  # HH.MM format
        ]
    
    def process(self, value: Any) -> ValidationResult:
        """Process time value"""
        if value is None or (isinstance(value, str) and value.strip() == ''):
            return ValidationResult(True, None)
        
        try:
            if isinstance(value, time):
                return ValidationResult(True, value.strftime('%H:%M:%S'))
            
            if isinstance(value, str):
                value = value.strip()
                
                for pattern in self.time_patterns:
                    match = re.search(pattern, value)
                    if match:
                        hour = int(match.group(1))
                        minute = int(match.group(2))
                        second = int(match.group(3)) if match.group(3) else 0
                        
                        if 0 <= hour <= 23 and 0 <= minute <= 59 and 0 <= second <= 59:
                            time_obj = time(hour, minute, second)
                            return ValidationResult(True, time_obj.strftime('%H:%M:%S'))
                
                return ValidationResult(False, value, f"Invalid time format: {value}")
            
            return ValidationResult(False, value, f"Unsupported time type: {type(value)}")
            
        except Exception as e:
            return ValidationResult(False, value, f"Time processing error: {str(e)}")