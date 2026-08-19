"""
Module: log_manager_lg
Description: Centralized logging management with configurable levels and outputs for MikroDok application.
            Provides thread-safe logging infrastructure with multiple output destinations, 
            structured logging, performance monitoring, and integration with the application state system.
Phase: 1
Location: /src/modules/logic/logging_infrastructure_lg/log_manager_lg/log_manager_lg.py
"""

# Standard library imports
import os
import sys
import json
import logging
import logging.handlers
from pathlib import Path
from typing import Dict, Any, Optional, List, Union, Callable
from enum import Enum
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
import threading
import traceback
from contextlib import contextmanager

# Third-party imports
# None required for this module

# Local imports
# Note: LogManager is foundation module - no internal dependencies


class LogLevel(Enum):
    """Enumeration of available log levels."""
    CRITICAL = "CRITICAL"
    ERROR = "ERROR"
    WARNING = "WARNING"
    INFO = "INFO"
    DEBUG = "DEBUG"
    TRACE = "TRACE"  # Custom level for detailed tracing


class LogDestination(Enum):
    """Enumeration of available log destinations."""
    CONSOLE = "console"
    FILE = "file"
    ROTATING_FILE = "rotating_file"
    MEMORY = "memory"
    DATABASE = "database"
    SPLASH_SCREEN = "splash_screen"


