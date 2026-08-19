"""
Module: validation_engine_lg
Description: Input validation and data integrity checking across modules
Phase: 1
Location: /src/modules/logic/error_handling_lg/validation_engine_lg/
"""

# Standard library imports
import re
import json
from typing import Dict, Any, Optional, List, Union, Callable, Type, Tuple
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
import threading
from abc import ABC, abstractmethod

# Third-party imports
# None required for this module

# Local imports
from src.modules.logic.logging_infrastructure_lg.log_manager_lg.log_manager_lg import (
    LogManager, LogLevel, get_log_manager
)
# Note: ValidationEngine should not depend on AppStateManager to avoid circular dependencies


class ValidationSeverity(Enum):
    """Validation error severity levels."""
    CRITICAL = "CRITICAL"
    ERROR = "ERROR"
    WARNING = "WARNING"
    INFO = "INFO"


class ValidationType(Enum):
    """Types of validation checks."""
    DATA_TYPE = "DATA_TYPE"
    RANGE = "RANGE"
    FORMAT = "FORMAT"
    REQUIRED = "REQUIRED"
    CUSTOM = "CUSTOM"
    CONSTRAINT = "CONSTRAINT"
    INTEGRITY = "INTEGRITY"
    BUSINESS_RULE = "BUSINESS_RULE"


@dataclass
class ValidationError:
    """Validation error information."""
    field_name: str
    error_message: str
    severity: ValidationSeverity
    validation_type: ValidationType
    expected_value: Optional[Any] = None
    actual_value: Optional[Any] = None
    error_code: Optional[str] = None
    context: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert validation error to dictionary."""
        return {
            'field_name': self.field_name,
            'error_message': self.error_message,
            'severity': self.severity.value,
            'validation_type': self.validation_type.value,
            'expected_value': self.expected_value,
            'actual_value': self.actual_value,
            'error_code': self.error_code,
            'context': self.context
        }


@dataclass
class ValidationResult:
    """Result of validation operation."""
    is_valid: bool
    errors: List[ValidationError] = field(default_factory=list)
    warnings: List[ValidationError] = field(default_factory=list)
    validation_time: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def add_error(self, error: ValidationError) -> None:
        """Add validation error."""
        if error.severity in [ValidationSeverity.CRITICAL, ValidationSeverity.ERROR]:
            self.errors.append(error)
            self.is_valid = False
        else:
            self.warnings.append(error)
    
    def has_errors(self) -> bool:
        """Check if validation has errors."""
        return len(self.errors) > 0
    
    def has_warnings(self) -> bool:
        """Check if validation has warnings."""
        return len(self.warnings) > 0
    
    def get_error_summary(self) -> str:
        """Get summary of validation errors."""
        if not self.has_errors():
            return "No validation errors"
        
        error_count = len(self.errors)
        warning_count = len(self.warnings)
        
        summary = f"{error_count} error(s)"
        if warning_count > 0:
            summary += f", {warning_count} warning(s)"
        
        return summary
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert validation result to dictionary."""
        return {
            'is_valid': self.is_valid,
            'errors': [error.to_dict() for error in self.errors],
            'warnings': [error.to_dict() for error in self.warnings],
            'validation_time': self.validation_time.isoformat() if self.validation_time else None,
            'metadata': self.metadata,
            'error_summary': self.get_error_summary()
        }


class ValidationRule(ABC):
    """Abstract base class for validation rules."""
    
    def __init__(self, field_name: str, error_message: str, 
                 severity: ValidationSeverity = ValidationSeverity.ERROR):
        self.field_name = field_name
        self.error_message = error_message
        self.severity = severity
    
    @abstractmethod
    def validate(self, value: Any, context: Dict[str, Any] = None) -> Optional[ValidationError]:
        """Validate a value against this rule."""
        pass


class RequiredRule(ValidationRule):
    """Validation rule for required fields."""
    
    def validate(self, value: Any, context: Dict[str, Any] = None) -> Optional[ValidationError]:
        if value is None or (isinstance(value, str) and not value.strip()):
            return ValidationError(
                field_name=self.field_name,
                error_message=self.error_message,
                severity=self.severity,
                validation_type=ValidationType.REQUIRED,
                actual_value=value,
                context=context or {}
            )
        return None


