"""
Base validator module for type-specific column validation
"""

from dataclasses import dataclass
from typing import Any, Optional
from abc import ABC, abstractmethod


@dataclass
class ValidationResult:
    """Result of column validation"""
    is_valid: bool
    processed_value: Any
    error_message: Optional[str] = None
    confidence_score: Optional[float] = None


class BaseValidator(ABC):
    """Base class for all validators"""
    
    @abstractmethod
    def process(self, value: Any) -> ValidationResult:
        """Process and validate value"""
        pass


class NumericBaseValidator(BaseValidator):
    """Base class for numeric validators"""
    
    def __init__(self, min_value: Optional[float] = None, max_value: Optional[float] = None):
        self.min_value = min_value
        self.max_value = max_value
    
    @abstractmethod
    def process(self, value: Any) -> ValidationResult:
        """Process and validate numeric value"""
        pass