"""
Module: config_loader_lg
Description: Loads and validates application configuration from multiple sources with environment-specific overrides
Phase: 1
Location: /src/modules/logic/configuration_manager_lg/config_loader_lg/
"""

# Standard library imports
import os
import json
import yaml
from typing import Dict, Any, Optional, List, Union, Tuple
from enum import Enum
from dataclasses import dataclass, field
from pathlib import Path
import threading
from abc import ABC, abstractmethod
import argparse
import sys

# Third-party imports
# None required for this module

# Local imports
from src.modules.logic.logging_infrastructure_lg.log_manager_lg.log_manager_lg import (
    LogManager, LogLevel, get_log_manager
)
from src.modules.logic.app_state_lg.app_state_lg import AppState
from src.modules.logic.error_handling_lg.validation_engine_lg.validation_engine_lg import (
    ValidationEngine, ValidationResult, ValidationError, ValidationSeverity
)


class ConfigurationSource(Enum):
    """Configuration source types."""
    FILE = "FILE"
    ENVIRONMENT = "ENVIRONMENT"
    COMMAND_LINE = "COMMAND_LINE"
    DEFAULT = "DEFAULT"
    OVERRIDE = "OVERRIDE"


class ConfigurationFormat(Enum):
    """Supported configuration file formats."""
    JSON = "JSON"
    YAML = "YAML"
    INI = "INI"
    TOML = "TOML"


@dataclass
class ConfigurationEntry:
    """Configuration entry with metadata."""
    key: str
    value: Any
    source: ConfigurationSource
    priority: int = 0
    is_sensitive: bool = False
    description: Optional[str] = None
    validation_rules: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        """Post-initialization processing."""
        if self.is_sensitive and isinstance(self.value, str):
            # Mark sensitive values for secure handling
            self._original_value = self.value
            self.value = "*" * len(self.value) if len(self.value) > 0 else ""


@dataclass
class ConfigurationSchema:
    """Configuration schema definition."""
    required_keys: List[str] = field(default_factory=list)
    optional_keys: List[str] = field(default_factory=list)
    default_values: Dict[str, Any] = field(default_factory=dict)
    validation_rules: Dict[str, List[str]] = field(default_factory=dict)
    sensitive_keys: List[str] = field(default_factory=list)
    environment_mappings: Dict[str, str] = field(default_factory=dict)