class TypeRule(ValidationRule):
    """Validation rule for data types."""
    
    def __init__(self, field_name: str, expected_type: Type, error_message: str = None,
                 severity: ValidationSeverity = ValidationSeverity.ERROR):
        super().__init__(
            field_name, 
            error_message or f"{field_name} must be of type {expected_type.__name__}",
            severity
        )
        self.expected_type = expected_type
    
    def validate(self, value: Any, context: Dict[str, Any] = None) -> Optional[ValidationError]:
        if value is not None and not isinstance(value, self.expected_type):
            return ValidationError(
                field_name=self.field_name,
                error_message=self.error_message,
                severity=self.severity,
                validation_type=ValidationType.DATA_TYPE,
                expected_value=self.expected_type.__name__,
                actual_value=type(value).__name__,
                context=context or {}
            )
        return None


class RangeRule(ValidationRule):
    """Validation rule for numeric ranges."""
    
    def __init__(self, field_name: str, min_value: Optional[Union[int, float]] = None,
                 max_value: Optional[Union[int, float]] = None, error_message: str = None,
                 severity: ValidationSeverity = ValidationSeverity.ERROR):
        super().__init__(
            field_name,
            error_message or f"{field_name} must be between {min_value} and {max_value}",
            severity
        )
        self.min_value = min_value
        self.max_value = max_value
    
    def validate(self, value: Any, context: Dict[str, Any] = None) -> Optional[ValidationError]:
        if value is None:
            return None
        
        try:
            numeric_value = float(value)
            
            if self.min_value is not None and numeric_value < self.min_value:
                return ValidationError(
                    field_name=self.field_name,
                    error_message=f"{self.field_name} must be at least {self.min_value}",
                    severity=self.severity,
                    validation_type=ValidationType.RANGE,
                    expected_value=f">= {self.min_value}",
                    actual_value=numeric_value,
                    context=context or {}
                )
            
            if self.max_value is not None and numeric_value > self.max_value:
                return ValidationError(
                    field_name=self.field_name,
                    error_message=f"{self.field_name} must be at most {self.max_value}",
                    severity=self.severity,
                    validation_type=ValidationType.RANGE,
                    expected_value=f"<= {self.max_value}",
                    actual_value=numeric_value,
                    context=context or {}
                )
                
        except (ValueError, TypeError):
            return ValidationError(
                field_name=self.field_name,
                error_message=f"{self.field_name} must be a numeric value",
                severity=self.severity,
                validation_type=ValidationType.DATA_TYPE,
                actual_value=value,
                context=context or {}
            )
        
        return None


class FormatRule(ValidationRule):
    """Validation rule for format patterns."""
    
    def __init__(self, field_name: str, pattern: str, error_message: str = None,
                 severity: ValidationSeverity = ValidationSeverity.ERROR):
        super().__init__(
            field_name,
            error_message or f"{field_name} format is invalid",
            severity
        )
        self.pattern = pattern
        self.regex = re.compile(pattern)
    
    def validate(self, value: Any, context: Dict[str, Any] = None) -> Optional[ValidationError]:
        if value is None:
            return None
        
        if not isinstance(value, str):
            return ValidationError(
                field_name=self.field_name,
                error_message=f"{self.field_name} must be a string for format validation",
                severity=self.severity,
                validation_type=ValidationType.DATA_TYPE,
                actual_value=type(value).__name__,
                context=context or {}
            )
        
        if not self.regex.match(value):
            return ValidationError(
                field_name=self.field_name,
                error_message=self.error_message,
                severity=self.severity,
                validation_type=ValidationType.FORMAT,
                expected_value=self.pattern,
                actual_value=value,
                context=context or {}
            )
        
        return None


class CustomRule(ValidationRule):
    """Custom validation rule with user-defined function."""
    
    def __init__(self, field_name: str, validator_func: Callable[[Any, Dict[str, Any]], bool],
                 error_message: str, severity: ValidationSeverity = ValidationSeverity.ERROR):
        super().__init__(field_name, error_message, severity)
        self.validator_func = validator_func
    
    def validate(self, value: Any, context: Dict[str, Any] = None) -> Optional[ValidationError]:
        try:
            if not self.validator_func(value, context or {}):
                return ValidationError(
                    field_name=self.field_name,
                    error_message=self.error_message,
                    severity=self.severity,
                    validation_type=ValidationType.CUSTOM,
                    actual_value=value,
                    context=context or {}
                )
        except Exception as e:
            return ValidationError(
                field_name=self.field_name,
                error_message=f"Custom validation failed: {str(e)}",
                severity=ValidationSeverity.ERROR,
                validation_type=ValidationType.CUSTOM,
                actual_value=value,
                context=context or {}
            )
        
        return None


