"""
Heat Data Schema for Story 3.1: Multi-Type Column Processing

This module defines the complete schema for the heat_data.csv output format,
including all 40+ columns with their data types, validation rules, and
business logic constraints.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Union, Any, Tuple
from enum import Enum
import re


class ColumnType(Enum):
    """Enumeration of supported column data types"""
    INTEGER = "integer"
    FLOAT = "float"
    DATE = "date"
    TIME = "time"
    BOOLEAN = "boolean"
    MULTICLASS = "multiclass"
    TEXT = "text"


class ValidationRule(Enum):
    """Enumeration of validation rules"""
    REQUIRED = "required"
    RANGE = "range"
    PATTERN = "pattern"
    VOCABULARY = "vocabulary"
    LENGTH = "length"
    ENCODING = "encoding"


@dataclass
class ColumnSpec:
    """Specification for a single column in the heat data schema"""
    name: str
    display_name: str
    data_type: ColumnType
    required: bool = False
    default_value: Optional[str] = None
    validation_rules: Dict[ValidationRule, Any] = None
    description: str = ""
    
    def __post_init__(self):
        """Initialize validation rules if None"""
        if self.validation_rules is None:
            self.validation_rules = {}


class HeatDataSchema:
    """
    Complete schema definition for heat_data.csv with 40+ columns
    
    This schema matches the exact structure from heat_data_sample.csv
    and includes data type specifications, validation rules, and
    business logic for each column.
    """
    
    # Exact column order from heat_data_sample.csv
    COLUMN_ORDER = [
        'ที่', 'จังหวัดที่เกิดเหตุ', 'อำเภอ', 'ตำบล', 'ภาค', 'สคร.', 'ปี', 'สถานะ',
        'ว/ด/ป เสียชีวิต', 'เดือน ที่เสียชีวิต', 'เวลาที่เสียชีวิต', 'เพศ', 'อายุ(ปี)',
        'เชื้อชาติ', 'สัญชาติ', 'อาชีพ', 'ลักษณะงาน', 'โรคประจำตัว', 'โรคประจำตัว(รายละเอียด)',
        'ความดันโลหิตสูง', 'เบาหวาน', 'หัวใจและหลอดเลือด', 'หอบหืด', 'โรคตับ', 'โรคอื่นๆ',
        'พฤติกรรมเสี่ยง', 'สถานที่ป่วย/หรือเสียชีวิต', 'ลักษณะพื้นที่', 'อุณหภูมิ สวล.(C°)',
        'ลักษณะอาการ', 'กิจกรรม/พฤติกรรมเสี่ยงก่อนเกิดเหตุ', 'อุณหภูมิร่างกาย(C°)',
        'ประวัติการสัมผัสความร้อนก่อนเสียชีวิต', 'ICD 10', 'ผลการวินิจฉัย', 'Unnamed: 35',
        'ข้อมูลอื่นๆ', 'หมายเหตุ', 'ที่มาสื่อออนไลน์'
    ]
    
    # Thai province vocabulary
    THAI_PROVINCES = [
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
    ]
    
    # Thai regions
    THAI_REGIONS = [
        'ภาคเหนือ', 'ภาคกลางและตะวันตก', 'ภาคตะวันออกเฉียงเหนือ', 'ภาคตะวันออก', 'ภาคใต้'
    ]
    
    # Gender vocabulary
    GENDER_VOCABULARY = ['ชาย', 'หญิง', 'ไม่ระบุ']
    
    # Boolean values mapping
    BOOLEAN_TRUE_VALUES = ['มี', '1', 'True', 'true', 'YES', 'Yes', 'yes', 'ใช่', 'มีการสัมผัส']
    BOOLEAN_FALSE_VALUES = ['ไม่มี', '0', 'False', 'false', 'NO', 'No', 'no', 'ไม่ใช่', 'ไม่มีการสัมผัส']
    
    # Status vocabulary
    STATUS_VOCABULARY = ['เสียชีวิต', 'รอดชีวิต', 'ไม่ระบุ']
    
    @classmethod
    def get_schema_definition(cls) -> Dict[str, ColumnSpec]:
        """
        Get complete schema definition with all column specifications
        
        Returns:
            Dictionary mapping column names to their specifications
        """
        return {
            # Numeric columns
            'ที่': ColumnSpec(
                name='ที่',
                display_name='ID',
                data_type=ColumnType.FLOAT,
                required=False,
                default_value=None,
                validation_rules={
                    ValidationRule.RANGE: (1, 99999)
                },
                description='Auto-increment ID number'
            ),
            
            'ปี': ColumnSpec(
                name='ปี',
                display_name='Year',
                data_type=ColumnType.INTEGER,
                required=False,
                default_value=None,
                validation_rules={
                    ValidationRule.RANGE: (2020, 2030)
                },
                description='Year of incident (Buddhist or Gregorian)'
            ),
            
            'อายุ(ปี)': ColumnSpec(
                name='อายุ(ปี)',
                display_name='Age (Years)',
                data_type=ColumnType.INTEGER,
                required=False,
                default_value=None,
                validation_rules={
                    ValidationRule.RANGE: (0, 120)
                },
                description='Age in years with clamping 0-120'
            ),
            
            'อุณหภูมิ สวล.(C°)': ColumnSpec(
                name='อุณหภูมิ สวล.(C°)',
                display_name='Environmental Temperature (°C)',
                data_type=ColumnType.FLOAT,
                required=False,
                default_value=None,
                validation_rules={
                    ValidationRule.RANGE: (-10.0, 60.0)
                },
                description='Environmental temperature in Celsius'
            ),
            
            'อุณหภูมิร่างกาย(C°)': ColumnSpec(
                name='อุณหภูมิร่างกาย(C°)',
                display_name='Body Temperature (°C)',
                data_type=ColumnType.FLOAT,
                required=False,
                default_value=None,
                validation_rules={
                    ValidationRule.RANGE: (30.0, 45.0)
                },
                description='Body temperature in Celsius'
            ),
            
            # Date column
            'ว/ด/ป เสียชีวิต': ColumnSpec(
                name='ว/ด/ป เสียชีวิต',
                display_name='Date of Death',
                data_type=ColumnType.DATE,
                required=False,
                default_value=None,
                validation_rules={
                    ValidationRule.PATTERN: r'\d{1,2}/\d{1,2}/\d{4}'
                },
                description='Date of death in M/D/YYYY format, converts to ISO'
            ),
            
            # Time column
            'เวลาที่เสียชีวิต': ColumnSpec(
                name='เวลาที่เสียชีวิต',
                display_name='Time of Death',
                data_type=ColumnType.TIME,
                required=False,
                default_value=None,
                validation_rules={
                    ValidationRule.PATTERN: r'^([0-1]?[0-9]|2[0-3]):[0-5][0-9](:[0-5][0-9])?$'
                },
                description='Time of death in HH:MM:SS format'
            ),
            
            # Boolean columns (medical conditions)
            'ความดันโลหิตสูง': ColumnSpec(
                name='ความดันโลหิตสูง',
                display_name='Hypertension',
                data_type=ColumnType.BOOLEAN,
                required=False,
                default_value=None,
                validation_rules={
                    ValidationRule.VOCABULARY: cls.BOOLEAN_TRUE_VALUES + cls.BOOLEAN_FALSE_VALUES
                },
                description='Hypertension condition (1/0/NULL)'
            ),
            
            'เบาหวาน': ColumnSpec(
                name='เบาหวาน',
                display_name='Diabetes',
                data_type=ColumnType.BOOLEAN,
                required=False,
                default_value=None,
                validation_rules={
                    ValidationRule.VOCABULARY: cls.BOOLEAN_TRUE_VALUES + cls.BOOLEAN_FALSE_VALUES
                },
                description='Diabetes condition (1/0/NULL)'
            ),
            
            'หัวใจและหลอดเลือด': ColumnSpec(
                name='หัวใจและหลอดเลือด',
                display_name='Cardiovascular Disease',
                data_type=ColumnType.BOOLEAN,
                required=False,
                default_value=None,
                validation_rules={
                    ValidationRule.VOCABULARY: cls.BOOLEAN_TRUE_VALUES + cls.BOOLEAN_FALSE_VALUES
                },
                description='Cardiovascular disease condition (1/0/NULL)'
            ),
            
            'หอบหืด': ColumnSpec(
                name='หอบหืด',
                display_name='Asthma',
                data_type=ColumnType.BOOLEAN,
                required=False,
                default_value=None,
                validation_rules={
                    ValidationRule.VOCABULARY: cls.BOOLEAN_TRUE_VALUES + cls.BOOLEAN_FALSE_VALUES
                },
                description='Asthma condition (1/0/NULL)'
            ),
            
            'โรคตับ': ColumnSpec(
                name='โรคตับ',
                display_name='Liver Disease',
                data_type=ColumnType.BOOLEAN,
                required=False,
                default_value=None,
                validation_rules={
                    ValidationRule.VOCABULARY: cls.BOOLEAN_TRUE_VALUES + cls.BOOLEAN_FALSE_VALUES
                },
                description='Liver disease condition (1/0/NULL)'
            ),
            
            'ประวัติการสัมผัสความร้อนก่อนเสียชีวิต': ColumnSpec(
                name='ประวัติการสัมผัสความร้อนก่อนเสียชีวิต',
                display_name='Heat Exposure History',
                data_type=ColumnType.BOOLEAN,
                required=False,
                default_value=None,
                validation_rules={
                    ValidationRule.VOCABULARY: cls.BOOLEAN_TRUE_VALUES + cls.BOOLEAN_FALSE_VALUES
                },
                description='History of heat exposure before death (1/0/NULL)'
            ),
            
            # Multiclass columns
            'จังหวัดที่เกิดเหตุ': ColumnSpec(
                name='จังหวัดที่เกิดเหตุ',
                display_name='Province',
                data_type=ColumnType.MULTICLASS,
                required=False,
                default_value=None,
                validation_rules={
                    ValidationRule.VOCABULARY: cls.THAI_PROVINCES
                },
                description='Thai province where incident occurred'
            ),
            
            'ภาค': ColumnSpec(
                name='ภาค',
                display_name='Region',
                data_type=ColumnType.MULTICLASS,
                required=False,
                default_value=None,
                validation_rules={
                    ValidationRule.VOCABULARY: cls.THAI_REGIONS
                },
                description='Thai geographical region'
            ),
            
            'เพศ': ColumnSpec(
                name='เพศ',
                display_name='Gender',
                data_type=ColumnType.MULTICLASS,
                required=False,
                default_value=None,
                validation_rules={
                    ValidationRule.VOCABULARY: cls.GENDER_VOCABULARY
                },
                description='Gender (Male/Female/Not specified)'
            ),
            
            'สถานะ': ColumnSpec(
                name='สถานะ',
                display_name='Status',
                data_type=ColumnType.MULTICLASS,
                required=False,
                default_value='เสียชีวิต',
                validation_rules={
                    ValidationRule.VOCABULARY: cls.STATUS_VOCABULARY
                },
                description='Life status (deceased/survived/unspecified)'
            ),
            
            'เดือน ที่เสียชีวิต': ColumnSpec(
                name='เดือน ที่เสียชีวิต',
                display_name='Month of Death',
                data_type=ColumnType.MULTICLASS,
                required=False,
                default_value=None,
                validation_rules={
                    ValidationRule.VOCABULARY: [
                        'มกราคม', 'กุมภาพันธ์', 'มีนาคม', 'เมษายน', 'พฤษภาคม', 'มิถุนายน',
                        'กรกฎาคม', 'สิงหาคม', 'กันยายน', 'ตุลาคม', 'พฤศจิกายน', 'ธันวาคม'
                    ]
                },
                description='Month of death (derived from date)'
            ),
            
            # Text columns
            'อำเภอ': ColumnSpec(
                name='อำเภอ',
                display_name='District',
                data_type=ColumnType.TEXT,
                required=False,
                default_value=None,
                validation_rules={
                    ValidationRule.LENGTH: (0, 100),
                    ValidationRule.ENCODING: 'utf-8'
                },
                description='District name (amphoe)'
            ),
            
            'ตำบล': ColumnSpec(
                name='ตำบล',
                display_name='Subdistrict',
                data_type=ColumnType.TEXT,
                required=False,
                default_value=None,
                validation_rules={
                    ValidationRule.LENGTH: (0, 100),
                    ValidationRule.ENCODING: 'utf-8'
                },
                description='Subdistrict name (tambon)'
            ),
            
            'สคร.': ColumnSpec(
                name='สคร.',
                display_name='Health Region',
                data_type=ColumnType.TEXT,
                required=False,
                default_value=None,
                validation_rules={
                    ValidationRule.LENGTH: (0, 50),
                    ValidationRule.PATTERN: r'^สคร\.\s*\d{1,2}$'
                },
                description='Health service region (สคร. X)'
            ),
            
            'เชื้อชาติ': ColumnSpec(
                name='เชื้อชาติ',
                display_name='Ethnicity',
                data_type=ColumnType.TEXT,
                required=False,
                default_value=None,
                validation_rules={
                    ValidationRule.LENGTH: (0, 50),
                    ValidationRule.ENCODING: 'utf-8'
                },
                description='Ethnicity'
            ),
            
            'สัญชาติ': ColumnSpec(
                name='สัญชาติ',
                display_name='Nationality',
                data_type=ColumnType.TEXT,
                required=False,
                default_value=None,
                validation_rules={
                    ValidationRule.LENGTH: (0, 50),
                    ValidationRule.ENCODING: 'utf-8'
                },
                description='Nationality'
            ),
            
            'อาชีพ': ColumnSpec(
                name='อาชีพ',
                display_name='Occupation',
                data_type=ColumnType.TEXT,
                required=False,
                default_value=None,
                validation_rules={
                    ValidationRule.LENGTH: (0, 100),
                    ValidationRule.ENCODING: 'utf-8'
                },
                description='Occupation'
            ),
            
            'ลักษณะงาน': ColumnSpec(
                name='ลักษณะงาน',
                display_name='Work Type',
                data_type=ColumnType.TEXT,
                required=False,
                default_value=None,
                validation_rules={
                    ValidationRule.LENGTH: (0, 200),
                    ValidationRule.ENCODING: 'utf-8'
                },
                description='Type of work/job description'
            ),
            
            'โรคประจำตัว': ColumnSpec(
                name='โรคประจำตัว',
                display_name='Chronic Disease',
                data_type=ColumnType.TEXT,
                required=False,
                default_value=None,
                validation_rules={
                    ValidationRule.LENGTH: (0, 200),
                    ValidationRule.ENCODING: 'utf-8'
                },
                description='Chronic diseases (summary)'
            ),
            
            'โรคประจำตัว(รายละเอียด)': ColumnSpec(
                name='โรคประจำตัว(รายละเอียด)',
                display_name='Chronic Disease Details',
                data_type=ColumnType.TEXT,
                required=False,
                default_value=None,
                validation_rules={
                    ValidationRule.LENGTH: (0, 500),
                    ValidationRule.ENCODING: 'utf-8'
                },
                description='Detailed chronic disease information'
            ),
            
            'โรคอื่นๆ': ColumnSpec(
                name='โรคอื่นๆ',
                display_name='Other Diseases',
                data_type=ColumnType.TEXT,
                required=False,
                default_value=None,
                validation_rules={
                    ValidationRule.LENGTH: (0, 200),
                    ValidationRule.ENCODING: 'utf-8'
                },
                description='Other diseases or conditions'
            ),
            
            'พฤติกรรมเสี่ยง': ColumnSpec(
                name='พฤติกรรมเสี่ยง',
                display_name='Risk Behavior',
                data_type=ColumnType.TEXT,
                required=False,
                default_value=None,
                validation_rules={
                    ValidationRule.LENGTH: (0, 300),
                    ValidationRule.ENCODING: 'utf-8'
                },
                description='Risk behaviors'
            ),
            
            'สถานที่ป่วย/หรือเสียชีวิต': ColumnSpec(
                name='สถานที่ป่วย/หรือเสียชีวิต',
                display_name='Location of Illness/Death',
                data_type=ColumnType.TEXT,
                required=False,
                default_value=None,
                validation_rules={
                    ValidationRule.LENGTH: (0, 200),
                    ValidationRule.ENCODING: 'utf-8'
                },
                description='Location where illness occurred or death happened'
            ),
            
            'ลักษณะพื้นที่': ColumnSpec(
                name='ลักษณะพื้นที่',
                display_name='Area Characteristics',
                data_type=ColumnType.TEXT,
                required=False,
                default_value=None,
                validation_rules={
                    ValidationRule.LENGTH: (0, 300),
                    ValidationRule.ENCODING: 'utf-8'
                },
                description='Characteristics of the area/environment'
            ),
            
            'ลักษณะอาการ': ColumnSpec(
                name='ลักษณะอาการ',
                display_name='Symptoms',
                data_type=ColumnType.TEXT,
                required=False,
                default_value=None,
                validation_rules={
                    ValidationRule.LENGTH: (0, 300),
                    ValidationRule.ENCODING: 'utf-8'
                },
                description='Symptoms and clinical presentation'
            ),
            
            'กิจกรรม/พฤติกรรมเสี่ยงก่อนเกิดเหตุ': ColumnSpec(
                name='กิจกรรม/พฤติกรรมเสี่ยงก่อนเกิดเหตุ',
                display_name='Pre-incident Activities',
                data_type=ColumnType.TEXT,
                required=False,
                default_value=None,
                validation_rules={
                    ValidationRule.LENGTH: (0, 400),
                    ValidationRule.ENCODING: 'utf-8'
                },
                description='Activities or risk behaviors before the incident'
            ),
            
            'ICD 10': ColumnSpec(
                name='ICD 10',
                display_name='ICD-10 Code',
                data_type=ColumnType.TEXT,
                required=False,
                default_value=None,
                validation_rules={
                    ValidationRule.LENGTH: (0, 20),
                    ValidationRule.PATTERN: r'^[A-Z]\d{2}(\.\d{1,2})?$'
                },
                description='ICD-10 diagnosis code'
            ),
            
            'ผลการวินิจฉัย': ColumnSpec(
                name='ผลการวินิจฉัย',
                display_name='Diagnosis Result',
                data_type=ColumnType.TEXT,
                required=False,
                default_value=None,
                validation_rules={
                    ValidationRule.LENGTH: (0, 300),
                    ValidationRule.ENCODING: 'utf-8'
                },
                description='Diagnosis result or conclusion'
            ),
            
            'Unnamed: 35': ColumnSpec(
                name='Unnamed: 35',
                display_name='Unnamed Column 35',
                data_type=ColumnType.TEXT,
                required=False,
                default_value=None,
                validation_rules={
                    ValidationRule.LENGTH: (0, 200),
                    ValidationRule.ENCODING: 'utf-8'
                },
                description='Additional information column'
            ),
            
            'ข้อมูลอื่นๆ': ColumnSpec(
                name='ข้อมูลอื่นๆ',
                display_name='Other Information',
                data_type=ColumnType.TEXT,
                required=False,
                default_value=None,
                validation_rules={
                    ValidationRule.LENGTH: (0, 500),
                    ValidationRule.ENCODING: 'utf-8'
                },
                description='Other relevant information'
            ),
            
            'หมายเหตุ': ColumnSpec(
                name='หมายเหตุ',
                display_name='Remarks',
                data_type=ColumnType.TEXT,
                required=False,
                default_value=None,
                validation_rules={
                    ValidationRule.LENGTH: (0, 500),
                    ValidationRule.ENCODING: 'utf-8'
                },
                description='Remarks or additional notes'
            ),
            
            'ที่มาสื่อออนไลน์': ColumnSpec(
                name='ที่มาสื่อออนไลน์',
                display_name='Online Media Source',
                data_type=ColumnType.TEXT,
                required=False,
                default_value=None,
                validation_rules={
                    ValidationRule.LENGTH: (0, 300),
                    ValidationRule.ENCODING: 'utf-8'
                },
                description='Online media source or URL'
            )
        }
    
    @classmethod
    def validate_column_order(cls, columns: List[str]) -> Tuple[bool, List[str]]:
        """
        Validate that columns match the expected order
        
        Args:
            columns: List of column names to validate
            
        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []
        
        if len(columns) != len(cls.COLUMN_ORDER):
            errors.append(f"Expected {len(cls.COLUMN_ORDER)} columns, got {len(columns)}")
        
        for i, expected in enumerate(cls.COLUMN_ORDER):
            if i < len(columns):
                if columns[i] != expected:
                    errors.append(f"Column {i}: expected '{expected}', got '{columns[i]}'")
            else:
                errors.append(f"Missing column {i}: '{expected}'")
        
        return len(errors) == 0, errors
    
    @classmethod
    def get_column_types_mapping(cls) -> Dict[str, ColumnType]:
        """
        Get mapping of column names to their data types
        
        Returns:
            Dictionary mapping column names to ColumnType
        """
        schema = cls.get_schema_definition()
        return {name: spec.data_type for name, spec in schema.items()}
    
    @classmethod
    def get_empty_row(cls) -> Dict[str, Optional[str]]:
        """
        Get an empty row with all columns initialized to None or default values
        
        Returns:
            Dictionary with all column names and default/None values
        """
        schema = cls.get_schema_definition()
        empty_row = {}
        
        for col_name in cls.COLUMN_ORDER:
            if col_name in schema:
                spec = schema[col_name]
                empty_row[col_name] = spec.default_value
            else:
                empty_row[col_name] = None
        
        return empty_row
    
    @classmethod
    def get_columns_by_type(cls, data_type: ColumnType) -> List[str]:
        """
        Get list of column names by data type
        
        Args:
            data_type: The data type to filter by
            
        Returns:
            List of column names matching the data type
        """
        schema = cls.get_schema_definition()
        return [name for name, spec in schema.items() if spec.data_type == data_type]
    
    @classmethod
    def is_required_column(cls, column_name: str) -> bool:
        """
        Check if a column is required
        
        Args:
            column_name: Name of the column to check
            
        Returns:
            True if column is required, False otherwise
        """
        schema = cls.get_schema_definition()
        if column_name in schema:
            return schema[column_name].required
        return False