@dataclass
class LoadResult:
    """Result of configuration loading operation."""
    success: bool
    configuration: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    sources_loaded: List[ConfigurationSource] = field(default_factory=list)
    load_time: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class IConfigurationLoader(ABC):
    """Interface for configuration loaders."""
    
    @abstractmethod
    def load_configuration(self, source_path: Optional[Path] = None) -> LoadResult:
        """Load configuration from source."""
        pass
    
    @abstractmethod
    def validate_configuration(self, config: Dict[str, Any]) -> ValidationResult:
        """Validate configuration against schema."""
        pass
    
    @abstractmethod
    def merge_configurations(self, configs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Merge multiple configuration dictionaries."""
        pass


class ConfigurationLoader(IConfigurationLoader):
    """
    Comprehensive configuration loader supporting multiple sources and formats.
    
    Loads configuration from files, environment variables, and command-line arguments
    with proper validation, merging, and environment-specific overrides.
    """
    
    def __init__(self, app_state_manager: Optional[Any] = None):
        """Initialize the configuration loader."""
        self._app_state_manager = app_state_manager
        self._log_manager = get_log_manager()
        self._logger = self._log_manager.get_logger("config_loader")
        self._validation_engine = ValidationEngine()
        
        # Configuration state
        self._loaded_configurations: Dict[ConfigurationSource, Dict[str, Any]] = {}
        self._merged_configuration: Dict[str, Any] = {}
        self._configuration_entries: Dict[str, ConfigurationEntry] = {}
        self._lock = threading.RLock()
        
        # Configuration schema
        self._schema = self._initialize_default_schema()
        
        # Source priorities (higher number = higher priority)
        self._source_priorities = {
            ConfigurationSource.DEFAULT: 0,
            ConfigurationSource.FILE: 10,
            ConfigurationSource.ENVIRONMENT: 20,
            ConfigurationSource.COMMAND_LINE: 30,
            ConfigurationSource.OVERRIDE: 40
        }
        
        # Supported file formats
        self._format_loaders = {
            ConfigurationFormat.JSON: self._load_json_file,
            ConfigurationFormat.YAML: self._load_yaml_file
        }
        
        self._logger.info("ConfigurationLoader initialized successfully")
    
    def load_configuration(self, source_path: Optional[Path] = None) -> LoadResult:
        """
        Load configuration from multiple sources with proper merging.
        
        Args:
            source_path: Optional path to configuration file
            
        Returns:
            LoadResult with merged configuration and metadata
        """
        start_time = self._get_current_time()
        result = LoadResult(success=False)  # Will be set to True if successful
        
        try:
            with self._lock:
                # Clear previous state
                self._loaded_configurations.clear()
                self._configuration_entries.clear()
                
                # Load from different sources in priority order
                self._load_default_configuration(result)
                
                if source_path:
                    self._load_file_configuration(source_path, result)
                else:
                    self._load_default_file_configuration(result)
                
                self._load_environment_configuration(result)
                self._load_command_line_configuration(result)
                
                # Merge all configurations
                self._merged_configuration = self._merge_all_configurations()
                
                # Validate merged configuration
                validation_result = self.validate_configuration(self._merged_configuration)
                if not validation_result.is_valid:
                    result.errors.extend([error.error_message for error in validation_result.errors])
                    result.success = False
                else:
                    result.configuration = self._merged_configuration.copy()
                    result.success = True
                
                result.load_time = self._get_current_time() - start_time
                result.metadata = {
                    'total_entries': len(self._configuration_entries),
                    'sources_count': len(self._loaded_configurations),
                    'validation_passed': validation_result.is_valid
                }
                
                self._logger.info(f"Configuration loaded successfully from {len(result.sources_loaded)} sources")
                
        except Exception as e:
            self._logger.error(f"Failed to load configuration: {str(e)}")
            result.success = False
            result.errors.append(f"Configuration loading failed: {str(e)}")
        
        return result
    
    def validate_configuration(self, config: Dict[str, Any]) -> ValidationResult:
        """
        Validate configuration against schema.
        
        Args:
            config: Configuration dictionary to validate
            
        Returns:
            ValidationResult with validation outcome
        """
        try:
            # Use validation engine with configuration schema
            return self._validation_engine.validate_data(config, "application_config")
            
        except Exception as e:
            self._logger.error(f"Configuration validation failed: {str(e)}")
            result = ValidationResult(is_valid=False)
            result.add_error(ValidationError(
                field_name="configuration",
                error_message=f"Validation failed: {str(e)}",
                severity=ValidationSeverity.ERROR,
                validation_type="INTEGRITY"
            ))
            return result
    
    def merge_configurations(self, configs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Merge multiple configuration dictionaries with priority handling.
        
        Args:
            configs: List of configuration dictionaries to merge
            
        Returns:
            Merged configuration dictionary
        """
        merged = {}
        
        for config in configs:
            merged.update(config)
        
        return merged

    def get_configuration_value(self, key: str, default: Any = None) -> Any:
        """
        Get configuration value by key.

        Args:
            key: Configuration key
            default: Default value if key not found

        Returns:
            Configuration value or default
        """
        with self._lock:
            return self._merged_configuration.get(key, default)

    def set_configuration_override(self, key: str, value: Any) -> None:
        """
        Set configuration override value.

        Args:
            key: Configuration key
            value: Override value
        """
        with self._lock:
            if ConfigurationSource.OVERRIDE not in self._loaded_configurations:
                self._loaded_configurations[ConfigurationSource.OVERRIDE] = {}

            self._loaded_configurations[ConfigurationSource.OVERRIDE][key] = value

            # Create configuration entry
            entry = ConfigurationEntry(
                key=key,
                value=value,
                source=ConfigurationSource.OVERRIDE,
                priority=self._source_priorities[ConfigurationSource.OVERRIDE]
            )
            self._configuration_entries[key] = entry

            # Re-merge configurations
            self._merged_configuration = self._merge_all_configurations()

            self._logger.debug(f"Configuration override set: {key}")

    def get_configuration_sources(self) -> Dict[str, List[str]]:
        """
        Get configuration sources and their keys.

        Returns:
            Dictionary mapping source names to key lists
        """
        with self._lock:
            sources = {}
            for source, config in self._loaded_configurations.items():
                sources[source.value] = list(config.keys())
            return sources

    def _initialize_default_schema(self) -> ConfigurationSchema:
        """Initialize default configuration schema."""
        schema = ConfigurationSchema()

        # Required configuration keys
        schema.required_keys = [
            "app_name",
            "app_version",
            "log_level",
            "data_directory",
            "temp_directory"
        ]

        # Optional configuration keys
        schema.optional_keys = [
            "debug_mode",
            "safe_mode",
            "offline_mode",
            "max_memory_usage",
            "gpu_enabled",
            "backup_enabled",
            "theme",
            "language"
        ]

        # Default values
        schema.default_values = {
            "app_name": "MikroDok",
            "app_version": "1.0.0",
            "log_level": "INFO",
            "debug_mode": False,
            "safe_mode": False,
            "offline_mode": True,
            "max_memory_usage": "8GB",
            "gpu_enabled": True,
            "backup_enabled": True,
            "theme": "dark",
            "language": "en",
            "data_directory": "./data",
            "temp_directory": "./temp"
        }

        # Environment variable mappings
        schema.environment_mappings = {
            "debug_mode": "MIKRODOK_DEBUG",
            "log_level": "MIKRODOK_LOG_LEVEL",
            "data_directory": "MIKRODOK_DATA_DIR",
            "temp_directory": "MIKRODOK_TEMP_DIR",
            "max_memory_usage": "MIKRODOK_MAX_MEMORY",
            "gpu_enabled": "MIKRODOK_GPU_ENABLED"
        }

        # Sensitive keys (values will be masked in logs)
        schema.sensitive_keys = [
            "api_key",
            "secret_key",
            "password",
            "token"
        ]

        # Register validation schema
        self._register_validation_schema()

        return schema

    def _register_validation_schema(self) -> None:
        """Register configuration validation schema with validation engine."""
        from src.modules.logic.error_handling_lg.validation_engine_lg.validation_engine_lg import (
            RequiredRule, TypeRule, RangeRule, FormatRule
        )

        config_rules = [
            # Required fields
            RequiredRule("app_name", "Application name is required"),
            TypeRule("app_name", str, "Application name must be a string"),

            RequiredRule("app_version", "Application version is required"),
            TypeRule("app_version", str, "Application version must be a string"),

            RequiredRule("log_level", "Log level is required"),
            TypeRule("log_level", str, "Log level must be a string"),

            RequiredRule("data_directory", "Data directory is required"),
            TypeRule("data_directory", str, "Data directory must be a string"),

            RequiredRule("temp_directory", "Temp directory is required"),
            TypeRule("temp_directory", str, "Temp directory must be a string"),

            # Optional fields with validation
            TypeRule("debug_mode", bool, "Debug mode must be a boolean"),
            TypeRule("safe_mode", bool, "Safe mode must be a boolean"),
            TypeRule("offline_mode", bool, "Offline mode must be a boolean"),
            TypeRule("gpu_enabled", bool, "GPU enabled must be a boolean"),
            TypeRule("backup_enabled", bool, "Backup enabled must be a boolean"),
            TypeRule("theme", str, "Theme must be a string"),
            TypeRule("language", str, "Language must be a string")
        ]

        self._validation_engine.register_schema("application_config", config_rules)

    def _load_default_configuration(self, result: LoadResult) -> None:
        """Load default configuration values."""
        try:
            default_config = self._schema.default_values.copy()
            self._loaded_configurations[ConfigurationSource.DEFAULT] = default_config
            result.sources_loaded.append(ConfigurationSource.DEFAULT)

            # Create configuration entries
            for key, value in default_config.items():
                entry = ConfigurationEntry(
                    key=key,
                    value=value,
                    source=ConfigurationSource.DEFAULT,
                    priority=self._source_priorities[ConfigurationSource.DEFAULT],
                    description=f"Default value for {key}"
                )
                self._configuration_entries[key] = entry

            self._logger.debug(f"Loaded {len(default_config)} default configuration values")

        except Exception as e:
            self._logger.error(f"Failed to load default configuration: {str(e)}")
            result.errors.append(f"Default configuration loading failed: {str(e)}")

    def _load_file_configuration(self, file_path: Path, result: LoadResult) -> None:
        """Load configuration from file."""
        try:
            if not file_path.exists():
                self._logger.warning(f"Configuration file not found: {file_path}")
                result.warnings.append(f"Configuration file not found: {file_path}")
                return

            # Determine file format
            format_type = self._detect_file_format(file_path)
            if format_type not in self._format_loaders:
                raise ValueError(f"Unsupported configuration file format: {format_type}")

            # Load configuration
            config = self._format_loaders[format_type](file_path)
            self._loaded_configurations[ConfigurationSource.FILE] = config
            result.sources_loaded.append(ConfigurationSource.FILE)

            # Create configuration entries
            for key, value in config.items():
                entry = ConfigurationEntry(
                    key=key,
                    value=value,
                    source=ConfigurationSource.FILE,
                    priority=self._source_priorities[ConfigurationSource.FILE],
                    is_sensitive=key in self._schema.sensitive_keys,
                    description=f"Loaded from file: {file_path}"
                )
                self._configuration_entries[key] = entry

            self._logger.info(f"Loaded configuration from file: {file_path}")

        except Exception as e:
            self._logger.error(f"Failed to load configuration file {file_path}: {str(e)}")
            result.errors.append(f"File configuration loading failed: {str(e)}")

    def _load_default_file_configuration(self, result: LoadResult) -> None:
        """Load configuration from default file locations."""
        default_paths = [
            Path("config.json"),
            Path("config.yaml"),
            Path("mikrodok.json"),
            Path("mikrodok.yaml"),
            Path("./config/config.json"),
            Path("./config/config.yaml")
        ]

        for path in default_paths:
            if path.exists():
                self._load_file_configuration(path, result)
                break

    def _load_environment_configuration(self, result: LoadResult) -> None:
        """Load configuration from environment variables."""
        try:
            env_config = {}

            # Load mapped environment variables
            for config_key, env_var in self._schema.environment_mappings.items():
                env_value = os.environ.get(env_var)
                if env_value is not None:
                    # Convert string values to appropriate types
                    converted_value = self._convert_environment_value(env_value, config_key)
                    env_config[config_key] = converted_value

            # Load any MIKRODOK_ prefixed environment variables
            for env_var, env_value in os.environ.items():
                if env_var.startswith("MIKRODOK_") and env_var not in self._schema.environment_mappings.values():
                    config_key = env_var.replace("MIKRODOK_", "").lower()
                    converted_value = self._convert_environment_value(env_value, config_key)
                    env_config[config_key] = converted_value

            if env_config:
                self._loaded_configurations[ConfigurationSource.ENVIRONMENT] = env_config
                result.sources_loaded.append(ConfigurationSource.ENVIRONMENT)

                # Create configuration entries
                for key, value in env_config.items():
                    entry = ConfigurationEntry(
                        key=key,
                        value=value,
                        source=ConfigurationSource.ENVIRONMENT,
                        priority=self._source_priorities[ConfigurationSource.ENVIRONMENT],
                        is_sensitive=key in self._schema.sensitive_keys,
                        description=f"Loaded from environment variable"
                    )
                    self._configuration_entries[key] = entry

                self._logger.debug(f"Loaded {len(env_config)} environment configuration values")

        except Exception as e:
            self._logger.error(f"Failed to load environment configuration: {str(e)}")
            result.errors.append(f"Environment configuration loading failed: {str(e)}")

    def _load_command_line_configuration(self, result: LoadResult) -> None:
        """Load configuration from command line arguments."""
        try:
            # Parse command line arguments
            parser = argparse.ArgumentParser(add_help=False)

            # Add common configuration arguments
            parser.add_argument('--debug', action='store_true', help='Enable debug mode')
            parser.add_argument('--safe-mode', action='store_true', help='Enable safe mode')
            parser.add_argument('--log-level', choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'], help='Set log level')
            parser.add_argument('--data-dir', help='Data directory path')
            parser.add_argument('--temp-dir', help='Temporary directory path')
            parser.add_argument('--config', help='Configuration file path')

            # Parse known arguments (ignore unknown ones)
            args, _ = parser.parse_known_args()

            # Convert to configuration dictionary
            cmd_config = {}
            if args.debug:
                cmd_config['debug_mode'] = True
            if args.safe_mode:
                cmd_config['safe_mode'] = True
            if args.log_level:
                cmd_config['log_level'] = args.log_level
            if args.data_dir:
                cmd_config['data_directory'] = args.data_dir
            if args.temp_dir:
                cmd_config['temp_directory'] = args.temp_dir

            if cmd_config:
                self._loaded_configurations[ConfigurationSource.COMMAND_LINE] = cmd_config
                result.sources_loaded.append(ConfigurationSource.COMMAND_LINE)

                # Create configuration entries
                for key, value in cmd_config.items():
                    entry = ConfigurationEntry(
                        key=key,
                        value=value,
                        source=ConfigurationSource.COMMAND_LINE,
                        priority=self._source_priorities[ConfigurationSource.COMMAND_LINE],
                        description=f"Loaded from command line argument"
                    )
                    self._configuration_entries[key] = entry

                self._logger.debug(f"Loaded {len(cmd_config)} command line configuration values")

        except Exception as e:
            self._logger.error(f"Failed to load command line configuration: {str(e)}")
            result.errors.append(f"Command line configuration loading failed: {str(e)}")

    def _merge_all_configurations(self) -> Dict[str, Any]:
        """Merge all loaded configurations by priority."""
        merged = {}

        # Sort sources by priority
        sorted_sources = sorted(
            self._loaded_configurations.items(),
            key=lambda x: self._source_priorities[x[0]]
        )

        # Merge configurations in priority order
        for source, config in sorted_sources:
            merged.update(config)

        return merged

    def _detect_file_format(self, file_path: Path) -> ConfigurationFormat:
        """Detect configuration file format from extension."""
        suffix = file_path.suffix.lower()

        if suffix in ['.json']:
            return ConfigurationFormat.JSON
        elif suffix in ['.yaml', '.yml']:
            return ConfigurationFormat.YAML
        elif suffix in ['.ini', '.cfg']:
            return ConfigurationFormat.INI
        elif suffix in ['.toml']:
            return ConfigurationFormat.TOML
        else:
            # Default to JSON
            return ConfigurationFormat.JSON

    def _load_json_file(self, file_path: Path) -> Dict[str, Any]:
        """Load configuration from JSON file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in configuration file: {str(e)}")
        except Exception as e:
            raise ValueError(f"Failed to read JSON configuration file: {str(e)}")

    def _load_yaml_file(self, file_path: Path) -> Dict[str, Any]:
        """Load configuration from YAML file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f) or {}
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML in configuration file: {str(e)}")
        except Exception as e:
            raise ValueError(f"Failed to read YAML configuration file: {str(e)}")

    def _convert_environment_value(self, value: str, key: str) -> Any:
        """Convert environment variable string to appropriate type."""
        # Boolean conversion
        if value.lower() in ['true', '1', 'yes', 'on']:
            return True
        elif value.lower() in ['false', '0', 'no', 'off']:
            return False

        # Numeric conversion
        try:
            if '.' in value:
                return float(value)
            else:
                return int(value)
        except ValueError:
            pass

        # JSON conversion for complex types
        if value.startswith('{') or value.startswith('['):
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                pass

        # Return as string
        return value

    def _get_current_time(self) -> float:
        """Get current time in seconds."""
        import time
        return time.time()


# Factory function for easy instantiation
def create_configuration_loader(app_state_manager: Optional[Any] = None) -> ConfigurationLoader:
    """
    Create a configuration loader instance.

    Args:
        app_state_manager: Optional app state manager instance

    Returns:
        ConfigurationLoader instance
    """
    return ConfigurationLoader(app_state_manager)
