"""
Multiclass Validator for Multi-Type Column Processing

This module implements MulticlassValidator class for handling categorical
columns with controlled vocabulary, fuzzy matching, and normalization.
"""

import re
from typing import Any, Optional, Dict, List, Set
from difflib import get_close_matches
from .base_validator import BaseValidator, ValidationResult


class MulticlassValidator(BaseValidator):
    """
    Validator for multiclass/categorical columns with controlled vocabulary
    
    Handles columns like จังหวัดที่เกิดเหตุ, ภาค, เพศ, etc. with support for:
    - Controlled vocabulary matching
    - Fuzzy string matching for typos
    - Thai province/region normalization
    - Gender standardization
    - Occupation categorization
    """
    
    def __init__(self, column_name: str, validation_config: Optional[Dict] = None):
        """
        Initialize multiclass validator
        
        Args:
            column_name: Name of the column being processed
            validation_config: Configuration with vocabulary and matching settings
        """
        super().__init__()
        self.column_name = column_name
        self.config = validation_config or {}
        
        # Validation settings
        self.vocabulary = set(self.config.get('vocabulary', []))
        self.allow_fuzzy_matching = self.config.get('allow_fuzzy_matching', True)
        self.fuzzy_threshold = self.config.get('fuzzy_threshold', 0.6)
        self.case_sensitive = self.config.get('case_sensitive', False)
        self.allow_partial_matches = self.config.get('allow_partial_matches', True)
        self.default_value = self.config.get('default_value', 'ไม่ระบุ')
        self.strict_mode = self.config.get('strict_mode', False)
        
        # Setup column-specific vocabularies
        self._setup_column_vocabulary()
        
        # Normalization mappings
        self.normalization_map = self._build_normalization_map()
    
    def process(self, value: Any) -> ValidationResult:
        """Process multiclass value (required by abstract base class)"""
        return self.validate_and_process(value)
    
    def validate_and_process(self, value: Any) -> ValidationResult:
        """
        Validate and process a multiclass value
        
        Args:
            value: Raw value to validate and process
            
        Returns:
            ValidationResult with processed categorical value or error information
        """
        # Handle null/empty values
        if self.is_null_or_empty(value):
            return self.create_success_result(
                processed_value=self.default_value,
                original_value=value,
                processing_notes=['Null value mapped to default']
            )
        
        try:
            # Convert to string and clean
            str_value = str(value).strip()
            
            # Try exact vocabulary matching first
            exact_match = self._find_exact_match(str_value)
            if exact_match:
                return self.create_success_result(
                    processed_value=exact_match,
                    original_value=value,
                    processing_notes=[f'Exact match found: {exact_match}']
                )
            
            # Try normalization mapping
            normalized_value = self._apply_normalization(str_value)
            if normalized_value and normalized_value in self.vocabulary:
                return self.create_success_result(
                    processed_value=normalized_value,
                    original_value=value,
                    processing_notes=[f'Normalized: {str_value} -> {normalized_value}']
                )
            
            # Try fuzzy matching if enabled
            if self.allow_fuzzy_matching:
                fuzzy_match = self._find_fuzzy_match(str_value)
                if fuzzy_match:
                    return self.create_success_result(
                        processed_value=fuzzy_match,
                        original_value=value,
                        processing_notes=[f'Fuzzy match found: {str_value} -> {fuzzy_match}']
                    )
            
            # Try partial matching if enabled
            if self.allow_partial_matches:
                partial_match = self._find_partial_match(str_value)
                if partial_match:
                    return self.create_success_result(
                        processed_value=partial_match,
                        original_value=value,
                        processing_notes=[f'Partial match found: {str_value} -> {partial_match}']
                    )
            
            # If strict mode, return error; otherwise use default
            if self.strict_mode:
                return self.create_failure_result(
                    original_value=value,
                    errors=[f'Value "{str_value}" not in controlled vocabulary']
                )
            else:
                return self.create_success_result(
                    processed_value=self.default_value,
                    original_value=value,
                    processing_notes=[f'No match found, using default: {self.default_value}']
                )
            
        except Exception as e:
            return self.create_failure_result(
                original_value=value,
                errors=[f'Multiclass processing error: {str(e)}']
            )
    
    def _setup_column_vocabulary(self) -> None:
        """
        Setup vocabulary specific to the column type
        """
        column_lower = self.column_name.lower()
        
        # Thai provinces
        if 'จังหวัด' in self.column_name:
            self.vocabulary.update([
                'กรุงเทพฯ', 'กรุงเทพมหานคร', 'กระบี่', 'กาญจนบุรี', 'กาฬสินธุ์', 'กำแพงเพชร',
                'ขอนแก่น', 'จันทบุรี', 'ฉะเชิงเทรา', 'ชลบุรี', 'ชัยนาท', 'ชัยภูมิ', 'ชุมพร',
                'เชียงราย', 'เชียงใหม่', 'ตรัง', 'ตราด', 'ตาก', 'นครนายก', 'นครปฐม', 'นครพนม',
                'นครราชสีมา', 'นครศรีธรรมราช', 'นครสวรรค์', 'นนทบุรี', 'นราธิวาส', 'น่าน',
                'บึงกาฬ', 'บุรีรัมย์', 'ปทุมธานี', 'ประจวบคีรีขันธ์', 'ปราจีนบุรี', 'ปัตตานี',
                'พระนครศรีอยุธยา', 'พะเยา', 'พังงา', 'พัทลุง', 'พิจิตร', 'พิษณุโลก', 'เพชรบุรี',
                'เพชรบูรณ์', 'แพร่', 'ภูเก็ต', 'มหาสารคาม', 'มุกดาหาร', 'แม่ฮ่องสอน', 'ยะลา',
                'ยโสธร', 'ร้อยเอ็ด', 'ระนอง', 'ระยอง', 'ราชบุรี', 'ลพบุรี', 'ลำปาง', 'ลำพูน',
                'เลย', 'ศรีสะเกษ', 'สกลนคร', 'สงขลา', 'สตูล', 'สมุทรปราการ', 'สมุทรสงคราม',
                'สมุทรสาคร', 'สระแก้ว', 'สระบุรี', 'สิงห์บุรี', 'สุโขทัย', 'สุพรรณบุรี', 'สุราษฎร์ธานี',
                'สุรินทร์', 'หนองคาย', 'หนองบัวลำภู', 'อ่างทอง', 'อำนาจเจริญ', 'อุดรธานี',
                'อุตรดิตถ์', 'อุทัยธานี', 'อุบลราชธานี'
            ])
        
        # Thai regions
        elif 'ภาค' in self.column_name:
            self.vocabulary.update([
                'ภาคเหนือ', 'ภาคกลางและตะวันตก', 'ภาคตะวันออกเฉียงเหนือ', 
                'ภาคตะวันออก', 'ภาคใต้', 'ภาคกลาง', 'ภาคตะวันตก'
            ])
        
        # Gender
        elif 'เพศ' in self.column_name or 'gender' in column_lower:
            self.vocabulary.update(['ชาย', 'หญิง', 'ไม่ระบุ'])
        
        # Status
        elif 'สถานะ' in self.column_name or 'status' in column_lower:
            self.vocabulary.update(['เสียชีวิต', 'รอดชีวิต', 'ไม่ระบุ', 'รักษาอยู่'])
        
        # Thai months
        elif 'เดือน' in self.column_name or 'month' in column_lower:
            self.vocabulary.update([
                'มกราคม', 'กุมภาพันธ์', 'มีนาคม', 'เมษายน', 'พฤษภาคม', 'มิถุนายน',
                'กรกฎาคม', 'สิงหาคม', 'กันยายน', 'ตุลาคม', 'พฤศจิกายน', 'ธันวาคม'
            ])
        
        # Occupations (common Thai occupations)
        elif 'อาชีพ' in self.column_name or 'occupation' in column_lower:
            self.vocabulary.update([
                'เกษตรกร', 'รับจ้าง', 'พนักงานบริษัท', 'ข้าราชการ', 'ค้าขาย', 'แม่บ้าน',
                'นักเรียน', 'นักศึกษา', 'พนักงานร้านอาหาร', 'ช่างซ่อม', 'คนขับรถ',
                'แรงงาน', 'ผู้ประกอบการ', 'วิศวกร', 'ครู', 'แพทย์', 'พยาบาล',
                'ไม่ระบุ', 'เร่ร่อน', 'ว่างงาน', 'เกษียณอายุ'
            ])
    
    def _find_exact_match(self, value: str) -> Optional[str]:
        """
        Find exact match in vocabulary
        
        Args:
            value: Value to match
            
        Returns:
            Exact match or None
        """
        if not self.case_sensitive:
            # Case-insensitive exact matching
            value_lower = value.lower()
            for vocab_item in self.vocabulary:
                if vocab_item.lower() == value_lower:
                    return vocab_item
        else:
            # Case-sensitive exact matching
            if value in self.vocabulary:
                return value
        
        return None
    
    def _apply_normalization(self, value: str) -> Optional[str]:
        """
        Apply normalization mappings to the value
        
        Args:
            value: Value to normalize
            
        Returns:
            Normalized value or None
        """
        # Clean the value first
        cleaned_value = self._clean_value(value)
        
        # Check normalization map
        if cleaned_value in self.normalization_map:
            return self.normalization_map[cleaned_value]
        
        # Check case-insensitive normalization
        if not self.case_sensitive:
            cleaned_lower = cleaned_value.lower()
            for norm_key, norm_value in self.normalization_map.items():
                if norm_key.lower() == cleaned_lower:
                    return norm_value
        
        return None
    
    def _find_fuzzy_match(self, value: str) -> Optional[str]:
        """
        Find fuzzy match using string similarity
        
        Args:
            value: Value to match
            
        Returns:
            Best fuzzy match or None
        """
        if not self.allow_fuzzy_matching or not self.vocabulary:
            return None
        
        # Clean the value
        cleaned_value = self._clean_value(value)
        
        # Get close matches
        vocab_list = list(self.vocabulary)
        close_matches = get_close_matches(
            cleaned_value, 
            vocab_list, 
            n=1, 
            cutoff=self.fuzzy_threshold
        )
        
        if close_matches:
            return close_matches[0]
        
        # Try case-insensitive fuzzy matching
        if not self.case_sensitive:
            cleaned_lower = cleaned_value.lower()
            vocab_lower = [item.lower() for item in vocab_list]
            close_matches_lower = get_close_matches(
                cleaned_lower,
                vocab_lower,
                n=1,
                cutoff=self.fuzzy_threshold
            )
            
            if close_matches_lower:
                # Find the original case version
                matched_lower = close_matches_lower[0]
                for i, vocab_lower_item in enumerate(vocab_lower):
                    if vocab_lower_item == matched_lower:
                        return vocab_list[i]
        
        return None
    
    def _find_partial_match(self, value: str) -> Optional[str]:
        """
        Find partial match where value is contained in vocabulary item or vice versa
        
        Args:
            value: Value to match
            
        Returns:
            Best partial match or None
        """
        if not self.allow_partial_matches:
            return None
        
        cleaned_value = self._clean_value(value)
        
        # Skip very short values for partial matching
        if len(cleaned_value) < 3:
            return None
        
        comparison_value = cleaned_value.lower() if not self.case_sensitive else cleaned_value
        
        # Look for vocabulary items that contain the value or are contained by the value
        best_match = None
        best_score = 0
        
        for vocab_item in self.vocabulary:
            comparison_vocab = vocab_item.lower() if not self.case_sensitive else vocab_item
            
            # Check containment in both directions
            if comparison_value in comparison_vocab:
                # Value is contained in vocab item
                score = len(comparison_value) / len(comparison_vocab)
                if score > best_score and score > 0.3:  # At least 30% match
                    best_match = vocab_item
                    best_score = score
            elif comparison_vocab in comparison_value:
                # Vocab item is contained in value
                score = len(comparison_vocab) / len(comparison_value)
                if score > best_score and score > 0.3:
                    best_match = vocab_item
                    best_score = score
        
        return best_match
    
    def _clean_value(self, value: str) -> str:
        """
        Clean and normalize value for matching
        
        Args:
            value: Raw value to clean
            
        Returns:
            Cleaned value
        """
        # Remove common prefixes and suffixes
        cleaned = value.strip()
        
        # Remove prefixes for provinces
        if 'จังหวัด' in self.column_name:
            cleaned = re.sub(r'^(จ\.|จังหวัด)\s*', '', cleaned)
        
        # Remove prefixes for districts
        if 'อำเภอ' in self.column_name:
            cleaned = re.sub(r'^(อ\.|อำเภอ)\s*', '', cleaned)
        
        # Remove prefixes for subdistricts
        if 'ตำบล' in self.column_name:
            cleaned = re.sub(r'^(ต\.|ตำบล)\s*', '', cleaned)
        
        # Clean extra whitespace
        cleaned = ' '.join(cleaned.split())
        
        return cleaned.strip()
    
    def _build_normalization_map(self) -> Dict[str, str]:
        """
        Build normalization mapping for common variations
        
        Returns:
            Dictionary mapping variations to canonical forms
        """
        normalization_map = {}
        
        # Province normalizations
        if 'จังหวัด' in self.column_name:
            normalization_map.update({
                'กรุงเทพ': 'กรุงเทพฯ',
                'กรุงเทพมหานคร': 'กรุงเทพฯ',
                'bangkok': 'กรุงเทพฯ',
                'bkk': 'กรุงเทพฯ',
                'chonburi': 'ชลบุรี',
                'chiangmai': 'เชียงใหม่',
                'chiang mai': 'เชียงใหม่',
                'phuket': 'ภูเก็ต',
                'khon kaen': 'ขอนแก่น',
                'korat': 'นครราชสีมา',
                'nakhon ratchasima': 'นครราชสีมา',
                'ubon ratchathani': 'อุบลราชธานี',
                'ubon': 'อุบลราชธานี',
                'udon thani': 'อุดรธานี',
                'udon': 'อุดรธานี'
            })
        
        # Region normalizations
        elif 'ภาค' in self.column_name:
            normalization_map.update({
                'เหนือ': 'ภาคเหนือ',
                'ใต้': 'ภาคใต้',
                'อีสาน': 'ภาคตะวันออกเฉียงเหนือ',
                'ตะวันออกเฉียงเหนือ': 'ภาคตะวันออกเฉียงเหนือ',
                'กลาง': 'ภาคกลางและตะวันตก',
                'ตะวันตก': 'ภาคกลางและตะวันตก',
                'ตะวันออก': 'ภาคตะวันออก'
            })
        
        # Gender normalizations
        elif 'เพศ' in self.column_name:
            normalization_map.update({
                'male': 'ชาย',
                'female': 'หญิง',
                'man': 'ชาย',
                'woman': 'หญิง',
                'm': 'ชาย',
                'f': 'หญิง',
                'ผู้ชาย': 'ชาย',
                'ผู้หญิง': 'หญิง',
                'unknown': 'ไม่ระบุ',
                'n/a': 'ไม่ระบุ',
                'not specified': 'ไม่ระบุ'
            })
        
        # Status normalizations
        elif 'สถานะ' in self.column_name:
            normalization_map.update({
                'dead': 'เสียชีวิต',
                'died': 'เสียชีวิต',
                'deceased': 'เสียชีวิต',
                'death': 'เสียชีวิต',
                'alive': 'รอดชีวิต',
                'survived': 'รอดชีวิต',
                'living': 'รอดชีวิต',
                'unknown': 'ไม่ระบุ'
            })
        
        return normalization_map
    
    def add_to_vocabulary(self, values: List[str]) -> None:
        """
        Add new values to the vocabulary
        
        Args:
            values: List of values to add
        """
        self.vocabulary.update(values)
    
    def get_vocabulary_list(self) -> List[str]:
        """
        Get the current vocabulary as a sorted list
        
        Returns:
            Sorted list of vocabulary items
        """
        return sorted(list(self.vocabulary))