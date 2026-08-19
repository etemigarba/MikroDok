"""
Module: file_validator_lg
Description: Validates file integrity, size limits (10GB max), and format compatibility before processing
Phase: 3
Location: /src/modules/logic/document_ingestion_lg/file_validator_lg/
"""

# Standard library imports
import hashlib
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Set, Union

# Local imports
from src.modules.logic.error_handling_lg import ValidationError, ValidationResult
from src.modules.logic.logging_infrastructure_lg import get_logger
from src.modules.logic.document_ingestion_lg.format_detector_lg import (
    FormatDetector, DocumentFormat, FormatDetectionResult
)


class ValidationSeverity(Enum):
    """Validation severity levels."""
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class ValidationCategory(Enum):
    """Validation categories."""
    FILE_EXISTENCE = "FILE_EXISTENCE"
    FILE_SIZE = "FILE_SIZE"
    FILE_FORMAT = "FILE_FORMAT"
    FILE_INTEGRITY = "FILE_INTEGRITY"
    FILE_PERMISSIONS = "FILE_PERMISSIONS"
    FILE_CONTENT = "FILE_CONTENT"
    SECURITY = "SECURITY"


@dataclass
class FileValidationError:
    """File validation error details."""
    category: ValidationCategory
    severity: ValidationSeverity
    message: str
    field_name: str
    expected_value: Optional[str] = None
    actual_value: Optional[str] = None
    suggestion: Optional[str] = None


@dataclass
class FileValidationResult:
    """Result of file validation."""
    is_valid: bool
    file_path: str
    file_size: Optional[int] = None
    file_hash: Optional[str] = None
    format_detection: Optional[FormatDetectionResult] = None
    errors: List[FileValidationError] = field(default_factory=list)
    warnings: List[FileValidationError] = field(default_factory=list)
    metadata: Dict[str, str] = field(default_factory=dict)
    
    def has_errors(self) -> bool:
        """Check if validation has errors."""
        return len(self.errors) > 0
    
    def has_warnings(self) -> bool:
        """Check if validation has warnings."""
        return len(self.warnings) > 0
    
    def add_error(self, error: FileValidationError) -> None:
        """Add validation error."""
        if error.severity in [ValidationSeverity.ERROR, ValidationSeverity.CRITICAL]:
            self.errors.append(error)
            self.is_valid = False
        else:
            self.warnings.append(error)
    
    def get_error_summary(self) -> str:
        """Get summary of validation errors."""
        if not self.has_errors():
            return "No errors"
        
        error_counts = {}
        for error in self.errors:
            category = error.category.value
            error_counts[category] = error_counts.get(category, 0) + 1
        
        return f"Errors: {', '.join(f'{cat}({count})' for cat, count in error_counts.items())}"


class IFileValidator(ABC):
    """Interface for file validators."""
    
    @abstractmethod
    def validate_file(self, file_path: Union[str, Path], 
                     check_integrity: bool = True) -> FileValidationResult:
        """
        Validate file for processing.
        
        Args:
            file_path: Path to the file to validate
            check_integrity: Whether to perform integrity checks
            
        Returns:
            FileValidationResult with validation details
        """
        pass
    
    @abstractmethod
    def validate_file_size(self, file_path: Union[str, Path], 
                          max_size_bytes: Optional[int] = None) -> bool:
        """
        Validate file size against limits.
        
        Args:
            file_path: Path to the file
            max_size_bytes: Maximum allowed size in bytes
            
        Returns:
            True if size is valid, False otherwise
        """
        pass
    
    @abstractmethod
    def validate_file_format(self, file_path: Union[str, Path], 
                           allowed_formats: Optional[Set[DocumentFormat]] = None) -> bool:
        """
        Validate file format.
        
        Args:
            file_path: Path to the file
            allowed_formats: Set of allowed formats
            
        Returns:
            True if format is valid, False otherwise
        """
        pass
    
    @abstractmethod
    def calculate_file_hash(self, file_path: Union[str, Path], 
                           algorithm: str = 'sha256') -> Optional[str]:
        """
        Calculate file hash for integrity checking.
        
        Args:
            file_path: Path to the file
            algorithm: Hash algorithm to use
            
        Returns:
            File hash string or None if calculation fails
        """
        pass