@dataclass
class LogEntry:
    """Structured log entry data class."""
    timestamp: datetime
    level: LogLevel
    logger_name: str
    message: str
    module: str
    function: str
    line_number: int
    thread_id: int
    process_id: int
    extra_data: Dict[str, Any] = None
    exception_info: Optional[str] = None
    
    def __post_init__(self):
        if self.extra_data is None:
            self.extra_data = {}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert log entry to dictionary."""
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        data['level'] = self.level.value
        return data
    
    def to_json(self) -> str:
        """Convert log entry to JSON string."""
        return json.dumps(self.to_dict(), default=str)
    
    def to_splash_format(self) -> List[str]:
        """Convert log entry to splash screen format with 11 lines.
        
        Returns:
            List of 11 strings in the exact format:
            ["timestamp", "level", "logger_name", "message", "module", 
             "function", "line_number", "thread_id", "process_id", 
             "extra_data", "exception_info"]
        """
        return [
            f'"timestamp": "{self.timestamp.isoformat()}"',          # timestamp
            f'"level": "{self.level.value}"',                        # level
            f'"logger_name": "{self.logger_name}"',                  # logger_name
            f'"message": "{self.message}"',                          # message
            f'"module": "{self.module}"',                            # module
            f'"function": "{self.function}"',                        # function
            f'"line_number": "{self.line_number}"',                  # line_number
            f'"thread_id": "{self.thread_id}"',                      # thread_id
            f'"process_id": "{self.process_id}"',                    # process_id
            f'"extra_data": "{json.dumps(self.extra_data)}"',        # extra_data
            f'"exception_info": "{self.exception_info or "None"}"'   # exception_info
        ]


@dataclass
class LoggerConfig:
    """Configuration for logger instances."""
    name: str
    level: LogLevel = LogLevel.INFO
    destinations: List[LogDestination] = None
    format_string: Optional[str] = None
    file_path: Optional[Path] = None
    max_file_size: int = 10 * 1024 * 1024  # 10MB
    backup_count: int = 5
    enable_console_colors: bool = True
    enable_structured_logging: bool = True
    
    def __post_init__(self):
        if self.destinations is None:
            self.destinations = [LogDestination.CONSOLE, LogDestination.FILE]


class LogFormatter(logging.Formatter):
    """Custom log formatter with color support and structured output."""
    
    # ANSI color codes
    COLORS = {
        'CRITICAL': '\033[95m',  # Magenta
        'ERROR': '\033[91m',     # Red
        'WARNING': '\033[93m',   # Yellow
        'INFO': '\033[92m',      # Green
        'DEBUG': '\033[94m',     # Blue
        'TRACE': '\033[96m',     # Cyan
        'RESET': '\033[0m'       # Reset
    }
    
    def __init__(self, enable_colors: bool = True, structured: bool = False):
        """
        Initialize the log formatter.
        
        Args:
            enable_colors: Whether to enable ANSI color codes
            structured: Whether to output structured JSON logs
        """
        self.enable_colors = enable_colors and sys.stdout.isatty()
        self.structured = structured
        
        if structured:
            super().__init__()
        else:
            format_string = (
                "%(asctime)s | %(levelname)-8s | %(name)-20s | "
                "%(module)s:%(funcName)s:%(lineno)d | %(message)s"
            )
            super().__init__(format_string, datefmt='%Y-%m-%d %H:%M:%S')
    
    def format(self, record: logging.LogRecord) -> str:
        """
        Format the log record.
        
        Args:
            record: Log record to format
            
        Returns:
            Formatted log string
        """
        if self.structured:
            return self._format_structured(record)
        else:
            return self._format_standard(record)
    
    def _format_structured(self, record: logging.LogRecord) -> str:
        """Format record as structured JSON."""
        log_entry = LogEntry(
            timestamp=datetime.fromtimestamp(record.created, tz=timezone.utc),
            level=LogLevel(record.levelname),
            logger_name=record.name,
            message=record.getMessage(),
            module=record.module,
            function=record.funcName,
            line_number=record.lineno,
            thread_id=record.thread,
            process_id=record.process,
            extra_data=getattr(record, 'extra_data', {}),
            exception_info=self.formatException(record.exc_info) if record.exc_info else None
        )
        return log_entry.to_json()
    
    def _format_standard(self, record: logging.LogRecord) -> str:
        """Format record as standard text with optional colors."""
        formatted = super().format(record)
        
        if self.enable_colors and record.levelname in self.COLORS:
            color = self.COLORS[record.levelname]
            reset = self.COLORS['RESET']
            formatted = f"{color}{formatted}{reset}"
        
        return formatted


class MemoryLogHandler(logging.Handler):
    """In-memory log handler for recent log storage."""
    
    def __init__(self, max_entries: int = 1000):
        """
        Initialize memory log handler.
        
        Args:
            max_entries: Maximum number of log entries to keep in memory
        """
        super().__init__()
        self.max_entries = max_entries
        self.entries: List[LogEntry] = []
        self._lock = threading.RLock()
    
    def emit(self, record: logging.LogRecord) -> None:
        """
        Emit a log record to memory storage.
        
        Args:
            record: Log record to store
        """
        try:
            log_entry = LogEntry(
                timestamp=datetime.fromtimestamp(record.created, tz=timezone.utc),
                level=LogLevel(record.levelname),
                logger_name=record.name,
                message=record.getMessage(),
                module=record.module,
                function=record.funcName,
                line_number=record.lineno,
                thread_id=record.thread,
                process_id=record.process,
                extra_data=getattr(record, 'extra_data', {}),
                exception_info=self.format(record) if record.exc_info else None
            )
            
            with self._lock:
                self.entries.append(log_entry)
                if len(self.entries) > self.max_entries:
                    self.entries.pop(0)
        except Exception:
            self.handleError(record)
    
    def get_recent_entries(self, count: Optional[int] = None, 
                          level: Optional[LogLevel] = None) -> List[LogEntry]:
        """
        Get recent log entries.
        
        Args:
            count: Maximum number of entries to return
            level: Filter by log level
            
        Returns:
            List of recent log entries
        """
        with self._lock:
            entries = self.entries.copy()
        
        if level:
            entries = [entry for entry in entries if entry.level == level]
        
        if count:
            entries = entries[-count:]
        
        return entries
    
    def clear(self) -> None:
        """Clear all stored log entries."""
        with self._lock:
            self.entries.clear()


class SplashScreenLogHandler(logging.Handler):
    """Log handler for splash screen display with observer pattern."""
    
    def __init__(self, max_entries: int = 50):
        """
        Initialize splash screen log handler.
        
        Args:
            max_entries: Maximum number of log entries to keep for display
        """
        super().__init__()
        self.max_entries = max_entries
        self.entries: List[LogEntry] = []
        self._observers: List[Callable[[LogEntry], None]] = []
        self._lock = threading.RLock()
    
    def emit(self, record: logging.LogRecord) -> None:
        """
        Emit a log record and notify observers.
        
        Args:
            record: Log record to process
        """
        try:
            # Format exception info if present
            exception_info = None
            if record.exc_info:
                exception_info = logging.Formatter().formatException(record.exc_info)
            
            log_entry = LogEntry(
                timestamp=datetime.fromtimestamp(record.created, tz=timezone.utc),
                level=LogLevel(record.levelname),
                logger_name=record.name,
                message=record.getMessage(),
                module=record.module,
                function=record.funcName,
                line_number=record.lineno,
                thread_id=record.thread,
                process_id=record.process,
                extra_data=getattr(record, 'extra_data', {}),
                exception_info=exception_info
            )
            
            with self._lock:
                # Store for recent access
                self.entries.append(log_entry)
                if len(self.entries) > self.max_entries:
                    self.entries.pop(0)
                
                # Notify all observers
                for observer in self._observers:
                    try:
                        observer(log_entry)
                    except Exception:
                        # Don't let observer errors break logging
                        pass
                        
        except Exception:
            self.handleError(record)
    
    def add_observer(self, observer: Callable[[LogEntry], None]) -> None:
        """
        Add an observer for real-time log updates.
        
        Args:
            observer: Function to call when new log entries are created
        """
        with self._lock:
            if observer not in self._observers:
                self._observers.append(observer)
    
    def remove_observer(self, observer: Callable[[LogEntry], None]) -> None:
        """
        Remove an observer.
        
        Args:
            observer: Function to remove from observers
        """
        with self._lock:
            if observer in self._observers:
                self._observers.remove(observer)
    
    def get_recent_entries(self, count: Optional[int] = None) -> List[LogEntry]:
        """
        Get recent log entries for splash screen display.
        
        Args:
            count: Maximum number of entries to return
            
        Returns:
            List of recent log entries
        """
        with self._lock:
            entries = self.entries.copy()
        
        if count:
            entries = entries[-count:]
        
        return entries
    
    def clear(self) -> None:
        """Clear all stored log entries and observers."""
        with self._lock:
            self.entries.clear()
            self._observers.clear()


class LogManager:
    """
    Centralized logging management system for MikroDok application.

    Provides comprehensive logging infrastructure with:
    - Multiple output destinations (console, file, memory, database)
    - Configurable log levels and formatting
    - Thread-safe operations
    - Structured logging support
    - Performance monitoring integration
    - Application state integration
    """

    _instance: Optional['LogManager'] = None
    _lock = threading.RLock()

    def __init__(self, app_state_manager: Optional[Any] = None):
        """
        Initialize the log manager.

        Args:
            app_state_manager: Application state manager for integration (optional)
        """
        self.app_state_manager = app_state_manager
        self.loggers: Dict[str, logging.Logger] = {}
        self.log_configs: Dict[str, LoggerConfig] = {}
        self._observers: List[Callable[[LogEntry], None]] = []

        # Lazy-loaded handlers for optimized startup performance
        self._memory_handler: Optional[MemoryLogHandler] = None
        self._splash_screen_handler: Optional[SplashScreenLogHandler] = None
        self._file_handlers: Dict[str, logging.Handler] = {}

        # Performance optimization flags
        self._handlers_initialized = False
        self._initialization_lock = threading.RLock()

        # Initialize core components
        self._setup_custom_levels()
        self._setup_default_logger()

    @classmethod
    def get_instance(cls, app_state_manager: Optional[Any] = None) -> 'LogManager':
        """
        Get singleton instance of LogManager.

        Args:
            app_state_manager: Application state manager for integration

        Returns:
            LogManager singleton instance
        """
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls(app_state_manager)
        return cls._instance

    def _setup_custom_levels(self) -> None:
        """Setup custom log levels."""
        # Add TRACE level
        logging.addLevelName(5, "TRACE")

        def trace(self, message, *args, **kwargs):
            if self.isEnabledFor(5):
                self._log(5, message, args, **kwargs)

        logging.Logger.trace = trace

    @property
    def memory_handler(self) -> MemoryLogHandler:
        """Lazy-loaded memory handler for optimized performance."""
        if self._memory_handler is None:
            with self._initialization_lock:
                if self._memory_handler is None:
                    self._memory_handler = MemoryLogHandler()
        return self._memory_handler

    @property
    def splash_screen_handler(self) -> SplashScreenLogHandler:
        """Lazy-loaded splash screen handler for optimized performance."""
        if self._splash_screen_handler is None:
            with self._initialization_lock:
                if self._splash_screen_handler is None:
                    self._splash_screen_handler = SplashScreenLogHandler()
        return self._splash_screen_handler

    def _setup_default_logger(self) -> None:
        """Setup default application logger with optimized initialization."""
        default_config = LoggerConfig(
            name="mikrodok",
            level=LogLevel.INFO,
            destinations=[LogDestination.CONSOLE, LogDestination.FILE, LogDestination.MEMORY, LogDestination.SPLASH_SCREEN],
            file_path=Path("logs/log.txt")
        )
        self.create_logger(default_config)

    def create_logger(self, config: LoggerConfig) -> logging.Logger:
        """
        Create a new logger with the specified configuration.

        Args:
            config: Logger configuration

        Returns:
            Configured logger instance
        """
        if config.name in self.loggers:
            return self.loggers[config.name]

        logger = logging.getLogger(config.name)
        logger.setLevel(getattr(logging, config.level.value))

        # Clear any existing handlers
        logger.handlers.clear()

        # Setup handlers based on destinations
        for destination in config.destinations:
            handler = self._create_handler(destination, config)
            if handler:
                logger.addHandler(handler)

        # Store configuration and logger
        self.log_configs[config.name] = config
        self.loggers[config.name] = logger

        return logger

    def _create_handler(self, destination: LogDestination,
                       config: LoggerConfig) -> Optional[logging.Handler]:
        """
        Create a log handler for the specified destination.

        Args:
            destination: Log destination type
            config: Logger configuration

        Returns:
            Configured log handler or None
        """
        handler = None

        if destination == LogDestination.CONSOLE:
            handler = logging.StreamHandler(sys.stdout)
            formatter = LogFormatter(
                enable_colors=config.enable_console_colors,
                structured=config.enable_structured_logging
            )
            handler.setFormatter(formatter)

        elif destination == LogDestination.FILE:
            if config.file_path:
                # Ensure log directory exists
                config.file_path.parent.mkdir(parents=True, exist_ok=True)
                handler = logging.FileHandler(config.file_path, encoding='utf-8')
                # Use structured JSON format to include all required fields for compliance
                formatter = LogFormatter(enable_colors=False, structured=True)
                handler.setFormatter(formatter)
                # Force immediate flushing for file handler
                handler.flush = lambda: handler.stream.flush()

        elif destination == LogDestination.ROTATING_FILE:
            if config.file_path:
                config.file_path.parent.mkdir(parents=True, exist_ok=True)
                handler = logging.handlers.RotatingFileHandler(
                    config.file_path,
                    maxBytes=config.max_file_size,
                    backupCount=config.backup_count,
                    encoding='utf-8'
                )
                # Use structured JSON format to include all required fields for compliance
                formatter = LogFormatter(enable_colors=False, structured=True)
                handler.setFormatter(formatter)

        elif destination == LogDestination.MEMORY:
            handler = self.memory_handler
            
        elif destination == LogDestination.SPLASH_SCREEN:
            handler = self.splash_screen_handler

        if handler:
            handler.setLevel(getattr(logging, config.level.value))

        return handler

    def _ensure_initialized(self) -> None:
        """Ensure the log manager is properly initialized with optimized checks."""
        # This method ensures that the default logger is set up
        # It's called by get_logger to make sure initialization is complete
        if "mikrodok" not in self.loggers:
            self._setup_default_logger()

    def optimize_performance(self) -> None:
        """
        Optimize logging performance by pre-initializing handlers and clearing caches.

        This method should be called after application startup to improve runtime performance.
        """
        try:
            with self._initialization_lock:
                # Pre-initialize lazy-loaded handlers
                _ = self.memory_handler
                _ = self.splash_screen_handler

                # Clear any unused file handlers
                active_files = set()
                for config in self.log_configs.values():
                    if config.file_path:
                        active_files.add(str(config.file_path))

                # Remove unused file handlers to free memory
                unused_handlers = []
                for key in self._file_handlers.keys():
                    if not any(active_file in key for active_file in active_files):
                        unused_handlers.append(key)

                for key in unused_handlers:
                    handler = self._file_handlers.pop(key)
                    if hasattr(handler, 'close'):
                        handler.close()

                self._handlers_initialized = True

        except Exception as e:
            # Don't let optimization errors break logging
            print(f"Logging optimization warning: {e}")

    def get_performance_stats(self) -> Dict[str, Any]:
        """
        Get performance statistics for logging operations.

        Returns:
            Dictionary containing performance metrics
        """
        stats = {
            'total_loggers': len(self.loggers),
            'total_configs': len(self.log_configs),
            'cached_file_handlers': len(self._file_handlers),
            'memory_handler_entries': len(self.memory_handler.entries) if self._memory_handler else 0,
            'splash_handler_entries': len(self.splash_screen_handler.entries) if self._splash_screen_handler else 0,
            'handlers_initialized': self._handlers_initialized,
            'observers_count': len(self._observers)
        }

        return stats

    def get_logger(self, name: str = "mikrodok") -> logging.Logger:
        """
        Get a logger by name.

        Args:
            name: Logger name

        Returns:
            Logger instance
        """
        if name not in self.loggers:
            # Create logger with same configuration as default logger
            default_config = self.log_configs.get("mikrodok")
            if default_config:
                # Use same destinations as default logger
                config = LoggerConfig(
                    name=name,
                    level=default_config.level,
                    destinations=default_config.destinations.copy(),
                    file_path=default_config.file_path,
                    max_file_size=default_config.max_file_size,
                    backup_count=default_config.backup_count,
                    enable_console_colors=default_config.enable_console_colors,
                    enable_structured_logging=default_config.enable_structured_logging
                )
                return self.create_logger(config)
            else:
                # Fallback to basic config
                config = LoggerConfig(name=name)
                return self.create_logger(config)

        return self.loggers[name]

    # Convenience methods for direct logging
    def debug(self, message: str, logger_name: str = "mikrodok", **kwargs) -> None:
        """Log a debug message."""
        logger = self.get_logger(logger_name)
        if logger:
            logger.debug(message, **kwargs)

    def info(self, message: str, logger_name: str = "mikrodok", **kwargs) -> None:
        """Log an info message."""
        logger = self.get_logger(logger_name)
        if logger:
            logger.info(message, **kwargs)

    def warning(self, message: str, logger_name: str = "mikrodok", **kwargs) -> None:
        """Log a warning message."""
        logger = self.get_logger(logger_name)
        if logger:
            logger.warning(message, **kwargs)

    def error(self, message: str, logger_name: str = "mikrodok", **kwargs) -> None:
        """Log an error message."""
        logger = self.get_logger(logger_name)
        if logger:
            logger.error(message, **kwargs)

    def critical(self, message: str, logger_name: str = "mikrodok", **kwargs) -> None:
        """Log a critical message."""
        logger = self.get_logger(logger_name)
        if logger:
            logger.critical(message, **kwargs)

    def get_log_level(self, logger_name: str = "mikrodok") -> str:
        """Get the current log level for a logger."""
        logger = self.get_logger(logger_name)
        if logger:
            return logging.getLevelName(logger.level)
        return "UNKNOWN"

    def set_log_level(self, name: str, level: LogLevel) -> None:
        """
        Set log level for a specific logger.

        Args:
            name: Logger name
            level: New log level
        """
        if name in self.loggers:
            logger = self.loggers[name]
            logger.setLevel(getattr(logging, level.value))

            # Update handlers
            for handler in logger.handlers:
                handler.setLevel(getattr(logging, level.value))

            # Update configuration
            if name in self.log_configs:
                self.log_configs[name].level = level

    def add_log_observer(self, observer: Callable[[LogEntry], None]) -> None:
        """
        Add a log observer for real-time log monitoring.

        Args:
            observer: Function to call when new log entries are created
        """
        if observer not in self._observers:
            self._observers.append(observer)

    def remove_log_observer(self, observer: Callable[[LogEntry], None]) -> None:
        """
        Remove a log observer.

        Args:
            observer: Function to remove from observers
        """
        if observer in self._observers:
            self._observers.remove(observer)

    def get_recent_logs(self, count: Optional[int] = None,
                       level: Optional[LogLevel] = None) -> List[LogEntry]:
        """
        Get recent log entries from memory.

        Args:
            count: Maximum number of entries to return
            level: Filter by log level

        Returns:
            List of recent log entries
        """
        return self.memory_handler.get_recent_entries(count, level)

    def clear_memory_logs(self) -> None:
        """Clear all log entries from memory."""
        self.memory_handler.clear()

    def get_splash_screen_handler(self):
        """Get the splash screen log handler."""
        return getattr(self, 'splash_screen_handler', None)

    def add_splash_screen_observer(self, observer):
        """Add a splash screen log observer."""
        handler = self.get_splash_screen_handler()
        if handler:
            handler.add_observer(observer)

    def remove_splash_screen_observer(self, observer):
        """Remove a splash screen log observer."""
        handler = self.get_splash_screen_handler()
        if handler:
            handler.remove_observer(observer)

    def get_splash_screen_logs(self, count=None):
        """Get recent log entries for splash screen display."""
        handler = self.get_splash_screen_handler()
        if handler:
            return handler.get_recent_entries(count)
        return []

    def log_performance_metric(self, operation: str, duration: float,
                             extra_data: Optional[Dict[str, Any]] = None) -> None:
        """
        Log a performance metric.

        Args:
            operation: Name of the operation
            duration: Duration in seconds
            extra_data: Additional metric data
        """
        logger = self.get_logger("performance")

        metric_data = {
            "operation": operation,
            "duration_seconds": duration,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

        if extra_data:
            metric_data.update(extra_data)

        # Add extra_data to the log record
        old_factory = logging.getLogRecordFactory()

        def record_factory(*args, **kwargs):
            record = old_factory(*args, **kwargs)
            record.extra_data = metric_data
            return record

        logging.setLogRecordFactory(record_factory)

        try:
            logger.info(f"Performance: {operation} completed in {duration:.3f}s")
        finally:
            logging.setLogRecordFactory(old_factory)

    @contextmanager
    def performance_timer(self, operation: str,
                         extra_data: Optional[Dict[str, Any]] = None):
        """
        Context manager for timing operations.

        Args:
            operation: Name of the operation
            extra_data: Additional metric data
        """
        start_time = datetime.now()
        try:
            yield
        finally:
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            self.log_performance_metric(operation, duration, extra_data)

    def log_system_event(self, event_type: str, message: str,
                        extra_data: Optional[Dict[str, Any]] = None) -> None:
        """
        Log a system event.

        Args:
            event_type: Type of system event
            message: Event message
            extra_data: Additional event data
        """
        logger = self.get_logger("system")

        event_data = {
            "event_type": event_type,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

        if extra_data:
            event_data.update(extra_data)

        # Add extra_data to the log record
        old_factory = logging.getLogRecordFactory()

        def record_factory(*args, **kwargs):
            record = old_factory(*args, **kwargs)
            record.extra_data = event_data
            return record

        logging.setLogRecordFactory(record_factory)

        try:
            logger.info(f"System Event [{event_type}]: {message}")
        finally:
            logging.setLogRecordFactory(old_factory)

    def log_error_with_context(self, error: Exception, context: Dict[str, Any],
                              logger_name: str = "mikrodok") -> None:
        """
        Log an error with additional context information.

        Args:
            error: Exception that occurred
            context: Additional context information
            logger_name: Name of the logger to use
        """
        logger = self.get_logger(logger_name)

        error_data = {
            "error_type": type(error).__name__,
            "error_message": str(error),
            "context": context,
            "traceback": traceback.format_exc(),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

        # Add extra_data to the log record
        old_factory = logging.getLogRecordFactory()

        def record_factory(*args, **kwargs):
            record = old_factory(*args, **kwargs)
            record.extra_data = error_data
            return record

        logging.setLogRecordFactory(record_factory)

        try:
            logger.error(f"Error in {context.get('operation', 'unknown')}: {error}")
        finally:
            logging.setLogRecordFactory(old_factory)

    def get_logger_stats(self) -> Dict[str, Any]:
        """
        Get statistics about all loggers.

        Returns:
            Dictionary containing logger statistics
        """
        stats = {
            "total_loggers": len(self.loggers),
            "memory_entries": len(self.memory_handler.entries),
            "loggers": {}
        }

        for name, logger in self.loggers.items():
            config = self.log_configs.get(name)
            stats["loggers"][name] = {
                "level": logger.level,
                "handlers": len(logger.handlers),
                "destinations": [dest.value for dest in config.destinations] if config else [],
                "effective_level": logging.getLevelName(logger.getEffectiveLevel())
            }

        return stats

    def shutdown(self) -> None:
        """Shutdown the logging system gracefully."""
        # Log shutdown event
        try:
            self.log_system_event("shutdown", "Logging system shutting down")
        except Exception:
            pass

        # Close all handlers
        for logger in self.loggers.values():
            for handler in logger.handlers[:]:
                try:
                    handler.close()
                    logger.removeHandler(handler)
                except Exception:
                    pass

        # Clear memory
        self.memory_handler.clear()

        # Clear observers
        self._observers.clear()

        # Reset singleton
        with self._lock:
            LogManager._instance = None


# Global convenience functions
def get_log_manager(app_state_manager: Optional[Any] = None) -> LogManager:
    """
    Get the global LogManager instance.

    Args:
        app_state_manager: Application state manager for integration

    Returns:
        LogManager singleton instance
    """
    return LogManager.get_instance(app_state_manager)


def get_logger(name: str = "mikrodok") -> logging.Logger:
    """
    Get a logger instance.

    Args:
        name: Logger name

    Returns:
        Logger instance
    """
    return get_log_manager().get_logger(name)


def log_performance(operation: str, duration: float,
                   extra_data: Optional[Dict[str, Any]] = None) -> None:
    """
    Log a performance metric.

    Args:
        operation: Name of the operation
        duration: Duration in seconds
        extra_data: Additional metric data
    """
    get_log_manager().log_performance_metric(operation, duration, extra_data)


def performance_timer(operation: str, extra_data: Optional[Dict[str, Any]] = None):
    """
    Context manager for timing operations.

    Args:
        operation: Name of the operation
        extra_data: Additional metric data
    """
    return get_log_manager().performance_timer(operation, extra_data)
