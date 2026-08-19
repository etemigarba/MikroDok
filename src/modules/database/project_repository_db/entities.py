"""
Module: entities
Description: Project repository entity models and data structures for database operations
Phase: 4
Location: /src/modules/database/project_repository_db/
"""

# Standard library imports
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Union


class ProjectStatus(Enum):
    """Project lifecycle status enumeration."""
    ACTIVE = "active"
    ARCHIVED = "archived"
    DELETED = "deleted"


class ProjectType(Enum):
    """Project type enumeration."""
    FINE_TUNING = "fine_tuning"
    RAG_TRAINING = "rag_training"
    CUSTOM_MODEL = "custom_model"
    INFERENCE_ONLY = "inference_only"


class SettingType(Enum):
    """Setting value type enumeration."""
    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    JSON = "json"
    LIST = "list"


class SettingCategory(Enum):
    """Setting category enumeration."""
    GENERAL = "general"
    TRAINING = "training"
    INFERENCE = "inference"
    PERFORMANCE = "performance"
    SECURITY = "security"
    UI = "ui"
    ADVANCED = "advanced"


@dataclass
class ProjectMetadata:
    """Project metadata container."""
    tags: List[str] = field(default_factory=list)
    category: Optional[str] = None
    priority: int = 0  # 0-10 scale
    estimated_duration_hours: Optional[float] = None
    complexity_score: Optional[float] = None  # 0.0-1.0 scale
    custom_fields: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON storage."""
        return {
            "tags": self.tags,
            "category": self.category,
            "priority": self.priority,
            "estimated_duration_hours": self.estimated_duration_hours,
            "complexity_score": self.complexity_score,
            "custom_fields": self.custom_fields
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ProjectMetadata':
        """Create from dictionary."""
        return cls(
            tags=data.get("tags", []),
            category=data.get("category"),
            priority=data.get("priority", 0),
            estimated_duration_hours=data.get("estimated_duration_hours"),
            complexity_score=data.get("complexity_score"),
            custom_fields=data.get("custom_fields", {})
        )


@dataclass
class ProjectSettings:
    """Project-specific configuration settings."""
    # Training settings
    max_epochs: int = 10
    batch_size: int = 8
    learning_rate: float = 0.0001
    model_architecture: str = "3B"
    quantization_type: str = "FP16"
    
    # Resource settings
    max_memory_gb: float = 8.0
    gpu_enabled: bool = True
    cpu_threads: int = 4
    
    # Data settings
    train_test_split: float = 0.8
    validation_split: float = 0.1
    random_seed: int = 42
    
    # Output settings
    output_directory: str = "./output"
    checkpoint_frequency: int = 100
    save_best_only: bool = True
    
    # Advanced settings
    gradient_accumulation_steps: int = 1
    warmup_steps: int = 100
    weight_decay: float = 0.01
    dropout_rate: float = 0.1
    
    # Custom settings
    custom_settings: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON storage."""
        return {
            "max_epochs": self.max_epochs,
            "batch_size": self.batch_size,
            "learning_rate": self.learning_rate,
            "model_architecture": self.model_architecture,
            "quantization_type": self.quantization_type,
            "max_memory_gb": self.max_memory_gb,
            "gpu_enabled": self.gpu_enabled,
            "cpu_threads": self.cpu_threads,
            "train_test_split": self.train_test_split,
            "validation_split": self.validation_split,
            "random_seed": self.random_seed,
            "output_directory": self.output_directory,
            "checkpoint_frequency": self.checkpoint_frequency,
            "save_best_only": self.save_best_only,
            "gradient_accumulation_steps": self.gradient_accumulation_steps,
            "warmup_steps": self.warmup_steps,
            "weight_decay": self.weight_decay,
            "dropout_rate": self.dropout_rate,
            "custom_settings": self.custom_settings
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ProjectSettings':
        """Create from dictionary."""
        return cls(
            max_epochs=data.get("max_epochs", 10),
            batch_size=data.get("batch_size", 8),
            learning_rate=data.get("learning_rate", 0.0001),
            model_architecture=data.get("model_architecture", "3B"),
            quantization_type=data.get("quantization_type", "FP16"),
            max_memory_gb=data.get("max_memory_gb", 8.0),
            gpu_enabled=data.get("gpu_enabled", True),
            cpu_threads=data.get("cpu_threads", 4),
            train_test_split=data.get("train_test_split", 0.8),
            validation_split=data.get("validation_split", 0.1),
            random_seed=data.get("random_seed", 42),
            output_directory=data.get("output_directory", "./output"),
            checkpoint_frequency=data.get("checkpoint_frequency", 100),
            save_best_only=data.get("save_best_only", True),
            gradient_accumulation_steps=data.get("gradient_accumulation_steps", 1),
            warmup_steps=data.get("warmup_steps", 100),
            weight_decay=data.get("weight_decay", 0.01),
            dropout_rate=data.get("dropout_rate", 0.1),
            custom_settings=data.get("custom_settings", {})
        )


@dataclass
class Project:
    """Project entity representing a machine learning project."""
    # Primary fields
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    description: str = ""
    project_type: ProjectType = ProjectType.FINE_TUNING
    status: ProjectStatus = ProjectStatus.ACTIVE
    
    # Timestamps
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    # Configuration
    settings: ProjectSettings = field(default_factory=ProjectSettings)
    metadata: ProjectMetadata = field(default_factory=ProjectMetadata)
    
    # File paths
    project_directory: Optional[str] = None
    data_directory: Optional[str] = None
    output_directory: Optional[str] = None
    
    # Statistics
    document_count: int = 0
    model_count: int = 0
    training_session_count: int = 0
    total_size_bytes: int = 0
    
    def __post_init__(self):
        """Post-initialization processing."""
        if not self.name:
            self.name = f"Project_{self.id[:8]}"
        
        # Ensure timestamps are timezone-aware
        if self.created_at.tzinfo is None:
            self.created_at = self.created_at.replace(tzinfo=timezone.utc)
        if self.updated_at.tzinfo is None:
            self.updated_at = self.updated_at.replace(tzinfo=timezone.utc)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for database storage."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "project_type": self.project_type.value,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "settings": self.settings.to_dict(),
            "metadata": self.metadata.to_dict(),
            "project_directory": self.project_directory,
            "data_directory": self.data_directory,
            "output_directory": self.output_directory,
            "document_count": self.document_count,
            "model_count": self.model_count,
            "training_session_count": self.training_session_count,
            "total_size_bytes": self.total_size_bytes
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Project':
        """Create from dictionary."""
        # Parse timestamps
        created_at = datetime.fromisoformat(data["created_at"])
        updated_at = datetime.fromisoformat(data["updated_at"])
        
        # Parse settings and metadata
        settings = ProjectSettings.from_dict(data.get("settings", {}))
        metadata = ProjectMetadata.from_dict(data.get("metadata", {}))
        
        return cls(
            id=data["id"],
            name=data["name"],
            description=data.get("description", ""),
            project_type=ProjectType(data.get("project_type", "fine_tuning")),
            status=ProjectStatus(data.get("status", "active")),
            created_at=created_at,
            updated_at=updated_at,
            settings=settings,
            metadata=metadata,
            project_directory=data.get("project_directory"),
            data_directory=data.get("data_directory"),
            output_directory=data.get("output_directory"),
            document_count=data.get("document_count", 0),
            model_count=data.get("model_count", 0),
            training_session_count=data.get("training_session_count", 0),
            total_size_bytes=data.get("total_size_bytes", 0)
        )
    
    def update_timestamp(self):
        """Update the modified timestamp."""
        self.updated_at = datetime.now(timezone.utc)
    
    def is_active(self) -> bool:
        """Check if project is active."""
        return self.status == ProjectStatus.ACTIVE
    
    def get_project_path(self) -> Optional[Path]:
        """Get project directory as Path object."""
        if self.project_directory:
            return Path(self.project_directory)
        return None


@dataclass
class ProjectSettingEntry:
    """Individual project setting entry."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    project_id: str = ""
    setting_key: str = ""
    setting_value: str = ""
    setting_type: SettingType = SettingType.STRING
    category: SettingCategory = SettingCategory.GENERAL
    description: Optional[str] = None
    is_user_defined: bool = True
    is_encrypted: bool = False
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self):
        """Post-initialization processing."""
        # Ensure timestamps are timezone-aware
        if self.created_at.tzinfo is None:
            self.created_at = self.created_at.replace(tzinfo=timezone.utc)
        if self.updated_at.tzinfo is None:
            self.updated_at = self.updated_at.replace(tzinfo=timezone.utc)

    def get_typed_value(self) -> Any:
        """Get the setting value with proper type conversion."""
        try:
            if self.setting_type == SettingType.INTEGER:
                return int(self.setting_value)
            elif self.setting_type == SettingType.FLOAT:
                return float(self.setting_value)
            elif self.setting_type == SettingType.BOOLEAN:
                return self.setting_value.lower() in ('true', '1', 'yes', 'on')
            elif self.setting_type == SettingType.JSON:
                return json.loads(self.setting_value)
            elif self.setting_type == SettingType.LIST:
                return json.loads(self.setting_value) if self.setting_value else []
            else:
                return self.setting_value
        except (ValueError, json.JSONDecodeError):
            return self.setting_value

    def set_typed_value(self, value: Any):
        """Set the setting value with proper type conversion."""
        if self.setting_type == SettingType.JSON or self.setting_type == SettingType.LIST:
            self.setting_value = json.dumps(value)
        else:
            self.setting_value = str(value)
        self.update_timestamp()

    def update_timestamp(self):
        """Update the modified timestamp."""
        self.updated_at = datetime.now(timezone.utc)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for database storage."""
        return {
            "id": self.id,
            "project_id": self.project_id,
            "setting_key": self.setting_key,
            "setting_value": self.setting_value,
            "setting_type": self.setting_type.value,
            "category": self.category.value,
            "description": self.description,
            "is_user_defined": self.is_user_defined,
            "is_encrypted": self.is_encrypted,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ProjectSettingEntry':
        """Create from dictionary."""
        created_at = datetime.fromisoformat(data["created_at"])
        updated_at = datetime.fromisoformat(data["updated_at"])

        return cls(
            id=data["id"],
            project_id=data["project_id"],
            setting_key=data["setting_key"],
            setting_value=data["setting_value"],
            setting_type=SettingType(data["setting_type"]),
            category=SettingCategory(data["category"]),
            description=data.get("description"),
            is_user_defined=data.get("is_user_defined", True),
            is_encrypted=data.get("is_encrypted", False),
            created_at=created_at,
            updated_at=updated_at
        )
