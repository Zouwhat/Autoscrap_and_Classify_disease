"""
Boolean Mapper for Multi-Type Column Processing

This module implements BooleanMapper class for standardizing boolean values
to 1/0/NULL format with support for Thai text variations and medical terminology.
"""

import re
from typing import Any, Optional, Dict, List
from .base_validator import BaseValidator, ValidationResult


class BooleanMapper(BaseValidator):
    """
    Mapper for boolean columns with standardized 1/0/NULL output
    
    Handles medical condition columns like ความดันโลหิตสูง, เบาหวาน, etc.
    with support for:
    - Thai text variations (มี/ไม่มี, ใช่/ไม่ใช่)
    - English boolean values (True/False, Yes/No) 
    - Numeric representations (1/0)
    - Medical terminology variations
    - Null value handling
    """
    
    # Comprehensive true value mappings
    TRUE_VALUES = {
        # Thai affirmative
        'มี', 'ใช่', 'จริง', 'ได้', 'เป็น', 'ผิด', 'มีอาการ', 'มีประวัติ', 
        'มีการสัมผัส', 'มีอาการแสดง', 'เป็นโรค', 'ป่วย', 'เป็นผู้ป่วย',
        
        # English affirmative
        'true', 'yes', 'positive', 'present', 'affected', 'confirmed',
        'diagnosed', 'existing', 'found', 'detected',
        
        # Numeric and symbols
        '1', '1.0', 'T', 'Y', '+', '✓', 'v',
        
        # Medical terminology (Thai)
        'พบ', 'ตรวจพบ', 'ได้รับการวินิจฉัย', 'มีการรักษา', 'ระบุ', 
        'มีโรคประจำตัว', 'ป่วยเป็น', 'เป็นโรคเรื้อรัง',
        
        # Specific medical conditions (Thai)
        'ความดันสูง', 'เบาหวาน', 'หัวใจ', 'หอบหืด', 'ตับ', 
        'ไต', 'ปอด', 'เลือด', 'ประสาท'
    }
    
    # Comprehensive false value mappings  
    FALSE_VALUES = {
        # Thai negative
        'ไม่มี', 'ไม่ใช่', 'ไม่จริง', 'ไม่ได้', 'ไม่เป็น', 'ไม่', 'ไม่พบ',
        'ไม่มีอาการ', 'ไม่มีประวัติ', 'ไม่มีการสัมผัส', 'ไม่เป็นโรค',
        'ไม่ป่วย', 'สุขภาพดี', 'ปกติ', 'ไม่ได้รับการวินิจฉัย',
        
        # English negative
        'false', 'no', 'negative', 'absent', 'normal', 'none', 'nil',
        'not found', 'not present', 'not affected', 'not confirmed',
        'not diagnosed', 'healthy', 'clear',
        
        # Numeric and symbols
        '0', '0.0', 'F', 'N', '-', '✗', 'x',
        
        # Medical terminology (Thai)
        'ไม่พบ', 'ไม่ตรวจพบ', 'ไม่มีโรคประจำตัว', 'ไม่เป็นโรค',
        'ไม่มีอาการแสดง', 'ไม่มีความผิดปกติ'
    }
    
    # Null/unknown value mappings
    NULL_VALUES = {
        # Thai unknown/unspecified
        'ไม่ระบุ', 'ไม่ทราบ', 'ไม่แน่ใจ', 'ไม่ชัดเจน', 'ไม่มีข้อมูล',
        'ไม่ได้บันทึก', 'ไม่ปรากฏ', 'รอตรวจสอบ', 'อยู่ระหว่างตรวจ',
        
        # English unknown/unspecified 
        'unknown', 'unclear', 'unspecified', 'pending', 'not recorded',
        'not available', 'not applicable', 'na', 'n/a', 'null', 'none',
        'empty', 'missing', 'tbd', 'to be determined',
        
        # Symbols and placeholders
        '', '-', '_', '?', '??', '...', 'xxx', 'n.a.'
    }
    
    def __init__(self, column_name: str, validation_config: Optional[Dict] = None):
        """
        Initialize boolean mapper
        
        Args:
            column_name: Name of the column being processed
            validation_config: Configuration with boolean mapping settings
        """
        super().__init__()
        self.column_name = column_name
        self.config = validation_config or {}
        
        # Boolean mapping settings
        self.output_format = self.config.get('output_format', 'numeric')  # 'numeric' or 'text'
        self.null_representation = self.config.get('null_representation', '')  # Empty string for CSV
        self.case_sensitive = self.config.get('case_sensitive', False)
        self.partial_matching = self.config.get('partial_matching', True)
        self.custom_true_values = set(self.config.get('custom_true_values', []))
        self.custom_false_values = set(self.config.get('custom_false_values', []))
        
        # Combine default and custom values
        self.all_true_values = self.TRUE_VALUES | self.custom_true_values
        self.all_false_values = self.FALSE_VALUES | self.custom_false_values
        
        # Medical condition specific mappings for this column
        self._setup_column_specific_mappings()
    
    def process(self, value: Any) -> ValidationResult:
        """Process boolean value (required by abstract base class)"""
        return self.validate_and_process(value)
    
    def validate_and_process(self, value: Any) -> ValidationResult:
        """
        Validate and process a boolean value
        
        Args:
            value: Raw value to validate and process
            
        Returns:
            ValidationResult with processed 1/0/NULL or error information
        """
        # Handle truly null/empty values first
        if self.is_null_or_empty(value):
            return self.create_success_result(
                processed_value=self.null_representation,
                original_value=value,
                processing_notes=['Null boolean value handled']
            )
        
        try:
            # Convert to string and clean
            str_value = str(value).strip()
            
            # Check for null/unknown patterns
            if self._is_null_value(str_value):
                return self.create_success_result(
                    processed_value=self.null_representation,
                    original_value=value,
                    processing_notes=['Unknown/null value mapped to empty']
                )
            
            # Try boolean value mapping
            boolean_result = self._map_boolean_value(str_value)
            
            if boolean_result[0] is not None:  # Mapping successful
                is_true, processing_note = boolean_result
                
                if self.output_format == 'numeric':
                    processed_value = '1' if is_true else '0'
                else:
                    processed_value = 'True' if is_true else 'False'
                
                return self.create_success_result(
                    processed_value=processed_value,
                    original_value=value,
                    processing_notes=[processing_note]
                )
            else:
                # Could not determine boolean value
                return self.create_failure_result(
                    original_value=value,
                    errors=[f'Cannot determine boolean value for: {str_value}']
                )
            
        except Exception as e:
            return self.create_failure_result(
                original_value=value,
                errors=[f'Boolean processing error: {str(e)}']
            )
    
    def _is_null_value(self, str_value: str) -> bool:
        """
        Check if string represents a null/unknown value
        
        Args:
            str_value: String value to check
            
        Returns:
            True if value represents null/unknown
        """
        normalized_value = str_value.lower().strip() if not self.case_sensitive else str_value.strip()
        
        # Check exact matches
        comparison_set = {v.lower() for v in self.NULL_VALUES} if not self.case_sensitive else self.NULL_VALUES
        
        if normalized_value in comparison_set:
            return True
        
        # Check partial matches if enabled
        if self.partial_matching:
            for null_val in comparison_set:
                if null_val in normalized_value or normalized_value in null_val:
                    return True
        
        return False
    
    def _map_boolean_value(self, str_value: str) -> tuple[Optional[bool], str]:
        """
        Map string value to boolean
        
        Args:
            str_value: String value to map
            
        Returns:
            Tuple of (boolean_value_or_None, processing_note)
        """
        normalized_value = str_value.lower().strip() if not self.case_sensitive else str_value.strip()
        
        # Check true values
        if self._matches_value_set(normalized_value, self.all_true_values):
            return True, f"Mapped '{str_value}' to True"
        
        # Check false values
        if self._matches_value_set(normalized_value, self.all_false_values):
            return False, f"Mapped '{str_value}' to False"
        
        # Try pattern-based matching for complex medical descriptions
        pattern_result = self._match_medical_patterns(str_value)
        if pattern_result[0] is not None:
            return pattern_result
        
        # Try numeric interpretation
        numeric_result = self._try_numeric_boolean(str_value)
        if numeric_result[0] is not None:
            return numeric_result
        
        return None, f"Could not map '{str_value}' to boolean value"
    
    def _matches_value_set(self, normalized_value: str, value_set: set) -> bool:
        """
        Check if normalized value matches any value in the set
        
        Args:
            normalized_value: Normalized string value
            value_set: Set of values to check against
            
        Returns:
            True if value matches
        """
        comparison_set = {v.lower() for v in value_set} if not self.case_sensitive else value_set
        
        # Exact match
        if normalized_value in comparison_set:
            return True
        
        # Partial match if enabled
        if self.partial_matching:
            for val in comparison_set:
                # Check if the value contains or is contained in any of the set values
                if (len(val) > 2 and val in normalized_value) or (len(normalized_value) > 2 and normalized_value in val):
                    return True
        
        return False
    
    def _match_medical_patterns(self, str_value: str) -> tuple[Optional[bool], str]:
        """
        Match medical condition patterns that might indicate true/false
        
        Args:
            str_value: String value to analyze
            
        Returns:
            Tuple of (boolean_value_or_None, processing_note)
        """
        str_lower = str_value.lower()
        
        # Patterns indicating positive/true condition
        positive_patterns = [
            r'(ป่วย|เป็น|มี).*(?:' + '|'.join(['โรค', 'อาการ', 'ความดัน', 'เบาหวาน', 'หัวใจ']) + ')',
            r'(?:ได้รับ|มี).*(?:การวินิจฉัย|การรักษา|การดูแล)',
            r'(?:ระดับ|ค่า).*(?:สูง|ต่ำ|ผิดปกติ)',
            r'(?:ประวัติ|ได้รับ).*(?:การรักษา|การผ่าตัด)'
        ]
        
        for pattern in positive_patterns:
            if re.search(pattern, str_value):
                return True, f"Medical pattern matched: positive condition detected"
        
        # Patterns indicating negative/false condition
        negative_patterns = [
            r'(?:ไม่|ไม่มี|ไม่เป็น|ไม่ป่วย).*(?:โรค|อาการ|ความดัน)',
            r'(?:สุขภาพ|ร่างกาย).*(?:ดี|ปกติ|แข็งแรง)',
            r'(?:ไม่ได้|ไม่มี).*(?:การรักษา|การดูแล|ประวัติ)'
        ]
        
        for pattern in negative_patterns:
            if re.search(pattern, str_value):
                return False, f"Medical pattern matched: negative condition detected"
        
        return None, "No medical pattern matched"
    
    def _try_numeric_boolean(self, str_value: str) -> tuple[Optional[bool], str]:
        """
        Try to interpret value as numeric boolean
        
        Args:
            str_value: String value to interpret
            
        Returns:
            Tuple of (boolean_value_or_None, processing_note)
        """
        try:
            # Extract numeric value
            numeric_match = re.search(r'(\d+(?:\.\d+)?)', str_value)
            if numeric_match:
                numeric_value = float(numeric_match.group(1))
                if numeric_value == 0:
                    return False, f"Numeric interpretation: {numeric_value} -> False"
                elif numeric_value == 1:
                    return True, f"Numeric interpretation: {numeric_value} -> True"
                else:
                    return None, f"Ambiguous numeric value: {numeric_value}"
        except:
            pass
        
        return None, "Could not interpret as numeric boolean"
    
    def _setup_column_specific_mappings(self) -> None:
        """
        Setup column-specific boolean mappings based on column name
        """
        column_lower = self.column_name.lower()
        
        # Medical condition specific mappings
        if 'ความดันโลหิตสูง' in self.column_name or 'hypertension' in column_lower:
            self.all_true_values.update(['ความดันสูง', 'bp สูง', 'htn', 'hypertensive'])
            self.all_false_values.update(['ความดันปกติ', 'bp ปกติ', 'normotensive'])
        
        elif 'เบาหวาน' in self.column_name or 'diabetes' in column_lower:
            self.all_true_values.update(['dm', 'diabetic', 'น้ำตาลในเลือดสูง', 'เบาหวานชนิดที่ 1', 'เบาหวานชนิดที่ 2'])
            self.all_false_values.update(['ไม่เป็นเบาหวาน', 'น้ำตาลในเลือดปกติ', 'non-diabetic'])
        
        elif 'หัวใจ' in self.column_name or 'cardiovascular' in column_lower or 'cardiac' in column_lower:
            self.all_true_values.update(['โรคหัวใจ', 'cardiac', 'cvd', 'หัวใจล้มเหลว', 'heart failure'])
            self.all_false_values.update(['หัวใจปกติ', 'cardiac normal', 'no cvd'])
        
        elif 'หอบหืด' in self.column_name or 'asthma' in column_lower:
            self.all_true_values.update(['asthmatic', 'มีอาการหอบหืด', 'ระบบทางเดินหายใจผิดปกติ'])
            self.all_false_values.update(['ไม่หอบหืด', 'ระบบทางเดินหายใจปกติ', 'no asthma'])
        
        elif 'โรคตับ' in self.column_name or 'liver' in column_lower:
            self.all_true_values.update(['liver disease', 'ตับแข็ง', 'ตับอักเสบ', 'hepatitis'])
            self.all_false_values.update(['ตับปกติ', 'liver normal', 'no liver disease'])