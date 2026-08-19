"""
Module: settings_validator_lg
Description: Validates user settings against schema, ensures configuration integrity, and provides default values
Phase: 1
Location: /src/modules/logic/configuration_manager_lg/settings_validator_lg/
"""

# Standard library imports
import json
from typing import Dict, Any, Optional, List, Union, Tuple, Callable
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
import threading
from abc import ABC, abstractmethod
import copy

# Third-party imports
# None required for this module

# Local imports
from src.modules.logic.logging_infrastructure_lg.log_manager_lg.log_manager_lg import (
    LogManager, LogLevel, get_log_manager
)
from src.modules.logic.app_state_lg.app_state_lg import AppStateManager
from src.modules.logic.error_handling_lg.validation_engine_lg.validation_engine_lg import (
    ValidationEngine, ValidationResult, ValidationError, ValidationSeverity, ValidationType
)


class SettingType(Enum):
    """Types of settings."""
    STRING = "STRING"
    INTEGER = "INTEGER"
    FLOAT = "FLOAT"
    BOOLEAN = "BOOLEAN"
    LIST = "LIST"
    DICT = "DICT"
    PATH = "PATH"
    EMAIL = "EMAIL"
    URL = "URL"
    COLOR = "COLOR"
    ENUM = "ENUM"


class SettingCategory(Enum):
    """Setting categories for organization."""
    GENERAL = "GENERAL"
    APPEARANCE = "APPEARANCE"
    PERFORMANCE = "PERFORMANCE"
    SECURITY = "SECURITY"
    ADVANCED = "ADVANCED"
    SYSTEM = "SYSTEM"
    USER_INTERFACE = "USER_INTERFACE"
    TRAINING = "TRAINING"
    INFERENCE = "INFERENCE"


@dataclass
class SettingConstraint:
    """Constraint definition for settings."""
    constraint_type: str
    value: Any
    error_message: str
    severity: ValidationSeverity = ValidationSeverity.ERROR
    
    def validate(self, setting_value: Any) -> Optional[ValidationError]:
        """Validate setting value against constraint."""
        if self.constraint_type == "min_value" and setting_value < self.value:
            return ValidationError(
                field_name="value",
                error_message=self.error_message,
                severity=self.severity,
                validation_type=ValidationType.RANGE,
                expected_value=f">= {self.value}",
                actual_value=setting_value
            )
        elif self.constraint_type == "max_value" and setting_value > self.value:
            return ValidationError(
                field_name="value",
                error_message=self.error_message,
                severity=self.severity,
                validation_type=ValidationType.RANGE,
                expected_value=f"<= {self.value}",
                actual_value=setting_value
            )
        elif self.constraint_type == "min_length" and len(str(setting_value)) < self.value:
            return ValidationError(
                field_name="value",
                error_message=self.error_message,
                severity=self.severity,
                validation_type=ValidationType.CONSTRAINT,
                expected_value=f"length >= {self.value}",
                actual_value=len(str(setting_value))
            )
        elif self.constraint_type == "max_length" and len(str(setting_value)) > self.value:
            return ValidationError(
                field_name="value",
                error_message=self.error_message,
                severity=self.severity,
                validation_type=ValidationType.CONSTRAINT,
                expected_value=f"length <= {self.value}",
                actual_value=len(str(setting_value))
            )
        elif self.constraint_type == "allowed_values" and setting_value not in self.value:
            return ValidationError(
                field_name="value",
                error_message=self.error_message,
                severity=self.severity,
                validation_type=ValidationType.CONSTRAINT,
                expected_value=f"one of {self.value}",
                actual_value=setting_value
            )
        elif self.constraint_type == "regex_pattern":
            import re
            if not re.match(self.value, str(setting_value)):
                return ValidationError(
                    field_name="value",
                    error_message=self.error_message,
                    severity=self.severity,
                    validation_type=ValidationType.FORMAT,
                    expected_value=f"pattern: {self.value}",
                    actual_value=setting_value
                )
        
        return None