class ValidationEngine:
    """
    Input validation and data integrity checking across modules.

    This class provides comprehensive validation capabilities including data type
    checking, constraint validation, format validation, and business rule validation.
    """

    def __init__(self):
        """Initialize the validation engine."""
        self._log_manager = get_log_manager()
        self._logger = self._log_manager.get_logger("validation_engine")
        self._app_state = None  # Will be set by dependency injection

        # Validation state
        self._validation_schemas: Dict[str, List[ValidationRule]] = {}
        self._custom_validators: Dict[str, Callable] = {}
        self._validation_cache: Dict[str, ValidationResult] = {}
        self._lock = threading.RLock()

        # Configuration
        self._cache_enabled = True
        self._max_cache_size = 1000
        self._validation_timeout = 30  # seconds

        # Initialize built-in validators
        self._initialize_builtin_validators()

        self._logger.info("ValidationEngine initialized successfully")

    def register_schema(self, schema_name: str, rules: List[ValidationRule]) -> None:
        """
        Register a validation schema with rules.

        Args:
            schema_name: Name of the validation schema
            rules: List of validation rules
        """
        with self._lock:
            self._validation_schemas[schema_name] = rules

        self._logger.info(f"Validation schema registered: {schema_name} with {len(rules)} rules")

    def validate_data(self, data: Dict[str, Any], schema_name: str,
                     context: Optional[Dict[str, Any]] = None) -> ValidationResult:
        """
        Validate data against a registered schema.

        Args:
            data: Data to validate
            schema_name: Name of the validation schema to use
            context: Additional validation context

        Returns:
            ValidationResult with validation outcome
        """
        start_time = datetime.now(timezone.utc)

        try:
            # Check if schema exists
            with self._lock:
                if schema_name not in self._validation_schemas:
                    result = ValidationResult(is_valid=False)
                    result.add_error(ValidationError(
                        field_name="schema",
                        error_message=f"Validation schema '{schema_name}' not found",
                        severity=ValidationSeverity.ERROR,
                        validation_type=ValidationType.CONSTRAINT
                    ))
                    return result

                rules = self._validation_schemas[schema_name]

            # Check cache if enabled
            if self._cache_enabled:
                cache_key = self._generate_cache_key(data, schema_name, context)
                with self._lock:
                    if cache_key in self._validation_cache:
                        cached_result = self._validation_cache[cache_key]
                        self._logger.debug(f"Using cached validation result for schema: {schema_name}")
                        return cached_result

            # Perform validation
            result = ValidationResult(is_valid=True, validation_time=start_time)
            validation_context = context or {}

            # Apply all rules
            for rule in rules:
                field_value = data.get(rule.field_name)
                validation_error = rule.validate(field_value, validation_context)

                if validation_error:
                    result.add_error(validation_error)

            # Add metadata
            result.metadata = {
                'schema_name': schema_name,
                'rules_applied': len(rules),
                'validation_duration': (datetime.now(timezone.utc) - start_time).total_seconds(),
                'data_fields': list(data.keys())
            }

            # Cache result if enabled
            if self._cache_enabled:
                with self._lock:
                    self._validation_cache[cache_key] = result
                    self._cleanup_cache()

            # Log validation result
            self._log_validation_result(schema_name, result)

            return result

        except Exception as e:
            self._logger.error(f"Validation failed for schema {schema_name}: {e}")
            result = ValidationResult(is_valid=False)
            result.add_error(ValidationError(
                field_name="validation_engine",
                error_message=f"Validation engine error: {str(e)}",
                severity=ValidationSeverity.CRITICAL,
                validation_type=ValidationType.CONSTRAINT
            ))
            return result

    def validate_field(self, field_name: str, value: Any, rules: List[ValidationRule],
                      context: Optional[Dict[str, Any]] = None) -> ValidationResult:
        """
        Validate a single field against specific rules.

        Args:
            field_name: Name of the field being validated
            value: Value to validate
            rules: List of validation rules to apply
            context: Additional validation context

        Returns:
            ValidationResult with validation outcome
        """
        start_time = datetime.now(timezone.utc)
        result = ValidationResult(is_valid=True, validation_time=start_time)
        validation_context = context or {}

        try:
            for rule in rules:
                # Ensure rule applies to this field
                if rule.field_name != field_name:
                    continue

                validation_error = rule.validate(value, validation_context)
                if validation_error:
                    result.add_error(validation_error)

            result.metadata = {
                'field_name': field_name,
                'rules_applied': len([r for r in rules if r.field_name == field_name]),
                'validation_duration': (datetime.now(timezone.utc) - start_time).total_seconds()
            }

            return result

        except Exception as e:
            self._logger.error(f"Field validation failed for {field_name}: {e}")
            result.add_error(ValidationError(
                field_name=field_name,
                error_message=f"Field validation error: {str(e)}",
                severity=ValidationSeverity.ERROR,
                validation_type=ValidationType.CONSTRAINT
            ))
            return result

    def validate_file_path(self, file_path: Union[str, Path],
                          must_exist: bool = True,
                          allowed_extensions: Optional[List[str]] = None) -> ValidationResult:
        """
        Validate file path and properties.

        Args:
            file_path: Path to validate
            must_exist: Whether file must exist
            allowed_extensions: List of allowed file extensions

        Returns:
            ValidationResult with validation outcome
        """
        result = ValidationResult(is_valid=True)
        path_obj = Path(file_path) if isinstance(file_path, str) else file_path

        try:
            # Check if path exists
            if must_exist and not path_obj.exists():
                result.add_error(ValidationError(
                    field_name="file_path",
                    error_message=f"File does not exist: {file_path}",
                    severity=ValidationSeverity.ERROR,
                    validation_type=ValidationType.CONSTRAINT,
                    actual_value=str(file_path)
                ))

            # Check file extension
            if allowed_extensions and path_obj.suffix.lower() not in [ext.lower() for ext in allowed_extensions]:
                result.add_error(ValidationError(
                    field_name="file_extension",
                    error_message=f"File extension not allowed. Expected: {allowed_extensions}",
                    severity=ValidationSeverity.ERROR,
                    validation_type=ValidationType.FORMAT,
                    expected_value=allowed_extensions,
                    actual_value=path_obj.suffix
                ))

            # Check if it's a file (not directory)
            if path_obj.exists() and not path_obj.is_file():
                result.add_error(ValidationError(
                    field_name="file_type",
                    error_message=f"Path is not a file: {file_path}",
                    severity=ValidationSeverity.ERROR,
                    validation_type=ValidationType.CONSTRAINT,
                    actual_value="directory" if path_obj.is_dir() else "other"
                ))

            return result

        except Exception as e:
            result.add_error(ValidationError(
                field_name="file_path",
                error_message=f"File path validation error: {str(e)}",
                severity=ValidationSeverity.ERROR,
                validation_type=ValidationType.CONSTRAINT
            ))
            return result

    def validate_json_data(self, json_data: Union[str, Dict[str, Any]],
                          schema_name: Optional[str] = None) -> ValidationResult:
        """
        Validate JSON data structure and content.

        Args:
            json_data: JSON data to validate (string or dict)
            schema_name: Optional schema name for additional validation

        Returns:
            ValidationResult with validation outcome
        """
        result = ValidationResult(is_valid=True)

        try:
            # Parse JSON if string
            if isinstance(json_data, str):
                try:
                    parsed_data = json.loads(json_data)
                except json.JSONDecodeError as e:
                    result.add_error(ValidationError(
                        field_name="json_format",
                        error_message=f"Invalid JSON format: {str(e)}",
                        severity=ValidationSeverity.ERROR,
                        validation_type=ValidationType.FORMAT
                    ))
                    return result
            else:
                parsed_data = json_data

            # Validate against schema if provided
            if schema_name:
                schema_result = self.validate_data(parsed_data, schema_name)
                result.errors.extend(schema_result.errors)
                result.warnings.extend(schema_result.warnings)
                if schema_result.has_errors():
                    result.is_valid = False

            return result

        except Exception as e:
            result.add_error(ValidationError(
                field_name="json_validation",
                error_message=f"JSON validation error: {str(e)}",
                severity=ValidationSeverity.ERROR,
                validation_type=ValidationType.CONSTRAINT
            ))
            return result

    def _generate_cache_key(self, data: Dict[str, Any], schema_name: str,
                           context: Optional[Dict[str, Any]]) -> str:
        """Generate cache key for validation result."""
        import hashlib

        key_data = {
            'data': data,
            'schema': schema_name,
            'context': context or {}
        }

        key_string = json.dumps(key_data, sort_keys=True, default=str)
        return hashlib.md5(key_string.encode()).hexdigest()

    def _cleanup_cache(self) -> None:
        """Clean up validation cache if it exceeds max size."""
        if len(self._validation_cache) > self._max_cache_size:
            # Remove oldest entries (simple FIFO)
            excess_count = len(self._validation_cache) - self._max_cache_size
            keys_to_remove = list(self._validation_cache.keys())[:excess_count]

            for key in keys_to_remove:
                del self._validation_cache[key]

    def _log_validation_result(self, schema_name: str, result: ValidationResult) -> None:
        """Log validation result."""
        if result.has_errors():
            self._logger.warning(f"Validation failed for schema '{schema_name}': {result.get_error_summary()}")
        elif result.has_warnings():
            self._logger.info(f"Validation completed with warnings for schema '{schema_name}': {result.get_error_summary()}")
        else:
            self._logger.debug(f"Validation successful for schema '{schema_name}'")

    def _initialize_builtin_validators(self) -> None:
        """Initialize built-in validation schemas."""
        # Email validation schema
        email_rules = [
            RequiredRule("email", "Email is required"),
            FormatRule("email", r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', "Invalid email format")
        ]
        self.register_schema("email", email_rules)

        # File path validation schema
        file_path_rules = [
            RequiredRule("path", "File path is required"),
            TypeRule("path", str, "File path must be a string")
        ]
        self.register_schema("file_path", file_path_rules)

        # Training configuration validation schema
        training_config_rules = [
            RequiredRule("batch_size", "Batch size is required"),
            TypeRule("batch_size", int, "Batch size must be an integer"),
            RangeRule("batch_size", min_value=1, max_value=1024, error_message="Batch size must be between 1 and 1024"),

            RequiredRule("learning_rate", "Learning rate is required"),
            TypeRule("learning_rate", (int, float), "Learning rate must be numeric"),
            RangeRule("learning_rate", min_value=0.0001, max_value=1.0, error_message="Learning rate must be between 0.0001 and 1.0"),

            RequiredRule("epochs", "Number of epochs is required"),
            TypeRule("epochs", int, "Epochs must be an integer"),
            RangeRule("epochs", min_value=1, max_value=10000, error_message="Epochs must be between 1 and 10000")
        ]
        self.register_schema("training_config", training_config_rules)

        # Model configuration validation schema
        model_config_rules = [
            RequiredRule("model_name", "Model name is required"),
            TypeRule("model_name", str, "Model name must be a string"),
            FormatRule("model_name", r'^[a-zA-Z0-9_-]+$', "Model name can only contain letters, numbers, underscores, and hyphens"),

            TypeRule("hidden_size", int, "Hidden size must be an integer", ValidationSeverity.WARNING),
            RangeRule("hidden_size", min_value=64, max_value=8192, error_message="Hidden size should be between 64 and 8192", severity=ValidationSeverity.WARNING)
        ]
        self.register_schema("model_config", model_config_rules)

    def register_custom_validator(self, name: str, validator_func: Callable) -> None:
        """
        Register a custom validator function.

        Args:
            name: Name of the custom validator
            validator_func: Validation function
        """
        with self._lock:
            self._custom_validators[name] = validator_func

        self._logger.info(f"Custom validator registered: {name}")

    def create_custom_rule(self, field_name: str, validator_name: str,
                          error_message: str, severity: ValidationSeverity = ValidationSeverity.ERROR) -> CustomRule:
        """
        Create a custom validation rule using a registered validator.

        Args:
            field_name: Name of the field to validate
            validator_name: Name of the registered custom validator
            error_message: Error message for validation failure
            severity: Validation error severity

        Returns:
            CustomRule instance
        """
        with self._lock:
            if validator_name not in self._custom_validators:
                raise ValueError(f"Custom validator '{validator_name}' not found")

            validator_func = self._custom_validators[validator_name]

        return CustomRule(field_name, validator_func, error_message, severity)

    def get_validation_stats(self) -> Dict[str, Any]:
        """Get validation engine statistics."""
        with self._lock:
            return {
                'registered_schemas': len(self._validation_schemas),
                'custom_validators': len(self._custom_validators),
                'cache_size': len(self._validation_cache),
                'cache_enabled': self._cache_enabled,
                'schema_names': list(self._validation_schemas.keys()),
                'validator_names': list(self._custom_validators.keys())
            }

    def clear_cache(self) -> None:
        """Clear the validation cache."""
        with self._lock:
            self._validation_cache.clear()

        self._logger.info("Validation cache cleared")

    def remove_schema(self, schema_name: str) -> bool:
        """
        Remove a validation schema.

        Args:
            schema_name: Name of the schema to remove

        Returns:
            bool: True if schema was removed, False if not found
        """
        with self._lock:
            if schema_name in self._validation_schemas:
                del self._validation_schemas[schema_name]
                self._logger.info(f"Validation schema removed: {schema_name}")
                return True
            return False

    def get_schema_rules(self, schema_name: str) -> Optional[List[ValidationRule]]:
        """
        Get rules for a validation schema.

        Args:
            schema_name: Name of the schema

        Returns:
            List of validation rules or None if schema not found
        """
        with self._lock:
            return self._validation_schemas.get(schema_name)