class FileValidator(IFileValidator):
    """
    File validator for document processing pipeline.
    
    Validates files for:
    - Existence and accessibility
    - Size limits (default 10GB)
    - Format compatibility
    - File integrity
    - Security considerations
    """
    
    def __init__(self, max_file_size_bytes: int = 10 * 1024 * 1024 * 1024):  # 10GB default
        """
        Initialize file validator.
        
        Args:
            max_file_size_bytes: Maximum allowed file size in bytes
        """
        self._logger = get_logger(__name__)
        self._max_file_size = max_file_size_bytes
        self._format_detector = FormatDetector()
        
        # Supported formats for processing
        self._supported_formats = {
            DocumentFormat.PDF,
            DocumentFormat.DOCX,
            DocumentFormat.DOC,
            DocumentFormat.TXT,
            DocumentFormat.HTML,
            DocumentFormat.HTM,
            DocumentFormat.MARKDOWN
        }
        
        # Security: Blocked file extensions
        self._blocked_extensions = {
            '.exe', '.bat', '.cmd', '.com', '.scr', '.pif',
            '.vbs', '.js', '.jar', '.app', '.deb', '.rpm',
            '.dmg', '.pkg', '.msi', '.dll', '.so', '.dylib'
        }
        
        # Minimum file size (1 byte)
        self._min_file_size = 1
        
        self._logger.info(f"FileValidator initialized with max size: {self._max_file_size} bytes")

    def validate_file(self, file_path: Union[str, Path],
                     check_integrity: bool = True) -> FileValidationResult:
        """
        Comprehensive file validation for processing pipeline.

        Args:
            file_path: Path to the file to validate
            check_integrity: Whether to perform integrity checks

        Returns:
            FileValidationResult with validation details
        """
        path_obj = Path(file_path)
        result = FileValidationResult(
            is_valid=True,
            file_path=str(file_path)
        )

        try:
            # 1. Check file existence
            if not self._validate_file_existence(path_obj, result):
                return result

            # 2. Check file permissions
            self._validate_file_permissions(path_obj, result)

            # 3. Check file size
            file_size = self._validate_file_size_internal(path_obj, result)
            if file_size is not None:
                result.file_size = file_size

            # 4. Security validation
            self._validate_file_security(path_obj, result)

            # 5. Format detection and validation
            format_result = self._validate_file_format_internal(path_obj, result)
            if format_result:
                result.format_detection = format_result

            # 6. Integrity checks (if requested and file is accessible)
            if check_integrity and result.is_valid:
                file_hash = self._validate_file_integrity(path_obj, result)
                if file_hash:
                    result.file_hash = file_hash

            # 7. Content validation (basic checks)
            if result.is_valid:
                self._validate_file_content(path_obj, result)

            # Add metadata
            result.metadata = {
                'validator_version': '1.0.0',
                'validation_timestamp': str(path_obj.stat().st_mtime),
                'file_extension': path_obj.suffix.lower(),
                'validation_level': 'comprehensive' if check_integrity else 'basic'
            }

            self._logger.info(
                f"File validation completed for {file_path}: "
                f"valid={result.is_valid}, errors={len(result.errors)}, warnings={len(result.warnings)}"
            )

            return result

        except Exception as e:
            self._logger.error(f"File validation failed for {file_path}: {e}")
            result.add_error(FileValidationError(
                category=ValidationCategory.FILE_INTEGRITY,
                severity=ValidationSeverity.CRITICAL,
                message=f"Validation process failed: {str(e)}",
                field_name="validation_process"
            ))
            return result

    def validate_file_size(self, file_path: Union[str, Path],
                          max_size_bytes: Optional[int] = None) -> bool:
        """
        Validate file size against limits.

        Args:
            file_path: Path to the file
            max_size_bytes: Maximum allowed size in bytes (uses instance default if None)

        Returns:
            True if size is valid, False otherwise
        """
        try:
            path_obj = Path(file_path)
            if not path_obj.exists():
                return False

            file_size = path_obj.stat().st_size
            max_size = max_size_bytes or self._max_file_size

            return self._min_file_size <= file_size <= max_size

        except Exception as e:
            self._logger.error(f"File size validation failed for {file_path}: {e}")
            return False

    def validate_file_format(self, file_path: Union[str, Path],
                           allowed_formats: Optional[Set[DocumentFormat]] = None) -> bool:
        """
        Validate file format against allowed formats.

        Args:
            file_path: Path to the file
            allowed_formats: Set of allowed formats (uses supported formats if None)

        Returns:
            True if format is valid, False otherwise
        """
        try:
            allowed = allowed_formats or self._supported_formats
            detection_result = self._format_detector.detect_format(file_path)

            return (detection_result.is_valid and
                   detection_result.format_type in allowed)

        except Exception as e:
            self._logger.error(f"File format validation failed for {file_path}: {e}")
            return False

    def calculate_file_hash(self, file_path: Union[str, Path],
                           algorithm: str = 'sha256') -> Optional[str]:
        """
        Calculate file hash for integrity checking.

        Args:
            file_path: Path to the file
            algorithm: Hash algorithm to use (sha256, md5, sha1)

        Returns:
            File hash string or None if calculation fails
        """
        try:
            path_obj = Path(file_path)
            if not path_obj.exists():
                return None

            # Get hash function
            if algorithm.lower() == 'sha256':
                hash_func = hashlib.sha256()
            elif algorithm.lower() == 'md5':
                hash_func = hashlib.md5()
            elif algorithm.lower() == 'sha1':
                hash_func = hashlib.sha1()
            else:
                self._logger.error(f"Unsupported hash algorithm: {algorithm}")
                return None

            # Calculate hash in chunks to handle large files
            chunk_size = 8192
            with open(path_obj, 'rb') as f:
                while chunk := f.read(chunk_size):
                    hash_func.update(chunk)

            return hash_func.hexdigest()

        except Exception as e:
            self._logger.error(f"Hash calculation failed for {file_path}: {e}")
            return None

    def _validate_file_existence(self, file_path: Path, result: FileValidationResult) -> bool:
        """Validate file existence and accessibility."""
        if not file_path.exists():
            result.add_error(FileValidationError(
                category=ValidationCategory.FILE_EXISTENCE,
                severity=ValidationSeverity.CRITICAL,
                message=f"File does not exist: {file_path}",
                field_name="file_path",
                actual_value=str(file_path),
                suggestion="Verify the file path is correct and the file exists"
            ))
            return False

        if not file_path.is_file():
            result.add_error(FileValidationError(
                category=ValidationCategory.FILE_EXISTENCE,
                severity=ValidationSeverity.ERROR,
                message=f"Path is not a file: {file_path}",
                field_name="file_path",
                actual_value=str(file_path),
                suggestion="Ensure the path points to a file, not a directory"
            ))
            return False

        return True

    def _validate_file_permissions(self, file_path: Path, result: FileValidationResult) -> None:
        """Validate file permissions."""
        try:
            if not os.access(file_path, os.R_OK):
                result.add_error(FileValidationError(
                    category=ValidationCategory.FILE_PERMISSIONS,
                    severity=ValidationSeverity.ERROR,
                    message=f"File is not readable: {file_path}",
                    field_name="file_permissions",
                    suggestion="Check file permissions and ensure read access"
                ))
        except Exception as e:
            result.add_error(FileValidationError(
                category=ValidationCategory.FILE_PERMISSIONS,
                severity=ValidationSeverity.WARNING,
                message=f"Could not check file permissions: {e}",
                field_name="file_permissions"
            ))

    def _validate_file_size_internal(self, file_path: Path, result: FileValidationResult) -> Optional[int]:
        """Internal file size validation."""
        try:
            file_size = file_path.stat().st_size

            # Check minimum size
            if file_size < self._min_file_size:
                result.add_error(FileValidationError(
                    category=ValidationCategory.FILE_SIZE,
                    severity=ValidationSeverity.ERROR,
                    message=f"File is too small: {file_size} bytes",
                    field_name="file_size",
                    expected_value=f"At least {self._min_file_size} bytes",
                    actual_value=f"{file_size} bytes",
                    suggestion="Ensure the file contains data"
                ))

            # Check maximum size
            if file_size > self._max_file_size:
                result.add_error(FileValidationError(
                    category=ValidationCategory.FILE_SIZE,
                    severity=ValidationSeverity.ERROR,
                    message=f"File exceeds maximum size: {file_size} bytes",
                    field_name="file_size",
                    expected_value=f"Maximum {self._max_file_size} bytes",
                    actual_value=f"{file_size} bytes",
                    suggestion="Consider splitting large files or increasing size limits"
                ))

            # Warning for very large files
            warning_threshold = self._max_file_size * 0.8  # 80% of max size
            if file_size > warning_threshold:
                result.add_error(FileValidationError(
                    category=ValidationCategory.FILE_SIZE,
                    severity=ValidationSeverity.WARNING,
                    message=f"File is very large: {file_size} bytes",
                    field_name="file_size",
                    actual_value=f"{file_size} bytes",
                    suggestion="Large files may take longer to process"
                ))

            return file_size

        except Exception as e:
            result.add_error(FileValidationError(
                category=ValidationCategory.FILE_SIZE,
                severity=ValidationSeverity.ERROR,
                message=f"Could not determine file size: {e}",
                field_name="file_size"
            ))
            return None

    def _validate_file_security(self, file_path: Path, result: FileValidationResult) -> None:
        """Validate file security considerations."""
        extension = file_path.suffix.lower()

        # Check for blocked extensions
        if extension in self._blocked_extensions:
            result.add_error(FileValidationError(
                category=ValidationCategory.SECURITY,
                severity=ValidationSeverity.CRITICAL,
                message=f"File extension is blocked for security: {extension}",
                field_name="file_extension",
                actual_value=extension,
                suggestion="Only document files are allowed for processing"
            ))

        # Check for suspicious file names
        suspicious_patterns = ['..', '~', '$', '%']
        file_name = file_path.name.lower()
        for pattern in suspicious_patterns:
            if pattern in file_name:
                result.add_error(FileValidationError(
                    category=ValidationCategory.SECURITY,
                    severity=ValidationSeverity.WARNING,
                    message=f"File name contains suspicious pattern: {pattern}",
                    field_name="file_name",
                    actual_value=file_name,
                    suggestion="Consider renaming the file"
                ))
                break

    def _validate_file_format_internal(self, file_path: Path, result: FileValidationResult) -> Optional[FormatDetectionResult]:
        """Internal file format validation."""
        try:
            detection_result = self._format_detector.detect_format(file_path)

            # Check if format was detected
            if detection_result.format_type == DocumentFormat.UNKNOWN:
                result.add_error(FileValidationError(
                    category=ValidationCategory.FILE_FORMAT,
                    severity=ValidationSeverity.ERROR,
                    message="Could not determine file format",
                    field_name="file_format",
                    suggestion="Ensure the file is a supported document format"
                ))
                return detection_result

            # Check if format is supported
            if detection_result.format_type not in self._supported_formats:
                result.add_error(FileValidationError(
                    category=ValidationCategory.FILE_FORMAT,
                    severity=ValidationSeverity.ERROR,
                    message=f"Unsupported file format: {detection_result.format_type.value}",
                    field_name="file_format",
                    actual_value=detection_result.format_type.value,
                    expected_value=", ".join(f.value for f in self._supported_formats),
                    suggestion="Convert the file to a supported format"
                ))

            # Check detection confidence
            if detection_result.confidence < 0.5:
                result.add_error(FileValidationError(
                    category=ValidationCategory.FILE_FORMAT,
                    severity=ValidationSeverity.WARNING,
                    message=f"Low confidence in format detection: {detection_result.confidence:.2f}",
                    field_name="format_confidence",
                    actual_value=f"{detection_result.confidence:.2f}",
                    suggestion="Verify the file is not corrupted"
                ))

            # Include any format detection errors
            if detection_result.validation_errors:
                for error in detection_result.validation_errors:
                    result.add_error(FileValidationError(
                        category=ValidationCategory.FILE_FORMAT,
                        severity=ValidationSeverity.WARNING,
                        message=f"Format detection warning: {error.error_message}",
                        field_name="format_detection"
                    ))

            return detection_result

        except Exception as e:
            result.add_error(FileValidationError(
                category=ValidationCategory.FILE_FORMAT,
                severity=ValidationSeverity.ERROR,
                message=f"Format validation failed: {e}",
                field_name="file_format"
            ))
            return None

    def _validate_file_integrity(self, file_path: Path, result: FileValidationResult) -> Optional[str]:
        """Validate file integrity through hash calculation."""
        try:
            file_hash = self.calculate_file_hash(file_path)

            if not file_hash:
                result.add_error(FileValidationError(
                    category=ValidationCategory.FILE_INTEGRITY,
                    severity=ValidationSeverity.WARNING,
                    message="Could not calculate file hash",
                    field_name="file_hash",
                    suggestion="File may be corrupted or inaccessible"
                ))
                return None

            # Basic integrity check - ensure file can be read completely
            try:
                with open(file_path, 'rb') as f:
                    # Try to read the entire file in chunks
                    chunk_size = 8192
                    while f.read(chunk_size):
                        pass
            except Exception as e:
                result.add_error(FileValidationError(
                    category=ValidationCategory.FILE_INTEGRITY,
                    severity=ValidationSeverity.ERROR,
                    message=f"File integrity check failed: {e}",
                    field_name="file_integrity",
                    suggestion="File may be corrupted"
                ))

            return file_hash

        except Exception as e:
            result.add_error(FileValidationError(
                category=ValidationCategory.FILE_INTEGRITY,
                severity=ValidationSeverity.WARNING,
                message=f"Integrity validation failed: {e}",
                field_name="file_integrity"
            ))
            return None

    def _validate_file_content(self, file_path: Path, result: FileValidationResult) -> None:
        """Basic file content validation."""
        try:
            # Check if file appears to be binary or text
            with open(file_path, 'rb') as f:
                sample = f.read(1024)  # Read first 1KB

            # Check for null bytes (indicates binary content)
            null_bytes = sample.count(b'\x00')
            if null_bytes > len(sample) * 0.1:  # More than 10% null bytes
                # This is likely a binary file, which is expected for PDF, DOCX, etc.
                if result.format_detection and result.format_detection.format_type in [DocumentFormat.TXT, DocumentFormat.HTML, DocumentFormat.MARKDOWN]:
                    result.add_error(FileValidationError(
                        category=ValidationCategory.FILE_CONTENT,
                        severity=ValidationSeverity.WARNING,
                        message="Text file appears to contain binary data",
                        field_name="file_content",
                        suggestion="Verify the file format is correct"
                    ))

            # Check for extremely long lines (potential issue for text files)
            if result.format_detection and result.format_detection.format_type in [DocumentFormat.TXT, DocumentFormat.MARKDOWN]:
                try:
                    lines = sample.decode('utf-8', errors='ignore').split('\n')
                    max_line_length = max(len(line) for line in lines) if lines else 0
                    if max_line_length > 10000:  # Very long line
                        result.add_error(FileValidationError(
                            category=ValidationCategory.FILE_CONTENT,
                            severity=ValidationSeverity.WARNING,
                            message=f"Very long line detected: {max_line_length} characters",
                            field_name="line_length",
                            actual_value=f"{max_line_length} characters",
                            suggestion="Consider reformatting the text"
                        ))
                except UnicodeDecodeError:
                    # Expected for binary files
                    pass

        except Exception as e:
            result.add_error(FileValidationError(
                category=ValidationCategory.FILE_CONTENT,
                severity=ValidationSeverity.WARNING,
                message=f"Content validation failed: {e}",
                field_name="file_content"
            ))