@dataclass
class SettingDefinition:
    """Definition of a setting with validation rules."""
    key: str
    setting_type: SettingType
    category: SettingCategory
    default_value: Any
    description: str
    is_required: bool = False
    is_sensitive: bool = False
    is_readonly: bool = False
    constraints: List[SettingConstraint] = field(default_factory=list)
    allowed_values: Optional[List[Any]] = None
    depends_on: Optional[List[str]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def validate_value(self, value: Any) -> ValidationResult:
        """Validate a value against this setting definition."""
        result = ValidationResult(is_valid=True)
        
        # Type validation
        if not self._validate_type(value):
            result.add_error(ValidationError(
                field_name=self.key,
                error_message=f"Invalid type for {self.key}. Expected {self.setting_type.value}",
                severity=ValidationSeverity.ERROR,
                validation_type=ValidationType.DATA_TYPE,
                expected_value=self.setting_type.value,
                actual_value=type(value).__name__
            ))
            return result
        
        # Constraint validation
        for constraint in self.constraints:
            error = constraint.validate(value)
            if error:
                error.field_name = self.key
                result.add_error(error)
        
        # Allowed values validation
        if self.allowed_values and value not in self.allowed_values:
            result.add_error(ValidationError(
                field_name=self.key,
                error_message=f"Value not allowed for {self.key}",
                severity=ValidationSeverity.ERROR,
                validation_type=ValidationType.CONSTRAINT,
                expected_value=f"one of {self.allowed_values}",
                actual_value=value
            ))
        
        return result
    
    def _validate_type(self, value: Any) -> bool:
        """Validate value type."""
        if self.setting_type == SettingType.STRING:
            return isinstance(value, str)
        elif self.setting_type == SettingType.INTEGER:
            return isinstance(value, int)
        elif self.setting_type == SettingType.FLOAT:
            return isinstance(value, (int, float))
        elif self.setting_type == SettingType.BOOLEAN:
            return isinstance(value, bool)
        elif self.setting_type == SettingType.LIST:
            return isinstance(value, list)
        elif self.setting_type == SettingType.DICT:
            return isinstance(value, dict)
        elif self.setting_type == SettingType.PATH:
            return isinstance(value, (str, Path))
        elif self.setting_type == SettingType.EMAIL:
            return isinstance(value, str) and '@' in value
        elif self.setting_type == SettingType.URL:
            return isinstance(value, str) and ('http://' in value or 'https://' in value)
        elif self.setting_type == SettingType.COLOR:
            return isinstance(value, str) and (value.startswith('#') or value in ['red', 'green', 'blue', 'black', 'white'])
        elif self.setting_type == SettingType.ENUM:
            return value in self.allowed_values if self.allowed_values else True
        
        return True


@dataclass
class ValidationContext:
    """Context for settings validation."""
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    validation_mode: str = "strict"
    ignore_warnings: bool = False
    custom_validators: Dict[str, Callable] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SettingsValidationResult:
    """Result of settings validation."""
    is_valid: bool
    validated_settings: Dict[str, Any] = field(default_factory=dict)
    errors: List[ValidationError] = field(default_factory=list)
    warnings: List[ValidationError] = field(default_factory=list)
    applied_defaults: List[str] = field(default_factory=list)
    validation_time: Optional[datetime] = None
    context: Optional[ValidationContext] = None
    
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


class ISettingsValidator(ABC):
    """Interface for settings validators."""
    
    @abstractmethod
    def validate_settings(self, settings: Dict[str, Any], 
                         context: Optional[ValidationContext] = None) -> SettingsValidationResult:
        """Validate settings dictionary."""
        pass
    
    @abstractmethod
    def validate_setting(self, key: str, value: Any) -> ValidationResult:
        """Validate individual setting."""
        pass
    
    @abstractmethod
    def get_default_settings(self) -> Dict[str, Any]:
        """Get default settings dictionary."""
        pass
    
    @abstractmethod
    def register_setting_definition(self, definition: SettingDefinition) -> None:
        """Register setting definition."""
        pass


class SettingsValidator(ISettingsValidator):
    """
    Comprehensive settings validator with schema-based validation.

    Validates user settings against predefined schemas, ensures configuration
    integrity, provides default values, and integrates with the validation engine.
    """

    def __init__(self, app_state_manager: Optional[AppStateManager] = None):
        """Initialize the settings validator."""
        self._app_state_manager = app_state_manager or AppStateManager()
        self._log_manager = get_log_manager(self._app_state_manager)
        self._logger = self._log_manager.get_logger("settings_validator")
        self._validation_engine = ValidationEngine()

        # Settings definitions
        self._setting_definitions: Dict[str, SettingDefinition] = {}
        self._categories: Dict[SettingCategory, List[str]] = {}
        self._dependencies: Dict[str, List[str]] = {}
        self._lock = threading.RLock()

        # Validation cache
        self._validation_cache: Dict[str, SettingsValidationResult] = {}
        self._cache_enabled = True
        self._max_cache_size = 1000

        # Initialize default settings definitions
        self._initialize_default_settings()

        self._logger.info("SettingsValidator initialized successfully")

    def validate_settings(self, settings: Dict[str, Any],
                         context: Optional[ValidationContext] = None) -> SettingsValidationResult:
        """
        Validate complete settings dictionary against schema.

        Args:
            settings: Settings dictionary to validate
            context: Optional validation context

        Returns:
            SettingsValidationResult with validation outcome
        """
        start_time = datetime.now(timezone.utc)
        result = SettingsValidationResult(is_valid=True, context=context)

        try:
            with self._lock:
                # Check cache if enabled
                cache_key = self._generate_cache_key(settings, context)
                if self._cache_enabled and cache_key in self._validation_cache:
                    cached_result = self._validation_cache[cache_key]
                    self._logger.debug(f"Using cached validation result for settings")
                    return cached_result

                # Apply defaults for missing settings
                validated_settings = self._apply_default_values(settings, result)

                # Validate each setting
                for key, value in validated_settings.items():
                    if key in self._setting_definitions:
                        setting_result = self.validate_setting(key, value)
                        if not setting_result.is_valid:
                            for error in setting_result.errors:
                                result.add_error(error)
                        for warning in setting_result.warnings:
                            result.add_error(warning)
                    else:
                        # Unknown setting - add warning
                        result.add_error(ValidationError(
                            field_name=key,
                            error_message=f"Unknown setting: {key}",
                            severity=ValidationSeverity.WARNING,
                            validation_type=ValidationType.CONSTRAINT
                        ))

                # Validate required settings
                self._validate_required_settings(validated_settings, result)

                # Validate dependencies
                self._validate_dependencies(validated_settings, result)

                # Apply custom validators if provided
                if context and context.custom_validators:
                    self._apply_custom_validators(validated_settings, context, result)

                result.validated_settings = validated_settings
                result.validation_time = start_time

                # Cache result if validation was successful
                if self._cache_enabled and result.is_valid:
                    self._cache_validation_result(cache_key, result)

                self._logger.debug(f"Settings validation completed: {result.is_valid}")

        except Exception as e:
            self._logger.error(f"Settings validation failed: {str(e)}")
            result.is_valid = False
            result.add_error(ValidationError(
                field_name="settings",
                error_message=f"Validation failed: {str(e)}",
                severity=ValidationSeverity.ERROR,
                validation_type=ValidationType.INTEGRITY
            ))

        return result

    def validate_setting(self, key: str, value: Any) -> ValidationResult:
        """
        Validate individual setting value.

        Args:
            key: Setting key
            value: Setting value to validate

        Returns:
            ValidationResult with validation outcome
        """
        try:
            if key not in self._setting_definitions:
                result = ValidationResult(is_valid=False)
                result.add_error(ValidationError(
                    field_name=key,
                    error_message=f"Unknown setting: {key}",
                    severity=ValidationSeverity.WARNING,
                    validation_type=ValidationType.CONSTRAINT
                ))
                return result

            definition = self._setting_definitions[key]
            return definition.validate_value(value)

        except Exception as e:
            self._logger.error(f"Setting validation failed for {key}: {str(e)}")
            result = ValidationResult(is_valid=False)
            result.add_error(ValidationError(
                field_name=key,
                error_message=f"Validation error: {str(e)}",
                severity=ValidationSeverity.ERROR,
                validation_type=ValidationType.INTEGRITY
            ))
            return result

    def get_default_settings(self) -> Dict[str, Any]:
        """
        Get dictionary of all default settings.

        Returns:
            Dictionary with default setting values
        """
        with self._lock:
            defaults = {}
            for key, definition in self._setting_definitions.items():
                defaults[key] = definition.default_value
            return defaults

    def register_setting_definition(self, definition: SettingDefinition) -> None:
        """
        Register a setting definition.

        Args:
            definition: Setting definition to register
        """
        with self._lock:
            self._setting_definitions[definition.key] = definition

            # Update category mapping
            if definition.category not in self._categories:
                self._categories[definition.category] = []
            self._categories[definition.category].append(definition.key)

            # Update dependencies
            if definition.depends_on:
                self._dependencies[definition.key] = definition.depends_on

            # Clear validation cache
            self._validation_cache.clear()

            self._logger.debug(f"Setting definition registered: {definition.key}")

    def get_setting_definition(self, key: str) -> Optional[SettingDefinition]:
        """
        Get setting definition by key.

        Args:
            key: Setting key

        Returns:
            SettingDefinition or None if not found
        """
        with self._lock:
            return self._setting_definitions.get(key)

    def get_settings_by_category(self, category: SettingCategory) -> List[str]:
        """
        Get setting keys by category.

        Args:
            category: Setting category

        Returns:
            List of setting keys in the category
        """
        with self._lock:
            return self._categories.get(category, [])

    def get_all_categories(self) -> List[SettingCategory]:
        """
        Get all setting categories.

        Returns:
            List of all setting categories
        """
        with self._lock:
            return list(self._categories.keys())

    def _initialize_default_settings(self) -> None:
        """Initialize default settings definitions."""
        # General settings
        self.register_setting_definition(SettingDefinition(
            key="app_name",
            setting_type=SettingType.STRING,
            category=SettingCategory.GENERAL,
            default_value="MikroDok",
            description="Application name",
            is_readonly=True
        ))

        self.register_setting_definition(SettingDefinition(
            key="app_version",
            setting_type=SettingType.STRING,
            category=SettingCategory.GENERAL,
            default_value="1.0.0",
            description="Application version",
            is_readonly=True
        ))

        self.register_setting_definition(SettingDefinition(
            key="language",
            setting_type=SettingType.ENUM,
            category=SettingCategory.GENERAL,
            default_value="en",
            description="Application language",
            allowed_values=["en", "es", "fr", "de", "it", "pt", "ru", "zh", "ja", "ko"]
        ))

        # Appearance settings
        self.register_setting_definition(SettingDefinition(
            key="theme",
            setting_type=SettingType.ENUM,
            category=SettingCategory.APPEARANCE,
            default_value="dark",
            description="Application theme",
            allowed_values=["light", "dark", "auto"]
        ))

        self.register_setting_definition(SettingDefinition(
            key="font_size",
            setting_type=SettingType.INTEGER,
            category=SettingCategory.APPEARANCE,
            default_value=12,
            description="Font size in pixels",
            constraints=[
                SettingConstraint("min_value", 8, "Font size must be at least 8px"),
                SettingConstraint("max_value", 24, "Font size must be at most 24px")
            ]
        ))

        self.register_setting_definition(SettingDefinition(
            key="window_width",
            setting_type=SettingType.INTEGER,
            category=SettingCategory.APPEARANCE,
            default_value=1200,
            description="Default window width",
            constraints=[
                SettingConstraint("min_value", 800, "Window width must be at least 800px"),
                SettingConstraint("max_value", 3840, "Window width must be at most 3840px")
            ]
        ))

        self.register_setting_definition(SettingDefinition(
            key="window_height",
            setting_type=SettingType.INTEGER,
            category=SettingCategory.APPEARANCE,
            default_value=800,
            description="Default window height",
            constraints=[
                SettingConstraint("min_value", 600, "Window height must be at least 600px"),
                SettingConstraint("max_value", 2160, "Window height must be at most 2160px")
            ]
        ))

        # Performance settings
        self.register_setting_definition(SettingDefinition(
            key="max_memory_usage",
            setting_type=SettingType.STRING,
            category=SettingCategory.PERFORMANCE,
            default_value="8GB",
            description="Maximum memory usage",
            constraints=[
                SettingConstraint("regex_pattern", r'^\d+[KMGT]?B$', "Memory format must be like '8GB', '512MB', etc.")
            ]
        ))

        self.register_setting_definition(SettingDefinition(
            key="gpu_enabled",
            setting_type=SettingType.BOOLEAN,
            category=SettingCategory.PERFORMANCE,
            default_value=True,
            description="Enable GPU acceleration"
        ))

        self.register_setting_definition(SettingDefinition(
            key="cpu_threads",
            setting_type=SettingType.INTEGER,
            category=SettingCategory.PERFORMANCE,
            default_value=0,  # 0 means auto-detect
            description="Number of CPU threads to use (0 for auto)",
            constraints=[
                SettingConstraint("min_value", 0, "CPU threads must be 0 or positive"),
                SettingConstraint("max_value", 64, "CPU threads must be at most 64")
            ]
        ))

        # System settings
        self.register_setting_definition(SettingDefinition(
            key="debug_mode",
            setting_type=SettingType.BOOLEAN,
            category=SettingCategory.SYSTEM,
            default_value=False,
            description="Enable debug mode"
        ))

        self.register_setting_definition(SettingDefinition(
            key="log_level",
            setting_type=SettingType.ENUM,
            category=SettingCategory.SYSTEM,
            default_value="INFO",
            description="Logging level",
            allowed_values=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        ))

        self.register_setting_definition(SettingDefinition(
            key="data_directory",
            setting_type=SettingType.PATH,
            category=SettingCategory.SYSTEM,
            default_value="./data",
            description="Data storage directory",
            is_required=True
        ))

        self.register_setting_definition(SettingDefinition(
            key="temp_directory",
            setting_type=SettingType.PATH,
            category=SettingCategory.SYSTEM,
            default_value="./temp",
            description="Temporary files directory",
            is_required=True
        ))

        # Training settings
        self.register_setting_definition(SettingDefinition(
            key="default_batch_size",
            setting_type=SettingType.INTEGER,
            category=SettingCategory.TRAINING,
            default_value=32,
            description="Default training batch size",
            constraints=[
                SettingConstraint("min_value", 1, "Batch size must be at least 1"),
                SettingConstraint("max_value", 1024, "Batch size must be at most 1024")
            ]
        ))

        self.register_setting_definition(SettingDefinition(
            key="default_learning_rate",
            setting_type=SettingType.FLOAT,
            category=SettingCategory.TRAINING,
            default_value=0.001,
            description="Default learning rate",
            constraints=[
                SettingConstraint("min_value", 0.0001, "Learning rate must be at least 0.0001"),
                SettingConstraint("max_value", 1.0, "Learning rate must be at most 1.0")
            ]
        ))

        # Security settings
        self.register_setting_definition(SettingDefinition(
            key="backup_enabled",
            setting_type=SettingType.BOOLEAN,
            category=SettingCategory.SECURITY,
            default_value=True,
            description="Enable automatic backups"
        ))

        self.register_setting_definition(SettingDefinition(
            key="encryption_enabled",
            setting_type=SettingType.BOOLEAN,
            category=SettingCategory.SECURITY,
            default_value=False,
            description="Enable data encryption"
        ))

        self._logger.debug("Default settings definitions initialized")

    def _apply_default_values(self, settings: Dict[str, Any],
                             result: SettingsValidationResult) -> Dict[str, Any]:
        """Apply default values for missing settings."""
        validated_settings = settings.copy()

        for key, definition in self._setting_definitions.items():
            if key not in validated_settings:
                validated_settings[key] = definition.default_value
                result.applied_defaults.append(key)

        return validated_settings

    def _validate_required_settings(self, settings: Dict[str, Any],
                                   result: SettingsValidationResult) -> None:
        """Validate that all required settings are present."""
        for key, definition in self._setting_definitions.items():
            if definition.is_required and key not in settings:
                result.add_error(ValidationError(
                    field_name=key,
                    error_message=f"Required setting missing: {key}",
                    severity=ValidationSeverity.ERROR,
                    validation_type=ValidationType.REQUIRED
                ))

    def _validate_dependencies(self, settings: Dict[str, Any],
                              result: SettingsValidationResult) -> None:
        """Validate setting dependencies."""
        for key, dependencies in self._dependencies.items():
            if key in settings:
                for dependency in dependencies:
                    if dependency not in settings:
                        result.add_error(ValidationError(
                            field_name=key,
                            error_message=f"Setting {key} requires {dependency} to be set",
                            severity=ValidationSeverity.ERROR,
                            validation_type=ValidationType.CONSTRAINT
                        ))

    def _apply_custom_validators(self, settings: Dict[str, Any],
                                context: ValidationContext,
                                result: SettingsValidationResult) -> None:
        """Apply custom validators from context."""
        for validator_name, validator_func in context.custom_validators.items():
            try:
                validator_result = validator_func(settings)
                if isinstance(validator_result, ValidationResult):
                    for error in validator_result.errors:
                        result.add_error(error)
                    for warning in validator_result.warnings:
                        result.add_error(warning)
            except Exception as e:
                self._logger.error(f"Custom validator {validator_name} failed: {str(e)}")
                result.add_error(ValidationError(
                    field_name="custom_validation",
                    error_message=f"Custom validator {validator_name} failed: {str(e)}",
                    severity=ValidationSeverity.WARNING,
                    validation_type=ValidationType.CUSTOM
                ))

    def _generate_cache_key(self, settings: Dict[str, Any],
                           context: Optional[ValidationContext]) -> str:
        """Generate cache key for validation result."""
        import hashlib

        # Create deterministic string representation
        settings_str = json.dumps(settings, sort_keys=True)
        context_str = ""
        if context:
            context_dict = {
                'user_id': context.user_id,
                'session_id': context.session_id,
                'validation_mode': context.validation_mode,
                'ignore_warnings': context.ignore_warnings
            }
            context_str = json.dumps(context_dict, sort_keys=True)

        combined_str = f"{settings_str}|{context_str}"
        return hashlib.md5(combined_str.encode()).hexdigest()

    def _cache_validation_result(self, cache_key: str,
                                result: SettingsValidationResult) -> None:
        """Cache validation result."""
        if len(self._validation_cache) >= self._max_cache_size:
            # Remove oldest entry
            oldest_key = next(iter(self._validation_cache))
            del self._validation_cache[oldest_key]

        # Store copy to avoid mutation
        cached_result = copy.deepcopy(result)
        self._validation_cache[cache_key] = cached_result


# Factory function for easy instantiation
def create_settings_validator(app_state_manager: Optional[AppStateManager] = None) -> SettingsValidator:
    """
    Create a settings validator instance.

    Args:
        app_state_manager: Optional app state manager instance

    Returns:
        SettingsValidator instance
    """
    return SettingsValidator(app_state_manager)
