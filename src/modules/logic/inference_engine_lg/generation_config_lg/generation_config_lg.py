"""
Module: generation_config_lg
Description: Manages text generation configurations including temperature, top-k, top-p, and other generation parameters
Phase: 4
Location: /src/modules/logic/inference_engine_lg/generation_config_lg/generation_config_lg.py
"""

# Standard library imports
import json
import threading
from pathlib import Path
from typing import Dict, Any, Optional, List
import logging
from dataclasses import asdict, replace
from copy import deepcopy

# Third-party imports
# None required for this module

# Local imports
from src.modules.logic.inference_engine_lg.base_interfaces import (
    IGenerationConfig,
    GenerationConfig,
    GenerationStrategy,
    InferenceMetrics
)
from src.modules.logic.error_handling_lg.validation_engine_lg.validation_engine_lg import (
    ValidationEngine, ValidationError, ValidationResult, ValidationSeverity, ValidationType
)
from src.modules.logic.logging_infrastructure_lg.log_manager_lg.log_manager_lg import (
    LogManager, LogLevel, get_log_manager
)


class ConfigurationError(Exception):
    """Exception raised when configuration operations fail."""
    pass


class GenerationConfigManager(IGenerationConfig):
    """
    Production-ready generation configuration manager.
    
    Manages text generation configurations with preset management,
    validation, and persistence capabilities.
    """
    
    def __init__(self, config_dir: Optional[Path] = None):
        """
        Initialize generation config manager.
        
        Args:
            config_dir: Optional directory for storing configuration presets
        """
        self._logger = get_log_manager().get_logger(__name__)
        self._config_dir = config_dir or Path("configs/generation")
        self._presets: Dict[str, GenerationConfig] = {}
        self._config_lock = threading.RLock()
        self._validator = ValidationEngine()
        self._metrics = InferenceMetrics()
        
        # Ensure config directory exists
        self._config_dir.mkdir(parents=True, exist_ok=True)
        
        # Load default presets
        self._load_default_presets()
        
        # Load saved presets
        self._load_saved_presets()
        
        self._logger.info(f"Generation config manager initialized with {len(self._presets)} presets")
    
    def create_config(self, **kwargs) -> GenerationConfig:
        """
        Create a generation configuration.
        
        Args:
            **kwargs: Configuration parameters
            
        Returns:
            GenerationConfig object
        """
        try:
            # Create config with defaults and overrides
            config = GenerationConfig(**kwargs)
            
            # Validate the configuration
            validation_result = self.validate_config(config)
            if not validation_result.is_valid:
                error_msg = f"Invalid configuration: {validation_result.get_error_summary()}"
                self._logger.error(error_msg)
                raise ValueError(error_msg)
            
            self._logger.debug(f"Created generation config with strategy: {config.strategy.value}")
            return config
            
        except Exception as e:
            self._logger.error(f"Failed to create config: {str(e)}")
            raise ConfigurationError(f"Configuration creation failed: {str(e)}")
    
    def validate_config(self, config: GenerationConfig) -> List[str]:
        """
        Validate generation configuration.
        
        Args:
            config: Configuration to validate
            
        Returns:
            List of validation errors (empty if valid)
        """
        errors = []
        
        try:
            # Validate max_new_tokens
            if config.max_new_tokens <= 0:
                errors.append("max_new_tokens must be positive")
            
            if config.min_new_tokens < 0:
                errors.append("min_new_tokens must be non-negative")
            
            if config.min_new_tokens >= config.max_new_tokens:
                errors.append("min_new_tokens must be less than max_new_tokens")
            
            # Validate temperature
            if config.temperature <= 0:
                errors.append("temperature must be positive")
            
            # Validate top_k
            if config.top_k <= 0:
                errors.append("top_k must be positive")
            
            # Validate top_p
            if config.top_p <= 0 or config.top_p > 1:
                errors.append("top_p must be between 0 and 1")
            
            # Validate repetition_penalty
            if config.repetition_penalty <= 0:
                errors.append("repetition_penalty must be positive")
            
            # Validate length_penalty
            if config.length_penalty <= 0:
                errors.append("length_penalty must be positive")
            
            # Validate num_beams
            if config.num_beams <= 0:
                errors.append("num_beams must be positive")
            
            # Validate num_return_sequences
            if config.num_return_sequences <= 0:
                errors.append("num_return_sequences must be positive")
            
            if config.num_return_sequences > config.num_beams:
                errors.append("num_return_sequences cannot exceed num_beams")
            
            # Validate strategy-specific parameters
            if config.strategy == GenerationStrategy.BEAM_SEARCH and config.num_beams == 1:
                errors.append("beam_search strategy requires num_beams > 1")
            
            if config.strategy == GenerationStrategy.SAMPLING and not config.do_sample:
                errors.append("sampling strategy requires do_sample=True")
            
            # Validate stopping criteria
            if config.custom_stopping_criteria:
                for criterion in config.custom_stopping_criteria:
                    if not isinstance(criterion, str) or not criterion.strip():
                        errors.append("custom_stopping_criteria must contain non-empty strings")
            
        except Exception as e:
            errors.append(f"Validation error: {str(e)}")
        
        if errors:
            self._logger.warning(f"Configuration validation failed: {errors}")
        
        return errors
    
    def get_preset_configs(self) -> Dict[str, GenerationConfig]:
        """
        Get predefined configuration presets.
        
        Returns:
            Dictionary of preset configurations
        """
        with self._config_lock:
            return deepcopy(self._presets)
    
    def save_config(self, name: str, config: GenerationConfig) -> bool:
        """
        Save a configuration preset.
        
        Args:
            name: Preset name
            config: Configuration to save
            
        Returns:
            True if saved successfully
        """
        try:
            # Validate configuration first
            validation_errors = self.validate_config(config)
            if validation_errors:
                error_msg = f"Cannot save invalid configuration: {validation_errors}"
                self._logger.error(error_msg)
                raise ValueError(error_msg)
            
            with self._config_lock:
                # Save to memory
                self._presets[name] = deepcopy(config)
                
                # Save to file
                config_file = self._config_dir / f"{name}.json"
                config_dict = asdict(config)
                
                # Convert enums to strings for JSON serialization
                config_dict['strategy'] = config.strategy.value
                
                with open(config_file, 'w', encoding='utf-8') as f:
                    json.dump(config_dict, f, indent=2, ensure_ascii=False)
                
                self._logger.info(f"Saved configuration preset: {name}")
                return True
                
        except Exception as e:
            self._logger.error(f"Failed to save config {name}: {str(e)}")
            return False
    
    def load_config(self, name: str) -> Optional[GenerationConfig]:
        """
        Load a configuration preset.
        
        Args:
            name: Preset name
            
        Returns:
            GenerationConfig if found, None otherwise
        """
        try:
            with self._config_lock:
                if name in self._presets:
                    return deepcopy(self._presets[name])
                
                # Try to load from file
                config_file = self._config_dir / f"{name}.json"
                if config_file.exists():
                    with open(config_file, 'r', encoding='utf-8') as f:
                        config_dict = json.load(f)
                    
                    # Convert strategy string back to enum
                    if 'strategy' in config_dict:
                        config_dict['strategy'] = GenerationStrategy(config_dict['strategy'])
                    
                    config = GenerationConfig(**config_dict)
                    
                    # Validate loaded config
                    validation_errors = self.validate_config(config)
                    if validation_errors:
                        self._logger.error(f"Loaded config {name} is invalid: {validation_errors}")
                        return None
                    
                    # Cache in memory
                    self._presets[name] = config
                    
                    self._logger.info(f"Loaded configuration preset: {name}")
                    return deepcopy(config)
                
                self._logger.warning(f"Configuration preset not found: {name}")
                return None
                
        except Exception as e:
            self._logger.error(f"Failed to load config {name}: {str(e)}")
            return None
    
    def delete_config(self, name: str) -> bool:
        """
        Delete a configuration preset.
        
        Args:
            name: Preset name
            
        Returns:
            True if deleted successfully
        """
        try:
            with self._config_lock:
                # Remove from memory
                if name in self._presets:
                    del self._presets[name]
                
                # Remove file
                config_file = self._config_dir / f"{name}.json"
                if config_file.exists():
                    config_file.unlink()
                
                self._logger.info(f"Deleted configuration preset: {name}")
                return True
                
        except Exception as e:
            self._logger.error(f"Failed to delete config {name}: {str(e)}")
            return False
    
    def list_presets(self) -> List[str]:
        """
        Get list of available preset names.
        
        Returns:
            List of preset names
        """
        with self._config_lock:
            return list(self._presets.keys())
    
    def update_config(self, name: str, **kwargs) -> bool:
        """
        Update an existing configuration preset.
        
        Args:
            name: Preset name
            **kwargs: Parameters to update
            
        Returns:
            True if updated successfully
        """
        try:
            config = self.load_config(name)
            if not config:
                self._logger.error(f"Configuration preset not found: {name}")
                return False
            
            # Update configuration
            updated_config = replace(config, **kwargs)
            
            # Save updated configuration
            return self.save_config(name, updated_config)
            
        except Exception as e:
            self._logger.error(f"Failed to update config {name}: {str(e)}")
            return False
    
    def _load_default_presets(self) -> None:
        """Load default configuration presets."""
        try:
            # Conservative preset
            conservative = GenerationConfig(
                max_new_tokens=256,
                temperature=0.7,
                top_k=40,
                top_p=0.9,
                repetition_penalty=1.1,
                do_sample=True,
                strategy=GenerationStrategy.SAMPLING
            )
            self._presets['conservative'] = conservative
            
            # Creative preset
            creative = GenerationConfig(
                max_new_tokens=512,
                temperature=1.2,
                top_k=50,
                top_p=0.95,
                repetition_penalty=1.05,
                do_sample=True,
                strategy=GenerationStrategy.SAMPLING
            )
            self._presets['creative'] = creative
            
            # Precise preset
            precise = GenerationConfig(
                max_new_tokens=256,
                temperature=0.1,
                top_k=10,
                top_p=0.8,
                repetition_penalty=1.2,
                do_sample=True,
                strategy=GenerationStrategy.SAMPLING
            )
            self._presets['precise'] = precise
            
            # Beam search preset
            beam_search = GenerationConfig(
                max_new_tokens=256,
                num_beams=4,
                early_stopping=True,
                do_sample=False,
                strategy=GenerationStrategy.BEAM_SEARCH
            )
            self._presets['beam_search'] = beam_search
            
            self._logger.info("Loaded default configuration presets")
            
        except Exception as e:
            self._logger.error(f"Failed to load default presets: {str(e)}")
    
    def _load_saved_presets(self) -> None:
        """Load saved configuration presets from files."""
        try:
            if not self._config_dir.exists():
                return
            
            for config_file in self._config_dir.glob("*.json"):
                preset_name = config_file.stem
                
                # Skip if already loaded (default presets)
                if preset_name in self._presets:
                    continue
                
                try:
                    config = self.load_config(preset_name)
                    if config:
                        self._logger.debug(f"Loaded saved preset: {preset_name}")
                except Exception as e:
                    self._logger.warning(f"Failed to load preset {preset_name}: {str(e)}")
            
        except Exception as e:
            self._logger.error(f"Failed to load saved presets: {str(e)}")
    
    def get_metrics(self) -> InferenceMetrics:
        """
        Get generation config manager metrics.
        
        Returns:
            InferenceMetrics with current statistics
        """
        try:
            with self._config_lock:
                self._metrics.metadata = {
                    'total_presets': len(self._presets),
                    'preset_names': list(self._presets.keys()),
                    'config_dir': str(self._config_dir)
                }
                
                return self._metrics
                
        except Exception as e:
            self._logger.error(f"Failed to get metrics: {str(e)}")
            return InferenceMetrics()
    
    async def shutdown(self) -> bool:
        """
        Shutdown generation config manager.
        
        Returns:
            True if shutdown successful
        """
        try:
            with self._config_lock:
                self._presets.clear()
            
            self._logger.info("Generation config manager shutdown completed")
            return True
            
        except Exception as e:
            self._logger.error(f"Failed to shutdown generation config manager: {str(e)}")
            return False
